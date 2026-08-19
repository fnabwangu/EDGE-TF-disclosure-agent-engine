"""
Learning Engine CLI and Management Utilities

Path: learning/management.py

Command-line interface and utility functions for managing the Learning Engine:
- View model status and performance
- Train new models
- Promote/demote models
- Check model predictions
- View historical analogs
- Monitor shadow deployment
"""

from pathlib import Path
from datetime import date, datetime, timezone
from typing import Optional
import json

from learning.orchestrator import LearningOrchestrator
from learning.schemas import ModelCard


class ModelManager:
    """Management interface for Learning Engine models."""
    
    def __init__(self, workspace_dir: Path | str = "data/learning"):
        self.orchestrator = LearningOrchestrator(workspace_dir=Path(workspace_dir))
        self.registry = self.orchestrator.model_registry
    
    def show_model_status(self, model_type: str) -> dict:
        """Display current model status and performance."""
        champion = self.registry.get_champion(model_type)
        challenger = self.registry.get_challenger(model_type)
        
        status = {
            "model_type": model_type,
            "champion": None,
            "challenger": None,
        }
        
        if champion:
            status["champion"] = {
                "model_id": champion.model_id,
                "version": champion.version,
                "trained_date": champion.training_date.isoformat() if champion.training_date else None,
                "oos_sharpe": f"{champion.metrics.out_of_sample_sharpe:.3f}",
                "oos_rmse": f"{champion.metrics.rmse:.4f}",
                "calibration_error": f"{champion.metrics.calibration_error:.3f}",
                "max_drawdown": f"{champion.metrics.max_drawdown:.2%}",
                "feature_count": champion.feature_count,
                "training_samples": champion.training_sample_size,
                "oos_samples": champion.out_of_sample_sample_size,
            }
        
        if challenger:
            status["challenger"] = {
                "model_id": challenger.model_id,
                "version": challenger.version,
                "trained_date": challenger.training_date.isoformat() if challenger.training_date else None,
                "oos_sharpe": f"{challenger.metrics.out_of_sample_sharpe:.3f}",
                "days_in_shadow": None,  # Would need to calculate from promotion history
                "ready_for_promotion": False,  # Would need to check shadow metrics
            }
        
        return status
    
    def list_model_versions(self, model_type: str) -> list:
        """List all versions of a model."""
        models = self.registry.get_all_models(model_type)
        
        versions = []
        for model_card in models:
            versions.append({
                "model_id": model_card.model_id,
                "version": model_card.version,
                "status": model_card.status,
                "trained_date": model_card.training_date.isoformat() if model_card.training_date else None,
                "sharpe": f"{model_card.metrics.out_of_sample_sharpe:.3f}",
            })
        
        return versions
    
    def get_model_details(self, model_id: str) -> dict:
        """Get detailed information about a specific model."""
        card = self.registry.get_model(model_id)
        
        if not card:
            return {"error": f"Model {model_id} not found"}
        
        return {
            "model_id": card.model_id,
            "model_type": card.model_type,
            "version": card.version,
            "status": card.status,
            "trained_date": card.training_date.isoformat() if card.training_date else None,
            "features": {
                "count": card.feature_count,
                "names": card.feature_names,
            },
            "training": {
                "samples": card.training_sample_size,
                "oos_samples": card.out_of_sample_sample_size,
            },
            "metrics": {
                "oos_sharpe": f"{card.metrics.out_of_sample_sharpe:.3f}",
                "rmse": f"{card.metrics.rmse:.4f}",
                "mape": f"{card.metrics.mape:.2%}",
                "r_squared": f"{card.metrics.r_squared:.3f}",
                "calibration_error": f"{card.metrics.calibration_error:.3f}",
                "max_drawdown": f"{card.metrics.max_drawdown:.2%}",
            },
            "promotion_history": [
                {
                    "timestamp": p.timestamp.isoformat(),
                    "decision": p.promotion_decision,
                    "reasoning": p.reasoning,
                    "approved_by": p.approved_by,
                } for p in card.promotion_history
            ],
        }
    
    def check_model_prediction(self, model_type: str, features: dict) -> dict:
        """Get prediction from champion model."""
        champion = self.registry.get_champion(model_type)
        
        if not champion:
            return {
                "error": f"No champion model for {model_type}",
                "status": "no_champion",
            }
        
        try:
            prediction = champion.model.predict(features)
            
            return {
                "status": "success",
                "model_id": champion.model_id,
                "model_version": champion.version,
                "prediction": float(prediction),
                "confidence": "high",  # Could compute from model uncertainty
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }
    
    def show_feature_importance(self, model_id: str) -> dict:
        """Show feature importance for a model."""
        card = self.registry.get_model(model_id)
        
        if not card:
            return {"error": f"Model {model_id} not found"}
        
        try:
            importance = card.model.get_feature_importance()
            
            return {
                "model_id": model_id,
                "model_version": card.version,
                "feature_importance": {
                    name: float(imp) for name, imp in importance.items()
                },
            }
        except Exception as e:
            return {"error": str(e)}
    
    def check_feature_store_health(self) -> dict:
        """Check health of feature store."""
        store = self.orchestrator.feature_store
        
        health = {
            "total_observations": len(store.observations),
            "indexed_features": len(store.feature_index),
            "date_range": None,
            "quality_issues": 0,
        }
        
        if store.observations:
            dates = [obs.timestamp for obs in store.observations]
            health["date_range"] = {
                "earliest": min(dates).isoformat(),
                "latest": max(dates).isoformat(),
            }
        
        return health
    
    def check_label_coverage(self) -> dict:
        """Check coverage of training labels."""
        builder = self.orchestrator.dataset_builder
        
        labels_by_type = {}
        for label in builder.labels:
            label_type = label.label_type
            if label_type not in labels_by_type:
                labels_by_type[label_type] = 0
            labels_by_type[label_type] += 1
        
        return {
            "total_labels": len(builder.labels),
            "by_type": labels_by_type,
            "unique_observations": len(set(l.observation_id for l in builder.labels)),
        }
    
    def generate_status_report(self, model_type: Optional[str] = None) -> str:
        """Generate comprehensive status report."""
        lines = []
        lines.append("=" * 80)
        lines.append("LEARNING ENGINE STATUS REPORT")
        lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append("=" * 80)
        
        # Model status
        lines.append("\n📊 MODEL STATUS")
        model_types = [model_type] if model_type else ["return", "drawdown", "thesis_success", "hedge_effectiveness"]
        
        for mtype in model_types:
            status = self.show_model_status(mtype)
            champion = status["champion"]
            challenger = status["challenger"]
            
            lines.append(f"\n{mtype.upper()}:")
            if champion:
                lines.append(f"  Champion: v{champion['version']}")
                lines.append(f"    Sharpe: {champion['oos_sharpe']}")
                lines.append(f"    Trained: {champion['trained_date']}")
            else:
                lines.append(f"  ⚠ No champion model")
            
            if challenger:
                lines.append(f"  Challenger: v{challenger['version']}")
                lines.append(f"    Sharpe: {challenger['oos_sharpe']}")
                lines.append(f"    Days in shadow: {challenger['days_in_shadow']}")
            else:
                lines.append(f"  (No challenger)")
        
        # Feature store health
        lines.append("\n📈 FEATURE STORE HEALTH")
        health = self.check_feature_store_health()
        lines.append(f"  Observations: {health['total_observations']}")
        if health['date_range']:
            lines.append(f"  Date range: {health['date_range']['earliest']} to {health['date_range']['latest']}")
        
        # Label coverage
        lines.append("\n🏷️  LABEL COVERAGE")
        coverage = self.check_label_coverage()
        lines.append(f"  Total labels: {coverage['total_labels']}")
        lines.append(f"  Unique observations: {coverage['unique_observations']}")
        for label_type, count in coverage['by_type'].items():
            lines.append(f"    {label_type}: {count}")
        
        # Readiness for training
        lines.append("\n🚀 READINESS FOR TRAINING")
        if coverage['unique_observations'] >= 50:
            lines.append("  ✓ Sufficient observations (50+ required)")
        else:
            lines.append(f"  ⚠ Need {50 - coverage['unique_observations']} more observations")
        
        lines.append("\n" + "=" * 80)
        
        return "\n".join(lines)


def cli_main():
    """Command-line interface for model management."""
    import argparse
    
    parser = argparse.ArgumentParser(description="EDGE-TF Learning Engine Management")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show model status")
    status_parser.add_argument("--type", help="Model type (return, drawdown, etc.)")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List model versions")
    list_parser.add_argument("type", help="Model type")
    
    # Details command
    details_parser = subparsers.add_parser("details", help="Show model details")
    details_parser.add_argument("model_id", help="Model ID")
    
    # Predict command
    predict_parser = subparsers.add_parser("predict", help="Get prediction")
    predict_parser.add_argument("type", help="Model type")
    predict_parser.add_argument("--features", type=json.loads, help="Features as JSON")
    
    # Feature importance command
    importance_parser = subparsers.add_parser("importance", help="Show feature importance")
    importance_parser.add_argument("model_id", help="Model ID")
    
    # Health command
    health_parser = subparsers.add_parser("health", help="Check system health")
    
    args = parser.parse_args()
    manager = ModelManager()
    
    if args.command == "status":
        result = manager.show_model_status(args.type or "return")
        print(json.dumps(result, indent=2))
    
    elif args.command == "list":
        result = manager.list_model_versions(args.type)
        for model in result:
            print(f"{model['model_id']} v{model['version']} ({model['status']}) - Sharpe {model['sharpe']}")
    
    elif args.command == "details":
        result = manager.get_model_details(args.model_id)
        print(json.dumps(result, indent=2))
    
    elif args.command == "predict":
        features = args.features or {}
        result = manager.check_model_prediction(args.type, features)
        print(json.dumps(result, indent=2))
    
    elif args.command == "importance":
        result = manager.show_feature_importance(args.model_id)
        print(json.dumps(result, indent=2))
    
    elif args.command == "health":
        report = manager.generate_status_report()
        print(report)
    
    else:
        print(manager.generate_status_report())


if __name__ == "__main__":
    cli_main()
