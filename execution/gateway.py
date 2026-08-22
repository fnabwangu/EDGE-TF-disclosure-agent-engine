"""
Execution gateway - the decision-side boundary for the external executor.

Path: execution/gateway.py

The execution service (separate repo, separate runtime) talks to EDGE-TF
through exactly this surface:

    list_instructions()   -> only trades in state APPROVED, unexpired,
                             kill-switch clear, serialized as
                             ExecutionInstruction with explicit trade ids
    claim(trade_id, ...)  -> revalidates and hands one trade off; atomic,
                             a second claim can never succeed
    report(...)           -> folds a broker outcome back into the record
                             and the append-only portfolio ledger
    record_snapshot(...)  -> ingests balances/positions reported by the
                             executor
    portfolio_state()     -> latest known broker state + open trades

It composes the existing TransactionService (intent -> preview -> approval ->
revalidation) and adds nothing to the trust surface: no broker credentials,
no model-authored orders, no way around the approval state machine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from execution.contracts import (
    BrokerAccountSnapshot,
    ExecutionInstruction,
    ExecutionReport,
)
from execution.portfolio import PortfolioStateStore
from risk.kill_switch import EmergencyKillSwitchEngine
from transactions.schemas import TransactionRecord, TransactionState, canonical_hash
from transactions.service import TransactionError, TransactionService
from transactions.state_machine import IllegalTransition


class ExecutionGatewayError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExecutionGateway:
    def __init__(
        self,
        *,
        transactions: TransactionService,
        portfolio_store: Optional[PortfolioStateStore] = None,
        kill_switch: Optional[EmergencyKillSwitchEngine] = None,
        max_slippage_bps: float = 25.0,
    ):
        self.transactions = transactions
        self.portfolio_store = portfolio_store or PortfolioStateStore()
        self.kill_switch = kill_switch
        self.max_slippage_bps = max_slippage_bps

    # -- trade decision API (executor pulls) --------------------------------

    def list_instructions(self) -> List[ExecutionInstruction]:
        """Every trade currently cleared for the execution service to claim."""
        return [self._to_instruction(record) for record in self.transactions.executable()]

    def claim(self, trade_id: str, *, executor_id: str) -> ExecutionInstruction:
        """Atomically claim one approved trade for external execution."""
        record = self._record_or_raise(trade_id)

        if record.state is not TransactionState.APPROVED:
            raise ExecutionGatewayError(
                "NOT_CLAIMABLE",
                f"trade {trade_id} is {record.state.value}; only APPROVED trades can be claimed",
            )

        try:
            record = self.transactions.claim_for_external_execution(trade_id, executor_id=executor_id)
        except IllegalTransition as exc:
            raise ExecutionGatewayError("CLAIM_CONFLICT", str(exc)) from exc

        if record.state is not TransactionState.SUBMITTED:
            raise ExecutionGatewayError(
                "REVALIDATION_FAILED",
                f"trade {trade_id} failed revalidation at claim time: {record.state.value}",
            )
        return self._to_instruction(record)

    # -- execution reporting (executor pushes) -------------------------------

    def report(self, report: ExecutionReport) -> Dict[str, Any]:
        record = self._record_or_raise(report.trade_id)
        updated = self.transactions.record_execution_report(report.trade_id, report)
        self.portfolio_store.record_report(report)
        return {
            "trade_id": report.trade_id,
            "status": report.status.value,
            "transaction_state": updated.state.value,
            "recorded": True,
        }

    def record_snapshot(self, snapshot: BrokerAccountSnapshot) -> Dict[str, Any]:
        self.portfolio_store.record_snapshot(snapshot)
        return {
            "broker": snapshot.broker,
            "account_id": snapshot.account_id,
            "as_of": snapshot.as_of.isoformat(),
            "recorded": True,
        }

    # -- portfolio state API --------------------------------------------------

    def portfolio_state(self) -> Dict[str, Any]:
        latest = self.portfolio_store.latest_snapshot()
        return {
            "latest_snapshot": latest.model_dump(mode="json") if latest else None,
            "positions_by_broker": self.portfolio_store.positions_by_broker(),
            "open_trades": [
                record.intent_id
                for record in self.transactions.records()
                if record.state in _OPEN_STATES
            ],
            "kill_switch_locked": self._locked(),
            "as_of": _utcnow().isoformat(),
        }

    # -- internals ------------------------------------------------------------

    def _record_or_raise(self, trade_id: str) -> TransactionRecord:
        try:
            return self.transactions.get(trade_id)
        except TransactionError as exc:
            raise ExecutionGatewayError("UNKNOWN_TRADE", str(exc)) from exc

    def _locked(self) -> bool:
        if self.kill_switch is not None:
            return self.kill_switch.is_locked
        router_switch = getattr(self.transactions.router, "kill_switch", None)
        return bool(router_switch is not None and router_switch.is_locked)

    def _to_instruction(self, record: TransactionRecord) -> ExecutionInstruction:
        preview = record.preview
        approval = record.approval
        if preview is None or approval is None:
            raise ExecutionGatewayError(
                "NOT_CLAIMABLE", f"trade {record.intent_id} has no approved preview"
            )
        fingerprint = record.approved_fingerprint or canonical_hash(
            record.intent.economic_fingerprint()
        )
        expires_at = datetime.fromtimestamp(
            approval.approved_at.timestamp() + approval.ttl_seconds, tz=timezone.utc
        )
        return ExecutionInstruction(
            instruction_id=f"{record.intent_id}:{fingerprint[:12]}",
            trade_id=record.intent_id,
            symbol=preview.symbol,
            side=preview.side,  # type: ignore[arg-type]
            quantity=preview.quantity,
            order_type="LIMIT",
            limit_price=record.intent.limit_price or preview.estimated_price,
            estimated_notional=preview.estimated_notional,
            thesis_id=record.intent.thesis_id,
            strategy_module=record.intent.strategy_module,
            rationale=record.intent.rationale,
            intent_hash=preview.intent_hash,
            approved_fingerprint=fingerprint,
            approval_expires_at=expires_at,
            max_slippage_bps=self.max_slippage_bps,
            idempotency_key=canonical_hash(
                {"trade_id": record.intent_id, "approved_fingerprint": fingerprint}
            ),
        )


_OPEN_STATES = {
    TransactionState.SUBMITTED,
    TransactionState.PARTIALLY_FILLED,
    TransactionState.CANCEL_REQUESTED,
}


__all__ = ["ExecutionGateway", "ExecutionGatewayError"]
