"""
EDGE-TF Core Data Contracts & Schema Definitions

Path: core/schemas.py

Pydantic and dataclass models defining canonical data contracts for:
- Disclosure payloads (DisclosurePayload)
- Manager actions (ManagerAction)
- Market data snapshots
- Ingestion batch reports
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class DataSourceType(str, Enum):
    """Enumeration of supported data source types."""
    BROKER_API = "BROKER_API"
    MARKET_DATA_FEED = "MARKET_DATA_FEED"
    SEC_EDGAR = "SEC_EDGAR"
    SYNTHETIC_SIMULATOR = "SYNTHETIC_SIMULATOR"


@dataclass
class MarketDataSnapshot:
    """Real-time market data snapshot for a single security."""
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
    """Summary report of a data ingestion batch."""
    batch_id: str
    timestamp_utc: str
    source: DataSourceType
    tickers_ingested: List[str]
    records_count: int
    validation_passed: bool
    quarantined_records_count: int = 0
    raw_storage_path: Optional[str] = None
    canonical_storage_path: Optional[str] = None


@dataclass
class DisclosurePayload:
    """Canonical disclosure record extracted from regulatory filings."""
    disclosure_id: str
    ticker: str
    filing_date: str
    filing_type: str
    extracted_text: str
    sections_map: Dict[str, str] = field(default_factory=dict)
    raw_payload_hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ManagerAction:
    """Canonical manager action record (trade, rebalance, allocation change)."""
    action_id: str
    manager_id: str
    action_type: str  # "TRADE", "REBALANCE", "ALLOCATION_CHANGE"
    securities: Dict[str, float]  # ticker -> weight or quantity
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    rationale: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


__all__ = [
    "DataSourceType",
    "MarketDataSnapshot",
    "IngestionBatchReport",
    "DisclosurePayload",
    "ManagerAction",
]
