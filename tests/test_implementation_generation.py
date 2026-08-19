"""Implementation generation must precede selection - never the other way round."""

from datetime import date

import pytest

from research.funnel import ResearchFunnel, SelectionBeforeGeneration, FunnelStage
from research.implementations import (
    ImplementationAssumptions,
    ImplementationCandidate,
    ImplementationGenerator,
    ImplementationType,
)


@pytest.fixture()
def funnel(tmp_path) -> ResearchFunnel:
    return ResearchFunnel(as_of=date(2026, 8, 18), storage_dir=tmp_path / "sim")


STRATEGY_ID = "power_infrastructure:uranium_mining"


def synthesized(funnel: ResearchFunnel) -> str:
    funnel.generate()
    funnel.synthesize(STRATEGY_ID)
    return STRATEGY_ID


# -- the guard --------------------------------------------------------------


def test_selecting_before_generating_is_refused(funnel):
    synthesized(funnel)
    with pytest.raises(SelectionBeforeGeneration):
        funnel.select_implementation(STRATEGY_ID, "anything")


def test_generating_before_synthesis_is_refused(funnel):
    with pytest.raises(SelectionBeforeGeneration):
        funnel.generate_implementations(STRATEGY_ID)


def test_selecting_an_unknown_id_after_generation_is_a_key_error(funnel):
    strategy_id = synthesized(funnel)
    funnel.generate_implementations(strategy_id)
    with pytest.raises(KeyError):
        funnel.select_implementation(strategy_id, "does-not-exist")


def test_generation_then_selection_succeeds(funnel):
    strategy_id = synthesized(funnel)
    candidates = funnel.generate_implementations(strategy_id)
    chosen = funnel.select_implementation(strategy_id, candidates[0].id)
    assert chosen.id == candidates[0].id
    assert funnel.selected_implementation(strategy_id) is chosen


# -- every eligible vehicle is a sibling candidate, not a foregone decision --


def test_no_trade_is_always_offered(funnel):
    strategy_id = synthesized(funnel)
    candidates = funnel.generate_implementations(strategy_id)
    assert ImplementationType.NO_TRADE in {c.type for c in candidates}


def test_multiple_expression_types_are_generated_side_by_side(funnel):
    strategy_id = synthesized(funnel)
    candidates = funnel.generate_implementations(strategy_id)
    types = {c.type for c in candidates}
    # At minimum a directional ETF view and the null option must coexist;
    # this is what "advancing straight to a single decision" would have skipped.
    assert ImplementationType.ETF_LONG in types
    assert len(types) >= 2


def test_generated_candidates_are_cached_until_refreshed(funnel):
    strategy_id = synthesized(funnel)
    first = funnel.generate_implementations(strategy_id)
    second = funnel.generate_implementations(strategy_id)
    assert first is second


def test_refresh_regenerates_and_clears_a_prior_selection(funnel):
    strategy_id = synthesized(funnel)
    candidates = funnel.generate_implementations(strategy_id)
    funnel.select_implementation(strategy_id, candidates[0].id)

    funnel.generate_implementations(strategy_id, refresh=True)
    assert funnel.selected_implementation(strategy_id) is None


def test_funnel_stage_advances_generation_then_selection(funnel):
    strategy_id = synthesized(funnel)
    candidates = funnel.generate_implementations(strategy_id)
    assert funnel.positions[strategy_id].stage is FunnelStage.IMPLEMENTATION_GENERATION

    funnel.select_implementation(strategy_id, candidates[0].id)
    position = funnel.positions[strategy_id]
    assert position.stage is FunnelStage.IMPLEMENTATION_SELECTED
    assert position.implementation_id == candidates[0].id


# -- ranking and rationale ----------------------------------------------


def test_candidates_are_ranked_by_risk_adjusted_score(funnel):
    strategy_id = synthesized(funnel)
    candidates = funnel.generate_implementations(strategy_id)
    scores = [c.risk_adjusted_score for c in candidates]
    assert scores == sorted(scores, reverse=True)


def test_every_candidate_carries_a_rationale_and_the_assumptions_used(funnel):
    strategy_id = synthesized(funnel)
    for candidate in funnel.generate_implementations(strategy_id):
        assert candidate.rationale
        assert candidate.assumptions


def test_no_trade_fits_best_when_the_measured_edge_is_weak():
    from research.strategy_generation import StrategyGenerator
    from research.synthesis import ThemeSynthesis

    generator = StrategyGenerator()
    candidate = generator.build("power_infrastructure", "uranium_mining")
    empty = ThemeSynthesis(
        strategy_id=candidate.strategy_id,
        theme=candidate.theme,
        function=candidate.function,
        fund_count=0,
        cluster_count=0,
        observation_dates=0,
        blocking_reasons=["NO_DISCLOSURES_AVAILABLE"],
    )
    result = ImplementationGenerator().generate(candidate, empty)
    assert len(result) == 1
    assert result[0].type == ImplementationType.NO_TRADE
    assert result[0].thesis_fit == 1.0


# -- numbers are derived, not invented -----------------------------------


def test_options_convexity_and_carry_come_from_black_scholes_greeks(funnel):
    strategy_id = synthesized(funnel)
    candidates = funnel.generate_implementations(strategy_id)
    options = next((c for c in candidates if c.type == ImplementationType.OPTIONS), None)
    assert options is not None
    assert options.convexity is not None and options.convexity > 0
    assert options.carry_cost is not None and options.carry_cost > 0
    assert "delta" in options.rationale.lower()


def test_directional_candidates_have_zero_convexity(funnel):
    strategy_id = synthesized(funnel)
    candidates = funnel.generate_implementations(strategy_id)
    for candidate in candidates:
        if candidate.type in (ImplementationType.ETF_LONG, ImplementationType.ETF_HEDGED):
            assert candidate.convexity == 0.0


def test_hedged_expression_costs_carry_that_long_does_not(funnel):
    strategy_id = synthesized(funnel)
    candidates = {c.type: c for c in funnel.generate_implementations(strategy_id)}
    if ImplementationType.ETF_HEDGED in candidates:
        assert candidates[ImplementationType.ETF_HEDGED].carry_cost > 0
        assert candidates[ImplementationType.ETF_LONG].carry_cost == 0.0


def test_custom_assumptions_change_the_generated_numbers(funnel):
    strategy_id = synthesized(funnel)
    baseline = funnel.generate_implementations(strategy_id, refresh=True)
    aggressive = funnel.generate_implementations(
        strategy_id,
        refresh=True,
        assumptions=ImplementationAssumptions(annualized_volatility=0.60, horizon_days=30),
    )
    base_by_type = {c.type: c for c in baseline}
    aggr_by_type = {c.type: c for c in aggressive}
    assert base_by_type[ImplementationType.ETF_LONG].downside_risk != aggr_by_type[ImplementationType.ETF_LONG].downside_risk
