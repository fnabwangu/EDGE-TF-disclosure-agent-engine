"""
Edge-TF Disclosure Agent Engine - Capital-Flow Leverage Engine
Path: analytics/capital_flow_leverage_engine.py

Separates two axes that must never be multiplied together into one number:

    Event probability     -> trade eligibility / EV gate (thesis validity)
    Capital-flow maturity  -> deployment intensity (how much leverage to request)

EvidenceState (WAIT/SEEDED/EMERGING/CONFIRMED/STRONG) is an institutional
adoption / evidence-maturity spectrum, not a confidence percentage. Each state
maps to a requested-leverage *band*; ``flow_progress`` interpolates within
that band as evidence accumulates toward the next state, rather than jumping
straight to the band ceiling the moment a state is entered. Risk caps are
supplied as already-computed ceilings and always override the requested
leverage -- capital flow determines what is requested, risk determines what
is approved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from analytics.leverage_tranches import EvidenceState


@dataclass(frozen=True)
class LeverageBand:
    floor: float
    ceiling: float

    def __post_init__(self) -> None:
        if self.floor < 0.0 or self.ceiling < self.floor:
            raise ValueError("LeverageBand requires 0 <= floor <= ceiling")


@dataclass(frozen=True)
class DeploymentPolicy:
    """Capital-flow state controls deployment intensity via a requested-leverage band.

    Event probability is a thesis/EV gate; it is never multiplied directly
    into flow confidence.
    """

    minimum_event_probability: float = 0.70

    wait: LeverageBand = LeverageBand(0.0, 0.0)
    seeded: LeverageBand = LeverageBand(0.0, 2.0)
    emerging: LeverageBand = LeverageBand(4.0, 6.0)
    confirmed: LeverageBand = LeverageBand(6.0, 8.0)
    strong: LeverageBand = LeverageBand(8.0, 10.0)

    def band_for(self, state: EvidenceState) -> LeverageBand:
        return {
            EvidenceState.WAIT: self.wait,
            EvidenceState.SEEDED: self.seeded,
            EvidenceState.EMERGING: self.emerging,
            EvidenceState.CONFIRMED: self.confirmed,
            EvidenceState.STRONG: self.strong,
        }[state]


@dataclass(frozen=True)
class DeploymentInputs:
    # Legal / event engine
    event_probability: float
    remaining_ev: float
    minimum_remaining_ev: float

    # EDGE-TF capital-flow engine
    flow_state: EvidenceState
    flow_progress: float  # 0 -> just entered the state, 1 -> nearly ready to graduate

    thesis_active: bool
    catalyst_active: bool

    # Hard risk limits, already resolved to leverage ceilings by the risk layer
    absolute_leverage_cap: float
    loss_cap_leverage: float
    volatility_cap_leverage: float
    liquidity_cap_leverage: float
    concentration_cap_leverage: float
    portfolio_cap_leverage: float


@dataclass(frozen=True)
class DeploymentDecision:
    requested_leverage: float
    approved_leverage: float
    state_floor: float
    state_ceiling: float
    limiting_constraint: str
    permitted: bool
    reason_codes: Tuple[str, ...] = field(default_factory=tuple)


class CapitalFlowLeverageEngine:
    """Computes requested leverage from capital-flow maturity, then risk-caps it."""

    def __init__(self, policy: Optional[DeploymentPolicy] = None):
        self.policy = policy or DeploymentPolicy()

    def calculate(self, inp: DeploymentInputs) -> DeploymentDecision:
        if not 0.0 <= inp.event_probability <= 1.0:
            raise ValueError("event_probability must be in [0, 1]")
        if not 0.0 <= inp.flow_progress <= 1.0:
            raise ValueError("flow_progress must be in [0, 1]")

        # Hard thesis gates
        if not inp.thesis_active:
            return self._blocked("THESIS", "THESIS_INVALIDATED")
        if not inp.catalyst_active:
            return self._blocked("CATALYST", "CATALYST_EXPIRED")

        # Event probability gate: eligibility, never multiplied into leverage
        if inp.event_probability < self.policy.minimum_event_probability:
            return self._blocked("EVENT_PROBABILITY", "EVENT_PROBABILITY_BELOW_THRESHOLD")

        # Remaining EV gate
        if inp.remaining_ev < inp.minimum_remaining_ev:
            return self._blocked("REMAINING_EV", "INSUFFICIENT_REMAINING_EV")

        # Capital-flow deployment curve: interpolate within the state's band
        band = self.policy.band_for(inp.flow_state)
        requested = band.floor + inp.flow_progress * (band.ceiling - band.floor)

        # Risk caps override the signal, always
        caps: Dict[str, float] = {
            "ABSOLUTE": inp.absolute_leverage_cap,
            "LOSS": inp.loss_cap_leverage,
            "VOLATILITY": inp.volatility_cap_leverage,
            "LIQUIDITY": inp.liquidity_cap_leverage,
            "CONCENTRATION": inp.concentration_cap_leverage,
            "PORTFOLIO": inp.portfolio_cap_leverage,
        }
        limiting_constraint, risk_ceiling = min(caps.items(), key=lambda item: item[1])
        approved = min(requested, risk_ceiling)

        return DeploymentDecision(
            requested_leverage=requested,
            approved_leverage=approved,
            state_floor=band.floor,
            state_ceiling=band.ceiling,
            limiting_constraint=limiting_constraint,
            permitted=approved > 0.0,
            reason_codes=(
                "EVENT_THESIS_VALID",
                f"FLOW_{inp.flow_state.value}",
                "CAPITAL_FLOW_DEPLOYMENT",
            ),
        )

    @staticmethod
    def _blocked(constraint: str, reason: str) -> DeploymentDecision:
        return DeploymentDecision(
            requested_leverage=0.0,
            approved_leverage=0.0,
            state_floor=0.0,
            state_ceiling=0.0,
            limiting_constraint=constraint,
            permitted=False,
            reason_codes=(reason,),
        )


__all__ = [
    "LeverageBand",
    "DeploymentPolicy",
    "DeploymentInputs",
    "DeploymentDecision",
    "CapitalFlowLeverageEngine",
]
