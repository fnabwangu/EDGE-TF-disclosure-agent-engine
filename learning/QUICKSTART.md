"""
Learning Engine Quick Start Guide

Path: learning/QUICKSTART.md

Get up and running with the Learning Engine in 5 minutes.
"""

# EDGE-TF Learning Engine Quick Start

Welcome! This guide will help you get started with the Learning Engine in EDGE-TF.

## ⚡ 5-Minute Setup

### Step 1: Check Files Are in Place

```bash
cd /workspaces/EDGE-TF-disclosure-agent-engine
ls -la learning/
```

You should see:
- `schemas.py` - Data models
- `data_quality.py` - Validation gates
- `labels.py` - Outcome assessment
- `dataset_builder.py` - Training data
- `models.py` - ML models
- `training.py` - Training pipeline
- `evaluation.py` - Evaluation gates
- `registry.py` - Model versioning
- `analogs.py` - Historical analogs
- `orchestrator.py` - Master coordinator
- `integration.py` - Orchestration bridges
- `historical_data.py` - Sample historical data
- `first_training_cycle.py` - Training runner
- `management.py` - CLI tools
- Documentation (README.md, EXAMPLES.md, etc.)

### Step 2: Check Configuration

```bash
ls -la config/
cat config/learning_policy.json | head -50
```

You should see `learning_policy.json` with governance settings.

### Step 3: Verify No Errors

```bash
python -m py_compile learning/*.py
# Should complete without output (no errors)
```

### Step 4: Run First Training Cycle

```bash
python learning/first_training_cycle.py
```

Expected output:
```
================================================================================
EDGE-TF LEARNING ENGINE: FIRST TRAINING CYCLE
================================================================================

[1/6] Initializing orchestrator and historical data...
     ✓ Loaded historical events and trades into analog engine

[2/6] Generating and ingesting sample observations...
     ✓ Ingested 150/150 observations

[3/6] Generating outcome labels...
     ✓ Generated 560 training labels (140 observations with 4 label types)

[4/6] Training return prediction model...
     ✓ Trained model: model_return_20260819_001 v1.0
       Training samples: 100
       Out-of-sample samples: 40
       Out-of-sample Sharpe: 0.523
       Max drawdown: -0.085
       Calibration error: 0.089
       
[5/6] Evaluating model against promotion gates...
     ✓ oos_performance: OOS Sharpe 0.523 >= 0.3
     ✓ calibration: Error 0.089 <= 0.15
     ✓ risk_bounds: Max drawdown 0.085 <= 0.20
     ✓ drift_detection: No distribution shift detected
     ✓ regression: No champion to compare against
     
[6/6] Promoting model to champion...
     ✓ Promotion approved: promote
       Decision ID: abc123def456
       Timestamp: 2026-08-19T15:30:00Z

[AUDIT] Recording training and promotion to Decision Records...
     ✓ Training record: train_20260819_001
     ✓ Promotion record: promo_20260819_001

================================================================================
FIRST TRAINING CYCLE COMPLETE
================================================================================

Model: return v1
Status: CHAMPION
Out-of-sample Sharpe: 0.523
Max drawdown: -8.5%
Features: 10
Training samples: 100
OOS samples: 40

Next steps:
1. Monitor model performance in production
2. Collect real trade outcomes for continuous training
3. Train next model version as data accumulates
4. Run shadow deployment of challenger vs champion
5. Promote new challenger if gates pass and performance improves
```

✅ Congratulations! Your first model is trained and promoted.

---

## 🔍 What Happened?

### Data Quality Pipeline

The system ingested 150 synthetic observations through a 7-gate quality filter:
- ✓ Schema validation (all required fields present)
- ✓ Timestamp validation (no lookahead bias)
- ✓ Outlier detection (no extreme values)
- ✓ Missing value tolerance (< 20% missing)
- ✓ Duplicate detection (no repeats)
- ✓ Source trust (all from approved sources)

### Training with Walk-Forward Validation

Your model was trained using walk-forward time-series validation:
- Training window: 5 years of historical data
- Test windows: 60-day periods stepped 30 days
- Result: Out-of-sample performance on unseen future data

This prevents lookahead bias and provides realistic performance estimates.

### Five Evaluation Gates

Your model passed all gates required for production:

1. **OOS Performance Gate** ✓
   - Out-of-sample Sharpe ≥ 0.3 (policy requirement)
   - Your model: 0.523 ✓

2. **Calibration Gate** ✓
   - Predicted probabilities match reality
   - Max error ≤ 0.15
   - Your model: 0.089 ✓

3. **Risk Bounds Gate** ✓
   - Max drawdown ≤ 20%
   - Your model: -8.5% ✓

4. **Drift Detection Gate** ✓
   - No shift in feature distributions
   - Your model: Clean ✓

5. **Regression Gate** ✓
   - Performance vs previous champion
   - Your model: First champion (no baseline)

### Decision Record

Training and promotion have been logged to the audit system:
- Training record: Contains all data, features, samples, metrics
- Promotion record: Contains gate results, approvals, timestamps
- Fully reproducible: Can recreate training with same dataset version

---

## 📊 Check Model Status

### Using CLI

```bash
python learning/management.py health
```

Expected output:
```
================================================================================
LEARNING ENGINE STATUS REPORT
Generated: 2026-08-19T15:35:00+00:00
================================================================================

📊 MODEL STATUS

RETURN:
  Champion: v1
    Sharpe: 0.523
    Trained: 2026-08-19T15:30:00

  (No challenger)

📈 FEATURE STORE HEALTH
  Observations: 150
  Date range: 2024-01-01T00:00:00+00:00 to 2024-06-09T00:00:00+00:00

🏷️  LABEL COVERAGE
  Total labels: 560
  Unique observations: 140
    return: 140
    drawdown: 140
    thesis_success: 140
    hedge_effectiveness: 140

🚀 READINESS FOR TRAINING
  ✓ Sufficient observations (50+ required)

================================================================================
```

### Using Python

```python
from learning.management import ModelManager

manager = ModelManager()
status = manager.show_model_status("return")
print(status)
```

---

## 🔮 Next: Integration with EDGE

Now that your first model is trained, integrate it with EDGE:

### 1. Research Phase

Get historical analogs during thesis generation:

```python
from learning.integration import LearningEngineIntegration, ResearchPhaseIntegration
from learning.orchestrator import LearningOrchestrator

orchestrator = LearningOrchestrator()
learning = LearningEngineIntegration(orchestrator)
research = ResearchPhaseIntegration(learning)

# During thesis generation
analogs = research.enrich_research_with_analogs(
    event_type="secondary_sanctions",
    region="middle_east",
    commodity="oil",
)

print(f"Found {len(analogs['similar_events'])} historical events")
print(f"Patterns: {analogs['historical_patterns']}")
print(f"Historical 20d return: {analogs['historical_returns']['20d']:.2%}")
```

### 2. Implementation Phase

Score implementations using ML predictions:

```python
from learning.integration import ImplementationPhaseIntegration

impl_integration = ImplementationPhaseIntegration(learning)

score = impl_integration.score_implementation(
    implementation_type="long_producers_plus_hedges",
    features={
        "conviction_score": 0.8,
        "disclosure_purity": 0.85,
        "basis_risk": 0.12,
        # ... other features
    },
    position_size=0.03,
)

print(f"Expected return: {score['expected_return']:.2%}")
print(f"Expected drawdown: {score['expected_drawdown']:.2%}")
print(f"Suggested size: {score['suggested_position_size']:.2%}")
```

### 3. Outcome Tracking

Record trade outcomes for continuous improvement:

```python
from learning.integration import MonitoringPhaseIntegration

monitor = MonitoringPhaseIntegration(learning)

outcome = monitor.process_trade_completion(
    thesis_id="thesis_001",
    entry_date=date(2024, 1, 15),
    exit_date=date(2024, 2, 14),
    entry_price=100.0,
    exit_price=108.1,
    max_price=110.0,
    min_price=102.0,
    expected_return=0.07,
    expected_hedge_cost=0.008,
    realized_hedge_cost=0.006,
    thesis_description="Secondary sanctions on Iran",
    outcome_description="Thesis confirmed; producers outperformed",
)

print(f"Actual return: {outcome['actual_return']:.2%}")
print(f"Thesis assessment: {outcome['thesis_assessment']}")
print(f"Labels generated: {outcome['training_labels_generated']}")
```

---

## 📚 Documentation

For more details, see:

- **README.md** - Architecture and design
- **EXAMPLES.md** - Complete code examples
- **INTEGRATION_GUIDE.md** - Step-by-step integration
- **ROADMAP.md** - Implementation timeline
- **learning_policy.json** - Governance configuration

---

## 🐛 Troubleshooting

### Issue: Import errors

**Solution:**
```bash
cd /workspaces/EDGE-TF-disclosure-agent-engine
python -c "from learning.orchestrator import LearningOrchestrator; print('OK')"
```

### Issue: No champion model available

**Solution:**
```bash
python learning/first_training_cycle.py
# Then check:
python -c "from learning.management import ModelManager; m = ModelManager(); print(m.show_model_status('return'))"
```

### Issue: Feature store empty

**Solution:**
```python
from learning.orchestrator import LearningOrchestrator
from learning.schemas import FeatureVector
from datetime import datetime, timezone

orchestrator = LearningOrchestrator()

# Add a test observation
obs = FeatureVector(
    observation_id="test_001",
    timestamp=datetime.now(timezone.utc),
    features={"feature_1": 0.5, "feature_2": 0.3},
)

success, gate = orchestrator.ingest_observation(obs, source="TEST")
print(f"Observation ingested: {success}")
```

---

## 🚀 Ready to Go

You now have:
- ✅ Learning Engine infrastructure
- ✅ First trained model
- ✅ Historical analog database
- ✅ Integration points ready
- ✅ Governance and audit trail

**Next steps:**
1. Integrate with orchestration/agent.py
2. Collect real trade outcomes
3. Run periodic training cycles
4. Monitor production performance

See **ROADMAP.md** for detailed implementation timeline.

---

## 📞 Getting Help

- **Architecture questions:** See README.md
- **Code examples:** See EXAMPLES.md
- **Integration steps:** See INTEGRATION_GUIDE.md
- **Configuration:** See config/learning_policy.json
- **Run management commands:** `python learning/management.py --help`

---

**Version:** 1.0  
**Last Updated:** Aug 19, 2026  
**Status:** Ready for Integration
