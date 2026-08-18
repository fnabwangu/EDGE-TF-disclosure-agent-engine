"""flow_decomposition.py
Computes simple decomposition placeholder values for unit tests.
"""

def compute_u_f_i_t(flows):
    """Return a simple normalized decomposition of flows (placeholder)."""
    total = sum(flows) or 1
    return [f / total for f in flows]
"""========================================================================================
MODULE: Flow Decomposition Engine (src/quant_engine/flow_decomposition.py)
PURPOSE: Decouple passive creation/redemption mechanics from active manager conviction.
========================================================================================

INPUT:
    - holdings_panel: Time-series table containing:
        * fund_id (f)
        * security_id (i)
        * effective_date (t)
        * raw_shares_held (q_{f,i,t})
        * etf_shares_outstanding (N_{f,t})

STEP 1: NORMALIZE UNIT SHARES (u)
    FOR EACH row IN holdings_panel:
        u_{f,i,t} = raw_shares_held / etf_shares_outstanding[cite: 1]
    COMMENT: Filters out raw size scaling; measures normalized ownership per ETF share.[cite: 1]

STEP 2: RETRIEVE HISTORICAL BASELINES (t - 1)
    GROUP holdings_panel BY fund_id, security_id SORTED BY effective_date:
        prev_q = LAG(raw_shares_held, 1)        # q_{f,i,t-1}[cite: 1]
    
    GROUP holdings_panel BY fund_id, effective_date:
        prev_N = LAG(etf_shares_outstanding, 1)  # N_{f,t-1}[cite: 1]

STEP 3: COMPUTE PASSIVE FLOW SCALING & EXPECTED QUANTITY
    FOR EACH position AT timestamp t:
        scaling_ratio = N_{f,t} / N_{f,t-1}[cite: 1]
        ExpectedQ_{f,i,t} = q_{f,i,t-1} * scaling_ratio[cite: 1]
    COMMENT: ExpectedQ is what the manager would hold if they only passively scaled the basket.[cite: 1]

STEP 4: ISOLATE ACTIVE QUANTITY DEVIATION (AQD)
    FOR EACH position AT timestamp t:
        AQD_{f,i,t} = raw_shares_held - ExpectedQ_{f,i,t}[cite: 1]
        AQD_pct = AQD_{f,i,t} / q_{f,i,t-1}

STEP 5: CLASSIFY DISCRETIONARY ALLOCATION INTENT
    IF AQD_{f,i,t} > threshold:
        SET signal_flag = "ACTIVE_ACCUMULATION"[cite: 1]
    ELSE IF AQD_{f,i,t} < -threshold:
        SET signal_flag = "ACTIVE_REDUCTION"[cite: 1]
    ELSE:
        SET signal_flag = "PASSIVE_FLOW_DRIFT"[cite: 1]

OUTPUT:
    - enriched_holdings_panel with [u, ExpectedQ, AQD, AQD_pct, signal_flag][cite: 1]
========================================================================================

Edge-TF / Reverse Engineering Alpha Engine
Module: src/quant_engine/flow_decomposition.py
Purpose: Isolate active managerial accumulation from creation/redemption noise.
"""

from typing import Optional
import numpy as np
import pandas as pd


def compute_normalized_units(
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
    holdings_df: pd.DataFrame,
    fund_id_col: str = "fund_id",
    security_id_col: str = "security_id",
    date_col: str = "effective_date",
    shares_col: str = "shares_held",
    etf_shares_col: str = "etf_shares_outstanding",
) -> pd.DataFrame:
    """Calculates Expected Quantity (ExpectedQ) and Active Quantity Deviation (AQD).

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


def filter_flow_distortion(
    df: pd.DataFrame,
    aqd_col: str = "aqd",
    threshold_shares: float = 0.0,
) -> pd.DataFrame:
    """Flags whether a share increase is genuinely active or purely creation-flow artifact."""
    df = df.copy()
    df["is_active_accumulation"] = df[aqd_col] > threshold_shares
    df["is_active_reduction"] = df[aqd_col] < -threshold_shares
    return df
