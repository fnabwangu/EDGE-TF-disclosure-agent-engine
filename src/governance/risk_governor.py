"""risk_governor.py
Hard sizing constraints placeholder.
"""

def check_single_stock_limit(position_pct: float, max_pct: float = 0.15) -> bool:
    return position_pct <= max_pct
# src/governance/risk_governor.py
"""
EDGE-TF Disclosure Agent Engine - Comprehensive Risk Governor.

Coordinates pre-trade statutory compliance, regulatory derivatives limits (SEC Rule 18f-4),
liquidity mandates (SEC Rule 22e-4), Names Rule enforcement (SEC Rule 35d-1),
and emergency circuit-breaker interactions before order release.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.governance.audit_logger import AuditEventType, AuditLogger
from risk.deterministic_execution_gate import (
    DeterministicExecutionGate,
    GateAuditReport,
    GateVerdict,
)
from risk.kill_switch import (
    EmergencyKillSwitchEngine,
    KillSwitchState,
    TripTriggerType,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@dataclass
class PreTradeAuditSummary:
    passed: bool
    timestamp_utc: str
    target_weights: Dict[str, float]
    gate_report: GateAuditReport
    kill_switch_state: KillSwitchState
    violations: List[str]
    audit_record_id: Optional[str] = None


class RiskGovernor:
    """
    Central orchestration engine for risk governance, statutory rule checks,
    and fail-safe validation across the ETF order pipeline.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        audit_logger: Optional[AuditLogger] = None,
        kill_switch: Optional[EmergencyKillSwitchEngine] = None,
    ):
        self.audit_logger = audit_logger or AuditLogger()
        self.kill_switch = kill_switch or EmergencyKillSwitchEngine()
        self.config = self._load_risk_parameters(config_path)
        self.config_valid = bool(self.config.get("_config_valid", False))
        self.config_error = self.config.get("_config_error")

        self.gate_engine = DeterministicExecutionGate(
            subchapter_m_single_cap=self.config.get("subchapter_m_single_issuer_cap", 0.25),
            subchapter_m_aggregate_cap=self.config.get("subchapter_m_aggregate_cap", 0.50),
            subchapter_m_concentrated_threshold=self.config.get("subchapter_m_concentrated_threshold", 0.05),
            sec_18f4_relative_var_limit=self.config.get("rule_18f4_relative_var_limit", 2.00),
            sec_22e4_illiquid_cap=self.config.get("rule_22e4_illiquid_cap", 0.15),
            sec_35d1_names_rule_floor=self.config.get("rule_35d1_names_rule_floor", 0.80),
        )

    def _load_risk_parameters(self, config_path: Optional[Path]) -> Dict[str, Any]:
        """Load policy configuration; malformed policy is a hard no-trade state."""
        default_config = {
            "subchapter_m_single_issuer_cap": 0.25,
            "subchapter_m_aggregate_cap": 0.50,
            "subchapter_m_concentrated_threshold": 0.05,
            "rule_18f4_relative_var_limit": 2.00,
            "rule_22e4_illiquid_cap": 0.15,
            "rule_35d1_names_rule_floor": 0.80,
            "max_portfolio_drawdown_limit": 0.15,
            "max_single_order_pct_aum": 0.05,
        }

        path = config_path or Path("config/risk_parameters.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                raise ValueError("configuration root must be an object")
            default_config.update(loaded)
            default_config["_config_valid"] = True
            logging.info(f"Loaded risk governance parameters from {path}")
            return default_config
        except Exception as exc:
            error = f"CONFIG_INVALID: failed to load risk config from {path}: {exc}"
            logging.critical(error)
            default_config["_config_valid"] = False
            default_config["_config_error"] = error
            return default_config

    def evaluate_pre_trade_compliance(
        self,
        target_weights: Dict[str, float],
        relative_var: float,
        illiquid_weight: float,
        mandate_aligned_weight: float,
        current_drawdown: float = 0.0,
        operator_id: str = "SYSTEM_RISK_GOVERNOR",
        role: str = "CHIEF_COMPLIANCE_OFFICER",
    ) -> PreTradeAuditSummary:
        """
        Executes a pre-trade audit against statutory gates and circuit-breaker states.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        violations: List[str] = []

        if not self.config_valid:
            violation = self.config_error or "CONFIG_INVALID: risk policy is unavailable"
            self.kill_switch.trip(TripTriggerType.STATUTORY_BREACH, violation)
            gate_report = GateAuditReport(
                passed_all_gates=False,
                total_violations=1,
                evaluations=[],
            )
            violations.append(violation)
            audit_record = self.audit_logger.log_event(
                event_type=AuditEventType.PRE_TRADE_COMPLIANCE,
                operator_id=operator_id,
                role=role,
                payload={"passed": False, "system_state": "NO_TRADE_PERMISSIBLE", "violations": violations},
            )
            return PreTradeAuditSummary(
                passed=False,
                timestamp_utc=now_utc,
                target_weights=target_weights,
                gate_report=gate_report,
                kill_switch_state=self.kill_switch.state,
                violations=violations,
                audit_record_id=audit_record.record_id,
            )

        # 1. Evaluate circuit breaker and active lockdown status
        if self.kill_switch.is_locked:
            violations.append(f"Emergency Kill Switch Active: {self.kill_switch.active_trigger_reason}")

        # 2. Check maximum drawdown limits against risk config
        max_dd = self.config.get("max_portfolio_drawdown_limit", 0.15)
        if current_drawdown > max_dd:
            dd_msg = f"Current portfolio drawdown ({current_drawdown:.2%}) exceeds risk cap ({max_dd:.2%})."
            violations.append(dd_msg)
            self.kill_switch.trip(TripTriggerType.DRAWDOWN_LIMIT, dd_msg)

        # 3. Execute deterministic statutory gate sweeps
        gate_report = self.gate_engine.execute_all_gates(
            target_weights=target_weights,
            relative_var=relative_var,
            illiquid_weight=illiquid_weight,
            mandate_aligned_weight=mandate_aligned_weight,
        )

        for evaluation in gate_report.evaluations:
            if evaluation.verdict == GateVerdict.FAIL:
                violations.append(f"[{evaluation.rule_id}] {evaluation.rule_name}: {evaluation.details}")

        # Trip kill switch automatically on statutory breaches
        if not gate_report.passed_all_gates:
            self.kill_switch.trip(
                TripTriggerType.STATUTORY_BREACH,
                f"Pre-trade audit failed with {gate_report.total_violations} regulatory violations."
            )

        passed_all = len(violations) == 0 and not self.kill_switch.is_locked

        audit_payload = {
            "passed": passed_all,
            "target_weights": target_weights,
            "metrics": {
                "relative_var": relative_var,
                "illiquid_weight": illiquid_weight,
                "mandate_aligned_weight": mandate_aligned_weight,
                "current_drawdown": current_drawdown,
            },
            "gate_report": [
                {
                    "rule_id": e.rule_id,
                    "verdict": e.verdict.value,
                    "metric": e.metric_value,
                    "limit": e.threshold_limit,
                    "details": e.details,
                }
                for e in gate_report.evaluations
            ],
            "violations": violations,
        }

        # 4. Log to immutable WORM audit repository
        audit_record = self.audit_logger.log_event(
            event_type=AuditEventType.PRE_TRADE_COMPLIANCE,
            operator_id=operator_id,
            role=role,
            payload=audit_payload,
        )

        return PreTradeAuditSummary(
            passed=passed_all,
            timestamp_utc=now_utc,
            target_weights=target_weights,
            gate_report=gate_report,
            kill_switch_state=self.kill_switch.state,
            violations=violations,
            audit_record_id=audit_record.record_id,
        )


__all__ = [
    "PreTradeAuditSummary",
    "RiskGovernor",
]
