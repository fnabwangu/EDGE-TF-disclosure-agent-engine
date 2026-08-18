"""Deterministic matrix, covariance, and VaR utilities."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict

import numpy as np
import pandas as pd


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
    max_single_weight: float = 0.20
    min_single_weight: float = 0.00
    subchapter_m_5_50_limit: float = 0.50
    names_rule_min_weight: float = 0.80
    max_portfolio_turnover: float = 0.25
    max_gross_options_leverage: float = 0.30


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
    @staticmethod
    def zscore_standardize(series: pd.Series, clip_outliers: float = 3.0) -> pd.Series:
        std = series.std(ddof=1)
        if std == 0 or np.isnan(std):
            return pd.Series(0.0, index=series.index)
        return ((series - series.mean()) / std).clip(-clip_outliers, clip_outliers)

    @staticmethod
    def calculate_shrinkage_covariance(returns_df: pd.DataFrame) -> np.ndarray:
        values = returns_df.values
        if values.shape[0] < 2:
            return np.eye(values.shape[1])
        sample_cov = np.cov(values, rowvar=False) * 252.0
        variances = np.diag(sample_cov)
        std_devs = np.sqrt(np.maximum(variances, 1e-8))
        corr = sample_cov / np.outer(std_devs, std_devs)
        n_features = values.shape[1]
        mean_corr = (np.sum(corr) - n_features) / (n_features * (n_features - 1)) if n_features > 1 else 0.0
        target = mean_corr * np.outer(std_devs, std_devs)
        np.fill_diagonal(target, variances)
        shrinkage = max(0.05, min(0.25, 1.0 / np.sqrt(values.shape[0])))
        return (1.0 - shrinkage) * sample_cov + shrinkage * target

    @staticmethod
    def compute_parametric_var(weights: np.ndarray, cov_matrix: np.ndarray, confidence_level: float = 0.99, holding_period_days: int = 1) -> float:
        portfolio_vol = np.sqrt(max(float(weights.T @ cov_matrix @ weights), 1e-8))
        z_score = 2.3263 if confidence_level == 0.99 else 1.6449
        return float(z_score * portfolio_vol / np.sqrt(252.0) * np.sqrt(holding_period_days))


__all__ = ["OptimizationObjective", "RiskModelType", "OptimizationConstraints", "QuantEngineDiagnostics", "QuantMatrixUtils"]
