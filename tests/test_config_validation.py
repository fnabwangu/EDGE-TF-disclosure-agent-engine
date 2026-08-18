import json
from pathlib import Path

import pytest

from core.config_validation import load_config, validate_config_directory


CONFIG_DIR = Path(__file__).parents[1] / "config"


def test_all_root_configs_are_valid_json_and_schema_compliant():
    configs = validate_config_directory(CONFIG_DIR)
    assert set(configs) == {
        "conviction_policy.json",
        "data_sources.json",
        "execution_routing.json",
        "fund_universe.json",
        "governance_policy.json",
        "rebalance_schedule.json",
        "risk_parameters.json",
        "strategy_ontology.json",
    }


def test_invalid_json_is_rejected(tmp_path):
    path = tmp_path / "risk_parameters.json"
    path.write_text("documentation, not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_config(path)


def test_missing_required_config_section_is_rejected(tmp_path):
    path = tmp_path / "risk_parameters.json"
    path.write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema invalid"):
        load_config(path)


def test_risk_numeric_bounds_are_enforced(tmp_path):
    path = tmp_path / "risk_parameters.json"
    path.write_text(json.dumps({
        "version": "1.0.0",
        "subchapter_m_single_issuer_cap": 0.25,
        "subchapter_m_aggregate_cap": 0.50,
        "subchapter_m_concentrated_threshold": 0.05,
        "rule_18f4_relative_var_limit": 2.0,
        "rule_22e4_illiquid_cap": 0.15,
        "rule_35d1_names_rule_floor": 0.80,
        "max_portfolio_drawdown_limit": 1.5,
        "max_single_order_pct_aum": 0.05,
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="max_portfolio_drawdown_limit"):
        load_config(path)


def test_nested_enum_and_extra_keys_are_rejected(tmp_path):
    path = tmp_path / "execution_routing.json"
    path.write_text(json.dumps({
        "version": "1.0.0",
        "environment_connectivity": {
            "environment": "unknown",
            "oms_protocol": "REST_API",
            "primary_broker_endpoint": "https://broker",
            "backup_broker_endpoint": "",
            "session_credentials_vault_key": "VAULT/KEY",
            "timeout_seconds": 15,
        },
        "algorithmic_execution_models": {"default_algo_strategy": "VWAP", "max_participation_rate_pct": 0.1, "urgency_level": "MEDIUM"},
        "slippage_and_tca_parameters": {"max_allowable_slippage_bps": 25, "pre_trade_tca_model": "SQUARE_ROOT_IMPACT", "target_tca_benchmark": "ARRIVAL_PRICE"},
        "custodian_and_ap_reporting": {"custodian_sftp_endpoint": "", "ap_pcfr_reporting_endpoint": "", "reporting_format": "CSV_EOD"},
        "unexpected": True,
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="environment|unexpected"):
        load_config(path)
