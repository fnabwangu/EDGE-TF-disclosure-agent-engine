"""Learning Engine README

# EDGE-TF Learning Engine

A governed, deterministic self-improvement system for EDGE-TF that accumulates
experience from trading outcomes and historical context while maintaining strict
control over model behavior.

## Architecture Overview

The Learning Engine comprises five major components:

### 1. Data Ingestion & Quality Control

**Files:** `data_quality.py`

All incoming data passes deterministic validation gates:
- Schema validation
- Timestamp validity
- Source trust (from configured trusted sources)
- Duplicate detection
- Outlier detection (z-score > 3.0)
- Missing value tolerance (<20%)
- Lookahead bias prevention

Only data passing all gates enters the feature store.

```python
from learning.data_quality import DataQualityGateKeeper, DataQualityConfig

config = DataQualityConfig(
    trusted_sources={"EDGE_RESEARCH", "SEC_EDGAR", "MARKET_DATA"},
    outlier_std_threshold=3.0,
)
gatekeeper = DataQualityGateKeeper(config)

# Validate incoming observation
gate_result = gatekeeper.validate_feature_vector(
    observation, 
    current_time, 
    source="EDGE_RESEARCH"
)

if gate_result.passed:
    feature_store.add_observation(observation, gate_result)
```

### 2. Outcome Labeling & Dataset Building

**Files:** `labels.py`, `dataset_builder.py`

When a trade or thesis completes, EDGE generates rich training signals by
decomposing outcomes across five dimensions:

- **Thesis correctness:** Was the conceptual thesis right?
- **Instrument correctness:** Was the instrument the right choice?
- **Timing correctness:** Was entry/exit timing appropriate?
- **Hedge effectiveness:** Did the protection work?
- **Sizing appropriateness:** Was position sizing correct?

This multi-dimensional labeling provides richer training signal than simple
win/loss classification.

```python
from learning.labels import OutcomeLabelingService

labeler = OutcomeLabelingService()

assessment, labels = labeler.label_trade_outcome(
    thesis_id="thesis_001",
    entry_date=date(2026, 1, 15),
    exit_date=date(2026, 2, 28),
    entry_price=85.5,
    exit_price=92.3,
    max_price=95.0,
    min_price=83.2,
    expected_return_target=0.08,
    expected_hedge_cost=0.019,
    realized_hedge_cost=0.018,
    expected_thesis="Sanctions tighten; energy equities outperform",
    actual_outcome_description="Thesis partially confirmed; equities underperformed expectations",
)

# assessment.thesis_correctness = "partially_correct"
# assessment.thesis_contribution = 0.045  # Attributed 4.5% of the return to thesis being right
# ... etc for other dimensions
```

Datasets are built by combining feature vectors with labels and creating
walk-forward splits to prevent lookahead bias:

```python
from learning.dataset_builder import DatasetBuilder

builder = DatasetBuilder(feature_store)
builder.add_labels(labels)

# Build training dataset
examples = builder.build_training_dataset(
    label_type="return",
    start_date=date(2018, 1, 1),
    end_date=date(2026, 8, 31),
)

# Create time-series aware validation splits
splits = builder.create_walk_forward_splits(
    all_data_start=date(2018, 1, 1),
    all_data_end=date(2026, 8, 31),
    training_window_years=5,
    test_window_days=60,
    step_days=30,
)

# Split 1: Train 2018-2023, Test 2023
# Split 2: Train 2018-2023-01, Test 2023-01
# Split 3: Train 2018-2023-02, Test 2023-02
# ...prevents lookahead bias in time-series data
```

### 3. Supervised Model Training

**Files:** `models.py`, `training.py`

EDGE maintains four supervised models:

1. **ReturnModel:** Predicts expected return from setup features
2. **DrawdownModel:** Predicts maximum expected drawdown
3. **ThesisSuccessModel:** Probability thesis will be validated
4. **HedgeEffectivenessModel:** Expected hedge effectiveness

All models:
- Use simple, interpretable algorithms (linear regression, logistic regression)
- Train on walk-forward validation (no lookahead bias)
- Output probabilities and confidence scores
- Report feature importance for interpretability

```python
from learning.models import ReturnModel
from learning.training import ModelTrainer

model = ReturnModel()
trainer = ModelTrainer()

trained_model, run = trainer.train_with_walk_forward(
    model, 
    dataset_builder, 
    label_type="return", 
    all_examples=examples,
    splits=splits,
)

# Metrics automatically computed on out-of-sample test periods
print(f"Out-of-sample Sharpe: {run.average_metrics.out_of_sample_sharpe:.3f}")
print(f"Max drawdown: {run.average_metrics.max_drawdown:.2%}")
print(f"Calibration error: {run.average_metrics.calibration_error:.3f}")
```

### 4. Deterministic Evaluation Gates

**Files:** `evaluation.py`

Candidate models must pass multiple gates before promotion:

1. **Out-of-Sample Performance Gate**
   - Minimum Sharpe ratio (default 0.3)
   - Minimum sample size (default 50)
   - Positive average return or reasonable R²

2. **Calibration Gate**
   - Predicted probabilities must match realized outcomes
   - Max calibration error tolerance (default 0.15)

3. **Risk Bounds Gate**
   - Max drawdown must not exceed policy limit (default 20%)

4. **Regression Gate**
   - Candidate must not degrade vs champion (within 10% tolerance)

5. **Drift Detection Gate**
   - Data distribution must not significantly shift from training
   - Uses z-score testing on features

```python
from learning.evaluation import ModelEvaluator

evaluator = ModelEvaluator()

gates, all_passed = evaluator.evaluate_candidate(
    candidate_card,
    champion_card,
    historical_data_distribution,
)

for gate in gates:
    print(f"{gate.gate_name}: {'PASS' if gate.passed else 'FAIL'}")
    print(f"  Score: {gate.score:.3f}")
    print(f"  {gate.message}")

if not all_passed:
    print("Candidate did not pass all gates. Cannot promote.")
```

### 5. Model Registry & Champion/Challenger Versioning

**Files:** `registry.py`

Models are versioned and tracked with:
- Model cards (full metadata and metrics)
- Champion/challenger status
- Promotion history
- Audit trail

```python
from learning.registry import ModelRegistry

registry = ModelRegistry()

# Register trained model
registry.register_model(model_card)

# Get current champion
champion = registry.get_champion("return")

# Get challenger model
challenger = registry.get_challenger("return")

# Promote only after gates pass
promotion_decision = registry.promote_model(
    model_id="return_model_v37",
    model_type="return",
    decision="promote",
    reasoning="New model exceeds champion on Sharpe, calibration, and risk metrics",
    approved_by="risk_committee",
)

print(f"Promotion recorded with id: {promotion_decision.decision_id}")
```

### 6. Historical Analog Retrieval

**Files:** `analogs.py`

Before making decisions, EDGE retrieves historically similar events and
implementations. This provides interpretable grounding for model scores.

Analogs are matched on:
- Event type (secondary sanctions, supply shock, etc.)
- Geography and commodity
- Policy mechanism
- Supply/demand impacts
- Market regime and volatility regime

```python
from learning.analogs import AnalogEngine

engine = AnalogEngine()

# Register historical events and trades
engine.register_historical_event(historical_event)
engine.register_historical_trade(historical_trade)

# Find analogs for current setup
analog_set = engine.find_analogs(
    current_setup=fingerprint,
    implementation_type="long_producers_plus_hedge",
    min_event_similarity=0.50,
)

print(f"Confidence: {analog_set.confidence_level}")
print(f"Patterns observed:")
for pattern in analog_set.observed_patterns:
    print(f"  - {pattern}")

# Outcome stats from historical analogs
print(f"Historical 20-day return (median): {analog_set.outcome_statistics.get('return_20d_avg'):.2%}")
```

### 7. Orchestration & Integration

**Files:** `orchestrator.py`

The `LearningOrchestrator` coordinates all components:

```python
from learning.orchestrator import LearningOrchestrator

orchestrator = LearningOrchestrator()

# 1. Ingest observations
success, gate = orchestrator.ingest_observation(obs, source="EDGE_RESEARCH")

# 2. Label outcomes
assessment, labels = orchestrator.label_trade_outcome(...)

# 3. Train models
trained_cards = orchestrator.train_models(
    label_type="return",
    data_start=date(2018, 1, 1),
    data_end=date(2026, 8, 31),
)

# 4. Evaluate models
gate_results, all_passed = orchestrator.evaluate_model("return_v37", "return")

# 5. Promote if gates pass
if all_passed:
    orchestrator.promote_model(
        model_id="return_v37",
        model_type="return",
        decision="promote",
        reasoning="...",
        approved_by="risk_committee",
    )

# 6. Retrieve analogs for next decision
analogs = orchestrator.find_analogs(
    event_type="secondary_sanctions",
    region="middle_east",
)
```

## Decision Record Integration

All learning activities create immutable audit entries:

```python
from audit.decision_records import DecisionRecorder

recorder = DecisionRecorder()

# Record training run
training_record = recorder.record_model_training(
    model_type="return",
    model_id="return_v37",
    model_version="37",
    dataset_version="canonical_2026_08_31",
    training_start_date="2018-01-01",
    training_end_date="2026-08-31",
    feature_count=47,
    training_sample_size=1250,
    out_of_sample_sample_size=310,
    metrics={
        "out_of_sample_sharpe": 1.31,
        "max_drawdown": -0.084,
        "calibration_error": 0.06,
    },
    walk_forward_splits=7,
    feature_names=["conviction_score", "disclosure_purity", ...],
)

# Record promotion decision
promo_record = recorder.record_model_promotion(
    model_type="return",
    model_id="return_v37",
    model_version="37",
    promotion_decision="promote",
    gate_results={
        "oos_performance": True,
        "calibration": True,
        "risk_bounds": True,
        "regression": True,
        "drift_detection": True,
    },
    reasoning="Challenger outperforms champion on Sharpe, calibration, and risk metrics",
    approved_by="risk_committee",
    champion_version="36",
)
```

## Policy Enforcement: What ML Can and Cannot Do

### ✓ ML CAN:

- **Predict probabilities and confidence scores**
  - "Thesis success probability: 73%"
  - "Expected return: 11.4% with 8.2% drawdown"

- **Rank implementations by expected return/risk**
  - "Implementation A ranks highest"
  - "Implementation C has lowest drawdown risk"

- **Suggest position sizing based on risk**
  - "Recommend 3.2% allocation (vs 2% minimum)"
  - "Max safe allocation: 4.8%"

- **Inform scores with historical analogs**
  - "Similar setups produced 15-20 day returns"
  - "Hedge effectiveness historically 85%"

### ✗ ML CANNOT:

- **Override deterministic risk limits**
  - Position limit stays 5% unless policy explicitly changes
  - Max leverage unchanged by model output

- **Bypass execution approval gates**
  - Trades requiring approval still require it
  - No auto-execution based on model confidence

- **Change kill-switch or halt conditions**
  - Circuit breakers remain fixed
  - No model-driven basis risk exceptions

- **Modify position-level risk rules**
  - Greeks limits, correlation limits, etc. fixed by policy

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ NEW MARKET DATA, ETF DISCLOSURES, RESEARCH SIGNALS          │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
        ┌────────────────────┐
        │ DATA QUALITY GATES │  Schema, timestamp, source, duplication,
        │                    │  outliers, missing values, lookahead bias
        └────────┬───────────┘
                 │ (passed only)
                 ▼
        ┌────────────────────┐
        │  FEATURE STORE     │  Append-only, time-indexed
        │                    │  features by observation ID
        └────────┬───────────┘
                 │
                 ├─────────────────────────────────────┐
                 │                                     │
                 ▼                                     ▼
        ┌──────────────────┐             ┌──────────────────────┐
        │ HISTORICAL EVENT │             │ HISTORICAL TRADES    │
        │ AND TRADE DATA   │             │ AND OUTCOMES         │
        │ INGEST           │             │ INGEST               │
        └────────┬─────────┘             └──────────┬───────────┘
                 │                                   │
                 └────────────────┬──────────────────┘
                                  │
                                  ▼
                         ┌────────────────────┐
                         │   ANALOG ENGINE    │  Setup fingerprints,
                         │                    │  similarity matching,
                         │                    │  outcome statistics
                         └────────┬───────────┘
                                  │
                 ┌────────────────┴─────────────────┐
                 │                                  │
┌────────────────┴────────────────┐    ┌─────────────────────────┐
│                                 │    │                         │
│   TRADE OUTCOME                 │    │ ML PREDICTIONS &        │
│   ├─ Thesis result              │    │ HISTORICAL CONTEXT      │
│   ├─ Instrument performance     │    │ ├─ Expected return      │
│   ├─ Timing quality             │    │ ├─ Drawdown risk        │
│   ├─ Hedge effectiveness        │    │ ├─ Thesis probability   │
│   └─ Position sizing quality    │    │ ├─ Hedge effectiveness  │
│                                 │    │ └─ Analog patterns      │
└─────────────┬────────────────────┘    └─────────────┬───────────┘
              │                                       │
              ▼                                       │
        ┌──────────────────────┐                    │
        │ OUTCOME LABELING     │                    │
        │ (Multi-dimensional)  │                    │
        └────────┬─────────────┘                    │
                 │                                  │
                 ▼                                  │
        ┌──────────────────────┐                    │
        │ TRAINING DATASET     │◄───────────────────┘
        │ (Features + Labels)  │
        └────────┬─────────────┘
                 │
                 ▼
        ┌──────────────────────┐
        │ WALK-FORWARD SPLITS  │  Time-series aware,
        │ (Time-series CV)     │  no lookahead bias
        └────────┬─────────────┘
                 │
                 ▼
        ┌──────────────────────┐
        │  MODEL TRAINING      │  Return, Drawdown,
        │                      │  Thesis Success,
        │                      │  Hedge Effectiveness
        └────────┬─────────────┘
                 │
                 ▼
        ┌──────────────────────┐
        │ EVALUATION GATES     │  OOS Performance,
        │ ├─ Sharpe            │  Calibration,
        │ ├─ Calibration       │  Risk Bounds,
        │ ├─ Risk Bounds       │  Regression,
        │ ├─ Regression        │  Drift Detection
        │ └─ Drift Detection   │
        └────────┬─────────────┘
                 │
          ┌──────┴──────┐
          │             │
       PASS           FAIL
          │             │
          ▼             ▼
     ┌─────────┐   ┌──────────┐
     │CHAMPION │   │  RETIRE  │
     │/CHALLEN-│   │          │
     │GER      │   └──────────┘
     │REGISTRY │
     └────┬────┘
          │
          ▼
    ┌──────────────────┐
    │ DECISION RECORD  │  Immutable audit trail
    │ (Model Training  │  - Dataset version
    │  & Promotion)    │  - Metrics & gates
    │                  │  - Promotion decision
    │                  │  - Approval chain
    └──────────────────┘
```

## Key Design Principles

1. **Governed Self-Improvement:** Models learn probabilities and rankings, not decisions.

2. **Deterministic Gates:** All promotion decisions must pass auditable, policy-backed gates.

3. **No Lookahead Bias:** Walk-forward validation ensures time-series models are not contaminated.

4. **Auditability:** Every training run and promotion creates immutable Decision Records.

5. **Human Approval:** Model promotions require explicit human approval and documented reasoning.

6. **Historical Grounding:** Analog retrieval provides interpretable context for predictions.

7. **Multi-Dimensional Learning:** Decompose outcomes across multiple dimensions for richer signals.

8. **Shadow Deployment:** Challengers run alongside champions before full promotion.

## Directory Structure

```
learning/
├── __init__.py
├── EXAMPLES.md                  # Usage examples and integration patterns
├── README.md                    # This file
├── schemas.py                   # Pydantic data contracts
├── data_quality.py              # Quality gates and feature store
├── labels.py                    # Outcome labeling service
├── dataset_builder.py           # Training dataset construction
├── models.py                    # Supervised learning models
├── training.py                  # Training pipeline with walk-forward validation
├── evaluation.py                # Evaluation gates and model comparator
├── registry.py                  # Model versioning and promotion
├── analogs.py                   # Historical analog retrieval
└── orchestrator.py              # Coordination and integration
```

## Getting Started

See `EXAMPLES.md` for detailed usage examples including:
- Basic model training workflow
- Outcome labeling from trades
- Model promotion workflow
- Historical analog retrieval
- Integration with Decision Records audit system

"""
