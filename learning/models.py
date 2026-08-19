"""
Core learning models.

Path: learning/models.py

Supervised models for:
- Predicting expected returns
- Predicting drawdown risk
- Estimating probability of thesis success
- Measuring hedge effectiveness

Models are probabilistic and interpretable. They inform scoring and sizing
but do not override deterministic risk limits or execution gates.
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import asdict

from learning.dataset_builder import TrainingExample
from learning.schemas import ModelCard, ModelMetrics


class Model(ABC):
    """Abstract base for all supervised models."""
    
    def __init__(self, model_type: str, model_id: str):
        self.model_type = model_type
        self.model_id = model_id
        self.version = "1.0"
        self.trained = False
        self.feature_names: List[str] = []
        self.params: Dict[str, Any] = {}
    
    @abstractmethod
    def fit(self, examples: List[TrainingExample]) -> None:
        """Train model on examples."""
        pass
    
    @abstractmethod
    def predict(self, features: Dict[str, float]) -> float:
        """Predict single observation."""
        pass
    
    @abstractmethod
    def predict_proba(self, features: Dict[str, float]) -> Dict[str, float]:
        """Return probability distribution if applicable."""
        pass
    
    @abstractmethod
    def get_feature_importance(self) -> Dict[str, float]:
        """Return feature importance scores."""
        pass


class ReturnModel(Model):
    """
    Predicts expected return from current setup features.
    
    Outputs: point estimate of expected return over horizon
    """
    
    def __init__(self, model_id: str = "return_model_v1"):
        super().__init__("return", model_id)
        self.coefficients: Dict[str, float] = {}
        self.intercept: float = 0.0
        self.mean_target: float = 0.0
        self.std_target: float = 1.0
    
    def fit(self, examples: List[TrainingExample]) -> None:
        """
        Simple linear regression: y = intercept + sum(coef_i * x_i)
        
        In production, use sklearn's LinearRegression, regularized regression,
        ensemble methods, or gradient boosting.
        """
        if not examples:
            return
        
        # Collect features and labels
        X: List[Dict[str, float]] = [e.features for e in examples]
        y: List[float] = [e.label for e in examples]
        
        # Simple online mean calculation
        self.mean_target = sum(y) / len(y) if y else 0.0
        variance = sum((yi - self.mean_target) ** 2 for yi in y) / max(1, len(y) - 1)
        self.std_target = max(1e-6, variance ** 0.5)
        
        # Get all feature names
        all_features = set()
        for x in X:
            all_features.update(x.keys())
        self.feature_names = sorted(list(all_features))
        
        # Naive coefficient estimation: correlation with target
        for feature_name in self.feature_names:
            values = [x.get(feature_name, 0.0) for x in X]
            
            mean_x = sum(values) / len(values) if values else 0.0
            
            cov = sum(
                (x.get(feature_name, 0.0) - mean_x) * (yi - self.mean_target)
                for x, yi in zip(X, y)
            ) / max(1, len(X) - 1)
            
            var_x = sum(
                (x.get(feature_name, 0.0) - mean_x) ** 2 for x in X
            ) / max(1, len(X) - 1)
            
            self.coefficients[feature_name] = cov / max(1e-6, var_x)
        
        self.intercept = self.mean_target
        self.trained = True
    
    def predict(self, features: Dict[str, float]) -> float:
        """Linear prediction."""
        if not self.trained:
            return self.mean_target
        
        pred = self.intercept
        for feature_name, coef in self.coefficients.items():
            pred += coef * features.get(feature_name, 0.0)
        
        return pred
    
    def predict_proba(self, features: Dict[str, float]) -> Dict[str, float]:
        """For regression, return dict with point estimate."""
        pred = self.predict(features)
        return {
            "prediction": pred,
            "confidence": 0.5,  # Placeholder
        }
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Return absolute coefficient values as importance."""
        return {name: abs(coef) for name, coef in self.coefficients.items()}


class DrawdownModel(Model):
    """
    Predicts maximum expected drawdown during position holding.
    
    Outputs: expected drawdown magnitude [0, 1]
    """
    
    def __init__(self, model_id: str = "drawdown_model_v1"):
        super().__init__("drawdown", model_id)
        self.coefficients: Dict[str, float] = {}
        self.intercept: float = 0.0
    
    def fit(self, examples: List[TrainingExample]) -> None:
        """Fit model on drawdown labels."""
        if not examples:
            return
        
        X = [e.features for e in examples]
        y = [e.label for e in examples]
        
        # Same as ReturnModel
        mean_y = sum(y) / len(y) if y else 0.0
        
        all_features = set()
        for x in X:
            all_features.update(x.keys())
        self.feature_names = sorted(list(all_features))
        
        for feature_name in self.feature_names:
            values = [x.get(feature_name, 0.0) for x in X]
            mean_x = sum(values) / len(values) if values else 0.0
            
            cov = sum(
                (x.get(feature_name, 0.0) - mean_x) * (yi - mean_y)
                for x, yi in zip(X, y)
            ) / max(1, len(X) - 1)
            
            var_x = sum(
                (x.get(feature_name, 0.0) - mean_x) ** 2 for x in X
            ) / max(1, len(X) - 1)
            
            self.coefficients[feature_name] = cov / max(1e-6, var_x)
        
        self.intercept = mean_y
        self.trained = True
    
    def predict(self, features: Dict[str, float]) -> float:
        """Predict drawdown, clipped to [0, 1]."""
        if not self.trained:
            return 0.0
        
        pred = self.intercept
        for feature_name, coef in self.coefficients.items():
            pred += coef * features.get(feature_name, 0.0)
        
        return max(0.0, min(1.0, pred))
    
    def predict_proba(self, features: Dict[str, float]) -> Dict[str, float]:
        """Return point estimate."""
        return {"drawdown": self.predict(features)}
    
    def get_feature_importance(self) -> Dict[str, float]:
        return {name: abs(coef) for name, coef in self.coefficients.items()}


class ThesisSuccessModel(Model):
    """
    Predicts probability that thesis will be validated/successful.
    
    Outputs: probability [0, 1]
    """
    
    def __init__(self, model_id: str = "thesis_success_model_v1"):
        super().__init__("thesis_success", model_id)
        self.weights: Dict[str, float] = {}
        self.bias: float = 0.5
    
    def fit(self, examples: List[TrainingExample]) -> None:
        """Fit logistic model."""
        if not examples:
            return
        
        X = [e.features for e in examples]
        y = [e.label for e in examples]  # Should be [0, 1] or close
        
        all_features = set()
        for x in X:
            all_features.update(x.keys())
        self.feature_names = sorted(list(all_features))
        
        # Simple logistic approximation
        pos_rate = sum(1 for yi in y if yi > 0.5) / max(1, len(y))
        self.bias = self._logit(pos_rate)
        
        # Feature weights
        for feature_name in self.feature_names:
            pos_values = [
                x.get(feature_name, 0.0)
                for x, yi in zip(X, y)
                if yi > 0.5
            ]
            neg_values = [
                x.get(feature_name, 0.0)
                for x, yi in zip(X, y)
                if yi <= 0.5
            ]
            
            mean_pos = sum(pos_values) / len(pos_values) if pos_values else 0.0
            mean_neg = sum(neg_values) / len(neg_values) if neg_values else 0.0
            
            self.weights[feature_name] = mean_pos - mean_neg
        
        self.trained = True
    
    def predict(self, features: Dict[str, float]) -> float:
        """Predict probability."""
        if not self.trained:
            return 0.5
        
        z = self.bias
        for feature_name, weight in self.weights.items():
            z += weight * features.get(feature_name, 0.0)
        
        return self._sigmoid(z)
    
    def predict_proba(self, features: Dict[str, float]) -> Dict[str, float]:
        """Return probability of success."""
        prob = self.predict(features)
        return {
            "success": prob,
            "failure": 1.0 - prob,
        }
    
    def get_feature_importance(self) -> Dict[str, float]:
        return {name: abs(w) for name, w in self.weights.items()}
    
    @staticmethod
    def _sigmoid(z: float) -> float:
        """Sigmoid activation."""
        import math
        try:
            return 1.0 / (1.0 + math.exp(-min(max(z, -500), 500)))
        except (ValueError, OverflowError):
            return 0.5
    
    @staticmethod
    def _logit(p: float) -> float:
        """Inverse sigmoid."""
        import math
        p = max(0.001, min(0.999, p))
        try:
            return math.log(p / (1.0 - p))
        except (ValueError, ZeroDivisionError):
            return 0.0


class HedgeEffectivenessModel(Model):
    """
    Predicts hedge effectiveness from setup and hedge design.
    
    Outputs: effectiveness score [0, 1]
    """
    
    def __init__(self, model_id: str = "hedge_effectiveness_model_v1"):
        super().__init__("hedge_effectiveness", model_id)
        self.coefficients: Dict[str, float] = {}
        self.intercept: float = 0.5
    
    def fit(self, examples: List[TrainingExample]) -> None:
        """Fit model on hedge effectiveness labels."""
        if not examples:
            return
        
        X = [e.features for e in examples]
        y = [e.label for e in examples]
        
        mean_y = sum(y) / len(y) if y else 0.5
        
        all_features = set()
        for x in X:
            all_features.update(x.keys())
        self.feature_names = sorted(list(all_features))
        
        for feature_name in self.feature_names:
            values = [x.get(feature_name, 0.0) for x in X]
            mean_x = sum(values) / len(values) if values else 0.0
            
            cov = sum(
                (x.get(feature_name, 0.0) - mean_x) * (yi - mean_y)
                for x, yi in zip(X, y)
            ) / max(1, len(X) - 1)
            
            var_x = sum(
                (x.get(feature_name, 0.0) - mean_x) ** 2 for x in X
            ) / max(1, len(X) - 1)
            
            self.coefficients[feature_name] = cov / max(1e-6, var_x)
        
        self.intercept = mean_y
        self.trained = True
    
    def predict(self, features: Dict[str, float]) -> float:
        """Predict effectiveness, clipped to [0, 1]."""
        if not self.trained:
            return 0.5
        
        pred = self.intercept
        for feature_name, coef in self.coefficients.items():
            pred += coef * features.get(feature_name, 0.0)
        
        return max(0.0, min(1.0, pred))
    
    def predict_proba(self, features: Dict[str, float]) -> Dict[str, float]:
        return {"effectiveness": self.predict(features)}
    
    def get_feature_importance(self) -> Dict[str, float]:
        return {name: abs(coef) for name, coef in self.coefficients.items()}
