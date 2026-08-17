# src/ingestion/__init__.py
"""
EDGE-TF Disclosure Agent Engine - Data Ingestion & Normalization Module.

Handles multi-source market data ingestion, corporate filings (SEC EDGAR),
real-time and historical pricing, options chains, and canonical schema harmonization.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any, Dict, List, Optional
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class DataSourceType(str, Enum):
    BROKER_API = "BROKER_API"
    MARKET_DATA_FEED = "MARKET_DATA_FEED"
    SEC_EDGAR = "SEC_EDGAR"
    SYNTHETIC_SIMULATOR = "SYNTHETIC_SIMULATOR"


@dataclass
class MarketDataSnapshot:
    ticker: str
    timestamp_utc: str
    last_price: float
    bid: float
    ask: float
    volume: int
    open_interest: Optional[int] = None
    implied_volatility: Optional[float] = None
    data_source: DataSourceType = DataSourceType.MARKET_DATA_FEED


@dataclass
class IngestionBatchReport:
    batch_id: str
    timestamp_utc: str
    source: DataSourceType
    tickers_ingested: List[str]
    records_count: int
    validation_passed: bool
    quarantined_records_count: int = 0
    raw_storage_path: Optional[str] = None
    canonical_storage_path: Optional[str] = None


class DataIngestionEngine:
    """
    Ingestion coordinator enforcing schema compliance, anomaly detection,
    and bi-temporal partitioning (data tier: raw -> canonical).
    """

    def __init__(self, raw_data_dir: str = "data/raw", canonical_data_dir: str = "data/canonical"):
        self.raw_dir = raw_data_dir
        self.canonical_dir = canonical_data_dir

    def validate_price_series(self, df: pd.DataFrame, max_daily_jump_pct: float = 0.50) -> bool:
        """
        Runs sanity checks on ingested pricing series to flag data corruption,
        null values, or non-market discontinuous price spikes.
        """
        if df.empty:
            logging.warning("Validation failed: Ingested DataFrame is empty.")
            return False

        if df.isnull().values.any():
            logging.warning("Validation failed: NaN or Null values detected in raw pricing matrix.")
            return False

        # Verify no negative or zero pricing
        if (df <= 0).values.any():
            logging.error("Validation failed: Non-positive price encountered.")
            return False

        # Spike detection check
        pct_changes = df.pct_change().abs().dropna()
        if (pct_changes > max_daily_jump_pct).values.any():
            logging.warning(f"Validation warning: Extreme price move (> {max_daily_jump_pct:.0%}) detected.")

        return True


__all__ = [
    "DataSourceType",
    "MarketDataSnapshot",
    "IngestionBatchReport",
    "DataIngestionEngine",
]# ingestion package
