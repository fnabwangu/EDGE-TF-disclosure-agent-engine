"""
Edge-TF Disclosure Agent Engine - Multi-Sleeve Portfolio Engine
Path: analytics/multi_sleeve_portfolio_engine.py

EDGE-TF's output is a trade architecture, not a single leveraged basket. This
module coordinates four independent sleeves --

    ETF     broad thesis exposure
    STOCK   concentrated high-purity/high-adoption beneficiaries
    OPTIONS asymmetric event/catalyst exposure
    HEDGE   strips out unwanted market/sector beta

-- each running its own staged leverage entry, risk caps, tranche accounting,
and profit-taking via an independent DynamicExposureController, and adds only
the portfolio-level constraint that aggregate gross exposure stays within a
configured ceiling. A sleeve without the data required to compute it (e.g. the
options sleeve without historical contract/IV/premium inputs) is marked
BLOCKED with zero exposure rather than fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from analytics.dynamic_exposure_controller import DynamicExposureController, DynamicExposureResult
from analytics.leverage_tranches import EvidenceState
from analytics.staged_leverage_gate import SignalLeverageGate
from core.schemas import LeverageLimits


class SleeveType(str, Enum):
    ETF = "ETF"
    STOCK = "STOCK"
    OPTIONS = "OPTIONS"
    HEDGE = "HEDGE"


@dataclass(frozen=True)
class SleevePolicy:
    """Configuration-only sleeve mandate; never inferred by an LLM."""

    sleeve: SleeveType
    base_weight: float
    max_weight: float
    max_leverage: float
    max_loss_nav_pct: float
    direction: float = 1.0  # +1.0 for long-oriented sleeves, -1.0 for hedge/short sleeves

    def __post_init__(self) -> None:
        if not 0.0 <= self.base_weight <= self.max_weight:
            raise ValueError("base_weight must be in [0, max_weight]")
        if self.max_leverage <= 0.0:
            raise ValueError("max_leverage must be > 0")
        if self.direction not in (1.0, -1.0):
            raise ValueError("direction must be 1.0 or -1.0")


@dataclass
class SleeveState:
    """Auditable per-sleeve snapshot for one evaluation period."""

    sleeve: SleeveType
    target_weight: float
    approved_leverage: float
    gross_exposure: float  # signed: NAV * target_weight * approved_leverage * direction
    current_value: float
    pnl: float
    blocked: bool = False
    reason_codes: List[str] = field(default_factory=list)


@dataclass
class PortfolioTradeArchitecture:
    """The deterministic trade-architecture object the paper describes, made concrete."""

    sleeves: Dict[SleeveType, SleeveState]
    gross_leverage: float
    net_leverage: float
    max_gross_leverage: float
    max_portfolio_loss_pct: float

    @property
    def total_pnl(self) -> float:
        return sum(state.pnl for state in self.sleeves.values())


@dataclass(frozen=True)
class SleeveEvaluationInputs:
    """One sleeve's per-period evidence and market context.

    ``data_available=False`` marks a sleeve as BLOCKED (e.g. the options sleeve
    without historical contract/IV/premium data) instead of fabricating a
    weight for it.
    """

    current_price: float
    evidence_state: EvidenceState
    evidence_score: float
    remaining_ev: float
    minimum_remaining_ev: float
    thesis_active: bool
    catalyst_active: bool
    invalidation_intact: bool
    market_confirmation: bool
    leverage_limits: LeverageLimits
    worst_case_loss_pct: float
    strategy_volatility: float
    maximum_executable_notional: float
    current_return: float
    generic_projected_return: float
    data_available: bool = True
    event_probability: float = 1.0
    flow_progress: float = 0.0


@dataclass
class PortfolioUpdateResult:
    architecture: PortfolioTradeArchitecture
    sleeve_results: Dict[SleeveType, Optional[DynamicExposureResult]]
    reason_codes: List[str] = field(default_factory=list)


class MultiSleevePortfolioEngine:
    """Coordinates independent per-sleeve controllers under one aggregate gross-leverage cap.

    Each sleeve steps its own DynamicExposureController (staged entry, risk
    caps, tranches, profit-taking) independently. This engine adds only:

        Gross_t = sum(|Exposure_s,t|) / NAV_t  <=  GrossMax

    By default every sleeve uses the conservative flat StagedLeverageGate.
    Pass ``signal_gates`` to opt individual sleeves into an alternative
    SignalLeverageGate (e.g. CapitalFlowSignalGate for an aggressive banded
    policy) -- a high-leverage profile is always opt-in, never the default.
    """

    def __init__(
        self,
        sleeve_policies: Dict[SleeveType, SleevePolicy],
        max_gross_leverage: float,
        max_portfolio_loss_pct: float,
        signal_gates: Optional[Dict[SleeveType, SignalLeverageGate]] = None,
    ):
        if not sleeve_policies:
            raise ValueError("MultiSleevePortfolioEngine requires at least one sleeve policy")
        if max_gross_leverage <= 0.0:
            raise ValueError("max_gross_leverage must be > 0")
        self.sleeve_policies = sleeve_policies
        self.max_gross_leverage = max_gross_leverage
        self.max_portfolio_loss_pct = max_portfolio_loss_pct
        signal_gates = signal_gates or {}
        self.controllers: Dict[SleeveType, DynamicExposureController] = {
            sleeve: DynamicExposureController(staged_gate=signal_gates.get(sleeve)) for sleeve in sleeve_policies
        }

    def update(
        self,
        current_time: datetime,
        nav: float,
        sleeve_inputs: Dict[SleeveType, SleeveEvaluationInputs],
    ) -> PortfolioUpdateResult:
        if nav <= 0.0:
            raise ValueError("nav must be > 0")

        sleeve_states: Dict[SleeveType, SleeveState] = {}
        sleeve_results: Dict[SleeveType, Optional[DynamicExposureResult]] = {}
        reason_codes: List[str] = []

        for sleeve, policy in self.sleeve_policies.items():
            inputs = sleeve_inputs.get(sleeve)
            if inputs is None or not inputs.data_available:
                reason = f"{sleeve.value}_SLEEVE_BLOCKED_MISSING_DATA"
                reason_codes.append(reason)
                sleeve_states[sleeve] = SleeveState(
                    sleeve=sleeve,
                    target_weight=0.0,
                    approved_leverage=0.0,
                    gross_exposure=0.0,
                    current_value=0.0,
                    pnl=0.0,
                    blocked=True,
                    reason_codes=[reason],
                )
                sleeve_results[sleeve] = None
                continue

            adjusted_limits = inputs.leverage_limits.model_copy(
                update={"max_absolute_leverage": min(inputs.leverage_limits.max_absolute_leverage, policy.max_leverage)}
            )
            target_weight = min(policy.base_weight, policy.max_weight)
            base_notional = nav * target_weight

            result = self.controllers[sleeve].update(
                current_time=current_time,
                current_price=inputs.current_price,
                evidence_state=inputs.evidence_state,
                evidence_score=inputs.evidence_score,
                remaining_ev=inputs.remaining_ev,
                minimum_remaining_ev=inputs.minimum_remaining_ev,
                thesis_active=inputs.thesis_active,
                catalyst_active=inputs.catalyst_active,
                invalidation_intact=inputs.invalidation_intact,
                market_confirmation=inputs.market_confirmation,
                leverage_limits=adjusted_limits,
                worst_case_loss_pct=inputs.worst_case_loss_pct,
                strategy_volatility=inputs.strategy_volatility,
                base_strategy_notional=base_notional,
                maximum_executable_notional=inputs.maximum_executable_notional,
                current_return=inputs.current_return,
                generic_projected_return=inputs.generic_projected_return,
                event_probability=inputs.event_probability,
                flow_progress=inputs.flow_progress,
            )
            sleeve_results[sleeve] = result
            reason_codes.extend(result.reason_codes)

            approved_leverage = result.leverage_after
            current_value = base_notional * (1.0 + inputs.current_return)
            sleeve_states[sleeve] = SleeveState(
                sleeve=sleeve,
                target_weight=target_weight,
                approved_leverage=approved_leverage,
                gross_exposure=nav * target_weight * approved_leverage * policy.direction,
                current_value=current_value,
                pnl=current_value - base_notional,
            )

        gross_leverage = sum(abs(state.gross_exposure) for state in sleeve_states.values()) / nav
        if gross_leverage > self.max_gross_leverage:
            reason_codes.append("PORTFOLIO_GROSS_LEVERAGE_CAP_APPLIED")
            scale = self.max_gross_leverage / gross_leverage
            for sleeve, policy in self.sleeve_policies.items():
                state = sleeve_states[sleeve]
                if state.blocked or state.approved_leverage <= 0.0:
                    continue
                controller = self.controllers[sleeve]
                excess_leverage = controller.book.current_leverage * (1.0 - scale)
                if excess_leverage > 0.0:
                    controller.book.reduce_leverage(
                        leverage_to_remove=excess_leverage,
                        exit_time=current_time,
                        exit_price=sleeve_inputs[sleeve].current_price,
                        reason="PORTFOLIO_GROSS_LEVERAGE_CAP",
                    )
                new_leverage = controller.book.current_leverage
                sleeve_states[sleeve] = SleeveState(
                    sleeve=sleeve,
                    target_weight=state.target_weight,
                    approved_leverage=new_leverage,
                    gross_exposure=nav * state.target_weight * new_leverage * policy.direction,
                    current_value=state.current_value,
                    pnl=state.pnl,
                    reason_codes=["PORTFOLIO_GROSS_LEVERAGE_CAP_APPLIED"],
                )
            gross_leverage = sum(abs(state.gross_exposure) for state in sleeve_states.values()) / nav

        net_leverage = sum(state.gross_exposure for state in sleeve_states.values()) / nav

        architecture = PortfolioTradeArchitecture(
            sleeves=sleeve_states,
            gross_leverage=gross_leverage,
            net_leverage=net_leverage,
            max_gross_leverage=self.max_gross_leverage,
            max_portfolio_loss_pct=self.max_portfolio_loss_pct,
        )
        return PortfolioUpdateResult(architecture=architecture, sleeve_results=sleeve_results, reason_codes=reason_codes)


__all__ = [
    "SleeveType",
    "SleevePolicy",
    "SleeveState",
    "PortfolioTradeArchitecture",
    "SleeveEvaluationInputs",
    "PortfolioUpdateResult",
    "MultiSleevePortfolioEngine",
]
