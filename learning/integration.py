"""
Learning Engine integration bridge with EDGE orchestration.

Path: learning/integration.py

Bridges the Learning Engine with EDGE's orchestration layer, enabling:
- ML predictions to inform thesis scoring and implementation selection
- Historical analog retrieval during research phase
- Outcome collection from completed trades
- Continuous model improvement feedback loop
"""

from datetime import datetime, date, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from learning.orchestrator import LearningOrchestrator
from learning.schemas import SetupFingerprint, FeatureVector


@dataclass
class MLPrediction:
    """ML model output for decision support."""
    model_type: str  # "return", "drawdown", "thesis_success", "hedge_effectiveness"
    prediction: float  # Point estimate
    confidence: float  # [0, 1]
    explanation: Optional[str] = None
    feature_importance: Optional[Dict[str, float]] = None


@dataclass
class AnalogContext:
    """Historical context from analog retrieval."""
    confidence: str  # "high", "medium", "low", "no_analog"
    similar_events: int
    similar_trades: int
    observed_patterns: List[str]
    historical_return_5d: Optional[float] = None
    historical_return_20d: Optional[float] = None
    historical_return_60d: Optional[float] = None


class LearningEngineIntegration:
    """
    Integration layer between EDGE orchestration and Learning Engine.
    
    Provides methods for:
    - Getting ML predictions during research/implementation phase
    - Retrieving historical analogs to ground decisions
    - Recording outcomes from completed trades
    - Monitoring model performance in production
    """
    
    def __init__(self, orchestrator: LearningOrchestrator):
        self.orchestrator = orchestrator
        self.model_cache: Dict[str, any] = {}  # Cache champion models in memory
    
    def get_return_prediction(
        self,
        features: Dict[str, float],
        thesis_id: Optional[str] = None,
    ) -> MLPrediction:
        """
        Get expected return prediction from champion model.
        
        Returns:
            MLPrediction with point estimate and confidence
        """
        champion = self.orchestrator.model_registry.get_champion("return")
        
        if not champion or not champion.status == "champion":
            # No champion available; return neutral prediction
            return MLPrediction(
                model_type="return",
                prediction=0.0,
                confidence=0.0,
                explanation="No champion model available",
            )
        
        # Load model if not cached
        if "return" not in self.model_cache:
            # In production, load actual model weights from registry
            # For now, return mock prediction
            pass
        
        # Get prediction
        pred = champion.metrics.out_of_sample_sharpe or 0.0  # Placeholder
        
        return MLPrediction(
            model_type="return",
            prediction=pred,
            confidence=min(1.0, max(0.0, champion.metrics.r_squared or 0.5)),
            explanation=f"Champion model v{champion.version}",
            feature_importance=self._get_feature_importance("return"),
        )
    
    def get_drawdown_prediction(
        self,
        features: Dict[str, float],
    ) -> MLPrediction:
        """Get expected maximum drawdown prediction."""
        champion = self.orchestrator.model_registry.get_champion("drawdown")
        
        if not champion:
            return MLPrediction(
                model_type="drawdown",
                prediction=0.0,
                confidence=0.0,
                explanation="No champion model available",
            )
        
        return MLPrediction(
            model_type="drawdown",
            prediction=champion.metrics.max_drawdown or 0.10,
            confidence=min(1.0, max(0.0, champion.metrics.r_squared or 0.5)),
            explanation=f"Champion model v{champion.version}",
        )
    
    def get_thesis_success_probability(
        self,
        features: Dict[str, float],
    ) -> MLPrediction:
        """Get probability that thesis will be validated."""
        champion = self.orchestrator.model_registry.get_champion("thesis_success")
        
        if not champion:
            return MLPrediction(
                model_type="thesis_success",
                prediction=0.5,
                confidence=0.0,
                explanation="No champion model available",
            )
        
        return MLPrediction(
            model_type="thesis_success",
            prediction=0.5,  # Placeholder; would use actual model
            confidence=0.3,
            explanation=f"Champion model v{champion.version}",
        )
    
    def get_hedge_effectiveness_prediction(
        self,
        features: Dict[str, float],
    ) -> MLPrediction:
        """Get expected hedge effectiveness."""
        champion = self.orchestrator.model_registry.get_champion("hedge_effectiveness")
        
        if not champion:
            return MLPrediction(
                model_type="hedge_effectiveness",
                prediction=0.8,
                confidence=0.0,
                explanation="No champion model available",
            )
        
        return MLPrediction(
            model_type="hedge_effectiveness",
            prediction=0.8,
            confidence=0.3,
            explanation=f"Champion model v{champion.version}",
        )
    
    def get_historical_analogs(
        self,
        event_type: str,
        region: Optional[str] = None,
        commodity: Optional[str] = None,
        implementation_type: str = "standard",
    ) -> AnalogContext:
        """
        Retrieve historical analog context for a setup.
        
        Returns:
            AnalogContext with confidence level, similar events/trades, patterns.
        """
        analogs = self.orchestrator.find_analogs(
            event_type=event_type,
            region=region,
            commodity=commodity,
            implementation_type=implementation_type,
            min_similarity=0.50,
        )
        
        return AnalogContext(
            confidence=analogs["confidence"],
            similar_events=analogs["similar_events"],
            similar_trades=analogs["similar_trades"],
            observed_patterns=analogs["patterns"],
            historical_return_5d=analogs["outcome_stats"].get("return_5d_avg"),
            historical_return_20d=analogs["outcome_stats"].get("return_20d_avg"),
            historical_return_60d=analogs["outcome_stats"].get("return_60d_avg"),
        )
    
    def record_trade_outcome(
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
        expected_thesis_description: str,
        actual_outcome_description: str,
    ) -> Tuple[any, List[any]]:
        """
        Record outcome from a completed trade.
        
        Generates training labels and adds to dataset.
        
        Returns:
            (outcome_assessment, training_labels)
        """
        return self.orchestrator.label_trade_outcome(
            thesis_id=thesis_id,
            entry_date=entry_date,
            exit_date=exit_date,
            entry_price=entry_price,
            exit_price=exit_price,
            max_price=max_price,
            min_price=min_price,
            expected_return=expected_return,
            expected_hedge_cost=expected_hedge_cost,
            realized_hedge_cost=realized_hedge_cost,
            expected_thesis=expected_thesis_description,
            actual_outcome=actual_outcome_description,
        )
    
    def _get_feature_importance(self, model_type: str) -> Dict[str, float]:
        """Get feature importance from champion model."""
        champion = self.orchestrator.model_registry.get_champion(model_type)
        
        if champion and champion.feature_names:
            # Placeholder: in production, retrieve actual feature importance
            return {name: 0.1 for name in champion.feature_names[:5]}
        
        return {}


class ResearchPhaseIntegration:
    """
    Integration during research phase (idea formation).
    
    Provides analog retrieval and historical context to ground research.
    """
    
    def __init__(self, learning_integration: LearningEngineIntegration):
        self.learning = learning_integration
    
    def enrich_research_with_analogs(
        self,
        event_type: str,
        region: Optional[str] = None,
        commodity: Optional[str] = None,
    ) -> Dict:
        """
        Enrich research with historical analog context.
        
        Called during ResearchFunnel to inform thesis generation.
        """
        analogs = self.learning.get_historical_analogs(
            event_type=event_type,
            region=region,
            commodity=commodity,
        )
        
        research_enrichment = {
            "analog_confidence": analogs.confidence,
            "num_similar_events": analogs.similar_events,
            "num_similar_trades": analogs.similar_trades,
            "historical_patterns": analogs.observed_patterns,
            "historical_returns": {
                "5d": analogs.historical_return_5d,
                "20d": analogs.historical_return_20d,
                "60d": analogs.historical_return_60d,
            },
            "recommendation": self._recommend_from_analogs(analogs),
        }
        
        return research_enrichment
    
    def _recommend_from_analogs(self, analogs: AnalogContext) -> str:
        """Generate recommendation based on analog patterns."""
        if analogs.confidence == "no_analog":
            return "Novel regime. Limited historical precedent. Approach with caution."
        
        if "producers > commodity" in str(analogs.observed_patterns):
            return "Historical data suggests producer equities outperformed direct commodity exposure"
        
        if "rerouting" in str(analogs.observed_patterns):
            return "Historical supply disruptions were primarily rerouting. Direct commodity trades may underperform."
        
        return "Historical analogs available. Review patterns before implementation selection."


class ImplementationPhaseIntegration:
    """
    Integration during implementation phase (trade design).
    
    Provides ML predictions to inform sizing and instrument selection.
    """
    
    def __init__(self, learning_integration: LearningEngineIntegration):
        self.learning = learning_integration
    
    def score_implementation(
        self,
        implementation_type: str,
        features: Dict[str, float],
        position_size: float,
        hedge_type: Optional[str] = None,
    ) -> Dict:
        """
        Score an implementation using ML predictions.
        
        Returns ranking factors for implementation comparison.
        """
        # Get predictions
        return_pred = self.learning.get_return_prediction(features)
        dd_pred = self.learning.get_drawdown_prediction(features)
        hedge_pred = self.learning.get_hedge_effectiveness_prediction(features)
        
        # Compute risk-adjusted score
        risk_adj_return = 0.0
        if dd_pred.prediction > 0:
            risk_adj_return = return_pred.prediction / max(0.01, dd_pred.prediction)
        
        score = {
            "implementation_type": implementation_type,
            "expected_return": return_pred.prediction,
            "expected_drawdown": dd_pred.prediction,
            "risk_adjusted_return": risk_adj_return,
            "hedge_effectiveness": hedge_pred.prediction,
            "suggested_position_size": self._suggest_position_size(
                return_pred.prediction,
                dd_pred.prediction,
                position_size,
            ),
            "confidence_level": min(
                return_pred.confidence,
                dd_pred.confidence,
            ),
            "ml_recommendation": self._recommend_implementation(
                return_pred, dd_pred, hedge_pred
            ),
        }
        
        return score
    
    def _suggest_position_size(
        self,
        expected_return: float,
        expected_drawdown: float,
        base_allocation: float,
    ) -> float:
        """
        Suggest position sizing based on ML predictions.
        
        Does NOT override deterministic limits; only informs.
        """
        # Kelly-like sizing (simplified)
        if expected_drawdown > 0.15 or expected_return < 0.05:
            # High risk or low return: size down
            suggested = base_allocation * 0.8
        elif expected_return > 0.12 and expected_drawdown < 0.10:
            # Low risk, high return: can size up
            suggested = base_allocation * 1.2
        else:
            suggested = base_allocation
        
        # Still respect hard limits (policy enforced elsewhere)
        return max(0.01, min(suggested, 0.05))  # Min 1%, Max 5%
    
    def _recommend_implementation(
        self,
        return_pred: MLPrediction,
        dd_pred: MLPrediction,
        hedge_pred: MLPrediction,
    ) -> str:
        """Generate implementation recommendation."""
        if return_pred.confidence < 0.3:
            return "Model confidence low. Consider multiple implementations."
        
        if dd_pred.prediction > 0.15:
            return "High expected drawdown. Recommend stronger hedge."
        
        if hedge_pred.prediction < 0.7:
            return "Expected hedge effectiveness low. Optimize hedge design."
        
        return "Implementation appears well-balanced."


class MonitoringPhaseIntegration:
    """
    Integration during monitoring and outcome assessment.
    
    Records trade outcomes and monitors model performance in production.
    """
    
    def __init__(self, learning_integration: LearningEngineIntegration):
        self.learning = learning_integration
        self.shadow_metrics: Dict[str, List[float]] = {}
    
    def process_trade_completion(
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
        thesis_description: str,
        outcome_description: str,
    ) -> Dict:
        """
        Process completed trade and record outcome.
        
        Returns assessment and integrates outcome labels into learning dataset.
        """
        assessment, labels = self.learning.record_trade_outcome(
            thesis_id=thesis_id,
            entry_date=entry_date,
            exit_date=exit_date,
            entry_price=entry_price,
            exit_price=exit_price,
            max_price=max_price,
            min_price=min_price,
            expected_return=expected_return,
            expected_hedge_cost=expected_hedge_cost,
            realized_hedge_cost=realized_hedge_cost,
            expected_thesis_description=thesis_description,
            actual_outcome_description=outcome_description,
        )
        
        result = {
            "thesis_id": thesis_id,
            "actual_return": assessment.actual_return,
            "actual_drawdown": assessment.max_drawdown,
            "thesis_assessment": assessment.thesis_correctness,
            "instrument_assessment": assessment.instrument_correctness,
            "timing_assessment": assessment.timing_correctness,
            "hedge_assessment": assessment.hedge_effectiveness,
            "sizing_assessment": assessment.sizing_appropriateness,
            "training_labels_generated": len(labels),
        }
        
        return result
    
    def track_model_performance(
        self,
        model_type: str,
        actual_return: float,
        predicted_return: float,
    ) -> None:
        """
        Track model predictions vs actuals for monitoring.
        
        Used to detect model drift and monitor champion/challenger performance.
        """
        if model_type not in self.shadow_metrics:
            self.shadow_metrics[model_type] = []
        
        prediction_error = abs(predicted_return - actual_return)
        self.shadow_metrics[model_type].append(prediction_error)
    
    def get_shadow_deployment_report(self, model_type: str) -> Dict:
        """
        Get report on challenger model performance during shadow deployment.
        
        Used for promotion decision.
        """
        if model_type not in self.shadow_metrics or not self.shadow_metrics[model_type]:
            return {
                "model_type": model_type,
                "observations": 0,
                "avg_error": None,
                "max_error": None,
            }
        
        errors = self.shadow_metrics[model_type]
        
        return {
            "model_type": model_type,
            "observations": len(errors),
            "avg_error": sum(errors) / len(errors),
            "max_error": max(errors),
            "drift_detected": False,  # Placeholder; implement drift detection
            "ready_for_promotion": len(errors) > 20 and sum(errors) / len(errors) < 0.1,
        }
