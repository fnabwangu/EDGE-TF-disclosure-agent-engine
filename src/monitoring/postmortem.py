"""postmortem.py
Closed trade taxonomy & calibration placeholder.
"""

def summarize_trade(trade):
    return {"trade_id": trade.get("id"), "outcome": "placeholder"}
# ==============================================================================
# PIPELINE STEP: CLOSED-TRADE DIAGNOSTIC & LEARNING ENGINE (postmortem.py)
# ==============================================================================
# Operational Goal: Classify closed trades across formal outcome taxonomies,
# isolate whether profit/loss arose from hypothesis vs. vehicle vs. signal mechanics,
# and write immutable diagnostic records to update the false-positive library.
# ==============================================================================

import json
from pathlib import Path
from datetime import datetime
import pandas as pd

def diagnose_closed_trade_pipeline(
    trade_summary: dict,
    market_benchmark_data: dict,
    storage_dir: str = "data/decision_records"
) -> dict:
    """
    Executes systematic postmortem diagnosis and archives structured decision records.
    
    Inputs:
      - trade_summary: Realized trade metrics (PnL, holding period, entry/exit state, vehicle type)
      - market_benchmark_data: Performance of functional benchmark, post-entry manager breadth delta, valuation shifts
      - storage_dir: Destination path for persistent JSON diagnostic files
    """
    trade_id = trade_summary["trade_id"]
    realized_pnl = trade_summary["realized_pnl_pct"]
    instrument_type = trade_summary["instrument_type"]
    benchmark_return = market_benchmark_data["function_benchmark_return"]
    breadth_delta = market_benchmark_data["post_entry_manager_breadth_delta"]
    valuation_compressed = market_benchmark_data.get("valuation_compressed", False)
    theta_drag_pct = trade_summary.get("theta_drag_pct", 0.0)

    # --------------------------------------------------------------------------
    # 1. EVALUATE HYPOTHESIS & SIGNAL INTEGRITY
    # --------------------------------------------------------------------------
    hypothesis_held = benchmark_return > 0.0
    signal_persisted = breadth_delta >= 0
    trade_profitable = realized_pnl > 0.0

    feedback_tags = []

    # --------------------------------------------------------------------------
    # 2. OUTCOME TAXONOMY CLASSIFICATION
    # --------------------------------------------------------------------------
    if hypothesis_held and signal_persisted:
        if trade_profitable:
            classification = "THESIS_CORRECT_IMPLEMENTATION_CORRECT"
            root_cause = "Strategic theme gained capital; vehicle captured expected asymmetry."
        else:
            if theta_drag_pct > 0.30:
                classification = "SIGNAL_CORRECT_TIMING_WRONG"
                root_cause = "Underlying theme worked, but option theta decay eroded premium before catalyst."
                feedback_tags.append("DERIVATIVE_DURATION_MISMATCH")
            elif valuation_compressed:
                classification = "SIGNAL_CORRECT_VALUATION_OVERRIDE"
                root_cause = "Adoption signal held, but severe valuation multiple contraction offset gains."
                feedback_tags.append("VALUATION_GATE_CONTAMINATION")
            else:
                classification = "THESIS_CORRECT_IMPLEMENTATION_WRONG"
                root_cause = "Theme performed, but selected vehicle lagged function peers."
                feedback_tags.append("VEHICLE_SELECTION_INEFFICIENCY")

    elif hypothesis_held and not signal_persisted:
        classification = "MANAGER_ADOPTION_REVERSED"
        root_cause = "Macro thesis held, but ETF institutional managers actively distributed shares."
        feedback_tags.append("PERSISTENCE_DECAY_FAILURE")

    elif not hypothesis_held and signal_persisted:
        classification = "SIGNAL_FALSE_POSITIVE"
        root_cause = "IAV indicated accumulation, but the underlying business function thesis failed."
        feedback_tags.append("FALSE_POSITIVE_IAV")

    else:  # Neither hypothesis nor signal held
        if instrument_type in ["CALL_SPREAD", "LEAP_CALL"] and not trade_profitable:
            classification = "THESIS_WRONG_IMPLEMENTATION_PROTECTED"
            root_cause = "Macro thesis and signal failed; defined-risk structure protected capital."
        else:
            classification = "THESIS_WRONG_IMPLEMENTATION_AMPLIFIED"
            root_cause = "Thesis failed and unhedged exposure or downside leverage amplified drawdown."
            feedback_tags.append("RISK_GOVERNOR_BREACH")

    # --------------------------------------------------------------------------
    # 3. DISCONFIRMATION & INVALIDATION ATTRIBUTION
    # --------------------------------------------------------------------------
    diagnostic_report = {
        "trade_id": trade_id,
        "thesis_id": trade_summary["thesis_id"],
        "canonical_id": trade_summary["canonical_id"],
        "timestamp": datetime.utcnow().isoformat(),
        "classification": classification,
        "metrics": {
            "realized_pnl_pct": realized_pnl,
            "holding_period_days": trade_summary["holding_period_days"],
            "hypothesis_validated": hypothesis_held,
            "signal_validated": signal_persisted,
            "implementation_effective": trade_profitable and (realized_pnl >= benchmark_return),
            "exit_reason": trade_summary["exit_reason"]
        },
        "root_cause_analysis": root_cause,
        "model_feedback_tags": feedback_tags
    }

    # --------------------------------------------------------------------------
    # 4. FEEDBACK LOOP TO FALSE-POSITIVE ARCHIVE
    # --------------------------------------------------------------------------
    output_path = Path(storage_dir) / f"postmortem_{trade_id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(diagnostic_report, f, indent=2)

    """
Edge-TF Disclosure Agent Engine - Trade Postmortem & Diagnostic System
Path: src/monitoring/postmortem.py

Classifies closed trades, diagnoses failure/success topologies, assesses
hypothesis versus implementation accuracy, and updates the false-positive archive.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from enum import Enum
from typing import Dict, List, Optional, Any
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PostmortemClassification(str, Enum):
    """Formal diagnostic outcome taxonomy for closed trades."""
    THESIS_CORRECT_IMPLEMENTATION_CORRECT = "THESIS_CORRECT_IMPLEMENTATION_CORRECT"
    THESIS_CORRECT_IMPLEMENTATION_WRONG = "THESIS_CORRECT_IMPLEMENTATION_WRONG"
    THESIS_WRONG_IMPLEMENTATION_PROTECTED = "THESIS_WRONG_IMPLEMENTATION_PROTECTED"
    THESIS_WRONG_IMPLEMENTATION_AMPLIFIED = "THESIS_WRONG_IMPLEMENTATION_AMPLIFIED"
    SIGNAL_CORRECT_TIMING_WRONG = "SIGNAL_CORRECT_TIMING_WRONG"
    SIGNAL_CORRECT_VALUATION_OVERRIDE = "SIGNAL_CORRECT_VALUATION_OVERRIDE"
    SIGNAL_FALSE_POSITIVE = "SIGNAL_FALSE_POSITIVE"
    SIGNAL_ARRIVED_LATE = "SIGNAL_ARRIVED_LATE"
    OPTIONS_CONFIRMATION_FALSE = "OPTIONS_CONFIRMATION_FALSE"
    MANAGER_ADOPTION_REVERSED = "MANAGER_ADOPTION_REVERSED"
    EXIT_PREMATURE = "EXIT_PREMATURE"
    EXIT_LATE = "EXIT_LATE"


class ExitReason(str, Enum):
    """Primary trigger responsible for trade termination."""
    THESIS_INVALIDATION = "THESIS_INVALIDATION"
    DISCLOSURE_DETERIORATION = "DISCLOSURE_DETERIORATION"
    VALUATION_COMPLETION = "VALUATION_COMPLETION"
    TRADE_STRUCTURE_DECAY = "TRADE_STRUCTURE_DECAY"
    RISK_BUDGET_STOP = "RISK_BUDGET_STOP"
    TAKE_PROFIT = "TAKE_PROFIT"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"


@dataclass
class TradeContext:
    """Historical context snapshot at the time of trade execution."""
    trade_id: str
    thesis_id: str
    canonical_id: str
    strategic_function: str
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    realized_pnl_pct: float
    holding_period_days: int
    instrument_type: str  # EQUITY, ETF, LEAP_CALL, CALL_SPREAD
    entry_iav_score: float
    entry_manager_breadth: int
    entry_adoption_state: str
    exit_reason: ExitReason


@dataclass
class DiagnosticReport:
    """Complete postmortem record written to the immutable decision log."""
    trade_id: str
    thesis_id: str
    canonical_id: str
    classification: PostmortemClassification
    hypothesis_validated: bool
    signal_validated: bool
    implementation_effective: bool
    exit_reason: ExitReason
    realized_pnl_pct: float
    holding_period_days: int
    root_cause_analysis: str
    model_feedback_tags: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class TradePostmortemEngine:
    """
    Evaluates completed trade lifecycles and archives structured postmortems.
    """

    def __init__(self, records_directory: str = "data/decision_records"):
        self.records_dir = Path(records_directory)
        self.records_dir.mkdir(parents=True, exist_ok=True)

    def diagnose(
        self,
        context: TradeContext,
        function_benchmark_return: float,
        post_entry_manager_breadth_delta: int,
        valuation_multiple_expansion: bool,
        options_theta_drag_pct: float = 0.0,
    ) -> DiagnosticReport:
        """
        Executes systematic rule-based diagnosis of closed trade performance.
        """
        # Determine whether underlying strategic function hypothesis held
        hypothesis_validated = function_benchmark_return > 0.0
        
        # Determine whether ETF manager adoption continued post-entry
        signal_validated = post_entry_manager_breadth_delta >= 0
        
        # Determine whether the vehicle implementation was accretive
        trade_profitable = context.realized_pnl_pct > 0.0
        implementation_effective = trade_profitable and (
            context.realized_pnl_pct >= function_benchmark_return
        )

        feedback_tags: List[str] = []

        # ----------------------------------------------------------------------
        # DIAGNOSTIC TAXONOMY ROUTING
        # ----------------------------------------------------------------------
        if hypothesis_validated and signal_validated:
            if trade_profitable:
                classification = PostmortemClassification.THESIS_CORRECT_IMPLEMENTATION_CORRECT
                root_cause = "Strategic function gained capital; vehicle captured asymmetric upside."
            else:
                if options_theta_drag_pct > 0.30:
                    classification = PostmortemClassification.SIGNAL_CORRECT_TIMING_WRONG
                    root_cause = "Thesis progressed, but derivative theta decay eroded premium before catalyst."
                    feedback_tags.append("DERIVATIVE_DURATION_MISMATCH")
                elif not valuation_multiple_expansion:
                    classification = PostmortemClassification.SIGNAL_CORRECT_VALUATION_OVERRIDE
                    root_cause = "Adoption continued, but severe valuation compression offset fundamentals."
                    feedback_tags.append("VALUATION_GATE_CONTAMINATION")
                else:
                    classification = PostmortemClassification.THESIS_CORRECT_IMPLEMENTATION_WRONG
                    root_cause = "Strategic theme outperformed, but selected vehicle underperformed peers."
                    feedback_tags.append("VEHICLE_SELECTION_INEFFICIENCY")

        elif hypothesis_validated and not signal_validated:
            classification = PostmortemClassification.MANAGER_ADOPTION_REVERSED
            root_cause = "Theme performed, but ETF manager adoption stalled or entered active distribution."
            feedback_tags.append("PERSISTENCE_DECAY_FAILURE")

        elif not hypothesis_validated and signal_validated:
            classification = PostmortemClassification.SIGNAL_FALSE_POSITIVE
            root_cause = "ETF adoption signals appeared robust, but the macroeconomic/function thesis failed."
            feedback_tags.append("FALSE_POSITIVE_IAV")

        else:  # Neither hypothesis nor signal held
            if context.instrument_type in ["CALL_SPREAD", "LEAP_CALL"] and not trade_profitable:
                classification = PostmortemClassification.THESIS_WRONG_IMPLEMENTATION_PROTECTED
                root_cause = "Thesis failed; defined-risk structure capped maximum aggregate loss."
            else:
                classification = PostmortemClassification.THESIS_WRONG_IMPLEMENTATION_AMPLIFIED
                root_cause = "Thesis failed and unhedged exposure or excessive volatility amplified drawdown."
                feedback_tags.append("RISK_GOVERNOR_BREACH")

        # Refine for exit timing anomalies
        if context.exit_reason == ExitReason.DISCLOSURE_DETERIORATION and trade_profitable:
            feedback_tags.append("SUCCESSFUL_EARLY_DISTRIBUTION_EXIT")

        report = DiagnosticReport(
            trade_id=context.trade_id,
            thesis_id=context.thesis_id,
            canonical_id=context.canonical_id,
            classification=classification,
            hypothesis_validated=hypothesis_validated,
            signal_validated=signal_validated,
            implementation_effective=implementation_effective,
            exit_reason=context.exit_reason,
            realized_pnl_pct=context.realized_pnl_pct,
            holding_period_days=context.holding_period_days,
            root_cause_analysis=root_cause,
            model_feedback_tags=feedback_tags,
        )

        self._archive_report(report)
        return report

    def _archive_report(self, report: DiagnosticReport) -> None:
        """
        Persists diagnostic output as an immutable JSON decision record.
        """
        file_path = self.records_dir / f"postmortem_{report.trade_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(asdict(report), f, indent=2)
            logger.info(f"Archived postmortem record for trade {report.trade_id} -> {file_path}")
        except Exception as e:
            logger.error(f"Failed to archive postmortem record for {report.trade_id}: {e}")

    return diagnostic_report
