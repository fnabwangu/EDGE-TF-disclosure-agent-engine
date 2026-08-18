"""persistence.py
Multi-period exponential persistence decay (placeholder).
"""
import math

def persistence_decay(value: float, half_life_periods: float, periods: int) -> float:
    rate = math.log(2) / half_life_periods
    return value * math.exp(-rate * periods)
"""========================================================================================
MODULE: Persistence & Half-Life Decay Engine (src/quant_engine/persistence.py)
PURPOSE: Discriminate between transient single-observation anomalies and durable, 
         multi-period institutional accumulation using exponential memory decay.
========================================================================================

INPUT:
    - signal_time_series: Historical series of Active Quantity Deviation (AQD) or 
      per-unit holding changes (Δu) for a given security i across rolling timestamps t[cite: 1].
    - delta (δ): Exponential decay factor (e.g., 0.95), where 0 < δ <= 1[cite: 1].
    - window (k): Number of consecutive observation periods (e.g., 20d, 60d, 180d)[cite: 1].

STEP 1: TIME-SERIES SLICING & VALIDATION
    FOR EACH security i IN holdings_panel:
        EXTRACT the last k sequential historical observations:
            V = [v_1, v_2, ..., v_k] where v_k is the most recent observation[cite: 1].
        IF length(V) < k:
            PAD or RETURN fractional persistence score based on available sample depth[cite: 1].

STEP 2: EXPONENTIAL HALF-LIFE WEIGHT GENERATION
    GENERATE geometric lag weight vector:
        W = [w_1, w_2, ..., w_k]
        WHERE w_j = δ ^ (k - j) for j in [1, 2, ..., k][cite: 1]
    NORMALIZE weights:
        W_norm = W / SUM(W)

STEP 3: COMPUTE WEIGHTED PERSISTENCE METRIC
    Persistence_i = DOT_PRODUCT(V, W_norm) = SUM(v_j * w_j) / SUM(w_j)[cite: 1]
    COMMENT: Gives greater informational weight to recent disclosures while 
             requiring multi-period directional consistency[cite: 1].

STEP 4: ROLLING MULTI-HORIZON ACCELERATION
    COMPUTE Persistence across rolling horizons:
        - P_short  = Persistence(window = 20)[cite: 1]
        - P_medium = Persistence(window = 60)[cite: 1]
        - P_long   = Persistence(window = 180)[cite: 1]
    
    Persistence_Acceleration = P_short - P_medium[cite: 1]

STEP 5: PERSISTENCE FILTER & THRESHOLDING
    IF Persistence_i >= persistence_threshold AND Persistence_Acceleration > 0:
        SET persistence_status = "DURABLE_ACCUMULATION"[cite: 1]
    ELSE IF Persistence_i < 0:
        SET persistence_status = "DURABLE_DISTRIBUTION"[cite: 1]
    ELSE:
        SET persistence_status = "TRANSIENT_NOISE"[cite: 1]

OUTPUT:
    - Persistence metrics table with [P_short, P_medium, P_long, Persistence_Acceleration, persistence_status][cite: 1].
========================================================================================

Edge-TF / Reverse Engineering Alpha Engine
Module: src/quant_engine/persistence.py
Purpose: Evaluate signal durability and exponential decay over multi-horizon windows.
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd


def compute_exponential_weights(delta: float, window: int) -> np.ndarray:
    """Generates normalized exponentially decaying weights for a given window.

    w_j = delta ^ (window - j - 1) for j in range(window)
    """
    taus = np.arange(window)
    # Most recent observation gets delta^0 = 1.0, oldest gets delta^(window-1)
    raw_weights = delta ** (window - 1 - taus)
    return raw_weights / np.sum(raw_weights)


def apply_persistence_decay(
    series: pd.Series,
    delta: float = 0.95,
    window: int = 20,
    min_periods: Optional[int] = None,
) -> float:
    """Calculates exponentially weighted persistence on a 1D slice of historical signals.

    Persistence = sum(v_j * w_j) / sum(w_j)
    """
    if min_periods is None:
        min_periods = max(1, window // 2)

    valid_vals = series.dropna().values
    n_obs = len(valid_vals)

    if n_obs < min_periods:
        return 0.0

    actual_window = min(n_obs, window)
    vals_slice = valid_vals[-actual_window:]
    weights = compute_exponential_weights(delta, actual_window)

    return float(np.dot(vals_slice, weights))


def compute_multi_horizon_persistence(
    df_signals: pd.DataFrame,
    security_id_col: str = "security_id",
    date_col: str = "effective_date",
    signal_col: str = "aqd",
    delta: float = 0.95,
    windows: Optional[Dict[str, int]] = None,
) -> pd.DataFrame:
    """Computes rolling persistence scores across Short (20d), Medium (60d),

    and Long (180d) observation horizons, along with persistence acceleration.
    """
    if windows is None:
        windows = {"short": 20, "medium": 60, "long": 180}

    df = df_signals.sort_values(by=[security_id_col, date_col]).copy()
    results: List[Dict[str, float]] = []

    for sec_id, group in df.groupby(security_id_col):
        sig_series = group[signal_col]
        row_dict: Dict[str, float] = {security_id_col: sec_id}

        for name, win in windows.items():
            col_name = f"persist_{name}"
            row_dict[col_name] = apply_persistence_decay(
                sig_series, delta=delta, window=win
            )

        # Persistence Acceleration: delta between short-term adoption and intermediate trend
        row_dict["persist_acceleration"] = (
            row_dict["persist_short"] - row_dict["persist_medium"]
        )

        results.append(row_dict)

    out_df = pd.DataFrame(results).set_index(security_id_col)
    return out_df


def classify_persistence_regime(
    persistence_score: float,
    acceleration: float,
    threshold: float = 0.0,
) -> str:
    """Classifies temporal accumulation quality into structured persistence regimes."""
    if persistence_score > threshold and acceleration >= 0.0:
        return "ACCELERATING_PERSISTENCE"
    elif persistence_score > threshold and acceleration < 0.0:
        return "DECELERATING_ACCUMULATION"
    elif persistence_score < -threshold:
        return "PERSISTENT_DISTRIBUTION"
    return "TRANSIENT_NEUTRAL"
