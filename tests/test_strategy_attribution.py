"""
Regression test for learning/strategy_attribution.py.

The module previously had a Python syntax error — `actual_thesis_description`
had no default value but appeared after several keyword arguments that did
(e.g. `expected_hedge_instrument: Optional[str] = None`), which Python
disallows for positional-or-keyword parameters. Nothing imported this module
directly in the existing test suite, so the SyntaxError went undetected.

Fixed by making everything after the always-required trade/price fields
keyword-only (`*`) — this module's only real caller (learning/coordinator.py)
already invokes it exclusively by keyword, so this is a pure syntax fix with
no behavior change. This test just needs to import the module and exercise
attribute_trade_outcome() once to make sure it can never regress silently.
"""

from datetime import date

from learning.strategy_attribution import (
    CorrectnessDimension,
    OutcomeRating,
    StrategyAttributor,
    TradeAttributionResult,
)


class TestAttributeTradeOutcome:
    def test_module_imports_and_compiles(self):
        # Importing this module used to raise SyntaxError outright.
        assert StrategyAttributor is not None

    def test_attribute_trade_outcome_returns_full_breakdown(self):
        attributor = StrategyAttributor()

        result = attributor.attribute_trade_outcome(
            trade_id="trade-001",
            thesis_id="thesis-001",
            entry_date=date(2026, 1, 1),
            exit_date=date(2026, 1, 15),
            entry_price=100.0,
            exit_price=110.0,
            max_price_during_trade=112.0,
            min_price_during_trade=98.0,
            expected_return=0.08,
            expected_thesis_description="Sector rotation into semis",
            expected_instrument="SMH",
            actual_thesis_description="Sector rotation into semis played out",
            expected_hedge_instrument=None,
            expected_hedge_cost=0.0,
            realized_hedge_cost=0.0,
            expected_position_size_pct=0.05,
            benchmark_return=0.02,
            analyst_notes="Clean example trade",
        )

        assert isinstance(result, TradeAttributionResult)
        assert result.trade_id == "trade-001"
        assert result.thesis_id == "thesis-001"
        assert result.duration_days == 14
        assert result.actual_return == 0.10

        dimensions = {o.dimension for o in result.outcomes}
        assert dimensions == {
            CorrectnessDimension.THESIS,
            CorrectnessDimension.INSTRUMENT,
            CorrectnessDimension.TIMING,
            CorrectnessDimension.HEDGE,
            CorrectnessDimension.SIZING,
        }
        # Unhedged position should rate the hedge dimension as correct with
        # zero contribution, per _assess_hedge_correctness's early return.
        hedge = next(o for o in result.outcomes if o.dimension == CorrectnessDimension.HEDGE)
        assert hedge.rating == OutcomeRating.CORRECT
        assert hedge.contribution_pct == 0.0

    def test_actual_thesis_description_is_keyword_only_and_required(self):
        import inspect

        sig = inspect.signature(StrategyAttributor.attribute_trade_outcome)
        param = sig.parameters["actual_thesis_description"]
        assert param.kind == inspect.Parameter.KEYWORD_ONLY
        assert param.default is inspect.Parameter.empty
