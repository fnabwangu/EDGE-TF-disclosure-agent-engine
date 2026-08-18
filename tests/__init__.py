# # tests/__init__.py
"""
EDGE-TF Disclosure Agent Engine - Verification & Test Suite.

Provides centralized test fixtures, synthetic market data generators,
mock broker adapters, and statutory compliance test harnesses.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@dataclass
class SyntheticMarketUniverse:
    """Mock universe container for unit testing and stress falsification."""
    tickers: List[str]
    prices_df: pd.DataFrame
    current_prices: Dict[str, float]
    historical_returns: pd.DataFrame
    volatilities: Dict[str, float]


def generate_synthetic_universe(
    tickers: Optional[List[str]] = None,
    num_days: int = 252,
    seed: int = 42,
    base_price: float = 100.0,
) -> SyntheticMarketUniverse:
    """
    Generates synthetic geometric Brownian motion price paths for testing
    factor extraction, alpha scoring, and statutory constraint gates.
    """
    np.random.seed(seed)
    tickers = tickers or ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META", "BE"]
    n_assets = len(tickers)

    # Correlated random normal steps
    mean_daily_return = 0.0004  # ~10% annual drift
    daily_vol = 0.015           # ~24% annual vol

    corr_matrix = np.full((n_assets, n_assets), 0.35)
    np.fill_diagonal(corr_matrix, 1.0)
    cholesky = np.linalg.cholesky(corr_matrix)

    uncorrelated_normals = np.random.normal(0, 1, size=(num_days, n_assets))
    correlated_normals = uncorrelated_normals @ cholesky.T

    daily_returns = mean_daily_return + daily_vol * correlated_normals
    price_paths = np.zeros((num_days, n_assets))
    price_paths[0] = base_price

    for t in range(1, num_days):
        price_paths[t] = price_paths[t - 1] * np.exp(daily_returns[t])

    dates = pd.date_range(end=datetime.now(timezone.utc), periods=num_days, freq="B")
    prices_df = pd.DataFrame(price_paths, index=dates, columns=tickers)
    returns_df = prices_df.pct_change().dropna()

    current_px = {t: round(float(prices_df[t].iloc[-1]), 2) for t in tickers}
    vols = {t: round(float(returns_df[t].std() * np.sqrt(252)), 4) for t in tickers}

    return SyntheticMarketUniverse(
        tickers=tickers,
        prices_df=prices_df,
        current_prices=current_px,
        historical_returns=returns_df,
        volatilities=vols,
    )


__all__ = [
    "SyntheticMarketUniverse",
    "generate_synthetic_universe",
]
