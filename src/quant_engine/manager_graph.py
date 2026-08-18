"""Independent manager clustering and breadth analytics."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ManagerMetadata:
    fund_id: str
    adviser: str
    subadviser: Optional[str] = None
    portfolio_team: Optional[str] = None
    index_provider: Optional[str] = None
    strategy_family: Optional[str] = None

    @property
    def cluster_id(self) -> str:
        if self.subadviser and self.subadviser.strip():
            return f"SUB_{self.subadviser.strip().upper()}"
        if self.portfolio_team and self.portfolio_team.strip():
            return f"TEAM_{self.portfolio_team.strip().upper()}"
        return f"ADV_{self.adviser.strip().upper()}"


@dataclass
class SecurityManagerMetrics:
    canonical_id: str
    manager_breadth: int
    manager_hhi: float
    directional_agreement: float
    signed_agreement: float
    z_breadth: float
    active_clusters: List[str] = field(default_factory=list)


class ManagerGraphEngine:
    def __init__(self, manager_registry: Optional[Dict[str, ManagerMetadata]] = None, holding_threshold: float = 0.001, delta_threshold: float = 0.0001):
        self.manager_registry = manager_registry or {}
        self.holding_threshold = holding_threshold
        self.delta_threshold = delta_threshold

    def get_cluster_id(self, fund_id: str) -> Optional[str]:
        """Return known manager lineage; unknown funds are excluded from breadth."""
        metadata = self.manager_registry.get(fund_id)
        return metadata.cluster_id if metadata else None

    def _active_with_clusters(self, df: pd.DataFrame, fund_id_col: str, holding_col: str) -> pd.DataFrame:
        active = df[df[holding_col] > self.holding_threshold].copy()
        active["cluster_id"] = active[fund_id_col].map(self.get_cluster_id)
        return active[active["cluster_id"].notna()]

    def compute_cluster_breadth(self, df: pd.DataFrame, security_id_col: str = "canonical_id", fund_id_col: str = "fund_id", holding_col: str = "u_normalized") -> pd.Series:
        active = self._active_with_clusters(df, fund_id_col, holding_col)
        if active.empty:
            return pd.Series(0, index=df[security_id_col].unique(), name="manager_breadth")
        return active.groupby(security_id_col)["cluster_id"].nunique().rename("manager_breadth")

    def compute_manager_hhi(self, df: pd.DataFrame, security_id_col: str = "canonical_id", fund_id_col: str = "fund_id", holding_col: str = "u_normalized") -> pd.Series:
        active = self._active_with_clusters(df, fund_id_col, holding_col)
        if active.empty:
            return pd.Series(1.0, index=df[security_id_col].unique(), name="manager_hhi")
        exposure = active.groupby([security_id_col, "cluster_id"])[holding_col].sum().reset_index()
        total = exposure.groupby(security_id_col)[holding_col].transform("sum")
        exposure["share_sq"] = (exposure[holding_col] / total) ** 2
        return exposure.groupby(security_id_col)["share_sq"].sum().rename("manager_hhi")

    def compute_directional_agreement(self, df: pd.DataFrame, security_id_col: str = "canonical_id", fund_id_col: str = "fund_id", date_col: str = "effective_date", holding_col: str = "u_normalized") -> Tuple[pd.Series, pd.Series]:
        work = df.copy()
        work["cluster_id"] = work[fund_id_col].map(self.get_cluster_id)
        work = work[work["cluster_id"].notna()]
        all_securities = pd.Index(df[security_id_col].unique(), name=security_id_col)
        if work.empty:
            zeros = pd.Series(0.0, index=all_securities)
            return zeros.rename("agreement"), zeros.rename("signed_agreement")
        panel = work.groupby([date_col, "cluster_id", security_id_col])[holding_col].sum().reset_index()
        panel = panel.sort_values(["cluster_id", security_id_col, date_col])
        panel["delta"] = panel.groupby(["cluster_id", security_id_col])[holding_col].diff().fillna(0.0)
        panel["sign"] = np.select([panel["delta"] > self.delta_threshold, panel["delta"] < -self.delta_threshold], [1, -1], default=0)
        changes = panel[panel["sign"] != 0]
        if changes.empty:
            zeros = pd.Series(0.0, index=all_securities)
            return zeros.rename("agreement"), zeros.rename("signed_agreement")
        net = changes.groupby(security_id_col)["sign"].sum()
        total = changes.groupby(security_id_col)["sign"].apply(lambda values: np.abs(values).sum())
        return ((net.abs() / total).reindex(all_securities, fill_value=0.0).rename("agreement"), (net / total).reindex(all_securities, fill_value=0.0).rename("signed_agreement"))

    def process_manager_network(self, holdings_df: pd.DataFrame, security_id_col: str = "canonical_id", fund_id_col: str = "fund_id", date_col: str = "effective_date", holding_col: str = "u_normalized") -> pd.DataFrame:
        if holdings_df.empty:
            return pd.DataFrame(columns=[security_id_col, "manager_breadth", "manager_hhi", "manager_agreement", "signed_manager_agreement", "z_manager_breadth"])
        securities = pd.Index(holdings_df[security_id_col].unique(), name=security_id_col)
        breadth = self.compute_cluster_breadth(holdings_df, security_id_col, fund_id_col, holding_col).reindex(securities, fill_value=0)
        hhi = self.compute_manager_hhi(holdings_df, security_id_col, fund_id_col, holding_col).reindex(securities, fill_value=1.0)
        agreement, signed = self.compute_directional_agreement(holdings_df, security_id_col, fund_id_col, date_col, holding_col)
        result = pd.DataFrame(index=securities)
        result["manager_breadth"] = breadth
        result["manager_hhi"] = hhi
        result["manager_agreement"] = agreement
        result["signed_manager_agreement"] = signed
        mean = result["manager_breadth"].mean()
        std = result["manager_breadth"].std()
        result["z_manager_breadth"] = ((result["manager_breadth"] - mean) / (std if std > 0 else 1.0)).fillna(0.0)
        return result.reset_index()


__all__ = ["ManagerMetadata", "SecurityManagerMetrics", "ManagerGraphEngine"]
