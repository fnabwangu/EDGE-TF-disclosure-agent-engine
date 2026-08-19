# EDGE Learning Engine - Comprehensive Implementation Guide

## Overview

The Learning Engine enables EDGE-TF to continuously improve through three types of learning while maintaining strict governance and deterministic risk controls:

1. **Knowledge Learning** - Fresh data ingestion (ETF disclosures, market data, sanctions)
2. **Statistical Learning** - Supervised models for return, drawdown, thesis success, hedge effectiveness
3. **Decision Learning** - Learning from historical trade outcomes via rich attribution

## Architecture

### Three-Layer Architecture

```
ML / LLM Layer
  ├─ Supervised Models (return, drawdown, thesis_success, hedge_effectiveness)
  ├─ Analog Retrieval (historical event/trade matching)
  └─ Predictions (probabilities, rankings, suggestions)
        ↓
EDGE Deterministic Layer
  ├─ Risk Limits (immutable)
  ├─ Execution Gates (immutable)
  ├─ Approval Requirements (mutable per policy)
  └─ Kill-switch Policy (immutable)
        ↓
Decision & Outcome Recording
  ├─ Decision Records (every choice auditable)
  ├─ Trade Attribution (rich outcome labels)
  └─ Model Promotion Gates (strict validation)
```

### Core Components

#### 1. Data Quality Gates (`data_quality.py`)

All incoming observations must pass deterministic validation:

- **Schema validity**: Required fields present and typed correctly
- **Timestamp validity**: Recent data, not from future
- **Source trust**: Whitelisted data sources only
- **Duplicate detection**: No repeated observations
- **Outlier detection**: Statistical bounds checks (±3σ)
- **Missing values**: Acceptable sparsity thresholds
- **Lookahead bias**: No forward-looking contamination

#### 2. Supervised Models (`models.py`)

Four core model types for decision support:

```python
ReturnModel              - Expected return over horizon
  └─ Linear regression on features
  
DrawdownModel          - Expected maximum drawdown
  └─ Linear regression on features
  
ThesisSuccessModel     - P(thesis validated)
  └─ Logistic regression on features
  
HedgeEffectivenessModel - Hedge protection quality
  └─ Linear regression on features
```

**Key constraint**: Models inform scoring and ranking but cannot override deterministic risk limits.

#### 3. Training Pipeline (`training.py`, `orchestrator.py`)

Walk-forward validation prevents lookahead bias:

```
Train on 2018-2022  │ Test on 2023  │ Gap: 1 day
Train on 2018-2023  │ Test on 2024  │ Gap: 1 day
Train on 2018-2024  │ Test on 2025  │ Gap: 1 day
Train on 2018-2025  │ Test on 2026  │ Gap: 1 day
```

### 4. Model Registry & Promotion (`registry.py`, `evaluation.py`)

Champion/Challenger pattern with multi-gate promotion:

```
Candidate Model
  ├─ Gate 1: Out-of-sample performance (min Sharpe 0.3)
  ├─ Gate 2: Calibration quality (max error 0.15)
  ├─ Gate 3: Risk bounds (max drawdown 20%)
  ├─ Gate 4: Regression testing (vs champion)
  ├─ Gate 5: Drift detection (data distribution)
  ├─ Gate 6: Shadow deployment (30+ days, 50+ observations)
  └─ Gate 7: Human approval
       ↓
   ONLY IF ALL PASS
       ↓
   Promoted to Champion
```

### 5. Shadow Deployment (`shadow_deployment.py`)

Challenger models run in parallel with champions before promotion:

- Both receive same inputs during decision phase
- Predictions recorded without affecting real decisions
- When outcomes are realized, performance compared
- Promotion only if challenger meets/beats champion + passes all gates

#### 6. Strategy Attribution (`strategy_attribution.py`)

Rich outcome decomposition instead of binary win/loss:

```
Trade Outcome
  ├─ Thesis Correctness (was the idea right?)
  ├─ Instrument Correctness (was the tool right?)
  ├─ Timing Correctness (was the timing right?)
  ├─ Hedge Correctness (was the protection right?)
  └─ Sizing Correctness (was the position size right?)
     ↓
  Multi-Dimensional Training Labels
```

Each dimension becomes separate training signal with calibrated weights.

#### 7. Historical Analog Retrieval (`analogs.py`, `historical_storage.py`)

Before ML prediction, find interpretable historical context:

```
Current Setup
  ├─ Event Fingerprinting
  │   └─ Event type, region, commodity, sanctions intensity, etc.
  ├─ Find Similar Historical Events (min 0.50 similarity)
  │   └─ Top 5 events sorted by relevance
  ├─ Find Similar Trade Implementations
  │   └─ Top 5 trades with same implementation type
  └─ Extract Patterns
      ├─ Commodity vs equity performance
      ├─ Time to realization
      ├─ Hedge effectiveness observed
      └─ Risk patterns
```

Result: **Interpretable Evidence** for model scoring.

#### 8. Decision Records (`audit/decision_records.py`, `coordinator.py`)

Every significant action recorded with full context:

```python
record_model_training(
    model_type="return",
    model_id="return_v20260819_143022",
    dataset_version="2018-2026",
    features_count=47,
    training_samples=1204,
    out_of_sample_samples=156,
    metrics={
        "out_of_sample_sharpe": 1.31,
        "max_drawdown": -0.084,
        "calibration_error": 0.06,
    }
)

record_model_promotion(
    model_type="return",
    model_id="return_v20260819_143022",
    promotion_decision="promote",
    gate_results={
        "out_of_sample_performance": True,
        "calibration": True,
        "regression_test": True,
        "drift_detection": True,
        "risk_gate": True,
        "shadow_deployment": True,
        "human_approval": True,
    },
    reasoning="Outperformed champion by 8% on OOS data. All gates passed.",
    approved_by="analytics_team",
)
```

## Usage Patterns

### 1. Ingesting New Data

```python
from learning.coordinator import LearningEngineCoordinator
from learning.schemas import FeatureVector

coordinator = LearningEngineCoordinator()

observation = FeatureVector(
    observation_id="obs_20260819_1",
    timestamp=datetime.now(timezone.utc),
    features={
        "etf_disclosure_score": 82.0,
        "volatility": 0.18,
        "momentum": 0.05,
        "sanctions_intensity": 0.7,
    }
)

success, quality_gate = coordinator.orchestrator.ingest_observation(
    observation=observation,
    source="SEC_EDGAR",
)
```

### 2. Recording Trade Outcomes

```python
attribution, labels = coordinator.record_trade_outcome(
    trade_id="TRADE_2026_08_001",
    thesis_id="THESIS_IRAN_SECONDARY",
    entry_date=date(2026, 8, 1),
    exit_date=date(2026, 8, 15),
    entry_price=52.30,
    exit_price=58.10,
    max_price_during_trade=59.20,
    min_price_during_trade=51.80,
    expected_return=0.11,
    expected_thesis_description="Secondary sanctions tighten, energy equities rally",
    expected_instrument="XLE",
    actual_thesis_description="Sanctions escalated, but tanker rates capped supply loss",
    expected_hedge_instrument="SPY puts",
    expected_hedge_cost=0.019,
    realized_hedge_cost=0.015,
    expected_position_size_pct=0.03,
)

print(f"Thesis Outcome: {attribution.thesis_outcome}")
print(f"Attribution breakdown: {attribution.outcomes}")
print(f"Training labels generated: {len(labels)}")
```

### 3. Training Models

```python
model_card, training_run = coordinator.train_model(
    model_type="return",
    label_type="return",
    start_date=date(2020, 1, 1),
    end_date=date(2026, 8, 18),
    notes="Retrain on full historical dataset",
)

print(f"Model {model_card.model_id} v{model_card.version}")
print(f"OOS Sharpe: {model_card.metrics.out_of_sample_sharpe:.2f}")
print(f"Max Drawdown: {model_card.metrics.max_drawdown:.2%}")
```

### 4. Promoting to Champion

```python
# Start shadow deployment
coordinator.start_shadow_deployment(
    model_type="return",
    challenger=model_card,
)

# During hypothesis generation, record shadow predictions
coordinator.record_shadow_prediction(
    model_type="return",
    observation_id="obs_1",
    champion_pred=0.08,
    challenger_pred=0.09,
)

# When outcome is known, record it
coordinator.record_shadow_outcome(
    model_type="return",
    observation_id="obs_1",
    actual_outcome=0.087,
)

# Check shadow metrics
metrics = coordinator.get_shadow_metrics("return")
print(f"Days in shadow: {metrics.days_in_shadow}")
print(f"Challenger wins: {metrics.challenger_beats_champion_count}")
print(f"Ready for promotion: {metrics.challenger_ready_for_promotion}")

# Promote if ready
if metrics.challenger_ready_for_promotion:
    coordinator.promote_model(
        model_type="return",
        model_id=model_card.model_id,
        decision="promote",
        reasoning="Outperformed champion consistently in shadow",
        approved_by="ml_ops_team",
    )
```

### 5. Retrieving Analogs

```python
from learning.analogs import SetupEncoder

encoder = SetupEncoder()
fingerprint = encoder.encode_setup(
    event_type="secondary_sanctions",
    region="middle_east",
    commodity="oil",
    supply_impact="medium",
    shipping_impact="high",
    policy_mechanism="tanker_restrictions",
    market_regime="risk_off",
    volatility_regime="elevated",
)

analog_context = coordinator.find_similar_events(
    fingerprint=fingerprint,
    top_k=5,
    min_similarity=0.50,
)

print(f"Similar events found: {analog_context['similar_events']}")
print(f"Confidence: {analog_context['similarity_confidence']}")
print(f"Patterns: {analog_context['observed_patterns']}")
```

### 6. Accessing Decision Records

```python
from audit.decision_records import DecisionRecorder

recorder = DecisionRecorder()

# Get all training runs
training_records = recorder.read_by_kind("MODEL_TRAINING")
for record in training_records:
    print(f"Training: {record.model} v{record.response_id}")

# Get all promotions
promotion_records = recorder.read_by_kind("MODEL_PROMOTION")
for record in promotion_records:
    print(f"Promotion: {record.model} -> {record.accepted_candidate_ids}")
```

## Governance Rules (Immutable)

### ML Layer Constraints

✓ **Allowed**:
- Predict probabilities (P(thesis success) = 74%)
- Suggest rankings (Instrument A > Instrument B)
- Estimate expected return (E[R] = 8.2%)
- Recommend sizing adjustments within policy

✗ **Forbidden**:
- Override deterministic risk limits
- Bypass execution gates
- Eliminate approval requirements
- Modify kill-switch policy
- Change position limits unilaterally

### Data Quality Standards

- **Minimum lookback**: 5 years historical for training
- **Maximum lookahead**: 0 days (no forward contamination)
- **Train/test split**: Time-series walk-forward only
- **Missing data tolerance**: 20% per feature max
- **Outlier threshold**: ±3 standard deviations

### Model Promotion Requirements

- **Minimum shadow period**: 30 calendar days
- **Minimum shadow observations**: 50+ outcomes
- **Performance threshold**: Match or beat champion
- **Calibration tolerance**: Max error 0.15
- **Risk bounds**: Max expected drawdown 20%
- **Human approval**: Always required

## File Structure

```
learning/
├── __init__.py
├── coordinator.py           # High-level orchestration
├── orchestrator.py          # Complete pipeline management
├── schemas.py               # Pydantic data contracts
├── data_quality.py          # Validation gates
├── models.py                # Supervised model classes
├── training.py              # Walk-forward training
├── evaluation.py            # Promotion gates
├── registry.py              # Model versioning
├── shadow_deployment.py     # A/B testing framework
├── strategy_attribution.py  # Trade outcome analysis
├── analogs.py               # Historical matching
├── historical_storage.py    # Event/trade persistence
├── integration.py           # EDGE orchestration bridge
├── management.py            # CLI utilities
└── dataset_builder.py       # Feature engineering

audit/
├── decision_records.py      # Audit trail
└── decision_records/        # Record storage
    └── *.json
```

## Expected Outcomes

Over time, the Learning Engine should produce:

1. **Improving Model Performance** - Out-of-sample Sharpe increases
2. **Better Predictions** - Return, drawdown, thesis success estimates improve
3. **Rich Patterns** - "Secondary sanctions historically favor producer equities over commodity direct"
4. **Adaptive Sizing** - Position sizes optimized by observed hedge effectiveness
5. **Self-Documenting** - Every decision auditable back to training data and code version

## Monitoring & Maintenance

### Weekly

- Check shadow deployment metrics
- Review recent decision records
- Monitor data quality gate pass rates

### Monthly

- Evaluate candidate model performance vs champion
- Review trade attribution patterns
- Update historical event/trade database

### Quarterly

- Retrain all models on fresh data
- Review promotion gates and thresholds
- Assess feature importance changes
- Consider adding new features

## References

- Decision Records: `audit/decision_records.py`
- Model Cards: `learning/schemas.py` -> `ModelCard`
- Walk-forward Validation: `learning/training.py`
- Gate Definitions: `learning/evaluation.py` -> `ModelEvaluator`
- Setup Fingerprinting: `learning/analogs.py` -> `SetupEncoder`
