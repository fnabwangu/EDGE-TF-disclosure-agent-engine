"""
Approval data contracts.

Path: approvals/schemas.py

Generalizes the trade-approval pattern to any consequential workflow action.
A model may compose an ActionRequest; only a human may approve one, and the
approval binds to a hash of exactly what was shown.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from transactions.schemas import canonical_hash


class ActionKind(str, Enum):
    TRADE_EXECUTION = "TRADE_EXECUTION"
    THESIS_PROMOTION = "THESIS_PROMOTION"
    THESIS_INVALIDATION = "THESIS_INVALIDATION"
    CAPITAL_ALLOCATION = "CAPITAL_ALLOCATION"
    REBALANCE_SCHEDULE_CHANGE = "REBALANCE_SCHEDULE_CHANGE"
    RISK_PARAMETER_CHANGE = "RISK_PARAMETER_CHANGE"
    DATA_SOURCE_ONBOARDING = "DATA_SOURCE_ONBOARDING"
    KILL_SWITCH_RESET = "KILL_SWITCH_RESET"
    PROJECT_ARCHIVE = "PROJECT_ARCHIVE"
    STRATEGY_ACTIVATION = "STRATEGY_ACTIVATION"


class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ApprovalState(str, Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    REJECTED = "REJECTED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REVALIDATING = "REVALIDATING"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ActionRequest(BaseModel):
    """A proposed change to the world, awaiting deterministic checks and a human."""

    request_id: str
    project_id: str
    kind: ActionKind
    title: str
    summary: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    risk_tier: RiskTier = RiskTier.MEDIUM
    reversible: bool = True
    consequences: List[str] = Field(default_factory=list)
    thesis_id: Optional[str] = None
    requested_by: str = "EDGE_TF"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def fingerprint(self) -> Dict[str, Any]:
        """Fields whose mutation must void a prior approval."""
        return {
            "request_id": self.request_id,
            "project_id": self.project_id,
            "kind": self.kind.value,
            "payload": self.payload,
            "risk_tier": self.risk_tier.value,
            "reversible": self.reversible,
        }


class ActionApproval(BaseModel):
    approval_id: str
    request_id: str
    action_hash: str
    approver_id: str
    approved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: int = 900

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return (now - self.approved_at).total_seconds() > self.ttl_seconds


class ActionRecord(BaseModel):
    request_id: str
    request: ActionRequest
    state: ApprovalState = ApprovalState.DRAFT
    action_hash: Optional[str] = None
    presented_at: Optional[datetime] = None
    blockers: List[str] = Field(default_factory=list)
    approvals: List[ActionApproval] = Field(default_factory=list)
    required_approvals: int = 1
    result: Optional[Dict[str, Any]] = None
    history: List[Dict[str, Any]] = Field(default_factory=list)

    @property
    def approvers(self) -> List[str]:
        return [a.approver_id for a in self.approvals]

    @property
    def outstanding_approvals(self) -> int:
        return max(0, self.required_approvals - len(self.approvals))


def compute_action_hash(request: ActionRequest, *, policy_version: str, presented_at: datetime) -> str:
    return canonical_hash(
        {
            "policy_version": policy_version,
            "presented_at": presented_at.isoformat(),
            **request.fingerprint(),
        }
    )


__all__ = [
    "ActionApproval",
    "ActionKind",
    "ActionRecord",
    "ActionRequest",
    "ApprovalState",
    "RiskTier",
    "compute_action_hash",
]
