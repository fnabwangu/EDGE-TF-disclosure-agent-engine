"""
First training cycle pipeline.

Path: learning/first_training_cycle.py

Demonstrates and runs the first training cycle for EDGE models.

Workflow:
1. Initialize orchestrator and historical data
2. Create sample training dataset from collected observations
3. Train initial models (target: return model)
4. Evaluate models against all gates
5. Promote first champion
6. Record decisions to audit log
"""

from datetime import datetime, date, timezone, timedelta
from pathlib import Path
from typing import Dict, List
import json

from learning.orchestrator import LearningOrchestrator
from learning.historical_data import create_historical_loader
from learning.schemas import FeatureVector, TrainingLabel
from learning.data_quality import DataQualityConfig
from audit.decision_records import DecisionRecorder


def generate_sample_observations(count: int = 100) -> List[FeatureVector]:
    """
    Generate sample observations for initial training.
    
    In production, these would come from collected EDGE research decisions.
    """
    observations = []
    base_date = date(2024, 1, 1)
    
    for i in range(count):
        obs_date = base_date + timedelta(days=i*3)
        
        # Simulate various feature combinations
        conviction_score = 0.6 + (i % 5) * 0.08  # Range 0.6-0.92
        disclosure_purity = 0.75 + (i % 4) * 0.05  # Range 0.75-0.95
        basis_risk = 0.1 + (i % 3) * 0.05  # Range 0.1-0.20
        
        obs = FeatureVector(
            observation_id=f"obs_{i:04d}",
            timestamp=datetime.combine(obs_date, datetime.min.time()).replace(tzinfo=timezone.utc),
            features={
                "conviction_score": conviction_score,
                "disclosure_purity": disclosure_purity,
                "basis_risk": basis_risk,
                "theta_decay_rate": 0.015 + (i % 2) * 0.01,
                "volatility_regime": 0.25 + (i % 4) * 0.08,
                "liquidity_score": 0.80 + (i % 3) * 0.05,
                "manager_concentration": 0.3 + (i % 5) * 0.05,
                "institutional_adoption": 0.5 + (i % 6) * 0.06,
                "catalyst_intensity": 0.4 + (i % 4) * 0.1,
                "policy_uncertainty": 0.2 + (i % 3) * 0.15,
            },
        )
        observations.append(obs)
    
    return observations


def generate_sample_labels(
    observation_ids: List[str],
    start_idx: int = 10,
) -> List[TrainingLabel]:
    """
    Generate sample outcome labels.
    
    In production, these would come from trade outcome assessment.
    """
    labels = []
    
    for i, obs_id in enumerate(observation_ids[start_idx:]):
        obs_idx = start_idx + i
        
        # Simulate returns correlated with conviction and purity
        base_return = 0.02 + 0.08 * (0.6 + (obs_idx % 5) * 0.08) * (0.75 + (obs_idx % 4) * 0.05)
        noise = 0.02 * (obs_idx % 3 - 1)
        actual_return = base_return + noise
        
        # Return label
        labels.append(TrainingLabel(
            observation_id=obs_id,
            label_type="return",
            value=actual_return,
            measured_at=datetime.now(timezone.utc),
            horizon_days=30,
            is_valid=True,
            quality_notes=f"Synthetic label for initial training",
        ))
        
        # Drawdown label
        drawdown = -0.08 + 0.1 * (obs_idx % 4) / 4
        labels.append(TrainingLabel(
            observation_id=obs_id,
            label_type="drawdown",
            value=abs(drawdown),
            measured_at=datetime.now(timezone.utc),
            horizon_days=30,
            is_valid=True,
        ))
        
        # Thesis success label
        thesis_success = 0.5 + 0.3 * (0.6 + (obs_idx % 5) * 0.08)
        labels.append(TrainingLabel(
            observation_id=obs_id,
            label_type="thesis_success",
            value=thesis_success,
            measured_at=datetime.now(timezone.utc),
            horizon_days=30,
            is_valid=True,
        ))
        
        # Hedge effectiveness label
        labels.append(TrainingLabel(
            observation_id=obs_id,
            label_type="hedge_effectiveness",
            value=0.75 + 0.15 * (obs_idx % 5) / 5,
            measured_at=datetime.now(timezone.utc),
            horizon_days=30,
            is_valid=True,
        ))
    
    return labels


def run_first_training_cycle(
    workspace_dir: Path | str = "data/learning",
) -> Dict:
    """
    Run the first complete training cycle.
    
    Returns:
        Summary of training results, model cards, and promotion decisions.
    """
    print("=" * 80)
    print("EDGE-TF LEARNING ENGINE: FIRST TRAINING CYCLE")
    print("=" * 80)
    
    # 1. Initialize orchestrator
    print("\n[1/6] Initializing orchestrator and historical data...")
    workspace_dir = Path(workspace_dir)
    orchestrator = LearningOrchestrator(workspace_dir=workspace_dir)
    
    # Load historical data
    loader = create_historical_loader(orchestrator.analog_engine)
    print(f"     ✓ Loaded historical events and trades into analog engine")
    
    # 2. Ingest observations
    print("\n[2/6] Generating and ingesting sample observations...")
    observations = generate_sample_observations(count=150)
    
    ingested_count = 0
    rejected_observations = []
    
    for obs in observations:
        success, gate = orchestrator.ingest_observation(obs, source="EDGE_RESEARCH")
        if success:
            ingested_count += 1
        else:
            rejected_observations.append({
                "observation_id": obs.observation_id,
                "issues": gate.quality_issues,
            })
    
    print(f"     ✓ Ingested {ingested_count}/{len(observations)} observations")
    if rejected_observations:
        print(f"     ⚠ {len(rejected_observations)} observations rejected by quality gates")
    
    # 3. Generate and register labels
    print("\n[3/6] Generating outcome labels...")
    observation_ids = [f"obs_{i:04d}" for i in range(len(observations))]
    labels = generate_sample_labels(observation_ids, start_idx=10)
    
    orchestrator.dataset_builder.add_labels(labels)
    print(f"     ✓ Generated {len(labels)} training labels ({len(labels)//4} observations with 4 label types)")
    
    # 4. Train models
    print("\n[4/6] Training return prediction model with walk-forward validation...")
    try:
        trained_cards = orchestrator.train_models(
            label_type="return",
            data_start=date(2024, 1, 1),
            data_end=date(2024, 12, 31),
            model_type="return",
        )
        
        model_card = trained_cards["return"]
        print(f"     ✓ Trained model: {model_card.model_id} v{model_card.version}")
        print(f"       Training samples: {model_card.training_sample_size}")
        print(f"       Out-of-sample samples: {model_card.out_of_sample_sample_size}")
        print(f"       Out-of-sample Sharpe: {model_card.metrics.out_of_sample_sharpe:.3f}")
        print(f"       Max drawdown: {model_card.metrics.max_drawdown:.2%}")
        print(f"       Calibration error: {model_card.metrics.calibration_error:.3f}")
        
    except Exception as e:
        print(f"     ✗ Training failed: {str(e)}")
        return {"status": "failed", "error": str(e)}
    
    # 5. Evaluate against gates
    print("\n[5/6] Evaluating model against promotion gates...")
    gate_results, all_passed = orchestrator.evaluate_model(
        model_id=model_card.model_id,
        model_type="return",
    )
    
    for gate_result in gate_results:
        status = "✓" if gate_result["passed"] else "✗"
        print(f"     {status} {gate_result['gate']}: {gate_result['message']}")
    
    if not all_passed:
        print(f"\n     Model did not pass all gates. Candidates must pass all gates before promotion.")
        return {
            "status": "gates_failed",
            "model_card": model_card,
            "gate_results": gate_results,
        }
    
    # 6. Promote to champion
    print("\n[6/6] Promoting model to champion...")
    promotion_result = orchestrator.promote_model(
        model_id=model_card.model_id,
        model_type="return",
        decision="promote",
        reasoning="First model passed all evaluation gates with acceptable OOS Sharpe and calibration",
        approved_by="training_pipeline",
    )
    
    print(f"     ✓ Promotion approved: {promotion_result['decision']}")
    print(f"       Decision ID: {promotion_result['decision_id']}")
    print(f"       Timestamp: {promotion_result['timestamp']}")
    
    # Record to decision records
    print("\n[AUDIT] Recording training and promotion to Decision Records...")
    recorder = DecisionRecorder()
    
    training_record = recorder.record_model_training(
        model_type="return",
        model_id=model_card.model_id,
        model_version=model_card.version,
        dataset_version="synthetic_2024",
        training_start_date="2024-01-01",
        training_end_date="2024-12-31",
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
    )
    
    promo_record = recorder.record_model_promotion(
        model_type="return",
        model_id=model_card.model_id,
        model_version=model_card.version,
        promotion_decision="promote",
        gate_results={gate["gate"]: gate["passed"] for gate in gate_results},
        reasoning=promotion_result["reasoning"],
        approved_by="training_pipeline",
    )
    
    print(f"     ✓ Training record: {training_record.record_id}")
    print(f"     ✓ Promotion record: {promo_record.record_id}")
    
    # 7. Summary
    print("\n" + "=" * 80)
    print("FIRST TRAINING CYCLE COMPLETE")
    print("=" * 80)
    print(f"\nModel: {model_card.model_type} v{model_card.version}")
    print(f"Status: CHAMPION")
    print(f"Out-of-sample Sharpe: {model_card.metrics.out_of_sample_sharpe:.3f}")
    print(f"Max drawdown: {model_card.metrics.max_drawdown:.2%}")
    print(f"Features: {model_card.feature_count}")
    print(f"Training samples: {model_card.training_sample_size}")
    print(f"OOS samples: {model_card.out_of_sample_sample_size}")
    print(f"\nNext steps:")
    print(f"1. Monitor model performance in production")
    print(f"2. Collect real trade outcomes for continuous training")
    print(f"3. Train next model version as data accumulates")
    print(f"4. Run shadow deployment of challenger vs champion")
    print(f"5. Promote new challenger if gates pass and performance improves")
    
    return {
        "status": "success",
        "model_card": {
            "model_id": model_card.model_id,
            "model_type": model_card.model_type,
            "version": model_card.version,
            "status": model_card.status,
            "out_of_sample_sharpe": model_card.metrics.out_of_sample_sharpe,
            "max_drawdown": model_card.metrics.max_drawdown,
            "calibration_error": model_card.metrics.calibration_error,
        },
        "gate_results": gate_results,
        "promotion_decision": promotion_result,
        "training_record_id": training_record.record_id,
        "promotion_record_id": promo_record.record_id,
    }


if __name__ == "__main__":
    result = run_first_training_cycle()
    print(f"\nFinal result: {result['status']}")
