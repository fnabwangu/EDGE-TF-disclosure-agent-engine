"""Tests for the multi-sleeve portfolio engine (ETF / STOCK / OPTIONS / HEDGE)."""

from datetime import datetime

import pytest

from analytics.leverage_tranches import EvidenceState
from analytics.multi_sleeve_portfolio_engine import (
    MultiSleevePortfolioEngine,
    SleeveEvaluationInputs,
    SleevePolicy,
    SleeveType,
)
from core.schemas import LeverageLimits

T0 = datetime(2026, 1, 1)

GENEROUS_LIMITS = LeverageLimits(
    max_absolute_leverage=20.0,
    max_trade_loss_pct=999.0,
    volatility_limit=999.0,
    liquidity_limit=999.0,
    concentration_limit=999.0,
    portfolio_limit=999.0,
)


def _sleeve_inputs(**overrides) -> SleeveEvaluationInputs:
    defaults = dict(
        current_price=100.0,
        evidence_state=EvidenceState.CONFIRMED,
        evidence_score=0.7,
        remaining_ev=0.10,
        minimum_remaining_ev=0.05,
        thesis_active=True,
        catalyst_active=True,
        invalidation_intact=True,
        market_confirmation=True,
        leverage_limits=GENEROUS_LIMITS,
        worst_case_loss_pct=-0.20,
        strategy_volatility=0.05,
        maximum_executable_notional=10_000_000.0,
        underlying_return=0.0,
        generic_projected_return=0.22,
    )
    defaults.update(overrides)
    return SleeveEvaluationInputs(**defaults)


def _four_sleeve_policies() -> dict:
    return {
        SleeveType.ETF: SleevePolicy(SleeveType.ETF, base_weight=0.40, max_weight=0.50, max_leverage=2.0, max_loss_nav_pct=0.05),
        SleeveType.STOCK: SleevePolicy(SleeveType.STOCK, base_weight=0.30, max_weight=0.40, max_leverage=2.0, max_loss_nav_pct=0.05),
        SleeveType.OPTIONS: SleevePolicy(SleeveType.OPTIONS, base_weight=0.20, max_weight=0.20, max_leverage=2.0, max_loss_nav_pct=0.03),
        SleeveType.HEDGE: SleevePolicy(SleeveType.HEDGE, base_weight=0.10, max_weight=0.10, max_leverage=2.0, max_loss_nav_pct=0.02, direction=-1.0),
    }


def test_sleeve_policy_rejects_invalid_direction():
    with pytest.raises(ValueError):
        SleevePolicy(SleeveType.HEDGE, base_weight=0.1, max_weight=0.1, max_leverage=1.0, max_loss_nav_pct=0.02, direction=0.5)


def test_sleeve_policy_rejects_base_weight_above_max_weight():
    with pytest.raises(ValueError):
        SleevePolicy(SleeveType.ETF, base_weight=0.6, max_weight=0.5, max_leverage=1.0, max_loss_nav_pct=0.05)


def test_options_sleeve_blocked_when_data_unavailable():
    engine = MultiSleevePortfolioEngine(_four_sleeve_policies(), max_gross_leverage=10.0, max_portfolio_loss_pct=0.15)
    result = engine.update(
        current_time=T0,
        nav=1_000_000.0,
        sleeve_inputs={
            SleeveType.ETF: _sleeve_inputs(),
            SleeveType.STOCK: _sleeve_inputs(),
            SleeveType.HEDGE: _sleeve_inputs(evidence_state=EvidenceState.EMERGING, current_price=50.0),
            SleeveType.OPTIONS: _sleeve_inputs(data_available=False),
        },
    )
    options_state = result.architecture.sleeves[SleeveType.OPTIONS]
    assert options_state.blocked is True
    assert options_state.gross_exposure == 0.0
    assert "OPTIONS_SLEEVE_BLOCKED_MISSING_DATA" in result.reason_codes
    assert result.sleeve_results[SleeveType.OPTIONS] is None


def test_missing_sleeve_input_is_also_blocked():
    engine = MultiSleevePortfolioEngine(_four_sleeve_policies(), max_gross_leverage=10.0, max_portfolio_loss_pct=0.15)
    result = engine.update(
        current_time=T0,
        nav=1_000_000.0,
        sleeve_inputs={
            SleeveType.ETF: _sleeve_inputs(),
        },
    )
    assert result.architecture.sleeves[SleeveType.STOCK].blocked is True
    assert result.architecture.sleeves[SleeveType.OPTIONS].blocked is True
    assert result.architecture.sleeves[SleeveType.HEDGE].blocked is True


def test_hedge_sleeve_direction_reduces_net_leverage():
    policies = {
        SleeveType.ETF: SleevePolicy(SleeveType.ETF, base_weight=0.5, max_weight=0.5, max_leverage=2.0, max_loss_nav_pct=0.05),
        SleeveType.HEDGE: SleevePolicy(SleeveType.HEDGE, base_weight=0.5, max_weight=0.5, max_leverage=2.0, max_loss_nav_pct=0.05, direction=-1.0),
    }
    engine = MultiSleevePortfolioEngine(policies, max_gross_leverage=10.0, max_portfolio_loss_pct=0.15)
    result = engine.update(
        current_time=T0,
        nav=1_000_000.0,
        sleeve_inputs={
            SleeveType.ETF: _sleeve_inputs(evidence_state=EvidenceState.STRONG),
            SleeveType.HEDGE: _sleeve_inputs(evidence_state=EvidenceState.STRONG),
        },
    )
    arch = result.architecture
    etf_exposure = arch.sleeves[SleeveType.ETF].gross_exposure
    hedge_exposure = arch.sleeves[SleeveType.HEDGE].gross_exposure
    assert etf_exposure > 0
    assert hedge_exposure < 0
    # Net leverage nets long ETF against short hedge; gross sums the magnitudes.
    assert arch.net_leverage == pytest.approx((etf_exposure + hedge_exposure) / 1_000_000.0)
    assert arch.gross_leverage == pytest.approx((abs(etf_exposure) + abs(hedge_exposure)) / 1_000_000.0)
    assert arch.gross_leverage > arch.net_leverage


def test_aggregate_gross_leverage_cap_scales_down_all_sleeves():
    policies = {
        SleeveType.ETF: SleevePolicy(SleeveType.ETF, base_weight=1.0, max_weight=1.0, max_leverage=5.0, max_loss_nav_pct=0.10),
        SleeveType.STOCK: SleevePolicy(SleeveType.STOCK, base_weight=1.0, max_weight=1.0, max_leverage=5.0, max_loss_nav_pct=0.10),
    }
    engine = MultiSleevePortfolioEngine(policies, max_gross_leverage=1.5, max_portfolio_loss_pct=0.20)
    result = engine.update(
        current_time=T0,
        nav=1_000_000.0,
        sleeve_inputs={
            SleeveType.ETF: _sleeve_inputs(evidence_state=EvidenceState.STRONG),
            SleeveType.STOCK: _sleeve_inputs(evidence_state=EvidenceState.STRONG),
        },
    )
    assert result.architecture.gross_leverage <= 1.5 + 1e-6
    assert "PORTFOLIO_GROSS_LEVERAGE_CAP_APPLIED" in result.reason_codes
    # Both sleeves were scaled down proportionally, not one zeroed and one left alone.
    etf_leverage = result.architecture.sleeves[SleeveType.ETF].approved_leverage
    stock_leverage = result.architecture.sleeves[SleeveType.STOCK].approved_leverage
    assert etf_leverage > 0
    assert stock_leverage > 0
    assert etf_leverage == pytest.approx(stock_leverage)


def test_nav_must_be_positive():
    engine = MultiSleevePortfolioEngine(_four_sleeve_policies(), max_gross_leverage=10.0, max_portfolio_loss_pct=0.15)
    with pytest.raises(ValueError):
        engine.update(current_time=T0, nav=0.0, sleeve_inputs={})


def test_requires_at_least_one_sleeve_policy():
    with pytest.raises(ValueError):
        MultiSleevePortfolioEngine({}, max_gross_leverage=10.0, max_portfolio_loss_pct=0.15)
