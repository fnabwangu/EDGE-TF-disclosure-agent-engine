"""Tests for the month-by-month evidence-gated leverage ratchet simulation."""

import pytest

from analytics.conviction_engine import ConvictionEngine
from analytics.monthly_leverage_simulation import MonthlyEvidenceSnapshot, MonthlyLeverageSimulator
from core.schemas import ConvictionInputs, LeverageLimits

GENEROUS_LIMITS = LeverageLimits(
    max_absolute_leverage=5.0,
    max_trade_loss_pct=999.0,
    volatility_limit=999.0,
    liquidity_limit=999.0,
    concentration_limit=999.0,
    portfolio_limit=999.0,
)


def _inputs(level: float) -> ConvictionInputs:
    """All seven weighted components set to the same level for a clean, known tier."""
    return ConvictionInputs(
        event_expected_value=0.05,
        event_probability_quality=0.9,
        iav=level,
        aqd_quality=level,
        anomaly_score=level,
        manager_breadth_score=level,
        persistence_score=level,
        diffusion_score=level,
        evidence_quality=level,
        ambiguity_penalty=0.0,
    )


def _snapshot(period: str, level: float) -> MonthlyEvidenceSnapshot:
    return MonthlyEvidenceSnapshot(
        period=period,
        inputs=_inputs(level),
        worst_case_loss_pct=-0.05,
        strategy_volatility=0.05,
        base_strategy_notional=100.0,
        maximum_executable_notional=1_000_000.0,
        leverage_limits=GENEROUS_LIMITS,
    )


def test_leverage_ceiling_only_rises_when_tier_improves():
    simulator = MonthlyLeverageSimulator(default_leverage_limits=GENEROUS_LIMITS)
    snapshots = [
        _snapshot("2026-01", 0.20),  # weak
        _snapshot("2026-02", 0.20),  # weak, unchanged
        _snapshot("2026-03", 0.50),  # emerging: tier improves
        _snapshot("2026-04", 0.65),  # confirmed: tier improves
        _snapshot("2026-05", 0.75),  # still confirmed but higher quality -> ceiling must NOT rise
    ]
    result = simulator.run(snapshots)

    tiers = [step.quality_tier for step in result.steps]
    assert tiers == ["weak", "weak", "emerging", "confirmed", "confirmed"]

    assert result.steps[0].evidence_state_improved is False
    assert result.steps[1].evidence_state_improved is False
    assert result.steps[2].evidence_state_improved is True
    assert result.steps[3].evidence_state_improved is True
    assert result.steps[4].evidence_state_improved is False

    # Month 5 stays in the "confirmed" tier despite higher raw quality/requested
    # leverage than month 4; the ceiling must not increase without a tier change.
    assert result.steps[4].requested_leverage > result.steps[3].requested_leverage
    assert result.steps[4].leverage_ceiling == result.steps[3].leverage_ceiling


def test_leverage_ceiling_drops_immediately_on_evidence_degradation():
    simulator = MonthlyLeverageSimulator(default_leverage_limits=GENEROUS_LIMITS)
    snapshots = [
        _snapshot("2026-01", 0.90),  # strong
        _snapshot("2026-02", 0.20),  # collapses to weak
    ]
    result = simulator.run(snapshots)

    assert result.steps[0].quality_tier == "strong"
    assert result.steps[1].quality_tier == "weak"
    assert result.steps[1].evidence_state_degraded is True
    assert result.steps[1].leverage_ceiling < result.steps[0].leverage_ceiling
    assert "EVIDENCE_STATE_DEGRADED_LEVERAGE_CEILING_LOWERED" in result.steps[1].reason_codes


def test_risk_caps_suppress_but_do_not_permanently_lower_ceiling():
    tight_limits = LeverageLimits(
        max_absolute_leverage=5.0,
        max_trade_loss_pct=0.01,  # very tight loss budget this month
        volatility_limit=999.0,
        liquidity_limit=999.0,
        concentration_limit=999.0,
        portfolio_limit=999.0,
    )
    simulator = MonthlyLeverageSimulator(default_leverage_limits=GENEROUS_LIMITS)
    snapshots = [
        _snapshot("2026-01", 0.90),  # strong: ceiling opens up high
        MonthlyEvidenceSnapshot(
            period="2026-02",
            inputs=_inputs(0.90),  # evidence still strong
            worst_case_loss_pct=-0.05,
            strategy_volatility=0.05,
            base_strategy_notional=100.0,
            maximum_executable_notional=1_000_000.0,
            leverage_limits=tight_limits,  # but risk caps bind hard this month
        ),
        _snapshot("2026-03", 0.90),  # risk caps relax again next month
    ]
    result = simulator.run(snapshots)

    assert result.steps[1].approved_leverage < result.steps[0].approved_leverage
    assert result.steps[1].limiting_constraint == "loss_budget_cap"
    # The ceiling itself is unaffected by a one-month risk cap breach.
    assert result.steps[2].leverage_ceiling == result.steps[0].leverage_ceiling
    assert result.steps[2].approved_leverage == pytest.approx(result.steps[0].approved_leverage)


def test_first_month_initializes_ceiling_without_improvement_flag():
    simulator = MonthlyLeverageSimulator(default_leverage_limits=GENEROUS_LIMITS)
    result = simulator.run([_snapshot("2026-01", 0.9)])
    assert result.steps[0].evidence_state_improved is False
    assert result.steps[0].evidence_state_degraded is False
    assert "EVIDENCE_STATE_INITIALIZED" in result.steps[0].reason_codes


def test_run_requires_at_least_one_snapshot():
    with pytest.raises(ValueError):
        MonthlyLeverageSimulator(default_leverage_limits=GENEROUS_LIMITS).run([])


def test_missing_leverage_limits_raises():
    simulator = MonthlyLeverageSimulator()  # no default limits
    snapshot = MonthlyEvidenceSnapshot(
        period="2026-01",
        inputs=_inputs(0.5),
        worst_case_loss_pct=-0.05,
        strategy_volatility=0.05,
        base_strategy_notional=100.0,
        maximum_executable_notional=1_000_000.0,
    )
    with pytest.raises(ValueError):
        simulator.run([snapshot])
