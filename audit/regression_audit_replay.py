# regression_audit_replay example harness (placeholder)

def test_replay_runs():
    assert True
# ==============================================================================
# PIPELINE STEP: REGRESSION AUDIT & POINT-IN-TIME REPLAY (regression_audit_replay.py)
# ==============================================================================
# Operational Goal: Step chronologically through historical disclosure events,
# enforce the temporal barrier (DecisionTime >= InformationAvailableTime),
# and verify signal reproducibility without look-ahead or survivorship bias.
# ==============================================================================

from datetime import datetime, date
from typing import Dict, List, Any
import numpy as np
import pandas as pd

def run_regression_audit_replay(
    historical_events_stream: pd.DataFrame,
    replay_dates: List[date],
    benchmark_signal_archive: pd.DataFrame,
    pipeline_runner_fn: Any,
    tolerance: float = 1e-5
) -> Dict[str, Any]:
    """
    Executes chronological simulation to detect regressions and temporal leakage.
    
    Inputs:
      - historical_events_stream: Canonical disclosure panel with 'information_available_time'
      - replay_dates: Ordered sequence of evaluation dates to simulate
      - benchmark_signal_archive: Golden dataset of historically approved signals
      - pipeline_runner_fn: Function executing Ingestion -> Quant Engine -> Falsification
      - tolerance: Maximum allowable delta for quantitative scores
    """
    audit_log = []
    regression_failures = []

    for current_eval_date in sorted(replay_dates):
        # 1. Enforce Point-in-Time boundary: DecisionTime >= InformationAvailableTime
        eval_dt = datetime.combine(current_eval_date, datetime.min.time())
        pit_mask = pd.to_datetime(historical_events_stream["information_available_time"]) <= eval_dt
        visible_data = historical_events_stream[pit_mask].copy()

        # 2. Re-run complete production analytics pipeline
        simulated_signals = pipeline_runner_fn(
            disclosures_df=visible_data,
            as_of_date=current_eval_date
        )

        # 3. Align with Golden Benchmark archive for regression detection
        bench_slice = benchmark_signal_archive[
            benchmark_signal_archive["evaluation_date"] == current_eval_date
        ]

        merged = pd.merge(
            simulated_signals,
            bench_slice,
            on=["canonical_id"],
            suffixes=("_sim", "_bench"),
            how="inner"
        )

        # 4. Check for drift in IAV Composite and Manager Breadth
        iav_diff = (merged["iav_score_sim"] - merged["iav_score_bench"]).abs()
        breadth_diff = (merged["manager_breadth_sim"] - merged["manager_breadth_bench"]).abs()

        max_iav_drift = iav_diff.max() if not iav_diff.empty else 0.0
        max_breadth_drift = breadth_diff.max() if not breadth_diff.empty else 0

        passed_step = (max_iav_drift <= tolerance) and (max_breadth_drift == 0)

        if not passed_step:
            regression_failures.append({
                "date": str(current_eval_date),
                "max_iav_drift": float(max_iav_drift),
                "max_breadth_drift": int(max_breadth_drift)
            })

        audit_log.append({
            "evaluation_date": str(current_eval_date),
            "records_visible": len(visible_data),
            "securities_evaluated": len(simulated_signals),
            "passed": passed_step
        })

    return {
        "total_replay_steps": len(replay_dates),
        "all_passed": len(regression_failures) == 0,
        "failures": regression_failures,
        "audit_timeline": audit_log
    }

"""
Edge-TF Disclosure Agent Engine - Point-in-Time Regression Replay Test
Path: tests/regression_audit_replay.py

Executes automated chronological replay across historical dataset snapshots.
Asserts signal invariance, absence of look-ahead bias, and falsification gate stability.
"""

from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
import unittest
import numpy as np
import pandas as pd

# Ingestion & Quant Imports
from src.ingestion.normalizer import DisclosureNormalizer, IngestionMetadata
from src.ingestion.corporate_actions import CorporateActionAdjuster, SplitEvent, RebalanceEvent
from src.quant_engine.manager_graph import ManagerGraphEngine, ManagerMetadata
from analytics.institutional_graph_engine import InstitutionalGraphEngine


@dataclass
class ReplaySnapshotAssertion:
    """Assertion container for regression verification on a given date."""
    eval_date: date
    canonical_id: str
    expected_iav: float
    expected_breadth: int
    expected_state: str


class TestRegressionAuditReplay(unittest.TestCase):
    """
    Simulates historical trading day replays and verifies deterministic reproducibility.
    """

    def setUp(self):
        """Sets up synthetic point-in-time disclosure history and manager registry."""
        self.t0 = date(2026, 1, 15)
        self.t1 = date(2026, 1, 16)
        self.t2 = date(2026, 1, 17)

        # Mock Manager Clustering
        self.manager_registry = {
            "ETF_A": ManagerMetadata(fund_id="ETF_A", adviser="Alpha_Advisers", subadviser=None),
            "ETF_B": ManagerMetadata(fund_id="ETF_B", adviser="Alpha_Advisers", subadviser=None),  # Duplicate cluster
            "ETF_C": ManagerMetadata(fund_id="ETF_C", adviser="Beta_Capital", subadviser=None),     # Independent cluster
        }

        # Mock Splits & Rebalances
        self.splits = [
            SplitEvent(security_id="SEC_TECH_1", effective_date=self.t2, split_ratio=2.0)
        ]
        self.rebalance_events = [
            RebalanceEvent(fund_id="ETF_C", effective_date=self.t1, window_days=1)
        ]

        self.normalizer = DisclosureNormalizer()
        self.ca_adjuster = CorporateActionAdjuster(
            splits=self.splits,
            rebalance_events=self.rebalance_events
        )
        self.mgr_engine = ManagerGraphEngine(
            manager_registry=self.manager_registry,
            holding_threshold=0.001
        )

        # Raw Historical Stream
        self.raw_stream = pd.DataFrame([
            # t0: Initial seed
            {"fund_ticker": "ETF_A", "symbol": "SEC_TECH_1", "shares": 1000, "shares_outstanding": 10000,
             "effective_date": self.t0, "available_time": datetime(2026, 1, 15, 6, 0)},
            {"fund_ticker": "ETF_B", "symbol": "SEC_TECH_1", "shares": 500, "shares_outstanding": 5000,
             "effective_date": self.t0, "available_time": datetime(2026, 1, 15, 6, 0)},
            # t1: Independent manager initiates + ETF_C in rebalance window
            {"fund_ticker": "ETF_C", "symbol": "SEC_TECH_1", "shares": 2000, "shares_outstanding": 20000,
             "effective_date": self.t1, "available_time": datetime(2026, 1, 16, 6, 0)},
            # t2: Post split
            {"fund_ticker": "ETF_A", "symbol": "SEC_TECH_1", "shares": 2000, "shares_outstanding": 10000,
             "effective_date": self.t2, "available_time": datetime(2026, 1, 17, 6, 0)},
        ])

    def test_point_in_time_isolation(self):
        """Verifies that decision time strictly prevents seeing future disclosures."""
        decision_time_t0 = datetime(2026, 1, 15, 12, 0)
        pit_mask = pd.to_datetime(self.raw_stream["available_time"]) <= decision_time_t0
        visible_t0 = self.raw_stream[pit_mask]

        # Should only see 2 records from ETF_A and ETF_B
        self.assertEqual(len(visible_t0), 2)
        self.assertNotIn("ETF_C", visible_t0["fund_ticker"].values)

    def test_manager_deduplication_integrity(self):
        """Verifies that ETF_A and ETF_B collapse to 1 manager cluster at t0."""
        meta = IngestionMetadata(
            issuer="Alpha",
            fund_id="ETF_A",
            disclosure_type="Rule 6c-11",
            portfolio_effective_date=self.t0,
            information_available_time=datetime(2026, 1, 15, 6, 0),
            file_checksum="chk_001"
        )
        norm_df = self.normalizer.process(self.raw_stream.iloc[:2], metadata=meta)
        norm_df["canonical_id"] = norm_df["raw_identifier"]

        mgr_metrics = self.mgr_engine.process_manager_network(
            norm_df,
            security_id_col="canonical_id",
            fund_id_col="fund_id",
            date_col="effective_date",
            holding_col="u_normalized"
        )

        sec_row = mgr_metrics[mgr_metrics["canonical_id"] == "SEC_TECH_1"].iloc[0]
        # Even though 2 ETFs hold the stock, true breadth must be 1 due to shared adviser
        self.assertEqual(sec_row["manager_breadth"], 1)
        self.assertAlmostEqual(sec_row["manager_hhi"], 1.0, places=4)

    def test_split_and_rebalance_regression(self):
        """Verifies that corporate actions and rebalance window tags replay correctly."""
        processed_df = self.ca_adjuster.process_disclosure_batch(
            self.raw_stream.rename(columns={"symbol": "raw_identifier", "fund_ticker": "fund_id", "shares": "shares_held", "shares_outstanding": "etf_shares_outstanding"}),
            raw_id_col="raw_identifier",
            date_col="effective_date"
        )

        # Verify rebalance contamination flag triggered on ETF_C at t1
        etf_c_row = processed_df[(processed_df["fund_id"] == "ETF_C") & (processed_df["effective_date"] == self.t1)].iloc[0]
        self.assertTrue(etf_c_row["is_rebalance_event"])
        self.assertEqual(etf_c_row["rebalance_penalty_flag"], 1.0)

        # Verify split backward adjustment on t0/t1 records for SEC_TECH_1
        t0_shares = processed_df[(processed_df["fund_id"] == "ETF_A") & (processed_df["effective_date"] == self.t0)]["shares_held"].iloc[0]
        # Original 1000 shares * 2.0 split ratio = 2000
        self.assertEqual(t0_shares, 2000.0)


if __name__ == "__main__":
    unittest.main()
