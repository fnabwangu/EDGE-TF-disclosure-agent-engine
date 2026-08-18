"""
Edge-TF Disclosure Agent Engine - Monthly Leverage Simulation
Path: analytics/monthly_leverage_simulation.py

Reconstructs a strategy month by month, converting each month's independently
computed evidence snapshot into a conviction result and then ratcheting the
*leverage ceiling* up only when EDGE-TF's evidence tier (weak/emerging/
confirmed/strong) improves relative to the prior month. The ceiling can always
be lowered immediately -- by evidence degrading or by the deterministic
risk caps in ``LeverageEngine`` -- because risk rules must always be free to
override conviction.

This module performs no LLM inference and requires no hindsight: each month
only sees its own snapshot and the ratchet state carried forward from strictly
earlier months.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from analytics.conviction_engine import ConvictionEngine
from analytics.leverage_engine import LeverageEngine
from core.schemas import ConvictionInputs, EventProbability, LeverageLimits

TIER_RANK = {"weak": 0, "emerging": 1, "confirmed": 2, "strong": 3}


@dataclass(frozen=True)
class MonthlyEvidenceSnapshot:
    """One month's independently normalized evidence and risk context."""

    period: str
    inputs: ConvictionInputs
    worst_case_loss_pct: float
    strategy_volatility: float
    base_strategy_notional: float
    maximum_executable_notional: float
    event_probability: Optional[EventProbability] = None
    leverage_limits: Optional[LeverageLimits] = None


@dataclass(frozen=True)
class MonthlyLeverageStep:
    """Auditable reconstruction of a single month's leverage decision."""

    period: str
    quality_tier: str
    implementation_quality: float
    requested_leverage: float
    leverage_ceiling: float
    approved_leverage: float
    limiting_constraint: str
    evidence_state_improved: bool
    evidence_state_degraded: bool
    reason_codes: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class MonthlyLeverageSimulationResult:
    """Ordered path of monthly leverage decisions."""

    steps: List[MonthlyLeverageStep]

    @property
    def leverage_path(self) -> List[float]:
        return [step.approved_leverage for step in self.steps]

    @property
    def leverage_ceiling_path(self) -> List[float]:
        return [step.leverage_ceiling for step in self.steps]


class MonthlyLeverageSimulator:
    """Steps chronologically through monthly evidence, ratcheting leverage.

    The leverage ceiling only rises when the current month's quality tier
    ranks strictly above the prior month's tier. It falls immediately when
    the tier degrades. Regardless of the ceiling, the month's *approved*
    leverage is always re-derived through ``LeverageEngine`` against that
    month's own loss, volatility, and liquidity context, so risk caps can
    suppress the ceiling on any given month without lowering it permanently.
    """

    def __init__(
        self,
        conviction_engine: Optional[ConvictionEngine] = None,
        leverage_engine: Optional[LeverageEngine] = None,
        default_leverage_limits: Optional[LeverageLimits] = None,
        floor_leverage: float = 0.0,
    ):
        self.conviction_engine = conviction_engine or ConvictionEngine()
        self.leverage_engine = leverage_engine or LeverageEngine()
        self.default_leverage_limits = default_leverage_limits
        if floor_leverage < 0.0:
            raise ValueError("floor_leverage cannot be negative")
        self.floor_leverage = floor_leverage

    def run(self, snapshots: Sequence[MonthlyEvidenceSnapshot]) -> MonthlyLeverageSimulationResult:
        if not snapshots:
            raise ValueError("MonthlyLeverageSimulator requires at least one monthly snapshot")

        steps: List[MonthlyLeverageStep] = []
        ceiling = self.floor_leverage
        previous_tier_rank: Optional[int] = None

        for snapshot in snapshots:
            conviction_result = self.conviction_engine.evaluate(snapshot.inputs, snapshot.event_probability)
            tier_rank = TIER_RANK[conviction_result.quality_tier]
            improved = previous_tier_rank is not None and tier_rank > previous_tier_rank
            degraded = previous_tier_rank is not None and tier_rank < previous_tier_rank
            reason_codes = list(conviction_result.reason_codes)

            if previous_tier_rank is None:
                ceiling = max(self.floor_leverage, conviction_result.requested_leverage)
                reason_codes.append("EVIDENCE_STATE_INITIALIZED")
            elif improved:
                ceiling = max(ceiling, conviction_result.requested_leverage)
                reason_codes.append("EVIDENCE_STATE_IMPROVED_LEVERAGE_CEILING_RAISED")
            elif degraded:
                ceiling = min(ceiling, conviction_result.requested_leverage)
                reason_codes.append("EVIDENCE_STATE_DEGRADED_LEVERAGE_CEILING_LOWERED")
            else:
                reason_codes.append("EVIDENCE_STATE_UNCHANGED_LEVERAGE_CEILING_HELD")

            limits = snapshot.leverage_limits or self.default_leverage_limits
            if limits is None:
                raise ValueError(f"No LeverageLimits available for period {snapshot.period!r}")

            decision = self.leverage_engine.evaluate(
                requested_leverage=ceiling,
                limits=limits,
                worst_case_loss_pct=snapshot.worst_case_loss_pct,
                strategy_volatility=snapshot.strategy_volatility,
                base_strategy_notional=snapshot.base_strategy_notional,
                maximum_executable_notional=snapshot.maximum_executable_notional,
            )
            reason_codes.extend(decision.reason_codes)

            steps.append(
                MonthlyLeverageStep(
                    period=snapshot.period,
                    quality_tier=conviction_result.quality_tier,
                    implementation_quality=conviction_result.implementation_quality,
                    requested_leverage=conviction_result.requested_leverage,
                    leverage_ceiling=ceiling,
                    approved_leverage=decision.approved_leverage,
                    limiting_constraint=decision.limiting_constraint,
                    evidence_state_improved=improved,
                    evidence_state_degraded=degraded,
                    reason_codes=reason_codes,
                )
            )
            previous_tier_rank = tier_rank

        return MonthlyLeverageSimulationResult(steps=steps)


__all__ = [
    "TIER_RANK",
    "MonthlyEvidenceSnapshot",
    "MonthlyLeverageStep",
    "MonthlyLeverageSimulationResult",
    "MonthlyLeverageSimulator",
]
