"""
Edge-TF Disclosure Agent Engine - Anomaly Detector
Path: analytics/anomaly_detector.py

Detects anomalies in ETF flow dynamics using Scipy baseline Z-score tests
to isolate active managerial accumulation from creation/redemption noise.
"""

from typing import Optional, Tuple, Dict, Any
import numpy as np
import pandas as pd
from scipy import stats
import logging

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Executes statistical anomaly detection on ETF holdings to distinguish
    active managerial positioning from passive creation/redemption flows.
    
    Implements flow decomposition to isolate Active Quantity Deviation (AQD)
    using Scipy baseline Z-score tests for anomaly flagging.
    """

    def __init__(
        self,
        z_score_threshold: float = 2.0,
        min_history_periods: int = 20,
    ):
        """
        Args:
            z_score_threshold: Number of standard deviations for anomaly flagging.
            min_history_periods: Minimum historical points required for baseline estimation.
        """
        self.z_threshold = z_score_threshold
        self.min_history = min_history_periods

    @staticmethod
    def calculate_flow_zscore(current_flow: float, historical_flows: list[float]) -> float:
        """Calculate a sample-standard-deviation Z-score against a fixed baseline."""
        if len(historical_flows) < 20:
            return 0.0
        baseline = np.asarray(historical_flows, dtype=float)
        std_dev = float(stats.tstd(baseline))
        if not np.isfinite(std_dev) or std_dev == 0.0:
            return 0.0
        return float((current_flow - float(np.mean(baseline))) / std_dev)

    def compute_normalized_units(
        self,
        df: pd.DataFrame,
        shares_col: str = "shares_held",
        etf_shares_col: str = "etf_shares_outstanding",
        out_col: str = "u_norm",
    ) -> pd.DataFrame:
        """Calculates normalized security shares held per single ETF share unit (u = q / N)."""
        df = df.copy()
        # Guard against division by zero or missing shares outstanding
        etf_shares = df[etf_shares_col].replace(0, np.nan)
        df[out_col] = df[shares_col] / etf_shares
        return df

    def compute_active_quantity_deviation(
        self,
        holdings_df: pd.DataFrame,
        fund_id_col: str = "fund_id",
        security_id_col: str = "security_id",
        date_col: str = "effective_date",
        shares_col: str = "shares_held",
        etf_shares_col: str = "etf_shares_outstanding",
    ) -> pd.DataFrame:
        """
        Calculates Expected Quantity (ExpectedQ) and Active Quantity Deviation (AQD).

        ExpectedQ_{f,i,t} = q_{f,i,t-1} * (N_{f,t} / N_{f,t-1})
        AQD_{f,i,t} = q_{f,i,t} - ExpectedQ_{f,i,t}
        """
        df = holdings_df.sort_values(
            by=[fund_id_col, security_id_col, date_col]
        ).copy()

        # 1. Compute lagged security shares held (q_{t-1})
        df["prev_q"] = df.groupby([fund_id_col, security_id_col])[
            shares_col
        ].shift(1)

        # 2. Compute lagged fund shares outstanding (N_{t-1})
        # Extract unique fund-date level shares outstanding to avoid duplicate row shifts
        fund_shares_df = (
            df[[fund_id_col, date_col, etf_shares_col]]
            .drop_duplicates()
            .sort_values(by=[fund_id_col, date_col])
        )
        fund_shares_df["prev_etf_n"] = fund_shares_df.groupby(fund_id_col)[
            etf_shares_col
        ].shift(1)

        # Merge lagged fund shares back into primary holdings panel
        df = pd.merge(
            df,
            fund_shares_df[[fund_id_col, date_col, "prev_etf_n"]],
            on=[fund_id_col, date_col],
            how="left",
        )

        # 3. Compute Creation/Redemption Scaling Factor: S_{f,t} = N_t / N_{t-1}
        scaling_ratio = df[etf_shares_col] / df["prev_etf_n"].replace(0, np.nan)

        # 4. Compute Expected Quantity and Active Quantity Deviation
        df["expected_q"] = df["prev_q"] * scaling_ratio
        df["aqd"] = df[shares_col] - df["expected_q"]

        # 5. Percentage Active Deviation relative to prior position baseline
        df["aqd_pct"] = np.where(
            df["prev_q"] > 0,
            (df["aqd"] / df["prev_q"]),
            np.nan,
        )

        # Clean intermediate operational columns
        return df.drop(columns=["prev_q", "prev_etf_n"])

    def compute_z_score_baseline(
        self,
        df: pd.DataFrame,
        fund_id_col: str = "fund_id",
        security_id_col: str = "security_id",
        metric_col: str = "aqd",
        lookback: int = 20,
    ) -> pd.DataFrame:
        """
        Computes rolling Z-score baseline using Scipy for anomaly detection.
        Uses historical mean and std to flag significant deviations.
        """
        df = df.copy()

        # transform, not apply: groupby.apply drops the grouping columns on pandas 3.
        grouped = df.groupby([fund_id_col, security_id_col])[metric_col]
        rolling_mean = grouped.transform(
            lambda series: series.rolling(window=lookback, min_periods=self.min_history).mean()
        )
        rolling_std = grouped.transform(
            lambda series: series.rolling(window=lookback, min_periods=self.min_history).std()
        )

        df["z_score"] = (df[metric_col] - rolling_mean) / (rolling_std + 1e-8)
        return df

    def flag_anomalies(
        self,
        df: pd.DataFrame,
        z_score_col: str = "z_score",
        anomaly_col: str = "is_anomaly",
    ) -> pd.DataFrame:
        """
        Flags anomalies where |Z-score| exceeds the configured threshold.
        """
        df = df.copy()
        df[anomaly_col] = np.abs(df[z_score_col]) > self.z_threshold
        return df

    def filter_flow_distortion(
        self,
        df: pd.DataFrame,
        aqd_col: str = "aqd",
        threshold_shares: float = 0.0,
    ) -> pd.DataFrame:
        """Flags whether a share increase is genuinely active or purely creation-flow artifact."""
        df = df.copy()
        df["is_active_accumulation"] = df[aqd_col] > threshold_shares
        df["is_active_reduction"] = df[aqd_col] < -threshold_shares
        return df

    def detect_anomalies(
        self,
        holdings_df: pd.DataFrame,
        fund_id_col: str = "fund_id",
        security_id_col: str = "security_id",
        date_col: str = "effective_date",
        shares_col: str = "shares_held",
        etf_shares_col: str = "etf_shares_outstanding",
        lookback: int = 20,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Complete anomaly detection pipeline combining flow decomposition and Z-score testing.
        
        Returns:
            Tuple of (enriched_dataframe, summary_statistics)
        """
        # Step 1: Flow decomposition
        df = self.compute_active_quantity_deviation(
            holdings_df,
            fund_id_col=fund_id_col,
            security_id_col=security_id_col,
            date_col=date_col,
            shares_col=shares_col,
            etf_shares_col=etf_shares_col,
        )

        # Step 2: Compute Z-score baseline
        df = self.compute_z_score_baseline(
            df,
            fund_id_col=fund_id_col,
            security_id_col=security_id_col,
            metric_col="aqd",
            lookback=lookback,
        )

        # Step 3: Flag anomalies
        df = self.flag_anomalies(df, z_score_col="z_score", anomaly_col="is_anomaly")

        # Step 4: Classify flows
        df = self.filter_flow_distortion(df, aqd_col="aqd")

        # Summary statistics
        summary = {
            "total_positions": len(df),
            "anomalous_positions": int(df["is_anomaly"].sum()),
            "active_accumulations": int(df["is_active_accumulation"].sum()),
            "active_reductions": int(df["is_active_reduction"].sum()),
            "mean_z_score": float(df["z_score"].mean()),
            "std_z_score": float(df["z_score"].std()),
            "anomaly_pct": float(df["is_anomaly"].mean() * 100),
        }

        return df, summary
