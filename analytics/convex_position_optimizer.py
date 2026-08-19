"""
Edge-TF Disclosure Agent Engine - Convex Position Optimizer
Path: analytics/convex_position_optimizer.py

Solves convex quadratic programs using CVXPY to construct trade implementation
portfolios matching strategic thesis exposures while controlling factor risk
and transaction costs.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
try:
    import cvxpy as cp
except ImportError:  # Keep graph and statistical analytics importable without the solver extra.
    cp = None
import logging

logger = logging.getLogger(__name__)

# Preferred order: CLARABEL first (fastest, most reliable for this problem
# shape), then SCS, then OSQP where applicable. At least one must be present.
APPROVED_SOLVERS: Tuple[str, ...] = ("CLARABEL", "SCS", "OSQP")


@dataclass(frozen=True)
class SolverDiagnostics:
    """Startup check: is the convex solver stack actually usable, not just importable?"""

    cvxpy_available: bool
    cvxpy_version: Optional[str]
    installed_solvers: Tuple[str, ...]
    approved_available: Tuple[str, ...]
    preferred_solver: Optional[str]

    @property
    def ok(self) -> bool:
        return self.cvxpy_available and bool(self.approved_available)

    def describe(self) -> str:
        if not self.cvxpy_available:
            return "cvxpy is not installed - convex optimization is unavailable, trades will fail closed."
        if not self.approved_available:
            return (
                f"cvxpy {self.cvxpy_version} is installed but none of {APPROVED_SOLVERS} are available "
                f"(found: {list(self.installed_solvers)}) - trades will fail closed."
            )
        return f"cvxpy {self.cvxpy_version} ready, solver stack: {list(self.approved_available)}"


def diagnose_solver_stack() -> SolverDiagnostics:
    """Never raises. Called at startup and before every optimization attempt."""
    if cp is None:
        return SolverDiagnostics(False, None, (), (), None)
    try:
        installed = tuple(cp.installed_solvers())
    except Exception:  # a broken cvxpy install must not crash the caller
        return SolverDiagnostics(True, getattr(cp, "__version__", None), (), (), None)
    approved = tuple(s for s in APPROVED_SOLVERS if s in installed)
    return SolverDiagnostics(
        True, getattr(cp, "__version__", None), installed, approved, approved[0] if approved else None
    )


@dataclass
class OptimizerParameters:
    """Configurable weights and thresholds for trade construction."""
    risk_lambda: float = 0.5        # Covariance risk penalty parameter
    cost_kappa: float = 0.01         # Turnover / Transaction cost penalty parameter
    max_position_weight: float = 0.15  # Single security concentration cap
    min_position_weight: float = 0.00  # Floor for active candidates
    max_thematic_tracking_error: Optional[float] = None
    long_only: bool = True
    solver: str = "OSQP"


@dataclass
class OptimizationResult:
    """Standardized output container for the convex optimizer."""
    status: str
    optimal_weights: Dict[str, float]
    function_exposures: Dict[str, float]
    target_exposures: Dict[str, float]
    tracking_mismatch_norm: float
    portfolio_variance: float
    turnover_pct: float


@dataclass(frozen=True)
class AllocationResult:
    """Execution-facing result for risk-constrained position sizing."""
    status: str
    weights: np.ndarray
    trade_permitted: bool
    reason_code: str


# A solver reports success within its own tolerance. Permission to commit
# capital must not depend on that tolerance, so the returned solution is
# re-checked against the hard constraints before it is allowed to trade.
# Measured CLARABEL overshoot on a binding variance budget is ~2e-6 relative.
FEASIBILITY_RELATIVE_TOLERANCE = 1e-4
WEIGHT_DUST_FLOOR = 1e-9


def _verify_constraints(
    weights: np.ndarray,
    covariance: np.ndarray,
    variance_budget: float,
    max_single_position: float,
) -> Optional[str]:
    """Return the name of the first hard constraint the solution breaches."""
    realized_variance = float(weights @ covariance @ weights)
    # Purely relative: a zero budget admits only an exactly zero variance.
    if realized_variance > variance_budget + abs(variance_budget) * FEASIBILITY_RELATIVE_TOLERANCE:
        return "VARIANCE_BUDGET"
    if weights.size and float(weights.max()) > max_single_position * (1 + FEASIBILITY_RELATIVE_TOLERANCE):
        return "SINGLE_POSITION_CAP"
    if float(weights.sum()) > 1.0 + FEASIBILITY_RELATIVE_TOLERANCE:
        return "GROSS_EXPOSURE"
    if weights.size and float(weights.min()) < -FEASIBILITY_RELATIVE_TOLERANCE:
        return "LONG_ONLY"
    return None


class ConvexPositionOptimizer:
    """
    Executes quadratic convex optimization to synthesize multi-asset trade structures
    matching specified ontology exposure vectors.
    
    Solves:
      min_x ||B x - tau||_2^2 + lambda * x^T Sigma x + kappa * ||x - x_0||_1
      subject to sum(x) == 1, bounds on x_i
    """

    def __init__(self, params: Optional[OptimizerParameters] = None):
        """
        Args:
            params: OptimizerParameters instance with solver configuration.
        """
        self.params = params or OptimizerParameters()

    @staticmethod
    def optimize_allocation_result(
        expected_returns: np.ndarray,
        covariance_matrix: np.ndarray,
        max_drawdown_limit: float = 0.05,
        max_single_position: float = 0.10,
        risk_aversion: float = 0.5,
    ) -> AllocationResult:
        """Solve a long-only risk-constrained allocation problem.

        ``max_drawdown_limit`` is represented by a hard annualized variance
        budget because drawdown itself is path-dependent and not convex.
        Infeasible or solver-failed problems return an explicit non-permitted
        result with a zero allocation.
        """
        returns = np.asarray(expected_returns, dtype=float).reshape(-1)
        zero_weights = np.zeros(returns.size, dtype=float)
        if cp is None:
            return AllocationResult("SOLVER_UNAVAILABLE", zero_weights, False, "OPTIMIZATION_SOLVER_UNAVAILABLE")
        diagnostics = diagnose_solver_stack()
        if not diagnostics.approved_available:
            logger.error("Convex solver stack unavailable: %s", diagnostics.describe())
            return AllocationResult("SOLVER_UNAVAILABLE", zero_weights, False, "OPTIMIZATION_SOLVER_UNAVAILABLE")
        covariance = np.asarray(covariance_matrix, dtype=float)
        if returns.size == 0 or covariance.shape != (returns.size, returns.size):
            return AllocationResult("INVALID_INPUT", zero_weights, False, "OPTIMIZATION_INVALID_DIMENSIONS")
        covariance = (covariance + covariance.T) / 2.0
        if np.min(np.linalg.eigvalsh(covariance)) < -1e-8:
            return AllocationResult("INVALID_INPUT", zero_weights, False, "OPTIMIZATION_INVALID_COVARIANCE")

        weights = cp.Variable(returns.size)
        portfolio_variance = cp.quad_form(weights, cp.psd_wrap(covariance))
        problem = cp.Problem(
            cp.Maximize(returns @ weights - risk_aversion * portfolio_variance),
            [
                cp.sum(weights) <= 1.0,
                weights >= 0.0,
                weights <= max_single_position,
                portfolio_variance <= max_drawdown_limit,
            ],
        )
        try:
            problem.solve(solver=cp.CLARABEL, warm_start=True)
        except Exception:
            try:
                problem.solve(solver=cp.SCS, warm_start=True)
            except Exception:
                return AllocationResult("SOLVER_ERROR", zero_weights, False, "OPTIMIZATION_SOLVER_ERROR")
        if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE) or weights.value is None:
            return AllocationResult(str(problem.status).upper(), zero_weights, False, "OPTIMIZATION_INFEASIBLE")
        solved_weights = np.asarray(weights.value, dtype=float).reshape(-1)
        solved_weights = np.where(np.abs(solved_weights) < WEIGHT_DUST_FLOOR, 0.0, solved_weights)

        breached = _verify_constraints(solved_weights, covariance, max_drawdown_limit, max_single_position)
        if breached is not None:
            return AllocationResult(
                "INFEASIBLE", zero_weights, False, f"OPTIMIZATION_CONSTRAINT_VIOLATION_{breached}"
            )

        permitted = bool(np.any(np.abs(solved_weights) > 1e-10))
        return AllocationResult(
            "OPTIMAL",
            solved_weights,
            permitted,
            "OPTIMIZATION_ACCEPTED" if permitted else "OPTIMIZATION_ZERO_ALLOCATION",
        )

    @staticmethod
    def optimize_allocation(
        expected_returns: np.ndarray,
        covariance_matrix: np.ndarray,
        max_drawdown_limit: float = 0.05,
        max_single_position: float = 0.10,
        risk_aversion: float = 0.5,
    ) -> np.ndarray:
        """Compatibility API returning only allocation weights."""
        return ConvexPositionOptimizer.optimize_allocation_result(
            expected_returns,
            covariance_matrix,
            max_drawdown_limit,
            max_single_position,
            risk_aversion,
        ).weights

    def optimize(
        self,
        exposure_matrix: pd.DataFrame,
        target_thesis_vector: pd.Series,
        covariance_matrix: pd.DataFrame,
        current_weights: Optional[pd.Series] = None,
        custom_bounds: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> OptimizationResult:
        """
        Solves the constrained convex portfolio optimization problem.

        Args:
            exposure_matrix: DataFrame of shape [n_securities, n_functions].
            target_thesis_vector: Series of target weights per function tau_k.
            covariance_matrix: DataFrame of shape [n_securities, n_securities].
            current_weights: Existing portfolio weights x_0 (optional).
            custom_bounds: Dict mapping canonical_id -> (min_w, max_w).

        Returns:
            OptimizationResult with status, weights, and exposures.
        """
        if cp is None:
            raise RuntimeError("CVXPY is required for deterministic portfolio optimization.")
        securities = exposure_matrix.index.tolist()
        functions = exposure_matrix.columns.tolist()
        n = len(securities)

        if n == 0:
            raise ValueError("Exposure matrix contains zero candidate securities.")

        # Align inputs
        B = exposure_matrix.loc[securities, functions].values.T  # [K, N]
        tau = target_thesis_vector.reindex(functions, fill_value=0.0).values  # [K]
        Sigma = covariance_matrix.loc[securities, securities].values  # [N, N]

        # Ensure positive semi-definite covariance
        Sigma = (Sigma + Sigma.T) / 2.0
        min_eig = np.min(np.linalg.eigvalsh(Sigma))
        if min_eig < 0:
            Sigma += (abs(min_eig) + 1e-6) * np.eye(n)

        # Baseline weights
        if current_weights is not None:
            x_0 = current_weights.reindex(securities, fill_value=0.0).values
        else:
            x_0 = np.zeros(n)

        # Decision variable
        x = cp.Variable(n)

        # Objective formulation
        mismatch = cp.sum_squares(B @ x - tau)
        risk = self.params.risk_lambda * cp.quad_form(x, Sigma)
        turnover = self.params.cost_kappa * cp.norm1(x - x_0)

        objective = cp.Minimize(mismatch + risk + turnover)

        # Constraints
        constraints = [
            cp.sum(x) == 1.0
        ]

        if custom_bounds:
            for i, sec in enumerate(securities):
                low, high = custom_bounds.get(
                    sec, 
                    (
                        self.params.min_position_weight if self.params.long_only else -self.params.max_position_weight,
                        self.params.max_position_weight
                    )
                )
                constraints.append(x[i] >= low)
                constraints.append(x[i] <= high)
        else:
            constraints.append(x <= self.params.max_position_weight)
            if self.params.long_only:
                constraints.append(x >= self.params.min_position_weight)

        if self.params.max_thematic_tracking_error is not None:
            constraints.append(cp.norm2(B @ x - tau) <= self.params.max_thematic_tracking_error)

        # Solve
        prob = cp.Problem(objective, constraints)
        try:
            prob.solve(solver=getattr(cp, self.params.solver, cp.OSQP), warm_start=True)
        except Exception as e:
            logger.error(f"Convex solver execution failed: {e}")
            prob.solve(solver=cp.SCS)

        if prob.status not in ["optimal", "optimal_inaccurate"]:
            logger.warning(f"Optimization returned non-optimal status: {prob.status}")

        weights_arr = np.array(x.value).flatten() if x.value is not None else np.zeros(n)
        weights_dict = {sec: float(np.round(w, 6)) for sec, w in zip(securities, weights_arr)}

        realized_exposure = B @ weights_arr
        function_exp_dict = {
            func: float(exp) for func, exp in zip(functions, realized_exposure)
        }
        target_exp_dict = {
            func: float(t) for func, t in zip(functions, tau)
        }

        mismatch_val = float(np.linalg.norm(realized_exposure - tau))
        port_var = float(weights_arr.T @ Sigma @ weights_arr)
        turnover_val = float(np.sum(np.abs(weights_arr - x_0)))

        return OptimizationResult(
            status=prob.status,
            optimal_weights=weights_dict,
            function_exposures=function_exp_dict,
            target_exposures=target_exp_dict,
            tracking_mismatch_norm=mismatch_val,
            portfolio_variance=port_var,
            turnover_pct=turnover_val,
        )

    def optimize_portfolio(
        self,
        exposure_matrix_df: pd.DataFrame,
        target_strategy_vector: pd.Series,
        covariance_df: pd.DataFrame,
        current_weights_df: Optional[pd.Series] = None,
        risk_lambda: Optional[float] = None,
        cost_kappa: Optional[float] = None,
        max_position_weight: Optional[float] = None,
        min_position_weight: Optional[float] = None,
        long_only: Optional[bool] = None
    ) -> pd.DataFrame:
        """
        Legacy interface for portfolio optimization.
        Returns DataFrame with optimized weights and rebalance deltas.
        """
        # Override parameters if provided
        if risk_lambda is not None:
            self.params.risk_lambda = risk_lambda
        if cost_kappa is not None:
            self.params.cost_kappa = cost_kappa
        if max_position_weight is not None:
            self.params.max_position_weight = max_position_weight
        if min_position_weight is not None:
            self.params.min_position_weight = min_position_weight
        if long_only is not None:
            self.params.long_only = long_only

        result = self.optimize(
            exposure_matrix_df,
            target_strategy_vector,
            covariance_df,
            current_weights_df,
        )

        securities = exposure_matrix_df.index.tolist()
        x_0 = (
            current_weights_df.reindex(securities, fill_value=0.0).values
            if current_weights_df is not None
            else np.zeros(len(securities))
        )

        optimal_weights = np.array([
            result.optimal_weights.get(sec, 0.0) for sec in securities
        ])

        result_df = pd.DataFrame({
            "canonical_id": securities,
            "optimized_weight": optimal_weights,
            "initial_weight": x_0,
            "rebalance_delta": optimal_weights - x_0
        }).sort_values(by="optimized_weight", ascending=False)

        return result_df
