"""
Learning engine data contracts and schemas.

Path: learning/schemas.py

Pydantic models for:
- Training datasets and feature vectors
- Model cards and metadata
- Outcome labels and performance metrics
- Setup fingerprints and analog records
- Promotion decisions and gates
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field


class FeatureVector(BaseModel):
    """Single row in a feature store."""
    observation_id: str
    timestamp: datetime
    features: Dict[str, float]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TrainingLabel(BaseModel):
    """Supervised label for model training."""
    observation_id: str
    label_type: Literal["return", "drawdown", "thesis_success", "hedge_effectiveness"]
    value: float
    measured_at: datetime
    horizon_days: int
    is_valid: bool = True
    quality_notes: Optional[str] = None


class DataQualityGate(BaseModel):
    """Validation result for incoming data."""
    observation_id: str
    schema_valid: bool
    timestamp_valid: bool
    source_trusted: bool
    not_duplicate: bool
    not_outlier: bool
    missing_values_acceptable: bool
    no_lookahead_bias: bool
    passed: bool
    quality_issues: List[str] = Field(default_factory=list)


class ModelMetrics(BaseModel):
    """Performance metrics for a trained model."""
    out_of_sample_sharpe: Optional[float] = None
    max_drawdown: Optional[float] = None
    calibration_error: Optional[float] = None
    mape: Optional[float] = None
    r_squared: Optional[float] = None
    precision_at_k: Optional[Dict[int, float]] = None
    auc_roc: Optional[float] = None
    custom_metrics: Dict[str, float] = Field(default_factory=dict)


class ModelCard(BaseModel):
    """Versioned model record with full metadata."""
    model_id: str
    model_type: Literal["return", "drawdown", "thesis_success", "hedge_effectiveness"]
    version: str
    trained_at: datetime
    training_start_date: date
    training_end_date: date
    feature_names: List[str]
    feature_count: int
    training_sample_size: int
    out_of_sample_sample_size: int
    metrics: ModelMetrics
    model_code_version: str
    model_config: Dict[str, Any]
    status: Literal["draft", "challenger", "champion", "retired"]
    predecessor_version: Optional[str] = None
    promotion_history: List[Dict[str, Any]] = Field(default_factory=list)
    regression_test_passed: bool = False
    drift_test_passed: bool = False
    risk_gate_passed: bool = False
    promotion_approved_by: Optional[str] = None
    promotion_approved_at: Optional[datetime] = None
    notes: Optional[str] = None


class WalkForwardSplit(BaseModel):
    """Time-series cross-validation split."""
    split_id: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    training_samples: int
    test_samples: int


class SetupFingerprint(BaseModel):
    """Structured representation of a trade setup for analog matching."""
    event_type: str  # e.g., "secondary_sanctions", "supply_shock"
    region: Optional[str] = None
    asset_class: Optional[str] = None
    commodity: Optional[str] = None
    policy_mechanism: Optional[str] = None
    supply_impact: Optional[Literal["high", "medium", "low"]] = None
    shipping_impact: Optional[Literal["high", "medium", "low"]] = None
    financial_enforcement: Optional[Literal["high", "medium", "low"]] = None
    demand_impact: Optional[Literal["high", "medium", "low"]] = None
    market_regime: Optional[str] = None
    volatility_regime: Optional[str] = None
    liquidity_regime: Optional[str] = None
    macro_backdrop: Optional[str] = None
    custom_features: Dict[str, Any] = Field(default_factory=dict)


class HistoricalEvent(BaseModel):
    """Historical event record with outcomes."""
    event_id: str
    event_date: date
    fingerprint: SetupFingerprint
    description: str
    macro_regime: str
    sanctions_intensity: Optional[float] = None
    oil_supply_impact: Optional[float] = None
    freight_impact: Optional[float] = None
    financial_enforcement_intensity: Optional[float] = None
    return_5d: Optional[float] = None
    return_20d: Optional[float] = None
    return_60d: Optional[float] = None
    volatility_response: Optional[float] = None
    commodity_return: Optional[float] = None
    producer_equity_return: Optional[float] = None
    broad_market_return: Optional[float] = None
    best_implementation: Optional[str] = None
    worst_implementation: Optional[str] = None
    max_drawdown: Optional[float] = None
    time_to_peak_response_days: Optional[int] = None
    thesis_outcome: Optional[Literal["confirmed", "partially_confirmed", "invalidated"]] = None
    notes: Optional[str] = None


class HistoricalTrade(BaseModel):
    """Historical trade implementation with outcomes."""
    trade_id: str
    event_id: Optional[str] = None
    implementation_type: str  # e.g., "long_producers_plus_hedge", "direct_commodity"
    entry_date: date
    exit_date: Optional[date] = None
    duration_days: Optional[int] = None
    initial_sizing: float
    instruments: List[str]
    return_realized: Optional[float] = None
    max_drawdown: Optional[float] = None
    hedge_effectiveness: Optional[float] = None
    time_to_profit_days: Optional[int] = None
    outcome: Optional[Literal["success", "partial", "failure"]] = None
    notes: Optional[str] = None


class AnalogMatch(BaseModel):
    """Match between current setup and historical analog."""
    current_setup_id: str
    analog_event_id: str
    similarity_score: float  # 0-1
    similarity_components: Dict[str, float] = Field(default_factory=dict)
    match_quality: Literal["high", "medium", "low"]


class AnalogSet(BaseModel):
    """Complete set of analogs for a setup with outcome statistics."""
    setup_id: str
    current_fingerprint: SetupFingerprint
    timestamp: datetime
    event_analogs: List[AnalogMatch]
    trade_analogs: List[AnalogMatch]
    outcome_statistics: Dict[str, Any]
    observed_patterns: List[str]
    confidence_level: Literal["high", "medium", "low", "no_analog"]
    minimum_similarity_threshold: float


class PromotionDecision(BaseModel):
    """Record of model promotion evaluation and decision."""
    decision_id: str
    model_id: str
    model_version: str
    timestamp: datetime
    champion_model_version: Optional[str] = None
    challenger_model_version: Optional[str] = None
    out_of_sample_performance_pass: bool
    calibration_pass: bool
    regression_suite_pass: bool
    drift_detection_pass: bool
    risk_gate_pass: bool
    shadow_deployment_days: int
    shadow_performance: Dict[str, float] = Field(default_factory=dict)
    promotion_decision: Literal["promote", "demote", "hold"]
    reasoning: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
