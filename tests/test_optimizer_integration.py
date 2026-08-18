import numpy as np

from analytics.convex_position_optimizer import ConvexPositionOptimizer


def test_optimizer_result_exposes_infeasible_reason_code():
    result = ConvexPositionOptimizer.optimize_allocation_result(
        expected_returns=np.array([0.1]),
        covariance_matrix=np.array([[1.0]]),
        max_drawdown_limit=0.0,
    )
    assert result.trade_permitted is False
    assert result.reason_code.startswith("OPTIMIZATION_")
    assert result.weights.shape == (1,)
    assert np.all(result.weights == 0.0)
