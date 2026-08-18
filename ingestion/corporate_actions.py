"""corporate_actions.py
Placeholder corporate actions adjustments (splits, mergers)

"""
# ==============================================================================
# PIPELINE STEP: CORPORATE ACTION & REBALANCE FILTERING (corporate_actions.py)
# ==============================================================================
# Operational Goal: Clean raw holdings by adjusting for splits, unifying ticker/CUSIP
# lineage into a Canonical ID, and flagging index rebalance events to prevent false IAV signals.
# ==============================================================================

import numpy as np
import pandas as pd

def process_corporate_actions_pipeline(
    raw_holdings_df: pd.DataFrame,
    corporate_events_db: dict,
    rebalance_schedule_db: dict
) -> pd.DataFrame:
    """
    Executes end-to-end adjustment across point-in-time holdings disclosures.
    
    Data Schema Inputs:
      - raw_holdings_df: [date, fund_id, raw_ticker, raw_shares (q), etf_shares_out (N)]
      - corporate_events_db: Historical mappings of splits, mergers, spinoffs, and CUSIP migrations
      - rebalance_schedule_db: Index reconstitution calendars per ETF/benchmark
    """
    clean_df = raw_holdings_df.copy()

    # --------------------------------------------------------------------------
    # 1. IDENTIFIER LINEAGE RESOLUTION
    # Map changing tickers/CUSIPs to a single permanent canonical_id to prevent
    # spurious 'new initiations' or 'full exits'.
    # --------------------------------------------------------------------------
    clean_df["canonical_id"] = clean_df.apply(
        lambda row: resolve_canonical_identity(
            raw_id=row["raw_ticker"],
            as_of_date=row["date"],
            lineage_registry=corporate_events_db["lineage_map"]
        ),
        axis=1
    )
    
    # Audit flag for symbol migration
    clean_df["is_spinoff_or_rename"] = clean_df["canonical_id"] != clean_df["raw_ticker"]

    # --------------------------------------------------------------------------
    # 2. SPLIT & SHARE RATIO ADJUSTMENT
    # Backward-adjust stock quantity (q) and fund shares (N) for stock/ETF splits
    # to preserve accurate normalized per-unit metrics: u = q / N
    # --------------------------------------------------------------------------
    for split_event in corporate_events_db["splits"]:
        # Match security-level splits
        stock_mask = (
            (clean_df["canonical_id"] == split_event["canonical_id"]) &
            (clean_df["date"] < split_event["effective_date"])
        )
        clean_df.loc[stock_mask, "raw_shares"] *= split_event["split_multiplier"]
        clean_df.loc[stock_mask, "is_split_adjusted"] = True

        # Match ETF-level share splits
        if split_event.get("is_etf_split", False):
            fund_mask = (
                (clean_df["fund_id"] == split_event["fund_id"]) &
                (clean_df["date"] < split_event["effective_date"])
            )
            clean_df.loc[fund_mask, "etf_shares_out"] *= split_event["split_multiplier"]
            clean_df.loc[fund_mask, "is_split_adjusted"] = True

    # --------------------------------------------------------------------------
    # 3. INDEX REBALANCE & RECONSTITUTION FLAGGING
    # Tag trades occurring within scheduled reconstitution windows to apply
    # downstream penalty lambda_R (rebalance contamination).
    # --------------------------------------------------------------------------
    clean_df["is_rebalance_contaminated"] = False
    clean_df["lambda_R_penalty"] = 0.0

    for event in rebalance_schedule_db["events"]:
        rebal_window_mask = (
            (clean_df["fund_id"] == event["fund_id"]) &
            (clean_df["date"].between(event["window_start"], event["window_end"]))
        )
        clean_df.loc[rebal_window_mask, "is_rebalance_contaminated"] = True
        clean_df.loc[rebal_window_mask, "lambda_R_penalty"] = event.get("penalty_weight", 0.25)

    # --------------------------------------------------------------------------
    # 4. NORMALIZED UNIT RECALCULATION & AUDIT TRAIL
    # --------------------------------------------------------------------------
    # Normalized share unit (u = q / N) free from split distortions
    clean_df["u_normalized"] = clean_df["raw_shares"] / clean_df["etf_shares_out"]

    # Generate explicit audit flags string
    clean_df["audit_flags"] = clean_df.apply(
        lambda r: [
            flag for flag, active in [
                ("IS_SPLIT_ADJUSTED", r.get("is_split_adjusted", False)),
                ("IS_REBALANCE_CONTAMINATED", r.get("is_rebalance_contaminated", False)),
                ("IS_SPINOFF_SUCCESSOR", r.get("is_spinoff_or_rename", False)),
            ] if active
        ],
        axis=1
    )

    return clean_df
    
def apply_split(holdings: dict, ticker: str, ratio: float) -> dict:
    """Apply split ratio to holdings for ticker."""
    if ticker in holdings:
        holdings[ticker] = holdings[ticker] * ratio
    return holdings
"""
Edge-TF Disclosure Agent Engine - Corporate Actions & Event Adjustment Layer
Path: src/ingestion/corporate_actions.py

Responsible for adjusting share counts, reconciling permanent security identifiers,
and flagging index rebalances/corporate actions before quantitative decomposition.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional, Set, Tuple
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SplitEvent:
    """Represents a forward or reverse stock or ETF split event."""
    security_id: str
    effective_date: date
    split_ratio: float  # e.g., 2.0 for 2:1 split, 0.5 for 1:2 reverse split
    is_etf_split: bool = False


@dataclass(frozen=True)
class IdentifierMapping:
    """Tracks corporate identity migrations (ticker renames, CUSIP/ISIN changes, mergers)."""
    old_identifier: str
    canonical_id: str
    effective_start: date
    effective_end: Optional[date] = None
    action_type: str = "RENAME"  # RENAME, MERGER, SPINOFF, CUSIP_CHANGE


@dataclass(frozen=True)
class RebalanceEvent:
    """Records scheduled benchmark reconstitution or rebalance windows."""
    fund_id: str
    effective_date: date
    window_days: int = 3
    index_provider: Optional[str] = None


class CorporateActionAdjuster:
    """
    Standardizes historical disclosures against corporate actions and index events.
    Applies split multipliers, enforces canonical ID continuity, and flags contamination.
    """

    def __init__(
        self,
        splits: Optional[List[SplitEvent]] = None,
        id_mappings: Optional[List[IdentifierMapping]] = None,
        rebalance_events: Optional[List[RebalanceEvent]] = None,
    ):
        self.splits = splits or []
        self.id_mappings = id_mappings or []
        self.rebalance_events = rebalance_events or []
        self._build_lookup_indexes()

    def _build_lookup_indexes(self) -> None:
        """Constructs fast lookup indexes for point-in-time matching."""
        self._split_lookup: Dict[Tuple[str, date], float] = {
            (s.security_id, s.effective_date): s.split_ratio for s in self.splits
        }
        self._rebalance_lookup: Dict[str, Set[date]] = {}
        for r in self.rebalance_events:
            self._rebalance_lookup.setdefault(r.fund_id, set()).add(r.effective_date)

    def resolve_canonical_id(self, raw_identifier: str, observation_date: date) -> str:
        """
        Maps a point-in-time raw ticker, CUSIP, or ISIN to its persistent canonical ID.
        """
        for m in self.id_mappings:
            if m.old_identifier == raw_identifier:
                if m.effective_start <= observation_date:
                    if m.effective_end is None or observation_date <= m.effective_end:
                        return m.canonical_id
        return raw_identifier

    def apply_split_adjustments(
        self,
        df: pd.DataFrame,
        shares_held_col: str = "shares_held",
        etf_shares_col: str = "etf_shares_outstanding",
        date_col: str = "effective_date",
        security_id_col: str = "canonical_id",
        fund_id_col: str = "fund_id",
    ) -> pd.DataFrame:
        """
        Backward-adjusts share quantities for corporate splits to preserve valid u = q / N metrics.
        """
        adjusted_df = df.copy()
        if adjusted_df.empty:
            return adjusted_df

        if "split_factor_applied" not in adjusted_df.columns:
            adjusted_df["split_factor_applied"] = 1.0
        if "is_split_adjusted" not in adjusted_df.columns:
            adjusted_df["is_split_adjusted"] = False

        # Apply security-level splits
        for split in self.splits:
            if split.is_etf_split:
                continue

            mask = (
                (adjusted_df[security_id_col] == split.security_id)
                & (pd.to_datetime(adjusted_df[date_col]).dt.date < split.effective_date)
            )
            if mask.any():
                adjusted_df.loc[mask, shares_held_col] = (
                    adjusted_df.loc[mask, shares_held_col] * split.split_ratio
                )
                adjusted_df.loc[mask, "split_factor_applied"] *= split.split_ratio
                adjusted_df.loc[mask, "is_split_adjusted"] = True
                logger.info(
                    f"Applied split factor {split.split_ratio} to {split.security_id} "
                    f"prior to {split.effective_date} on {mask.sum()} records."
                )

        # Apply ETF fund-level share splits
        for split in self.splits:
            if not split.is_etf_split:
                continue

            mask = (
                (adjusted_df[fund_id_col] == split.security_id)
                & (pd.to_datetime(adjusted_df[date_col]).dt.date < split.effective_date)
            )
            if mask.any():
                adjusted_df.loc[mask, etf_shares_col] = (
                    adjusted_df.loc[mask, etf_shares_col] * split.split_ratio
                )
                adjusted_df.loc[mask, "is_split_adjusted"] = True
                logger.info(
                    f"Applied ETF share split factor {split.split_ratio} to fund {split.security_id} "
                    f"prior to {split.effective_date}."
                )

        return adjusted_df

    def tag_rebalance_contamination(
        self,
        df: pd.DataFrame,
        fund_id_col: str = "fund_id",
        date_col: str = "effective_date",
    ) -> pd.DataFrame:
        """
        Flags observations that fall within scheduled index reconstitution windows.
        """
        tagged_df = df.copy()
        if tagged_df.empty:
            return tagged_df

        tagged_df["is_rebalance_event"] = False
        tagged_df["rebalance_penalty_flag"] = 0.0

        for r_event in self.rebalance_events:
            r_date = pd.to_datetime(r_event.effective_date)
            window_start = r_date - pd.Timedelta(days=r_event.window_days)
            window_end = r_date + pd.Timedelta(days=r_event.window_days)

            mask = (
                (tagged_df[fund_id_col] == r_event.fund_id)
                & (pd.to_datetime(tagged_df[date_col]) >= window_start)
                & (pd.to_datetime(tagged_df[date_col]) <= window_end)
            )
            if mask.any():
                tagged_df.loc[mask, "is_rebalance_event"] = True
                tagged_df.loc[mask, "rebalance_penalty_flag"] = 1.0

        return tagged_df

    def process_disclosure_batch(
        self,
        raw_df: pd.DataFrame,
        raw_id_col: str = "raw_identifier",
        date_col: str = "effective_date",
        shares_held_col: str = "shares_held",
        etf_shares_col: str = "etf_shares_outstanding",
        fund_id_col: str = "fund_id",
    ) -> pd.DataFrame:
        """
        Unified ingestion entrypoint: resolves identities, adjusts splits, and tags events.
        """
        df = raw_df.copy()
        if df.empty:
            return df

        # Step 1: Resolve permanent canonical identifier
        df["canonical_id"] = [
            self.resolve_canonical_id(raw_id, pd.to_datetime(obs_date).date())
            for raw_id, obs_date in zip(df[raw_id_col], df[date_col])
        ]

        # Step 2: Apply split adjustments to historical shares and ETF share counts
        df = self.apply_split_adjustments(
            df=df,
            shares_held_col=shares_held_col,
            etf_shares_col=etf_shares_col,
            date_col=date_col,
            security_id_col="canonical_id",
            fund_id_col=fund_id_col,
        )

        # Step 3: Flag rebalance window contamination
        df = self.tag_rebalance_contamination(
            df=df,
            fund_id_col=fund_id_col,
            date_col=date_col,
        )

        return df
