"""manager_graph.py
Deduplicated manager clusters and a simple HHI calculation.
"""

def compute_hhi(shares):
    """Compute concentration Herfindahl-Hirschman Index (percent shares list)."""
    return sum((s * 100) ** 2 for s in shares)
# ==============================================================================
# PIPELINE STEP: MANAGER INDEPENDENCE & CLUSTERING (manager_graph.py)
# ==============================================================================
# Operational Goal: Deduplicate ETF ownership into independent manager clusters (m),
# calculate true manager breadth (B_i), evaluate manager concentration (HHI),
# and quantify directional cross-manager agreement.
# ==============================================================================

from typing import Dict, List, Optional
import numpy as np
import pandas as pd

def compute_manager_graph_pipeline(
    holdings_df: pd.DataFrame,
    fund_to_cluster_map: Dict[str, str],
    holding_threshold: float = 0.001,
    delta_threshold: float = 0.0001
) -> pd.DataFrame:
    """
    Computes Independent-Manager Breadth (B), Concentration (HHI), and Directional Agreement.

    Inputs:
      - holdings_df: [date, fund_id, canonical_id, u_normalized, active_weight]
      - fund_to_cluster_map: Mapping of fund_id -> independent manager cluster ID
      - holding_threshold: Minimum per-unit exposure to qualify as an active position
      - delta_threshold: Minimum delta in u_normalized to register directional allocation change
    """
    df = holdings_df.copy()

    # --------------------------------------------------------------------------
    # 1. MANAGER CLUSTER MAPPING
    # Map each fund to its governing adviser / manager cluster.
    # --------------------------------------------------------------------------
    df["manager_cluster"] = df["fund_id"].map(fund_to_cluster_map).fillna(df["fund_id"])
    all_securities = pd.Index(df["canonical_id"].unique(), name="canonical_id")

    # --------------------------------------------------------------------------
    # 2. INDEPENDENT-MANAGER BREADTH (B_i)
    # Count unique, deduplicated manager clusters holding the security above threshold.
    # --------------------------------------------------------------------------
    active_mask = df["u_normalized"] > holding_threshold
    active_holdings = df[active_mask]

    manager_breadth = (
        active_holdings.groupby("canonical_id")["manager_cluster"]
        .nunique()
        .reindex(all_securities, fill_value=0)
        .rename("manager_breadth")
    )

    # --------------------------------------------------------------------------
    # 3. MANAGER HERFINDAHL CONCENTRATION (ManagerHHI_i = sum(s_m,i ^ 2))
    # Measure exposure dependency on a single institutional complex.
    # --------------------------------------------------------------------------
    cluster_exposures = (
        active_holdings.groupby(["canonical_id", "manager_cluster"])["u_normalized"]
        .sum()
        .reset_index()
    )
    
    total_sec_exposures = cluster_exposures.groupby("canonical_id")["u_normalized"].transform("sum")
    cluster_exposures["share"] = cluster_exposures["u_normalized"] / (total_sec_exposures + 1e-12)
    cluster_exposures["share_squared"] = cluster_exposures["share"] ** 2

    manager_hhi = (
        cluster_exposures.groupby("canonical_id")["share_squared"]
        .sum()
        .reindex(all_securities, fill_value=1.0)
        .rename("manager_hhi")
    )

    # --------------------------------------------------------------------------
    # 4. CROSS-MANAGER DIRECTIONAL AGREEMENT SCORE
    # Aggregate manager-level allocation sign: d_m,i in {-1, 0, +1}
    # Agreement = |sum(d_m,i)| / sum(|d_m,i|)
    # --------------------------------------------------------------------------
    df = df.sort_values(by=["manager_cluster", "canonical_id", "date"])
    
    # Manager-level aggregated delta
    mgr_panel = (
        df.groupby(["date", "manager_cluster", "canonical_id"])["u_normalized"]
        .sum()
        .reset_index()
    )
    
    mgr_panel["delta_u"] = (
        mgr_panel.groupby(["manager_cluster", "canonical_id"])["u_normalized"]
        .diff()
        .fillna(0.0)
    )

    mgr_panel["sign"] = np.select(
        [
            mgr_panel["delta_u"] > delta_threshold,
            mgr_panel["delta_u"] < -delta_threshold
        ],
        [1, -1],
        default=0
    )

    # Calculate net directional consensus across actively trading managers
    latest_signs = mgr_panel[mgr_panel["sign"] != 0]
    
    if not latest_signs.empty:
        net_direction = latest_signs.groupby("canonical_id")["sign"].sum()
        total_active_managers = latest_signs.groupby("canonical_id")["sign"].apply(lambda s: np.abs(s).sum())
        agreement_score = (
            (net_direction.abs() / total_active_managers)
            .reindex(all_securities, fill_value=0.0)
            .rename("manager_agreement")
        )
        signed_agreement = (
            (net_direction / total_active_managers)
            .reindex(all_securities, fill_value=0.0)
            .rename("signed_manager_agreement")
        )
    else:
        agreement_score = pd.Series(0.0, index=all_securities, name="manager_agreement")
        signed_agreement = pd.Series(0.0, index=all_securities, name="signed_manager_agreement")

    # --------------------------------------------------------------------------
    # 5. CONSOLIDATE OUTPUT PANEL
    # --------------------------------------------------------------------------
    results = pd.DataFrame(index=all_securities)
    results["manager_breadth"] = manager_breadth
    results["manager_hhi"] = manager_hhi
    results["manager_agreement"] = agreement_score
    results["signed_manager_agreement"] = signed_agreement

    # Standardize manager breadth for IAV engine: Z(B_i,h)
    b_mean = results["manager_breadth"].mean()
    b_std = results["manager_breadth"].std()
    results["z_manager_breadth"] = (
        (results["manager_breadth"] - b_mean) / (b_std if b_std > 0 else 1.0)
    )

    return results.reset_index()"""
Edge-TF Disclosure Agent Engine - Manager Graph & Independence Resolver
Path: src/quant_engine/manager_graph.py

Maps ETF holdings to independent manager clusters, resolves duplicate fund complexes,
calculates Herfindahl manager concentration (HHI), and scores directional cross-manager agreement.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ManagerMetadata:
    """Institutional metadata describing an ETF's administrative and operational lineage."""
    fund_id: str
    adviser: str
    subadviser: Optional[str] = None
    portfolio_team: Optional[str] = None
    index_provider: Optional[str] = None
    strategy_family: Optional[str] = None

    @property
    def cluster_id(self) -> str:
        """Resolves primary manager cluster identity based on subadviser or adviser."""
        if self.subadviser and self.subadviser.strip():
            return f"SUB_{self.subadviser.strip().upper()}"
        if self.portfolio_team and self.portfolio_team.strip():
            return f"TEAM_{self.portfolio_team.strip().upper()}"
        return f"ADV_{self.adviser.strip().upper()}"


@dataclass
class SecurityManagerMetrics:
    """Computed manager network metrics for a single security."""
    canonical_id: str
    manager_breadth: int
    manager_hhi: float
    directional_agreement: float
    signed_agreement: float
    z_breadth: float
    active_clusters: List[str] = field(default_factory=list)


class ManagerGraphEngine:
    """
    Constructs manager-to-fund relationship graphs and evaluates cross-manager consensus.
    """

    def __init__(
        self,
        manager_registry: Optional[Dict[str, ManagerMetadata]] = None,
        holding_threshold: float = 0.001,
        delta_threshold: float = 0.0001,
    ):
        self.manager_registry = manager_registry or {}
        self.holding_threshold = holding_threshold
        self.delta_threshold = delta_threshold

    def get_cluster_id(self, fund_id: str) -> str:
        """Maps an ETF fund_id to its resolved manager cluster."""
        if fund_id in self.manager_registry:
            return self.manager_registry[fund_id].cluster_id
        return f"FUND_{fund_id.upper()}"

    def compute_cluster_breadth(
        self,
        df: pd.DataFrame,
        security_id_col: str = "canonical_id",
        fund_id_col: str = "fund_id",
        holding_col: str = "u_normalized",
    ) -> pd.Series:
        """
        Computes the deduplicated count of independent manager clusters holding security i.
        """
        active_df = df[df[holding_col] > self.holding_threshold].copy()
        if active_df.empty:
            return pd.Series(0, index=df[security_id_col].unique(), name="manager_breadth")

        active_df["cluster_id"] = active_df[fund_id_col].map(self.get_cluster_id)
        
        breadth = (
            active_df.groupby(security_id_col)["cluster_id"]
            .nunique()
            .rename("manager_breadth")
        )
        return breadth

    def compute_manager_hhi(
        self,
        df: pd.DataFrame,
        security_id_col: str = "canonical_id",
        fund_id_col: str = "fund_id",
        holding_col: str = "u_normalized",
    ) -> pd.Series:
        """
        Calculates Herfindahl-Hirschman Index of manager concentration:
          HHI_i = sum_m (s_{m,i}^2)
        """
        active_df = df[df[holding_col] > self.holding_threshold].copy()
        if active_df.empty:
            return pd.Series(1.0, index=df[security_id_col].unique(), name="manager_hhi")

        active_df["cluster_id"] = active_df[fund_id_col].map(self.get_cluster_id)

        # Sum exposure per cluster
        cluster_sum = (
            active_df.groupby([security_id_col, "cluster_id"])[holding_col]
            .sum()
            .reset_index()
        )
        
        total_sum = cluster_sum.groupby(security_id_col)[holding_col].transform("sum")
        cluster_sum["share"] = cluster_sum[holding_col] / (total_sum + 1e-12)
        cluster_sum["share_sq"] = cluster_sum["share"] ** 2

        hhi = cluster_sum.groupby(security_id_col)["share_sq"].sum().rename("manager_hhi")
        return hhi

    def compute_directional_agreement(
        self,
        df: pd.DataFrame,
        security_id_col: str = "canonical_id",
        fund_id_col: str = "fund_id",
        date_col: str = "effective_date",
        holding_col: str = "u_normalized",
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Calculates consensus agreement across independent manager allocation changes.
        Returns (unsigned_agreement, signed_agreement).
        """
        work_df = df.copy()
        work_df["cluster_id"] = work_df[fund_id_col].map(self.get_cluster_id)
        
        # Aggregate holdings to (date, cluster_id, security)
        panel = (
            work_df.groupby([date_col, "cluster_id", security_id_col])[holding_col]
            .sum()
            .reset_index()
            .sort_values(by=["cluster_id", security_id_col, date_col])
        )

        panel["delta"] = panel.groupby(["cluster_id", security_id_col])[holding_col].diff().fillna(0.0)

        panel["sign"] = np.select(
            [
                panel["delta"] > self.delta_threshold,
                panel["delta"] < -self.delta_threshold,
            ],
            [1, -1],
            default=0,
        )

        active_changes = panel[panel["sign"] != 0]
        all_secs = pd.Index(df[security_id_col].unique(), name=security_id_col)

        if active_changes.empty:
            zeros = pd.Series(0.0, index=all_secs)
            return zeros.rename("agreement"), zeros.rename("signed_agreement")

        net_sum = active_changes.groupby(security_id_col)["sign"].sum()
        total_active = active_changes.groupby(security_id_col)["sign"].apply(lambda s: np.abs(s).sum())

        unsigned_agreement = (net_sum.abs() / total_active).reindex(all_secs, fill_value=0.0)
        signed_agreement = (net_sum / total_active).reindex(all_secs, fill_value=0.0)

        return unsigned_agreement.rename("agreement"), signed_agreement.rename("signed_agreement")

    def process_manager_network(
        self,
        holdings_df: pd.DataFrame,
        security_id_col: str = "canonical_id",
        fund_id_col: str = "fund_id",
        date_col: str = "effective_date",
        holding_col: str = "u_normalized",
    ) -> pd.DataFrame:
        """
        Unified processing pipeline: calculates Breadth, HHI, Agreement, and Z-scores.
        """
        if holdings_df.empty:
            return pd.DataFrame(
                columns=[
                    security_id_col,
                    "manager_breadth",
                    "manager_hhi",
                    "manager_agreement",
                    "signed_manager_agreement",
                    "z_manager_breadth",
                ]
            )

        all_secs = pd.Index(holdings_df[security_id_col].unique(), name=security_id_col)

        # 1. Independent Manager Breadth
        breadth = self.compute_cluster_breadth(
            holdings_df, security_id_col, fund_id_col, holding_col
        ).reindex(all_secs, fill_value=0)

        # 2. Manager HHI
        hhi = self.compute_manager_hhi(
            holdings_df, security_id_col, fund_id_col, holding_col
        ).reindex(all_secs, fill_value=1.0)

        # 3. Directional Agreement
        unsigned_agr, signed_agr = self.compute_directional_agreement(
            holdings_df, security_id_col, fund_id_col, date_col, holding_col
        )

        results = pd.DataFrame(index=all_secs)
        results["manager_breadth"] = breadth
        results["manager_hhi"] = hhi
        results["manager_agreement"] = unsigned_agr
        results["signed_manager_agreement"] = signed_agr

        # 4. Standardized Z-Score for IAV Engine
        b_mean = results["manager_breadth"].mean()
        b_std = results["manager_breadth"].std()
        results["z_manager_breadth"] = (
            (results["manager_breadth"] - b_mean) / (b_std if b_std > 0 else 1.0)
        ).fillna(0.0)

        return results.reset_index()
