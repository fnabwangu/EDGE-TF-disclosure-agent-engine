"""
Strategy attribution and outcome decomposition.

Path: learning/strategy_attribution.py

After a trade or thesis concludes, attribute the outcome across multiple dimensions:
- Was the thesis right?
- Was the instrument right?
- Was the timing right?
- Was the hedge right?
- Was sizing right?

This produces rich training signal instead of binary win/loss labels.
"""

from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Tuple, Literal
from dataclasses import dataclass, field
from enum import Enum

from learning.schemas import TrainingLabel, HistoricalTrade


class CorrectnessDimension(str, Enum):
    """Dimensions of trade correctness."""
    THESIS = "thesis"
    INSTRUMENT = "instrument"
    TIMING = "timing"
    HEDGE = "hedge"
    SIZING = "sizing"


class OutcomeRating(str, Enum):
    """Rating for outcome dimension."""
    CORRECT = "correct"
    PARTIALLY_CORRECT = "partially_correct"
    INCORRECT = "incorrect"


@dataclass
class DimensionalOutcome:
    """Outcome rating for a single dimension."""
    dimension: CorrectnessDimension
    rating: OutcomeRating
    contribution_pct: float  # 0-100%, should sum to ~100 across dimensions
    explanation: str
    evidence: List[str] = field(default_factory=list)


@dataclass
class TradeAttributionResult:
    """Complete attribution breakdown for a trade."""
    trade_id: str
    thesis_id: str
    entry_date: date
    exit_date: date
    duration_days: int
    
    # Realized metrics
    actual_return: float
    max_drawdown: float
    realized_hedge_cost: float
    volatility_realized: float
    
    # Outcome ratings
    outcomes: List[DimensionalOutcome] = field(default_factory=list)
    
    # Attribution residuals (what wasn't explained)
    total_attribution_pct: float = 0.0
    unexplained_pct: float = 0.0
    
    # Conclusion
    thesis_outcome: Literal["confirmed", "partially_confirmed", "invalidated"]
    improvement_areas: List[str] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    analyst_notes: Optional[str] = None


class StrategyAttributor:
    """
    Analyzes completed trades and attributes outcomes across dimensions.
    
    Produces rich training signals for the learning engine.
    """
    
    def __init__(self):
        # Configurable thresholds
        self.thesis_success_threshold = 0.05  # 5% return validates thesis
        self.thesis_partial_threshold = 0.01  # 1% is partial
        self.timing_window_days = 30  # Expected realization window
        self.hedge_effectiveness_threshold = 0.50  # >50% drawdown reduction is effective
    
    def attribute_trade_outcome(
        self,
        trade_id: str,
        thesis_id: str,
        entry_date: date,
        exit_date: date,
        entry_price: float,
        exit_price: float,
        max_price_during_trade: float,
        min_price_during_trade: float,
        
        # Expected values at entry
        expected_return: float,
        expected_thesis_description: str,
        expected_instrument: str,
        expected_hedge_instrument: Optional[str] = None,
        expected_hedge_cost: float = 0.0,
        expected_position_size_pct: float = 0.0,
        
        # What actually happened
        actual_thesis_description: str,
        realized_hedge_cost: float = 0.0,
        actual_catalyst_description: Optional[str] = None,
        
        # Market context
        benchmark_return: float = 0.0,
        volatility_realized: Optional[float] = None,
        
        # Human assessment
        analyst_notes: Optional[str] = None,
    ) -> TradeAttributionResult:
        """
        Comprehensive attribution of trade outcome across dimensions.
        
        Returns:
            TradeAttributionResult with dimensional breakdown
        """
        # Compute basic metrics
        actual_return = (exit_price - entry_price) / entry_price
        max_drawdown = (min_price_during_trade - entry_price) / entry_price
        duration_days = (exit_date - entry_date).days
        
        outcomes: List[DimensionalOutcome] = []
        
        # Dimension 1: Thesis correctness
        thesis_outcome = self._assess_thesis_correctness(
            expected_thesis_description,
            actual_thesis_description,
            expected_return,
            actual_return,
            actual_catalyst_description,
        )
        outcomes.append(thesis_outcome)
        
        # Dimension 2: Instrument correctness
        instrument_outcome = self._assess_instrument_correctness(
            expected_instrument,
            expected_return,
            actual_return,
            benchmark_return,
        )
        outcomes.append(instrument_outcome)
        
        # Dimension 3: Timing correctness
        timing_outcome = self._assess_timing_correctness(
            duration_days,
            expected_return,
            actual_return,
            max_drawdown,
        )
        outcomes.append(timing_outcome)
        
        # Dimension 4: Hedge correctness
        hedge_outcome = self._assess_hedge_correctness(
            expected_hedge_instrument,
            expected_hedge_cost,
            realized_hedge_cost,
            max_drawdown,
        )
        outcomes.append(hedge_outcome)
        
        # Dimension 5: Sizing correctness
        sizing_outcome = self._assess_sizing_correctness(
            expected_position_size_pct,
            actual_return,
            max_drawdown,
        )
        outcomes.append(sizing_outcome)
        
        # Compute total attribution
        total_attribution = sum(o.contribution_pct for o in outcomes)
        unexplained = 100.0 - total_attribution
        
        # Overall thesis outcome
        overall_thesis_outcome = self._aggregate_outcome([o for o in outcomes if o.dimension == CorrectnessDimension.THESIS])
        
        # Identify improvement areas
        improvement_areas = [
            o.dimension.value for o in outcomes
            if o.rating in [OutcomeRating.INCORRECT, OutcomeRating.PARTIALLY_CORRECT]
        ]
        
        return TradeAttributionResult(
            trade_id=trade_id,
            thesis_id=thesis_id,
            entry_date=entry_date,
            exit_date=exit_date,
            duration_days=duration_days,
            actual_return=actual_return,
            max_drawdown=max_drawdown,
            realized_hedge_cost=realized_hedge_cost,
            volatility_realized=volatility_realized or 0.0,
            outcomes=outcomes,
            total_attribution_pct=total_attribution,
            unexplained_pct=unexplained,
            thesis_outcome=overall_thesis_outcome,
            improvement_areas=improvement_areas,
            analyst_notes=analyst_notes,
        )
    
    def _assess_thesis_correctness(
        self,
        expected_description: str,
        actual_description: str,
        expected_return: float,
        actual_return: float,
        catalyst_description: Optional[str] = None,
    ) -> DimensionalOutcome:
        """Assess if thesis about why an event would happen was correct."""
        evidence = []
        
        if expected_return > 0 and actual_return > self.thesis_success_threshold:
            rating = OutcomeRating.CORRECT
            contribution = 60.0  # Thesis being right is most important
            evidence.append(f"Realized return {actual_return:.1%} exceeded success threshold {self.thesis_success_threshold:.1%}")
        elif expected_return > 0 and actual_return > self.thesis_partial_threshold:
            rating = OutcomeRating.PARTIALLY_CORRECT
            contribution = 30.0
            evidence.append(f"Realized return {actual_return:.1%} achieved partial success")
        else:
            rating = OutcomeRating.INCORRECT
            contribution = 5.0
            evidence.append(f"Realized return {actual_return:.1%} did not validate thesis")
        
        # Check if described mechanism actually happened
        if catalyst_description:
            evidence.append(f"Catalyst: {catalyst_description}")
        
        return DimensionalOutcome(
            dimension=CorrectnessDimension.THESIS,
            rating=rating,
            contribution_pct=contribution,
            explanation=f"Thesis correctness: {rating.value}. Expected return: {expected_return:.1%}, Actual: {actual_return:.1%}",
            evidence=evidence,
        )
    
    def _assess_instrument_correctness(
        self,
        expected_instrument: str,
        expected_return: float,
        actual_return: float,
        benchmark_return: float = 0.0,
    ) -> DimensionalOutcome:
        """Assess if the specific instrument chosen was the right one."""
        evidence = []
        
        # Did the instrument outperform the benchmark?
        relative_return = actual_return - benchmark_return
        
        if expected_return > 0 and relative_return > benchmark_return * 0.5:
            rating = OutcomeRating.CORRECT
            contribution = 20.0
            evidence.append(f"Outperformed benchmark by {relative_return - benchmark_return:.1%}")
        elif expected_return > 0 and relative_return > 0:
            rating = OutcomeRating.PARTIALLY_CORRECT
            contribution = 10.0
            evidence.append(f"Slightly outperformed benchmark")
        else:
            rating = OutcomeRating.INCORRECT
            contribution = 1.0
            evidence.append(f"Underperformed benchmark by {benchmark_return - relative_return:.1%}")
        
        evidence.append(f"Instrument: {expected_instrument}, Return: {actual_return:.1%} vs Benchmark: {benchmark_return:.1%}")
        
        return DimensionalOutcome(
            dimension=CorrectnessDimension.INSTRUMENT,
            rating=rating,
            contribution_pct=contribution,
            explanation=f"Instrument selection: {expected_instrument}. Performance vs benchmark: {relative_return - benchmark_return:+.1%}",
            evidence=evidence,
        )
    
    def _assess_timing_correctness(
        self,
        duration_days: int,
        expected_return: float,
        actual_return: float,
        max_drawdown: float,
    ) -> DimensionalOutcome:
        """Assess if entry/exit timing was appropriate."""
        evidence = []
        
        # Did the move happen in reasonable timeframe?
        within_window = duration_days <= self.timing_window_days
        
        if within_window and actual_return > 0:
            rating = OutcomeRating.CORRECT
            contribution = 10.0
            evidence.append(f"Trade completed within expected window ({duration_days} days)")
        elif duration_days > self.timing_window_days and actual_return > 0:
            rating = OutcomeRating.PARTIALLY_CORRECT
            contribution = 5.0
            evidence.append(f"Trade took longer than expected ({duration_days} vs {self.timing_window_days} days)")
        else:
            rating = OutcomeRating.INCORRECT
            contribution = 2.0
            evidence.append(f"Adverse timing: duration {duration_days} days, return {actual_return:.1%}")
        
        # Check if drawdown was acceptable
        if max_drawdown > -0.05:
            evidence.append("Timing allowed avoiding significant drawdown")
        else:
            evidence.append(f"Experienced drawdown of {max_drawdown:.1%}")
        
        return DimensionalOutcome(
            dimension=CorrectnessDimension.TIMING,
            rating=rating,
            contribution_pct=contribution,
            explanation=f"Timing: {duration_days} days to realization. Max drawdown: {max_drawdown:.1%}",
            evidence=evidence,
        )
    
    def _assess_hedge_correctness(
        self,
        hedge_instrument: Optional[str],
        expected_hedge_cost: float,
        realized_hedge_cost: float,
        max_drawdown: float,
    ) -> DimensionalOutcome:
        """Assess if hedge was effective."""
        evidence = []
        
        if not hedge_instrument:
            return DimensionalOutcome(
                dimension=CorrectnessDimension.HEDGE,
                rating=OutcomeRating.CORRECT,  # No hedge = no hedge cost
                contribution_pct=0.0,
                explanation="No hedge was used",
                evidence=["Unhedged position"],
            )
        
        # Was drawdown reduction significant?
        drawdown_magnitude = abs(max_drawdown)
        hedge_cost_ratio = realized_hedge_cost / max(abs(max_drawdown), 0.001)
        
        if drawdown_magnitude > 0.10 and hedge_cost_ratio < 1.0:
            rating = OutcomeRating.CORRECT
            contribution = 5.0
            evidence.append(f"Hedge cost ({realized_hedge_cost:.1%}) less than drawdown avoided ({drawdown_magnitude:.1%})")
        elif hedge_cost_ratio < 1.5:
            rating = OutcomeRating.PARTIALLY_CORRECT
            contribution = 2.0
            evidence.append(f"Hedge cost acceptable but not optimal")
        else:
            rating = OutcomeRating.INCORRECT
            contribution = 1.0
            evidence.append(f"Hedge too expensive relative to protection")
        
        evidence.append(f"Hedge: {hedge_instrument}, Expected cost: {expected_hedge_cost:.1%}, Realized: {realized_hedge_cost:.1%}")
        
        return DimensionalOutcome(
            dimension=CorrectnessDimension.HEDGE,
            rating=rating,
            contribution_pct=contribution,
            explanation=f"Hedge effectiveness: {hedge_instrument if hedge_instrument else 'none'}",
            evidence=evidence,
        )
    
    def _assess_sizing_correctness(
        self,
        expected_position_size_pct: float,
        actual_return: float,
        max_drawdown: float,
    ) -> DimensionalOutcome:
        """Assess if position sizing was appropriate."""
        evidence = []
        
        # Risk-return balance
        if max_drawdown > -0.15:  # Acceptable drawdown
            if actual_return > 0.03:  # Good return
                rating = OutcomeRating.CORRECT
                contribution = 5.0
                evidence.append("Sizing allowed profitable return with acceptable drawdown")
            else:
                rating = OutcomeRating.PARTIALLY_CORRECT
                contribution = 2.0
                evidence.append("Sizing conservative, but missed upside opportunity")
        else:
            rating = OutcomeRating.INCORRECT
            contribution = 1.0
            evidence.append(f"Sizing too large: experienced {max_drawdown:.1%} drawdown")
        
        evidence.append(f"Position size: {expected_position_size_pct:.1%}")
        
        return DimensionalOutcome(
            dimension=CorrectnessDimension.SIZING,
            rating=rating,
            contribution_pct=contribution,
            explanation=f"Position sizing: {expected_position_size_pct:.1%}. Return: {actual_return:.1%}, Max DD: {max_drawdown:.1%}",
            evidence=evidence,
        )
    
    def _aggregate_outcome(
        self,
        dimension_outcomes: List[DimensionalOutcome],
    ) -> Literal["confirmed", "partially_confirmed", "invalidated"]:
        """Aggregate outcome across multiple instances of same dimension."""
        if not dimension_outcomes:
            return "invalidated"
        
        correct_count = sum(1 for o in dimension_outcomes if o.rating == OutcomeRating.CORRECT)
        partial_count = sum(1 for o in dimension_outcomes if o.rating == OutcomeRating.PARTIALLY_CORRECT)
        
        total = len(dimension_outcomes)
        
        if correct_count >= total * 0.7:
            return "confirmed"
        elif (correct_count + partial_count) >= total * 0.5:
            return "partially_confirmed"
        else:
            return "invalidated"
    
    def generate_training_labels_from_attribution(
        self,
        attribution: TradeAttributionResult,
        feature_observation_id: str,
    ) -> List[TrainingLabel]:
        """
        Convert attribution result to training labels.
        
        Each dimension becomes a separate training example.
        """
        labels: List[TrainingLabel] = []
        
        for outcome in attribution.outcomes:
            # Convert rating to numeric label
            if outcome.rating == OutcomeRating.CORRECT:
                label_value = 1.0
            elif outcome.rating == OutcomeRating.PARTIALLY_CORRECT:
                label_value = 0.5
            else:
                label_value = 0.0
            
            # Weight by contribution
            label_value *= (outcome.contribution_pct / 100.0)
            
            label = TrainingLabel(
                observation_id=feature_observation_id,
                label_type=f"thesis_outcome_{outcome.dimension.value}",
                value=label_value,
                measured_at=attribution.created_at,
                horizon_days=attribution.duration_days,
                is_valid=True,
                quality_notes=f"Attribution: {outcome.explanation}",
            )
            labels.append(label)
        
        # Also create aggregate label
        thesis_labels = [o for o in attribution.outcomes if o.dimension == CorrectnessDimension.THESIS]
        if thesis_labels:
            thesis_value = sum(o.contribution_pct for o in thesis_labels if o.rating == OutcomeRating.CORRECT) / 100.0
            labels.append(
                TrainingLabel(
                    observation_id=feature_observation_id,
                    label_type="thesis_success",
                    value=thesis_value,
                    measured_at=attribution.created_at,
                    horizon_days=attribution.duration_days,
                    is_valid=True,
                    quality_notes="Aggregate thesis success label from attribution",
                )
            )
        
        return labels
