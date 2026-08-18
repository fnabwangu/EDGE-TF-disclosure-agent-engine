"""Deterministic trade slippage and deviation analysis."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class TradeDeviationReport:
    trade_id: str
    targeted_weight: float
    realized_weight: float
    target_price: float
    realized_price: float
    slippage_bps: float
    reason_codes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PostmortemAnalyzer:
    def __init__(self, slippage_threshold_bps: float = 25.0):
        self.slippage_threshold_bps = slippage_threshold_bps

    def analyze_trade_deviation(self, trade_id: str, targeted_weight: float, realized_weight: float, target_price: float, realized_price: float, volume_impact_pct: float = 0.0) -> TradeDeviationReport:
        slippage_bps = ((realized_price - target_price) / target_price * 10000) if target_price > 0 else 0.0
        reasons = []
        if abs(slippage_bps) > self.slippage_threshold_bps:
            reasons.append("SLIPPAGE_EXCEEDED_THRESHOLD")
        if abs(realized_weight - targeted_weight) > 0.01:
            reasons.append("WEIGHT_DEVIATION")
        if volume_impact_pct > 0.5:
            reasons.append("HIGH_VOLUME_IMPACT")
        return TradeDeviationReport(trade_id, targeted_weight, realized_weight, target_price, realized_price, slippage_bps, reasons)


__all__ = ["TradeDeviationReport", "PostmortemAnalyzer"]
