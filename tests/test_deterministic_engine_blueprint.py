import numpy as np
import pytest

from core.schemas import DisclosurePayload, ManagerAction
from analytics.diffusion_scorer import InstitutionalGraphEngine
from analytics.flow_decomposition import AnomalyDetector
from risk.deterministic_gates import DeterministicExecutionGate


def test_typed_disclosure_contract_rejects_unbounded_action_type():
    action = ManagerAction(
        source_entity="Fund_A",
        target_ticker="XYZ",
        action_type="ACCUMULATE",
        reported_shares_delta=500_000,
    )
    payload = DisclosurePayload(filing_id="F1", filing_timestamp=1, actions=[action])
    assert payload.actions[0].target_ticker == "XYZ"
    with pytest.raises(ValueError):
        ManagerAction(
            source_entity="Fund_A",
            target_ticker="XYZ",
            action_type="MAKE_UP_A_TRADE",
            reported_shares_delta=1,
        )


def test_graph_engine_uses_weighted_pagerank():
    engine = InstitutionalGraphEngine()
    engine.update_graph("Fund_A", "XYZ", 1.0)
    engine.update_graph("Fund_B", "XYZ", 2.0)
    assert engine.calculate_diffusion_score("XYZ") > 0.0
    assert engine.calculate_diffusion_score("UNKNOWN") == 0.0


def test_anomaly_detector_uses_fixed_baseline():
    assert AnomalyDetector.calculate_flow_zscore(100.0, [0.0] * 19) == 0.0
    assert AnomalyDetector.calculate_flow_zscore(30.0, list(range(20))) > 0.0


def test_execution_gate_rejects_signal_and_spread_failures():
    gate = DeterministicExecutionGate(min_zscore=1.96, min_diffusion=0.01, max_spread_pct=0.02)
    assert gate.verify_order(1.0, 0.5, 99.0, 100.0)[0] is False
    assert gate.verify_order(2.0, 0.5, 90.0, 100.0)[0] is False
    assert gate.verify_order(2.0, 0.5, 99.5, 100.0)[0] is True
