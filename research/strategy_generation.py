"""
Stage 1 - strategy generation.

Path: research/strategy_generation.py

Turns the fund universe and strategy ontology into ranked, implementable
strategy candidates. This is the step that decides *what is worth looking at*
before any disclosure is pulled.

A candidate is only interesting if independent managers can express it: a theme
covered by one manager cluster is a single opinion, not an adoption signal.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence

ONTOLOGY_PATH = Path("config/strategy_ontology.json")
UNIVERSE_PATH = Path("config/fund_universe.json")

SIGNAL_CLASSIFICATIONS = {"active_thematic", "rules_based_thematic", "specialist_adjacency"}
IMPLEMENTATION_CLASSIFICATIONS = {"implementation_etf"}
CONTROL_CLASSIFICATIONS = {"broad_passive_control"}

MIN_INDEPENDENT_CLUSTERS = 2


@dataclass(frozen=True)
class FundRef:
    fund_id: str
    ticker: str
    name: str
    classification: str
    manager_cluster_id: str
    primary_theme: str
    eligible_functions: tuple[str, ...]
    mandate_relevance: float
    activeness: float
    manager_independence: float
    liquidity: float

    @classmethod
    def from_config(cls, raw: Dict[str, Any]) -> "FundRef":
        quality = raw.get("fund_quality_meta", {})
        return cls(
            fund_id=raw["fund_id"],
            ticker=raw["ticker"],
            name=raw.get("name", raw["ticker"]),
            classification=raw.get("classification", "unknown"),
            manager_cluster_id=raw.get("manager_cluster_id", f"ADV_{raw['fund_id']}"),
            primary_theme=raw.get("primary_theme", "unclassified"),
            eligible_functions=tuple(raw.get("eligible_functions", [])),
            mandate_relevance=float(quality.get("mandate_relevance", 0.0)),
            activeness=float(quality.get("activeness", 0.0)),
            manager_independence=float(quality.get("manager_independence", 0.0)),
            liquidity=float(quality.get("liquidity", 0.0)),
        )


@dataclass(frozen=True)
class StrategyCandidate:
    strategy_id: str
    theme: str
    function: str
    thesis_seed: str
    signal_funds: List[FundRef]
    implementation_funds: List[FundRef]
    control_funds: List[FundRef]
    independent_clusters: List[str]
    mean_mandate_relevance: float
    mean_activeness: float
    mean_independence: float
    observability_score: float
    rejection_reasons: List[str] = field(default_factory=list)

    @property
    def viable(self) -> bool:
        return not self.rejection_reasons

    @property
    def cluster_count(self) -> int:
        return len(self.independent_clusters)

    @property
    def signal_tickers(self) -> List[str]:
        return [f.ticker for f in self.signal_funds]

    @property
    def implementation_tickers(self) -> List[str]:
        return [f.ticker for f in self.implementation_funds]

    def summary(self) -> str:
        return (
            f"{self.cluster_count} independent manager clusters across "
            f"{len(self.signal_funds)} disclosing funds; "
            f"observability {self.observability_score:.2f}"
        )


def _humanize(token: str) -> str:
    return token.replace("_", " ")


class StrategyGenerator:
    """Ranks theme/function pairs by how observably institutions can express them."""

    def __init__(
        self,
        *,
        ontology_path: Path | str = ONTOLOGY_PATH,
        universe_path: Path | str = UNIVERSE_PATH,
    ):
        self.ontology: Dict[str, Any] = json.loads(Path(ontology_path).read_text(encoding="utf-8"))
        universe_raw = json.loads(Path(universe_path).read_text(encoding="utf-8"))
        funds_raw: Sequence[Dict[str, Any]] = (
            universe_raw["funds"] if isinstance(universe_raw, dict) else universe_raw
        )
        self.funds: List[FundRef] = [FundRef.from_config(row) for row in funds_raw]
        self._by_fund_id = {f.fund_id: f for f in self.funds}

    # -- universe views ----------------------------------------------------

    @property
    def mandate(self) -> str:
        return self.ontology.get("strategy_identity", {}).get("mandate", "")

    @property
    def factor_weights(self) -> Dict[str, float]:
        return dict(self.ontology.get("factor_weighting_matrix", {}).get("weights", {}))

    def themes(self) -> List[str]:
        return sorted({f.primary_theme for f in self.funds})

    def functions(self, theme: Optional[str] = None) -> List[str]:
        pool = [f for f in self.funds if theme is None or f.primary_theme == theme]
        return sorted({fn for f in pool for fn in f.eligible_functions})

    def fund(self, fund_id: str) -> FundRef:
        return self._by_fund_id[fund_id]

    def cluster_map(self) -> Dict[str, str]:
        return {f.fund_id: f.manager_cluster_id for f in self.funds}

    def theme_map(self) -> Dict[str, str]:
        return {f.fund_id: f.primary_theme for f in self.funds}

    # -- generation --------------------------------------------------------

    def search(self, query: str, *, limit: int = 8, include_unviable: bool = False) -> List[StrategyCandidate]:
        """Free-text entry point: 'nuclear' -> smr_technology, fuel_enrichment, ..."""
        from research.lexicon import expand

        terms = [t for t in re.split(r"[^a-z0-9]+", query.lower()) if len(t) > 2]
        concept = expand(query)
        if not terms and not concept.matched:
            return self.generate(limit=limit, include_unviable=include_unviable)

        scored: List[tuple[float, str, str]] = []
        for theme in self.themes():
            for function in self.functions(theme):
                haystack = f"{theme} {function}".lower()
                hits = sum(1 for term in terms if term in haystack)
                # Concept hits outrank literal ones: vocabulary rarely matches token names.
                if function in concept.functions:
                    hits += 3
                if theme in concept.themes:
                    hits += 1
                if hits:
                    scored.append((hits, theme, function))

        scored.sort(key=lambda row: -row[0])
        candidates = [self.build(theme, function) for _, theme, function in scored[: limit * 3]]
        if not include_unviable:
            candidates = [c for c in candidates if c.viable]
        return self._rank(candidates)[:limit]

    def generate(
        self,
        *,
        theme: Optional[str] = None,
        function: Optional[str] = None,
        limit: int = 10,
        include_unviable: bool = False,
    ) -> List[StrategyCandidate]:
        pairs = [
            (t, fn)
            for t in ([theme] if theme else self.themes())
            for fn in ([function] if function else self.functions(t))
        ]
        candidates = [self.build(t, fn) for t, fn in pairs]
        if not include_unviable:
            candidates = [c for c in candidates if c.viable]
        return self._rank(candidates)[:limit]

    def build(self, theme: str, function: str) -> StrategyCandidate:
        matching = [
            f for f in self.funds if f.primary_theme == theme and function in f.eligible_functions
        ]
        signal = [f for f in matching if f.classification in SIGNAL_CLASSIFICATIONS]
        dedicated = [
            f
            for f in self.funds
            if f.classification in IMPLEMENTATION_CLASSIFICATIONS
            and (f.primary_theme == theme or function in f.eligible_functions)
        ]
        # A dedicated implementation vehicle is preferred, but the disclosing
        # funds are themselves tradeable ETFs and are a valid fallback.
        implementation = sorted(dedicated, key=lambda f: -f.liquidity) + sorted(
            (f for f in signal if f not in dedicated), key=lambda f: -f.liquidity
        )
        control = [f for f in self.funds if f.classification in CONTROL_CLASSIFICATIONS]
        clusters = sorted({f.manager_cluster_id for f in signal})

        relevance = mean([f.mandate_relevance for f in signal]) if signal else 0.0
        activeness = mean([f.activeness for f in signal]) if signal else 0.0
        independence = mean([f.manager_independence for f in signal]) if signal else 0.0

        rejections: List[str] = []
        if not signal:
            rejections.append("NO_DISCLOSING_SIGNAL_FUNDS")
        if len(clusters) < MIN_INDEPENDENT_CLUSTERS:
            rejections.append(
                f"INSUFFICIENT_MANAGER_BREADTH: {len(clusters)} cluster(s), need {MIN_INDEPENDENT_CLUSTERS}"
            )
        if not implementation:
            rejections.append("NO_IMPLEMENTATION_VEHICLE")

        return StrategyCandidate(
            strategy_id=f"{theme}:{function}",
            theme=theme,
            function=function,
            thesis_seed=(
                f"Independent managers are expressing {_humanize(function)} within "
                f"{_humanize(theme)} ahead of consensus."
            ),
            signal_funds=sorted(signal, key=lambda f: -f.activeness),
            implementation_funds=implementation[:5],
            control_funds=control[:3],
            independent_clusters=clusters,
            mean_mandate_relevance=relevance,
            mean_activeness=activeness,
            mean_independence=independence,
            observability_score=self._observability(clusters, relevance, activeness, independence),
            rejection_reasons=rejections,
        )

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _observability(
        clusters: Sequence[str], relevance: float, activeness: float, independence: float
    ) -> float:
        if not clusters:
            return 0.0
        # Breadth saturates: the fourth independent cluster adds less than the second.
        breadth = min(1.0, len(clusters) / 4.0)
        return round(breadth * (0.4 * relevance + 0.3 * activeness + 0.3 * independence), 4)

    @staticmethod
    def _rank(candidates: Iterable[StrategyCandidate]) -> List[StrategyCandidate]:
        return sorted(
            candidates,
            key=lambda c: (c.viable, c.observability_score, c.cluster_count),
            reverse=True,
        )



__all__ = [
    "FundRef",
    "MIN_INDEPENDENT_CLUSTERS",
    "StrategyCandidate",
    "StrategyGenerator",
]
