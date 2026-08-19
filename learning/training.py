"""
Model training with walk-forward validation.

Path: learning/training.py

Handles training loop using time-series aware walk-forward validation.
Prevents lookahead bias and produces out-of-sample performance estimates.

Training loop:
1. For each walk-forward split:
   - Train model on historical data up to split point
   - Evaluate on held-out test period
   - Record performance
2. Average OOS performance across splits
3. Return trained model and metrics
"""

from datetime import date, datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict

from learning.schemas import WalkForwardSplit, ModelMetrics
from learning.dataset_builder import TrainingExample, DatasetBuilder
from learning.models import Model


@dataclass
class TrainingRun:
    """Results from a model training run."""
    model_id: str
    model_type: str
    version: str
    trained_at: datetime
    training_examples_total: int
    out_of_sample_examples_total: int
    walk_forward_splits: int
    average_metrics: ModelMetrics
    split_metrics: List[Dict[str, float]]
    feature_names: List[str]
    feature_count: int


class ModelTrainer:
    """
    Trains models using walk-forward validation on time-series data.
    """
    
    def __init__(self):
        self.training_runs: List[TrainingRun] = []
    
    def train_with_walk_forward(
        self,
        model: Model,
        dataset_builder: DatasetBuilder,
        label_type: str,
        all_examples: List[TrainingExample],
        splits: List[WalkForwardSplit],
    ) -> Tuple[Model, TrainingRun]:
        """
        Train model using walk-forward validation.
        
        For each split:
        - Train on examples up to split.test_start
        - Evaluate on examples in [split.test_start, split.test_end)
        - Record metrics
        
        Returns:
            (trained_model, training_run_summary)
        """
        split_metrics_list: List[Dict[str, float]] = []
        all_oos_predictions: List[Tuple[float, float]] = []  # (actual, pred)
        
        # Train on each split
        for split in splits:
            # Partition examples by split
            train_examples, test_examples = dataset_builder.split_by_walk_forward(
                all_examples,
                split,
            )
            
            if not train_examples or not test_examples:
                continue
            
            # Train
            model.fit(train_examples)
            
            # Evaluate on test set
            split_metrics = self._evaluate_split(model, test_examples)
            split_metrics_list.append(split_metrics)
            
            # Collect predictions for overall OOS metrics
            for example in test_examples:
                pred = model.predict(example.features)
                all_oos_predictions.append((example.label, pred))
        
        # Compute average metrics across splits
        avg_metrics = self._average_metrics(split_metrics_list, all_oos_predictions)
        
        # Final training on all data
        model.fit(all_examples)
        
        run = TrainingRun(
            model_id=model.model_id,
            model_type=model.model_type,
            version=model.version,
            trained_at=datetime.utcnow(),
            training_examples_total=len(all_examples),
            out_of_sample_examples_total=sum(len(examples[1]) for examples in
                [dataset_builder.split_by_walk_forward(all_examples, s) for s in splits]),
            walk_forward_splits=len(splits),
            average_metrics=avg_metrics,
            split_metrics=split_metrics_list,
            feature_names=model.feature_names,
            feature_count=len(model.feature_names),
        )
        
        self.training_runs.append(run)
        
        return model, run
    
    def _evaluate_split(self, model: Model, test_examples: List[TrainingExample]) -> Dict[str, float]:
        """Evaluate model on a single test split."""
        if not test_examples:
            return {}
        
        predictions = []
        actuals = []
        
        for example in test_examples:
            pred = model.predict(example.features)
            predictions.append(pred)
            actuals.append(example.label)
        
        # Compute metrics
        metrics = {}
        
        # MAE
        mae = sum(abs(p - a) for p, a in zip(predictions, actuals)) / len(predictions)
        metrics["mae"] = mae
        
        # RMSE
        mse = sum((p - a) ** 2 for p, a in zip(predictions, actuals)) / len(predictions)
        metrics["rmse"] = mse ** 0.5
        
        # MAPE
        mape = sum(
            abs(p - a) / max(0.01, abs(a))
            for p, a in zip(predictions, actuals)
        ) / len(predictions)
        metrics["mape"] = mape
        
        # R²
        mean_actual = sum(actuals) / len(actuals)
        ss_res = sum((a - p) ** 2 for a, p in zip(actuals, predictions))
        ss_tot = sum((a - mean_actual) ** 2 for a in actuals)
        r_squared = 1.0 - (ss_res / max(1e-6, ss_tot))
        metrics["r_squared"] = r_squared
        
        return metrics
    
    def _average_metrics(
        self,
        split_metrics: List[Dict[str, float]],
        all_predictions: List[Tuple[float, float]],
    ) -> ModelMetrics:
        """Compute average metrics across all splits."""
        if not split_metrics:
            return ModelMetrics()
        
        # Average across splits
        avg_metrics_dict: Dict[str, float] = {}
        for key in split_metrics[0].keys():
            values = [m[key] for m in split_metrics if key in m]
            if values:
                avg_metrics_dict[key] = sum(values) / len(values)
        
        # Compute Sharpe on OOS predictions (simplified)
        if all_predictions:
            returns = [p - a for a, p in all_predictions]
            mean_return = sum(returns) / len(returns) if returns else 0.0
            variance = sum((r - mean_return) ** 2 for r in returns) / max(1, len(returns) - 1)
            std_return = max(1e-6, variance ** 0.5)
            sharpe = mean_return / std_return if std_return > 0 else 0.0
            
            # Simple calibration error: are probabilities actually calibrated?
            max_pred = max((p for a, p in all_predictions), default=0.0)
            min_pred = min((p for a, p in all_predictions), default=0.0)
            calibration_error = abs(sum(p - a for a, p in all_predictions) / len(all_predictions))
        else:
            sharpe = 0.0
            calibration_error = 0.0
        
        return ModelMetrics(
            out_of_sample_sharpe=sharpe,
            calibration_error=calibration_error,
            r_squared=avg_metrics_dict.get("r_squared"),
            mape=avg_metrics_dict.get("mape"),
        )
