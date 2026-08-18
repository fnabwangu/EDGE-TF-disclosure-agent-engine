import json

import pandas as pd
import pytest

from risk.risk_governor import RiskGovernor
from normalization.normalizer import DisclosureNormalizer


VALID_RISK_CONFIG = {
    "subchapter_m_single_issuer_cap": 0.25,
    "subchapter_m_aggregate_cap": 0.50,
    "subchapter_m_concentrated_threshold": 0.05,
    "rule_18f4_relative_var_limit": 2.0,
    "rule_22e4_illiquid_cap": 0.15,
    "rule_35d1_names_rule_floor": 0.80,
    "max_portfolio_drawdown_limit": 0.15,
    "max_single_order_pct_aum": 0.05,
}


def test_invalid_risk_config_fails_closed(tmp_path):
    config_path = tmp_path / "risk.json"
    config_path.write_text("not-json", encoding="utf-8")
    governor = RiskGovernor(config_path=config_path)

    result = governor.evaluate_pre_trade_compliance({}, 0.0, 0.0, 1.0)

    assert result.passed is False
    assert governor.config_valid is False
    assert any("CONFIG_INVALID" in violation for violation in result.violations)
    assert governor.kill_switch.is_locked is True


def test_valid_risk_config_can_reach_gate_evaluation(tmp_path):
    config_path = tmp_path / "risk.json"
    config_path.write_text(json.dumps(VALID_RISK_CONFIG), encoding="utf-8")
    governor = RiskGovernor(config_path=config_path)

    result = governor.evaluate_pre_trade_compliance({"XYZ": 0.10}, 1.0, 0.05, 0.90)

    assert governor.config_valid is True
    assert all("CONFIG_INVALID" not in violation for violation in result.violations)
    assert result.gate_report.total_violations == 0


def test_missing_etf_denominator_blocks_normalization():
    frame = pd.DataFrame({"shares_held": [100.0]})
    with pytest.raises(ValueError, match="NORMALIZATION_BLOCKED"):
        DisclosureNormalizer().compute_flow_normalized_units(frame)


def test_invalid_etf_denominator_blocks_normalization():
    frame = pd.DataFrame({"shares_held": [100.0], "etf_shares_outstanding": [0.0]})
    with pytest.raises(ValueError, match="NORMALIZATION_BLOCKED"):
        DisclosureNormalizer().compute_flow_normalized_units(frame)
