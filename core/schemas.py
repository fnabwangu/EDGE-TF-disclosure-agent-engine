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
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field, model_validator

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


class ETFHoldingObservation(BaseModel):
    """One point-in-time ETF holding disclosure."""
    etf_ticker: str
    fund_id: str
    security_id: str
    raw_identifier: str
    shares_held: float
    portfolio_weight: Optional[float] = None
    portfolio_effective_date: date
    information_available_time: datetime
    source: str
    source_uri: Optional[str] = None


class ETFSharesOutstanding(BaseModel):
    """ETF share denominator required for q/N normalization."""
    etf_ticker: str
    fund_id: str
    shares_outstanding: float = Field(gt=0)
    effective_date: date
    information_available_time: datetime
    source: str
    source_uri: Optional[str] = None


class BasketPosition(BaseModel):
    security_id: str
    raw_identifier: str
    shares: float


class CreationRedemptionBasket(BaseModel):
    """Creation or redemption basket disclosed by an ETF provider."""
    etf_ticker: str
    fund_id: str
    side: Literal["CREATION", "REDEMPTION"]
    creation_unit_size: int = Field(gt=0)
    basket_date: date
    information_available_time: datetime
    positions: List[BasketPosition] = Field(min_length=1)
    cash_component: Optional[float] = None
    source: str
    source_uri: Optional[str] = None


class ManagerRelationship(BaseModel):
    """Manager/adviser lineage needed for independent breadth calculations."""
    fund_id: str
    manager_id: str
    adviser: str
    subadviser: Optional[str] = None
    portfolio_team: Optional[str] = None
    effective_date: date
    information_available_time: datetime
    source: str
    source_uri: Optional[str] = None


class ETFRebalanceEvent(BaseModel):
    """Methodology or scheduled rebalance event."""
    etf_ticker: str
    fund_id: str
    event_type: Literal["METHODOLOGY", "REBALANCE", "RECONSTITUTION"]
    effective_date: date
    information_available_time: datetime
    details: Dict[str, Any] = Field(default_factory=dict)
    source: str
    source_uri: Optional[str] = None


class CorporateActionObservation(BaseModel):
    """Corporate action required to preserve security/share lineage."""
    security_id: str
    action_type: Literal["SPLIT", "MERGER", "SPINOFF", "RENAME", "CUSIP_CHANGE"]
    effective_date: date
    information_available_time: datetime
    ratio: Optional[float] = None
    successor_security_id: Optional[str] = None
    source: str
    source_uri: Optional[str] = None


class ETFDisclosureBundle(BaseModel):
    """Complete canonical ETF disclosure snapshot for downstream analytics."""
    holdings: List[ETFHoldingObservation] = Field(min_length=1)
    shares_outstanding: List[ETFSharesOutstanding] = Field(default_factory=list)
    baskets: List[CreationRedemptionBasket] = Field(default_factory=list)
    manager_relationships: List[ManagerRelationship] = Field(default_factory=list)
    rebalance_events: List[ETFRebalanceEvent] = Field(default_factory=list)
    corporate_actions: List[CorporateActionObservation] = Field(default_factory=list)
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EventScenario(BaseModel):
    """One discrete legal/regulatory outcome branch with an assigned payoff."""
    name: str
    probability: float = Field(ge=0.0, le=1.0)
    expected_return: float


class EventProbability(BaseModel):
    """Deterministic legal/event-arb scenario tree used to derive expected value.

    ``expected_value`` is the probability-weighted payoff (EV = sum(p_s * r_s)),
    not a leverage number. Scenario probabilities must sum to 1.0.
    """
    scenarios: List[EventScenario] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_probabilities_sum_to_one(self) -> "EventProbability":
        total = sum(scenario.probability for scenario in self.scenarios)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"EventProbability scenario probabilities must sum to 1.0, got {total}")
        return self

    @property
    def expected_value(self) -> float:
        return sum(scenario.probability * scenario.expected_return for scenario in self.scenarios)


class ConvictionInputs(BaseModel):
    """Normalized, deterministic evidence feeding the EDGE-TF conviction engine.

    Every field is a pre-computed numerical feature produced upstream by
    analytics modules (IAV, anomaly detector, manager graph, diffusion, hypothesis
    quality). No field is an LLM-asserted confidence value.
    """
    event_expected_value: float
    event_probability_quality: float = Field(ge=0.0, le=1.0)
    iav: float = Field(ge=0.0, le=1.0)
    aqd_quality: float = Field(ge=0.0, le=1.0)
    anomaly_score: float = Field(ge=0.0, le=1.0)
    manager_breadth_score: float = Field(ge=0.0, le=1.0)
    persistence_score: float = Field(ge=0.0, le=1.0)
    diffusion_score: float = Field(ge=0.0, le=1.0)
    evidence_quality: float = Field(ge=0.0, le=1.0)
    ambiguity_penalty: float = Field(default=0.0, ge=0.0, le=1.0)


class ConvictionResult(BaseModel):
    """Deterministic output of the conviction engine; not a final leverage decision."""
    implementation_quality: float
    quality_tier: str
    requested_leverage: float
    reason_codes: List[str] = Field(default_factory=list)


class LeverageLimits(BaseModel):
    """Risk-governance-sourced ceilings applied independently of conviction."""
    max_absolute_leverage: float = Field(gt=0.0)
    max_trade_loss_pct: float = Field(gt=0.0)
    volatility_limit: float = Field(gt=0.0)
    liquidity_limit: float = Field(gt=0.0)
    concentration_limit: float = Field(gt=0.0)
    portfolio_limit: float = Field(gt=0.0)


class SizingResult(BaseModel):
    """Final deterministic hand-off from risk-capped leverage to the order router."""
    requested_leverage: float
    approved_leverage: float
    limiting_constraint: str
    target_notional: float
    long_notional: Optional[float] = None
    short_notional: Optional[float] = None
    shares: Optional[int] = None
    contracts: Optional[int] = None
    execution_permitted: bool
    reason_codes: List[str] = Field(default_factory=list)


__all__ = [
    "DataSourceType",
    "MarketDataSnapshot",
    "IngestionBatchReport",
    "DisclosurePayload",
    "ManagerAction",
    "ETFHoldingObservation",
    "ETFSharesOutstanding",
    "BasketPosition",
    "CreationRedemptionBasket",
    "ManagerRelationship",
    "ETFRebalanceEvent",
    "CorporateActionObservation",
    "ETFDisclosureBundle",
    "EventScenario",
    "EventProbability",
    "ConvictionInputs",
    "ConvictionResult",
    "LeverageLimits",
    "SizingResult",
]
