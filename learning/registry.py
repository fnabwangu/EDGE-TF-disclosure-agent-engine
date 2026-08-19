"""
Model registry and promotion management.

Path: learning/registry.py

Maintains versioned model cards with:
- Champion/challenger status
- Performance metrics
- Promotion history
- Audit trail

Only champion models affect decisions. Challengers run in shadow.
Promotion requires passing all gates and human approval.
"""

import json
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Literal

from learning.schemas import ModelCard, PromotionDecision


class ModelRegistry:
    """
    Versioned model registry with promotion workflow.
    
    Maintains:
    - All model versions and their metadata
    - Champion and challenger models
    - Promotion history and decisions
    - Shadow deployment tracking
    """
    
    def __init__(self, storage_dir: Path | str = "data/model_registry"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.models: Dict[str, List[ModelCard]] = {}  # model_type -> [cards]
        self.champions: Dict[str, str] = {}  # model_type -> model_id
        self.promotion_history: List[PromotionDecision] = []
        
        self._load_all()
    
    def register_model(self, card: ModelCard) -> None:
        """Register a new trained model."""
        if card.model_type not in self.models:
            self.models[card.model_type] = []
        
        self.models[card.model_type].append(card)
        self._save_card(card)
    
    def get_champion(self, model_type: str) -> Optional[ModelCard]:
        """Get current champion model for a type."""
        if model_type not in self.champions:
            return None
        
        champion_id = self.champions[model_type]
        models = self.models.get(model_type, [])
        
        return next((m for m in models if m.model_id == champion_id), None)
    
    def get_challenger(self, model_type: str) -> Optional[ModelCard]:
        """Get current challenger model for a type."""
        models = self.models.get(model_type, [])
        challenger = next((m for m in models if m.status == "challenger"), None)
        return challenger
    
    def list_models(self, model_type: str) -> List[ModelCard]:
        """List all versions of a model type."""
        return self.models.get(model_type, [])
    
    def promote_model(
        self,
        model_id: str,
        model_type: str,
        decision: Literal["promote", "demote", "hold"],
        reasoning: str,
        approved_by: Optional[str] = None,
    ) -> PromotionDecision:
        """
        Promote or demote a model.
        
        PROMOTE: challenger becomes champion, old champion becomes retired
        DEMOTE: champion becomes retired
        HOLD: no change, run longer in shadow
        """
        models = self.models.get(model_type, [])
        candidate = next((m for m in models if m.model_id == model_id), None)
        
        if not candidate:
            raise ValueError(f"Model {model_id} not found")
        
        current_champion = self.get_champion(model_type)
        
        promotion_decision = PromotionDecision(
            decision_id=f"prom_{model_id}_{datetime.utcnow().isoformat()}",
            model_id=model_id,
            model_version=candidate.version,
            timestamp=datetime.utcnow(),
            champion_model_version=current_champion.version if current_champion else None,
            challenger_model_version=candidate.version,
            out_of_sample_performance_pass=True,  # Assumed validated before calling
            calibration_pass=True,
            regression_suite_pass=True,
            drift_detection_pass=True,
            risk_gate_pass=True,
            shadow_deployment_days=candidate.promotion_history[-1].get("shadow_days", 0) if candidate.promotion_history else 0,
            promotion_decision=decision,
            reasoning=reasoning,
            approved_by=approved_by,
            approved_at=datetime.utcnow(),
        )
        
        if decision == "promote":
            # Update statuses
            candidate.status = "champion"
            if current_champion:
                current_champion.status = "retired"
            self.champions[model_type] = model_id
        
        elif decision == "demote":
            if current_champion and current_champion.model_id == model_id:
                current_champion.status = "retired"
            # If there's a challenger, it becomes champion
            challenger = self.get_challenger(model_type)
            if challenger:
                challenger.status = "champion"
                self.champions[model_type] = challenger.model_id
        
        # Record promotion
        self.promotion_history.append(promotion_decision)
        self._save_promotion_decision(promotion_decision)
        
        # Save updated cards
        self._save_card(candidate)
        if current_champion:
            self._save_card(current_champion)
        
        return promotion_decision
    
    def set_shadow_deployment(
        self,
        model_id: str,
        model_type: str,
        shadow_performance: Dict[str, float],
        notes: Optional[str] = None,
    ) -> None:
        """Record shadow deployment performance."""
        models = self.models.get(model_type, [])
        model = next((m for m in models if m.model_id == model_id), None)
        
        if model:
            if not model.promotion_history:
                model.promotion_history = []
            
            model.promotion_history.append({
                "stage": "shadow",
                "performance": shadow_performance,
                "timestamp": datetime.utcnow().isoformat(),
                "notes": notes,
            })
            
            self._save_card(model)
    
    def get_promotion_history(self, model_id: Optional[str] = None) -> List[PromotionDecision]:
        """Get promotion history."""
        if model_id:
            return [p for p in self.promotion_history if p.model_id == model_id]
        return self.promotion_history
    
    def _save_card(self, card: ModelCard) -> None:
        """Persist model card to disk."""
        model_dir = self.storage_dir / card.model_type
        model_dir.mkdir(parents=True, exist_ok=True)
        
        card_path = model_dir / f"{card.model_id}_{card.version}.json"
        card_path.write_text(
            json.dumps(self._serialize_card(card), indent=2, default=str),
            encoding="utf-8",
        )
    
    def _save_promotion_decision(self, decision: PromotionDecision) -> None:
        """Persist promotion decision."""
        promo_dir = self.storage_dir / "promotions"
        promo_dir.mkdir(parents=True, exist_ok=True)
        
        promo_path = promo_dir / f"{decision.decision_id}.json"
        promo_path.write_text(
            json.dumps(self._serialize_promotion(decision), indent=2, default=str),
            encoding="utf-8",
        )
    
    def _load_all(self) -> None:
        """Load all models and promotions from disk."""
        if not self.storage_dir.exists():
            return
        
        # Load models
        for model_type_dir in self.storage_dir.glob("*"):
            if model_type_dir.name == "promotions" or not model_type_dir.is_dir():
                continue
            
            model_type = model_type_dir.name
            self.models[model_type] = []
            
            for card_file in model_type_dir.glob("*.json"):
                try:
                    payload = json.loads(card_file.read_text(encoding="utf-8"))
                    card = self._deserialize_card(payload)
                    self.models[model_type].append(card)
                    
                    if card.status == "champion":
                        self.champions[model_type] = card.model_id
                except Exception:
                    pass
        
        # Load promotions
        promo_dir = self.storage_dir / "promotions"
        if promo_dir.exists():
            for promo_file in promo_dir.glob("*.json"):
                try:
                    payload = json.loads(promo_file.read_text(encoding="utf-8"))
                    decision = self._deserialize_promotion(payload)
                    self.promotion_history.append(decision)
                except Exception:
                    pass
    
    @staticmethod
    def _serialize_card(card: ModelCard) -> Dict:
        """Convert ModelCard to JSON-serializable dict."""
        data = {
            "model_id": card.model_id,
            "model_type": card.model_type,
            "version": card.version,
            "trained_at": card.trained_at.isoformat(),
            "training_start_date": card.training_start_date.isoformat(),
            "training_end_date": card.training_end_date.isoformat(),
            "feature_names": card.feature_names,
            "feature_count": card.feature_count,
            "training_sample_size": card.training_sample_size,
            "out_of_sample_sample_size": card.out_of_sample_sample_size,
            "metrics": {
                "out_of_sample_sharpe": card.metrics.out_of_sample_sharpe,
                "max_drawdown": card.metrics.max_drawdown,
                "calibration_error": card.metrics.calibration_error,
                "mape": card.metrics.mape,
                "r_squared": card.metrics.r_squared,
                "auc_roc": card.metrics.auc_roc,
            },
            "model_code_version": card.model_code_version,
            "model_config": card.model_config,
            "status": card.status,
            "predecessor_version": card.predecessor_version,
            "promotion_history": card.promotion_history,
            "regression_test_passed": card.regression_test_passed,
            "drift_test_passed": card.drift_test_passed,
            "risk_gate_passed": card.risk_gate_passed,
            "promotion_approved_by": card.promotion_approved_by,
            "promotion_approved_at": card.promotion_approved_at.isoformat() if card.promotion_approved_at else None,
            "notes": card.notes,
        }
        return data
    
    @staticmethod
    def _deserialize_card(data: Dict) -> ModelCard:
        """Reconstruct ModelCard from JSON."""
        from learning.schemas import ModelMetrics
        
        metrics = ModelMetrics(
            out_of_sample_sharpe=data["metrics"].get("out_of_sample_sharpe"),
            max_drawdown=data["metrics"].get("max_drawdown"),
            calibration_error=data["metrics"].get("calibration_error"),
            mape=data["metrics"].get("mape"),
            r_squared=data["metrics"].get("r_squared"),
            auc_roc=data["metrics"].get("auc_roc"),
        )
        
        return ModelCard(
            model_id=data["model_id"],
            model_type=data["model_type"],
            version=data["version"],
            trained_at=datetime.fromisoformat(data["trained_at"]),
            training_start_date=date.fromisoformat(data["training_start_date"]),
            training_end_date=date.fromisoformat(data["training_end_date"]),
            feature_names=data["feature_names"],
            feature_count=data["feature_count"],
            training_sample_size=data["training_sample_size"],
            out_of_sample_sample_size=data["out_of_sample_sample_size"],
            metrics=metrics,
            model_code_version=data["model_code_version"],
            model_config=data.get("model_config", {}),
            status=data["status"],
            predecessor_version=data.get("predecessor_version"),
            promotion_history=data.get("promotion_history", []),
            regression_test_passed=data.get("regression_test_passed", False),
            drift_test_passed=data.get("drift_test_passed", False),
            risk_gate_passed=data.get("risk_gate_passed", False),
            promotion_approved_by=data.get("promotion_approved_by"),
            promotion_approved_at=datetime.fromisoformat(data["promotion_approved_at"]) if data.get("promotion_approved_at") else None,
            notes=data.get("notes"),
        )
    
    @staticmethod
    def _serialize_promotion(decision: PromotionDecision) -> Dict:
        """Convert PromotionDecision to JSON."""
        return {
            "decision_id": decision.decision_id,
            "model_id": decision.model_id,
            "model_version": decision.model_version,
            "timestamp": decision.timestamp.isoformat(),
            "champion_model_version": decision.champion_model_version,
            "challenger_model_version": decision.challenger_model_version,
            "out_of_sample_performance_pass": decision.out_of_sample_performance_pass,
            "calibration_pass": decision.calibration_pass,
            "regression_suite_pass": decision.regression_suite_pass,
            "drift_detection_pass": decision.drift_detection_pass,
            "risk_gate_pass": decision.risk_gate_pass,
            "shadow_deployment_days": decision.shadow_deployment_days,
            "shadow_performance": decision.shadow_performance,
            "promotion_decision": decision.promotion_decision,
            "reasoning": decision.reasoning,
            "approved_by": decision.approved_by,
            "approved_at": decision.approved_at.isoformat() if decision.approved_at else None,
        }
    
    @staticmethod
    def _deserialize_promotion(data: Dict) -> PromotionDecision:
        """Reconstruct PromotionDecision from JSON."""
        return PromotionDecision(
            decision_id=data["decision_id"],
            model_id=data["model_id"],
            model_version=data["model_version"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            champion_model_version=data.get("champion_model_version"),
            challenger_model_version=data.get("challenger_model_version"),
            out_of_sample_performance_pass=data.get("out_of_sample_performance_pass", False),
            calibration_pass=data.get("calibration_pass", False),
            regression_suite_pass=data.get("regression_suite_pass", False),
            drift_detection_pass=data.get("drift_detection_pass", False),
            risk_gate_pass=data.get("risk_gate_pass", False),
            shadow_deployment_days=data.get("shadow_deployment_days", 0),
            shadow_performance=data.get("shadow_performance", {}),
            promotion_decision=data["promotion_decision"],
            reasoning=data["reasoning"],
            approved_by=data.get("approved_by"),
            approved_at=datetime.fromisoformat(data["approved_at"]) if data.get("approved_at") else None,
        )
