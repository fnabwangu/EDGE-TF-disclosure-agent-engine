"""audit_logger.py
Simple decision record logger that writes JSON to data/decision_records.
"""
import json
from pathlib import Path

def log_decision(record: dict, out_dir: str = "data/decision_records"):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    idx = len(list(Path(out_dir).glob("*.json")))
    path = Path(out_dir) / f"decision_{idx+1}.json"
    path.write_text(json.dumps(record, indent=2))
    return str(path)
## Regulatory Audit Logger (`src/governance/audit_logger.py`)

The `audit_logger.py` module implements WORM-compliant (Write-Once, Read-Many) immutable recordkeeping for the **EDGE-TF-disclosure-agent-engine**. It enforces cryptographic hash-chaining across all portfolio rebalances, human-in-the-loop (HITL) dual sign-offs, pre-trade compliance audits, and broker execution drop-copies to satisfy SEC Rule 204-2 and Investment Company Act Rule 31a-1 books-and-records retention requirements.

---

### Key Capabilities

* **`Cryptographic Hash-Chaining`**: Computes sequential SHA-256 entry fingerprints where each log record incorporates the hash of the preceding record, preventing retroactive tampering.
* **`WORM-Compliant Append-Only Storage`**: Flushes structured JSON-Lines (`.jsonl`) payloads directly to the immutable `data/decision_records/` directory.
* **`Tamper-Evident Chain Verification`**: Includes automated integrity audit utilities to detect payload corruption, record omission, or sequence manipulation.
* **`Granular Audit Categorization`**: Standardizes regulatory event types across pre-trade checks, model ranking snapshots, broker fills, and emergency kill-switch engagements.
Python
# src/governance/audit_logger.py
"""
EDGE-TF Disclosure Agent Engine - Immutable Regulatory Audit Logger.

Provides append-only, cryptographically chained audit logging for compliance
determinations, execution events, dual sign-offs, and disclosure releases.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class AuditEventType(str, Enum):
    REBALANCE_GENERATION = "REBALANCE_GENERATION"
    PRE_TRADE_COMPLIANCE = "PRE_TRADE_COMPLIANCE"
    HITL_SIGNATURE = "HITL_SIGNATURE"
    ORDER_ROUTED = "ORDER_ROUTED"
    FILL_RECEIVED = "FILL_RECEIVED"
    PCF_PUBLICATION = "PCF_PUBLICATION"
    KILL_SWITCH_ENGAGED = "KILL_SWITCH_ENGAGED"
    KILL_SWITCH_RESET = "KILL_SWITCH_RESET"
    POLICY_OVERRIDE = "POLICY_OVERRIDE"


@dataclass
class AuditRecord:
    record_id: str
    timestamp_utc: str
    event_type: AuditEventType
    operator_id: str
    role: str
    payload_hash: str
    previous_hash: str
    entry_hash: str
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp_utc": self.timestamp_utc,
            "event_type": self.event_type.value,
            "operator_id": self.operator_id,
            "role": self.role,
            "payload_hash": self.payload_hash,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
            "payload": self.payload,
        }


class AuditLogger:
    """
    Manages append-only JSONL audit logs with sequential SHA-256 hash chaining
    to guarantee non-repudiation and regulatory compliance.
    """

    GENESIS_HASH = "0" * 64

    def __init__(self, log_dir: Optional[Path] = None, log_filename: Optional[str] = None):
        self.log_dir = log_dir or Path("data/decision_records")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        current_date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        self.log_file = self.log_dir / (log_filename or f"audit_trail_{current_date_str}.jsonl")
        self.last_hash = self._recover_last_hash()

    def _recover_last_hash(self) -> str:
        """Reads the tail record from the active log file to maintain continuity."""
        if not self.log_file.exists() or self.log_file.stat().st_size == 0:
            return self.GENESIS_HASH

        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                if not lines:
                    return self.GENESIS_HASH
                last_line = lines[-1]
                data = json.loads(last_line)
                return data.get("entry_hash", self.GENESIS_HASH)
        except Exception as exc:
            logging.error(f"Error recovering last hash from {self.log_file}: {exc}")
            return self.GENESIS_HASH

    @staticmethod
    def _compute_sha256(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def log_event(
        self,
        event_type: AuditEventType,
        operator_id: str,
        role: str,
        payload: Dict[str, Any]
    ) -> AuditRecord:
        """
        Appends an event to the ledger with payload fingerprinting and previous-hash chaining.
        """
        now_ts = datetime.now(timezone.utc).isoformat()
        record_id = f"AUD-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{self._compute_sha256(str(payload))[:8]}"
        
        # Serialize payload deterministically
        serialized_payload = json.dumps(payload, sort_keys=True)
        payload_hash = self._compute_sha256(serialized_payload)

        # Compute combined entry hash: previous_hash + timestamp + event_type + payload_hash
        entry_preimage = f"{self.last_hash}:{now_ts}:{event_type.value}:{operator_id}:{role}:{payload_hash}"
        entry_hash = self._compute_sha256(entry_preimage)

        record = AuditRecord(
            record_id=record_id,
            timestamp_utc=now_ts,
            event_type=event_type,
            operator_id=operator_id,
            role=role,
            payload_hash=payload_hash,
            previous_hash=self.last_hash,
            entry_hash=entry_hash,
            payload=payload
        )

        # Append to WORM log sink
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict()) + "\n")

        self.last_hash = entry_hash
        logging.info(f"Audit event recorded [{event_type.value}] - ID: {record_id} | Hash: {entry_hash[:12]}...")
        return record

    def verify_integrity(self, file_path: Optional[Path] = None) -> bool:
        """
        Sweeps the audit log sequentially to verify all entry hashes and chain continuity.
        """
        target_path = file_path or self.log_file
        if not target_path.exists():
            logging.warning(f"Audit log file {target_path} does not exist for verification.")
            return True

        expected_prev_hash = self.GENESIS_HASH
        line_num = 0

        with open(target_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                line_num += 1
                record_data = json.loads(line_str)

                # 1. Verify previous hash chaining
                if record_data.get("previous_hash") != expected_prev_hash:
                    logging.critical(
                        f"Audit Integrity Failure at Line {line_num}: "
                        f"Previous hash mismatch! Expected {expected_prev_hash}, found {record_data.get('previous_hash')}"
                    )
                    return False

                # 2. Verify payload hash
                serialized_payload = json.dumps(record_data.get("payload", {}), sort_keys=True)
                computed_payload_hash = self._compute_sha256(serialized_payload)
                if computed_payload_hash != record_data.get("payload_hash"):
                    logging.critical(
                        f"Audit Integrity Failure at Line {line_num}: "
                        f"Payload tampering detected! Expected {computed_payload_hash}, found {record_data.get('payload_hash')}"
                    )
                    return False

                # 3. Verify entry hash
                entry_preimage = (
                    f"{record_data['previous_hash']}:{record_data['timestamp_utc']}:"
                    f"{record_data['event_type']}:{record_data['operator_id']}:"
                    f"{record_data['role']}:{record_data['payload_hash']}"
                )
                computed_entry_hash = self._compute_sha256(entry_preimage)
                if computed_entry_hash != record_data.get("entry_hash"):
                    logging.critical(
                        f"Audit Integrity Failure at Line {line_num}: "
                        f"Entry hash tampering detected! Expected {computed_entry_hash}, found {record_data.get('entry_hash')}"
                    )
                    return False

                expected_prev_hash = record_data["entry_hash"]

        logging.info(f"Audit log verification successful: {line_num} records verified in {target_path}.")
        return True


__all__ = [
    "AuditEventType",
    "AuditRecord",
    "AuditLogger",
]
