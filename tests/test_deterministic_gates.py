from risk.deterministic_execution_gate import GateVerdict


def test_ev_gate():
    assert ev_gate(0.8, 0.7)
    assert not ev_gate(0.5, 0.7)
========================================================================================
MODULE: Deterministic Gates Test Suite (tests/test_deterministic_gates.py)
PURPOSE: Verify deterministic pre-execution risk boundaries, boolean state transitions, 
         and the strict enforcement of the NO_TRADE_PERMISSIBLE governance state[cite: 1].
========================================================================================

INPUT:
    - Risk parameters configuration (max delta, max single-position weight, liquidity floors)[cite: 1].
    - Simulated candidate trade payloads (valid vs. limit-breaching scenarios)[cite: 1].
    - Pipeline telemetry states (data freshness, falsification pass/fail status, kill-switch triggers)[cite: 1].

STEP 1: POSITION CONCENTRATION & DELTA BOUND TESTS
    TEST that candidate trades exceeding max_single_position_pct (e.g., > 15%) are rejected by the Risk Governor[cite: 1].
    TEST that candidate structures exceeding max_portfolio_delta (e.g., > 0.85) trigger explicit delta budget violations[cite: 1].

STEP 2: ADVERSARIAL DISCONFIRMATION GATE TESTS
    TEST that signals failing manager breadth (e.g., < 2 independent clusters) or Herfindahl limits (HHI > 0.65) trigger disconfirmation rejection[cite: 1].
    TEST that signals coinciding with scheduled index rebalance windows are flagged as rebalance noise[cite: 1].

STEP 3: NO_TRADE_PERMISSIBLE STATE ENFORCEMENT
    VERIFY that evaluate_deterministic_gates() returns:
        * system_state = "NO_TRADE_PERMISSIBLE" AND execution_permitted = False
        whenever ANY single validation gate (data quality, falsification, risk approval) fails[cite: 1].
    VERIFY that system_state = "TRADE_DISPATCH_PERMISSIBLE" ONLY when all gates evaluate to True[cite: 1].

STEP 4: EMERGENCY KILL-SWITCH & CIRCUIT BREAKER TESTS
    TEST that tripping the kill-switch immediately halts execution permissions across all subsequent checks[cite: 1].

STEP 5: AUDIT LOGGING & POINT-IN-TIME HASH INTEGRITY
    VERIFY that the audit logger produces valid SHA-256 hashes matching payload serialization for immutable decision records[cite: 1].

OUTPUT:
    - Test execution assertions verifying deterministic safety controls[cite: 1].
========================================================================================

"""
Edge-TF / Reverse Engineering Alpha Engine
Module: tests/test_deterministic_gates.py
Purpose: Unit and integration tests for deterministic risk boundaries,
         governance gates, and NO_TRADE_PERMISSIBLE state transitions.
"""

import hashlib
import json
import pytest

from risk.deterministic_execution_gate import GateVerdict, evaluate_deterministic_gates
from risk.risk_governor import RiskGovernor
from risk.kill_switch import EmergencyKillSwitchEngine
from src.governance.audit_logger import AuditLogger
from src.inference.falsification_pass import evaluate_adversarial_falsification


@pytest.fixture
def standard_risk_limits():
    return {
        "max_portfolio_delta": 0.85,
        "max_single_position_pct": 0.15,
        "min_underlying_adv_usd": 10000000.0,
        "min_options_open_interest": 500,
        "max_slippage_bps": 25,
        "enforce_no_trade_default": True
    }


# ==============================================================================
# 1. RISK GOVERNOR HARD-BOUND TESTS
# ==============================================================================

def test_risk_governor_approves_compliant_trade(standard_risk_limits):
    governor = RiskGovernor(standard_risk_limits)
    candidate_trade = {
        "symbol": "IOT",
        "weight": 0.10,
        "delta": 0.70,
        "adv_usd": 15000000.0
    }
    result = governor.audit_trade(candidate_trade)
    assert result["status"] == "APPROVED"
    assert len(result["violations"]) == 0


def test_risk_governor_rejects_excess_weight(standard_risk_limits):
    governor = RiskGovernor(standard_risk_limits)
    candidate_trade = {
        "symbol": "IOT",
        "weight": 0.22,  # Limit is 0.15
        "delta": 0.70
    }
    result = governor.audit_trade(candidate_trade)
    assert result["status"] == "REJECTED"
    assert "WEIGHT_EXCEEDS_SINGLE_POSITION_LIMIT" in result["violations"]


def test_risk_governor_rejects_excess_delta(standard_risk_limits):
    governor = RiskGovernor(standard_risk_limits)
    candidate_trade = {
        "symbol": "IOT",
        "weight": 0.10,
        "delta": 0.95  # Limit is 0.85
    }
    result = governor.audit_trade(candidate_trade)
    assert result["status"] == "REJECTED"
    assert "DELTA_EXCEEDS_MAX_BUDGET" in result["violations"]


# ==============================================================================
# 2. ADVERSARIAL FALSIFICATION GATE TESTS
# ==============================================================================

def test_falsification_pass_valid_candidate():
    verdict = evaluate_adversarial_falsification(
        security_id="SEC_VALID",
        breadth=3,
        manager_hhi=0.25,
        is_rebalance_window=False
    )
    assert verdict["falsification_passed"] is True
    assert len(verdict["rejection_reasons"]) == 0


def test_falsification_pass_kills_rebalance_noise():
    verdict = evaluate_adversarial_falsification(
        security_id="SEC_REBAL",
        breadth=4,
        manager_hhi=0.20,
        is_rebalance_window=True
    )
    assert verdict["falsification_passed"] is False
    assert "COINCIDES_WITH_SCHEDULED_INDEX_REBALANCE" in verdict["rejection_reasons"]


def test_falsification_pass_kills_single_manager_cluster():
    verdict = evaluate_adversarial_falsification(
        security_id="SEC_CONCENTRATED",
        breadth=1,  # Fails minimum breadth >= 2
        manager_hhi=0.85,  # Exceeds HHI limit 0.65
        is_rebalance_window=False
    )
    assert verdict["falsification_passed"] is False
    assert "INSUFFICIENT_INDEPENDENT_MANAGER_BREADTH" in verdict["rejection_reasons"]
    assert "EXCESSIVE_MANAGER_CLUSTER_CONCENTRATION" in verdict["rejection_reasons"]


# ==============================================================================
# 3. DETERMINISTIC GATES & NO_TRADE_PERMISSIBLE ENFORCEMENT
# ==============================================================================

def test_deterministic_gates_all_pass():
    gate_eval = evaluate_deterministic_gates(
        data_quality_ok=True,
        falsification_passed=True,
        governor_approved=True
    )
    assert gate_eval["execution_permitted"] is True
    assert gate_eval["system_state"] == "TRADE_DISPATCH_PERMISSIBLE"


@pytest.mark.parametrize(
    "dq_ok, falsify_ok, gov_ok",
    [
        (False, True, True),
        (True, False, True),
        (True, True, False),
        (False, False, False),
    ]
)
def test_deterministic_gates_enforce_no_trade(dq_ok, falsify_ok, gov_ok):
    gate_eval = evaluate_deterministic_gates(
        data_quality_ok=dq_ok,
        falsification_passed=falsify_ok,
        governor_approved=gov_ok
    )
    assert gate_eval["execution_permitted"] is False
    assert gate_eval["system_state"] == "NO_TRADE_PERMISSIBLE"


# ==============================================================================
# 4. EMERGENCY KILL-SWITCH CIRCUIT BREAKER TESTS
# ==============================================================================

def test_kill_switch_lifecycle():
    kill_switch = EmergencyKillSwitchEngine()
    assert kill_switch.is_locked is False

    from risk.kill_switch import TripTriggerType
    kill_switch.trip(TripTriggerType.DATA_STALENESS, "DATA_CORRUPTION_FLAG_TRIPPED")
    assert kill_switch.is_locked is True


# ==============================================================================
# 5. AUDIT LOGGER POINT-IN-TIME HASH INTEGRITY
# ==============================================================================

def test_audit_logger_hash_verification():
    decision_payload = {
        "trade_id": "TRD-TEST-001",
        "symbol": "IOT",
        "action": "BUY_TO_OPEN",
        "target_delta": 0.70
    }
    raw_log = AuditLogger.log_decision_record(decision_payload)
    parsed_record = json.loads(raw_log)

    assert "sha256" in parsed_record
    assert "timestamp" in parsed_record

    # Verify cryptographic reproducibility
    expected_hash = hashlib.sha256(
        json.dumps(decision_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert parsed_record["sha256"] == expected_hash
