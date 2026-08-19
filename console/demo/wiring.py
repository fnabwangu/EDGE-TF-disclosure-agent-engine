"""
Demo wiring for the interaction layer.

Path: console/demo/wiring.py

Assembles a complete, runnable stack with simulated market data and a dry-run
broker so the project/session/approval flow can be operated end to end. Only
the data providers are fake; the workbench, transaction, approval, UI and
guardrail code is exactly what runs in production.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from approvals.schemas import ActionKind, ActionRequest, RiskTier
from approvals.service import ApprovalService
from execution.order_router import OrderRouter
from risk.kill_switch import EmergencyKillSwitchEngine
from transactions.preview import PortfolioSnapshot
from transactions.schemas import Quote, RiskDecision, TradeIntent, canonical_hash
from transactions.service import TransactionService
from workbench.schemas import EventKind, Evidence, IdeaState, Thesis, WatchCondition
from workbench.store import WorkbenchStore

DEMO_LOG = Path("data/workbench/demo_events.jsonl")

SEED_PRICES = {"NLR": 92.40, "URA": 41.15, "SMH": 268.80, "SOXX": 244.10}


class SimulatedQuotes:
    """Deterministic-by-default quotes with an optional drift knob."""

    def __init__(self, prices: Optional[Dict[str, float]] = None, jitter: float = 0.0):
        self.prices = dict(prices or SEED_PRICES)
        self.jitter = jitter
        self.spread_pct = 0.004

    def bump(self, symbol: str, pct: float) -> None:
        self.prices[symbol] = self.prices.get(symbol, 100.0) * (1 + pct)

    def get_quote(self, symbol: str) -> Quote:
        base = self.prices.get(symbol, 100.0)
        if self.jitter:
            base *= 1 + random.uniform(-self.jitter, self.jitter)
        half = base * self.spread_pct / 2
        return Quote(
            symbol=symbol,
            bid=round(base - half, 4),
            ask=round(base + half, 4),
            last=round(base, 4),
            timestamp=datetime.now(timezone.utc),
        )


class SimulatedPortfolio:
    def __init__(self, nav: float = 5_000_000.0):
        self.nav = nav
        self.positions: Dict[str, float] = {"SMH": 205_000.0, "NLR": 61_000.0}
        self.option_market_value = 48_000.0

    def snapshot(self) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            nav=self.nav,
            positions_market_value=dict(self.positions),
            option_market_value=self.option_market_value,
        )


class DemoRiskEvaluator:
    """Stands in for RiskGovernor: caps single-name weight and total option sleeve."""

    def __init__(self, max_position_weight: float = 0.10, max_option_allocation: float = 0.02):
        self.max_position_weight = max_position_weight
        self.max_option_allocation = max_option_allocation

    def evaluate(self, intent: TradeIntent, portfolio: PortfolioSnapshot) -> RiskDecision:
        reasons: List[str] = []
        current = portfolio.weight_of(intent.underlying)
        if current > self.max_position_weight:
            reasons.append(
                f"POSITION_WEIGHT_CAP: {intent.underlying} at {current:.2%} exceeds {self.max_position_weight:.0%}"
            )
        if intent.instrument_type == "OPTION" and portfolio.option_allocation > self.max_option_allocation:
            reasons.append(
                f"OPTION_SLEEVE_CAP: {portfolio.option_allocation:.2%} exceeds {self.max_option_allocation:.0%}"
            )
        return RiskDecision(
            passed=not reasons,
            reasons=reasons,
            record_hash=canonical_hash(
                {"underlying": intent.underlying, "nav": portfolio.nav, "weight": round(current, 8)}
            ),
        )


class DryRunBroker:
    """Accepts orders and records them; never contacts a venue."""

    def __init__(self):
        self.submitted: List[Any] = []

    def submit_order(self, request) -> Dict[str, Any]:
        self.submitted.append(request)
        return {
            "status": "ACCEPTED",
            "order_id": f"DRYRUN-{len(self.submitted):04d}",
            "symbol": request.symbol,
            "quantity": request.quantity,
            "limit_price": request.limit_price,
        }


@dataclass
class DemoStack:
    workbench: WorkbenchStore
    transactions: TransactionService
    approvals: ApprovalService
    quotes: SimulatedQuotes
    portfolio: SimulatedPortfolio
    broker: DryRunBroker
    kill_switch: EmergencyKillSwitchEngine
    project_ids: List[str] = field(default_factory=list)
    applied_config: Dict[str, Any] = field(default_factory=dict)


def build_stack(*, log_path: Path | str = DEMO_LOG, fresh: bool = True) -> DemoStack:
    log_path = Path(log_path)
    if fresh and log_path.exists():
        log_path.unlink()

    workbench = WorkbenchStore(log_path=log_path)
    quotes = SimulatedQuotes()
    portfolio = SimulatedPortfolio()
    broker = DryRunBroker()
    kill_switch = EmergencyKillSwitchEngine()

    transactions = TransactionService(
        quotes=quotes,
        portfolio=portfolio,
        risk=DemoRiskEvaluator(),
        router=OrderRouter(broker=broker, kill_switch=kill_switch),
        approval_ttl_seconds=600,
    )
    approvals = ApprovalService(workbench=workbench)
    stack = DemoStack(
        workbench=workbench,
        transactions=transactions,
        approvals=approvals,
        quotes=quotes,
        portfolio=portfolio,
        broker=broker,
        kill_switch=kill_switch,
    )
    _register_executors(stack)
    return stack


def _register_executors(stack: DemoStack) -> None:
    def apply_risk_parameter(request: ActionRequest) -> Dict[str, Any]:
        stack.applied_config.update(request.payload)
        return {"applied": request.payload}

    def onboard_source(request: ActionRequest) -> Dict[str, Any]:
        return {"onboarded": request.payload.get("source"), "at": datetime.now(timezone.utc).isoformat()}

    def promote_thesis(request: ActionRequest) -> Dict[str, Any]:
        stack.workbench.append(
            EventKind.STATE_CHANGED,
            project_id=request.project_id,
            actor="APPROVAL_SERVICE",
            subject_id=request.thesis_id,
            payload={"state": IdeaState.CONFIRMED.value, "reason": f"approved:{request.request_id}"},
        )
        return {"thesis_id": request.thesis_id, "state": IdeaState.CONFIRMED.value}

    stack.approvals.register_executor(ActionKind.RISK_PARAMETER_CHANGE, apply_risk_parameter)
    stack.approvals.register_executor(ActionKind.DATA_SOURCE_ONBOARDING, onboard_source)
    stack.approvals.register_executor(ActionKind.THESIS_PROMOTION, promote_thesis)

    stack.approvals.register_validator(
        ActionKind.RISK_PARAMETER_CHANGE,
        lambda req: (
            ["ILLIQUID_CAP_ABOVE_STATUTORY_MAX"]
            if float(req.payload.get("rule_22e4_illiquid_cap", 0)) > 0.15
            else []
        ),
    )


def seed(stack: DemoStack) -> DemoStack:
    """Populate two projects with history so continuity has something to restore."""
    nuclear = stack.workbench.create_project(
        project_id="proj-nuclear",
        name="Nuclear power",
        mandate="Institutional adoption of nuclear generation and fuel cycle exposure.",
        tags=["energy", "thematic"],
    )
    semis = stack.workbench.create_project(
        project_id="proj-semis",
        name="Semiconductors",
        mandate="Independent manager accumulation across the semi supply chain.",
        tags=["technology"],
    )
    stack.project_ids = [nuclear.project_id, semis.project_id]

    # --- prior session in Nuclear -------------------------------------------
    past = stack.workbench.open_session(project_id=nuclear.project_id, actor="op-1")
    thesis = _add_thesis(
        stack,
        project_id=nuclear.project_id,
        session_id=past.session_id,
        thesis_id="th-nuclear",
        title="Nuclear adoption is broadening",
        claim="Independent managers are accumulating nuclear exposure ahead of consensus.",
        universe=["NLR", "URA"],
        invalidation="IAV falls below 0.40 or breadth narrows to a single cluster",
        state=IdeaState.EVIDENCED,
    )
    _add_evidence(stack, nuclear.project_id, past.session_id, thesis.thesis_id, [
        ("SUPPORTS", "Four independent manager clusters raised normalized weight", "iav", 0.71),
        ("SUPPORTS", "Creation baskets show persistent NLR accumulation", "aqd_zscore", 2.42),
        ("CONTRADICTS", "Two of the four clusters share a common sub-advisor", "independence", 0.58),
    ])
    stack.workbench.append(
        EventKind.WATCH_CONDITION_SET,
        project_id=nuclear.project_id,
        session_id=past.session_id,
        subject_id=thesis.thesis_id,
        payload=WatchCondition(
            condition_id="wc-iav-floor",
            metric="iav",
            operator="<",
            threshold=0.40,
            on_breach="DEMOTE",
            description="Adoption velocity collapse",
        ).model_dump(mode="json"),
    )
    stack.workbench.append(
        EventKind.NOTE_ADDED,
        project_id=nuclear.project_id,
        session_id=past.session_id,
        payload={"kind": "OPEN_QUESTION", "text": "Is URA breadth genuine or one allocator recycling?"},
    )

    # --- prior session in Semis ---------------------------------------------
    semis_session = stack.workbench.open_session(project_id=semis.project_id, actor="op-1")
    _add_thesis(
        stack,
        project_id=semis.project_id,
        session_id=semis_session.session_id,
        thesis_id="th-semis",
        title="Semis accumulation is late-cycle",
        claim="Breadth is narrowing while price persists; adoption may be exhausted.",
        universe=["SMH", "SOXX"],
        invalidation="Breadth re-broadens above 5 clusters",
        state=IdeaState.CONTESTED,
    )

    _seed_pending_work(stack, nuclear.project_id, past.session_id, thesis.thesis_id)
    return stack


def _add_thesis(
    stack: DemoStack,
    *,
    project_id: str,
    session_id: str,
    thesis_id: str,
    title: str,
    claim: str,
    universe: List[str],
    invalidation: str,
    state: IdeaState,
) -> Thesis:
    thesis = Thesis(
        thesis_id=thesis_id,
        project_id=project_id,
        title=title,
        claim=claim,
        universe=universe,
        invalidation_condition=invalidation,
        conviction=0.62,
    )
    stack.workbench.append(
        EventKind.THESIS_CREATED,
        project_id=project_id,
        session_id=session_id,
        actor="op-1",
        subject_id=thesis_id,
        payload=thesis.model_dump(mode="json"),
    )
    for step in _path_to(state):
        stack.workbench.append(
            EventKind.STATE_CHANGED,
            project_id=project_id,
            session_id=session_id,
            subject_id=thesis_id,
            payload={"state": step.value, "reason": "seeded history"},
        )
    return thesis


def _path_to(state: IdeaState) -> List[IdeaState]:
    routes = {
        IdeaState.RESEARCHING: [IdeaState.RESEARCHING],
        IdeaState.EVIDENCED: [IdeaState.RESEARCHING, IdeaState.EVIDENCED],
        IdeaState.CONTESTED: [IdeaState.RESEARCHING, IdeaState.CONTESTED],
        IdeaState.CONFIRMED: [IdeaState.RESEARCHING, IdeaState.EVIDENCED, IdeaState.CONFIRMED],
    }
    return routes.get(state, [IdeaState.RESEARCHING])


def _add_evidence(stack: DemoStack, project_id: str, session_id: str, thesis_id: str, rows) -> None:
    for stance, claim, metric, value in rows:
        evidence = Evidence(
            evidence_id=str(uuid.uuid4()),
            thesis_id=thesis_id,
            claim=claim,
            stance=stance,
            metric=metric,
            value=value,
            source_uri="https://www.sec.gov/edgar",
        )
        stack.workbench.append(
            EventKind.EVIDENCE_ADDED if stance == "SUPPORTS" else EventKind.COUNTER_EVIDENCE_ADDED,
            project_id=project_id,
            session_id=session_id,
            subject_id=thesis_id,
            payload=evidence.model_dump(mode="json"),
        )


def _seed_pending_work(stack: DemoStack, project_id: str, session_id: str, thesis_id: str) -> None:
    """Leave a trade and two workflow actions mid-flight, so continuity has to restore them."""
    intent = TradeIntent(
        intent_id="intent-nlr-1",
        strategy_module="EDGE_TF",
        underlying="NLR",
        instrument_type="ETF",
        direction="BUY",
        thesis_id=thesis_id,
        requested_notional=120_000.0,
        max_loss=18_000.0,
        maximum_holding_period_days=180,
        profit_targets=[1.18, 1.35],
        invalidation_condition="IAV falls below 0.40",
        exit_plan="Scale out at both targets; exit fully on invalidation.",
        rationale="Independent adoption across four manager clusters with persistent normalized accumulation.",
        generated_by="EDGE_TF",
    )
    stack.transactions.register_draft(intent)
    stack.workbench.append(
        EventKind.INTENT_LINKED,
        project_id=project_id,
        session_id=session_id,
        subject_id=thesis_id,
        payload={"intent_id": intent.intent_id, "state": "DRAFT"},
    )
    record = stack.transactions.create_preview(
        intent.intent_id, user_id="op-1", strategy_state="CONFIRMED_ADOPTION"
    )
    stack.workbench.append(
        EventKind.INTENT_STATE_CHANGED,
        project_id=project_id,
        session_id=session_id,
        payload={"intent_id": intent.intent_id, "state": record.state.value},
    )

    stack.approvals.propose(
        ActionRequest(
            request_id="req-promote-nuclear",
            project_id=project_id,
            kind=ActionKind.THESIS_PROMOTION,
            title="Promote nuclear thesis to CONFIRMED",
            summary="Breadth and persistence thresholds met across four independent clusters.",
            payload={"thesis_id": thesis_id},
            risk_tier=RiskTier.MEDIUM,
            thesis_id=thesis_id,
            consequences=["Unlocks position sizing at full conviction weight."],
        ),
        session_id=session_id,
    )
    stack.approvals.submit_for_approval("req-promote-nuclear", session_id=session_id)

    stack.approvals.propose(
        ActionRequest(
            request_id="req-illiquid-cap",
            project_id=project_id,
            kind=ActionKind.RISK_PARAMETER_CHANGE,
            title="Raise illiquid cap to 12%",
            summary="Widen Rule 22e-4 illiquid budget to accommodate fuel-cycle names.",
            payload={"rule_22e4_illiquid_cap": 0.12},
            risk_tier=RiskTier.MEDIUM,
            reversible=False,
            consequences=["Applies to every sleeve.", "Irreversible without a second change request."],
            requested_by="EDGE_TF",
        ),
        session_id=session_id,
    )
    stack.approvals.submit_for_approval("req-illiquid-cap", session_id=session_id)


def option_intent_missing_fields(thesis_id: str) -> Dict[str, Any]:
    """An intentionally incomplete option intent, to show validation highlighting."""
    return {
        "intent_id": f"intent-opt-{uuid.uuid4().hex[:6]}",
        "strategy_module": "HEDGE_ENGINE",
        "underlying": "URA",
        "instrument_type": "OPTION",
        "direction": "BUY",
        "thesis_id": thesis_id,
        "max_loss": 9_000.0,
        "legs": [
            {
                "underlying": "URA",
                "option_symbol": "URA   261218C00050000",
                "call_put": "CALL",
                "strike": 50.0,
                "expiration": str(date.today() + timedelta(days=30)),
                "side": "BUY",
                "position_effect": "OPEN",
                "quantity": 20,
                "limit_price": 1.85,
            }
        ],
        "catalyst_id": "nrc-decision",
        "catalyst_date": str(date.today() + timedelta(days=25)),
        "execution_buffer_days": 14,
    }


__all__ = [
    "DemoStack",
    "DemoRiskEvaluator",
    "DryRunBroker",
    "SimulatedPortfolio",
    "SimulatedQuotes",
    "build_stack",
    "option_intent_missing_fields",
    "seed",
]
