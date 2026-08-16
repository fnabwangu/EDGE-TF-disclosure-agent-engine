# src/inference/__init__.py
"""
EDGE-TF Disclosure Agent Engine - Quantitative Inference & Alpha Generation Module.

Exposes signal generation pipelines, cross-sectional factor scoring engines,
and systematic derivative overlay selectors for ETF portfolio construction.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class FactorType(str, Enum):
    MOMENTUM = "MOMENTUM"
    QUALITY = "QUALITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    VALUE = "VALUE"
    SENTIMENT = "SENTIMENT"


@dataclass
class ConstituentScore:
    ticker: str
    composite_score: float
    rank: int
    factor_breakdown: Dict[FactorType, float]
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class CrossSectionalAlphaEngine:
    """
    Computes normalized cross-sectional factor Z-scores and composite alpha rankings
    across a defined equity universe for systematic ETF rebalancing.
    """

    def __init__(self, factor_weights: Optional[Dict[FactorType, float]] = None):
        self.factor_weights = factor_weights or {
            FactorType.MOMENTUM: 0.40,
            FactorType.QUALITY: 0.30,
            FactorType.LOW_VOLATILITY: 0.30,
        }
        self._validate_weights()

    def _validate_weights(self):
        total_w = sum(self.factor_weights.values())
        if not np.isclose(total_w, 1.0, atol=1e-4):
            raise ValueError(f"Factor weights must sum to 1.0; got {total_w:.4f}")

    @staticmethod
    def _compute_zscores(series: pd.Series, winsorize_std: float = 3.0) -> pd.Series:
        """Calculates winsorized and standard deviation-normalized Z-scores."""
        std = series.std(ddof=0)
        if std == 0 or np.isnan(std):
            return pd.Series(0.0, index=series.index)
        mean = series.mean()
        z = (series - mean) / std
        return z.clip(lower=-winsorize_std, upper=winsorize_std)

    def score_universe(self, raw_factor_df: pd.DataFrame) -> List[ConstituentScore]:
        """
        Takes a DataFrame indexed by ticker with raw factor metrics, computes
        standardized factor Z-scores, and generates rank-ordered alpha scores.
        """
        if raw_factor_df.empty:
            logging.warning("Empty factor matrix provided to CrossSectionalAlphaEngine.")
            return []

        df_scored = pd.DataFrame(index=raw_factor_df.index)
        zscore_map: Dict[FactorType, pd.Series] = {}

        for factor, weight in self.factor_weights.items():
            col_name = factor.value.lower()
            if col_name in raw_factor_df.columns:
                z = self._compute_zscores(raw_factor_df[col_name])
                zscore_map[factor] = z
                df_scored[col_name + "_z"] = z * weight
            else:
                logging.warning(f"Factor column '{col_name}' missing from input data. Imputing zero.")
                zscore_map[factor] = pd.Series(0.0, index=raw_factor_df.index)
                df_scored[col_name + "_z"] = 0.0

        # Composite weighted alpha score
        df_scored["composite_alpha"] = df_scored.sum(axis=1)
        df_scored["rank"] = df_scored["composite_alpha"].rank(ascending=False, method="min").astype(int)

        scores: List[ConstituentScore] = []
        for ticker in df_scored.index:
            f_breakdown = {
                factor: float(zscore_map[factor].get(ticker, 0.0))
                for factor in self.factor_weights
            }
            scores.append(
                ConstituentScore(
                    ticker=str(ticker),
                    composite_score=float(df_scored.loc[ticker, "composite_alpha"]),
                    rank=int(df_scored.loc[ticker, "rank"]),
                    factor_breakdown=f_breakdown,
                )
            )

        scores.sort(key=lambda x: x.rank)
        return scores


__all__ = [
    "FactorType",
    "ConstituentScore",
    "CrossSectionalAlphaEngine",
]# inference package
