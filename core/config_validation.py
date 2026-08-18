"""Deep JSON Schema validation for the root configuration contracts."""

from pathlib import Path
import json
from typing import Any, Dict

from jsonschema import Draft202012Validator, FormatChecker

VERSION = {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"}
RATIO = {"type": "number", "minimum": 0.0, "maximum": 1.0}
POSITIVE = {"type": "number", "exclusiveMinimum": 0.0}
STRING = {"type": "string", "minLength": 1}


def object_schema(required, properties, additional=False):
    return {"type": "object", "required": required, "properties": properties, "additionalProperties": additional}


def simple_contract(required):
    return object_schema(required, {key: {} for key in required})


CONFIG_SCHEMAS = {
    "data_sources.json": object_schema(
        ["version", "provider_hierarchy", "rate_limits_and_concurrency", "caching_and_freshness", "data_sanity_checks"],
        {
            "version": VERSION,
            "provider_hierarchy": object_schema(["primary_feed", "fallback_feeds", "switch_to_fallback_on_error_count", "environment"], {"primary_feed": STRING, "fallback_feeds": {"type": "array", "items": STRING}, "switch_to_fallback_on_error_count": {"type": "integer", "minimum": 1}, "environment": {"enum": ["production", "staging", "paper"]}}),
            "rate_limits_and_concurrency": object_schema(["max_requests_per_minute", "retry_attempts", "backoff_factor", "max_concurrent_workers", "request_timeout_seconds"], {"max_requests_per_minute": {"type": "integer", "minimum": 1}, "retry_attempts": {"type": "integer", "minimum": 0}, "backoff_factor": POSITIVE, "max_concurrent_workers": {"type": "integer", "minimum": 1}, "request_timeout_seconds": POSITIVE}),
            "caching_and_freshness": object_schema(["enable_local_cache", "intraday_price_ttl_seconds", "eod_bars_ttl_seconds"], {"enable_local_cache": {"type": "boolean"}, "intraday_price_ttl_seconds": {"type": "integer", "minimum": 1}, "eod_bars_ttl_seconds": {"type": "integer", "minimum": 1}}),
            "data_sanity_checks": object_schema(["max_stale_data_seconds", "max_permitted_price_jump_pct", "zero_volume_rejection"], {"max_stale_data_seconds": {"type": "integer", "minimum": 1}, "max_permitted_price_jump_pct": {"type": "number", "minimum": 0}, "zero_volume_rejection": {"type": "boolean"}}),
        },
    ),
    "execution_routing.json": object_schema(
        ["version", "environment_connectivity", "algorithmic_execution_models", "slippage_and_tca_parameters", "custodian_and_ap_reporting"],
        {
            "version": VERSION,
            "environment_connectivity": object_schema(["environment", "oms_protocol", "primary_broker_endpoint", "backup_broker_endpoint", "session_credentials_vault_key", "timeout_seconds"], {"environment": {"enum": ["production", "staging_sandbox", "paper_trading"]}, "oms_protocol": {"enum": ["FIX_4_4", "REST_API", "GRPC"]}, "primary_broker_endpoint": {"type": "string"}, "backup_broker_endpoint": {"type": "string"}, "session_credentials_vault_key": STRING, "timeout_seconds": POSITIVE}),
            "algorithmic_execution_models": object_schema(["default_algo_strategy", "max_participation_rate_pct", "urgency_level"], {"default_algo_strategy": {"enum": ["TWAP", "VWAP", "POV", "MOC", "ARRIVAL_PRICE"]}, "max_participation_rate_pct": RATIO, "urgency_level": {"enum": ["LOW", "MEDIUM", "HIGH"]}}),
            "slippage_and_tca_parameters": object_schema(["max_allowable_slippage_bps", "pre_trade_tca_model", "target_tca_benchmark"], {"max_allowable_slippage_bps": {"type": "number", "minimum": 0}, "pre_trade_tca_model": {"enum": ["ALMGREN_CHRISS", "LINEAR_SPREAD", "SQUARE_ROOT_IMPACT"]}, "target_tca_benchmark": {"enum": ["ARRIVAL_PRICE", "VWAP_INTERVAL", "CLOSING_PRICE"]}}),
            "custodian_and_ap_reporting": object_schema(["custodian_sftp_endpoint", "ap_pcfr_reporting_endpoint", "reporting_format"], {"custodian_sftp_endpoint": {"type": "string"}, "ap_pcfr_reporting_endpoint": {"type": "string"}, "reporting_format": {"enum": ["SWIFT_MT515", "CSV_EOD", "FIX_CONFIRM"]}}),
        },
    ),
    "governance_policy.json": object_schema(["version", "max_single_stock_percent", "hitl_threshold", "fund_identity_and_mandate", "prohibited_transactions", "liquidity_and_redemption_governance", "human_oversight_and_kill_switches"], {"version": VERSION, "max_single_stock_percent": {"type": "number", "exclusiveMinimum": 0, "maximum": 100}, "hitl_threshold": RATIO, "fund_identity_and_mandate": object_schema(["fund_name", "fund_type", "regulatory_regime", "names_rule_min_policy_weight", "permitted_asset_classes"], {"fund_name": STRING, "fund_type": {"enum": ["ACTIVE_TRANSPARENT_ETF", "PASSIVE_INDEX_ETF", "SEMI_TRANSPARENT_ETF"]}, "regulatory_regime": STRING, "names_rule_min_policy_weight": RATIO, "permitted_asset_classes": {"type": "array", "minItems": 1, "items": STRING}}), "prohibited_transactions": object_schema(["allow_naked_options", "allow_illiquid_assets", "allow_unregistered_securities"], {key: {"type": "boolean"} for key in ["allow_naked_options", "allow_illiquid_assets", "allow_unregistered_securities"]}), "liquidity_and_redemption_governance": object_schema(["illiquid_investment_max_pct", "highly_liquid_investment_min_pct"], {"illiquid_investment_max_pct": RATIO, "highly_liquid_investment_min_pct": RATIO}), "human_oversight_and_kill_switches": object_schema(["manual_override_authority", "automated_kill_switch_enabled", "consecutive_rejection_threshold"], {"manual_override_authority": {"type": "array", "minItems": 1, "items": STRING}, "automated_kill_switch_enabled": {"type": "boolean"}, "consecutive_rejection_threshold": {"type": "integer", "minimum": 1}})}),
    "rebalance_schedule.json": object_schema(["version", "schedule_regime", "execution_windows", "turnover_controls", "events"], {"version": VERSION, "schedule_regime": object_schema(["frequency", "rebalance_day_of_week", "rebalance_day_of_month", "holiday_convention"], {"frequency": {"enum": ["daily", "weekly", "monthly", "quarterly"]}, "rebalance_day_of_week": {"type": ["string", "null"]}, "rebalance_day_of_month": {"type": ["integer", "null"], "minimum": -31, "maximum": 31}, "holiday_convention": {"enum": ["MODIFIED_FOLLOWING", "PRECEDING", "FOLLOWING"]}}), "execution_windows": object_schema(["market_timezone", "order_generation_time", "execution_open_time", "execution_cutoff_time", "allow_moc_orders"], {"market_timezone": STRING, "order_generation_time": {"type": "string", "pattern": r"^\d{2}:\d{2}:\d{2}$"}, "execution_open_time": {"type": "string", "pattern": r"^\d{2}:\d{2}:\d{2}$"}, "execution_cutoff_time": {"type": "string", "pattern": r"^\d{2}:\d{2}:\d{2}$"}, "allow_moc_orders": {"type": "boolean"}}), "turnover_controls": object_schema(["absolute_weight_buffer", "relative_weight_buffer", "min_order_notional_usd", "max_daily_turnover_pct"], {"absolute_weight_buffer": RATIO, "relative_weight_buffer": RATIO, "min_order_notional_usd": POSITIVE, "max_daily_turnover_pct": RATIO}), "events": {"type": "array", "items": {"type": "object"}}}),
    "risk_parameters.json": object_schema(["version", "subchapter_m_single_issuer_cap", "subchapter_m_aggregate_cap", "subchapter_m_concentrated_threshold", "rule_18f4_relative_var_limit", "rule_22e4_illiquid_cap", "rule_35d1_names_rule_floor", "max_portfolio_drawdown_limit", "max_single_order_pct_aum"], {"version": VERSION, "subchapter_m_single_issuer_cap": RATIO, "subchapter_m_aggregate_cap": RATIO, "subchapter_m_concentrated_threshold": RATIO, "rule_18f4_relative_var_limit": {"type": "number", "exclusiveMinimum": 0, "maximum": 2}, "rule_22e4_illiquid_cap": RATIO, "rule_35d1_names_rule_floor": RATIO, "max_portfolio_drawdown_limit": {"type": "number", "exclusiveMinimum": 0, "maximum": 1}, "max_single_order_pct_aum": RATIO}),
    "strategy_ontology.json": object_schema(["version", "strategy_identity", "signal_taxonomy", "factor_weighting_matrix", "overlay_mechanics", "allocation_hierarchy", "themes", "functions"], {"version": VERSION, "strategy_identity": object_schema(["name", "mandate"], {"name": STRING, "mandate": STRING}), "signal_taxonomy": object_schema(["factors", "lookback_windows_days", "normalization_method"], {"factors": {"type": "array", "minItems": 1, "items": STRING}, "lookback_windows_days": {"type": "array", "minItems": 1, "items": {"type": "integer", "minimum": 1}}, "normalization_method": {"enum": ["Z_SCORE", "MIN_MAX", "WINSORIZED_Z_SCORE"]}}), "factor_weighting_matrix": object_schema(["weights", "factor_interaction_mode"], {"weights": {"type": "object", "minProperties": 1, "additionalProperties": RATIO}, "factor_interaction_mode": {"enum": ["LINEAR_COMBINATION", "MULTIPLICATIVE_GATING", "HIERARCHICAL"]}}), "overlay_mechanics": object_schema(["overlay_type", "target_delta", "dte_target_days", "roll_dte_threshold"], {"overlay_type": {"enum": ["COVERED_CALL_OVERLAY", "COLLAR", "CASH_BUFFER_RESERVE"]}, "target_delta": RATIO, "dte_target_days": {"type": "integer", "minimum": 1}, "roll_dte_threshold": {"type": "integer", "minimum": 0}}), "allocation_hierarchy": {"type": "object", "minProperties": 1, "additionalProperties": {"type": "number", "minimum": 0, "maximum": 1}}, "themes": {"type": "array", "items": STRING}, "functions": {"type": "array", "items": STRING}}),
    "fund_universe.json": {"type": "object"},
    "conviction_policy.json": object_schema(
        ["version", "implementation_quality_weights", "ambiguity_penalty_weight", "quality_thresholds", "leverage_bounds", "default_leverage_limits"],
        {
            "version": VERSION,
            "implementation_quality_weights": {"type": "object", "minProperties": 1, "additionalProperties": RATIO},
            "ambiguity_penalty_weight": RATIO,
            "quality_thresholds": object_schema(["weak_max", "emerging_max", "confirmed_max"], {"weak_max": RATIO, "emerging_max": RATIO, "confirmed_max": RATIO}),
            "leverage_bounds": object_schema(["min_leverage", "max_leverage"], {"min_leverage": POSITIVE, "max_leverage": POSITIVE}),
            "default_leverage_limits": object_schema(
                ["max_absolute_leverage", "max_trade_loss_pct", "volatility_limit", "liquidity_limit", "concentration_limit", "portfolio_limit"],
                {key: POSITIVE for key in ["max_absolute_leverage", "max_trade_loss_pct", "volatility_limit", "liquidity_limit", "concentration_limit", "portfolio_limit"]},
            ),
        },
    ),
}


def load_config(path: str | Path) -> Dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    schema = CONFIG_SCHEMAS.get(config_path.name, {"type": "object"})
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(f"{list(error.path)}: {error.message}" for error in errors)
        raise ValueError(f"Configuration schema invalid for {config_path}: {details}")
    return document


def validate_config_directory(config_dir: str | Path = "config") -> Dict[str, Dict[str, Any]]:
    return {path.name: load_config(path) for path in sorted(Path(config_dir).glob("*.json"))}


__all__ = ["CONFIG_SCHEMAS", "load_config", "validate_config_directory"]
