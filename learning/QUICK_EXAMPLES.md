# Learning Engine - Code Examples

## Example 1: Recording a Trade Outcome

When a trade completes, record it for learning:

```python
from learning.coordinator import LearningEngineCoordinator
from datetime import date

coordinator = LearningEngineCoordinator()

# A thesis was: "Secondary sanctions on Iran tighten, XLE rallies"
# Implementation: Long XLE, hedge with SPY puts

attribution, labels = coordinator.record_trade_outcome(
    trade_id="TRADE_2026_08_001",
    thesis_id="THESIS_IRAN_SECONDARY_AUG2026",
    
    # Entry
    entry_date=date(2026, 8, 1),
    entry_price=52.30,
    expected_thesis_description="Secondary sanctions tighten, energy equities outperform",
    expected_instrument="XLE (Chevron energy ETF)",
    
    # Exit
    exit_date=date(2026, 8, 15),
    exit_price=58.10,
    
    # Realized path
    max_price_during_trade=59.20,
    min_price_during_trade=51.80,
    
    # Expected vs realized
    expected_return=0.114,
    actual_thesis_description="Sanctions escalated but tanker routing reduced actual supply loss",
    
    # Hedge performance
    expected_hedge_instrument="SPY puts (3-month)",
    expected_hedge_cost=0.019,
    realized_hedge_cost=0.015,
    
    # Position sizing
    expected_position_size_pct=0.03,
    
    # Context
    benchmark_return=0.005,  # SPY return during period
    analyst_notes="Thesis partially confirmed. Supply route-around more effective than expected.",
)

# See how the outcome was decomposed
print(f"Trade completed with {attribution.actual_return:.1%} return")
print(f"Thesis outcome: {attribution.thesis_outcome}")
print(f"\nOutcome decomposition:")

for outcome in attribution.outcomes:
    print(f"\n{outcome.dimension.value.upper()}: {outcome.rating.value}")
    print(f"  Contribution to return: {outcome.contribution_pct:.0f}%")
    print(f"  Evidence:")
    for evidence in outcome.evidence:
        print(f"    • {evidence}")

# Trading labels have been generated and registered
# Next time the model trains, it will use these dimensional outcomes
```

## Example 2: Training a Model

Train a new version of the return prediction model:

```python
from learning.coordinator import LearningEngineCoordinator
from datetime import date

coordinator = LearningEngineCoordinator()

# Train on 5+ years of data
model_card, training_run = coordinator.train_model(
    model_type="return",
    label_type="return",
    start_date=date(2020, 1, 1),
    end_date=date(2026, 8, 18),
    notes="Quarterly retraining with new outcome labels",
)

# Check results
if model_card:
    print(f"✓ Model trained successfully")
    print(f"  ID: {model_card.model_id}")
    print(f"  Version: {model_card.version}")
    print(f"  Status: {model_card.status}")
    print(f"\n  Performance:")
    print(f"    OOS Sharpe: {model_card.metrics.out_of_sample_sharpe:.2f}")
    print(f"    Max Drawdown: {model_card.metrics.max_drawdown:.2%}")
    print(f"    Calibration Error: {model_card.metrics.calibration_error:.3f}")
    print(f"    MAPE: {model_card.metrics.mape:.4f}")
    print(f"\n  Training:")
    print(f"    Samples: {model_card.training_sample_size}")
    print(f"    OOS Samples: {model_card.out_of_sample_sample_size}")
    print(f"    Features: {model_card.feature_count}")
    print(f"    Walk-forward splits: {len(model_card.promotion_history)} completed")
    
    # Model is automatically registered
    print(f"\n✓ Model registered in registry")
    print(f"✓ Decision Record created for audit trail")
else:
    print("✗ Training failed - no data available")
```

## Example 3: Shadow Deployment

Compare a new model against the current champion:

```python
from learning.coordinator import LearningEngineCoordinator

coordinator = LearningEngineCoordinator()

# Get the current champion and challenger
registry = coordinator.orchestrator.model_registry
champion = registry.get_champion("return")
challenger = registry.get_challenger("return")

if not challenger:
    print("No challenger model in shadow deployment")
else:
    # Start tracking if not already
    coordinator.start_shadow_deployment("return", challenger)
    
    # During hypothesis generation, evaluate both models
    features = {
        "etf_disclosure_score": 82.0,
        "volatility": 0.18,
        "momentum": 0.05,
    }
    
    champion_pred = champion.predict(features)
    challenger_pred = challenger.predict(features)
    
    print(f"Setup analyzed:")
    print(f"  Champion prediction (v{champion.version}): {champion_pred:.3f} return")
    print(f"  Challenger prediction (v{challenger.version}): {challenger_pred:.3f} return")
    print(f"  Difference: {(challenger_pred - champion_pred)*100:+.1f} bps")
    
    # Record both
    coordinator.record_shadow_prediction(
        model_type="return",
        observation_id="obs_123",
        champion_pred=champion_pred,
        challenger_pred=challenger_pred,
    )
    
    # Later, when the outcome is known
    actual_return = 0.087
    coordinator.record_shadow_outcome(
        model_type="return",
        observation_id="obs_123",
        actual_outcome=actual_return,
    )
    
    # Check performance
    metrics = coordinator.get_shadow_metrics("return")
    
    print(f"\nShadow Deployment Status:")
    print(f"  Days running: {metrics.days_in_shadow}")
    print(f"  Observations: {metrics.observation_count}")
    print(f"  Outcomes recorded: {metrics.outcome_count}")
    print(f"  Challenger MAPE: {metrics.challenger_mape:.4f}")
    print(f"  Champion MAPE: {metrics.champion_mape:.4f}")
    print(f"  Challenger wins: {metrics.challenger_beats_champion_count}/{metrics.outcome_count}")
    print(f"  Champion wins: {metrics.champion_beats_challenger_count}/{metrics.outcome_count}")
    
    if metrics.challenger_ready_for_promotion:
        print(f"\n✓ READY FOR PROMOTION")
        print(f"\nReasoning:")
        print(metrics.promotion_reasoning)
    else:
        print(f"\n✗ Not ready yet")
        print(f"\nWhy:")
        print(metrics.promotion_reasoning)
```

## Example 4: Promoting to Champion

Promote a challenger model after shadow validation:

```python
from learning.coordinator import LearningEngineCoordinator

coordinator = LearningEngineCoordinator()

# Check if ready
metrics = coordinator.get_shadow_metrics("return")

if metrics and metrics.challenger_ready_for_promotion:
    challenger = coordinator.orchestrator.model_registry.get_challenger("return")
    
    success = coordinator.promote_model(
        model_type="return",
        model_id=challenger.model_id,
        decision="promote",
        reasoning="Outperformed champion by 12% on shadow data over 67 days with 91 observations",
        approved_by="ml_ops_team",
    )
    
    if success:
        print(f"✓ Model {challenger.model_id} promoted to champion")
        print(f"✓ Decision Record created for audit trail")
        
        # Old champion retired, new champion active
        new_champion = coordinator.orchestrator.model_registry.get_champion("return")
        print(f"\n  New champion: {new_champion.model_id} v{new_champion.version}")
    else:
        print(f"✗ Promotion failed")
else:
    print("Shadow deployment not ready for promotion yet")
```

## Example 5: Analog Retrieval

Find historical context for a strategy:

```python
from learning.coordinator import LearningEngineCoordinator
from learning.analogs import SetupEncoder

coordinator = LearningEngineCoordinator()
encoder = SetupEncoder()

# Current situation: Iran threatens new sanctions on oil exports
# Build a fingerprint
fingerprint = encoder.encode_setup(
    event_type="secondary_sanctions",
    region="middle_east",
    asset_class="energy",
    commodity="oil",
    policy_mechanism="export_restrictions",
    supply_impact="high",  # Could disrupt major supply
    shipping_impact="high",  # Shipping restrictions expected
    financial_enforcement="high",  # Sanctions enforcement strong
    market_regime="risk_off",
    volatility_regime="elevated",
    liquidity_regime="normal",
)

# Find similar past events
analog_context = coordinator.find_similar_events(
    fingerprint=fingerprint,
    top_k=5,
    min_similarity=0.50,
)

print("=== Historical Analog Analysis ===\n")
print(f"Current setup match quality: {analog_context['similarity_confidence']}")
print(f"Historical similar events found: {analog_context['similar_events']}")
print(f"Similar trade implementations found: {analog_context['similar_trades']}")

print(f"\nObserved Historical Patterns:")
for pattern in analog_context['observed_patterns']:
    print(f"  • {pattern}")

print(f"\nRecommendations:")
for rec in analog_context['recommendations']:
    print(f"  • {rec}")

# Use this evidence when scoring the current thesis
print(f"\nUse case:")
print(f"  The model predicts +8% expected return")
print(f"  But historical analogs show this type of setup")
print(f"  actually favored producer equities (XLE) over crude (WTI)")
print(f"  Therefore: Adjust implementation to long XLE with small crude hedge")
```

## Example 6: Monitoring & Reporting

Get a comprehensive status report:

```python
from learning.coordinator import LearningEngineCoordinator

coordinator = LearningEngineCoordinator()

report = coordinator.generate_learning_engine_report()

print("=== LEARNING ENGINE STATUS REPORT ===\n")

# Models
print("📊 MODEL STATUS")
for model_type, status in report['models'].items():
    champion = status['champion']
    challenger = status['challenger']
    
    if champion or challenger:
        print(f"\n  {model_type.upper()}:")
        
        if champion:
            print(f"    Champion: {champion.model_id}")
            print(f"      Version: {champion.version}")
            print(f"      Sharpe: {champion.metrics.out_of_sample_sharpe:.2f}")
            print(f"      Max DD: {champion.metrics.max_drawdown:.2%}")
        else:
            print(f"    Champion: None")
        
        if challenger:
            print(f"    Challenger: {challenger.model_id}")
            print(f"      Version: {challenger.version}")
            print(f"      Sharpe: {challenger.metrics.out_of_sample_sharpe:.2f}")
        else:
            print(f"    Challenger: None")

# Shadow deployments
print("\n\n🔄 SHADOW DEPLOYMENT STATUS")
for model_type, metrics in report['shadow_deployments'].items():
    if metrics.observation_count > 0:
        print(f"\n  {model_type}:")
        print(f"    Days: {metrics.days_in_shadow}")
        print(f"    Observations: {metrics.observation_count}")
        print(f"    Outcomes: {metrics.outcome_count}/{metrics.observation_count}")
        print(f"    Challenger wins: {metrics.challenger_beats_champion_count}")
        print(f"    Champion wins: {metrics.champion_beats_challenger_count}")
        print(f"    Ready: {'✓ YES' if metrics.challenger_ready_for_promotion else '✗ No'}")

# Historical data
print("\n\n📚 HISTORICAL DATA AVAILABLE")
events = report['historical_data']['events']
trades = report['historical_data']['trades']
print(f"  Events: {events['total_events']}")
if events.get('event_types'):
    print(f"    Types: {', '.join(events['event_types'])}")
if events.get('regions'):
    print(f"    Regions: {', '.join(events['regions'])}")
print(f"  Trades: {trades['total_trades']}")
print(f"    Win rate: {trades.get('win_rate', 0):.0%}")

# Audit trail
print("\n\n📋 AUDIT TRAIL")
audit = report['audit_trail']
print(f"  Total decisions: {audit['total_decisions']}")
print(f"  Training runs: {audit['training_runs']}")
print(f"  Promotions: {audit['promotions']}")
```

## Example 7: Decision Records

Access the complete audit trail:

```python
from audit.decision_records import DecisionRecorder
from datetime import datetime, timedelta, timezone

recorder = DecisionRecorder()

# Get all training runs
print("=== MODEL TRAINING AUDIT TRAIL ===\n")

training_records = recorder.read_by_kind("MODEL_TRAINING")
print(f"Total training runs: {len(training_records)}\n")

for record in sorted(training_records, key=lambda r: r.at, reverse=True)[:5]:
    print(f"Training: {record.model}")
    print(f"  ID: {record.record_id}")
    print(f"  Time: {record.at}")
    print(f"  Input samples: {record.training_sample_size}")
    print(f"  OOS samples: {record.out_of_sample_sample_size}")
    print(f"  Features: {record.feature_count}")
    print(f"  Record hash: {record.record_hash[:16]}...")
    print()

# Get all promotions
print("\n=== MODEL PROMOTION AUDIT TRAIL ===\n")

promotions = recorder.read_by_kind("MODEL_PROMOTION")
print(f"Total promotions: {len(promotions)}\n")

for record in sorted(promotions, key=lambda r: r.at, reverse=True)[:3]:
    print(f"Promotion: {record.model}")
    print(f"  ID: {record.record_id}")
    print(f"  Time: {record.at}")
    print(f"  Decision: {'promote' if record.accepted_candidate_ids else 'hold/demote'}")
    print(f"  Gates evaluated: {len(record.validation_results)}")
    gates_passed = sum(1 for g in record.validation_results if g.get('passed'))
    print(f"  Gates passed: {gates_passed}/{len(record.validation_results)}")
    print()
```

## Example 8: Ingesting New Data

Add new observations to the feature store:

```python
from learning.coordinator import LearningEngineCoordinator
from learning.schemas import FeatureVector
from datetime import datetime, timezone

coordinator = LearningEngineCoordinator()

# Create an observation (simulating research feature extraction)
observation = FeatureVector(
    observation_id="obs_20260819_145",
    timestamp=datetime.now(timezone.utc),
    features={
        "etf_disclosure_score": 82.0,      # Conviction level
        "volatility": 0.18,                # Current IV
        "momentum": 0.05,                  # Trend
        "sanctions_intensity": 0.7,        # Policy severity
        "oil_supply_risk": 0.45,           # Supply disruption risk
        "shipping_capacity_impact": 0.3,   # Logistical impact
        "alternative_supply_available": 0.2,  # Route-around options
    }
)

# Ingest with validation
success, quality_gate = coordinator.orchestrator.ingest_observation(
    observation=observation,
    source="SEC_EDGAR",  # Trusted source
)

if success:
    print(f"✓ Observation {observation.observation_id} ingested")
    print(f"  Quality checks passed")
    print(f"  Features: {len(observation.features)}")
    
    # Now this observation is in the feature store
    # and will be matched with labels when the trade completes
else:
    print(f"✗ Observation rejected")
    print(f"  Failed checks: {quality_gate.quality_issues}")
```

## Common Patterns

### Monthly Maintenance

```python
from learning.coordinator import LearningEngineCoordinator
from datetime import date

coordinator = LearningEngineCoordinator()

print("=== MONTHLY LEARNING ENGINE MAINTENANCE ===\n")

# 1. Retrain all models
print("[1/4] Retraining models...")
for model_type in ["return", "drawdown", "thesis_success", "hedge_effectiveness"]:
    model_card, _ = coordinator.train_model(
        model_type=model_type,
        label_type=model_type,
        start_date=date(2020, 1, 1),
        end_date=date.today(),
    )
    if model_card:
        print(f"      ✓ {model_type}: Sharpe {model_card.metrics.out_of_sample_sharpe:.2f}")

# 2. Check shadow deployments
print("\n[2/4] Checking shadow deployments...")
for model_type in ["return", "drawdown", "thesis_success", "hedge_effectiveness"]:
    metrics = coordinator.get_shadow_metrics(model_type)
    if metrics and metrics.observation_count > 0:
        status = "READY" if metrics.challenger_ready_for_promotion else "In progress"
        print(f"      {model_type}: {metrics.days_in_shadow} days [{status}]")

# 3. Promote ready models
print("\n[3/4] Promoting ready models...")
for model_type in ["return", "drawdown", "thesis_success", "hedge_effectiveness"]:
    challenger = coordinator.orchestrator.model_registry.get_challenger(model_type)
    if challenger:
        metrics = coordinator.get_shadow_metrics(model_type)
        if metrics and metrics.challenger_ready_for_promotion:
            coordinator.promote_model(
                model_type=model_type,
                model_id=challenger.model_id,
                decision="promote",
                reasoning="Shadow deployment successful",
                approved_by="ml_team",
            )
            print(f"      ✓ {model_type} promoted")

# 4. Summary
print("\n[4/4] Status summary...")
report = coordinator.generate_learning_engine_report()
audit = report['audit_trail']
print(f"      Training runs total: {audit['training_runs']}")
print(f"      Promotions total: {audit['promotions']}")
print(f"      Historical events: {report['historical_data']['events']['total_events']}")

print("\n✓ Monthly maintenance complete")
```
