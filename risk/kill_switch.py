"""
EDGE-TF Disclosure Agent Engine - Emergency Kill Switch & Circuit Breaker

Path: risk/kill_switch.py

Provides stateful operational lockouts, consecutive rejection monitoring,
dual-key cryptographic reset controls, and outbound trading halt triggers.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Set

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class KillSwitchState(str, Enum):
    ARMED_NOMINAL = "ARMED_NOMINAL"
    TRIPPED_AUTO = "TRIPPED_AUTO"
    ENGAGED_MANUAL = "ENGAGED_MANUAL"
    AWAITING_DUAL_AUTH = "AWAITING_DUAL_AUTH"


class TripTriggerType(str, Enum):
    CONSECUTIVE_REJECTIONS = "CONSECUTIVE_REJECTIONS"
    STATUTORY_BREACH = "STATUTORY_BREACH"
    DRAWDOWN_LIMIT = "DRAWDOWN_LIMIT"
    DATA_STALENESS = "DATA_STALENESS"
    MANUAL_OPERATOR_OVERRIDE = "MANUAL_OPERATOR_OVERRIDE"


@dataclass
class ResetSignature:
    signor_id: str
    role: str
    timestamp_utc: str
    justification: str
    signature_hash: str


@dataclass
class KillSwitchTelemetry:
    state: KillSwitchState
    is_trading_halted: bool
    rejection_count: int
    rejection_threshold: int
    active_trigger_reason: Optional[str]
    trip_timestamp_utc: Optional[str]
    signatures_collected: List[ResetSignature] = field(default_factory=list)


class ExecutionControl(Protocol):
    def cancel_all_open_orders(self) -> Any: ...
    def reconcile_positions(self) -> Any: ...


class EmergencyKillSwitchEngine:
    """
    Stateful circuit breaker that intercepts execution pipelines upon anomaly detection
    or compliance violations, requiring dual-fiduciary sign-offs to restore flow.
    """

    def __init__(
        self,
        consecutive_rejection_threshold: int = 3,
        authorized_reset_roles: Optional[Set[str]] = None,
        state_path: Optional[Path] = None,
        execution_control: Optional[ExecutionControl] = None,
        authorization_verifier: Optional[Callable[[str, str, str], bool]] = None,
    ):
        self.rejection_threshold = consecutive_rejection_threshold
        self.authorized_roles = authorized_reset_roles or {
            "CHIEF_COMPLIANCE_OFFICER",
            "LEAD_PORTFOLIO_MANAGER",
            "CHIEF_FINANCIAL_OFFICER"
        }
        self.required_signers_count = 2

        self.state: KillSwitchState = KillSwitchState.ARMED_NOMINAL
        self.consecutive_rejections: int = 0
        self.active_trigger_reason: Optional[str] = None
        self.trip_timestamp_utc: Optional[str] = None
        self.reset_signatures: Dict[str, ResetSignature] = {}
        self.state_path = Path(state_path) if state_path else None
        self.execution_control = execution_control
        self.authorization_verifier = authorization_verifier
        self.control_actions: Dict[str, str] = {}
        self._load_state()

    def _load_state(self) -> None:
        if self.state_path is None or not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.state = KillSwitchState(payload["state"])
            self.consecutive_rejections = int(payload.get("consecutive_rejections", 0))
            self.active_trigger_reason = payload.get("active_trigger_reason")
            self.trip_timestamp_utc = payload.get("trip_timestamp_utc")
            self.control_actions = dict(payload.get("control_actions", {}))
            self.reset_signatures = {
                item["role"]: ResetSignature(**item)
                for item in payload.get("reset_signatures", [])
            }
        except (OSError, ValueError, KeyError) as exc:
            self.state = KillSwitchState.TRIPPED_AUTO
            self.active_trigger_reason = f"[STATE_INVALID] Kill-switch state could not be restored: {exc}"

    def _persist_state(self) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "state": self.state.value,
            "consecutive_rejections": self.consecutive_rejections,
            "active_trigger_reason": self.active_trigger_reason,
            "trip_timestamp_utc": self.trip_timestamp_utc,
            "control_actions": self.control_actions,
            "reset_signatures": [signature.__dict__ for signature in self.reset_signatures.values()],
        }
        temp_path = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        temp_path.replace(self.state_path)

    @property
    def is_locked(self) -> bool:
        """Indicates whether the trading engine is actively halted."""
        return self.state != KillSwitchState.ARMED_NOMINAL

    def record_order_success(self):
        """Resets the consecutive rejection counter when an order executes normally."""
        if self.consecutive_rejections > 0:
            logging.info(
                f"Order executed successfully. Clearing previous {self.consecutive_rejections} rejections."
            )
            self.consecutive_rejections = 0

    def record_order_rejection(self, reason: str) -> bool:
        """
        Increments rejection tally and trips the circuit breaker if the threshold is met.
        Returns True if the kill switch was engaged.
        """
        if self.is_locked:
            return True

        self.consecutive_rejections += 1
        logging.warning(
            f"Broker rejection recorded ({self.consecutive_rejections}/{self.rejection_threshold}): {reason}"
        )

        if self.consecutive_rejections >= self.rejection_threshold:
            self.trip(
                trigger=TripTriggerType.CONSECUTIVE_REJECTIONS,
                reason=f"Exceeded rejection threshold ({self.consecutive_rejections} consecutive failures): {reason}"
            )
            return True
        return False

    def trip(self, trigger: TripTriggerType, reason: str):
        """Engages the emergency kill switch and suspends all downstream pipelines."""
        self.state = (
            KillSwitchState.ENGAGED_MANUAL
            if trigger == TripTriggerType.MANUAL_OPERATOR_OVERRIDE
            else KillSwitchState.TRIPPED_AUTO
        )
        self.active_trigger_reason = f"[{trigger.value}] {reason}"
        self.trip_timestamp_utc = datetime.now(timezone.utc).isoformat()
        self.reset_signatures.clear()

        self.control_actions = {}
        if self.execution_control is not None:
            for action_name, action in (
                ("cancel_open_orders", self.execution_control.cancel_all_open_orders),
                ("reconcile_positions", self.execution_control.reconcile_positions),
            ):
                try:
                    action()
                    self.control_actions[action_name] = "COMPLETED"
                except Exception as exc:
                    self.control_actions[action_name] = f"FAILED: {exc}"
        
        logging.critical(
            f"!!! KILL SWITCH TRIPPED !!! -> Trading and AP publications HALTED. Reason: {self.active_trigger_reason}"
        )
        self._persist_state()

    def submit_reset_authorization(
        self,
        signor_id: str,
        role: str,
        justification: str
    ) -> KillSwitchTelemetry:
        """
        Submits an authorized signature to unlock the engine. Requires dual-role agreement.
        """
        if not self.is_locked:
            logging.info("Reset ignored: Kill switch is currently nominal.")
            return self.get_telemetry()

        if self.authorization_verifier is None or not self.authorization_verifier(signor_id, role, justification):
            raise PermissionError("Authenticated restart authorization is required to reset the kill switch.")

        if role not in self.authorized_roles:
            raise PermissionError(
                f"Role '{role}' is not authorized to reset the emergency kill switch. "
                f"Required roles: {', '.join(self.authorized_roles)}"
            )

        if role in self.reset_signatures:
            logging.warning(f"Role '{role}' has already submitted a signature for this unlock cycle.")
            return self.get_telemetry()

        now_utc = datetime.now(timezone.utc).isoformat()
        sig_raw = f"{signor_id}:{role}:{now_utc}:{justification}"
        sig_hash = hashlib.sha256(sig_raw.encode("utf-8")).hexdigest()[:16]

        sig = ResetSignature(
            signor_id=signor_id,
            role=role,
            timestamp_utc=now_utc,
            justification=justification,
            signature_hash=sig_hash
        )
        self.reset_signatures[role] = sig
        logging.info(
            f"Reset signature accepted from {signor_id} ({role}). Total signatures: "
            f"{len(self.reset_signatures)}/{self.required_signers_count}"
        )

        if len(self.reset_signatures) >= self.required_signers_count:
            self._disengage_lock()
        else:
            self.state = KillSwitchState.AWAITING_DUAL_AUTH
            self._persist_state()

        return self.get_telemetry()

    def _disengage_lock(self):
        """Restores the kill switch to nominal operations once dual sign-off is satisfied."""
        logging.info("Dual authorization requirements fulfilled. Resetting kill switch to ARMED_NOMINAL.")
        self.state = KillSwitchState.ARMED_NOMINAL
        self.active_trigger_reason = None
        self.trip_timestamp_utc = None
        self.consecutive_rejections = 0
        self.reset_signatures.clear()
        self._persist_state()

    def get_telemetry(self) -> KillSwitchTelemetry:
        """Returns structured status telemetry for console dashboards and health checks."""
        return KillSwitchTelemetry(
            state=self.state,
            is_trading_halted=self.is_locked,
            rejection_count=self.consecutive_rejections,
            rejection_threshold=self.rejection_threshold,
            active_trigger_reason=self.active_trigger_reason,
            trip_timestamp_utc=self.trip_timestamp_utc,
            signatures_collected=list(self.reset_signatures.values())
        )


__all__ = [
    "KillSwitchState",
    "TripTriggerType",
    "ResetSignature",
    "KillSwitchTelemetry",
    "EmergencyKillSwitchEngine",
    "ExecutionControl",
]
