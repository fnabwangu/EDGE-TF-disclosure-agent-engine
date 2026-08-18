import json
from pathlib import Path

import pytest

from core.config_validation import load_config, validate_config_directory


CONFIG_DIR = Path(__file__).parents[1] / "config"


def test_all_root_configs_are_valid_json_and_schema_compliant():
    configs = validate_config_directory(CONFIG_DIR)
    assert set(configs) == {
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
