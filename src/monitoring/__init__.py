# src/monitoring/__init__.py
"""
EDGE-TF Disclosure Agent Engine - Monitoring, Telemetry, and Alerting Module.

Provides real-time telemetry streaming, tracking error calculations,
broker execution health diagnostics, and terminal console monitoring surfaces.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class SystemHealthLevel(str, Enum):
    NOMINAL = "NOMINAL"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class AlertNotification:
    alert_id: str
    severity: AlertSeverity
    source_module: str
    message: str
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class TelemetryFrame:
    timestamp_utc: str
    health_level: SystemHealthLevel
    active_broker_state: str
    kill_switch_locked: bool
    nav_usd: float
    settled_cash_usd: float
    tracking_error_bps: float
    relative_var: float
    subchapter_m_passed: bool
    open_orders_count: int
    pending_approvals_count: int
    alerts: List[AlertNotification] = field(default_factory=list)


class SystemHealthMonitor:
    """
    Central operational watchdog aggregating heartbeat signals,
    gateway connectivity states, and regulatory threshold metrics.
    """

    def __init__(self, tracking_error_alert_bps: float = 25.0):
        self.tracking_error_threshold_bps = tracking_error_alert_bps
        self.alert_history: List[AlertNotification] = []

    def evaluate_health(
        self,
        broker_connected: bool,
        kill_switch_locked: bool,
        statutory_gates_passed: bool,
        tracking_error_bps: float,
    ) -> SystemHealthLevel:
        """Determines overarching operational status across subsystems."""
        if kill_switch_locked or not statutory_gates_passed:
            return SystemHealthLevel.CRITICAL

        if not broker_connected or tracking_error_bps > self.tracking_error_threshold_bps:
            return SystemHealthLevel.DEGRADED

        return SystemHealthLevel.NOMINAL

    def record_alert(
        self,
        severity: AlertSeverity,
        source_module: str,
        message: str
    ) -> AlertNotification:
        """Logs and retains real-time operational notifications."""
        alert_id = f"ALT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')[:17]}"
        alert = AlertNotification(
            alert_id=alert_id,
            severity=severity,
            source_module=source_module,
            message=message
        )
        self.alert_history.append(alert)
        log_fn = logging.info
        if severity == AlertSeverity.WARNING:
            log_fn = logging.warning
        elif severity in (AlertSeverity.ERROR, AlertSeverity.CRITICAL):
            log_fn = logging.critical
        log_fn(f"[{severity.value}] [{source_module}] {message}")
        return alert


__all__ = [
    "SystemHealthLevel",
    "AlertSeverity",
    "AlertNotification",
    "TelemetryFrame",
    "SystemHealthMonitor",
]# monitoring package
