from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from analytics.pipeline import process_disclosure_pipeline
from core.etf_disclosures import ETFDisclosureIngestor, StaticETFDisclosureProvider
from core.schemas import ManagerAction
from risk.kill_switch import EmergencyKillSwitchEngine, KillSwitchState, TripTriggerType
from analytics.manager_independence import ManagerGraphEngine, ManagerMetadata, compute_manager_graph_pipeline


def etf_payload(available_time: datetime):
    return {
        "source": "FIXTURE",
        "holdings": [{
            "etf_ticker": "EDGE", "fund_id": "FUND-A", "security_id": "SEC-A", "raw_identifier": "A",
            "shares_held": 100.0, "portfolio_effective_date": "2026-08-18",
            "information_available_time": available_time.isoformat(),
        }],
        "shares_outstanding": [{
            "etf_ticker": "EDGE", "fund_id": "FUND-A", "shares_outstanding": 1000.0,
            "effective_date": "2026-08-18", "information_available_time": available_time.isoformat(),
        }],
    }


def test_stale_etf_disclosure_is_rejected(tmp_path):
    as_of = datetime(2026, 8, 18, tzinfo=timezone.utc)
    provider = StaticETFDisclosureProvider({"EDGE": etf_payload(as_of - timedelta(days=8))})
    ingestor = ETFDisclosureIngestor(provider, tmp_path / "raw", tmp_path / "canonical")

    with pytest.raises(ValueError, match="stale"):
        ingestor.ingest("EDGE", as_of)


def test_unknown_manager_does_not_create_artificial_breadth():
    engine = ManagerGraphEngine({"KNOWN": ManagerMetadata("KNOWN", "Adviser A")})
    frame = pd.DataFrame([
        {"canonical_id": "SEC-A", "fund_id": "KNOWN", "u_normalized": 0.10},
        {"canonical_id": "SEC-A", "fund_id": "UNKNOWN", "u_normalized": 0.20},
    ])

    breadth = engine.compute_cluster_breadth(frame)
    assert breadth["SEC-A"] == 1


def test_legacy_manager_pipeline_excludes_unknown_relationships():
    frame = pd.DataFrame([
        {"canonical_id": "SEC-A", "fund_id": "KNOWN", "u_normalized": 0.10, "effective_date": "2026-08-18"},
        {"canonical_id": "SEC-A", "fund_id": "UNKNOWN", "u_normalized": 0.20, "effective_date": "2026-08-18"},
    ])
    result = compute_manager_graph_pipeline(frame, {"KNOWN": "ADVISER-A"})
    assert result.loc[result["canonical_id"] == "SEC-A", "manager_breadth"].iloc[0] == 1


def test_duplicate_manager_funds_are_deduplicated():
    registry = {
        "FUND-A": ManagerMetadata("FUND-A", "Same Adviser"),
        "FUND-B": ManagerMetadata("FUND-B", "Same Adviser"),
        "FUND-C": ManagerMetadata("FUND-C", "Independent Adviser"),
    }
    engine = ManagerGraphEngine(registry)
    frame = pd.DataFrame([
        {"canonical_id": "SEC-A", "fund_id": "FUND-A", "u_normalized": 0.10},
        {"canonical_id": "SEC-A", "fund_id": "FUND-B", "u_normalized": 0.10},
        {"canonical_id": "SEC-A", "fund_id": "FUND-C", "u_normalized": 0.10},
    ])

    assert engine.compute_cluster_breadth(frame)["SEC-A"] == 2


def test_infeasible_optimizer_blocks_complete_pipeline():
    action = ManagerAction(
        source_entity="Fund-A", target_ticker="SEC-A", action_type="ACCUMULATE", reported_shares_delta=100.0
    )
    result = process_disclosure_pipeline(
        action, list(range(20)), 99.5, 100.0, np.array([0.10]), np.array([[1.0]]),
        max_drawdown_limit=0.0,
    )

    assert result["execution_permitted"] is False
    assert result["gate_reason"].startswith("NO_TRADE")
    assert result["optimizer_status"] in {"INFEASIBLE", "SOLVER_UNAVAILABLE", "SOLVER_ERROR"}
    assert result["optimizer_reason_code"].startswith("OPTIMIZATION_")
    assert np.all(result["optimized_weights"] == 0.0)


def test_complete_pipeline_replay_is_identical():
    action = ManagerAction(
        source_entity="Fund-A", target_ticker="SEC-A", action_type="ACCUMULATE", reported_shares_delta=1.0
    )
    kwargs = dict(
        action=action, historical_flow_data=[0.0] * 20, current_bid=90.0, current_ask=100.0,
        expected_returns=np.array([0.10]), covariance_matrix=np.array([[0.04]]),
    )
    first = process_disclosure_pipeline(**kwargs)
    second = process_disclosure_pipeline(**kwargs)
    assert first["execution_permitted"] == second["execution_permitted"]
    assert first["gate_reason"] == second["gate_reason"]
    np.testing.assert_array_equal(first["optimized_weights"], second["optimized_weights"])


def test_kill_switch_trip_persists_across_restart(tmp_path):
    state_path = tmp_path / "kill_switch.json"
    first = EmergencyKillSwitchEngine(state_path=state_path)
    first.trip(TripTriggerType.DATA_STALENESS, "stale provider feed")

    restarted = EmergencyKillSwitchEngine(state_path=state_path)
    assert restarted.state == KillSwitchState.TRIPPED_AUTO
    assert restarted.is_locked is True
    assert "stale provider feed" in restarted.active_trigger_reason
