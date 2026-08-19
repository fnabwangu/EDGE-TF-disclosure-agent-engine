"""
Decision Records for model-in-the-loop generation.

Path: audit/decision_records.py

Every time EDGE asks a model to propose something that will reach a human, the
full chain must be reconstructable afterward: what was asked, what came back,
what the deterministic gates did with it, and what was actually published.
This is that record - append-only, hash-stamped, and written independently of
the workbench event log so it survives even if that log is unavailable.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_DIR = Path("data/decision_records")


@dataclass(frozen=True)
class DecisionRecord:
    record_id: str
    kind: str
    at: str
    project_id: Optional[str]
    strategy_id: Optional[str]
    model: str
    response_id: Optional[str]
    request_instructions: str
    request_input: str
    raw_candidates: List[Dict[str, Any]]
    validation_results: List[Dict[str, Any]]
    accepted_candidate_ids: List[str]
    error: Optional[str]
    record_hash: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k != "record_hash"}

    def compute_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(self.as_dict(), sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()


class DecisionRecorder:
    def __init__(self, log_dir: Path | str = DEFAULT_DIR):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def record_implementation_generation(
        self,
        *,
        project_id: Optional[str],
        strategy_id: str,
        model: str,
        response_id: Optional[str],
        instructions: str,
        input_summary: str,
        raw_candidates: List[Dict[str, Any]],
        validation_results: List[Dict[str, Any]],
        accepted_candidate_ids: List[str],
        error: Optional[str] = None,
    ) -> DecisionRecord:
        record = DecisionRecord(
            record_id=str(uuid.uuid4()),
            kind="IMPLEMENTATION_GENERATION",
            at=datetime.now(timezone.utc).isoformat(),
            project_id=project_id,
            strategy_id=strategy_id,
            model=model,
            response_id=response_id,
            request_instructions=instructions,
            request_input=input_summary,
            raw_candidates=raw_candidates,
            validation_results=validation_results,
            accepted_candidate_ids=accepted_candidate_ids,
            error=error,
        )
        record = DecisionRecord(**{**record.as_dict(), "record_hash": record.compute_hash()})
        self._write(record)
        return record

    def _write(self, record: DecisionRecord) -> None:
        path = self.log_dir / f"{record.record_id}.json"
        path.write_text(json.dumps(record.as_dict() | {"record_hash": record.record_hash}, indent=2, default=str), encoding="utf-8")

    def record_model_training(
        self,
        *,
        model_type: str,
        model_id: str,
        model_version: str,
        dataset_version: str,
        training_start_date: str,
        training_end_date: str,
        feature_count: int,
        training_sample_size: int,
        out_of_sample_sample_size: int,
        metrics: Dict[str, Any],
        walk_forward_splits: int,
        feature_names: List[str],
        code_version: str = "1.0",
    ) -> DecisionRecord:
        """
        Record model training run with full auditability.
        
        Documents:
        - Training dataset version and date range
        - Model architecture and features
        - Training metrics and walk-forward results
        - Code version for reproducibility
        """
        record = DecisionRecord(
            record_id=str(uuid.uuid4()),
            kind="MODEL_TRAINING",
            at=datetime.now(timezone.utc).isoformat(),
            project_id=None,
            strategy_id=None,
            model=f"{model_type}_{model_id}",
            response_id=model_version,
            request_instructions=f"Train {model_type} model on dataset {dataset_version}",
            request_input=f"Training: {training_start_date} to {training_end_date}. Features: {feature_count}. Samples: {training_sample_size}/{out_of_sample_sample_size}",
            raw_candidates=[],
            validation_results=[
                {
                    "metric": k,
                    "value": v,
                }
                for k, v in metrics.items()
            ],
            accepted_candidate_ids=[model_version],
            error=None,
        )
        
        # Attach extended metadata
        record_dict = record.as_dict()
        record_dict["model_type"] = model_type
        record_dict["model_id"] = model_id
        record_dict["model_version"] = model_version
        record_dict["dataset_version"] = dataset_version
        record_dict["feature_count"] = feature_count
        record_dict["training_sample_size"] = training_sample_size
        record_dict["out_of_sample_sample_size"] = out_of_sample_sample_size
        record_dict["walk_forward_splits"] = walk_forward_splits
        record_dict["feature_names"] = feature_names
        record_dict["code_version"] = code_version
        
        record = DecisionRecord(**{**record_dict, "record_hash": record.compute_hash()})
        self._write(record)
        return record
    
    def record_model_promotion(
        self,
        *,
        model_type: str,
        model_id: str,
        model_version: str,
        promotion_decision: str,
        gate_results: Dict[str, bool],
        reasoning: str,
        approved_by: Optional[str] = None,
        champion_version: Optional[str] = None,
    ) -> DecisionRecord:
        """
        Record model promotion decision with gate results.
        
        Documents:
        - Promotion decision (promote/demote/hold)
        - All gate pass/fail results
        - Decision reasoning and approval
        """
        record = DecisionRecord(
            record_id=str(uuid.uuid4()),
            kind="MODEL_PROMOTION",
            at=datetime.now(timezone.utc).isoformat(),
            project_id=None,
            strategy_id=None,
            model=f"{model_type}_{model_id}",
            response_id=model_version,
            request_instructions=f"Evaluate {model_type} model {model_id} for promotion",
            request_input=f"Champion: {champion_version or 'none'}. Gates: {list(gate_results.keys())}",
            raw_candidates=[],
            validation_results=[
                {
                    "gate": gate,
                    "passed": passed,
                }
                for gate, passed in gate_results.items()
            ],
            accepted_candidate_ids=[model_version] if promotion_decision == "promote" else [],
            error=None,
        )
        
        # Attach extended metadata
        record_dict = record.as_dict()
        record_dict["model_type"] = model_type
        record_dict["model_id"] = model_id
        record_dict["model_version"] = model_version
        record_dict["promotion_decision"] = promotion_decision
        record_dict["champion_version"] = champion_version
        record_dict["reasoning"] = reasoning
        record_dict["approved_by"] = approved_by
        record_dict["approved_at"] = datetime.now(timezone.utc).isoformat()
        record_dict["all_gates_passed"] = all(gate_results.values())
        
        record = DecisionRecord(**{**record_dict, "record_hash": record.compute_hash()})
        self._write(record)
        return record

    def read_all(self) -> List[DecisionRecord]:
        records = []
        for path in sorted(self.log_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            records.append(DecisionRecord(**payload))
        return records
    
    def read_by_kind(self, kind: str) -> List[DecisionRecord]:
        """Get all decision records of a specific kind."""
        records = []
        for path in sorted(self.log_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("kind") == kind:
                records.append(DecisionRecord(**payload))
        return records


__all__ = ["DecisionRecord", "DecisionRecorder", "DEFAULT_DIR"]
