"""
Transaction data contracts.

Path: transactions/schemas.py

Separates *intent* (which a generative layer may compose) from *execution*
(which only deterministic code may authorize). A TradeIntent is never
executable; it must be validated, previewed, approved against a binding
hash, and revalidated before an OrderRequest is constructed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

GeneratedBy = Literal[
    "USER",
    "EDGE_TF",
    "HEDGE_ENGINE",
    "GAMMA_ECHO",
    "CONGRESSIONAL_ALPHA",
    "LEGAL_ARB",
    "SENTIMENT_ARB",
]


class TransactionState(str, Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    REJECTED = "REJECTED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REVALIDATING = "REVALIDATING"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"
    KILL_SWITCHED = "KILL_SWITCHED"


class OptionLeg(BaseModel):
    """A single option contract leg. Options are never reduced to ticker+quantity."""

    underlying: str
    option_symbol: str
    call_put: Literal["CALL", "PUT"]
    strike: float = Field(gt=0)
    expiration: date
    side: Literal["BUY", "SELL"]
    position_effect: Literal["OPEN", "CLOSE"]
    quantity: int = Field(gt=0)
    limit_price: float = Field(ge=0)


class TradeIntent(BaseModel):
    """
    A proposed transaction. May be authored by a model, a strategy module or a
    human. Carries thesis provenance so that no position exists without a
    recorded reason and a recorded invalidation condition.
    """

    intent_id: str
    strategy_module: str
    underlying: str
    instrument_type: Literal["ETF", "EQUITY", "OPTION"]
    direction: Literal["BUY", "SELL"]
    thesis_id: str
    catalyst_id: Optional[str] = None
    catalyst_date: Optional[date] = None
    execution_buffer_days: Optional[int] = None
    requested_notional: Optional[float] = None
    requested_quantity: Optional[float] = None
    max_loss: float = Field(gt=0)
    maximum_holding_period_days: Optional[int] = None
    limit_price: Optional[float] = None
    profit_targets: List[float] = Field(default_factory=list)
    invalidation_condition: Optional[str] = None
    exit_plan: Optional[str] = None
    legs: List[OptionLeg] = Field(default_factory=list)
    generated_by: GeneratedBy = "USER"
    rationale: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _size_or_notional(self) -> "TradeIntent":
        if self.instrument_type == "OPTION":
            if not self.legs:
                raise ValueError("OPTION intent requires at least one leg")
        elif self.requested_notional is None and self.requested_quantity is None:
            raise ValueError("intent requires requested_notional or requested_quantity")
        return self

    def economic_fingerprint(self) -> Dict[str, Any]:
        """The fields whose mutation must invalidate a prior human approval."""
        return {
            "intent_id": self.intent_id,
            "underlying": self.underlying,
            "instrument_type": self.instrument_type,
            "direction": self.direction,
            "thesis_id": self.thesis_id,
            "requested_notional": self.requested_notional,
            "requested_quantity": self.requested_quantity,
            "limit_price": self.limit_price,
            "max_loss": self.max_loss,
            "legs": [
                leg.model_dump(mode="json")
                for leg in sorted(self.legs, key=lambda l: l.option_symbol)
            ],
        }


class ValidationFinding(BaseModel):
    code: str
    severity: Literal["ERROR", "WARNING"]
    message: str
    field: Optional[str] = None


class ValidationResult(BaseModel):
    passed: bool
    findings: List[ValidationFinding] = Field(default_factory=list)

    @property
    def errors(self) -> List[ValidationFinding]:
        return [f for f in self.findings if f.severity == "ERROR"]

    @property
    def missing_fields(self) -> List[str]:
        return [f.field for f in self.errors if f.field]


class RiskDecision(BaseModel):
    """Deterministic verdict produced outside the generative layer."""

    passed: bool
    reasons: List[str] = Field(default_factory=list)
    record_hash: str
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Quote(BaseModel):
    symbol: str
    bid: float = Field(ge=0)
    ask: float = Field(ge=0)
    last: float = Field(ge=0)
    timestamp: datetime

    @property
    def mid(self) -> float:
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return self.last

    @property
    def spread_pct(self) -> float:
        mid = self.mid
        if mid <= 0:
            return 1.0
        return (self.ask - self.bid) / mid


class TransactionPreview(BaseModel):
    """The object a human actually reviews. Approval binds to `intent_hash`."""

    intent_id: str
    intent_hash: str
    symbol: str
    side: str
    quantity: float
    estimated_price: float
    estimated_notional: float
    estimated_portfolio_weight_before: float
    estimated_portfolio_weight_after: float
    current_option_allocation: Optional[float] = None
    post_trade_option_allocation: Optional[float] = None
    expected_max_loss: float
    spread_pct: float
    liquidity_status: Literal["PASS", "WARN", "FAIL"]
    strategy_state: str
    risk_gate_passed: bool
    risk_reasons: List[str] = Field(default_factory=list)
    validation: ValidationResult
    quote_timestamp: datetime
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rationale: Optional[str] = None
    invalidation_condition: Optional[str] = None
    approval_required: bool = True


class Approval(BaseModel):
    approval_id: str
    intent_id: str
    intent_hash: str
    approver_id: str
    approved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: int = 120

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return (now - self.approved_at).total_seconds() > self.ttl_seconds


class TransactionRecord(BaseModel):
    """Append-only lifecycle record for one intent."""

    intent_id: str
    state: TransactionState
    intent: TradeIntent
    preview: Optional[TransactionPreview] = None
    approval: Optional[Approval] = None
    approved_fingerprint: Optional[str] = None
    broker_response: Optional[Dict[str, Any]] = None
    history: List[Dict[str, Any]] = Field(default_factory=list)


def canonical_hash(payload: Dict[str, Any]) -> str:
    """Order-independent, whitespace-independent SHA256 of a JSON payload."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compute_intent_hash(
    intent: TradeIntent,
    *,
    user_id: str,
    risk_record_hash: str,
    preview_timestamp: datetime,
    estimated_price: float,
) -> str:
    """
    Binds a human approval to the exact reviewed economics. Any mutation by the
    generative layer (42 -> 420 shares) changes the hash and voids the approval.
    """
    return canonical_hash(
        {
            "user_id": user_id,
            "risk_record_hash": risk_record_hash,
            "preview_timestamp": preview_timestamp.isoformat(),
            "estimated_price": round(float(estimated_price), 6),
            **intent.economic_fingerprint(),
        }
    )


__all__ = [
    "Approval",
    "GeneratedBy",
    "OptionLeg",
    "Quote",
    "RiskDecision",
    "TradeIntent",
    "TransactionPreview",
    "TransactionRecord",
    "TransactionState",
    "ValidationFinding",
    "ValidationResult",
    "canonical_hash",
    "compute_intent_hash",
]
