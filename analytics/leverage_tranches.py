"""
Edge-TF Disclosure Agent Engine - Leverage Tranche Accounting
Path: analytics/leverage_tranches.py

Leverage is tracked as discrete tranches added as EDGE-TF's evidence state
improves (WAIT -> SEEDED -> EMERGING -> CONFIRMED -> STRONG) and removed
riskiest-first when evidence deteriorates or profit is harvested, instead of
collapsing a whole position to a single scalar that jumps straight from zero
to maximum leverage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class EvidenceState(str, Enum):
    WAIT = "WAIT"
    SEEDED = "SEEDED"
    EMERGING = "EMERGING"
    CONFIRMED = "CONFIRMED"
    STRONG = "STRONG"


_STATE_RANK = {
    EvidenceState.WAIT: 0,
    EvidenceState.SEEDED: 1,
    EvidenceState.EMERGING: 2,
    EvidenceState.CONFIRMED: 3,
    EvidenceState.STRONG: 4,
}


@dataclass(frozen=True)
class EvidenceStateThresholds:
    """Config-driven quality cutoffs for the 5-state staged-entry ladder."""

    wait_max: float = 0.15
    seeded_max: float = 0.35
    emerging_max: float = 0.60
    confirmed_max: float = 0.80

    def __post_init__(self) -> None:
        ordered = (self.wait_max, self.seeded_max, self.emerging_max, self.confirmed_max)
        if list(ordered) != sorted(ordered):
            raise ValueError("EvidenceStateThresholds cutoffs must be strictly increasing")

    def classify(self, quality: float) -> EvidenceState:
        if quality < self.wait_max:
            return EvidenceState.WAIT
        if quality < self.seeded_max:
            return EvidenceState.SEEDED
        if quality < self.emerging_max:
            return EvidenceState.EMERGING
        if quality < self.confirmed_max:
            return EvidenceState.CONFIRMED
        return EvidenceState.STRONG


@dataclass(frozen=True)
class LeveragePolicy:
    """Target gross leverage by EDGE-TF evidence state; a configuration input, not an inference."""

    wait: float = 0.0
    seeded: float = 0.5
    emerging: float = 1.25
    confirmed: float = 1.75
    strong: float = 2.0

    def target_for(self, state: EvidenceState) -> float:
        return {
            EvidenceState.WAIT: self.wait,
            EvidenceState.SEEDED: self.seeded,
            EvidenceState.EMERGING: self.emerging,
            EvidenceState.CONFIRMED: self.confirmed,
            EvidenceState.STRONG: self.strong,
        }[state]


@dataclass
class LeverageTranche:
    """One discrete slice of leverage opened at a specific evidence state."""

    tranche_id: str
    evidence_state: EvidenceState
    entry_time: datetime
    entry_price: float
    leverage_added: float
    entry_remaining_ev: float
    entry_evidence_score: float
    active: bool = True
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None

    def mtm_return(self, current_price: float) -> float:
        if self.entry_price <= 0:
            raise ValueError("entry_price must be > 0")
        return (current_price - self.entry_price) / self.entry_price


@dataclass
class TrancheBook:
    """Ordered ledger of leverage tranches for one position/thesis."""

    tranches: List[LeverageTranche] = field(default_factory=list)

    @property
    def active_tranches(self) -> List[LeverageTranche]:
        return [t for t in self.tranches if t.active]

    @property
    def current_leverage(self) -> float:
        return sum(t.leverage_added for t in self.active_tranches)

    def add_tranche(self, tranche: LeverageTranche) -> None:
        if tranche.leverage_added <= 0:
            raise ValueError("leverage_added must be > 0")
        self.tranches.append(tranche)

    def active_by_risk_order(self) -> List[LeverageTranche]:
        """Highest-conviction tranches are reduced first; ties broken by most recent entry."""
        return sorted(
            self.active_tranches,
            key=lambda t: (_STATE_RANK[t.evidence_state], t.entry_time),
            reverse=True,
        )

    def reduce_leverage(
        self,
        leverage_to_remove: float,
        exit_time: datetime,
        exit_price: float,
        reason: str,
    ) -> float:
        """Closes/trims tranches riskiest-first until the requested leverage is removed.

        Returns the leverage actually removed (capped at ``current_leverage``).
        """
        if leverage_to_remove <= 0:
            return 0.0
        remaining = min(leverage_to_remove, self.current_leverage)
        removed_total = 0.0
        for tranche in self.active_by_risk_order():
            if remaining <= 1e-12:
                break
            if tranche.leverage_added <= remaining + 1e-12:
                remaining -= tranche.leverage_added
                removed_total += tranche.leverage_added
                tranche.active = False
                tranche.exit_time = exit_time
                tranche.exit_price = exit_price
                tranche.exit_reason = reason
            else:
                tranche.leverage_added -= remaining
                removed_total += remaining
                remaining = 0.0
        return removed_total


__all__ = [
    "EvidenceState",
    "EvidenceStateThresholds",
    "LeveragePolicy",
    "LeverageTranche",
    "TrancheBook",
]
