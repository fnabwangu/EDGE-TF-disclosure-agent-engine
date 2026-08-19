"""
Learning Engine Integration with EDGE Orchestration.

Path: learning/INTEGRATION_GUIDE.md

Step-by-step guide for integrating the Learning Engine with EDGE's existing
orchestration, research, and execution layers.
"""

# Learning Engine Integration Guide

## Overview

The Learning Engine now provides:
- ML predictions for thesis scoring and implementation ranking
- Historical analog context to ground research decisions
- Outcome assessment for continuous model improvement
- Full audit trail via Decision Records

This guide shows how to integrate the Learning Engine into each phase of EDGE's workflow.

## Architecture: Learning Engine in EDGE Pipeline

```
RESEARCH PHASE
    ├─ Idea generation
    ├─ Analog retrieval (via LearningEngine)
    ├─ Historical patterns
    └─ Risk/reward estimates

IMPLEMENTATION PHASE
    ├─ Implementation design
    ├─ ML scoring (via LearningEngine)
    ├─ Position sizing suggestion
    └─ Approval gates (deterministic)

EXECUTION PHASE
    ├─ Order submission
    ├─ Risk monitoring
    └─ Daily tracking

OUTCOME PHASE
    ├─ Trade completion
    ├─ Outcome assessment (via LearningEngine)
    ├─ Multi-dimensional labels
    └─ Continuous training

MODEL IMPROVEMENT
    ├─ Dataset building
    ├─ Walk-forward training
    ├─ Gate evaluation
    ├─ Promotion decision
    └─ Audit recording
```

## Phase 1: Research Phase Integration

### What Happens

During the research phase, EDGE generates thesis ideas and evaluates them. The Learning Engine provides:

1. **Historical Analogs** - Similar past events and how they played out
2. **Pattern Recognition** - What worked and didn't work historically
3. **Return Distributions** - Expected return ranges from past similar setups

### Implementation

**File:** `orchestration/research.py` or similar research phase handler

```python
from learning.integration import ResearchPhaseIntegration
from learning.orchestrator import LearningOrchestrator

# Initialize during research setup
orchestrator = LearningOrchestrator()
research_integration = ResearchPhaseIntegration(
    LearningEngineIntegration(orchestrator)
)

# During thesis generation
def evaluate_thesis_idea(event_type, region, commodity):
    """
    Enrich thesis idea with historical context.
    """
    enrichment = research_integration.enrich_research_with_analogs(
        event_type=event_type,
        region=region,
        commodity=commodity,
    )
    
    thesis.analog_confidence = enrichment["analog_confidence"]
    thesis.historical_patterns = enrichment["historical_patterns"]
    thesis.historical_returns = enrichment["historical_returns"]
    
    # Display to researcher
    print(f"Similar historical events: {enrichment['num_similar_events']}")
    print(f"Patterns: {enrichment['historical_patterns']}")
    print(f"Historical 20-day return: {enrichment['historical_returns']['20d']:.2%}")
    
    return thesis
```

### Integration Points

- `orchestration/agent.py` → Call `find_analogs()` when generating thesis descriptions
- `research/funnel.py` → Annotate thesis objects with analog data
- `research/implementations.py` → Provide historical context for implementation choice

---

## Phase 2: Implementation Phase Integration

### What Happens

During implementation design, the Learning Engine provides:

1. **ML Predictions** - Expected return, drawdown, hedge effectiveness
2. **Scoring** - Rank implementations by risk-adjusted return
3. **Sizing Suggestion** - Recommend position size based on risk

### Implementation

**File:** `orchestration/implementation.py` or similar

```python
from learning.integration import ImplementationPhaseIntegration
from learning.orchestrator import LearningOrchestrator

# Initialize
orchestrator = LearningOrchestrator()
impl_integration = ImplementationPhaseIntegration(
    LearningEngineIntegration(orchestrator)
)

# During implementation evaluation
def score_implementation(implementation):
    """
    Score implementation using ML predictions.
    """
    # Extract features from implementation
    features = {
        "conviction_score": implementation.thesis.conviction,
        "disclosure_purity": implementation.purity_score,
        "basis_risk": implementation.basis_risk,
        # ... other features
    }
    
    # Get ML scoring
    score = impl_integration.score_implementation(
        implementation_type=implementation.type,
        features=features,
        position_size=implementation.nominal_allocation,
        hedge_type=implementation.hedge,
    )
    
    implementation.ml_expected_return = score["expected_return"]
    implementation.ml_expected_drawdown = score["expected_drawdown"]
    implementation.ml_risk_adjusted_return = score["risk_adjusted_return"]
    implementation.ml_suggested_size = score["suggested_position_size"]
    implementation.ml_confidence = score["confidence_level"]
    
    # Display to trader
    print(f"ML Expected Return: {score['expected_return']:.2%}")
    print(f"ML Expected Drawdown: {score['expected_drawdown']:.2%}")
    print(f"ML Suggested Size: {score['suggested_position_size']:.2%}")
    print(f"Recommendation: {score['ml_recommendation']}")
    
    return score
```

### Ranking Multiple Implementations

```python
def rank_implementations(implementations):
    """
    Rank implementations by ML scoring.
    """
    scores = []
    
    for impl in implementations:
        score = impl_integration.score_implementation(
            implementation_type=impl.type,
            features=extract_features(impl),
            position_size=impl.nominal_allocation,
        )
        scores.append({
            "implementation": impl,
            "score": score,
            "risk_adj_return": score["risk_adjusted_return"],
        })
    
    # Sort by risk-adjusted return
    scores.sort(key=lambda x: x["risk_adj_return"], reverse=True)
    
    # Display rankings
    for rank, item in enumerate(scores, 1):
        print(f"{rank}. {item['implementation'].type}")
        print(f"   Risk-Adj Return: {item['score']['risk_adjusted_return']:.3f}")
        print(f"   Confidence: {item['score']['confidence_level']:.2%}")
    
    return scores
```

### Key Points

- ML scoring is **advisory** - traders still make final decisions
- ML output flows through approval gates like everything else
- Position sizing is a **suggestion** - deterministic limits still apply
- Low confidence predictions are flagged to user

### Integration Points

- `orchestration/ui_composer.py` → Display ML scores on implementation cards
- `approvals/service.py` → Consider ML confidence in approval logic
- `execution/order_router.py` → Use suggested sizing as input to order construction

---

## Phase 3: Execution Phase Integration

### What Happens

During execution, the Learning Engine:

1. **Monitors predictions** - Track whether ML predictions were accurate
2. **Detects drift** - Identify if market conditions changed
3. **Records performance** - Accumulate performance data for retraining

### Implementation

**File:** `orchestration/monitoring.py` or similar

```python
from learning.integration import MonitoringPhaseIntegration
from learning.orchestrator import LearningOrchestrator

# Initialize monitoring
orchestrator = LearningOrchestrator()
monitor_integration = MonitoringPhaseIntegration(
    LearningEngineIntegration(orchestrator)
)

# During daily monitoring
def track_position_performance(position, daily_return):
    """
    Track position performance vs ML predictions for model monitoring.
    """
    if position.ml_expected_return:
        # Record error for shadow deployment tracking
        monitor_integration.track_model_performance(
            model_type="return",
            actual_return=daily_return,
            predicted_return=position.ml_expected_return,
        )
        
        # Check for unexpected behavior
        prediction_error = abs(daily_return - position.ml_expected_return)
        if prediction_error > 2 * abs(position.ml_expected_return):
            alert(f"Large prediction error: predicted {position.ml_expected_return:.2%}, got {daily_return:.2%}")
```

### Integration Points

- `orchestration/guardrails.py` → Monitor prediction accuracy
- `audit/audit_logger.py` → Log prediction performance
- Daily reconciliation scripts → Track model performance

---

## Phase 4: Outcome Assessment Phase

### What Happens

When a trade completes:

1. **Outcome Assessment** - Multi-dimensional evaluation of what worked
2. **Label Generation** - Convert outcome to training labels
3. **Dataset Integration** - Add labels to training dataset

### Implementation

**File:** `orchestration/outcomes.py` or similar

```python
from learning.integration import MonitoringPhaseIntegration
from datetime import date

def process_trade_completion(trade):
    """
    Process completed trade and generate training labels.
    """
    monitor_integration = MonitoringPhaseIntegration(
        LearningEngineIntegration(orchestrator)
    )
    
    # Record outcome
    assessment = monitor_integration.process_trade_completion(
        thesis_id=trade.thesis_id,
        entry_date=trade.entry_date,
        exit_date=trade.exit_date,
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        max_price=trade.max_price,
        min_price=trade.min_price,
        expected_return=trade.expected_return,
        expected_hedge_cost=trade.expected_hedge_cost,
        realized_hedge_cost=trade.realized_hedge_cost,
        thesis_description=trade.thesis.description,
        outcome_description=trade.outcome_narrative,
    )
    
    # Save outcome assessment
    trade.outcome_assessment = assessment
    
    # Log components
    print(f"Trade {trade.trade_id} outcome assessment:")
    print(f"  Actual return: {assessment['actual_return']:.2%}")
    print(f"  Thesis correctness: {assessment['thesis_assessment']}")
    print(f"  Instrument choice: {assessment['instrument_assessment']}")
    print(f"  Timing quality: {assessment['timing_assessment']}")
    print(f"  Hedge effectiveness: {assessment['hedge_assessment']:.2%}")
    print(f"  Sizing: {assessment['sizing_assessment']}")
    print(f"  Training labels generated: {assessment['training_labels_generated']}")
    
    # Create decision record (if not already created)
    record_outcome_to_audit(assessment)
```

### Multi-Dimensional Labels

The outcome assessment generates **4 training labels** from each trade:

1. **Return Label** - Actual return (for return model training)
2. **Drawdown Label** - Maximum drawdown experienced (for risk model)
3. **Thesis Success Label** - Was the thesis validated? (for thesis model)
4. **Hedge Effectiveness Label** - Did hedge work? (for hedge model)

This provides richer training signal than binary win/loss.

### Integration Points

- `orchestration/agent.py` → Call `process_trade_completion()` when trade exits
- `research/implementations.py` → Record implementation outcomes
- Nightly reconciliation → Batch process completed trades

---

## Phase 5: Model Training & Promotion Pipeline

### What Happens

Once sufficient outcomes accumulate (50+ labeled trades):

1. **Dataset Building** - Combine features and labels
2. **Walk-Forward Training** - Train models with time-series validation
3. **Gate Evaluation** - Check models pass all promotion gates
4. **Promotion** - Champion/challenger versioning
5. **Decision Recording** - Audit trail via Decision Records

### Running First Training Cycle

**File:** `learning/first_training_cycle.py`

```bash
cd /workspaces/EDGE-TF-disclosure-agent-engine
python learning/first_training_cycle.py
```

This will:
1. Load historical data
2. Generate sample observations and labels
3. Train return model with walk-forward validation
4. Evaluate against all gates
5. Promote to champion if gates pass
6. Record decisions to audit log

### Running Continuous Training

```python
from learning.orchestrator import LearningOrchestrator
from audit.decision_records import DecisionRecorder
from datetime import date

def run_training_cycle():
    """
    Run periodic training cycle (monthly, weekly, etc.).
    """
    orchestrator = LearningOrchestrator()
    recorder = DecisionRecorder()
    
    # Build training dataset
    examples = orchestrator.dataset_builder.build_training_dataset(
        label_type="return",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    
    if len(examples) < 50:
        print("Insufficient training examples. Skipping training cycle.")
        return
    
    # Train models
    trained_cards = orchestrator.train_models(
        label_type="return",
        data_start=date(2024, 1, 1),
        data_end=date(2024, 12, 31),
    )
    
    model_card = trained_cards["return"]
    
    # Evaluate
    gate_results, all_passed = orchestrator.evaluate_model(
        model_id=model_card.model_id,
        model_type="return",
    )
    
    # Record training
    recorder.record_model_training(
        model_type=model_card.model_type,
        model_id=model_card.model_id,
        model_version=model_card.version,
        dataset_version="canonical_2024",
        training_start_date="2024-01-01",
        training_end_date="2024-12-31",
        feature_count=model_card.feature_count,
        training_sample_size=model_card.training_sample_size,
        out_of_sample_sample_size=model_card.out_of_sample_sample_size,
        metrics={
            "out_of_sample_sharpe": model_card.metrics.out_of_sample_sharpe,
            "max_drawdown": model_card.metrics.max_drawdown,
            "calibration_error": model_card.metrics.calibration_error,
        },
        walk_forward_splits=7,
        feature_names=model_card.feature_names,
    )
    
    # If gates pass, promote
    if all_passed:
        orchestrator.promote_model(
            model_id=model_card.model_id,
            model_type="return",
            decision="promote",
            reasoning="New model passes all gates with improved Sharpe",
            approved_by="training_pipeline",
        )
        
        recorder.record_model_promotion(
            model_type=model_card.model_type,
            model_id=model_card.model_id,
            model_version=model_card.version,
            promotion_decision="promote",
            gate_results={g["gate"]: g["passed"] for g in gate_results},
            reasoning="All gates passed",
            approved_by="training_pipeline",
        )
```

### Shadow Deployment

Before promoting new model:

```python
def run_shadow_deployment(days=14):
    """
    Run challenger model in shadow for specified days.
    """
    orchestrator = LearningOrchestrator()
    monitor = MonitoringPhaseIntegration(LearningEngineIntegration(orchestrator))
    
    # Run challenger alongside champion
    for _ in range(days):
        # Get both predictions
        champion_pred = get_champion_prediction()
        challenger_pred = get_challenger_prediction()
        
        # Track challenger performance
        actual_return = get_actual_market_return()
        monitor.track_model_performance(
            model_type="return",
            actual_return=actual_return,
            predicted_return=challenger_pred,
        )
    
    # Evaluate shadow performance
    report = monitor.get_shadow_deployment_report("return")
    
    if report["ready_for_promotion"]:
        orchestrator.promote_model(
            model_id=challenger_id,
            model_type="return",
            decision="promote",
            reasoning=f"Shadow deployment: {report['avg_error']:.4f} avg error",
            approved_by="risk_committee",
        )
```

### Integration Points

- `orchestration/scheduler.py` → Schedule training cycles (weekly/monthly)
- `orchestration/monitoring.py` → Track model performance
- Decision Records → Audit all training and promotion

---

## Integration Checklist

### ✅ Research Phase
- [ ] Import `ResearchPhaseIntegration`
- [ ] Call `enrich_research_with_analogs()` during thesis generation
- [ ] Display historical patterns and returns to researcher
- [ ] Store analog data with thesis object

### ✅ Implementation Phase
- [ ] Import `ImplementationPhaseIntegration`
- [ ] Extract features from implementation
- [ ] Call `score_implementation()` for each candidate
- [ ] Display ML predictions in implementation cards
- [ ] Use ML suggested sizing as input to order construction
- [ ] Respect deterministic size limits regardless of ML output

### ✅ Execution Phase
- [ ] Import `MonitoringPhaseIntegration`
- [ ] Track position performance vs ML predictions
- [ ] Monitor prediction errors for drift detection
- [ ] Alert on large unexpected moves

### ✅ Outcome Phase
- [ ] Call `process_trade_completion()` when trades exit
- [ ] Record multi-dimensional assessments
- [ ] Store training labels in dataset
- [ ] Create outcome decision records

### ✅ Training Phase
- [ ] Run `first_training_cycle.py` to train initial models
- [ ] Schedule periodic training cycles (weekly/monthly)
- [ ] Implement shadow deployment for challengers
- [ ] Record all training and promotion to Decision Records

---

## Data Flow Example: End-to-End

```
1. RESEARCH PHASE
   Analyst: "Thinking about secondary sanctions on Iran oil"
   
   → find_analogs("secondary_sanctions", "middle_east", "oil")
   ← Historical analog: 2022 Iran escalation, 5 similar events
   ← Patterns: "Producer equities outperformed direct crude 3/5 times"
   ← Historical 20-day return: 8.7%
   
2. IMPLEMENTATION PHASE
   Analyst: "Long XLE (producer equity ETF) with put spreads"
   
   → score_implementation(
       type="long_producers_plus_hedges",
       features={"conviction": 0.8, ...},
       allocation=0.03,
     )
   ← Expected return: 7.2%, Expected drawdown: 3.5%
   ← Suggested size: 3.2% (vs proposed 3.0%)
   ← Confidence: 65%, Recommendation: "Hedge effectiveness could be higher"

3. APPROVAL GATES
   Deterministic gates evaluate:
   - Position size ≤ 5% ✓
   - Basis risk ≤ 15% ✓
   - Convictions ≥ 0.6 ✓
   - Approval: APPROVED

4. EXECUTION PHASE
   Order submitted: 3.2% XLE, 1.2% PUT_SPREADS
   Daily tracking:
   - ML predicted 7.2% for 20 days
   - Actual daily return tracking
   - Error monitoring: < 0.5% drift OK
   
5. OUTCOME PHASE (Day 20, trade exits)
   Realized return: +8.1% (vs predicted 7.2%)
   Max drawdown: -2.1% (vs predicted -3.5%)
   
   → process_trade_completion(
       actual_return=0.081,
       max_drawdown=-0.021,
       expected_thesis="sanctions escalation",
       actual_outcome="thesis confirmed; producers outperformed",
     )
   ← Outcome assessment:
     - Thesis correctness: "confirmed"
     - Instrument correctness: "correct"
     - Timing correctness: "good"
     - Hedge effectiveness: "very effective"
     - Sizing: "appropriate"
   ← Training labels generated: 4 labels (return, drawdown, thesis, hedge)

6. MODEL TRAINING (accumulate 50+ outcomes)
   → train_models("return", start=2024-01-01, end=2024-12-31)
   ← Training run: 100 samples, 25 OOS, Sharpe 0.85, Calibration 0.08
   ← Gate evaluation: ✓ OOS ✓ Calibration ✓ Risk ✓ Drift
   ← Promotion: PROMOTE to champion
   ← Decision record created: MODEL_PROMOTION decision_id=uuid

7. CONTINUOUS IMPROVEMENT
   Next cycle: Collect 50 more outcomes
   New model: Sharpe 0.92 (vs 0.85), all gates pass
   Shadow deployment: 14 days, error 0.045
   Promotion: PROMOTE new model to champion
```

---

## Monitoring Dashboard

Recommend creating dashboard showing:

**Live Metrics:**
- Current champion model version
- Current challenger (if any)
- Days in shadow deployment
- Prediction errors (rolling 7-day)

**Training Progress:**
- Labeled outcomes collected
- Next training cycle date
- Training/OOS samples
- Last training date

**Model Performance:**
- Champion Sharpe
- Champion calibration error
- Challenger performance vs champion
- Prediction drift indicators

**Audit Trail:**
- Last promotion decision
- Approval chain
- Gate results
- Training record links

---

## Troubleshooting

### Issue: No champion model available

**Symptoms:** ML predictions always return confidence 0.0

**Causes:**
- First training cycle hasn't run yet
- All models failed gate evaluation

**Solution:**
1. Run `python learning/first_training_cycle.py`
2. Check gate results in output
3. Review model metrics

### Issue: Very low prediction accuracy

**Symptoms:** Model predictions consistently wrong

**Causes:**
- Insufficient training data (<50 samples)
- Features not predictive of outcomes
- Data quality issues

**Solution:**
1. Check data quality gates in logs
2. Verify feature engineering
3. Check for lookahead bias in training data
4. Train with more data (50+ outcomes minimum)

### Issue: Model fails evaluation gates

**Symptoms:** Trained model won't promote

**Causes:**
- Out-of-sample Sharpe < 0.3
- Calibration error > 0.15
- Max drawdown prediction > 20%

**Solution:**
1. Review gate results for which gate failed
2. Check model metrics
3. Consider feature engineering improvements
4. Verify data quality

---

## Next Steps

1. ✅ Learning Engine modules created
2. ✅ Integration layer built
3. ✅ Historical data loader ready
4. ✅ First training cycle script provided
5. **→ Connect to orchestration layer**
6. **→ Populate historical analogs**
7. **→ Start collecting trade outcomes**
8. **→ Run periodic training cycles**
9. **→ Promote models as gates pass**
10. **→ Monitor production performance**

---

## Support

For questions or issues:
- Review `learning/README.md` for architecture
- Review `learning/EXAMPLES.md` for code examples
- Check `learning/IMPLEMENTATION_SUMMARY.md` for overview
- Run tests: `pytest tests/test_learning.py`
