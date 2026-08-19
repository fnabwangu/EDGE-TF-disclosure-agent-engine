"""
Shadow deployment and model performance tracking.

Path: learning/shadow_deployment.py

Challenger models run in shadow mode before promotion:
- Receive same inputs as champion model
- Generate predictions alongside champion
- Track performance metrics without affecting decisions
- Collect evidence for promotion decision

Shadow period requirements:
- Minimum observations (e.g., 50+)
- Minimum calendar time (e.g., 30 days)
- Challenger must outperform champion or at least match it
- Human approval required before promotion
"""

from datetime import datetime, date, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import json

from learning.schemas import ModelCard, ModelMetrics


@dataclass
class ShadowPrediction:
    """Record of both champion and challenger predictions."""
    observation_id: str
    timestamp: datetime
    actual_outcome: Optional[float] = None
    
    # Champion predictions
    champion_model_id: str = ""
    champion_prediction: float = 0.0
    
    # Challenger predictions
    challenger_model_id: str = ""
    challenger_prediction: float = 0.0
    
    # Outcome recorded later when available
    outcome_recorded_at: Optional[datetime] = None


@dataclass
class ShadowMetrics:
    """Performance metrics comparing challenger vs champion."""
    observation_count: int = 0
    outcome_count: int = 0
    
    champion_mape: Optional[float] = None
    challenger_mape: Optional[float] = None
    
    champion_sharpe: Optional[float] = None
    challenger_sharpe: Optional[float] = None
    
    champion_max_dd: Optional[float] = None
    challenger_max_dd: Optional[float] = None
    
    # Head-to-head comparison
    challenger_beats_champion_count: int = 0
    champion_beats_challenger_count: int = 0
    ties: int = 0
    
    days_in_shadow: int = 0
    challenger_ready_for_promotion: bool = False
    promotion_reasoning: Optional[str] = None


class ShadowDeploymentController:
    """
    Manages shadow deployment of challenger models.
    
    Ensures challenger runs alongside champion, collects performance data,
    and makes evidence-based promotion recommendations.
    """
    
    def __init__(self, storage_dir: Path | str = "data/shadow_deployment"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Active shadow deployments: model_type -> ShadowDeployment
        self.deployments: Dict[str, "ShadowDeployment"] = {}
        self.predictions_log: Dict[str, List[ShadowPrediction]] = {}
        
        self._load_existing()
    
    def _load_existing(self) -> None:
        """Load existing shadow deployment records."""
        deployments_dir = self.storage_dir / "deployments"
        if deployments_dir.exists():
            for json_file in deployments_dir.glob("*.json"):
                deployment = ShadowDeployment.from_json(json_file)
                self.deployments[deployment.model_type] = deployment
    
    def start_shadow_deployment(
        self,
        model_type: str,
        champion: ModelCard,
        challenger: ModelCard,
    ) -> "ShadowDeployment":
        """
        Start new shadow deployment for a challenger model.
        
        Returns:
            ShadowDeployment object tracking the deployment
        """
        deployment = ShadowDeployment(
            model_type=model_type,
            champion_model_id=champion.model_id,
            challenger_model_id=challenger.model_id,
            start_date=date.today(),
        )
        
        self.deployments[model_type] = deployment
        deployment.save(self.storage_dir / "deployments")
        
        return deployment
    
    def record_prediction_pair(
        self,
        model_type: str,
        observation_id: str,
        champion_pred: float,
        challenger_pred: float,
        champion_model_id: str,
        challenger_model_id: str,
    ) -> None:
        """
        Record predictions from both champion and challenger models.
        
        Called during research/implementation phase when both models
        are evaluated on same inputs.
        """
        if model_type not in self.deployments:
            return
        
        pred = ShadowPrediction(
            observation_id=observation_id,
            timestamp=datetime.now(timezone.utc),
            champion_model_id=champion_model_id,
            champion_prediction=champion_pred,
            challenger_model_id=challenger_model_id,
            challenger_prediction=challenger_pred,
        )
        
        if model_type not in self.predictions_log:
            self.predictions_log[model_type] = []
        
        self.predictions_log[model_type].append(pred)
    
    def record_outcome(
        self,
        model_type: str,
        observation_id: str,
        actual_outcome: float,
    ) -> None:
        """
        Record actual outcome when trade/thesis completes.
        
        This allows comparison of model predictions to actual results.
        """
        if model_type not in self.predictions_log:
            return
        
        for pred in self.predictions_log[model_type]:
            if pred.observation_id == observation_id and pred.actual_outcome is None:
                pred.actual_outcome = actual_outcome
                pred.outcome_recorded_at = datetime.now(timezone.utc)
                break
    
    def compute_shadow_metrics(
        self,
        model_type: str,
    ) -> ShadowMetrics:
        """
        Compute performance comparison between challenger and champion.
        
        Returns:
            ShadowMetrics with head-to-head performance statistics
        """
        if model_type not in self.predictions_log or model_type not in self.deployments:
            return ShadowMetrics()
        
        deployment = self.deployments[model_type]
        predictions = self.predictions_log[model_type]
        
        # Filter to predictions with outcomes recorded
        completed = [p for p in predictions if p.actual_outcome is not None]
        
        if not completed:
            return ShadowMetrics(observation_count=len(predictions))
        
        # Compute errors
        champion_errors = [
            abs(p.champion_prediction - p.actual_outcome)
            for p in completed
        ]
        challenger_errors = [
            abs(p.challenger_prediction - p.actual_outcome)
            for p in completed
        ]
        
        champion_mape = (sum(champion_errors) / len(champion_errors)) if champion_errors else 0.0
        challenger_mape = (sum(challenger_errors) / len(challenger_errors)) if challenger_errors else 0.0
        
        # Head-to-head comparison
        challenger_wins = sum(
            1 for c_err, ch_err in zip(challenger_errors, champion_errors)
            if c_err < ch_err
        )
        champion_wins = sum(
            1 for c_err, ch_err in zip(challenger_errors, champion_errors)
            if c_err > ch_err
        )
        ties = len(completed) - challenger_wins - champion_wins
        
        # Days in shadow
        days_in_shadow = (date.today() - deployment.start_date).days
        
        # Promotion readiness
        ready_for_promotion = (
            challenger_mape <= champion_mape and
            days_in_shadow >= deployment.min_shadow_days and
            len(completed) >= deployment.min_shadow_observations
        )
        
        promotion_reasoning = self._generate_promotion_reasoning(
            challenger_mape=challenger_mape,
            champion_mape=champion_mape,
            challenger_wins=challenger_wins,
            champion_wins=champion_wins,
            days_in_shadow=days_in_shadow,
            observation_count=len(completed),
            ready=ready_for_promotion,
            deployment=deployment,
        )
        
        return ShadowMetrics(
            observation_count=len(predictions),
            outcome_count=len(completed),
            champion_mape=champion_mape,
            challenger_mape=challenger_mape,
            champion_sharpe=None,  # Would compute from prediction series
            challenger_sharpe=None,
            champion_max_dd=None,
            challenger_max_dd=None,
            challenger_beats_champion_count=challenger_wins,
            champion_beats_challenger_count=champion_wins,
            ties=ties,
            days_in_shadow=days_in_shadow,
            challenger_ready_for_promotion=ready_for_promotion,
            promotion_reasoning=promotion_reasoning,
        )
    
    def _generate_promotion_reasoning(
        self,
        challenger_mape: float,
        champion_mape: float,
        challenger_wins: int,
        champion_wins: int,
        days_in_shadow: int,
        observation_count: int,
        ready: bool,
        deployment: "ShadowDeployment",
    ) -> str:
        """Generate human-readable promotion recommendation."""
        parts = []
        
        # Performance comparison
        improvement = ((champion_mape - challenger_mape) / max(champion_mape, 1e-6)) * 100
        parts.append(f"Challenger MAPE: {challenger_mape:.4f} vs Champion {champion_mape:.4f} ({improvement:+.1f}%)")
        
        # Head-to-head
        parts.append(f"Head-to-head: Challenger wins {challenger_wins}/{observation_count}, Champion wins {champion_wins}/{observation_count}")
        
        # Shadow duration
        parts.append(f"Shadow deployment duration: {days_in_shadow} days (minimum required: {deployment.min_shadow_days})")
        
        # Sample size
        parts.append(f"Completed outcomes: {observation_count}/{len(self.predictions_log.get(deployment.model_type, []))} (minimum: {deployment.min_shadow_observations})")
        
        # Ready status
        if ready:
            parts.append("✓ READY FOR PROMOTION: All gates passed")
        else:
            blocking = []
            if challenger_mape > champion_mape:
                blocking.append("challenger performance not better than champion")
            if days_in_shadow < deployment.min_shadow_days:
                blocking.append(f"shadow period too short ({days_in_shadow} < {deployment.min_shadow_days} days)")
            if observation_count < deployment.min_shadow_observations:
                blocking.append(f"insufficient outcomes ({observation_count} < {deployment.min_shadow_observations})")
            parts.append(f"✗ NOT READY: {'; '.join(blocking)}")
        
        return "\n".join(parts)
    
    def get_shadow_deployment(self, model_type: str) -> Optional["ShadowDeployment"]:
        """Get current shadow deployment for model type."""
        return self.deployments.get(model_type)


@dataclass
class ShadowDeployment:
    """Configuration and metadata for a shadow deployment."""
    model_type: str
    champion_model_id: str
    challenger_model_id: str
    start_date: date
    
    min_shadow_days: int = 30
    min_shadow_observations: int = 50
    required_performance_improvement: float = 0.0  # At least tie
    
    promotion_approved: bool = False
    promotion_approved_at: Optional[datetime] = None
    promotion_approved_by: Optional[str] = None
    
    notes: Optional[str] = None
    
    def save(self, storage_dir: Path) -> None:
        """Persist deployment to JSON."""
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        path = storage_dir / f"{self.model_type}_shadow.json"
        data = {
            "model_type": self.model_type,
            "champion_model_id": self.champion_model_id,
            "challenger_model_id": self.challenger_model_id,
            "start_date": self.start_date.isoformat(),
            "min_shadow_days": self.min_shadow_days,
            "min_shadow_observations": self.min_shadow_observations,
            "required_performance_improvement": self.required_performance_improvement,
            "promotion_approved": self.promotion_approved,
            "promotion_approved_at": self.promotion_approved_at.isoformat() if self.promotion_approved_at else None,
            "promotion_approved_by": self.promotion_approved_by,
            "notes": self.notes,
        }
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def from_json(cls, path: Path) -> "ShadowDeployment":
        """Load deployment from JSON."""
        with open(path) as f:
            data = json.load(f)
        
        return cls(
            model_type=data["model_type"],
            champion_model_id=data["champion_model_id"],
            challenger_model_id=data["challenger_model_id"],
            start_date=date.fromisoformat(data["start_date"]),
            min_shadow_days=data.get("min_shadow_days", 30),
            min_shadow_observations=data.get("min_shadow_observations", 50),
            required_performance_improvement=data.get("required_performance_improvement", 0.0),
            promotion_approved=data.get("promotion_approved", False),
            promotion_approved_at=datetime.fromisoformat(data["promotion_approved_at"]) if data.get("promotion_approved_at") else None,
            promotion_approved_by=data.get("promotion_approved_by"),
            notes=data.get("notes"),
        )
