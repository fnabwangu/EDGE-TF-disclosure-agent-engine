"""LLM-facing hypothesis registry; no deterministic math is performed here."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List


class ThesisStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CONFIRMED = "CONFIRMED"
    FALSIFIED = "FALSIFIED"
    EXPIRED = "EXPIRED"


class CatalystType(str, Enum):
    EARNINGS_SURPRISE = "EARNINGS_SURPRISE"
    PRODUCT_CYCLE = "PRODUCT_CYCLE"
    REGULATORY_SHIFT = "REGULATORY_SHIFT"
    MACRO_REGIME = "MACRO_REGIME"
    MARGIN_EXPANSION = "MARGIN_EXPANSION"


@dataclass
class FalsificationCriteria:
    invalidation_drawdown_pct: float
    max_underperformance_vs_benchmark_bps: float
    nullification_catalyst: str
    target_timeframe_days: int


@dataclass
class InvestmentHypothesis:
    hypothesis_id: str
    target_ticker: str
    thematic_cluster: str
    thesis_statement: str
    primary_catalyst: CatalystType
    falsification_criteria: FalsificationCriteria
    status: ThesisStatus = ThesisStatus.ACTIVE
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, object]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "target_ticker": self.target_ticker,
            "thematic_cluster": self.thematic_cluster,
            "thesis_statement": self.thesis_statement,
            "primary_catalyst": self.primary_catalyst.value,
            "status": self.status.value,
        }


class HypothesisAgent:
    """Stores structured hypotheses produced by a semantic extraction layer."""

    def __init__(self):
        self.registry: Dict[str, InvestmentHypothesis] = {}

    def register_hypothesis(self, ticker: str, thematic_cluster: str, thesis_statement: str, primary_catalyst: CatalystType, **criteria) -> InvestmentHypothesis:
        hypothesis_id = f"HYP-{ticker}-{len(self.registry) + 1:04d}"
        hypothesis = InvestmentHypothesis(
            hypothesis_id=hypothesis_id,
            target_ticker=ticker,
            thematic_cluster=thematic_cluster,
            thesis_statement=thesis_statement,
            primary_catalyst=primary_catalyst,
            falsification_criteria=FalsificationCriteria(
                invalidation_drawdown_pct=criteria.get("invalidation_drawdown_pct", 0.12),
                max_underperformance_vs_benchmark_bps=criteria.get("max_underperformance_bps", 500.0),
                nullification_catalyst=criteria.get("nullification_catalyst", "Unspecified"),
                target_timeframe_days=criteria.get("target_timeframe_days", 90),
            ),
        )
        self.registry[hypothesis_id] = hypothesis
        return hypothesis

    def extract_active_universe(self) -> List[str]:
        return sorted({item.target_ticker for item in self.registry.values() if item.status == ThesisStatus.ACTIVE})


def generate_theses(seed: str) -> List[str]:
    return [f"Primary thesis for {seed}", f"Alternative thesis for {seed}"]


__all__ = ["ThesisStatus", "CatalystType", "FalsificationCriteria", "InvestmentHypothesis", "HypothesisAgent", "generate_theses"]
