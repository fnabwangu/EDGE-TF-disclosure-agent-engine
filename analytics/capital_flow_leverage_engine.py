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
is approved. ``requested_leverage_cap`` is a separate, policy-level ceiling on
the *requested* number itself (config/capital_flow_leverage.json), distinct
from the risk-cap ceilings that produce the *approved* number.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from analytics.leverage_tranches import EvidenceState
from analytics.staged_leverage_gate import StagedLeverageDecision, StagedLeverageInputs
from core.schemas import LeverageLimits

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("config/capital_flow_leverage.json")


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

    # Policy-level ceiling on the *requested* number, separate from risk caps.
    requested_leverage_cap: Optional[float] = None

    def band_for(self, state: EvidenceState) -> LeverageBand:
        return {
            EvidenceState.WAIT: self.wait,
            EvidenceState.SEEDED: self.seeded,
            EvidenceState.EMERGING: self.emerging,
            EvidenceState.CONFIRMED: self.confirmed,
            EvidenceState.STRONG: self.strong,
        }[state]

    @staticmethod
    def from_config(config: Mapping[str, Any]) -> "DeploymentPolicy":
        bands_cfg: Mapping[str, Any] = config.get("bands", {})

        def band(name: str, fallback: LeverageBand) -> LeverageBand:
            raw = bands_cfg.get(name)
            return LeverageBand(float(raw[0]), float(raw[1])) if raw else fallback

        defaults = DeploymentPolicy()
        return DeploymentPolicy(
            minimum_event_probability=float(config.get("minimum_event_probability", defaults.minimum_event_probability)),
            wait=band("WAIT", defaults.wait),
            seeded=band("SEEDED", defaults.seeded),
            emerging=band("EMERGING", defaults.emerging),
            confirmed=band("CONFIRMED", defaults.confirmed),
            strong=band("STRONG", defaults.strong),
            requested_leverage_cap=config.get("requested_leverage_cap"),
        )


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
    """Computes requested leverage from capital-flow maturity, then risk-caps it.

    When ``policy`` is not supplied explicitly, bands/thresholds are loaded
    from ``config/capital_flow_leverage.json`` (falling back to built-in
    defaults if the file is absent), and ``default_risk_limits`` is exposed
    as a convenience ``LeverageLimits`` built from that file's ``risk_limits``
    section for callers that don't compute their own.
    """

    def __init__(self, policy: Optional[DeploymentPolicy] = None, config_path: Optional[Path] = None):
        config = self._load_config(config_path)
        self.policy = policy or DeploymentPolicy.from_config(config)
        risk_limits = config.get("risk_limits")
        self.default_risk_limits: Optional[LeverageLimits] = LeverageLimits(**risk_limits) if risk_limits else None

    @staticmethod
    def _load_config(config_path: Optional[Path]) -> Dict[str, Any]:
        path = config_path or DEFAULT_CONFIG_PATH
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception as exc:
            logger.warning("Falling back to built-in capital-flow defaults: failed to load %s: %s", path, exc)
            return {}

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

        reason_codes = ["EVENT_THESIS_VALID", f"FLOW_{inp.flow_state.value}", "CAPITAL_FLOW_DEPLOYMENT"]
        if self.policy.requested_leverage_cap is not None and requested > self.policy.requested_leverage_cap:
            requested = self.policy.requested_leverage_cap
            reason_codes.append("REQUESTED_LEVERAGE_CAP_APPLIED")

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
            reason_codes=tuple(reason_codes),
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


class CapitalFlowSignalGate:
    """Adapts CapitalFlowLeverageEngine to the SignalLeverageGate interface.

    This is the signal source DynamicExposureController uses by default: the
    banded, config-driven capital-flow curve (up to the STRONG-band ceiling)
    rather than the legacy flat StagedLeverageGate/LeveragePolicy. Risk caps
    are intentionally left uncapped here (float("inf")): the real risk-cap
    stage is DynamicExposureController's own LeverageEngine step, applied
    independently after this gate returns its requested leverage.
    """

    def __init__(self, engine: Optional[CapitalFlowLeverageEngine] = None):
        self.engine = engine or CapitalFlowLeverageEngine()

    def evaluate(self, inputs: StagedLeverageInputs) -> StagedLeverageDecision:
        decision = self.engine.calculate(
            DeploymentInputs(
                event_probability=inputs.event_probability,
                remaining_ev=inputs.remaining_ev,
                minimum_remaining_ev=inputs.minimum_remaining_ev,
                flow_state=inputs.evidence_state,
                flow_progress=inputs.flow_progress,
                thesis_active=inputs.thesis_active,
                catalyst_active=inputs.catalyst_active,
                absolute_leverage_cap=float("inf"),
                loss_cap_leverage=float("inf"),
                volatility_cap_leverage=float("inf"),
                liquidity_cap_leverage=float("inf"),
                concentration_cap_leverage=float("inf"),
                portfolio_cap_leverage=float("inf"),
            )
        )
        return StagedLeverageDecision(
            signal_target_leverage=decision.requested_leverage,
            entry_permitted=decision.permitted,
            reason_codes=list(decision.reason_codes),
        )


__all__ = [
    "LeverageBand",
    "DeploymentPolicy",
    "DeploymentInputs",
    "DeploymentDecision",
    "CapitalFlowLeverageEngine",
    "CapitalFlowSignalGate",
]
