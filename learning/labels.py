"""
Outcome labeling for supervised learning.

Path: learning/labels.py

After a trade or thesis completes, EDGE labels outcomes from multiple angles:
- Was the thesis right? (conceptual correctness)
- Was the instrument right? (selection correctness)
- Was the timing right? (entry/exit correctness)
- Was the hedge right? (protection effectiveness)
- Was sizing right? (risk management correctness)

These multi-dimensional labels are richer training signal than binary win/loss.
"""

from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Literal
from dataclasses import dataclass, field

from learning.schemas import TrainingLabel


@dataclass
class ThesisOutcomeAssessment:
    """Detailed outcome breakdown for a thesis/trade."""
    thesis_id: str
    exit_date: date
    actual_return: float
    max_drawdown: float
    duration_days: int
    
    # Multi-dimensional outcome assessment
    thesis_correctness: Literal["correct", "partially_correct", "incorrect"]
    instrument_correctness: Literal["correct", "partially_correct", "incorrect"]
    timing_correctness: Literal["correct", "partially_correct", "incorrect"]
    hedge_effectiveness: Literal["effective", "partially_effective", "ineffective"]
    sizing_appropriateness: Literal["appropriate", "too_small", "too_large"]
    
    # Attribution
    thesis_contribution: float = 0.0  # attribution to thesis being right
    instrument_contribution: float = 0.0  # attribution to instrument being right
    timing_contribution: float = 0.0  # attribution to timing being right
    hedge_contribution: float = 0.0  # attribution to hedge effectiveness
    sizing_contribution: float = 0.0  # attribution to sizing
    unexplained: float = 0.0  # residual
    
    notes: Optional[str] = None


class OutcomeLabelingService:
    """
    Assigns training labels from trade/thesis outcomes.
    
    Creates multiple supervised training examples from a single trade outcome
    by breaking down the return attribution across different decision dimensions.
    """
    
    def label_trade_outcome(
        self,
        thesis_id: str,
        entry_date: date,
        exit_date: date,
        entry_price: float,
        exit_price: float,
        max_price_during_trade: float,
        min_price_during_trade: float,
        expected_return_target: float,
        expected_hedge_cost: float,
        realized_hedge_cost: float,
        expected_thesis_description: str,
        actual_outcome_description: str,
    ) -> tuple[ThesisOutcomeAssessment, List[TrainingLabel]]:
        """
        Generate comprehensive outcome assessment and training labels.
        
        Returns:
            (ThesisOutcomeAssessment, List[TrainingLabel]) where labels
            are indexed by observation features from when thesis was created.
        """
        # Compute metrics
        actual_return = (exit_price - entry_price) / entry_price
        drawdown = (min_price_during_trade - entry_price) / entry_price
        duration = (exit_date - entry_date).days
        
        # Qualitative assessment of each dimension
        # This is where domain expertise enters: analysts manually assess outcomes
        thesis_correct = self._assess_thesis_correctness(
            expected_thesis_description,
            actual_outcome_description,
        )
        instrument_correct = self._assess_instrument_correctness(
            expected_return_target,
            actual_return,
        )
        timing_correct = self._assess_timing_correctness(
            duration,
            expected_return_target,
        )
        hedge_effective = self._assess_hedge_effectiveness(
            expected_hedge_cost,
            realized_hedge_cost,
            drawdown,
        )
        sizing_appropriate = self._assess_sizing(actual_return, expected_return_target)
        
        # Attribution: decompose return across dimensions
        # In practice, this uses regression or domain judgment
        attribution = self._decompose_return(
            actual_return=actual_return,
            expected_return=expected_return_target,
            realized_drawdown=drawdown,
            hedge_cost_variance=realized_hedge_cost - expected_hedge_cost,
            thesis_correctness_score=self._correctness_to_score(thesis_correct),
            instrument_correctness_score=self._correctness_to_score(instrument_correct),
            timing_correctness_score=self._correctness_to_score(timing_correct),
            hedge_effectiveness_score=self._correctness_to_score(hedge_effective),
        )
        
        assessment = ThesisOutcomeAssessment(
            thesis_id=thesis_id,
            exit_date=exit_date,
            actual_return=actual_return,
            max_drawdown=abs(drawdown),
            duration_days=duration,
            thesis_correctness=thesis_correct,
            instrument_correctness=instrument_correct,
            timing_correctness=timing_correct,
            hedge_effectiveness=hedge_effective,
            sizing_appropriateness=sizing_appropriate,
            thesis_contribution=attribution["thesis"],
            instrument_contribution=attribution["instrument"],
            timing_contribution=attribution["timing"],
            hedge_contribution=attribution["hedge"],
            sizing_contribution=attribution["sizing"],
            unexplained=attribution["unexplained"],
        )
        
        # Create training labels
        # These will be matched back to feature observations from entry_date
        labels = [
            TrainingLabel(
                observation_id=thesis_id,  # Will be joined to features by thesis_id
                label_type="return",
                value=actual_return,
                measured_at=datetime.combine(exit_date, datetime.min.time()).replace(tzinfo=timezone.utc),
                horizon_days=duration,
                is_valid=True,
                quality_notes=f"Actual return: {actual_return:.2%}",
            ),
            TrainingLabel(
                observation_id=thesis_id,
                label_type="drawdown",
                value=abs(drawdown),
                measured_at=datetime.combine(exit_date, datetime.min.time()).replace(tzinfo=timezone.utc),
                horizon_days=duration,
                is_valid=True,
                quality_notes=f"Max drawdown during trade: {drawdown:.2%}",
            ),
            TrainingLabel(
                observation_id=thesis_id,
                label_type="thesis_success",
                value=self._correctness_to_score(thesis_correct),
                measured_at=datetime.combine(exit_date, datetime.min.time()).replace(tzinfo=timezone.utc),
                horizon_days=duration,
                is_valid=True,
                quality_notes=f"Thesis assessment: {thesis_correct}",
            ),
            TrainingLabel(
                observation_id=thesis_id,
                label_type="hedge_effectiveness",
                value=self._correctness_to_score(hedge_effective),
                measured_at=datetime.combine(exit_date, datetime.min.time()).replace(tzinfo=timezone.utc),
                horizon_days=duration,
                is_valid=True,
                quality_notes=f"Hedge effectiveness: {hedge_effective}. Expected cost: {expected_hedge_cost:.2%}, Realized: {realized_hedge_cost:.2%}",
            ),
        ]
        
        return assessment, labels
    
    def _assess_thesis_correctness(
        self,
        expected_description: str,
        actual_outcome: str,
    ) -> Literal["correct", "partially_correct", "incorrect"]:
        """
        Qualitative assessment of whether the thesis premise was validated.
        
        In practice, a human or domain-specific heuristic evaluates this.
        """
        # Placeholder: in production, this would be a human review or LLM-assisted
        if "confirmed" in actual_outcome.lower():
            return "correct"
        elif "partially" in actual_outcome.lower():
            return "partially_correct"
        else:
            return "incorrect"
    
    def _assess_instrument_correctness(
        self,
        expected_return: float,
        actual_return: float,
    ) -> Literal["correct", "partially_correct", "incorrect"]:
        """Was the chosen instrument the right one for the thesis?"""
        # Achieved close to expected return
        if abs(actual_return - expected_return) / max(0.01, abs(expected_return)) < 0.3:
            return "correct"
        # Achieved some reasonable return
        elif abs(actual_return) > 0.05:
            return "partially_correct"
        else:
            return "incorrect"
    
    def _assess_timing_correctness(
        self,
        duration_days: int,
        expected_return: float,
    ) -> Literal["correct", "partially_correct", "incorrect"]:
        """Was the entry/exit timing appropriate?"""
        # Fast profit = good timing
        if duration_days < 30 and expected_return > 0.05:
            return "correct"
        # Reasonable duration = adequate timing
        elif 30 <= duration_days <= 180:
            return "partially_correct"
        # Very long or short with small return = poor timing
        else:
            return "incorrect"
    
    def _assess_hedge_effectiveness(
        self,
        expected_cost: float,
        realized_cost: float,
        actual_drawdown: float,
    ) -> Literal["effective", "partially_effective", "ineffective"]:
        """Did the hedge do its job?"""
        cost_variance = realized_cost - expected_cost
        # Hedge cost was reasonable and drawdown was controlled
        if abs(cost_variance) < expected_cost * 0.3 and actual_drawdown < 0.10:
            return "effective"
        # Some cost variance but drawdown still controlled
        elif actual_drawdown < 0.15:
            return "partially_effective"
        else:
            return "ineffective"
    
    def _assess_sizing(
        self,
        actual_return: float,
        expected_return: float,
    ) -> Literal["appropriate", "too_small", "too_large"]:
        """Was the position size right relative to risk/reward?"""
        ratio = actual_return / max(0.01, abs(expected_return))
        if 0.7 <= ratio <= 1.3:
            return "appropriate"
        elif ratio < 0.7:
            return "too_small"
        else:
            return "too_large"
    
    def _correctness_to_score(self, correctness: str) -> float:
        """Convert qualitative assessment to numeric score [0, 1]."""
        mapping = {
            "correct": 1.0,
            "effective": 1.0,
            "appropriate": 1.0,
            "partially_correct": 0.5,
            "partially_effective": 0.5,
            "too_small": 0.5,
            "too_large": 0.5,
            "incorrect": 0.0,
            "ineffective": 0.0,
        }
        return mapping.get(correctness, 0.0)
    
    def _decompose_return(
        self,
        actual_return: float,
        expected_return: float,
        realized_drawdown: float,
        hedge_cost_variance: float,
        thesis_correctness_score: float,
        instrument_correctness_score: float,
        timing_correctness_score: float,
        hedge_effectiveness_score: float,
    ) -> Dict[str, float]:
        """
        Decompose realized return into contributions from each dimension.
        
        Simple attribution model: weight correctness scores by their relative importance.
        In production, use regression or Shapley values.
        """
        scores = {
            "thesis": thesis_correctness_score,
            "instrument": instrument_correctness_score,
            "timing": timing_correctness_score,
            "hedge": hedge_effectiveness_score,
        }
        
        total_score = sum(scores.values())
        if total_score == 0:
            total_score = 1.0  # Avoid division by zero
        
        # Allocate return proportionally to correctness
        contribution = {}
        for key, score in scores.items():
            contribution[key] = actual_return * (score / total_score)
        
        # Account for hedge cost variance
        contribution["hedge"] -= abs(hedge_cost_variance)
        
        # Sizing contribution
        sizing_score = 0.5  # Placeholder
        contribution["sizing"] = realized_drawdown * sizing_score
        
        # Unexplained (residual)
        total_allocated = sum(contribution.values())
        contribution["unexplained"] = actual_return - total_allocated
        
        return contribution
