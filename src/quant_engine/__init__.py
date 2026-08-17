# src/quant_engine/__init__.py
"""
EDGE-TF Disclosure Agent Engine - Quantitative Modeling & Factor Optimization Module.

Provides matrix operations, portfolio covariance estimators, cross-sectional factor
standardization, constrained quadratic programming optimizers, and Value-at-Risk (VaR)
calculation engines adhering to SEC Rule 18f-4 standards.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class OptimizationObjective(str, Enum):
    MAXIMIZE_SHARPE = "MAXIMIZE_SHARPE"
    MINIMIZE_VARIANCE = "MINIMIZE_VARIANCE"
    MAXIMIZE_FACTOR_ALPHA = "MAXIMIZE_FACTOR_ALPHA"
    TARGET_VOLATILITY = "TARGET_VOLATILITY"


class RiskModelType(str, Enum):
    SAMPLE_COVARIANCE = "SAMPLE_COVARIANCE"
    LEDOIT_WOLF_SHRINKAGE = "LEDOIT_WOLF_SHRINKAGE"
    EXPONENTIALLY_WEIGHTED = "EXPONENTIALLY_WEIGHTED"


@dataclass
class OptimizationConstraints:
    max_single_weight: float = 0.20           # IRC Subchapter M 25% hard cap buffer
    min_single_weight: float = 0.00           # Long-only spot equity constraint
    subchapter_m_5_50_limit: float = 0.50     # Sum of positions > 5% must be <= 50%
    names_rule_min_weight: float = 0.80       # SEC Rule 35d-1 80% thematic mandate alignment
    max_portfolio_turnover: float = 0.25      # Target single-period rebalance turnover cap
    max_gross_options_leverage: float = 0.30  # SEC Rule 18f-4 derivatives notional ceiling


@dataclass
class QuantEngineDiagnostics:
    timestamp_utc: str
    solver_status: str
    iterations: int
    optimal_objective_value: float
    annualized_expected_return: float
    annualized_volatility: float
    sharpe_ratio: float
    active_risk_tracking_error_bps: float
    subchapter_m_passed: bool
    names_rule_passed: bool
    weights_allocated: Dict[str, float] = field(default_factory=dict)


class QuantMatrixUtils:
    """Mathematical and statistical utility helpers for portfolio matrix computations."""

    @staticmethod
    def zscore_standardize(series: pd.Series, clip_outliers: float = 3.0) -> pd.Series:
        """Winsorizes and computes standard normal z-scores for cross-sectional factors."""
        std = series.std(ddof=1)
        if std == 0 or np.isnan(std):
            return pd.Series(0.0, index=series.index)
        z = (series - series.mean()) / std
        return z.clip(-clip_outliers, clip_outliers)

    @staticmethod
    def calculate_shrinkage_covariance(returns_df: pd.DataFrame) -> np.ndarray:
        """
        Computes Ledoit-Wolf shrinkage covariance matrix to prevent ill-conditioned
        inversion during quadratic optimization.
        """
        X = returns_df.values
        n_samples, n_features = X.shape
        if n_samples < 2:
            return np.eye(n_features)

        # Sample covariance
        sample_cov = np.cov(X, rowvar=False) * 252.0

        # Prior: Constant correlation model
        variances = np.diag(sample_cov)
        std_devs = np.sqrt(np.maximum(variances, 1e-8))
        corr = sample_cov / np.outer(std_devs, std_devs)
        mean_corr = (np.sum(corr) - n_features) / (n_features * (n_features - 1)) if n_features > 1 else 0.0

        target = mean_corr * np.outer(std_devs, std_devs)
        np.fill_diagonal(target, variances)

        # Heuristic shrinkage intensity
        shrinkage = max(0.05, min(0.25, 1.0 / np.sqrt(n_samples)))
        shrunk_cov = (1.0 - shrinkage) * sample_cov + shrinkage * target
        return shrunk_cov

    @staticmethod
    def compute_parametric_var(
        weights: np.ndarray,
        cov_matrix: np.ndarray,
        confidence_level: float = 0.99,
        holding_period_days: int = 1,
    ) -> float:
        """
        Calculates SEC Rule 18f-4 standard Value-at-Risk (VaR) under normal distribution.
        """
        port_var = float(weights.T @ cov_matrix @ weights)
        annualized_port_vol = np.sqrt(max(port_var, 1e-8))
        daily_vol = annualized_port_vol / np.sqrt(252.0)

        # Standard normal quantile (z=2.326 for 99%)
        z_score = 2.3263 if confidence_level == 0.99 else 1.6449
        period_var = z_score * daily_vol * np.sqrt(holding_period_days)
        return float(period_var)


__all__ = [
    "OptimizationObjective",
    "RiskModelType",
    "OptimizationConstraints",
    "QuantEngineDiagnostics",
    "QuantMatrixUtils",
]# quant_engine package
