"""Tests reconciling CapitalFlowSignalGate (the real default, banded, up to 10x)
with StagedLeverageGate (the legacy flat opt-in policy) inside
DynamicExposureController and MultiSleevePortfolioEngine, plus the
previously-dead conviction_policy.json default_leverage_limits config."""

from datetime import datetime

import pytest

from analytics.capital_flow_leverage_engine import CapitalFlowSignalGate
from analytics.conviction_engine import ConvictionEngine
from analytics.dynamic_exposure_controller import DynamicExposureController
from analytics.leverage_tranches import EvidenceState, LeveragePolicy
from analytics.multi_sleeve_portfolio_engine import MultiSleevePortfolioEngine, SleeveEvaluationInputs, SleevePolicy, SleeveType
from analytics.staged_leverage_gate import StagedLeverageGate
from core.schemas import LeverageLimits

T0 = datetime(2026, 1, 1)

HIGH_LIMITS = LeverageLimits(
    max_absolute_leverage=20.0,
    max_trade_loss_pct=999.0,
    volatility_limit=999.0,
    liquidity_limit=999.0,
    concentration_limit=999.0,
    portfolio_limit=999.0,
)


def _update_kwargs(**overrides):
    kwargs = dict(
        current_time=T0,
        current_price=100.0,
        evidence_state=EvidenceState.STRONG,
        evidence_score=0.9,
        remaining_ev=0.10,
        minimum_remaining_ev=0.05,
        thesis_active=True,
        catalyst_active=True,
        invalidation_intact=True,
        market_confirmation=True,
        leverage_limits=HIGH_LIMITS,
        worst_case_loss_pct=-0.20,
        strategy_volatility=0.05,
        base_strategy_notional=100_000.0,
        maximum_executable_notional=10_000_000.0,
        underlying_return=0.0,
        generic_projected_return=0.22,
    )
    kwargs.update(overrides)
    return kwargs


def test_default_controller_uses_capital_flow_engine_and_reaches_strong_band():
    controller = DynamicExposureController()
    result = controller.update(**_update_kwargs(event_probability=0.90, flow_progress=0.5))
    # STRONG band is 8-10x; floor 8.0 + 0.5*(10-8) = 9.0x
    assert result.signal_target_leverage == pytest.approx(9.0)
    assert result.leverage_after == pytest.approx(9.0)


def test_default_controller_still_respects_risk_caps():
    tight_limits = LeverageLimits(
        max_absolute_leverage=3.0,
        max_trade_loss_pct=999.0,
        volatility_limit=999.0,
        liquidity_limit=999.0,
        concentration_limit=999.0,
        portfolio_limit=999.0,
    )
    controller = DynamicExposureController()
    result = controller.update(**_update_kwargs(leverage_limits=tight_limits, event_probability=0.9, flow_progress=1.0))
    assert result.signal_target_leverage == pytest.approx(10.0)
    assert result.leverage_after == pytest.approx(3.0)


def test_default_controller_blocks_below_event_probability_threshold():
    controller = DynamicExposureController()
    result = controller.update(**_update_kwargs(event_probability=0.4, flow_progress=1.0))
    assert result.leverage_after == 0.0
    assert "EVENT_PROBABILITY_BELOW_THRESHOLD" in result.reason_codes


def test_staged_leverage_gate_is_still_available_as_a_conservative_opt_in():
    controller = DynamicExposureController(staged_gate=StagedLeverageGate(LeveragePolicy()))
    result = controller.update(**_update_kwargs())
    assert result.leverage_after == pytest.approx(2.0)


def test_multi_sleeve_engine_lets_one_sleeve_opt_into_conservative_policy():
    policies = {
        SleeveType.ETF: SleevePolicy(SleeveType.ETF, base_weight=0.5, max_weight=0.5, max_leverage=20.0, max_loss_nav_pct=0.10),
        SleeveType.STOCK: SleevePolicy(SleeveType.STOCK, base_weight=0.5, max_weight=0.5, max_leverage=20.0, max_loss_nav_pct=0.10),
    }
    engine = MultiSleevePortfolioEngine(
        policies,
        max_gross_leverage=100.0,
        max_portfolio_loss_pct=0.20,
        signal_gates={SleeveType.STOCK: StagedLeverageGate(LeveragePolicy())},
    )
    inputs = dict(
        current_price=100.0,
        evidence_state=EvidenceState.STRONG,
        evidence_score=0.9,
        remaining_ev=0.10,
        minimum_remaining_ev=0.05,
        thesis_active=True,
        catalyst_active=True,
        invalidation_intact=True,
        market_confirmation=True,
        leverage_limits=HIGH_LIMITS,
        worst_case_loss_pct=-0.20,
        strategy_volatility=0.05,
        maximum_executable_notional=10_000_000.0,
        underlying_return=0.0,
        generic_projected_return=0.22,
        event_probability=0.9,
        flow_progress=1.0,
    )
    result = engine.update(
        current_time=T0,
        nav=1_000_000.0,
        sleeve_inputs={
            SleeveType.ETF: SleeveEvaluationInputs(**inputs),
            SleeveType.STOCK: SleeveEvaluationInputs(**inputs),
        },
    )
    etf_leverage = result.architecture.sleeves[SleeveType.ETF].approved_leverage
    stock_leverage = result.architecture.sleeves[SleeveType.STOCK].approved_leverage
    assert etf_leverage == pytest.approx(10.0)  # default CapitalFlowSignalGate STRONG ceiling
    assert stock_leverage == pytest.approx(2.0)  # opted into the legacy flat StagedLeverageGate ceiling


def test_profit_taking_sees_leveraged_return_not_underlying_return():
    """An 8% underlying move at 6x exposure must be evaluated as a ~48% leveraged move."""
    controller = DynamicExposureController()
    # Establish leverage first (flow_progress=1.0 => STRONG ceiling = 10x).
    controller.update(**_update_kwargs(event_probability=0.9, flow_progress=1.0))
    result = controller.update(
        **_update_kwargs(current_time=T0, event_probability=0.9, flow_progress=1.0, underlying_return=0.05)
    )
    assert result.underlying_return == pytest.approx(0.05)
    assert result.leveraged_return == pytest.approx(0.05 * result.leverage_before)
    # 0.05 * 10x = 50% leveraged return, well past the 40% profit-taking tier.
    assert result.profit_decision.action.value in {"SELL_33", "SELL_25", "CLOSE"}


def test_conviction_engine_loads_default_leverage_limits_from_config():
    engine = ConvictionEngine()
    assert engine.default_leverage_limits is not None
    assert engine.default_leverage_limits.max_absolute_leverage == pytest.approx(2.0)
    assert engine.default_leverage_limits.max_trade_loss_pct == pytest.approx(0.075)


def test_conviction_engine_default_leverage_limits_none_without_config_file(tmp_path):
    missing_path = tmp_path / "does_not_exist.json"
    engine = ConvictionEngine(config_path=missing_path)
    assert engine.default_leverage_limits is None
