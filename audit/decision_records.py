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

    def read_all(self) -> List[DecisionRecord]:
        records = []
        for path in sorted(self.log_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            records.append(DecisionRecord(**payload))
        return records


__all__ = ["DecisionRecord", "DecisionRecorder", "DEFAULT_DIR"]
