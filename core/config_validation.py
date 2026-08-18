"""Runtime JSON and JSON Schema validation for root configuration files."""

from pathlib import Path
import json
from typing import Any, Dict, Mapping

from jsonschema import Draft202012Validator


CONFIG_SCHEMAS: Mapping[str, Dict[str, Any]] = {
    "data_sources.json": {"required": ["version", "provider_hierarchy", "rate_limits_and_concurrency", "caching_and_freshness", "data_sanity_checks"]},
    "execution_routing.json": {"required": ["version", "environment_connectivity", "algorithmic_execution_models", "slippage_and_tca_parameters", "custodian_and_ap_reporting"]},
    "fund_universe.json": {"type": "object"},
    "governance_policy.json": {"required": ["version", "fund_identity_and_mandate", "prohibited_transactions", "liquidity_and_redemption_governance", "human_oversight_and_kill_switches"]},
    "rebalance_schedule.json": {"required": ["version", "schedule_regime", "execution_windows", "turnover_controls", "events"]},
    "risk_parameters.json": {"required": ["version", "subchapter_m_single_issuer_cap", "subchapter_m_aggregate_cap", "subchapter_m_concentrated_threshold", "rule_18f4_relative_var_limit", "rule_22e4_illiquid_cap", "rule_35d1_names_rule_floor", "max_portfolio_drawdown_limit", "max_single_order_pct_aum"]},
    "strategy_ontology.json": {"required": ["version", "signal_taxonomy", "factor_weighting_matrix", "overlay_mechanics", "allocation_hierarchy"]},
}


def load_config(path: str | Path) -> Dict[str, Any]:
    """Load one configuration file as pure JSON and validate its structure."""
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise ValueError(f"Configuration root must be an object: {config_path}")
    schema = CONFIG_SCHEMAS.get(config_path.name, {"type": "object"})
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ValueError(f"Configuration schema invalid for {config_path}: {details}")
    return document


def validate_config_directory(config_dir: str | Path = "config") -> Dict[str, Dict[str, Any]]:
    """Load and validate every root JSON configuration deterministically."""
    directory = Path(config_dir)
    return {path.name: load_config(path) for path in sorted(directory.glob("*.json"))}


__all__ = ["CONFIG_SCHEMAS", "load_config", "validate_config_directory"]
