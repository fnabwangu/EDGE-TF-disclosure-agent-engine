"""Tests for the external execution boundary (gateway + transaction handoff)."""

from datetime import datetime, timedelta, timezone

import pytest

from execution.contracts import (
    BrokerAccountSnapshot,
    BrokerPosition,
    ExecutionReport,
    ExecutionReportStatus,
)
from execution.gateway import ExecutionGateway, ExecutionGatewayError
from execution.order_router import OrderRouter
from execution.portfolio import PortfolioStateStore
from risk.kill_switch import EmergencyKillSwitchEngine, TripTriggerType
from transactions.preview import PortfolioSnapshot
from transactions.schemas import Quote, RiskDecision, TradeIntent, TransactionState
from transactions.service import TransactionService


class FakeQuotes:
    def __init__(self, price: float = 100.0, spread: float = 0.02):
        self.price = price
        self.spread = spread

    def get_quote(self, symbol: str) -> Quote:
        half = self.price * self.spread / 2
        return Quote(
            symbol=symbol,
            bid=self.price - half,
            ask=self.price + half,
            last=self.price,
            timestamp=datetime(2026, 1, 2, 15, 30, tzinfo=timezone.utc),
        )


class FakePortfolio:
    def snapshot(self) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            nav=1_000_000.0, positions_market_value={"SMH": 41_000.0}, option_market_value=0.0
        )


class FakeRisk:
    def evaluate(self, intent, portfolio) -> RiskDecision:
        return RiskDecision(passed=True, reasons=[], record_hash="risk-hash-1")


class FakeBroker:
    def __init__(self):
        self.submitted = []

    def submit_order(self, request):
        self.submitted.append(request)
        return {"status": "ACCEPTED", "order_id": "BRK-1"}


def make_intent(**overrides) -> TradeIntent:
    payload = {
        "intent_id": "intent-1",
        "strategy_module": "EDGE_TF",
        "underlying": "SMH",
        "instrument_type": "ETF",
        "direction": "BUY",
        "thesis_id": "thesis-1",
        "requested_quantity": 42,
        "max_loss": 5_000.0,
        "invalidation_condition": "IAV falls below 0.40",
        "exit_plan": "Scale out on 2 targets; hard stop at max loss.",
        "rationale": "Independent adoption across 4 manager clusters.",
    }
    payload.update(overrides)
    return TradeIntent.model_validate(payload)


@pytest.fixture()
def stack(tmp_path):
    kill_switch = EmergencyKillSwitchEngine()
    broker = FakeBroker()
    service = TransactionService(
        quotes=FakeQuotes(),
        portfolio=FakePortfolio(),
        risk=FakeRisk(),
        router=OrderRouter(broker=broker, kill_switch=kill_switch),
        approval_ttl_seconds=600,
    )
    gateway = ExecutionGateway(
        transactions=service,
        portfolio_store=PortfolioStateStore(tmp_path / "portfolio"),
        kill_switch=kill_switch,
    )
    return {"service": service, "gateway": gateway, "broker": broker, "kill_switch": kill_switch}


def approve_intent(service: TransactionService, intent_id: str = "intent-1") -> None:
    service.register_draft(make_intent(intent_id=intent_id))
    record = service.create_preview(intent_id, user_id="op-1")
    assert record.state is TransactionState.AWAITING_APPROVAL
    service.approve(intent_id, intent_hash=record.preview.intent_hash, approver_id="op-1")


def test_only_approved_trades_are_listed(stack):
    service, gateway = stack["service"], stack["gateway"]
    approve_intent(service, "intent-1")
    service.register_draft(make_intent(intent_id="intent-2"))  # never approved

    orders = gateway.list_instructions()

    assert [o.trade_id for o in orders] == ["intent-1"]
    assert orders[0].symbol == "SMH"
    assert orders[0].quantity == 42
    assert orders[0].idempotency_key


def test_claim_hands_off_without_touching_the_broker(stack):
    service, gateway, broker = stack["service"], stack["gateway"], stack["broker"]
    approve_intent(service)

    instruction = gateway.claim("intent-1", executor_id="exec-1")
    record = service.get("intent-1")

    assert instruction.trade_id == "intent-1"
    assert instruction.intent_hash == record.preview.intent_hash
    assert instruction.instruction_id.startswith("intent-1:")
    assert record.state is TransactionState.SUBMITTED
    assert record.broker_response["status"] == "HANDED_OFF"
    assert record.broker_response["executor_id"] == "exec-1"
    assert broker.submitted == []  # the in-process broker was never called


def test_a_second_claim_can_never_succeed(stack):
    gateway = stack["gateway"]
    approve_intent(stack["service"])
    gateway.claim("intent-1", executor_id="exec-1")

    with pytest.raises(ExecutionGatewayError) as err:
        gateway.claim("intent-1", executor_id="exec-2")
    assert err.value.code == "NOT_CLAIMABLE"


def test_expired_approval_cannot_be_claimed(stack):
    service, gateway = stack["service"], stack["gateway"]
    approve_intent(service)
    approval = service.get("intent-1").approval
    approval.approved_at -= timedelta(seconds=approval.ttl_seconds + 1)

    assert gateway.list_instructions() == []
    with pytest.raises(ExecutionGatewayError) as err:
        gateway.claim("intent-1", executor_id="exec-1")
    assert err.value.code == "REVALIDATION_FAILED"
    assert service.get("intent-1").state is TransactionState.APPROVAL_EXPIRED


def test_kill_switch_blocks_listing_and_claim(stack):
    service, gateway, kill_switch = stack["service"], stack["gateway"], stack["kill_switch"]
    approve_intent(service)
    kill_switch.trip(trigger=TripTriggerType.MANUAL_OPERATOR_OVERRIDE, reason="operator halt")

    assert gateway.list_instructions() == []
    with pytest.raises(ExecutionGatewayError) as err:
        gateway.claim("intent-1", executor_id="exec-1")
    assert err.value.code == "REVALIDATION_FAILED"
    assert service.get("intent-1").state is TransactionState.KILL_SWITCHED


def test_fill_report_moves_record_to_filled_and_is_stored(stack):
    service, gateway = stack["service"], stack["gateway"]
    approve_intent(service)
    instruction = gateway.claim("intent-1", executor_id="exec-1")

    result = gateway.report(
        ExecutionReport(
            trade_id="intent-1",
            instruction_id=instruction.instruction_id,
            broker="schwab",
            broker_order_id="SCH-9001",
            status=ExecutionReportStatus.FILLED,
            filled_quantity=42,
            average_price=100.10,
        )
    )

    assert result["transaction_state"] == "FILLED"
    assert service.get("intent-1").state is TransactionState.FILLED
    stored = gateway.portfolio_store.reports(trade_id="intent-1")
    assert len(stored) == 1
    assert stored[0].broker_order_id == "SCH-9001"


def test_partial_fills_then_fill(stack):
    service, gateway = stack["service"], stack["gateway"]
    approve_intent(service)
    gateway.claim("intent-1", executor_id="exec-1")

    for filled in (20, 22):
        status = (
            ExecutionReportStatus.PARTIALLY_FILLED if filled == 20 else ExecutionReportStatus.FILLED
        )
        gateway.report(
            ExecutionReport(
                trade_id="intent-1",
                broker="schwab",
                status=status,
                filled_quantity=filled,
                average_price=100.05,
            )
        )

    assert service.get("intent-1").state is TransactionState.FILLED


def test_out_of_order_report_is_logged_not_raised(stack):
    service, gateway = stack["service"], stack["gateway"]
    approve_intent(service)  # approved, never claimed

    gateway.report(
        ExecutionReport(trade_id="intent-1", broker="schwab", status=ExecutionReportStatus.FILLED)
    )

    record = service.get("intent-1")
    assert record.state is TransactionState.APPROVED
    assert any("EXECUTION_REPORT_IGNORED" in entry["event"] for entry in record.history)


def test_report_for_unknown_trade_raises(stack):
    with pytest.raises(ExecutionGatewayError) as err:
        stack["gateway"].report(
            ExecutionReport(trade_id="nope", broker="schwab", status=ExecutionReportStatus.FILLED)
        )
    assert err.value.code == "UNKNOWN_TRADE"


def test_portfolio_snapshot_round_trip(stack):
    gateway = stack["gateway"]
    ack = gateway.record_snapshot(
        BrokerAccountSnapshot(
            broker="schwab",
            account_id="acct-1",
            cash=250_000.0,
            positions=[BrokerPosition(symbol="SMH", quantity=500, market_value=50_050.0)],
        )
    )

    assert ack["recorded"] is True
    state = gateway.portfolio_state()
    assert state["latest_snapshot"]["broker"] == "schwab"
    assert state["positions_by_broker"] == {"schwab": {"SMH": 500}}
    assert state["kill_switch_locked"] is False


def test_open_trades_appear_in_portfolio_state(stack):
    gateway = stack["gateway"]
    approve_intent(stack["service"])
    gateway.claim("intent-1", executor_id="exec-1")

    assert gateway.portfolio_state()["open_trades"] == ["intent-1"]


# -- HTTP transport (skipped when httpx is unavailable) ----------------------


@pytest.fixture()
def http(stack, monkeypatch):
    pytest.importorskip("httpx")
    from starlette.testclient import TestClient

    from api.execution_app import app, set_gateway

    set_gateway(stack["gateway"])
    monkeypatch.delenv("EDGE_EXECUTION_TOKEN", raising=False)
    return TestClient(app)


def test_http_fails_closed_without_configured_token(http):
    response = http.get("/execution/orders")
    assert response.status_code == 401
    assert "no EDGE_EXECUTION_TOKEN" in response.json()["detail"]


def test_http_claim_and_report_round_trip(http, stack, monkeypatch):
    monkeypatch.setenv("EDGE_EXECUTION_TOKEN", "secret")
    approve_intent(stack["service"])

    orders = http.get("/execution/orders", headers={"Authorization": "Bearer secret"}).json()
    assert [o["trade_id"] for o in orders["orders"]] == ["intent-1"]

    claimed = http.post(
        "/execution/orders/intent-1/claim",
        json={"executor_id": "exec-1"},
        headers={"Authorization": "Bearer secret"},
    )
    assert claimed.status_code == 200
    assert claimed.json()["trade_id"] == "intent-1"

    conflict = http.post(
        "/execution/orders/intent-1/claim",
        json={"executor_id": "exec-2"},
        headers={"Authorization": "Bearer secret"},
    )
    assert conflict.status_code == 409

    reported = http.post(
        "/execution/orders/intent-1/reports",
        json={
            "trade_id": "intent-1",
            "broker": "schwab",
            "status": "FILLED",
            "filled_quantity": 42,
            "average_price": 100.10,
            "broker_order_id": "SCH-9001",
        },
        headers={"Authorization": "Bearer secret"},
    )
    assert reported.status_code == 200
    assert reported.json()["transaction_state"] == "FILLED"

    state = http.get(
        "/execution/portfolio/state", headers={"Authorization": "Bearer secret"}
    ).json()
    assert state["open_trades"] == []
