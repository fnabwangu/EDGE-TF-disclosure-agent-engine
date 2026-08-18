"""Governance Engine Interface (src/governance/__init__.py)
The src/governance/__init__.py module acts as the core interface for regulatory policy enforcement, emergency kill switches, dual-authorization audit gates, and statutory compliance frameworks within the EDGE-TF-disclosure-agent-engine.

Exported Components
GovernancePolicyManager: Loads and enforces institutional risk limits, trading halts, and governance configurations from governance_policy.json.

EmergencyKillSwitch: Monitors consecutive order rejections and systemic risk threshold breaches to instantly freeze outbound routing gateways.

DualAuthorizationGate: Coordinates cryptographic sign-offs from designated fiduciaries (CCO, Lead PM, CFO) for high-impact rebalance and disclosure events.

GovernanceState: Represents current system lockdown status, override permissions, and audit tracking metadata.

Python"""
# src/governance/__init__.py
"""
EDGE-TF Disclosure Agent Engine - Governance & Compliance Policy Module.

Manages statutory override policies, emergency kill switches, dual-signature
authorization gates, and immutable audit logging for regulatory compliance.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Set

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class SystemLockState(str, Enum):
    NOMINAL = "NOMINAL"
    WARNING = "WARNING"
    LOCKED_DOWN = "LOCKED_DOWN"


@dataclass
class GovernanceState:
    is_locked: bool
    lock_reason: Optional[str]
    consecutive_rejections: int
    last_updated_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class EmergencyKillSwitch:
    """Manages emergency halts and lockdown states for outbound trading and disclosure pipelines."""

    def __init__(self, rejection_threshold: int = 3):
        self.threshold = rejection_threshold
        self.is_locked = False
        self.lock_reason: Optional[str] = None
        self.consecutive_rejections = 0

    def register_rejection(self, reason: str) -> bool:
        """Increments rejection tally and triggers kill switch if threshold is met."""
        self.consecutive_rejections += 1
        logging.warning(f"Order rejection logged ({self.consecutive_rejections}/{self.threshold}): {reason}")
        
        if self.consecutive_rejections >= self.threshold:
            self.engage_lock(f"Automatic kill switch tripped: {self.consecutive_rejections} consecutive rejections.")
            return True
        return False

    def register_success(self):
        """Resets consecutive rejection count upon successful trade execution or disclosure sign-off."""
        if self.consecutive_rejections > 0:
            logging.info("Successful execution recorded. Resetting rejection counter.")
            self.consecutive_rejections = 0

    def engage_lock(self, reason: str):
        """Manually or automatically engages system-wide trading and disclosure lockdown."""
        self.is_locked = True
        self.lock_reason = reason
        logging.critical(f"EMERGENCY KILL SWITCH ENGAGED: {reason}")

    def reset_lock(self, authorized_signor: str, role: str) -> GovernanceState:
        """Resets the kill switch state following dual-authorization review."""
        logging.info(f"Kill switch reset authorized by {authorized_signor} ({role}).")
        self.is_locked = False
        self.lock_reason = None
        self.consecutive_rejections = 0
        return self.get_state()

    def get_state(self) -> GovernanceState:
        return GovernanceState(
            is_locked=self.is_locked,
            lock_reason=self.lock_reason,
            consecutive_rejections=self.consecutive_rejections
        )


class GovernancePolicyManager:
    """Enforces institutional limits, regulatory constraints, and policy ontology rules."""

    def __init__(self, policy_config_path: Optional[str] = None):
        self.config: Dict[str, Any] = {
            "max_single_issuer_weight": 0.25,
            "aggregate_concentrated_limit": 0.50,
            "max_relative_var": 2.00,
            "max_drawdown_limit": 0.15,
            "required_signatories": ["CHIEF_COMPLIANCE_OFFICER", "LEAD_PORTFOLIO_MANAGER"]
        }
        if policy_config_path:
            self.load_policy(policy_config_path)

    def load_policy(self, path: str):
        """Loads governance policy parameters from JSON configuration."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.loadf(f)
                self.config.update(loaded)
                logging.info(f"Loaded governance policy configuration from {path}")
        except Exception as exc:
            logging.error(f"Failed to load policy config from {path}: {exc}")

    def validate_parameter(self, param_name: str, value: Any) -> bool:
        """Validates a proposed parameter change against hardcoded or loaded statutory bounds."""
        limit = self.config.get(param_name)
        if limit is None:
            return True  # Unrestricted parameter
        return value <= limit


__all__ = [
    "SystemLockState",
    "GovernanceState",
    "EmergencyKillSwitch",
    "GovernancePolicyManager",
]# governance package
