"""Deterministic thesis state and market-drift monitoring."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class ThesisState(str, Enum):
    ACTIVE = "ACTIVE"
    INVALIDATED = "INVALIDATED"
    CLOSED = "CLOSED"


@dataclass
class ThesisTracker:
    thesis_id: str
    title: str
    conviction_score: float
    canonical_securities: List[str]
    state: ThesisState = ThesisState.ACTIVE
    entry_prices: Dict[str, float] = field(default_factory=dict)
    price_moves_pct: Dict[str, float] = field(default_factory=dict)


class ThesisMonitor:
    def __init__(self, price_drift_threshold_pct: float = 0.20):
        self.price_drift_threshold = price_drift_threshold_pct
        self.active_theses: Dict[str, ThesisTracker] = {}

    def register_thesis(self, thesis_id: str, title: str, conviction_score: float, canonical_securities: List[str]) -> ThesisTracker:
        tracker = ThesisTracker(thesis_id, title, conviction_score, canonical_securities)
        self.active_theses[thesis_id] = tracker
        return tracker

    def update_market_data(self, thesis_id: str, current_prices: Dict[str, float]) -> None:
        thesis = self.active_theses[thesis_id]
        for ticker, price in current_prices.items():
            entry = thesis.entry_prices.get(ticker)
            if entry and entry > 0:
                thesis.price_moves_pct[ticker] = (price - entry) / entry
                if abs(thesis.price_moves_pct[ticker]) > self.price_drift_threshold:
                    thesis.state = ThesisState.INVALIDATED

    def close_thesis(self, thesis_id: str) -> None:
        self.active_theses[thesis_id].state = ThesisState.CLOSED


__all__ = ["ThesisState", "ThesisTracker", "ThesisMonitor"]
