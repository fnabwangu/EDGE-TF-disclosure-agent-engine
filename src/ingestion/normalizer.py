"""normalizer.py
Identifier resolution stub (CUSIP/ISIN -> UUID)
"""
import uuid

def resolve_identifier(identifier: str) -> str:
    """Return a deterministic UUID for the provided identifier string (placeholder)."""
    # NOTE: replace with real resolution against an external service or mapping table
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, identifier))
# ==============================================================================
# PIPELINE STEP: DISCLOSURE NORMALIZATION & FLOW FILTERING (normalizer.py)
# ==============================================================================
# Operational Goal: Translate raw ETF provider disclosures into a canonical schema,
# calculate flow-normalized units (u = q / N), compute Active Quantity Deviation (AQD),
# and enforce point-in-time constraints (DecisionTime >= InformationAvailableTime).
# ==============================================================================

from datetime import datetime, date
import numpy as np
import pandas as pd

def normalize_disclosures_pipeline(
    raw_df: pd.DataFrame,
    schema_mapping: dict,
    provenance_metadata: dict,
    decision_timestamp: datetime
) -> pd.DataFrame:
    """
    Executes schema standardization, per-unit flow adjustment, AQD calculation,
    and point-in-time enforcement across incoming disclosure streams.
    """
    df = raw_df.copy()

    # --------------------------------------------------------------------------
    # 1. SCHEMA CANONICALIZATION
    # Remap provider-specific header variants (e.g., 'Units Held', 'Shares')
    # into standardized internal column names.
    # --------------------------------------------------------------------------
    cleaned_headers = {
        col: col.strip().lower().replace(" ", "_").replace("%", "percentage")
        for col in df.columns
    }
    df = df.rename(columns=cleaned_headers)
    df = df.rename(columns=schema_mapping)

    # --------------------------------------------------------------------------
    # 2. PROVENANCE & DUAL-TIMESTAMP ATTACHMENT
    # Attach tracking metadata to support auditability and point-in-time alignment.
    # --------------------------------------------------------------------------
    df["issuer"] = provenance_metadata["issuer"]
    df["disclosure_type"] = provenance_metadata["disclosure_type"]
    df["effective_date"] = pd.to_datetime(provenance_metadata["effective_date"]).date()
    df["information_available_time"] = pd.to_datetime(provenance_metadata["available_time"])
    df["parser_version"] = provenance_metadata.get("parser_version", "1.0.0")

    # --------------------------------------------------------------------------
    # 3. FLOW NORMALIZATION: u = q / N
    # Compute normalized share units per ETF share outstanding (N) to isolate
    # portfolio manager reallocations from passive creation/redemption expansions.
    # --------------------------------------------------------------------------
    df["u_normalized"] = np.where(
        df["etf_shares_outstanding"] > 0,
        df["shares_held"] / df["etf_shares_outstanding"],
        0.0
    )

    # --------------------------------------------------------------------------
    # 4. ACTIVE QUANTITY DEVIATION (AQD)
    # Measure deviations between actual shares held and expected shares scaled
    # purely by changes in the fund's total shares outstanding:
    #   ExpectedQ_{f,i,t} = q_{f,i,t-1} * (N_{f,t} / N_{f,t-1})
    #   AQD_{f,i,t} = q_{f,i,t} - ExpectedQ_{f,i,t}
    # --------------------------------------------------------------------------
    df = df.sort_values(by=["fund_id", "security_id", "effective_date"])

    lagged_q = df.groupby(["fund_id", "security_id"])["shares_held"].shift(1)
    lagged_n = df.groupby(["fund_id", "security_id"])["etf_shares_outstanding"].shift(1)

    fund_expansion_factor = np.where(
        (lagged_n > 0) & (df["etf_shares_outstanding"] > 0),
        df["etf_shares_outstanding"] / lagged_n,
        1.0
    )

    df["expected_q"] = lagged_q * fund_expansion_factor
    df["aqd"] = df["shares_held"] - df["expected_q"].fillna(0.0)

    # --------------------------------------------------------------------------
    # 5. POINT-IN-TIME INTEGRITY ENFORCEMENT
    # Filter observations: DecisionTime >= InformationAvailableTime
    # Guarantees zero look-ahead bias in backtests and signal evaluation queues.
    # --------------------------------------------------------------------------
    pit_mask = df["information_available_time"] <= decision_timestamp
    canonical_state_df = df[pit_mask].copy()

    """
Edge-TF Disclosure Agent Engine - Ingestion Normalizer
Path: src/ingestion/normalizer.py

Normalizes disparate ETF provider files, calculates per-unit exposure metrics (u = q / N),
computes Active Quantity Deviations (AQD), and enforces point-in-time data integrity.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Standard column mapping dictionary across known ETF issuers/formats
DEFAULT_SCHEMA_MAP: Dict[str, str] = {
    # Fund identifiers
    "fund_ticker": "fund_id",
    "etf_ticker": "fund_id",
    "fund_symbol": "fund_id",
    "fund": "fund_id",
    
    # Security identifiers
    "ticker": "raw_identifier",
    "symbol": "raw_identifier",
    "cusip": "raw_identifier",
    "sedol": "raw_identifier",
    "isin": "raw_identifier",
    "security_name": "security_name",
    "name": "security_name",
    
    # Quantities & Weights
    "shares": "shares_held",
    "quantity": "shares_held",
    "units": "shares_held",
    "weight": "portfolio_weight",
    "weight_percentage": "portfolio_weight",
    "market_value": "market_value",
    "market_val": "market_value",
    
    # Fund Level Metrics
    "shares_outstanding": "etf_shares_outstanding",
    "fund_shares": "etf_shares_outstanding",
    "nav": "fund_nav",
    "total_net_assets": "fund_net_assets",
}


@dataclass(frozen=True)
class IngestionMetadata:
    """Provenance tracking record for point-in-time audit trails."""
    issuer: str
    fund_id: str
    disclosure_type: str  # Rule 6c-11 Daily, N-PORT Monthly, Basket File
    portfolio_effective_date: date
    information_available_time: datetime
    file_checksum: str
    parser_version: str = "1.0.0"


class DisclosureNormalizer:
    """
    Standardizes ingestion payloads and calculates flow-invariant holdings metrics.
    """

    def __init__(self, schema_map: Optional[Dict[str, str]] = None):
        self.schema_map = schema_map or DEFAULT_SCHEMA_MAP

    def canonicalize_schema(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """
        Renames incoming variant columns into Edge-TF canonical names.
        """
        df = raw_df.copy()
        
        # Normalize column header casings and whitespace
        normalized_cols = {
            col: col.strip().lower().replace(" ", "_").replace("%", "percentage")
            for col in df.columns
        }
        df = df.rename(columns=normalized_cols)
        
        # Remap known variants to internal canonical schema
        remapped_cols = {
            col: self.schema_map[col]
            for col in df.columns
            if col in self.schema_map
        }
        df = df.rename(columns=remapped_cols)
        
        # Enforce minimum required fields
        required_fields = ["fund_id", "raw_identifier", "shares_held"]
        missing_fields = [f for f in required_fields if f not in df.columns]
        if missing_fields:
            raise ValueError(f"Schema normalization failed. Missing required fields: {missing_fields}")
            
        return df

    def compute_flow_normalized_units(
        self,
        df: pd.DataFrame,
        shares_held_col: str = "shares_held",
        etf_shares_col: str = "etf_shares_outstanding",
        output_col: str = "u_normalized"
    ) -> pd.DataFrame:
        """
        Calculates per-unit holdings: u = q / N.
        Filters out raw share changes caused solely by fund creations or redemptions.
        """
        norm_df = df.copy()
        
        # Handle cases where ETF shares outstanding is missing or zero
        if etf_shares_col not in norm_df.columns or norm_df[etf_shares_col].isnull().all():
            logger.warning("etf_shares_outstanding missing; defaulting u_normalized to raw shares (un-normalized).")
            norm_df[output_col] = norm_df[shares_held_col]
            return norm_df

        norm_df[output_col] = np.where(
            norm_df[etf_shares_col] > 0,
            norm_df[shares_held_col] / norm_df[etf_shares_col],
            0.0
        )
        return norm_df

    def compute_active_quantity_deviation(
        self,
        df: pd.DataFrame,
        fund_id_col: str = "fund_id",
        security_id_col: str = "canonical_id",
        date_col: str = "effective_date",
        shares_held_col: str = "shares_held",
        etf_shares_col: str = "etf_shares_outstanding",
    ) -> pd.DataFrame:
        """
        Calculates Active Quantity Deviation (AQD) relative to prior period fund scaling:
          ExpectedQ = q_{t-1} * (N_t / N_{t-1})
          AQD = q_t - ExpectedQ
        """
        res_df = df.copy()
        res_df = res_df.sort_values(by=[fund_id_col, security_id_col, date_col])

        # Lagged security quantity
        res_df["lagged_shares_held"] = (
            res_df.groupby([fund_id_col, security_id_col])[shares_held_col].shift(1)
        )
        
        # Lagged ETF total shares outstanding
        res_df["lagged_etf_shares"] = (
            res_df.groupby([fund_id_col, security_id_col])[etf_shares_col].shift(1)
        )

        # Fund-level scaling ratio
        scaling_ratio = np.where(
            (res_df["lagged_etf_shares"] > 0) & (res_df[etf_shares_col] > 0),
            res_df[etf_shares_col] / res_df["lagged_etf_shares"],
            1.0
        )

        res_df["expected_shares"] = res_df["lagged_shares_held"] * scaling_ratio
        
        # Active Quantity Deviation: Difference between actual shares and flow-scaled shares
        res_df["aqd"] = res_df[shares_held_col] - res_df["expected_shares"].fillna(0.0)
        
        # Drop temporary calculation columns
        res_df = res_df.drop(columns=["lagged_shares_held", "lagged_etf_shares"])
        return res_df

    def enforce_point_in_time(
        self,
        df: pd.DataFrame,
        decision_time: datetime,
        timestamp_col: str = "information_available_time"
    ) -> pd.DataFrame:
        """
        Applies point-in-time filtering: DecisionTime >= InformationAvailableTime.
        Guarantees zero future-information leakage into backtests or queues.
        """
        filtered_df = df.copy()
        if timestamp_col in filtered_df.columns:
            mask = pd.to_datetime(filtered_df[timestamp_col]) <= decision_time
            return filtered_df[mask].copy()
        return filtered_df

    def process(
        self,
        raw_df: pd.DataFrame,
        metadata: IngestionMetadata,
        decision_time: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Full ingestion pipeline normalization workflow.
        """
        # Step 1: Canonicalize Schema
        df = self.canonicalize_schema(raw_df)

        # Step 2: Attach Provenance and Audit Timestamps
        df["issuer"] = metadata.issuer
        df["disclosure_type"] = metadata.disclosure_type
        df["effective_date"] = pd.to_datetime(metadata.portfolio_effective_date).date()
        df["information_available_time"] = metadata.information_available_time
        df["file_checksum"] = metadata.file_checksum
        df["parser_version"] = metadata.parser_version

        # Step 3: Compute Flow-Invariant Units (u = q / N)
        df = self.compute_flow_normalized_units(df)

        # Step 4: Compute Active Quantity Deviation (AQD)
        if "canonical_id" in df.columns:
            sec_col = "canonical_id"
        else:
            sec_col = "raw_identifier"
            
        df = self.compute_active_quantity_deviation(
            df=df,
            fund_id_col="fund_id",
            security_id_col=sec_col,
            date_col="effective_date"
        )

        # Step 5: Point-in-Time Constraint Enforcement
        if decision_time is not None:
            df = self.enforce_point_in_time(df, decision_time)

        return df

    

