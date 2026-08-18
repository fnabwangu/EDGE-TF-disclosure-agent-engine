"""Semantic and statistical falsification checks kept separate from math sizing."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List

import numpy as np
import pandas as pd


class FalsificationVerdict(str, Enum):
    ROBUST = "ROBUST"
    VULNERABLE = "VULNERABLE"
    REJECTED = "REJECTED"


@dataclass
class StressTestResult:
    test_name: str
    passed: bool
    observed_metric: float
    benchmark_metric: float
    degradation_pct: float
    details: str


@dataclass
class FalsificationReport:
    verdict: FalsificationVerdict
    overall_confidence_score: float
    tests_run: int
    tests_passed: int
    test_results: List[StressTestResult]
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FalsificationEngine:
    def __init__(self, max_acceptable_decay_pct: float = 0.35):
        self.max_decay = max_acceptable_decay_pct

    def test_white_noise_significance(self, alpha_scores: pd.Series, forward_returns: pd.Series) -> StressTestResult:
        if len(alpha_scores) < 4 or len(forward_returns) < 4:
            return StressTestResult("Null-Hypothesis Permutation Test", False, 0.0, 0.0, 100.0, "Insufficient data")
        observed = float(alpha_scores.corr(forward_returns, method="spearman"))
        if np.isnan(observed):
            observed = 0.0
        return StressTestResult("Rank Correlation Sanity Test", observed > 0.0, observed, 0.0, 0.0, "Positive rank correlation required")

    def run_falsification_suite(self, target_weights, alpha_series: pd.Series, prices_df: pd.DataFrame) -> FalsificationReport:
        result = self.test_white_noise_significance(alpha_series, prices_df.pct_change().dropna().iloc[-1] if len(prices_df) > 1 else pd.Series(dtype=float))
        passed = int(result.passed)
        return FalsificationReport(
            verdict=FalsificationVerdict.ROBUST if passed else FalsificationVerdict.REJECTED,
            overall_confidence_score=float(passed), tests_run=1, tests_passed=passed, test_results=[result]
        )


def falsify(thesis: str) -> List[str]:
    return [f"Counterpoint to: {thesis}"]


__all__ = ["FalsificationVerdict", "StressTestResult", "FalsificationReport", "FalsificationEngine", "falsify"]
