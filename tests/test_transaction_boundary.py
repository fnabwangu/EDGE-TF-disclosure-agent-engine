"""Tests for the intent -> preview -> approval -> execution boundary."""

from datetime import date, datetime, timedelta, timezone

import pytest

from execution.order_router import OrderRouter
from risk.kill_switch import EmergencyKillSwitchEngine, TripTriggerType
from transactions.preview import PortfolioSnapshot
from transactions.schemas import (
    OptionLeg,
    Quote,
    RiskDecision,
    TradeIntent,
    TransactionState,
)
from transactions.service import TransactionService, TransactionError
from transactions.state_machine import IllegalTransition, can_transition
from transactions.validator import validate_intent


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
        return PortfolioSnapshot(nav=1_000_000.0, positions_market_value={"SMH": 41_000.0}, option_market_value=0.0)


class FakeRisk:
    def __init__(self, passed: bool = True, reasons=None):
        self.passed = passed
        self.reasons = reasons or []

    def evaluate(self, intent, portfolio) -> RiskDecision:
        return RiskDecision(passed=self.passed, reasons=list(self.reasons), record_hash="risk-hash-1")


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
        "profit_targets": [1.15, 1.30],
        "rationale": "Independent adoption across 4 manager clusters.",
    }
    payload.update(overrides)
    return TradeIntent.model_validate(payload)


def make_service(*, risk=None, quotes=None, kill_switch=None, broker=None) -> TransactionService:
    broker = broker or FakeBroker()
    router = OrderRouter(broker=broker, kill_switch=kill_switch)
    return TransactionService(
        quotes=quotes or FakeQuotes(spread=0.005),
        portfolio=FakePortfolio(),
        risk=risk or FakeRisk(),
        router=router,
    )


def test_happy_path_reaches_submitted():
    broker = FakeBroker()
    service = make_service(broker=broker)
    service.register_draft(make_intent())

    record = service.create_preview("intent-1", user_id="op-1", strategy_state="CONFIRMED_ADOPTION")
    assert record.state is TransactionState.AWAITING_APPROVAL
    assert record.preview.liquidity_status == "PASS"

    service.approve("intent-1", intent_hash=record.preview.intent_hash, approver_id="op-1")
    final = service.execute("intent-1", user_id="op-1")

    assert final.state is TransactionState.SUBMITTED
    assert broker.submitted[0].quantity == 42


def test_mutating_size_after_approval_voids_the_approval():
    broker = FakeBroker()
    service = make_service(broker=broker)
    service.register_draft(make_intent())
    record = service.create_preview("intent-1", user_id="op-1")
    service.approve("intent-1", intent_hash=record.preview.intent_hash, approver_id="op-1")

    record.intent.requested_quantity = 420  # generative layer silently ups the size

    final = service.execute("intent-1", user_id="op-1")
    assert final.state is TransactionState.APPROVAL_EXPIRED
    assert broker.submitted == []


def test_approval_with_stale_hash_is_rejected():
    service = make_service()
    service.register_draft(make_intent())
    service.create_preview("intent-1", user_id="op-1")

    record = service.approve("intent-1", intent_hash="not-the-reviewed-hash", approver_id="op-1")
    assert record.state is TransactionState.APPROVAL_EXPIRED
    assert record.approval is None


def test_risk_failure_blocks_before_approval():
    service = make_service(risk=FakeRisk(passed=False, reasons=["RULE_22E4_ILLIQUID_CAP"]))
    service.register_draft(make_intent())
    record = service.create_preview("intent-1", user_id="op-1")

    assert record.state is TransactionState.REJECTED
    assert "RULE_22E4_ILLIQUID_CAP" in record.history[-1]["detail"]["blockers"]


def test_wide_spread_blocks_execution():
    service = make_service(quotes=FakeQuotes(spread=0.05))
    service.register_draft(make_intent())
    record = service.create_preview("intent-1", user_id="op-1")

    assert record.preview.liquidity_status == "FAIL"
    assert record.state is TransactionState.REJECTED


def test_kill_switch_halts_preview():
    switch = EmergencyKillSwitchEngine()
    switch.trip(TripTriggerType.DRAWDOWN_LIMIT, "drawdown breach")
    service = make_service(kill_switch=switch)
    service.register_draft(make_intent())

    record = service.create_preview("intent-1", user_id="op-1")
    assert record.state is TransactionState.KILL_SWITCHED


def test_execution_requires_an_approved_preview():
    service = make_service()
    service.register_draft(make_intent())
    with pytest.raises(TransactionError):
        service.execute("intent-1", user_id="op-1")


def test_state_machine_forbids_draft_to_submitted():
    assert not can_transition(TransactionState.DRAFT, TransactionState.SUBMITTED)
    with pytest.raises(IllegalTransition):
        from transactions.state_machine import assert_transition

        assert_transition(TransactionState.DRAFT, TransactionState.SUBMITTED)


def test_option_expiration_must_clear_catalyst_plus_buffer():
    today = date(2026, 1, 2)
    leg = OptionLeg(
        underlying="SMH",
        option_symbol="SMH  260220C00250000",
        call_put="CALL",
        strike=250.0,
        expiration=today + timedelta(days=20),
        side="BUY",
        position_effect="OPEN",
        quantity=5,
        limit_price=4.20,
    )
    intent = make_intent(
        intent_id="intent-opt",
        instrument_type="OPTION",
        requested_quantity=None,
        legs=[leg],
        catalyst_id="earnings-q1",
        catalyst_date=today + timedelta(days=15),
        execution_buffer_days=14,
        maximum_holding_period_days=45,
    )

    result = validate_intent(intent, today=today)
    assert not result.passed
    assert "EXPIRATION_BEFORE_CATALYST_BUFFER" in {f.code for f in result.errors}


def test_option_intent_missing_catalyst_is_incomplete():
    today = date(2026, 1, 2)
    leg = OptionLeg(
        underlying="SMH",
        option_symbol="SMH  260619C00250000",
        call_put="CALL",
        strike=250.0,
        expiration=today + timedelta(days=168),
        side="BUY",
        position_effect="OPEN",
        quantity=5,
        limit_price=4.20,
    )
    intent = make_intent(intent_id="intent-opt-2", instrument_type="OPTION", requested_quantity=None, legs=[leg])

    result = validate_intent(intent, today=today)
    assert not result.passed
    assert {"CATALYST_MISSING", "CATALYST_DATE_MISSING"} <= {f.code for f in result.errors}
