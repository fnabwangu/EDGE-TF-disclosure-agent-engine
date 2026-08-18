"""
Edge-TF Disclosure Agent Engine - Profit Taking Engine
Path: analytics/profit_taking_engine.py

Deterministic staged exit ladder. The generic (non-EDGE-TF) model's projected
return is used strictly as a benchmark hurdle:

    BenchmarkCapture_t = RealizedReturn_t / GenericProjectedReturn_t

Profit-taking never depends on "we still think the thesis is right" alone.
It depends on whether EDGE-TF has already captured more than the generic
projection while the remaining expected value of the thesis has shrunk below
the minimum required to justify continuing to hold -- and highly levered
positions are always flagged for mandatory de-risk review rather than left to
run automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.schemas import ProfitAction, ProfitTakingInputs, ProfitTakingResult


@dataclass(frozen=True)
class ProfitTakingThresholds:
    """Configurable staged-exit thresholds; never hard-coded confidence rules."""

    return_tier_1: float = 0.20
    return_tier_2: float = 0.40
    tier_1_trim_fraction: float = 0.25
    tier_2_default_trim_fraction: float = 0.25
    tier_2_large_trim_fraction: float = 0.33
    benchmark_capture_close_threshold: float = 2.0
    benchmark_capture_large_trim_threshold: float = 1.5
    benchmark_capture_revalidate_threshold: float = 1.0
    mandatory_derisk_leverage: float = 5.0
    mandatory_derisk_return: float = 0.40


class ProfitTakingEngine:
    """Evaluates the deterministic profit-taking ladder against a position snapshot."""

    def __init__(self, thresholds: Optional[ProfitTakingThresholds] = None):
        self.thresholds = thresholds or ProfitTakingThresholds()

    @staticmethod
    def compute_benchmark_capture_ratio(current_return: float, generic_projected_return: float) -> Optional[float]:
        """BenchmarkCapture = RealizedReturn / GenericProjectedReturn; undefined if hurdle <= 0."""
        if generic_projected_return <= 0.0:
            return None
        return current_return / generic_projected_return

    def evaluate(self, inputs: ProfitTakingInputs) -> ProfitTakingResult:
        t = self.thresholds
        benchmark_capture = self.compute_benchmark_capture_ratio(
            inputs.current_return, inputs.generic_projected_return
        )
        reason_codes: list[str] = []
        if benchmark_capture is None:
            reason_codes.append("GENERIC_PROJECTED_RETURN_NON_POSITIVE")
        if not inputs.catalyst_active:
            reason_codes.append("CATALYST_INACTIVE")

        result = self._evaluate_ladder(inputs, benchmark_capture, reason_codes, t)

        requires_derisk_review = (
            inputs.leverage >= t.mandatory_derisk_leverage
            and inputs.current_return >= t.mandatory_derisk_return
        )
        if requires_derisk_review:
            result = result.model_copy(
                update={
                    "requires_derisk_review": True,
                    "reason_codes": [*result.reason_codes, "MANDATORY_DERISK_EVALUATION_LEVERAGE_RETURN"],
                }
            )
        return result

    @staticmethod
    def _evaluate_ladder(
        inputs: ProfitTakingInputs,
        benchmark_capture: Optional[float],
        base_reason_codes: list[str],
        t: ProfitTakingThresholds,
    ) -> ProfitTakingResult:
        # Falsification override: a broken thesis or invalidation is closed regardless of return.
        if not inputs.invalidation_intact or not inputs.thesis_active:
            invalidation_reason = "THESIS_INVALIDATED" if not inputs.invalidation_intact else "THESIS_INACTIVE"
            return ProfitTakingResult(
                action=ProfitAction.CLOSE,
                fraction_to_sell=1.0,
                benchmark_capture_ratio=benchmark_capture,
                capital_to_recover=inputs.current_position_value,
                reason_codes=[*base_reason_codes, invalidation_reason],
            )

        # Benchmark-aware exit: EDGE-TF has already captured >=2x the generic
        # projection and remaining EV no longer justifies holding for the catalyst.
        if (
            benchmark_capture is not None
            and benchmark_capture >= t.benchmark_capture_close_threshold
            and inputs.remaining_ev < inputs.minimum_remaining_ev
        ):
            return ProfitTakingResult(
                action=ProfitAction.CLOSE,
                fraction_to_sell=1.0,
                benchmark_capture_ratio=benchmark_capture,
                capital_to_recover=inputs.current_position_value,
                reason_codes=[
                    *base_reason_codes,
                    "PROFIT_TARGET",
                    "GENERIC_BENCHMARK_EXCEEDED_2X",
                    "INSUFFICIENT_REMAINING_EV",
                ],
            )

        # 40% rule: trim harder if far beyond the generic projection already.
        if inputs.current_return >= t.return_tier_2:
            large_trim = benchmark_capture is not None and benchmark_capture >= t.benchmark_capture_large_trim_threshold
            fraction = t.tier_2_large_trim_fraction if large_trim else t.tier_2_default_trim_fraction
            return ProfitTakingResult(
                action=ProfitAction.SELL_33 if large_trim else ProfitAction.SELL_25,
                fraction_to_sell=fraction,
                benchmark_capture_ratio=benchmark_capture,
                capital_to_recover=0.0,
                reason_codes=[*base_reason_codes, "PROFIT_TARGET", "RETURN_GTE_40", "GENERIC_BENCHMARK_CAPTURED"],
            )

        # 20% rule
        if inputs.current_return >= t.return_tier_1:
            return ProfitTakingResult(
                action=ProfitAction.SELL_25,
                fraction_to_sell=t.tier_1_trim_fraction,
                benchmark_capture_ratio=benchmark_capture,
                capital_to_recover=0.0,
                reason_codes=[*base_reason_codes, "PROFIT_TARGET", "RETURN_GTE_20"],
            )

        # Generic projection reached early: not yet a profit target, but re-check remaining EV.
        if benchmark_capture is not None and benchmark_capture >= t.benchmark_capture_revalidate_threshold:
            return ProfitTakingResult(
                action=ProfitAction.REVALIDATE,
                fraction_to_sell=0.0,
                benchmark_capture_ratio=benchmark_capture,
                capital_to_recover=0.0,
                reason_codes=[*base_reason_codes, "GENERIC_PROJECTED_RETURN_CAPTURED", "REVALIDATE_REMAINING_EV"],
            )

        return ProfitTakingResult(
            action=ProfitAction.HOLD,
            fraction_to_sell=0.0,
            benchmark_capture_ratio=benchmark_capture,
            capital_to_recover=0.0,
            reason_codes=[*base_reason_codes, "THESIS_ACTIVE"],
        )


def evaluate_profit_taking(
    inputs: ProfitTakingInputs, thresholds: Optional[ProfitTakingThresholds] = None
) -> ProfitTakingResult:
    """Convenience wrapper matching the deterministic ladder call site."""
    return ProfitTakingEngine(thresholds).evaluate(inputs)


__all__ = ["ProfitTakingThresholds", "ProfitTakingEngine", "evaluate_profit_taking"]
