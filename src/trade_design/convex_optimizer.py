"""convex_optimizer.py
Placeholder convex optimization wrapper.
"""

def optimize_portfolio(objective, constraints):
    return {"weights": [], "status": "not_implemented"}

# ==============================================================================
# PIPELINE STEP: CONVEX TRADE OPTIMIZATION (convex_optimizer.py)
# ==============================================================================
# Operational Goal: Synthesize target trade weights (x) that minimize exposure
# distance to a target strategy vector (tau), penalized for covariance risk (Sigma)
# and transaction costs (TC), subject to hard portfolio bounds.
# ==============================================================================

import cvxpy as cp
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple

def run_convex_optimization_pipeline(
    exposure_matrix_df: pd.DataFrame,
    target_strategy_vector: pd.Series,
    covariance_df: pd.DataFrame,
    current_weights_df: Optional[pd.Series] = None,
    risk_lambda: float = 0.5,
    cost_kappa: float = 0.01,
    max_position_weight: float = 0.15,
    min_position_weight: float = 0.0,
    long_only: bool = True
) -> pd.DataFrame:
    """
    Solves the constrained convex portfolio optimization problem:
      min_x ||Bx - tau||_W^2 + lambda * x^T Sigma x + kappa * ||x - x_0||_1
      subject to: sum(x) == 1, min_w <= x_i <= max_w
    """
    # --------------------------------------------------------------------------
    # 1. ALIGN MATRICES AND TARGET VECTORS
    # --------------------------------------------------------------------------
    securities = exposure_matrix_df.index.tolist()
    functions = exposure_matrix_df.columns.tolist()
    n_sec = len(securities)

    # B matrix: [n_functions x n_securities]
    B = exposure_matrix_df.loc[securities, functions].values.T
    
    # Target vector tau: [n_functions]
    tau = target_strategy_vector.reindex(functions, fill_value=0.0).values
    
    # Covariance matrix Sigma: [n_securities x n_securities]
    Sigma = covariance_df.loc[securities, securities].values
    
    # Initial weights x_0
    if current_weights_df is not None:
        x_0 = current_weights_df.reindex(securities, fill_value=0.0).values
    else:
        x_0 = np.zeros(n_sec)

    # --------------------------------------------------------------------------
    # 2. DEFINE CVXPY VARIABLES & OBJECTIVE
    # --------------------------------------------------------------------------
    x = cp.Variable(n_sec)

    # Strategy mismatch term: ||Bx - tau||_2^2
    mismatch_term = cp.sum_squares(B @ x - tau)

    # Risk penalization term: lambda * x^T Sigma x
    risk_term = risk_lambda * cp.quad_form(x, Sigma)

    # Transaction cost / turnover term: kappa * ||x - x_0||_1
    turnover_term = cost_kappa * cp.norm1(x - x_0)

    objective = cp.Minimize(mismatch_term + risk_term + turnover_term)

    # --------------------------------------------------------------------------
    # 3. ENFORCE HARD CONSTRAINTS
    # --------------------------------------------------------------------------
    constraints = [
        cp.sum(x) == 1.0,  # Full allocation budget
        x <= max_position_weight
    ]
    if long_only:
        constraints.append(x >= min_position_weight)

    # --------------------------------------------------------------------------
    # 4. SOLVE CONVEX PROBLEM
    # --------------------------------------------------------------------------
    prob = cp.Problem(objective, constraints)
    prob.solve(solver=cp.OSQP, warm_start=True)

    if prob.status not in ["optimal", "optimal_inaccurate"]:
        raise ValueError(f"Convex optimizer failed to converge: status={prob.status}")

    optimal_x = np.array(x.value).flatten()

    # --------------------------------------------------------------------------
    # 5. CONSOLIDATE OUTPUT PORTFOLIO
    # --------------------------------------------------------------------------
    result_df = pd.DataFrame({
        "canonical_id": securities,
        "optimized_weight": optimal_x,
        "initial_weight": x_0,
        "rebalance_delta": optimal_x - x_0
    }).sort_values(by="optimized_weight", ascending=False)

    return result_df

"""
Edge-TF Disclosure Agent Engine - Trade Design Convex Optimizer
Path: src/trade_design/convex_optimizer.py

Solves convex quadratic programs to construct trade implementation portfolios
matching strategic thesis exposures while controlling factor risk and friction.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
import cvxpy as cp
import logging

logger = logging.getLogger(__name__)


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


class StrategyConvexOptimizer:
    """
    Executes quadratic convex optimization to synthesize multi-asset trade structures
    matching specified ontology exposure vectors.
    """

    def __init__(self, params: Optional[OptimizerParameters] = None):
        self.params = params or OptimizerParameters()

    def optimize(
        self,
        exposure_matrix: pd.DataFrame,
        target_thesis_vector: pd.Series,
        covariance_matrix: pd.DataFrame,
        current_weights: Optional[pd.Series] = None,
        custom_bounds: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> OptimizationResult:
        """
        Solves:
          min_x ||B x - tau||_2^2 + lambda * x^T Sigma x + kappa * ||x - x_0||_1
          subject to sum(x) == 1, bounds on x_i.

        Args:
            exposure_matrix: DataFrame of shape [n_securities, n_functions].
            target_thesis_vector: Series of target weights per function tau_k.
            covariance_matrix: DataFrame of shape [n_securities, n_securities].
            current_weights: Existing portfolio weights x_0.
            custom_bounds: Dict mapping canonical_id -> (min_w, max_w).
        """
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






