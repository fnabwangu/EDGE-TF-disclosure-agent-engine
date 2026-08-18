"""Tests for the two-axis capital-flow leverage engine (event probability vs. flow maturity)."""

import pytest

from analytics.capital_flow_leverage_engine import (
    CapitalFlowLeverageEngine,
    DeploymentInputs,
    DeploymentPolicy,
    LeverageBand,
)
from analytics.leverage_tranches import EvidenceState


def _inputs(**overrides) -> DeploymentInputs:
    defaults = dict(
        event_probability=0.70,
        remaining_ev=0.10,
        minimum_remaining_ev=0.05,
        flow_state=EvidenceState.EMERGING,
        flow_progress=0.0,
        thesis_active=True,
        catalyst_active=True,
        absolute_leverage_cap=10.0,
        loss_cap_leverage=10.0,
        volatility_cap_leverage=10.0,
        liquidity_cap_leverage=10.0,
        concentration_cap_leverage=10.0,
        portfolio_cap_leverage=10.0,
    )
    defaults.update(overrides)
    return DeploymentInputs(**defaults)


def test_leverage_band_rejects_ceiling_below_floor():
    with pytest.raises(ValueError):
        LeverageBand(6.0, 4.0)


def test_leverage_band_rejects_negative_floor():
    with pytest.raises(ValueError):
        LeverageBand(-1.0, 2.0)


def test_emerging_entry_establishes_four_times_floor():
    engine = CapitalFlowLeverageEngine()
    decision = engine.calculate(_inputs(flow_state=EvidenceState.EMERGING, flow_progress=0.0))
    assert decision.requested_leverage == pytest.approx(4.0)
    assert decision.approved_leverage == pytest.approx(4.0)
    assert decision.state_floor == 4.0
    assert decision.state_ceiling == 6.0


def test_emerging_midpoint_progress_gives_five_times():
    engine = CapitalFlowLeverageEngine()
    decision = engine.calculate(_inputs(flow_state=EvidenceState.EMERGING, flow_progress=0.50))
    assert decision.requested_leverage == pytest.approx(5.0)


def test_emerging_near_graduation_gives_5_8x():
    engine = CapitalFlowLeverageEngine()
    decision = engine.calculate(_inputs(flow_state=EvidenceState.EMERGING, flow_progress=0.90))
    assert decision.requested_leverage == pytest.approx(5.8)


def test_confirmed_and_strong_bands():
    engine = CapitalFlowLeverageEngine()
    confirmed = engine.calculate(_inputs(flow_state=EvidenceState.CONFIRMED, flow_progress=0.0))
    assert confirmed.state_floor == 6.0 and confirmed.state_ceiling == 8.0

    strong = engine.calculate(_inputs(flow_state=EvidenceState.STRONG, flow_progress=1.0))
    assert strong.requested_leverage == pytest.approx(10.0)


def test_wait_and_seeded_bands_stay_low():
    engine = CapitalFlowLeverageEngine()
    wait = engine.calculate(_inputs(flow_state=EvidenceState.WAIT, flow_progress=1.0, event_probability=0.9))
    assert wait.requested_leverage == pytest.approx(0.0)

    seeded = engine.calculate(_inputs(flow_state=EvidenceState.SEEDED, flow_progress=0.5))
    assert seeded.requested_leverage == pytest.approx(1.0)


def test_loss_cap_overrides_high_requested_leverage():
    # Requested 8.4x from a STRONG-band flow, but the loss cap only permits 2x.
    engine = CapitalFlowLeverageEngine()
    decision = engine.calculate(
        _inputs(
            flow_state=EvidenceState.STRONG,
            flow_progress=0.2,  # 8.0 + 0.2*(10-8) = 8.4x requested
            loss_cap_leverage=2.0,
        )
    )
    assert decision.requested_leverage == pytest.approx(8.4)
    assert decision.approved_leverage == pytest.approx(2.0)
    assert decision.limiting_constraint == "LOSS"
    assert decision.permitted is True


def test_event_probability_below_threshold_blocks_regardless_of_flow_state():
    engine = CapitalFlowLeverageEngine()
    decision = engine.calculate(_inputs(event_probability=0.55, flow_state=EvidenceState.STRONG, flow_progress=1.0))
    assert decision.approved_leverage == 0.0
    assert decision.permitted is False
    assert decision.limiting_constraint == "EVENT_PROBABILITY"
    assert decision.reason_codes == ("EVENT_PROBABILITY_BELOW_THRESHOLD",)


def test_event_probability_is_not_multiplied_into_leverage():
    """A 70% event probability must not scale the requested leverage down to 70% of the band."""
    engine = CapitalFlowLeverageEngine()
    decision = engine.calculate(_inputs(event_probability=0.70, flow_state=EvidenceState.CONFIRMED, flow_progress=1.0))
    assert decision.requested_leverage == pytest.approx(8.0)  # full band ceiling, not 0.70 * 8.0


def test_insufficient_remaining_ev_blocks():
    engine = CapitalFlowLeverageEngine()
    decision = engine.calculate(_inputs(remaining_ev=0.01, minimum_remaining_ev=0.05))
    assert decision.permitted is False
    assert decision.limiting_constraint == "REMAINING_EV"


def test_thesis_invalidation_and_catalyst_expiry_block_before_event_probability_check():
    engine = CapitalFlowLeverageEngine()
    thesis_blocked = engine.calculate(_inputs(thesis_active=False, event_probability=0.01))
    assert thesis_blocked.limiting_constraint == "THESIS"

    catalyst_blocked = engine.calculate(_inputs(catalyst_active=False, event_probability=0.01))
    assert catalyst_blocked.limiting_constraint == "CATALYST"


def test_custom_policy_thresholds():
    policy = DeploymentPolicy(
        minimum_event_probability=0.60,
        emerging=LeverageBand(1.0, 2.0),
    )
    engine = CapitalFlowLeverageEngine(policy)
    decision = engine.calculate(_inputs(event_probability=0.65, flow_state=EvidenceState.EMERGING, flow_progress=0.5))
    assert decision.requested_leverage == pytest.approx(1.5)


def test_invalid_event_probability_raises():
    engine = CapitalFlowLeverageEngine()
    with pytest.raises(ValueError):
        engine.calculate(_inputs(event_probability=1.5))


def test_invalid_flow_progress_raises():
    engine = CapitalFlowLeverageEngine()
    with pytest.raises(ValueError):
        engine.calculate(_inputs(flow_progress=-0.1))


def test_requested_leverage_cap_overrides_band_ceiling():
    policy = DeploymentPolicy(strong=LeverageBand(8.0, 10.0), requested_leverage_cap=6.0)
    engine = CapitalFlowLeverageEngine(policy)
    decision = engine.calculate(_inputs(flow_state=EvidenceState.STRONG, flow_progress=1.0))
    assert decision.requested_leverage == pytest.approx(6.0)
    assert "REQUESTED_LEVERAGE_CAP_APPLIED" in decision.reason_codes


def test_engine_loads_policy_and_default_risk_limits_from_config():
    engine = CapitalFlowLeverageEngine()
    assert engine.policy.minimum_event_probability == pytest.approx(0.70)
    assert engine.policy.emerging.floor == pytest.approx(4.0)
    assert engine.policy.emerging.ceiling == pytest.approx(6.0)
    assert engine.policy.requested_leverage_cap == pytest.approx(10.0)
    assert engine.default_risk_limits is not None
    assert engine.default_risk_limits.max_absolute_leverage == pytest.approx(10.0)
    assert engine.default_risk_limits.max_trade_loss_pct == pytest.approx(0.075)


def test_engine_falls_back_to_builtin_defaults_without_config_file(tmp_path):
    missing_path = tmp_path / "does_not_exist.json"
    engine = CapitalFlowLeverageEngine(config_path=missing_path)
    assert engine.policy.strong.ceiling == pytest.approx(10.0)
    assert engine.default_risk_limits is None


def test_explicit_policy_bypasses_config_loading():
    policy = DeploymentPolicy(emerging=LeverageBand(1.0, 2.0))
    engine = CapitalFlowLeverageEngine(policy)
    assert engine.policy is policy
