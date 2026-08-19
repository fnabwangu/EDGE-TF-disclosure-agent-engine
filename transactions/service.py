"""
Transaction service - the only path from intent to broker.

Path: transactions/service.py

    UI / orchestrator
        -> TransactionService
        -> validator + RiskEvaluator
        -> preview + binding intent hash
        -> human approval
        -> revalidation (fresh quote, fresh risk, kill switch, unchanged hash)
        -> OrderRouter
        -> broker

No caller may skip a stage; each stage is a whitelisted state transition.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol

from execution.order_router import OrderRequest, OrderRouter
from transactions.preview import (
    MAX_ACCEPTABLE_SPREAD_PCT,
    PortfolioSnapshot,
    build_preview,
)
from transactions.schemas import (
    Approval,
    Quote,
    RiskDecision,
    TradeIntent,
    TransactionPreview,
    TransactionRecord,
    TransactionState,
    canonical_hash,
)
from transactions.state_machine import assert_transition
from transactions.validator import validate_intent

MATERIAL_PRICE_DRIFT_PCT = 0.005


class QuoteProvider(Protocol):
    def get_quote(self, symbol: str) -> Quote: ...


class PortfolioProvider(Protocol):
    def snapshot(self) -> PortfolioSnapshot: ...


class RiskEvaluator(Protocol):
    def evaluate(self, intent: TradeIntent, portfolio: PortfolioSnapshot) -> RiskDecision: ...


class TransactionError(RuntimeError):
    pass


class TransactionService:
    """Stateful coordinator holding one record per intent."""

    def __init__(
        self,
        *,
        quotes: QuoteProvider,
        portfolio: PortfolioProvider,
        risk: RiskEvaluator,
        router: OrderRouter,
        approval_ttl_seconds: int = 120,
    ):
        self.quotes = quotes
        self.portfolio = portfolio
        self.risk = risk
        self.router = router
        self.approval_ttl_seconds = approval_ttl_seconds
        self._records: Dict[str, TransactionRecord] = {}

    # -- lifecycle ---------------------------------------------------------

    def register_draft(self, intent: TradeIntent) -> TransactionRecord:
        if intent.intent_id in self._records:
            raise TransactionError(f"intent {intent.intent_id} already registered")
        record = TransactionRecord(intent_id=intent.intent_id, state=TransactionState.DRAFT, intent=intent)
        self._log(record, "REGISTERED", {"generated_by": intent.generated_by})
        self._records[intent.intent_id] = record
        return record

    def create_preview(self, intent_id: str, *, user_id: str, strategy_state: str = "UNKNOWN") -> TransactionRecord:
        record = self.get(intent_id)
        self._set_state(record, TransactionState.VALIDATING)

        if self._kill_switch_locked():
            self._set_state(record, TransactionState.KILL_SWITCHED, {"reason": "KILL_SWITCH_LOCKED"})
            return record

        validation = validate_intent(record.intent)
        portfolio = self.portfolio.snapshot()
        risk = self.risk.evaluate(record.intent, portfolio)
        quote = self.quotes.get_quote(self._quote_symbol(record.intent))

        preview = build_preview(
            record.intent,
            quote=quote,
            portfolio=portfolio,
            risk=risk,
            validation=validation,
            user_id=user_id,
            strategy_state=strategy_state,
        )
        record.preview = preview

        blockers = self._blockers(preview)
        if blockers:
            self._set_state(record, TransactionState.REJECTED, {"blockers": blockers})
        else:
            self._set_state(record, TransactionState.AWAITING_APPROVAL, {"intent_hash": preview.intent_hash})
        return record

    def approve(self, intent_id: str, *, intent_hash: str, approver_id: str) -> TransactionRecord:
        record = self.get(intent_id)
        if record.preview is None:
            raise TransactionError("cannot approve an intent that has no preview")
        if intent_hash != record.preview.intent_hash:
            self._set_state(record, TransactionState.APPROVAL_EXPIRED, {"reason": "INTENT_HASH_MISMATCH"})
            return record

        approval = Approval(
            approval_id=str(uuid.uuid4()),
            intent_id=intent_id,
            intent_hash=intent_hash,
            approver_id=approver_id,
            ttl_seconds=self.approval_ttl_seconds,
        )
        record.approval = approval
        self._set_state(record, TransactionState.APPROVED, {"approval_id": approval.approval_id})
        return record

    def execute(self, intent_id: str, *, user_id: str) -> TransactionRecord:
        record = self.get(intent_id)
        approval = record.approval
        prior = record.preview
        if approval is None or prior is None:
            raise TransactionError("execution requires an approved preview")

        self._set_state(record, TransactionState.REVALIDATING)

        if self._kill_switch_locked():
            self._set_state(record, TransactionState.KILL_SWITCHED, {"reason": "KILL_SWITCH_LOCKED"})
            return record
        if approval.is_expired():
            self._set_state(record, TransactionState.APPROVAL_EXPIRED, {"reason": "APPROVAL_TTL_ELAPSED"})
            return record

        validation = validate_intent(record.intent)
        portfolio = self.portfolio.snapshot()
        risk = self.risk.evaluate(record.intent, portfolio)
        quote = self.quotes.get_quote(self._quote_symbol(record.intent))
        fresh = build_preview(
            record.intent,
            quote=quote,
            portfolio=portfolio,
            risk=risk,
            validation=validation,
            user_id=user_id,
            strategy_state=prior.strategy_state,
        )

        drift = self._material_drift(prior, fresh)
        if drift:
            record.preview = fresh
            self._set_state(record, TransactionState.APPROVAL_EXPIRED, {"drift": drift})
            return record

        blockers = self._blockers(fresh)
        if blockers:
            record.preview = fresh
            self._set_state(record, TransactionState.REJECTED, {"blockers": blockers})
            return record

        record.preview = fresh
        self._set_state(record, TransactionState.SUBMITTING)
        request = OrderRequest(
            symbol=fresh.symbol,
            quantity=fresh.quantity,
            side=fresh.side,
            order_type="LIMIT",
            limit_price=fresh.estimated_price,
        )
        response = self.router.route(request, execution_permitted=True)
        record.broker_response = response

        if str(response.get("status", "")).upper() == "REJECTED":
            self._set_state(record, TransactionState.REJECTED, {"broker": response})
        else:
            self._set_state(record, TransactionState.SUBMITTED, {"broker": response})
        return record

    def cancel(self, intent_id: str, *, reason: str = "USER_CANCELLED") -> TransactionRecord:
        record = self.get(intent_id)
        target = (
            TransactionState.CANCEL_REQUESTED
            if record.state in {TransactionState.SUBMITTED, TransactionState.PARTIALLY_FILLED}
            else TransactionState.CANCELLED
        )
        self._set_state(record, target, {"reason": reason})
        return record

    def get(self, intent_id: str) -> TransactionRecord:
        record = self._records.get(intent_id)
        if record is None:
            raise TransactionError(f"unknown intent {intent_id}")
        return record

    def records(self) -> List[TransactionRecord]:
        return list(self._records.values())

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _quote_symbol(intent: TradeIntent) -> str:
        if intent.instrument_type == "OPTION" and intent.legs:
            return intent.legs[0].option_symbol
        return intent.underlying

    @staticmethod
    def _blockers(preview: TransactionPreview) -> List[str]:
        blockers: List[str] = []
        if not preview.validation.passed:
            blockers.extend(f.code for f in preview.validation.errors)
        if not preview.risk_gate_passed:
            blockers.extend(preview.risk_reasons or ["RISK_GATE_FAILED"])
        if preview.liquidity_status == "FAIL":
            blockers.append(f"SPREAD_EXCEEDS_{MAX_ACCEPTABLE_SPREAD_PCT:.2%}")
        if preview.quantity <= 0:
            blockers.append("QUANTITY_NOT_EXECUTABLE")
        return blockers

    @staticmethod
    def _material_drift(prior: TransactionPreview, fresh: TransactionPreview) -> Optional[Dict[str, Any]]:
        if prior.intent_hash == fresh.intent_hash:
            return None
        drift: Dict[str, Any] = {}
        if prior.estimated_price > 0:
            move = abs(fresh.estimated_price - prior.estimated_price) / prior.estimated_price
            if move > MATERIAL_PRICE_DRIFT_PCT:
                drift["price_drift_pct"] = move
        if fresh.liquidity_status != prior.liquidity_status:
            drift["liquidity_status"] = fresh.liquidity_status
        if fresh.risk_gate_passed != prior.risk_gate_passed:
            drift["risk_gate_passed"] = fresh.risk_gate_passed
        if fresh.quantity != prior.quantity:
            drift["quantity"] = fresh.quantity
        # Hash changed for a reason not captured above: treat as material.
        return drift or {"intent_hash": "CHANGED"}

    def _kill_switch_locked(self) -> bool:
        switch = getattr(self.router, "kill_switch", None)
        return bool(switch is not None and switch.is_locked)

    def _set_state(self, record: TransactionRecord, target: TransactionState, detail: Optional[Dict[str, Any]] = None) -> None:
        assert_transition(record.state, target)
        record.state = target
        self._log(record, target.value, detail or {})

    @staticmethod
    def _log(record: TransactionRecord, event: str, detail: Dict[str, Any]) -> None:
        entry = {
            "at": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "detail": detail,
        }
        entry["entry_hash"] = canonical_hash(entry)
        record.history.append(entry)


__all__ = [
    "MATERIAL_PRICE_DRIFT_PCT",
    "PortfolioProvider",
    "QuoteProvider",
    "RiskEvaluator",
    "TransactionError",
    "TransactionService",
]
