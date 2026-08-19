"""
Approval policy.

Path: approvals/policy.py

How many humans, how fresh the approval must be, and whether the requester may
approve their own request - all keyed by risk tier and action kind.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from approvals.schemas import ActionKind, ActionRequest, RiskTier

POLICY_VERSION = "2026-08-19.1"


@dataclass(frozen=True)
class TierRule:
    required_approvals: int
    ttl_seconds: int
    self_approval_allowed: bool = True


DEFAULT_TIER_RULES: Dict[RiskTier, TierRule] = {
    RiskTier.LOW: TierRule(required_approvals=1, ttl_seconds=3600),
    RiskTier.MEDIUM: TierRule(required_approvals=1, ttl_seconds=900),
    RiskTier.HIGH: TierRule(required_approvals=2, ttl_seconds=300, self_approval_allowed=False),
    RiskTier.CRITICAL: TierRule(required_approvals=2, ttl_seconds=120, self_approval_allowed=False),
}

# Actions that are never allowed to run at their nominal tier.
TIER_FLOOR_BY_KIND: Dict[ActionKind, RiskTier] = {
    ActionKind.KILL_SWITCH_RESET: RiskTier.CRITICAL,
    ActionKind.RISK_PARAMETER_CHANGE: RiskTier.HIGH,
    ActionKind.CAPITAL_ALLOCATION: RiskTier.HIGH,
}

_TIER_ORDER = [RiskTier.LOW, RiskTier.MEDIUM, RiskTier.HIGH, RiskTier.CRITICAL]


@dataclass(frozen=True)
class ApprovalPolicy:
    version: str = POLICY_VERSION
    tier_rules: Dict[RiskTier, TierRule] = field(default_factory=lambda: dict(DEFAULT_TIER_RULES))
    tier_floors: Dict[ActionKind, RiskTier] = field(default_factory=lambda: dict(TIER_FLOOR_BY_KIND))

    def effective_tier(self, request: ActionRequest) -> RiskTier:
        """Irreversible actions and floored kinds are escalated, never de-escalated."""
        tier = request.risk_tier
        floor = self.tier_floors.get(request.kind)
        if floor is not None and _TIER_ORDER.index(floor) > _TIER_ORDER.index(tier):
            tier = floor
        if not request.reversible and _TIER_ORDER.index(tier) < _TIER_ORDER.index(RiskTier.HIGH):
            tier = RiskTier.HIGH
        return tier

    def rule_for(self, request: ActionRequest) -> TierRule:
        return self.tier_rules[self.effective_tier(request)]


__all__ = ["ApprovalPolicy", "DEFAULT_TIER_RULES", "POLICY_VERSION", "TIER_FLOOR_BY_KIND", "TierRule"]
