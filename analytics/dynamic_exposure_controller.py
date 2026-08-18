"""
Edge-TF Disclosure Agent Engine - Dynamic Exposure Controller
Path: analytics/dynamic_exposure_controller.py

Orchestrates staged leverage entry, independent risk caps, tranche
accounting, and profit-protected exit into one deterministic per-period
update:

    TargetExposure_t = min(SignalExposure_t, RiskExposure_t, ProfitProtectedExposure_t)

Evidence-state improvements only ever open the door to more leverage
(SignalExposure, via a SignalLeverageGate -- StagedLeverageGate's flat,
conservative policy by default, or an opt-in alternative such as
CapitalFlowSignalGate for an aggressive banded policy). Risk caps
(LeverageEngine) and profit-taking (ProfitTakingEngine +
ExposureReductionEngine) can always cut exposure below that door regardless
of conviction. New tranches are only opened for the incremental leverage
newly unlocked; exits unwind the highest-risk tranches first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from analytics.leverage_engine import LeverageDecision, LeverageEngine
from analytics.leverage_tranches import EvidenceState, LeverageTranche, TrancheBook
from analytics.profit_taking_engine import ProfitTakingEngine
from analytics.staged_leverage_gate import SignalLeverageGate, StagedLeverageGate, StagedLeverageInputs
from core.schemas import LeverageLimits, ProfitTakingInputs, ProfitTakingResult
from risk.exposure_reduction_engine import ExposureReductionEngine, ExposureReductionResult


@dataclass(frozen=True)
class DynamicExposureResult:
    """Full audit trail of one evaluation period's scale-in/scale-out decision."""

    leverage_before: float
    signal_target_leverage: float
    risk_capped_leverage: float
    tranche_added: float
    profit_decision: ProfitTakingResult
    reduction_result: ExposureReductionResult
    leverage_after: float
    reason_codes: List[str] = field(default_factory=list)


class DynamicExposureController:
    """Steps one evaluation period, scaling a TrancheBook's leverage in or out."""

    def __init__(
        self,
        staged_gate: Optional[SignalLeverageGate] = None,
        leverage_engine: Optional[LeverageEngine] = None,
        profit_engine: Optional[ProfitTakingEngine] = None,
        book: Optional[TrancheBook] = None,
    ):
        self.staged_gate: SignalLeverageGate = staged_gate or StagedLeverageGate()
        self.leverage_engine = leverage_engine or LeverageEngine()
        self.profit_engine = profit_engine or ProfitTakingEngine()
        self.book = book or TrancheBook()

    def update(
        self,
        *,
        current_time: datetime,
        current_price: float,
        evidence_state: EvidenceState,
        evidence_score: float,
        remaining_ev: float,
        minimum_remaining_ev: float,
        thesis_active: bool,
        catalyst_active: bool,
        invalidation_intact: bool,
        market_confirmation: bool,
        leverage_limits: LeverageLimits,
        worst_case_loss_pct: float,
        strategy_volatility: float,
        base_strategy_notional: float,
        maximum_executable_notional: float,
        current_return: float,
        generic_projected_return: float,
        event_probability: float = 1.0,
        flow_progress: float = 0.0,
    ) -> DynamicExposureResult:
        reason_codes: List[str] = []
        leverage_before = self.book.current_leverage

        # 1. SignalExposure: evidence state only opens the door to more leverage.
        staged_decision = self.staged_gate.evaluate(
            StagedLeverageInputs(
                evidence_state=evidence_state,
                remaining_ev=remaining_ev,
                minimum_remaining_ev=minimum_remaining_ev,
                thesis_active=thesis_active,
                catalyst_active=catalyst_active,
                market_confirmation=market_confirmation,
                event_probability=event_probability,
                flow_progress=flow_progress,
            )
        )
        reason_codes.extend(staged_decision.reason_codes)

        # 2. RiskExposure: independent loss/volatility/liquidity/portfolio caps.
        risk_decision: LeverageDecision = self.leverage_engine.evaluate(
            requested_leverage=staged_decision.signal_target_leverage,
            limits=leverage_limits,
            worst_case_loss_pct=worst_case_loss_pct,
            strategy_volatility=strategy_volatility,
            base_strategy_notional=base_strategy_notional,
            maximum_executable_notional=maximum_executable_notional,
        )
        reason_codes.extend(risk_decision.reason_codes)
        risk_capped_leverage = risk_decision.approved_leverage

        # 3. Open a new tranche only for the incremental leverage newly unlocked.
        tranche_added = 0.0
        if staged_decision.entry_permitted and risk_capped_leverage > leverage_before:
            tranche_added = risk_capped_leverage - leverage_before
            self.book.add_tranche(
                LeverageTranche(
                    tranche_id=str(uuid4()),
                    evidence_state=evidence_state,
                    entry_time=current_time,
                    entry_price=current_price,
                    leverage_added=tranche_added,
                    entry_remaining_ev=remaining_ev,
                    entry_evidence_score=evidence_score,
                )
            )
            reason_codes.append("TRANCHE_ADDED")

        # 4. ProfitProtectedExposure: harvesting/exit can only ever reduce exposure.
        profit_decision = self.profit_engine.evaluate(
            ProfitTakingInputs(
                current_return=current_return,
                generic_projected_return=generic_projected_return,
                remaining_ev=remaining_ev,
                minimum_remaining_ev=minimum_remaining_ev,
                thesis_active=thesis_active,
                catalyst_active=catalyst_active,
                invalidation_intact=invalidation_intact,
                leverage=max(self.book.current_leverage, 1e-9),
                original_capital=base_strategy_notional,
                current_position_value=base_strategy_notional * (1.0 + current_return),
            )
        )
        reduction_result = ExposureReductionEngine.apply(self.book, profit_decision, current_time, current_price)
        reason_codes.extend(profit_decision.reason_codes)

        return DynamicExposureResult(
            leverage_before=leverage_before,
            signal_target_leverage=staged_decision.signal_target_leverage,
            risk_capped_leverage=risk_capped_leverage,
            tranche_added=tranche_added,
            profit_decision=profit_decision,
            reduction_result=reduction_result,
            leverage_after=self.book.current_leverage,
            reason_codes=reason_codes,
        )


__all__ = ["DynamicExposureResult", "DynamicExposureController"]
