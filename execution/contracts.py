"""
Wire contracts for the external execution boundary.

Path: execution/contracts.py

EDGE-TF is the decision engine. Broker connectivity lives in a separate
execution service (its own repo, its own runtime). These are the only shapes
that cross the wire between the two:

    ExecutionInstruction  - what an approved trade looks like when the
                            execution service pulls it. Carries the trade id
                            and the hashes the approval was bound to, so the
                            handoff is auditable end to end.
    ExecutionReport       - what the execution service posts back after the
                            broker responds (ack, partial fill, fill, cancel,
                            rejection).
    BrokerAccountSnapshot - balances and positions reported back so the
                            decision engine always reasons over real state.

Nothing here talks to a broker. Nothing here may be authored by a model: an
instruction is only ever derived from a TransactionRecord in state APPROVED.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExecutionReportStatus(str, Enum):
    """Broker-side outcomes the execution service may report."""

    ACCEPTED = "ACCEPTED"                  # broker acknowledged, nothing filled yet
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"                  # broker refused the order
    ERROR = "ERROR"                        # transport/auth/unexpected failure


class ExecutionInstruction(BaseModel):
    """
    A single approved trade, serialized for the execution service.

    `trade_id` is the authoritative audit key (the transaction intent id).
    `instruction_id` additionally binds the approved economics, so claiming a
    mutated or re-approved record yields a different instruction id.
    """

    instruction_id: str
    trade_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: float = Field(gt=0)
    order_type: Literal["LIMIT", "MARKET"] = "LIMIT"
    limit_price: Optional[float] = Field(default=None, ge=0)
    estimated_notional: float = Field(ge=0)
    currency: str = "USD"

    thesis_id: str
    strategy_module: str
    rationale: Optional[str] = None

    intent_hash: str
    approved_fingerprint: str
    approval_expires_at: datetime
    max_slippage_bps: float = 25.0

    idempotency_key: str
    issued_at: datetime = Field(default_factory=_utcnow)


class Fill(BaseModel):
    quantity: float = Field(gt=0)
    price: float = Field(ge=0)
    at: datetime = Field(default_factory=_utcnow)


class ExecutionReport(BaseModel):
    """Broker outcome for one trade, reported by the execution service."""

    trade_id: str
    instruction_id: Optional[str] = None
    broker: str
    broker_order_id: Optional[str] = None
    status: ExecutionReportStatus
    filled_quantity: float = Field(default=0, ge=0)
    average_price: Optional[float] = Field(default=None, ge=0)
    fills: List[Fill] = Field(default_factory=list)
    message: Optional[str] = None
    reported_at: datetime = Field(default_factory=_utcnow)


class BrokerPosition(BaseModel):
    symbol: str
    quantity: float
    market_value: Optional[float] = None
    average_cost: Optional[float] = None


class BrokerAccountSnapshot(BaseModel):
    """Balances and positions at one broker, as reported by the executor."""

    broker: str
    account_id: str
    cash: float = 0.0
    positions: List[BrokerPosition] = Field(default_factory=list)
    as_of: datetime = Field(default_factory=_utcnow)
    source: str = "EXTERNAL_EXECUTION_SERVICE"


__all__ = [
    "BrokerAccountSnapshot",
    "BrokerPosition",
    "ExecutionInstruction",
    "ExecutionReport",
    "ExecutionReportStatus",
    "Fill",
]
