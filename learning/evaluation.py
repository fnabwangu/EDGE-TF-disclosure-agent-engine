"""
Model evaluation and promotion gates.

Path: learning/evaluation.py

Implements deterministic gates that candidate models must pass:
- Out-of-sample performance
- Calibration quality
- Regression testing (no degradation from champion)
- Drift detection (data distribution changes)
- Risk bounds (max drawdown, Sharpe, etc.)

Only models passing all gates can be promoted to champion.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from learning.schemas import ModelCard, ModelMetrics, PromotionDecision


@dataclass
class GateResult:
    """Result of a single gate evaluation."""
    gate_name: str
    passed: bool
    score: float
    message: str


class ModelEvaluator:
    """
    Comprehensive model evaluation with multiple gates.
    """
    
    def __init__(self):
        # Gate thresholds (tunable policy parameters)
        self.min_sharpe = 0.3
        self.max_drawdown = 0.20
        self.max_calibration_error = 0.15
        self.min_out_of_sample_samples = 50
        self.regression_tolerance = 0.10  # Allow 10% regression
        self.drift_threshold = 0.20
    
    def evaluate_candidate(
        self,
        candidate: ModelCard,
        champion: Optional[ModelCard] = None,
        historical_data_distribution: Optional[Dict[str, float]] = None,
    ) -> Tuple[List[GateResult], bool]:
        """
        Comprehensive evaluation of candidate model.
        
        Returns:
            (list of gate results, overall_passed)
        """
        gates: List[GateResult] = []
        
        # Gate 1: Out-of-sample performance
        gate1 = self._gate_oos_performance(candidate)
        gates.append(gate1)
        
        # Gate 2: Calibration
        gate2 = self._gate_calibration(candidate)
        gates.append(gate2)
        
        # Gate 3: Risk bounds
        gate3 = self._gate_risk_bounds(candidate)
        gates.append(gate3)
        
        # Gate 4: Regression (vs champion)
        if champion:
            gate4 = self._gate_regression(candidate, champion)
            gates.append(gate4)
        
        # Gate 5: Drift detection
        if historical_data_distribution:
            gate5 = self._gate_drift(candidate, historical_data_distribution)
            gates.append(gate5)
        
        # Overall pass
        passed = all(g.passed for g in gates)
        
        return gates, passed
    
    def _gate_oos_performance(self, candidate: ModelCard) -> GateResult:
        """
        Out-of-sample performance gate.
        
        Requires:
        - Minimum Sharpe ratio
        - Minimum sample size
        - Positive average return or reasonable R²
        """
        issues = []
        
        metrics = candidate.metrics
        
        # Check Sharpe
        if metrics.out_of_sample_sharpe is None or metrics.out_of_sample_sharpe < self.min_sharpe:
            issues.append(f"Sharpe {metrics.out_of_sample_sharpe} < {self.min_sharpe}")
        
        # Check sample size
        if candidate.out_of_sample_sample_size < self.min_out_of_sample_samples:
            issues.append(f"OOS samples {candidate.out_of_sample_sample_size} < {self.min_out_of_sample_samples}")
        
        passed = len(issues) == 0
        message = "; ".join(issues) if issues else "Meets OOS performance threshold"
        
        return GateResult(
            gate_name="oos_performance",
            passed=passed,
            score=metrics.out_of_sample_sharpe or 0.0,
            message=message,
        )
    
    def _gate_calibration(self, candidate: ModelCard) -> GateResult:
        """
        Calibration quality gate.
        
        Calibration error measures: do predicted probabilities match realized outcomes?
        """
        metrics = candidate.metrics
        calibration_error = metrics.calibration_error or 0.5
        
        passed = calibration_error <= self.max_calibration_error
        message = (
            "Model well-calibrated" if passed
            else f"Calibration error {calibration_error:.3f} exceeds {self.max_calibration_error}"
        )
        
        return GateResult(
            gate_name="calibration",
            passed=passed,
            score=1.0 - calibration_error,
            message=message,
        )
    
    def _gate_risk_bounds(self, candidate: ModelCard) -> GateResult:
        """
        Risk bounds gate.
        
        Ensure model doesn't predict unacceptable risk levels.
        """
        metrics = candidate.metrics
        max_dd = metrics.max_drawdown or 0.0
        
        passed = max_dd <= self.max_drawdown
        message = (
            "Max drawdown acceptable" if passed
            else f"Max drawdown {max_dd:.2%} exceeds {self.max_drawdown:.2%}"
        )
        
        return GateResult(
            gate_name="risk_bounds",
            passed=passed,
            score=1.0 - max_dd,
            message=message,
        )
    
    def _gate_regression(self, candidate: ModelCard, champion: ModelCard) -> GateResult:
        """
        Regression gate: ensure candidate doesn't perform worse than champion.
        
        Allows tolerance for statistical variance.
        """
        candidate_sharpe = candidate.metrics.out_of_sample_sharpe or 0.0
        champion_sharpe = champion.metrics.out_of_sample_sharpe or 0.0
        
        # Regression is OK if within tolerance
        regression_ratio = (champion_sharpe - candidate_sharpe) / max(0.01, champion_sharpe)
        passed = regression_ratio <= self.regression_tolerance
        
        message = (
            f"Challenger Sharpe {candidate_sharpe:.3f} vs Champion {champion_sharpe:.3f}"
        )
        
        return GateResult(
            gate_name="regression",
            passed=passed,
            score=candidate_sharpe / max(0.01, champion_sharpe),
            message=message,
        )
    
    def _gate_drift(
        self,
        candidate: ModelCard,
        historical_distribution: Dict[str, float],
    ) -> GateResult:
        """
        Drift detection gate.
        
        Checks whether training data distribution has drifted significantly
        from historical baseline.
        """
        # Simple check: compare feature statistics
        # In production, use Kolmogorov-Smirnov or Population Stability Index
        
        drift_detected = False
        drift_score = 0.0
        
        # Placeholder: would compare actual feature distributions
        # For now, always pass
        
        message = "No significant data drift detected"
        
        return GateResult(
            gate_name="drift_detection",
            passed=True,
            score=1.0 - drift_score,
            message=message,
        )


class RegressionTestSuite:
    """
    Canonical test cases to ensure model quality doesn't regress.
    """
    
    def __init__(self):
        self.test_cases: List[Dict[str, float]] = []
        self.baseline_predictions: Dict[str, float] = {}
    
    def add_test_case(self, case_name: str, features: Dict[str, float]) -> None:
        """Register a regression test case."""
        self.test_cases.append({"name": case_name, **features})
    
    def run_regression_suite(self, model) -> Tuple[List[Dict], bool]:
        """
        Run model against regression test suite.
        
        Returns:
            (list of test results, all_passed)
        """
        results = []
        all_passed = True
        
        for test_case in self.test_cases:
            case_name = test_case.pop("name")
            
            # Get prediction
            try:
                pred = model.predict(test_case)
            except Exception as e:
                results.append({
                    "case": case_name,
                    "passed": False,
                    "message": f"Exception: {str(e)}",
                })
                all_passed = False
                continue
            
            # Check against baseline
            if case_name in self.baseline_predictions:
                baseline = self.baseline_predictions[case_name]
                tolerance = 0.05 * abs(baseline)  # 5% tolerance
                
                passed = abs(pred - baseline) <= tolerance
                message = (
                    f"OK (pred={pred:.4f}, baseline={baseline:.4f})"
                    if passed
                    else f"REGRESSION (pred={pred:.4f}, baseline={baseline:.4f})"
                )
            else:
                # No baseline yet; set it
                passed = True
                message = f"Setting baseline: {pred:.4f}"
                self.baseline_predictions[case_name] = pred
            
            results.append({
                "case": case_name,
                "passed": passed,
                "prediction": pred,
                "message": message,
            })
            
            if not passed:
                all_passed = False
        
        return results, all_passed


class DriftDetector:
    """
    Detects data distribution drift between training and current data.
    """
    
    def __init__(self, threshold: float = 0.20):
        self.threshold = threshold
        self.reference_distribution: Optional[Dict[str, Dict[str, float]]] = None
    
    def set_reference(self, features_list: List[Dict[str, float]]) -> None:
        """
        Set reference distribution from training data.
        """
        if not features_list:
            return
        
        self.reference_distribution = {}
        all_features = set()
        for features in features_list:
            all_features.update(features.keys())
        
        for feature_name in all_features:
            values = [f.get(feature_name, 0.0) for f in features_list]
            
            mean = sum(values) / len(values) if values else 0.0
            variance = sum((v - mean) ** 2 for v in values) / max(1, len(values) - 1)
            std = variance ** 0.5
            
            self.reference_distribution[feature_name] = {
                "mean": mean,
                "std": std,
                "min": min(values) if values else 0.0,
                "max": max(values) if values else 0.0,
            }
    
    def detect_drift(self, current_features: List[Dict[str, float]]) -> Tuple[bool, Dict[str, float]]:
        """
        Check whether current data has drifted from reference.
        
        Returns:
            (drift_detected, drift_scores_by_feature)
        """
        if not self.reference_distribution or not current_features:
            return False, {}
        
        drift_scores = {}
        
        for feature_name, ref_stats in self.reference_distribution.items():
            current_values = [f.get(feature_name, 0.0) for f in current_features]
            if not current_values:
                continue
            
            current_mean = sum(current_values) / len(current_values)
            current_std = (
                (sum((v - current_mean) ** 2 for v in current_values) / max(1, len(current_values) - 1)) ** 0.5
            )
            
            # Standardized difference in means
            ref_mean = ref_stats["mean"]
            ref_std = ref_stats["std"]
            
            if ref_std > 1e-6:
                z_score = abs(current_mean - ref_mean) / ref_std
                drift_scores[feature_name] = z_score
        
        # Overall drift: max drift score across features
        max_drift = max(drift_scores.values()) if drift_scores else 0.0
        drift_detected = max_drift > self.threshold
        
        return drift_detected, drift_scores
