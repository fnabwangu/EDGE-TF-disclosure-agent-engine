"""
EDGE-TF Risk Management Module

Centralized execution gates, risk controls, and emergency circuit breakers for trade compliance.
"""

from .deterministic_execution_gate import (
    DeterministicExecutionGate,
    GateVerdict,
    RuleEvaluationResult,
    GateAuditReport,
    evaluate_deterministic_gates,
)
from .kill_switch import (
    EmergencyKillSwitchEngine,
    KillSwitchState,
    TripTriggerType,
    ResetSignature,
    KillSwitchTelemetry,
)
from .risk_governor import RiskGovernor, PreTradeAuditSummary
from .exposure_reduction_engine import ExposureReductionEngine, ExposureReductionResult

__all__ = [
    "DeterministicExecutionGate",
    "GateVerdict",
    "RuleEvaluationResult",
    "GateAuditReport",
    "evaluate_deterministic_gates",
    "EmergencyKillSwitchEngine",
    "KillSwitchState",
    "TripTriggerType",
    "ResetSignature",
    "KillSwitchTelemetry",
    "RiskGovernor",
    "PreTradeAuditSummary",
    "ExposureReductionEngine",
    "ExposureReductionResult",
]

