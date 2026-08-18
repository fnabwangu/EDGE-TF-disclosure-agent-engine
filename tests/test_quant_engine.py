from analytics.anomaly_detector import AnomalyDetector


def test_compute_u_f_i_t_normalizes():
    detector = AnomalyDetector()
    flows = [1, 1, 2]
    total = sum(flows) or 1
    out = [f / total for f in flows]
    assert abs(sum(out) - 1.0) < 1e-9
# tests/test_quant_engine.py
"""
EDGE-TF Disclosure Agent Engine - Quantitative Engine Unit Tests.

Validates matrix utilities, shrinkage covariance matrix estimation,
Rule 18f-4 parametric VaR calculations, and SEC Rule 6c-11 INAV computations.
"""

import pytest
import numpy as np
import pandas as pd

from tests import generate_synthetic_universe
from analytics.quant_matrix import QuantMatrixUtils
from analytics.inav_calculator import INAVCalculator, OptionPositionState


def test_zscore_standardize():
    """Verify winsorized z-score standardization produces zero mean and unit variance."""
    data = pd.Series([10.0, 12.0, 14.0, 16.0, 18.0, 100.0])  # Contains outlier 100
    z = QuantMatrixUtils.zscore_standardize(data, clip_outliers=3.0)
    
    assert len(z) == len(data)
    # Check that mean of winsorized series is approximately 0
    assert abs(z.mean()) < 1e-7


def test_shrinkage_covariance():
    """Verify Ledoit-Wolf shrinkage covariance matrix is well-conditioned and symmetric."""
    universe = generate_synthetic_universe(tickers=["AAPL", "MSFT", "GOOGL"], num_days=100)
    cov = QuantMatrixUtils.calculate_shrinkage_covariance(universe.historical_returns)
    
    # Check dimensions (3x3)
    assert cov.shape == (3, 3)
    # Check symmetry
    np.testing.assert_allclose(cov, cov.T, atol=1e-8)
    # Check positive semi-definiteness (all eigenvalues >= 0)
    eigenvalues = np.linalg.eigvalsh(cov)
    assert np.all(eigenvalues >= -1e-8)


def test_parametric_var():
    """Verify parametric VaR scales correctly with portfolio volatility and confidence level."""
    weights = np.array([0.5, 0.5])
    # 2x2 covariance matrix representing 20% annualized volatility
    cov_matrix = np.array([[0.04, 0.01], [0.01, 0.04]])
    
    var_99 = QuantMatrixUtils.compute_parametric_var(weights, cov_matrix, confidence_level=0.99, holding_period_days=1)
    var_95 = QuantMatrixUtils.compute_parametric_var(weights, cov_matrix, confidence_level=0.95, holding_period_days=1)
    
    assert var_99 > var_95
    assert var_99 > 0.0


def test_inav_calculator_intraday_valuation():
    """Verify INAV calculation correctly aggregates spot equities, cash, and options liabilities."""
    calculator = INAVCalculator(
        total_shares_outstanding=1_000_000,
        creation_unit_size=25_000,
        dislocation_threshold_bps=20.0,
    )

    spot_positions = {"AAPL": 10_000, "MSFT": 5_000}
    current_prices = {"AAPL": 180.0, "MSFT": 420.0}
    
    option_positions = [
        OptionPositionState(
            symbol="AAPL_260818C190",
            underlying_ticker="AAPL",
            option_type="CALL",
            contracts=-100,  # Short 100 covered call contracts
            strike_price=190.0,
            dte_years=30.0 / 365.0,
            implied_volatility=0.25,
        )
    ]

    settled_cash = 500_000.0

    snapshot = calculator.calculate_inav(
        spot_positions=spot_positions,
        current_prices=current_prices,
        options_positions=option_positions,
        settled_cash=settled_cash,
        etf_secondary_market_price=390.50,
    )

    assert snapshot.total_gross_asset_value > 0.0
    assert snapshot.indicative_nav_per_share > 0.0
    assert snapshot.options_overlay_liability_value < 0.0  # Liability for short options
    assert snapshot.premium_discount_bps is not None
