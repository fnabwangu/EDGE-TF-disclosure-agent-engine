"""
Edge-TF Disclosure Agent Engine - Dynamic Exposure Controller
Path: analytics/dynamic_exposure_controller.py

Orchestrates staged leverage entry, independent risk caps, tranche
accounting, and profit-protected exit into one deterministic per-period
update:

    TargetExposure_t = min(SignalExposure_t, RiskExposure_t, ProfitProtectedExposure_t)

Evidence-state improvements only ever open the door to more leverage
(SignalExposure, via a SignalLeverageGate -- CapitalFlowSignalGate's banded,
config-driven capital-flow curve by default, or the legacy flat
StagedLeverageGate/LeveragePolicy if explicitly supplied). Risk caps
(LeverageEngine) and profit-taking (ProfitTakingEngine +
ExposureReductionEngine) can always cut exposure below that door regardless
of conviction. New tranches are only opened for the incremental leverage
newly unlocked; exits unwind the highest-risk tranches first.

Profit-taking operates on the *leveraged* return (underlying_return *
current_leverage), not the sleeve's raw unlevered price return -- an 8%
underlying move at 6x exposure is a 48% move on the capital actually at risk,
and must be evaluated as such by the harvest ladder.

Once a harvest actually removes leverage, the resulting lower leverage
becomes a persistent ``profit_protected_leverage_cap`` -- the standing signal
target alone can never re-add the harvested exposure. That cap is only
released when fresh evidence arrives: the evidence state ranks higher than it
did when the cap was set, or flow_progress has increased since then.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from analytics.capital_flow_leverage_engine import CapitalFlowSignalGate
from analytics.leverage_engine import LeverageDecision, LeverageEngine
from analytics.leverage_tranches import EVIDENCE_STATE_RANK, EvidenceState, LeverageTranche, TrancheBook
from analytics.profit_taking_engine import ProfitTakingEngine
from analytics.staged_leverage_gate import SignalLeverageGate, StagedLeverageInputs
from core.schemas import LeverageLimits, ProfitTakingInputs, ProfitTakingResult
from risk.exposure_reduction_engine import ExposureReductionEngine, ExposureReductionResult


@dataclass(frozen=True)
class DynamicExposureResult:
    """Full audit trail of one evaluation period's scale-in/scale-out decision."""

    leverage_before: float
    signal_target_leverage: float
    risk_capped_leverage: float
    tranche_added: float
    underlying_return: float
    leveraged_return: float
    profit_decision: ProfitTakingResult
    reduction_result: ExposureReductionResult
    leverage_after: float
    profit_protected_leverage_cap: Optional[float]
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
        self.staged_gate: SignalLeverageGate = staged_gate or CapitalFlowSignalGate()
        self.leverage_engine = leverage_engine or LeverageEngine()
        self.profit_engine = profit_engine or ProfitTakingEngine()
        self.book = book or TrancheBook()

        # Persistent harvest ceiling: once profit-taking removes leverage, the
        # resulting level becomes a standing cap until fresh evidence earns it back.
        self.profit_protected_leverage_cap: Optional[float] = None
        self._cap_evidence_rank: Optional[int] = None
        self._cap_flow_progress: Optional[float] = None

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
        underlying_return: float,
        generic_projected_return: float,
        event_probability: float = 1.0,
        flow_progress: float = 0.0,
    ) -> DynamicExposureResult:
        reason_codes: List[str] = []
        leverage_before = self.book.current_leverage
        current_rank = EVIDENCE_STATE_RANK[evidence_state]

        # 0. Release any standing harvest ceiling only on genuinely fresh evidence:
        # a higher-ranked evidence state, or continued progress within/above the
        # state the cap was set at. The standing signal target alone never does this.
        if self.profit_protected_leverage_cap is not None:
            fresh_evidence = (self._cap_evidence_rank is not None and current_rank > self._cap_evidence_rank) or (
                self._cap_flow_progress is not None and flow_progress > self._cap_flow_progress + 1e-9
            )
            if fresh_evidence:
                self.profit_protected_leverage_cap = None
                self._cap_evidence_rank = None
                self._cap_flow_progress = None
                reason_codes.append("PROFIT_PROTECTED_CAP_RELEASED_FRESH_EVIDENCE")
            else:
                reason_codes.append("PROFIT_PROTECTED_CAP_ACTIVE")

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

        # 3. ProfitProtectedExposure ceiling: a still-active harvest cap can only
        # ever tighten this period's ceiling further, never loosen it.
        effective_ceiling = risk_capped_leverage
        if self.profit_protected_leverage_cap is not None:
            effective_ceiling = min(effective_ceiling, self.profit_protected_leverage_cap)

        # 4. Open a new tranche only for the incremental leverage newly unlocked.
        tranche_added = 0.0
        if staged_decision.entry_permitted and effective_ceiling > leverage_before:
            tranche_added = effective_ceiling - leverage_before
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

        # 5. Harvesting/exit can only ever reduce exposure further. Profit-taking
        # sees the LEVERAGED return on capital at risk, not the sleeve's raw
        # underlying price return.
        leveraged_return = underlying_return * self.book.current_leverage
        profit_decision = self.profit_engine.evaluate(
            ProfitTakingInputs(
                current_return=leveraged_return,
                generic_projected_return=generic_projected_return,
                remaining_ev=remaining_ev,
                minimum_remaining_ev=minimum_remaining_ev,
                thesis_active=thesis_active,
                catalyst_active=catalyst_active,
                invalidation_intact=invalidation_intact,
                leverage=max(self.book.current_leverage, 1e-9),
                original_capital=base_strategy_notional,
                current_position_value=base_strategy_notional * (1.0 + leveraged_return),
            )
        )
        reduction_result = ExposureReductionEngine.apply(self.book, profit_decision, current_time, current_price)
        reason_codes.extend(profit_decision.reason_codes)

        # 6. A harvest that actually removed leverage establishes/tightens the
        # persistent ceiling at the new, lower level.
        if reduction_result.leverage_removed > 0.0:
            self.profit_protected_leverage_cap = self.book.current_leverage
            self._cap_evidence_rank = current_rank
            self._cap_flow_progress = flow_progress
            reason_codes.append("PROFIT_PROTECTED_CAP_ESTABLISHED")

        return DynamicExposureResult(
            leverage_before=leverage_before,
            signal_target_leverage=staged_decision.signal_target_leverage,
            risk_capped_leverage=risk_capped_leverage,
            tranche_added=tranche_added,
            underlying_return=underlying_return,
            leveraged_return=leveraged_return,
            profit_decision=profit_decision,
            reduction_result=reduction_result,
            leverage_after=self.book.current_leverage,
            profit_protected_leverage_cap=self.profit_protected_leverage_cap,
            reason_codes=reason_codes,
        )


__all__ = ["DynamicExposureResult", "DynamicExposureController"]
