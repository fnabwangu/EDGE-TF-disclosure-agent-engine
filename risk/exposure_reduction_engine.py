"""
Edge-TF Disclosure Agent Engine - Exposure Reduction Engine
Path: risk/exposure_reduction_engine.py

Converts a ProfitTakingResult's ``fraction_to_sell`` into a concrete unwind of
a TrancheBook, closing the highest-risk (highest evidence-state / most recent)
tranches first rather than shrinking the whole position uniformly. This is
the ProfitProtectedExposure stage: it can only ever reduce leverage, never
increase it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, List

from core.schemas import ProfitTakingResult

if TYPE_CHECKING:  # avoid a risk -> analytics runtime import cycle
    from analytics.leverage_tranches import TrancheBook


@dataclass(frozen=True)
class ExposureReductionResult:
    leverage_before: float
    leverage_removed: float
    leverage_after: float
    reason_codes: List[str] = field(default_factory=list)


class ExposureReductionEngine:
    """Applies a profit-taking decision to a tranche book, riskiest tranches first."""

    @staticmethod
    def apply(
        book: TrancheBook,
        decision: ProfitTakingResult,
        exit_time: datetime,
        exit_price: float,
    ) -> ExposureReductionResult:
        before = book.current_leverage
        if decision.fraction_to_sell <= 0.0:
            return ExposureReductionResult(before, 0.0, before, list(decision.reason_codes))

        leverage_to_remove = before * decision.fraction_to_sell
        removed = book.reduce_leverage(
            leverage_to_remove=leverage_to_remove,
            exit_time=exit_time,
            exit_price=exit_price,
            reason="|".join(decision.reason_codes) or decision.action.value,
        )
        return ExposureReductionResult(
            leverage_before=before,
            leverage_removed=removed,
            leverage_after=book.current_leverage,
            reason_codes=list(decision.reason_codes),
        )


__all__ = ["ExposureReductionResult", "ExposureReductionEngine"]
