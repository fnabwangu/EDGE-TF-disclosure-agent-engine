"""
Learning engine orchestration and Decision Record integration.

Path: learning/orchestrator.py

Coordinates the full learning pipeline:
1. Ingestion: New observations pass data quality gates
2. Feature engineering: Extract features from raw data
3. Dataset building: Combine features and labels
4. Model training: Walk-forward validation and evaluation
5. Promotion: Champion/challenger versioning
6. Analog retrieval: Historical context for decisions
7. Auditability: Record all training and promotion decisions

All activities create auditable Decision Records.
"""

from datetime import datetime, date, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import uuid

from learning.schemas import (
    FeatureVector,
    TrainingLabel,
    DataQualityGate,
    ModelCard,
    AnalogSet,
)
from learning.data_quality import DataQualityGateKeeper, DataQualityConfig, FeatureStore
from learning.dataset_builder import DatasetBuilder
from learning.labels import OutcomeLabelingService
from learning.models import (
    ReturnModel,
    DrawdownModel,
    ThesisSuccessModel,
    HedgeEffectivenessModel,
)
from learning.training import ModelTrainer
from learning.evaluation import ModelEvaluator, RegressionTestSuite, DriftDetector
from learning.registry import ModelRegistry
from learning.analogs import AnalogEngine


class LearningOrchestrator:
    """
    Coordinates all learning engine components.
    
    Manages the complete pipeline from data ingestion to model promotion.
    """
    
    def __init__(self, workspace_dir: Path | str = "data/learning"):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Core components
        self.quality_config = DataQualityConfig(
            trusted_sources={"EDGE_RESEARCH", "SEC_EDGAR", "MARKET_DATA", "INTERNAL"},
            max_lookahead_days=0,
            outlier_std_threshold=3.0,
            missing_value_threshold=0.2,
        )
        self.gatekeeper = DataQualityGateKeeper(self.quality_config)
        self.feature_store = FeatureStore()
        self.dataset_builder = DatasetBuilder(self.feature_store)
        self.labeling_service = OutcomeLabelingService()
        self.model_trainer = ModelTrainer()
        self.model_evaluator = ModelEvaluator()
        self.model_registry = ModelRegistry(self.workspace_dir / "models")
        self.regression_suite = RegressionTestSuite()
        self.drift_detector = DriftDetector(threshold=0.20)
        self.analog_engine = AnalogEngine()
        
        # Training runs log
        self.training_log_dir = self.workspace_dir / "training_logs"
        self.training_log_dir.mkdir(parents=True, exist_ok=True)
    
    def ingest_observation(
        self,
        observation: FeatureVector,
        source: str,
    ) -> Tuple[bool, Optional[DataQualityGate]]:
        """
        Ingest a feature vector and validate it.
        
        Returns:
            (success, quality_gate)
        """
        current_time = datetime.now(timezone.utc)
        
        quality_gate = self.gatekeeper.validate_feature_vector(
            observation,
            current_time,
            source,
        )
        
        if quality_gate.passed:
            added = self.feature_store.add_observation(observation, quality_gate)
            return added, quality_gate
        
        return False, quality_gate
    
    def label_trade_outcome(
        self,
        thesis_id: str,
        entry_date: date,
        exit_date: date,
        entry_price: float,
        exit_price: float,
        max_price: float,
        min_price: float,
        expected_return: float,
        expected_hedge_cost: float,
        realized_hedge_cost: float,
        expected_thesis: str,
        actual_outcome: str,
    ) -> Tuple[any, List[TrainingLabel]]:
        """
        Process trade outcome and generate training labels.
        
        Returns:
            (outcome_assessment, training_labels)
        """
        assessment, labels = self.labeling_service.label_trade_outcome(
            thesis_id=thesis_id,
            entry_date=entry_date,
            exit_date=exit_date,
            entry_price=entry_price,
            exit_price=exit_price,
            max_price_during_trade=max_price,
            min_price_during_trade=min_price,
            expected_return_target=expected_return,
            expected_hedge_cost=expected_hedge_cost,
            realized_hedge_cost=realized_hedge_cost,
            expected_thesis_description=expected_thesis,
            actual_outcome_description=actual_outcome,
        )
        
        # Register labels
        self.dataset_builder.add_labels(labels)
        
        return assessment, labels
    
    def train_models(
        self,
        label_type: str,
        data_start: date,
        data_end: date,
        model_type: Optional[str] = None,
    ) -> Dict[str, ModelCard]:
        """
        Train all model types or a specific model.
        
        Creates walk-forward trained models with comprehensive evaluation.
        
        Returns:
            Dictionary of trained model cards by model_type.
        """
        # Build training dataset
        examples = self.dataset_builder.build_training_dataset(
            label_type=label_type,
            start_date=data_start,
            end_date=data_end,
        )
        
        if not examples:
            raise ValueError(f"No training examples for label_type={label_type}")
        
        # Create walk-forward splits
        splits = self.dataset_builder.create_walk_forward_splits(
            all_data_start=data_start,
            all_data_end=data_end,
            training_window_years=5,
            test_window_days=60,
            step_days=30,
        )
        
        # Train model
        if model_type == "return" or not model_type:
            model = ReturnModel()
            trained_model, run = self.model_trainer.train_with_walk_forward(
                model, self.dataset_builder, label_type, examples, splits
            )
            model_card = self._create_model_card(
                model, run, data_start, data_end
            )
            self.model_registry.register_model(model_card)
            self._log_training_run(run, model_card)
            
            return {model_type: model_card}
        
        return {}
    
    def evaluate_model(
        self,
        model_id: str,
        model_type: str,
    ) -> Tuple[List[Dict], bool]:
        """
        Evaluate a trained model against all gates.
        
        Returns:
            (gate_results, all_passed)
        """
        candidate = self._get_model_card(model_id, model_type)
        champion = self.model_registry.get_champion(model_type)
        
        gates, passed = self.model_evaluator.evaluate_candidate(
            candidate,
            champion=champion,
        )
        
        return [
            {
                "gate": g.gate_name,
                "passed": g.passed,
                "score": g.score,
                "message": g.message,
            }
            for g in gates
        ], passed
    
    def promote_model(
        self,
        model_id: str,
        model_type: str,
        decision: str,
        reasoning: str,
        approved_by: Optional[str] = None,
    ) -> Dict:
        """
        Promote or demote a model with audit trail.
        
        Returns:
            Promotion decision record.
        """
        promo_decision = self.model_registry.promote_model(
            model_id=model_id,
            model_type=model_type,
            decision=decision,
            reasoning=reasoning,
            approved_by=approved_by,
        )
        
        return {
            "decision_id": promo_decision.decision_id,
            "model_id": model_id,
            "model_type": model_type,
            "decision": promo_decision.promotion_decision,
            "timestamp": promo_decision.timestamp.isoformat(),
            "reasoning": reasoning,
            "approved_by": approved_by,
        }
    
    def find_analogs(
        self,
        event_type: str,
        region: Optional[str] = None,
        commodity: Optional[str] = None,
        implementation_type: str = "standard",
        min_similarity: float = 0.50,
    ) -> Dict:
        """
        Find historical analogs for a setup.
        
        Returns:
            Structured analog set with outcomes and patterns.
        """
        fingerprint = self.analog_engine.encoder.encode_setup(
            event_type=event_type,
            region=region,
            commodity=commodity,
        )
        
        analog_set = self.analog_engine.find_analogs(
            fingerprint,
            implementation_type=implementation_type,
            min_event_similarity=min_similarity,
        )
        
        return {
            "confidence": analog_set.confidence_level,
            "similar_events": len(analog_set.event_analogs),
            "similar_trades": len(analog_set.trade_analogs),
            "patterns": analog_set.observed_patterns,
            "outcome_stats": analog_set.outcome_statistics,
        }
    
    def _create_model_card(
        self,
        model,
        run,
        data_start: date,
        data_end: date,
    ) -> ModelCard:
        """Create model card from training run."""
        return ModelCard(
            model_id=model.model_id,
            model_type=model.model_type,
            version=model.version,
            trained_at=datetime.utcnow(),
            training_start_date=data_start,
            training_end_date=data_end,
            feature_names=run.feature_names,
            feature_count=run.feature_count,
            training_sample_size=run.training_examples_total,
            out_of_sample_sample_size=run.out_of_sample_examples_total,
            metrics=run.average_metrics,
            model_code_version="1.0",
            model_parameters={"walk_forward_splits": run.walk_forward_splits},
            status="draft",
            predecessor_version=None,
            promotion_history=[],
            regression_test_passed=False,
            drift_test_passed=False,
            risk_gate_passed=False,
        )
    
    def _get_model_card(self, model_id: str, model_type: str) -> ModelCard:
        """Retrieve model card from registry."""
        models = self.model_registry.list_models(model_type)
        model = next((m for m in models if m.model_id == model_id), None)
        if not model:
            raise ValueError(f"Model {model_id} not found")
        return model
    
    def _log_training_run(self, run, card: ModelCard) -> None:
        """Log training run to disk."""
        log_path = self.training_log_dir / f"{card.model_id}_{card.version}_run.json"
        
        log_data = {
            "model_id": card.model_id,
            "model_type": card.model_type,
            "version": card.version,
            "trained_at": card.trained_at.isoformat(),
            "training_samples": card.training_sample_size,
            "out_of_sample_samples": card.out_of_sample_sample_size,
            "walk_forward_splits": run.walk_forward_splits,
            "metrics": {
                "out_of_sample_sharpe": card.metrics.out_of_sample_sharpe,
                "max_drawdown": card.metrics.max_drawdown,
                "calibration_error": card.metrics.calibration_error,
                "r_squared": card.metrics.r_squared,
                "mape": card.metrics.mape,
            },
            "feature_count": card.feature_count,
        }
        
        log_path.write_text(json.dumps(log_data, indent=2, default=str))


def create_learning_engine_decision_record(
    orchestrator: LearningOrchestrator,
    dataset_version: str,
    training_date: date,
    model_type: str,
    model_version: str,
    metrics: Dict,
    gate_results: List[Dict],
    promotion_decision: Optional[str] = None,
) -> Dict:
    """
    Create a Decision Record for a learning engine training/promotion event.
    
    This hooks into the audit system to make all learning activities auditable.
    
    Returns:
        Decision Record data structure for audit log.
    """
    return {
        "record_id": str(uuid.uuid4()),
        "kind": "MODEL_TRAINING_AND_PROMOTION",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_version": dataset_version,
        "training_date": training_date.isoformat(),
        "model_type": model_type,
        "model_version": model_version,
        "metrics": metrics,
        "gate_results": gate_results,
        "promotion_decision": promotion_decision,
        "policy_enforced": True,
        "notes": "All models must pass deterministic gates. ML cannot override risk limits.",
    }
