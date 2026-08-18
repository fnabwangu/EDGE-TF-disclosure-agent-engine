"""
EDGE-TF Core Data Contracts & Schema Definitions

Path: core/schemas.py

Pydantic and dataclass models defining canonical data contracts for:
- Disclosure payloads (DisclosurePayload)
- Manager actions (ManagerAction)
- Market data snapshots
- Ingestion batch reports
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field

class DataSourceType(str, Enum):
    """Enumeration of supported data source types."""
    BROKER_API = "BROKER_API"
    MARKET_DATA_FEED = "MARKET_DATA_FEED"
    SEC_EDGAR = "SEC_EDGAR"
    SYNTHETIC_SIMULATOR = "SYNTHETIC_SIMULATOR"


class MarketDataSnapshot(BaseModel):
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


class IngestionBatchReport(BaseModel):
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


class ManagerAction(BaseModel):
    """Strict, machine-readable action extracted from a disclosure."""
    source_entity: str
    target_ticker: str
    action_type: Literal["ACCUMULATE", "DIVEST", "SHORT", "OPTION_LEAP", "STAKE_INCREASE"]
    reported_shares_delta: float
    reported_conviction_indicators: List[str] = Field(default_factory=list)


class DisclosurePayload(BaseModel):
    """Typed contract passed from semantic extraction into deterministic code."""
    filing_id: str
    filing_timestamp: int
    actions: List[ManagerAction] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def timestamp_utc(self) -> str:
        return datetime.fromtimestamp(self.filing_timestamp, timezone.utc).isoformat()


__all__ = [
    "DataSourceType",
    "MarketDataSnapshot",
    "IngestionBatchReport",
    "DisclosurePayload",
    "ManagerAction",
]
