"""Deterministic post-extraction disclosure-to-sizing pipeline."""

from typing import Any, Dict, Sequence

import numpy as np

from core.schemas import ManagerAction
from analytics.anomaly_detector import AnomalyDetector
from analytics.convex_position_optimizer import ConvexPositionOptimizer
from analytics.institutional_graph_engine import InstitutionalGraphEngine
from risk.deterministic_execution_gate import DeterministicExecutionGate


def process_disclosure_pipeline(
    action: ManagerAction,
    historical_flow_data: Sequence[float],
    current_bid: float,
    current_ask: float,
    expected_returns: np.ndarray,
    covariance_matrix: np.ndarray,
    *,
    min_zscore: float = 1.96,
    min_diffusion: float = 0.01,
    max_spread_pct: float = 0.015,
    max_drawdown_limit: float = 0.05,
    max_single_position: float = 0.10,
) -> Dict[str, Any]:
    """Run deterministic analytics, hard gates, and position sizing.

    The LLM is intentionally absent from this function. It accepts only a
    validated ``ManagerAction`` and returns reproducible numerical outputs.
    """
    graph_engine = InstitutionalGraphEngine()
    graph_engine.update_graph(action.source_entity, action.target_ticker, abs(action.reported_shares_delta))
    diffusion_score = graph_engine.calculate_diffusion_score(action.target_ticker)

    z_score = AnomalyDetector.calculate_flow_zscore(
        current_flow=action.reported_shares_delta,
        historical_flows=list(historical_flow_data),
    )

    gate = DeterministicExecutionGate(
        min_zscore=min_zscore,
        min_diffusion=min_diffusion,
        max_spread_pct=max_spread_pct,
    )
    execution_permitted, gate_reason = gate.verify_order(
        z_score=z_score,
        diffusion_score=diffusion_score,
        bid_price=current_bid,
        ask_price=current_ask,
    )

    weights = np.zeros(len(expected_returns), dtype=float)
    if execution_permitted:
        try:
            weights = ConvexPositionOptimizer.optimize_allocation(
                expected_returns=np.asarray(expected_returns, dtype=float),
                covariance_matrix=np.asarray(covariance_matrix, dtype=float),
                max_drawdown_limit=max_drawdown_limit,
                max_single_position=max_single_position,
            )
            if not np.any(np.abs(weights) > 1e-10):
                execution_permitted = False
                gate_reason = "NO_TRADE: optimizer infeasible or unavailable"
        except (RuntimeError, ValueError):
            execution_permitted = False
            gate_reason = "NO_TRADE: optimizer failed deterministically"

    return {
        "target_ticker": action.target_ticker,
        "z_score": float(z_score),
        "diffusion_score": float(diffusion_score),
        "execution_permitted": execution_permitted,
        "gate_reason": gate_reason,
        "optimized_weights": weights,
    }


__all__ = ["process_disclosure_pipeline"]
