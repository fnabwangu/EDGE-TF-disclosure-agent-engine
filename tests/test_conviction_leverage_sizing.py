"""Tests for the deterministic conviction -> leverage -> position-sizing pipeline."""

import pytest

from analytics.conviction_engine import ConvictionEngine
from analytics.leverage_engine import LeverageEngine
from analytics.position_sizer import PositionSizer
from core.schemas import ConvictionInputs, EventProbability, EventScenario, LeverageLimits


def _engine():
    return ConvictionEngine(
        weights={
            "iav": 0.25,
            "aqd_quality": 0.15,
            "anomaly_score": 0.10,
            "manager_breadth_score": 0.15,
            "persistence_score": 0.15,
            "diffusion_score": 0.10,
            "evidence_quality": 0.10,
        },
        quality_thresholds={"weak_max": 0.30, "emerging_max": 0.60, "confirmed_max": 0.80},
        leverage_bounds={"min_leverage": 0.5, "max_leverage": 2.0},
        ambiguity_penalty_weight=0.25,
    )


def test_event_probability_expected_value():
    event = EventProbability(
        scenarios=[
            EventScenario(name="upheld", probability=0.10, expected_return=-0.10),
            EventScenario(name="invalidated_no_refund", probability=0.45, expected_return=0.05),
            EventScenario(name="invalidated_refund", probability=0.45, expected_return=0.15),
        ]
    )
    assert event.expected_value == pytest.approx(0.10 * -0.10 + 0.45 * 0.05 + 0.45 * 0.15)


def test_event_probability_requires_probabilities_sum_to_one():
    with pytest.raises(ValueError):
        EventProbability(
            scenarios=[
                EventScenario(name="a", probability=0.5, expected_return=0.1),
                EventScenario(name="b", probability=0.4, expected_return=0.1),
            ]
        )


def test_conviction_engine_matches_worked_example():
    engine = _engine()
    inputs = ConvictionInputs(
        event_expected_value=0.05,
        event_probability_quality=0.9,
        iav=0.80,
        aqd_quality=0.80,
        anomaly_score=0.80,
        manager_breadth_score=0.80,
        persistence_score=0.80,
        diffusion_score=0.80,
        evidence_quality=0.80,
        ambiguity_penalty=0.0,
    )
    result = engine.evaluate(inputs)
    assert result.implementation_quality == pytest.approx(0.80)
    assert result.quality_tier == "strong"
    # L_requested = 0.5 + 0.8 * (2.0 - 0.5) = 1.7
    assert result.requested_leverage == pytest.approx(1.7)


def test_conviction_engine_rejects_incomplete_weights():
    with pytest.raises(ValueError):
        ConvictionEngine(weights={"iav": 1.0})


def test_conviction_result_flags_non_positive_event_ev():
    engine = _engine()
    inputs = ConvictionInputs(
        event_expected_value=-0.02,
        event_probability_quality=0.9,
        iav=0.5,
        aqd_quality=0.5,
        anomaly_score=0.5,
        manager_breadth_score=0.5,
        persistence_score=0.5,
        diffusion_score=0.5,
        evidence_quality=0.5,
        ambiguity_penalty=0.0,
    )
    result = engine.evaluate(inputs)
    assert "EVENT_EXPECTED_VALUE_NON_POSITIVE" in result.reason_codes


def test_leverage_engine_caps_requested_leverage_with_loss_budget():
    limits = LeverageLimits(
        max_absolute_leverage=2.0,
        max_trade_loss_pct=0.075,
        volatility_limit=999.0,
        liquidity_limit=999.0,
        concentration_limit=999.0,
        portfolio_limit=999.0,
    )
    decision = LeverageEngine().evaluate(
        requested_leverage=1.7,
        limits=limits,
        worst_case_loss_pct=-0.05,
        strategy_volatility=0.01,
        base_strategy_notional=100.0,
        maximum_executable_notional=1_000_000.0,
    )
    # L_loss = 0.075 / 0.05 = 1.5, binds below the 1.7x request
    assert decision.approved_leverage == pytest.approx(1.5)
    assert decision.limiting_constraint == "loss_budget_cap"
    assert "LEVERAGE_CAPPED_BY_LOSS_BUDGET_CAP" in decision.reason_codes


def test_leverage_engine_volatility_cap_overrides_conviction():
    limits = LeverageLimits(
        max_absolute_leverage=5.0,
        max_trade_loss_pct=999.0,
        volatility_limit=0.15,
        liquidity_limit=999.0,
        concentration_limit=999.0,
        portfolio_limit=999.0,
    )
    decision = LeverageEngine().evaluate(
        requested_leverage=3.0,
        limits=limits,
        worst_case_loss_pct=-0.99,
        strategy_volatility=0.20,
        base_strategy_notional=100.0,
        maximum_executable_notional=1_000_000.0,
    )
    # L_vol = 0.15 / 0.20 = 0.75
    assert decision.approved_leverage == pytest.approx(0.75)
    assert decision.limiting_constraint == "volatility_cap"


def test_leverage_engine_zero_worst_case_loss_is_no_trade():
    limits = LeverageLimits(
        max_absolute_leverage=2.0,
        max_trade_loss_pct=0.075,
        volatility_limit=0.15,
        liquidity_limit=2.0,
        concentration_limit=2.0,
        portfolio_limit=2.0,
    )
    decision = LeverageEngine().evaluate(
        requested_leverage=1.5,
        limits=limits,
        worst_case_loss_pct=0.0,
        strategy_volatility=0.1,
        base_strategy_notional=100.0,
        maximum_executable_notional=1_000.0,
    )
    assert decision.approved_leverage == 0.0
    assert "LEVERAGE_ZERO_NO_TRADE" in decision.reason_codes


def test_position_sizer_equity_shares_and_long_short_split():
    decision = LeverageEngine().evaluate(
        requested_leverage=1.7,
        limits=LeverageLimits(
            max_absolute_leverage=2.0,
            max_trade_loss_pct=0.075,
            volatility_limit=0.15,
            liquidity_limit=2.0,
            concentration_limit=2.0,
            portfolio_limit=2.0,
        ),
        worst_case_loss_pct=-0.05,
        strategy_volatility=0.10,
        base_strategy_notional=100.0,
        maximum_executable_notional=1_000_000.0,
    )
    sizer = PositionSizer()
    result = sizer.size_equity(
        leverage_decision=decision,
        portfolio_nav=1_000_000.0,
        base_allocation=0.10,
        price=50.0,
        long_weight=0.5,
        short_weight=0.5,
    )
    assert result.approved_leverage == pytest.approx(1.5)
    assert result.target_notional == pytest.approx(1_000_000.0 * 0.10 * 1.5)
    assert result.long_notional == pytest.approx(result.target_notional * 0.5)
    assert result.short_notional == pytest.approx(result.target_notional * 0.5)
    assert result.execution_permitted is True
    assert result.shares == (result.long_notional // 50.0) + (result.short_notional // 50.0)


def test_position_sizer_options_uses_premium_at_risk():
    decision = LeverageEngine().evaluate(
        requested_leverage=1.0,
        limits=LeverageLimits(
            max_absolute_leverage=2.0,
            max_trade_loss_pct=0.05,
            volatility_limit=0.15,
            liquidity_limit=2.0,
            concentration_limit=2.0,
            portfolio_limit=2.0,
        ),
        worst_case_loss_pct=-1.0,
        strategy_volatility=0.05,
        base_strategy_notional=100.0,
        maximum_executable_notional=1_000_000.0,
    )
    sizer = PositionSizer()
    result = sizer.size_options(
        leverage_decision=decision,
        portfolio_nav=1_000_000.0,
        base_allocation=0.02,
        premium_per_contract=3.0,
    )
    assert result.contracts == int((1_000_000.0 * 0.02 * decision.approved_leverage) // (3.0 * 100.0))
    assert result.shares is None


def test_position_sizer_zero_leverage_blocks_execution():
    decision = LeverageEngine().evaluate(
        requested_leverage=1.0,
        limits=LeverageLimits(
            max_absolute_leverage=2.0,
            max_trade_loss_pct=0.05,
            volatility_limit=0.15,
            liquidity_limit=2.0,
            concentration_limit=2.0,
            portfolio_limit=2.0,
        ),
        worst_case_loss_pct=0.0,
        strategy_volatility=0.05,
        base_strategy_notional=100.0,
        maximum_executable_notional=1_000_000.0,
    )
    result = PositionSizer().size_equity(
        leverage_decision=decision,
        portfolio_nav=1_000_000.0,
        base_allocation=0.10,
        price=50.0,
    )
    assert result.execution_permitted is False
    assert "SIZING_ZERO_SHARES_NO_TRADE" in result.reason_codes
