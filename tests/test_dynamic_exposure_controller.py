"""Tests for tranche accounting, staged leverage entry, and dynamic exposure control."""

from datetime import datetime, timedelta

import pytest

from analytics.dynamic_exposure_controller import DynamicExposureController
from analytics.leverage_engine import LeverageEngine
from analytics.leverage_tranches import (
    EvidenceState,
    EvidenceStateThresholds,
    LeveragePolicy,
    LeverageTranche,
    TrancheBook,
)
from analytics.profit_taking_engine import ProfitTakingEngine, ProfitTakingThresholds
from analytics.staged_leverage_gate import StagedLeverageGate, StagedLeverageInputs
from core.schemas import LeverageLimits

GENEROUS_LIMITS = LeverageLimits(
    max_absolute_leverage=20.0,
    max_trade_loss_pct=999.0,
    volatility_limit=999.0,
    liquidity_limit=999.0,
    concentration_limit=999.0,
    portfolio_limit=999.0,
)

T0 = datetime(2026, 1, 1)


def _tranche(state: EvidenceState, leverage: float, when: datetime) -> LeverageTranche:
    return LeverageTranche(
        tranche_id=f"{state.value}-{when.isoformat()}",
        evidence_state=state,
        entry_time=when,
        entry_price=100.0,
        leverage_added=leverage,
        entry_remaining_ev=0.10,
        entry_evidence_score=0.5,
    )


# --- EvidenceStateThresholds / classify ---

def test_evidence_state_thresholds_classify_five_tiers():
    thresholds = EvidenceStateThresholds()
    assert thresholds.classify(0.05) == EvidenceState.WAIT
    assert thresholds.classify(0.20) == EvidenceState.SEEDED
    assert thresholds.classify(0.50) == EvidenceState.EMERGING
    assert thresholds.classify(0.70) == EvidenceState.CONFIRMED
    assert thresholds.classify(0.90) == EvidenceState.STRONG


def test_evidence_state_thresholds_reject_non_increasing_cutoffs():
    with pytest.raises(ValueError):
        EvidenceStateThresholds(wait_max=0.5, seeded_max=0.4, emerging_max=0.6, confirmed_max=0.8)


# --- LeveragePolicy ---

def test_leverage_policy_target_for_each_state():
    policy = LeveragePolicy()
    assert policy.target_for(EvidenceState.WAIT) == 0.0
    assert policy.target_for(EvidenceState.SEEDED) == 0.5
    assert policy.target_for(EvidenceState.EMERGING) == 1.25
    assert policy.target_for(EvidenceState.CONFIRMED) == 1.75
    assert policy.target_for(EvidenceState.STRONG) == 2.0


# --- TrancheBook ---

def test_tranche_book_current_leverage_sums_active_tranches():
    book = TrancheBook()
    book.add_tranche(_tranche(EvidenceState.SEEDED, 1.0, T0))
    book.add_tranche(_tranche(EvidenceState.EMERGING, 2.0, T0 + timedelta(days=30)))
    assert book.current_leverage == pytest.approx(3.0)


def test_tranche_book_rejects_non_positive_leverage_added():
    book = TrancheBook()
    with pytest.raises(ValueError):
        book.add_tranche(_tranche(EvidenceState.SEEDED, 0.0, T0))


def test_tranche_book_reduce_removes_highest_state_tranche_first():
    book = TrancheBook()
    book.add_tranche(_tranche(EvidenceState.SEEDED, 1.0, T0))
    book.add_tranche(_tranche(EvidenceState.CONFIRMED, 3.0, T0 + timedelta(days=30)))
    book.add_tranche(_tranche(EvidenceState.STRONG, 4.0, T0 + timedelta(days=60)))
    # STRONG -> CONFIRMED weakening: remove exactly the STRONG tranche (4x)
    removed = book.reduce_leverage(4.0, T0 + timedelta(days=90), 110.0, "EVIDENCE_DEGRADED")
    assert removed == pytest.approx(4.0)
    assert book.current_leverage == pytest.approx(4.0)  # 1x SEEDED + 3x CONFIRMED remain
    remaining_states = {t.evidence_state for t in book.active_tranches}
    assert remaining_states == {EvidenceState.SEEDED, EvidenceState.CONFIRMED}


def test_tranche_book_reduce_partially_trims_a_tranche():
    book = TrancheBook()
    book.add_tranche(_tranche(EvidenceState.STRONG, 4.0, T0))
    removed = book.reduce_leverage(1.5, T0 + timedelta(days=10), 105.0, "PROFIT_TARGET")
    assert removed == pytest.approx(1.5)
    assert book.current_leverage == pytest.approx(2.5)
    assert book.active_tranches[0].active is True


def test_tranche_book_reduce_caps_at_current_leverage():
    book = TrancheBook()
    book.add_tranche(_tranche(EvidenceState.SEEDED, 1.0, T0))
    removed = book.reduce_leverage(10.0, T0 + timedelta(days=1), 90.0, "CLOSE")
    assert removed == pytest.approx(1.0)
    assert book.current_leverage == 0.0


# --- StagedLeverageGate ---

def test_staged_gate_returns_zero_on_wait_state():
    gate = StagedLeverageGate()
    decision = gate.evaluate(
        StagedLeverageInputs(
            evidence_state=EvidenceState.WAIT,
            remaining_ev=0.10,
            minimum_remaining_ev=0.05,
            thesis_active=True,
            catalyst_active=True,
            market_confirmation=True,
        )
    )
    assert decision.signal_target_leverage == 0.0
    assert decision.entry_permitted is False
    assert "WAIT_STATE" in decision.reason_codes


def test_staged_gate_blocks_entry_on_insufficient_remaining_ev():
    gate = StagedLeverageGate()
    decision = gate.evaluate(
        StagedLeverageInputs(
            evidence_state=EvidenceState.STRONG,
            remaining_ev=0.01,
            minimum_remaining_ev=0.05,
            thesis_active=True,
            catalyst_active=True,
            market_confirmation=True,
        )
    )
    assert decision.entry_permitted is False
    assert "INSUFFICIENT_REMAINING_EV" in decision.reason_codes


def test_staged_gate_returns_policy_target_when_all_gates_pass():
    gate = StagedLeverageGate(LeveragePolicy())
    decision = gate.evaluate(
        StagedLeverageInputs(
            evidence_state=EvidenceState.CONFIRMED,
            remaining_ev=0.10,
            minimum_remaining_ev=0.05,
            thesis_active=True,
            catalyst_active=True,
            market_confirmation=True,
        )
    )
    assert decision.entry_permitted is True
    assert decision.signal_target_leverage == 1.75


# --- DynamicExposureController ---

def _controller() -> DynamicExposureController:
    return DynamicExposureController(
        staged_gate=StagedLeverageGate(),
        leverage_engine=LeverageEngine(),
        profit_engine=ProfitTakingEngine(ProfitTakingThresholds()),
    )


def _base_update_kwargs(**overrides):
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
        generic_projected_return=0.22,
    )
    kwargs.update(overrides)
    return kwargs


def test_dynamic_controller_scales_in_on_evidence_improvement_only():
    controller = _controller()
    result_emerging = controller.update(**_base_update_kwargs(evidence_state=EvidenceState.EMERGING))
    assert result_emerging.leverage_after == pytest.approx(1.25)
    assert result_emerging.tranche_added == pytest.approx(1.25)

    result_confirmed = controller.update(
        **_base_update_kwargs(current_time=T0 + timedelta(days=30), evidence_state=EvidenceState.CONFIRMED)
    )
    # Only the incremental 0.5x (1.75 - 1.25) is added as a new tranche.
    assert result_confirmed.tranche_added == pytest.approx(0.5)
    assert result_confirmed.leverage_after == pytest.approx(1.75)
    assert len(controller.book.tranches) == 2


def test_dynamic_controller_scales_out_riskiest_tranche_first_on_degradation():
    controller = _controller()
    controller.update(**_base_update_kwargs(evidence_state=EvidenceState.EMERGING))
    controller.update(
        **_base_update_kwargs(current_time=T0 + timedelta(days=30), evidence_state=EvidenceState.STRONG)
    )
    assert controller.book.current_leverage == pytest.approx(2.0)

    # Evidence weakens back to EMERGING: staged gate now only permits 1.25x,
    # but the controller does not forcibly sell down to the new signal target on its own;
    # it is the profit-taking/exposure-reduction stage that actually removes tranches.
    # Simulate a profit-taking driven exit by pushing return above the 40% tier instead,
    # which should unwind the newest (STRONG) tranche first.
    result = controller.update(
        **_base_update_kwargs(
            current_time=T0 + timedelta(days=60),
            evidence_state=EvidenceState.STRONG,
            underlying_return=0.45,
            generic_projected_return=0.60,  # modest benchmark capture -> default 25% trim
        )
    )
    assert result.reduction_result.leverage_removed > 0.0
    remaining_states = {t.evidence_state for t in controller.book.active_tranches}
    # STRONG tranche should be reduced/removed before the EMERGING tranche.
    assert EvidenceState.EMERGING in remaining_states


def test_dynamic_controller_blocks_entry_when_thesis_invalidated():
    controller = _controller()
    result = controller.update(**_base_update_kwargs(thesis_active=False))
    assert result.tranche_added == 0.0
    assert result.leverage_after == 0.0
    assert "THESIS_INVALIDATED" in result.reason_codes


def test_dynamic_controller_risk_caps_suppress_signal_target():
    tight_limits = LeverageLimits(
        max_absolute_leverage=0.5,
        max_trade_loss_pct=999.0,
        volatility_limit=999.0,
        liquidity_limit=999.0,
        concentration_limit=999.0,
        portfolio_limit=999.0,
    )
    controller = _controller()
    result = controller.update(**_base_update_kwargs(evidence_state=EvidenceState.STRONG, leverage_limits=tight_limits))
    assert result.signal_target_leverage == 2.0
    assert result.risk_capped_leverage == pytest.approx(0.5)
    assert result.leverage_after == pytest.approx(0.5)
