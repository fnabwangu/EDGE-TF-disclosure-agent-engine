"""diffusion_scorer.py
Placeholder that scores theme diffusion between nodes.
"""

def diffusion_score(node_a, node_b):
    # simplistic constant score
    return 0.5
# ==============================================================================
# PIPELINE STEP: STRATEGIC THEME DIFFUSION SCORING (diffusion_scorer.py)
# ==============================================================================
# Operational Goal: Quantify cross-thematic portfolio migration (D_i,h) by tracking
# how a security expands into distinct strategic themes, weighted by ontological distance
# and filtered for active conviction thresholds.
# ==============================================================================

from typing import Dict, List, Optional
import numpy as np
import pandas as pd

def compute_theme_diffusion_pipeline(
    holdings_df: pd.DataFrame,
    fund_theme_map: Dict[str, str],
    ontology_distance_matrix: Optional[pd.DataFrame] = None,
    active_weight_threshold: float = 0.01
) -> pd.DataFrame:
    """
    Computes Strategic Theme Diffusion metrics across securities.
    
    Inputs:
      - holdings_df: [fund_id, canonical_id, portfolio_weight, active_weight]
      - fund_theme_map: Dictionary mapping fund_id -> primary strategic theme
      - ontology_distance_matrix: Matrix specifying semantic distance between thematic pairs
      - active_weight_threshold: Minimum allocation required to represent meaningful ownership
    """
    df = holdings_df.copy()

    # --------------------------------------------------------------------------
    # 1. THEME ASSIGNMENT & CONVICTION FILTERING
    # Filter for positions meeting the minimum active conviction threshold.
    # --------------------------------------------------------------------------
    df["theme_id"] = df["fund_id"].map(fund_theme_map)
    qualifying_mask = df["portfolio_weight"] >= active_weight_threshold
    qualified_df = df[qualifying_mask].copy()

    # --------------------------------------------------------------------------
    # 2. RAW THEME BREADTH COUNT: D_raw = |Theta_i|
    # Count unique strategic thematic mandates adopting each security.
    # --------------------------------------------------------------------------
    all_securities = pd.Index(df["canonical_id"].unique(), name="canonical_id")
    
    raw_diffusion = (
        qualified_df.groupby("canonical_id")["theme_id"]
        .nunique()
        .reindex(all_securities, fill_value=0)
        .rename("raw_theme_diffusion")
    )

    results_df = pd.DataFrame(index=all_securities)
    results_df["raw_theme_diffusion"] = raw_diffusion

    # --------------------------------------------------------------------------
    # 3. ONTOLOGY-WEIGHTED STRATEGIC DIFFUSION
    # Scale diffusion by pairwise ontological distance between adopted themes
    # to avoid double-counting overlapping/adjacent fund categories.
    # --------------------------------------------------------------------------
    if ontology_distance_matrix is not None:
        weighted_scores = {}
        for sec_id, group in qualified_df.groupby("canonical_id"):
            unique_themes = group["theme_id"].dropna().unique()
            if len(unique_themes) <= 1:
                weighted_scores[sec_id] = float(len(unique_themes))
            else:
                # Calculate mean ontological distance between all adopted theme pairs
                distances = []
                for i in range(len(unique_themes)):
                    for j in range(i + 1, len(unique_themes)):
                        t1, t2 = unique_themes[i], unique_themes[j]
                        dist = ontology_distance_matrix.loc[t1, t2] if (
                            t1 in ontology_distance_matrix.index and t2 in ontology_distance_matrix.columns
                        ) else 1.0
                        distances.append(dist)
                
                # Base score scaled by mean cross-thematic semantic divergence
                mean_dist = np.mean(distances) if distances else 1.0
                weighted_scores[sec_id] = float(len(unique_themes)) * mean_dist

        results_df["weighted_diffusion_score"] = (
            pd.Series(weighted_scores).reindex(all_securities, fill_value=0.0)
        )
    else:
        results_df["weighted_diffusion_score"] = results_df["raw_theme_diffusion"].astype(float)

    # --------------------------------------------------------------------------
    # 4. STANDARDIZATION: Z(D_i,h) FOR IAV AGGREGATION
    # --------------------------------------------------------------------------
    mean_val = results_df["weighted_diffusion_score"].mean()
    std_val = results_df["weighted_diffusion_score"].std()
    results_df["z_diffusion"] = (
        (results_df["weighted_diffusion_score"] - mean_val) / (std_val + 1e-6)
    )
    """
Edge-TF Disclosure Agent Engine - Strategic Theme Diffusion Scorer
Path: src/ontology/diffusion_scorer.py

Calculates cross-thematic diffusion metrics (D_i,h) for securities across
disclosed ETF portfolios, weighting expansion by ontological thematic distance.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


@dataclass
class DiffusionMetrics:
    """Standardized output container for security theme diffusion."""
    canonical_id: str
    raw_theme_count: int
    weighted_diffusion_score: float
    z_diffusion_score: float
    adopted_themes: List[str] = field(default_factory=list)


class StrategicDiffusionScorer:
    """
    Computes theme diffusion across ETF portfolios to measure cross-domain thesis migration.
    """

    def __init__(
        self,
        fund_theme_map: Dict[str, str],
        ontology_distance_matrix: Optional[pd.DataFrame] = None,
        min_holding_threshold: float = 0.005,
    ):
        """
        Args:
            fund_theme_map: Mapping of fund_id -> primary theme string.
            ontology_distance_matrix: Precomputed pairwise distance matrix between themes.
            min_holding_threshold: Minimum portfolio weight (e.g., 0.5%) to qualify as active adoption.
        """
        self.fund_theme_map = fund_theme_map
        self.distance_matrix = ontology_distance_matrix
        self.min_threshold = min_holding_threshold

    def calculate_pairwise_distance(self, theme_a: str, theme_b: str) -> float:
        """
        Retrieves ontological distance between two strategic themes.
        Defaults to 1.0 (distinct) if not present in the distance matrix.
        """
        if self.distance_matrix is None:
            return 1.0
        if theme_a == theme_b:
            return 0.0

        if theme_a in self.distance_matrix.index and theme_b in self.distance_matrix.columns:
            return float(self.distance_matrix.loc[theme_a, theme_b])
        return 1.0

    def score_security_diffusion(
        self,
        security_holdings: pd.DataFrame,
        weight_col: str = "portfolio_weight",
    ) -> Dict[str, Any]:
        """
        Calculates raw and ontologically weighted diffusion scores for a single security group.
        """
        # Filter for qualifying holdings
        qualifying = security_holdings[security_holdings[weight_col] >= self.min_threshold].copy()
        if qualifying.empty:
            return {
                "raw_theme_count": 0,
                "weighted_score": 0.0,
                "themes": [],
            }

        # Resolve unique themes
        themes = list(
            {
                self.fund_theme_map[f_id]
                for f_id in qualifying["fund_id"]
                if f_id in self.fund_theme_map
            }
        )

        n_themes = len(themes)
        if n_themes <= 1:
            return {
                "raw_theme_count": n_themes,
                "weighted_score": float(n_themes),
                "themes": themes,
            }

        # Compute average ontological distance across all theme pairs
        pairwise_distances: List[float] = []
        for i in range(n_themes):
            for j in range(i + 1, n_themes):
                dist = self.calculate_pairwise_distance(themes[i], themes[j])
                pairwise_distances.append(dist)

        mean_distance = np.mean(pairwise_distances) if pairwise_distances else 1.0
        weighted_score = n_themes * mean_distance

        return {
            "raw_theme_count": n_themes,
            "weighted_score": float(weighted_score),
            "themes": themes,
        }

    def compute_diffusion_panel(
        self,
        holdings_df: pd.DataFrame,
        security_id_col: str = "canonical_id",
        fund_id_col: str = "fund_id",
        weight_col: str = "portfolio_weight",
    ) -> pd.DataFrame:
        """
        Processes a full holdings dataframe and produces standardized diffusion scores.
        """
        if holdings_df.empty:
            return pd.DataFrame(
                columns=[
                    security_id_col,
                    "raw_theme_count",
                    "weighted_diffusion_score",
                    "z_diffusion",
                    "adopted_themes",
                ]
            )

        records = []
        for sec_id, sec_group in holdings_df.groupby(security_id_col):
            score_data = self.score_security_diffusion(sec_group, weight_col=weight_col)
            records.append({
                security_id_col: sec_id,
                "raw_theme_count": score_data["raw_theme_count"],
                "weighted_diffusion_score": score_data["weighted_score"],
                "adopted_themes": score_data["themes"],
            })

        result_df = pd.DataFrame(records)

        # Standardize for downstream IAV aggregation
        raw_scores = result_df["weighted_diffusion_score"]
        std = raw_scores.std()
        mean = raw_scores.mean()

        result_df["z_diffusion"] = (
            (raw_scores - mean) / (std if std > 0 else 1.0)
        ).fillna(0.0)

        return result_df.sort_values(by="weighted_diffusion_score", ascending=False)

