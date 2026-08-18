"""Tests for the benchmark-aware deterministic profit-taking ladder."""

import pytest

from analytics.profit_taking_engine import ProfitTakingEngine, evaluate_profit_taking
from core.schemas import ProfitAction, ProfitTakingInputs


def test_worked_example_closes_on_benchmark_exceeded_and_low_remaining_ev():
    result = evaluate_profit_taking(
        ProfitTakingInputs(
            current_return=0.465,
            generic_projected_return=0.22,
            remaining_ev=0.03,
            minimum_remaining_ev=0.05,
            thesis_active=True,
            catalyst_active=True,
            invalidation_intact=True,
            leverage=10.0,
            original_capital=100_000,
            current_position_value=146_500,
        )
    )
    assert result.action == ProfitAction.CLOSE
    assert result.fraction_to_sell == 1.0
    assert result.benchmark_capture_ratio == pytest.approx(0.465 / 0.22)
    assert result.capital_to_recover == 146_500
    assert "PROFIT_TARGET" in result.reason_codes
    assert "GENERIC_BENCHMARK_EXCEEDED_2X" in result.reason_codes
    assert "INSUFFICIENT_REMAINING_EV" in result.reason_codes
    assert result.requires_derisk_review is True
    assert "MANDATORY_DERISK_EVALUATION_LEVERAGE_RETURN" in result.reason_codes


def test_thesis_invalidation_forces_close_even_with_positive_remaining_ev():
    result = evaluate_profit_taking(
        ProfitTakingInputs(
            current_return=0.05,
            generic_projected_return=0.22,
            remaining_ev=0.50,
            minimum_remaining_ev=0.05,
            invalidation_intact=False,
            leverage=1.0,
            original_capital=100_000,
            current_position_value=105_000,
        )
    )
    assert result.action == ProfitAction.CLOSE
    assert result.fraction_to_sell == 1.0
    assert "THESIS_INVALIDATED" in result.reason_codes


def test_forty_percent_rule_trims_larger_fraction_when_benchmark_capture_is_high():
    result = evaluate_profit_taking(
        ProfitTakingInputs(
            current_return=0.45,
            generic_projected_return=0.25,  # capture ~1.8x, above the 1.5x large-trim threshold
            remaining_ev=0.10,
            minimum_remaining_ev=0.05,
            leverage=1.0,
            original_capital=100_000,
            current_position_value=145_000,
        )
    )
    assert result.action == ProfitAction.SELL_33
    assert result.fraction_to_sell == pytest.approx(0.33)
    assert "RETURN_GTE_40" in result.reason_codes


def test_forty_percent_rule_default_trim_when_benchmark_capture_is_modest():
    result = evaluate_profit_taking(
        ProfitTakingInputs(
            current_return=0.42,
            generic_projected_return=0.60,  # capture 0.7x, below the 1.5x threshold
            remaining_ev=0.10,
            minimum_remaining_ev=0.05,
            leverage=1.0,
            original_capital=100_000,
            current_position_value=142_000,
        )
    )
    assert result.action == ProfitAction.SELL_25
    assert result.fraction_to_sell == pytest.approx(0.25)


def test_twenty_percent_rule():
    result = evaluate_profit_taking(
        ProfitTakingInputs(
            current_return=0.22,
            generic_projected_return=0.60,
            remaining_ev=0.10,
            minimum_remaining_ev=0.05,
            leverage=1.0,
            original_capital=100_000,
            current_position_value=122_000,
        )
    )
    assert result.action == ProfitAction.SELL_25
    assert result.fraction_to_sell == pytest.approx(0.25)
    assert result.reason_codes == ["PROFIT_TARGET", "RETURN_GTE_20"]


def test_generic_projection_captured_early_triggers_revalidate():
    result = evaluate_profit_taking(
        ProfitTakingInputs(
            current_return=0.12,
            generic_projected_return=0.10,  # capture 1.2x but below the 20% sell tier
            remaining_ev=0.10,
            minimum_remaining_ev=0.05,
            leverage=1.0,
            original_capital=100_000,
            current_position_value=112_000,
        )
    )
    assert result.action == ProfitAction.REVALIDATE
    assert result.fraction_to_sell == 0.0
    assert "GENERIC_PROJECTED_RETURN_CAPTURED" in result.reason_codes


def test_hold_when_thesis_active_and_no_thresholds_met():
    result = evaluate_profit_taking(
        ProfitTakingInputs(
            current_return=0.05,
            generic_projected_return=0.22,
            remaining_ev=0.10,
            minimum_remaining_ev=0.05,
            leverage=1.0,
            original_capital=100_000,
            current_position_value=105_000,
        )
    )
    assert result.action == ProfitAction.HOLD
    assert result.requires_derisk_review is False


def test_non_positive_generic_projection_disables_benchmark_rules():
    result = evaluate_profit_taking(
        ProfitTakingInputs(
            current_return=0.10,
            generic_projected_return=0.0,
            remaining_ev=0.10,
            minimum_remaining_ev=0.05,
            leverage=1.0,
            original_capital=100_000,
            current_position_value=110_000,
        )
    )
    assert result.benchmark_capture_ratio is None
    assert "GENERIC_PROJECTED_RETURN_NON_POSITIVE" in result.reason_codes
    assert result.action == ProfitAction.HOLD


def test_mandatory_derisk_review_flag_independent_of_chosen_action():
    engine = ProfitTakingEngine()
    result = engine.evaluate(
        ProfitTakingInputs(
            current_return=0.41,
            generic_projected_return=10.0,  # tiny benchmark capture, stays on the plain 40% branch
            remaining_ev=0.50,
            minimum_remaining_ev=0.05,
            leverage=6.0,
            original_capital=100_000,
            current_position_value=141_000,
        )
    )
    assert result.action == ProfitAction.SELL_25
    assert result.requires_derisk_review is True
    assert "MANDATORY_DERISK_EVALUATION_LEVERAGE_RETURN" in result.reason_codes
