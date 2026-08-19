"""
Environment gate: this build must not ship without a usable convex solver.

Path: tests/test_solver_stack.py

Unlike other tests, this one never skips. A missing solver stack is an
environment defect, not an expected condition - failing loudly here means a
bad Codespace/CI image is caught at test time, not discovered later as every
optimization silently returning SOLVER_UNAVAILABLE.
"""

from analytics.convex_position_optimizer import (
    APPROVED_SOLVERS,
    ConvexPositionOptimizer,
    diagnose_solver_stack,
)


def test_cvxpy_is_importable():
    diagnostics = diagnose_solver_stack()
    assert diagnostics.cvxpy_available, "cvxpy is not installed - run: pip install -e . (or pip install cvxpy)"


def test_at_least_one_approved_solver_is_installed():
    diagnostics = diagnose_solver_stack()
    assert diagnostics.approved_available, (
        f"None of {APPROVED_SOLVERS} are installed (found: {list(diagnostics.installed_solvers)}). "
        "Run: pip install cvxpy clarabel scs osqp"
    )


def test_clarabel_is_preferred_when_available():
    diagnostics = diagnose_solver_stack()
    if "CLARABEL" in diagnostics.installed_solvers:
        assert diagnostics.preferred_solver == "CLARABEL"


def test_diagnostics_never_raise_even_if_cvxpy_is_broken(monkeypatch):
    import analytics.convex_position_optimizer as module

    class BrokenCp:
        __version__ = "broken"

        @staticmethod
        def installed_solvers():
            raise RuntimeError("solver registry corrupted")

    monkeypatch.setattr(module, "cp", BrokenCp())
    diagnostics = module.diagnose_solver_stack()
    assert diagnostics.ok is False


def test_the_optimizer_actually_solves_with_the_installed_stack():
    """The diagnostic is necessary but not sufficient: prove a real solve succeeds."""
    import numpy as np

    result = ConvexPositionOptimizer.optimize_allocation_result(
        expected_returns=np.array([0.12, 0.08]),
        covariance_matrix=np.diag([0.04, 0.03]),
        max_drawdown_limit=0.05,
        max_single_position=0.10,
    )
    assert result.status == "OPTIMAL"
    assert result.trade_permitted is True
