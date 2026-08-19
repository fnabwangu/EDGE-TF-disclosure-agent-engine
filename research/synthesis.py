"""
Stage 2 - ETF disclosure synthesis.

Path: research/synthesis.py

Takes normalized holdings panels and drives the existing deterministic engine:

    holdings panel
      -> AnomalyDetector          (active quantity deviation, flow z-scores)
      -> ManagerGraphEngine       (independent cluster breadth, HHI, agreement)
      -> InstitutionalGraphEngine (thematic diffusion, centrality)
      -> InstitutionalAdoptionVelocity
      -> ConvictionEngine

Nothing here invents a number. Every field on a SecuritySynthesis traces to one
of those engines, and `evidence()` emits the citations for the UI.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

import pandas as pd

from analytics.anomaly_detector import AnomalyDetector
from analytics.conviction_engine import ConvictionEngine
from analytics.institutional_adoption_velocity import (
    IAVInputs,
    IAVResult,
    InstitutionalAdoptionVelocity,
)
from analytics.institutional_graph_engine import InstitutionalGraphEngine
from analytics.manager_independence import compute_manager_graph_pipeline
from core.schemas import ConvictionInputs

MIN_OBSERVATION_DATES = 2


def to_unit(value: float) -> float:
    """Map a [-1, 1] score onto [0, 1] for the conviction engine."""
    return max(0.0, min(1.0, (value + 1.0) / 2.0))


def squash(z: float, *, scale: float = 2.0) -> float:
    """Compress an unbounded z-score into [-1, 1] without clipping information away."""
    if z is None or (isinstance(z, float) and math.isnan(z)):
        return 0.0
    return math.tanh(float(z) / scale)


def clip1(value: float) -> float:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0.0
    return max(-1.0, min(1.0, float(value)))


@dataclass(frozen=True)
class EvidenceRow:
    claim: str
    stance: str
    metric: str
    value: float
    source: str


@dataclass
class SecuritySynthesis:
    security_id: str
    raw_identifier: str
    holding_funds: List[str]
    u_normalized: float
    aqd: float
    aqd_pct: float
    z_score: float
    is_anomaly: bool
    manager_breadth: int
    manager_hhi: float
    manager_agreement: float
    persistence: float
    diffusion_score: float
    z_diffusion: float
    adopted_themes: List[str]
    centrality: float
    strategic_relevance: float
    ambiguity: float
    iav: IAVResult
    conviction: Any

    @property
    def state(self) -> str:
        tier = getattr(self.conviction, "quality_tier", "weak")
        return {
            "weak": "WEAK",
            "emerging": "EMERGING",
            "confirmed": "CONFIRMED_ADOPTION",
            "strong": "STRONG_ADOPTION",
        }.get(tier, tier.upper())

    def evidence(self) -> List[EvidenceRow]:
        rows = [
            EvidenceRow(
                claim=(
                    f"{self.manager_breadth} independent manager cluster(s) hold {self.raw_identifier}"
                ),
                stance="SUPPORTS" if self.manager_breadth >= 2 else "CONTRADICTS",
                metric="manager_breadth",
                value=float(self.manager_breadth),
                source="ManagerGraphEngine",
            ),
            EvidenceRow(
                claim=(
                    f"Active quantity deviation of {self.aqd_pct:+.2%} versus the "
                    f"cross-fund expected position"
                ),
                stance="SUPPORTS" if self.aqd_pct > 0 else "CONTRADICTS",
                metric="aqd_pct",
                value=self.aqd_pct,
                source="AnomalyDetector",
            ),
            EvidenceRow(
                claim=f"Flow z-score of {self.z_score:+.2f} against its own history",
                stance="SUPPORTS" if self.z_score > 0 else "CONTRADICTS",
                metric="flow_zscore",
                value=self.z_score,
                source="AnomalyDetector",
            ),
            EvidenceRow(
                claim=f"Adopted across {len(self.adopted_themes)} theme(s): {', '.join(self.adopted_themes) or 'none'}",
                stance="SUPPORTS" if len(self.adopted_themes) > 1 else "CONTRADICTS",
                metric="diffusion",
                value=self.diffusion_score,
                source="InstitutionalGraphEngine",
            ),
        ]
        if self.manager_hhi > 0.5:
            rows.append(
                EvidenceRow(
                    claim=(
                        f"Holdings are concentrated in few managers (HHI {self.manager_hhi:.2f}); "
                        "breadth may overstate independence"
                    ),
                    stance="CONTRADICTS",
                    metric="manager_hhi",
                    value=self.manager_hhi,
                    source="ManagerGraphEngine",
                )
            )
        return rows


@dataclass
class ThemeSynthesis:
    strategy_id: str
    theme: str
    function: str
    fund_count: int
    cluster_count: int
    observation_dates: int
    securities: List[SecuritySynthesis] = field(default_factory=list)
    anomaly_summary: Dict[str, Any] = field(default_factory=dict)
    blocking_reasons: List[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return not self.blocking_reasons and bool(self.securities)

    def ranked(self) -> List[SecuritySynthesis]:
        return sorted(self.securities, key=lambda s: -s.iav.composite_score)

    def leader(self) -> Optional[SecuritySynthesis]:
        ranked = self.ranked()
        return ranked[0] if ranked else None


def build_panel(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Normalize `ETFDisclosureIngestor.holdings_panel` output for the analytics stack."""
    frame = pd.DataFrame(list(rows))
    if frame.empty:
        return frame
    frame["canonical_id"] = frame["security_id"]
    frame["effective_date"] = pd.to_datetime(frame["portfolio_effective_date"])
    if "portfolio_weight" not in frame.columns:
        frame["portfolio_weight"] = frame["u_normalized"]
    frame["portfolio_weight"] = frame["portfolio_weight"].fillna(frame["u_normalized"])
    return frame


class DisclosureSynthesizer:
    def __init__(
        self,
        *,
        cluster_map: Mapping[str, str],
        theme_map: Mapping[str, str],
        relevance_map: Optional[Mapping[str, float]] = None,
        independence_map: Optional[Mapping[str, float]] = None,
        iav: Optional[InstitutionalAdoptionVelocity] = None,
        conviction: Optional[ConvictionEngine] = None,
        anomaly_lookback: int = 5,
    ):
        self.cluster_map = dict(cluster_map)
        self.theme_map = dict(theme_map)
        self.relevance_map = dict(relevance_map or {})
        self.independence_map = dict(independence_map or {})
        self.iav = iav or InstitutionalAdoptionVelocity()
        self.conviction = conviction or ConvictionEngine()
        self.anomaly_lookback = anomaly_lookback

    def synthesize(self, panel: pd.DataFrame, *, strategy_id: str, theme: str, function: str) -> ThemeSynthesis:
        result = ThemeSynthesis(
            strategy_id=strategy_id,
            theme=theme,
            function=function,
            fund_count=int(panel["fund_id"].nunique()) if not panel.empty else 0,
            cluster_count=len({self.cluster_map.get(f, f) for f in panel["fund_id"].unique()})
            if not panel.empty
            else 0,
            observation_dates=int(panel["effective_date"].nunique()) if not panel.empty else 0,
        )
        if panel.empty:
            result.blocking_reasons.append("NO_DISCLOSURES_AVAILABLE")
            return result
        if result.observation_dates < MIN_OBSERVATION_DATES:
            result.blocking_reasons.append(
                f"INSUFFICIENT_HISTORY: {result.observation_dates} disclosure date(s), "
                f"need {MIN_OBSERVATION_DATES}"
            )
            return result

        enriched, summary = AnomalyDetector(min_history_periods=self.anomaly_lookback).detect_anomalies(
            panel,
            fund_id_col="fund_id",
            security_id_col="security_id",
            date_col="effective_date",
            shares_col="shares_held",
            etf_shares_col="etf_shares_outstanding",
            lookback=self.anomaly_lookback,
        )
        result.anomaly_summary = summary

        manager_panel = compute_manager_graph_pipeline(panel, fund_to_cluster_map=self.cluster_map)
        diffusion_panel = InstitutionalGraphEngine(fund_theme_map=self.theme_map).compute_diffusion_panel(
            panel, security_id_col="canonical_id", fund_id_col="fund_id", weight_col="portfolio_weight"
        )
        persistence = self._persistence(panel)

        managers = manager_panel.set_index("canonical_id") if not manager_panel.empty else pd.DataFrame()
        diffusion = diffusion_panel.set_index("canonical_id") if not diffusion_panel.empty else pd.DataFrame()

        latest_date = enriched["effective_date"].max()
        for security_id, group in enriched.groupby("security_id"):
            latest = group[group["effective_date"] == latest_date]
            if latest.empty:
                latest = group.tail(1)
            result.securities.append(
                self._synthesize_security(
                    security_id=str(security_id),
                    latest=latest,
                    managers=managers,
                    diffusion=diffusion,
                    persistence=persistence.get(str(security_id), 0.0),
                )
            )
        return result

    # -- internals ---------------------------------------------------------

    def _synthesize_security(
        self,
        *,
        security_id: str,
        latest: pd.DataFrame,
        managers: pd.DataFrame,
        diffusion: pd.DataFrame,
        persistence: float,
    ) -> SecuritySynthesis:
        funds = sorted(latest["fund_id"].unique().tolist())
        manager_row = managers.loc[security_id] if security_id in managers.index else None
        diffusion_row = diffusion.loc[security_id] if security_id in diffusion.index else None

        breadth = int(manager_row["manager_breadth"]) if manager_row is not None else len(
            {self.cluster_map.get(f, f) for f in funds}
        )
        hhi = float(manager_row["manager_hhi"]) if manager_row is not None else 1.0
        agreement = float(manager_row["manager_agreement"]) if manager_row is not None else 0.0
        z_breadth = float(manager_row["z_manager_breadth"]) if manager_row is not None else 0.0

        diffusion_score = float(diffusion_row["weighted_diffusion_score"]) if diffusion_row is not None else 0.0
        z_diffusion = float(diffusion_row["z_diffusion"]) if diffusion_row is not None else 0.0
        themes = list(diffusion_row["adopted_themes"]) if diffusion_row is not None else []
        centrality = float(diffusion_row["centrality_score"]) if diffusion_row is not None else 0.0

        aqd_pct = float(latest["aqd_pct"].mean()) if "aqd_pct" in latest else 0.0
        aqd = float(latest["aqd"].mean()) if "aqd" in latest else 0.0
        z_score = float(latest["z_score"].mean()) if "z_score" in latest else 0.0
        u_normalized = float(latest["u_normalized"].sum())
        is_anomaly = bool(latest["is_anomaly"].any()) if "is_anomaly" in latest else False

        relevance = self._mean_for(funds, self.relevance_map, default=0.5)
        independence = self._mean_for(funds, self.independence_map, default=0.5)
        ambiguity = max(0.0, min(1.0, 1.0 - independence))

        iav_inputs = IAVInputs(
            normalized_active_allocation=squash(aqd_pct * 10),
            independent_manager_breadth=clip1(squash(z_breadth) if z_breadth else (breadth - 2) / 2),
            persistence=clip1(persistence),
            diffusion=squash(z_diffusion),
            strategic_relevance=clip1(relevance * 2 - 1),
            anomaly_quality=squash(z_score),
            ambiguity=ambiguity,
            manager_dependence_penalty=max(0.0, min(1.0, hhi)),
        )
        iav_result = self.iav.compute(iav_inputs)

        conviction_result = self.conviction.evaluate(
            ConvictionInputs(
                event_expected_value=iav_result.composite_score,
                event_probability_quality=to_unit(clip1(agreement)),
                iav=to_unit(iav_result.composite_score),
                aqd_quality=to_unit(squash(aqd_pct * 10)),
                anomaly_score=to_unit(squash(z_score)),
                manager_breadth_score=to_unit(clip1((breadth - 2) / 2)),
                persistence_score=to_unit(clip1(persistence)),
                diffusion_score=to_unit(squash(z_diffusion)),
                evidence_quality=relevance,
                ambiguity_penalty=ambiguity,
            )
        )

        return SecuritySynthesis(
            security_id=security_id,
            raw_identifier=str(latest["raw_identifier"].iloc[0]) if "raw_identifier" in latest else security_id,
            holding_funds=funds,
            u_normalized=u_normalized,
            aqd=aqd,
            aqd_pct=aqd_pct,
            z_score=z_score,
            is_anomaly=is_anomaly,
            manager_breadth=breadth,
            manager_hhi=hhi,
            manager_agreement=agreement,
            persistence=persistence,
            diffusion_score=diffusion_score,
            z_diffusion=z_diffusion,
            adopted_themes=themes,
            centrality=centrality,
            strategic_relevance=relevance,
            ambiguity=ambiguity,
            iav=iav_result,
            conviction=conviction_result,
        )

    @staticmethod
    def _persistence(panel: pd.DataFrame) -> Dict[str, float]:
        """Share of period-over-period moves that keep the same sign, mapped to [-1, 1]."""
        out: Dict[str, float] = {}
        ordered = panel.sort_values("effective_date")
        for security_id, group in ordered.groupby("security_id"):
            totals = group.groupby("effective_date")["u_normalized"].sum()
            deltas = totals.diff().dropna()
            if deltas.empty:
                out[str(security_id)] = 0.0
                continue
            positive = float((deltas > 0).sum())
            negative = float((deltas < 0).sum())
            moves = positive + negative
            out[str(security_id)] = 0.0 if moves == 0 else (positive - negative) / moves
        return out

    @staticmethod
    def _mean_for(funds: Sequence[str], lookup: Mapping[str, float], *, default: float) -> float:
        values = [lookup[f] for f in funds if f in lookup]
        return sum(values) / len(values) if values else default


__all__ = [
    "DisclosureSynthesizer",
    "EvidenceRow",
    "SecuritySynthesis",
    "ThemeSynthesis",
    "build_panel",
    "clip1",
    "squash",
    "to_unit",
]
