from risk.deterministic_gates import (
    DeterministicExecutionGate,
    GateVerdict,
    evaluate_deterministic_gates,
)


def test_execution_gate_accepts_valid_market_data():
    gate = DeterministicExecutionGate(min_zscore=1.96, min_diffusion=0.01, max_spread_pct=0.02)
    passed, reason = gate.verify_order(2.0, 0.10, 99.5, 100.0)
    assert passed is True
    assert reason == "ACCEPTED"


def test_execution_gate_rejects_invalid_signal():
    gate = DeterministicExecutionGate()
    passed, reason = gate.verify_order(1.0, 0.10, 99.5, 100.0)
    assert passed is False
    assert "Z-score" in reason


def test_statutory_gate_report_has_hard_failures():
    gate = DeterministicExecutionGate()
    report = gate.execute_all_gates({"XYZ": 0.30}, 2.0, 0.05, 0.90)
    assert report.passed_all_gates is False
    assert report.total_violations >= 1
    assert any(item.verdict == GateVerdict.FAIL for item in report.evaluations)


def test_boolean_gate_wrapper_is_fail_closed():
    result = evaluate_deterministic_gates(True, False, True)
    assert result["execution_permitted"] is False
    assert result["system_state"] == "NO_TRADE_PERMISSIBLE"
