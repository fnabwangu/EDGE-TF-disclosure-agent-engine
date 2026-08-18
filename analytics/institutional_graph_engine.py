"""
Edge-TF Disclosure Agent Engine - Institutional Graph Engine
Path: analytics/institutional_graph_engine.py

Calculates cross-thematic diffusion metrics (D_i,h) for securities across
disclosed ETF portfolios using NetworkX PageRank and centrality measures,
weighting expansion by ontological thematic distance.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
import numpy as np
import pandas as pd
import networkx as nx
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
    centrality_score: float = 0.0


class InstitutionalGraphEngine:
    """
    Computes theme diffusion across ETF portfolios to measure cross-domain thesis migration.
    Uses NetworkX PageRank and centrality measures to quantify institutional adoption patterns.
    """

    def __init__(
        self,
        fund_theme_map: Optional[Dict[str, str]] = None,
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
        self.graph = nx.DiGraph()

    def update_graph(self, manager: str, ticker: str, weight: float) -> None:
        """Add or replace a deterministic manager-to-security edge."""
        if weight < 0:
            raise ValueError("Graph edge weights cannot be negative.")
        self.graph.add_edge(manager, ticker, weight=float(weight))

    def calculate_diffusion_score(self, target_ticker: str) -> float:
        """Return the target's weighted PageRank score, or zero if unknown."""
        if not self.graph.has_node(target_ticker):
            return 0.0
        scores = nx.pagerank(self.graph, weight="weight")
        return float(scores.get(target_ticker, 0.0))

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
                "centrality": 0.0,
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
                "centrality": 0.0,
            }

        # Compute average ontological distance across all theme pairs
        pairwise_distances: List[float] = []
        for i in range(n_themes):
            for j in range(i + 1, n_themes):
                dist = self.calculate_pairwise_distance(themes[i], themes[j])
                pairwise_distances.append(dist)

        mean_distance = np.mean(pairwise_distances) if pairwise_distances else 1.0
        weighted_score = n_themes * mean_distance

        # Compute centrality (average degree of theme adoption)
        centrality = mean_distance * (n_themes / (n_themes + 1)) if n_themes > 0 else 0.0

        return {
            "raw_theme_count": n_themes,
            "weighted_score": float(weighted_score),
            "themes": themes,
            "centrality": float(centrality),
        }

    def compute_diffusion_panel(
        self,
        holdings_df: pd.DataFrame,
        security_id_col: str = "canonical_id",
        fund_id_col: str = "fund_id",
        weight_col: str = "portfolio_weight",
    ) -> pd.DataFrame:
        """
        Processes a full holdings dataframe and produces standardized diffusion scores
        incorporating institutional centrality measures.
        """
        if holdings_df.empty:
            return pd.DataFrame(
                columns=[
                    security_id_col,
                    "raw_theme_count",
                    "weighted_diffusion_score",
                    "z_diffusion",
                    "centrality_score",
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
                "centrality_score": score_data["centrality"],
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

    def build_institutional_graph(
        self,
        holdings_df: pd.DataFrame,
        fund_id_col: str = "fund_id",
        security_id_col: str = "canonical_id",
        weight_col: str = "portfolio_weight",
    ) -> Dict[str, Any]:
        """
        Constructs institutional adoption graph for PageRank analysis.
        Returns network structure suitable for centrality computation.
        """
        if holdings_df.empty:
            return {"nodes": [], "edges": [], "weights": {}}

        # Build bipartite fund-security graph
        qualifying = holdings_df[holdings_df[weight_col] >= self.min_threshold].copy()
        
        edges = []
        weights = {}
        
        for _, row in qualifying.iterrows():
            fund = row[fund_id_col]
            security = row[security_id_col]
            weight = row[weight_col]
            
            edges.append((fund, security))
            weights[(fund, security)] = float(weight)
            self.update_graph(fund, security, float(weight))

        nodes = set()
        for edge in edges:
            nodes.update(edge)

        return {
            "nodes": list(nodes),
            "edges": edges,
            "weights": weights,
        }
