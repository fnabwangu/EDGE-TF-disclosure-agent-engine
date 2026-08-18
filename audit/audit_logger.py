"""Immutable SHA-256 audit records."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional


class AuditEventType(str, Enum):
    PRE_TRADE_COMPLIANCE = "PRE_TRADE_COMPLIANCE"
    EXECUTION_ORDER = "EXECUTION_ORDER"
    TRADE_EXECUTION_RESULT = "TRADE_EXECUTION_RESULT"
    POSTMORTEM_ANALYSIS = "POSTMORTEM_ANALYSIS"


@dataclass
class AuditRecord:
    record_id: str
    event_type: AuditEventType
    timestamp_utc: str
    operator_id: str
    role: str
    payload: Dict[str, Any]
    record_hash: str = ""

    def compute_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.payload, sort_keys=True, default=str).encode()).hexdigest()


class AuditLogger:
    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or Path("data/audit_logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_event(self, event_type: AuditEventType, operator_id: str, role: str, payload: Dict[str, Any]) -> AuditRecord:
        timestamp = datetime.now(timezone.utc).isoformat()
        record = AuditRecord(f"{event_type.value}-{int(datetime.now(timezone.utc).timestamp() * 1000)}", event_type, timestamp, operator_id, role, payload)
        record.record_hash = record.compute_hash()
        with (self.log_dir / f"{record.record_id}.json").open("w", encoding="utf-8") as handle:
            json.dump({**record.__dict__, "event_type": record.event_type.value}, handle, default=str, indent=2)
        return record

    def verify_record_integrity(self, record: AuditRecord) -> bool:
        return record.record_hash == record.compute_hash()


__all__ = ["AuditEventType", "AuditRecord", "AuditLogger"]
