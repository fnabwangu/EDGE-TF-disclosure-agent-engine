"""The optimizer must not let solver tolerance manufacture permission to trade."""

import numpy as np

from analytics.convex_position_optimizer import (
    FEASIBILITY_RELATIVE_TOLERANCE,
    ConvexPositionOptimizer,
    _verify_constraints,
)

COV = np.array([[1.0]])


def test_zero_variance_budget_admits_only_a_zero_allocation():
    result = ConvexPositionOptimizer.optimize_allocation_result(
        expected_returns=np.array([0.1]), covariance_matrix=COV, max_drawdown_limit=0.0
    )
    assert result.trade_permitted is False
    assert result.status == "INFEASIBLE"
    assert result.reason_code == "OPTIMIZATION_CONSTRAINT_VIOLATION_VARIANCE_BUDGET"
    assert np.all(result.weights == 0.0)


def test_a_real_budget_still_produces_a_tradeable_allocation():
    result = ConvexPositionOptimizer.optimize_allocation_result(
        expected_returns=np.array([0.12, 0.08]),
        covariance_matrix=np.diag([0.04, 0.03]),
        max_drawdown_limit=0.05,
        max_single_position=0.10,
    )
    assert result.trade_permitted is True
    realized = float(result.weights @ np.diag([0.04, 0.03]) @ result.weights)
    assert realized <= 0.05 * (1 + FEASIBILITY_RELATIVE_TOLERANCE)


def test_a_small_but_real_budget_is_not_a_false_negative():
    result = ConvexPositionOptimizer.optimize_allocation_result(
        expected_returns=np.array([0.1]), covariance_matrix=COV, max_drawdown_limit=1e-4
    )
    assert result.trade_permitted is True


def test_verifier_catches_each_hard_constraint():
    assert _verify_constraints(np.array([0.5]), COV, 0.01, 0.10) == "VARIANCE_BUDGET"
    assert _verify_constraints(np.array([0.2]), COV, 1.0, 0.10) == "SINGLE_POSITION_CAP"
    assert _verify_constraints(np.array([0.6, 0.6]), np.eye(2), 10.0, 1.0) == "GROSS_EXPOSURE"
    assert _verify_constraints(np.array([-0.5]), COV, 10.0, 1.0) == "LONG_ONLY"
    assert _verify_constraints(np.array([0.05]), COV, 0.01, 0.10) is None
