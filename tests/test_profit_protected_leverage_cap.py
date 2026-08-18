"""Tests for the persistent profit-protected leverage ceiling.

Reproduces the reported bug: after a profit trim reduces leverage, the
standing signal target (unchanged evidence state/progress) must not silently
re-add the harvested exposure on the next period.
"""

from datetime import datetime, timedelta

import pytest

from analytics.dynamic_exposure_controller import DynamicExposureController
from analytics.leverage_tranches import EvidenceState
from core.schemas import LeverageLimits

T0 = datetime(2026, 8, 1)

GENEROUS_LIMITS = LeverageLimits(
    max_absolute_leverage=20.0,
    max_trade_loss_pct=999.0,
    volatility_limit=999.0,
    liquidity_limit=999.0,
    concentration_limit=999.0,
    portfolio_limit=999.0,
)


def _kwargs(**overrides):
    kwargs = dict(
        current_time=T0,
        current_price=100.0,
        evidence_state=EvidenceState.EMERGING,
        evidence_score=0.5,
        remaining_ev=0.10,
        minimum_remaining_ev=0.05,
        thesis_active=True,
        catalyst_active=True,
        invalidation_intact=True,
        market_confirmation=True,
        leverage_limits=GENEROUS_LIMITS,
        worst_case_loss_pct=-0.20,
        strategy_volatility=0.05,
        base_strategy_notional=100_000.0,
        maximum_executable_notional=10_000_000.0,
        underlying_return=0.0,
        generic_projected_return=0.60,  # keep benchmark capture modest -> default 25% trim
        event_probability=0.90,
        flow_progress=0.0,
    )
    kwargs.update(overrides)
    return kwargs


def test_profit_trim_establishes_a_persistent_ceiling_not_re_added_next_period():
    controller = DynamicExposureController()

    # August: EMERGING at entry -> 4.0x requested/approved, no risk caps binding.
    august = controller.update(**_kwargs(current_time=T0, underlying_return=0.0))
    assert august.leverage_after == pytest.approx(4.0)
    assert august.profit_protected_leverage_cap is None

    # A +7.31% underlying move at 4x -> ~29.24% leveraged return, crosses the
    # 20% tier and trims 25%: 4.0x -> 3.0x.
    trim = controller.update(**_kwargs(current_time=T0 + timedelta(days=30), underlying_return=0.0731))
    assert trim.leveraged_return == pytest.approx(0.0731 * 4.0)
    assert trim.reduction_result.leverage_removed > 0.0
    assert trim.leverage_after == pytest.approx(3.0)
    assert trim.profit_protected_leverage_cap == pytest.approx(3.0)
    assert "PROFIT_PROTECTED_CAP_ESTABLISHED" in trim.reason_codes

    # September: still EMERGING, flow_progress unchanged at 0.0 -> signal target
    # is still 4.0x, but the harvest ceiling must hold the book at 3.0x.
    september = controller.update(
        **_kwargs(current_time=T0 + timedelta(days=60), underlying_return=0.0)
    )
    assert september.signal_target_leverage == pytest.approx(4.0)
    assert september.tranche_added == 0.0
    assert september.leverage_after == pytest.approx(3.0)
    assert "PROFIT_PROTECTED_CAP_ACTIVE" in september.reason_codes


def test_evidence_state_upgrade_releases_the_profit_protected_cap():
    controller = DynamicExposureController()
    controller.update(**_kwargs(current_time=T0, underlying_return=0.0))
    trim = controller.update(**_kwargs(current_time=T0 + timedelta(days=30), underlying_return=0.0731))
    assert trim.leverage_after == pytest.approx(3.0)

    # Evidence genuinely improves to CONFIRMED: the cap must release and the
    # controller may scale back in toward the new (higher) band.
    confirmed = controller.update(
        **_kwargs(
            current_time=T0 + timedelta(days=60),
            evidence_state=EvidenceState.CONFIRMED,
            underlying_return=0.0,
        )
    )
    assert "PROFIT_PROTECTED_CAP_RELEASED_FRESH_EVIDENCE" in confirmed.reason_codes
    assert confirmed.profit_protected_leverage_cap is None
    assert confirmed.leverage_after > 3.0


def test_increased_flow_progress_releases_the_profit_protected_cap():
    controller = DynamicExposureController()
    controller.update(**_kwargs(current_time=T0, underlying_return=0.0, flow_progress=0.0))
    trim = controller.update(**_kwargs(current_time=T0 + timedelta(days=30), underlying_return=0.0731, flow_progress=0.0))
    assert trim.leverage_after == pytest.approx(3.0)

    progressed = controller.update(
        **_kwargs(current_time=T0 + timedelta(days=60), underlying_return=0.0, flow_progress=0.5)
    )
    assert "PROFIT_PROTECTED_CAP_RELEASED_FRESH_EVIDENCE" in progressed.reason_codes
    assert progressed.profit_protected_leverage_cap is None
    # EMERGING band 4-6x, progress 0.5 -> 5.0x, above the released 3.0x floor.
    assert progressed.leverage_after == pytest.approx(5.0)


def test_no_cap_established_when_no_harvest_occurs():
    controller = DynamicExposureController()
    result = controller.update(**_kwargs(current_time=T0, underlying_return=0.0))
    assert result.reduction_result.leverage_removed == 0.0
    assert result.profit_protected_leverage_cap is None
    assert "PROFIT_PROTECTED_CAP_ESTABLISHED" not in result.reason_codes
    assert "PROFIT_PROTECTED_CAP_ACTIVE" not in result.reason_codes
