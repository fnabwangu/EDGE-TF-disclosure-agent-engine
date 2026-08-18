"""
Edge-TF Disclosure Agent Engine - Staged Leverage Entry Gate
Path: analytics/staged_leverage_gate.py

Computes the signal-side target leverage (SignalExposure) for the current
evidence state. Leverage is only permitted to step up when the evidence state
itself has evidence-of-improvement gates satisfied: remaining EV is
sufficient, the thesis and catalyst are still active, and market confirmation
holds. This module never applies risk caps or profit-taking -- those are
independent downstream stages (analytics/leverage_engine.py and
risk/exposure_reduction_engine.py) that can only ever reduce this target.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Protocol

from analytics.leverage_tranches import EvidenceState, LeveragePolicy


@dataclass(frozen=True)
class StagedLeverageInputs:
    evidence_state: EvidenceState
    remaining_ev: float
    minimum_remaining_ev: float
    thesis_active: bool
    catalyst_active: bool
    market_confirmation: bool
    # Optional fields consumed only by alternative signal gates (e.g.
    # CapitalFlowSignalGate); StagedLeverageGate itself ignores them.
    event_probability: float = 1.0
    flow_progress: float = 0.0


@dataclass(frozen=True)
class StagedLeverageDecision:
    """Signal-side target leverage before risk caps or profit-taking are applied."""

    signal_target_leverage: float
    entry_permitted: bool
    reason_codes: List[str] = field(default_factory=list)


class SignalLeverageGate(Protocol):
    """Any signal-side gate DynamicExposureController can be configured with."""

    def evaluate(self, inputs: StagedLeverageInputs) -> StagedLeverageDecision: ...


class StagedLeverageGate:
    """Gates whether the signal target leverage may reflect the current evidence state."""

    def __init__(self, policy: Optional[LeveragePolicy] = None):
        self.policy = policy or LeveragePolicy()

    def evaluate(self, inputs: StagedLeverageInputs) -> StagedLeverageDecision:
        if not inputs.thesis_active:
            return StagedLeverageDecision(0.0, False, ["THESIS_INVALIDATED"])
        if not inputs.catalyst_active:
            return StagedLeverageDecision(0.0, False, ["CATALYST_EXPIRED"])
        if inputs.evidence_state == EvidenceState.WAIT:
            return StagedLeverageDecision(0.0, False, ["WAIT_STATE"])
        if inputs.remaining_ev < inputs.minimum_remaining_ev:
            return StagedLeverageDecision(0.0, False, ["INSUFFICIENT_REMAINING_EV"])
        if not inputs.market_confirmation:
            return StagedLeverageDecision(0.0, False, ["MARKET_CONFIRMATION_FAILED"])

        target = self.policy.target_for(inputs.evidence_state)
        return StagedLeverageDecision(target, True, [f"SIGNAL_TARGET_{inputs.evidence_state.value}"])


__all__ = ["StagedLeverageInputs", "StagedLeverageDecision", "SignalLeverageGate", "StagedLeverageGate"]


__all__ = ["StagedLeverageInputs", "StagedLeverageDecision", "StagedLeverageGate"]
