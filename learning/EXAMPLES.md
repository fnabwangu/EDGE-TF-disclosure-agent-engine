"""
Learning Engine Usage Examples and Integration Guide.

Path: learning/EXAMPLES.md

This document shows how to use the Learning Engine in EDGE-TF:

1. Basic model training workflow
2. Outcome labeling from trades
3. Model promotion workflow
4. Historical analog retrieval
5. Integration with Decision Records audit system
"""

# Example 1: Training a Return Prediction Model

from datetime import date
from learning.orchestrator import LearningOrchestrator
from learning.schemas import FeatureVector
import datetime

# Initialize the orchestrator
orchestrator = LearningOrchestrator(workspace_dir="data/learning")

# Ingest feature observations
observations = [
    FeatureVector(
        observation_id="obs_001",
        timestamp=datetime.datetime(2026, 1, 15, 10, 30),
        features={
            "conviction_score": 0.78,
            "disclosure_purity": 0.92,
            "basis_risk": 0.15,
            "theta_decay_rate": 0.02,
            "volatility_regime": 0.35,
            "liquidity_score": 0.88,
        },
    ),
    # ... more observations
]

for obs in observations:
    success, gate = orchestrator.ingest_observation(obs, source="EDGE_RESEARCH")
    if not success:
        print(f"Observation {obs.observation_id} failed quality gates: {gate.quality_issues}")
    else:
        print(f"Observation {obs.observation_id} passed, added to feature store")


# Example 2: Label Trade Outcomes

# When a trade completes, generate training labels from the outcome
assessment, labels = orchestrator.label_trade_outcome(
    thesis_id="thesis_iran_sanctions_2026",
    entry_date=date(2026, 1, 15),
    exit_date=date(2026, 2, 28),
    entry_price=85.5,
    exit_price=92.3,
    max_price=95.0,
    min_price=83.2,
    expected_return=0.08,
    expected_hedge_cost=0.019,
    realized_hedge_cost=0.018,
    expected_thesis="Secondary sanctions will tighten; energy equities will outperform",
    actual_outcome="Thesis partially confirmed; producer equities outperformed but less than expected",
)

print(f"Trade outcome assessment:")
print(f"  Actual return: {assessment.actual_return:.2%}")
print(f"  Thesis correctness: {assessment.thesis_correctness}")
print(f"  Instrument correctness: {assessment.instrument_correctness}")
print(f"  Timing correctness: {assessment.timing_correctness}")
print(f"  Hedge effectiveness: {assessment.hedge_effectiveness}")


# Example 3: Train and Evaluate Models

# Train a return prediction model using walk-forward validation
trained_cards = orchestrator.train_models(
    label_type="return",
    data_start=date(2018, 1, 1),
    data_end=date(2026, 8, 31),
    model_type="return",
)

model_card = trained_cards["return"]

print(f"Model trained: {model_card.model_id} v{model_card.version}")
print(f"  Training samples: {model_card.training_sample_size}")
print(f"  Out-of-sample samples: {model_card.out_of_sample_sample_size}")
print(f"  Out-of-sample Sharpe: {model_card.metrics.out_of_sample_sharpe:.3f}")
print(f"  Max drawdown: {model_card.metrics.max_drawdown:.2%}")


# Example 4: Evaluate and Promote Models

# Run comprehensive evaluation against all gates
gate_results, all_passed = orchestrator.evaluate_model(
    model_id=model_card.model_id,
    model_type="return",
)

print("Gate evaluation results:")
for gate_result in gate_results:
    status = "✓ PASS" if gate_result["passed"] else "✗ FAIL"
    print(f"  {status} {gate_result['gate']}: {gate_result['message']}")

# If all gates pass, promote to champion
if all_passed:
    promotion_result = orchestrator.promote_model(
        model_id=model_card.model_id,
        model_type="return",
        decision="promote",
        reasoning="New model exceeds champion on Sharpe, calibration, and risk metrics",
        approved_by="risk_committee",
    )
    print(f"Promotion approved: {promotion_result['decision']}")


# Example 5: Find Historical Analogs

# When analyzing a new setup, retrieve similar historical events and trades
analog_results = orchestrator.find_analogs(
    event_type="secondary_sanctions",
    region="middle_east",
    commodity="oil",
    implementation_type="long_producers_plus_index_hedge",
    min_similarity=0.60,
)

print(f"Analog retrieval results:")
print(f"  Confidence: {analog_results['confidence']}")
print(f"  Similar events: {analog_results['similar_events']}")
print(f"  Similar trades: {analog_results['similar_trades']}")
print(f"  Observed patterns:")
for pattern in analog_results['patterns']:
    print(f"    - {pattern}")

if analog_results['outcome_stats']:
    print(f"  Historical outcome stats:")
    for horizon, return_val in analog_results['outcome_stats'].items():
        if 'return' in horizon:
            print(f"    {horizon}: {return_val:.2%}")


# Example 6: Integration with Decision Records

from audit.decision_records import DecisionRecorder

recorder = DecisionRecorder()

# Record the training run
training_record = recorder.record_model_training(
    model_type="return",
    model_id=model_card.model_id,
    model_version=model_card.version,
    dataset_version="canonical_2026_08_31",
    training_start_date="2018-01-01",
    training_end_date="2026-08-31",
    feature_count=model_card.feature_count,
    training_sample_size=model_card.training_sample_size,
    out_of_sample_sample_size=model_card.out_of_sample_sample_size,
    metrics={
        "out_of_sample_sharpe": model_card.metrics.out_of_sample_sharpe,
        "max_drawdown": model_card.metrics.max_drawdown,
        "calibration_error": model_card.metrics.calibration_error,
        "r_squared": model_card.metrics.r_squared,
    },
    walk_forward_splits=7,
    feature_names=model_card.feature_names,
    code_version="1.0",
)

print(f"Training recorded to audit log: {training_record.record_id}")

# Record the promotion decision
promotion_record = recorder.record_model_promotion(
    model_type="return",
    model_id=model_card.model_id,
    model_version=model_card.version,
    promotion_decision="promote",
    gate_results={
        "oos_performance": True,
        "calibration": True,
        "risk_bounds": True,
        "regression": True,
        "drift_detection": True,
    },
    reasoning="Challenger outperforms champion on all key metrics",
    approved_by="risk_committee",
    champion_version="3.6",
)

print(f"Promotion recorded to audit log: {promotion_record.record_id}")


# Example 7: Shadow Deployment Tracking

# Before fully promoting, run model in shadow for observation period
shadow_performance = {
    "shadow_days": 14,
    "predictions_vs_actual_rmse": 0.045,
    "predictions_vs_actual_mae": 0.032,
    "drift_detected": False,
}

orchestrator.model_registry.set_shadow_deployment(
    model_id=model_card.model_id,
    model_type="return",
    shadow_performance=shadow_performance,
    notes="Running in shadow alongside champion for 2 weeks. Performance tracking on par with backtests.",
)


# POLICY ENFORCEMENT NOTES
#
# 1. ML Models May:
#    - Predict probabilities and confidence scores
#    - Rank implementations by expected return/risk
#    - Suggest position sizing based on risk metrics
#    - Inform thesis scoring with historical context
#
# 2. ML Models May NOT:
#    - Override deterministic risk limits
#    - Bypass execution approval gates
#    - Change max position size without policy change
#    - Modify kill-switch conditions
#
# 3. All Training Must:
#    - Use walk-forward validation (no lookahead bias)
#    - Pass out-of-sample performance gates
#    - Pass calibration gates
#    - Pass regression testing against champion
#    - Create auditable Decision Records
#
# 4. All Promotions Require:
#    - Human approval by risk committee
#    - Shadow deployment observation period
#    - All gates passing
#    - Documented reasoning
#    - Immutable audit trail in Decision Records
