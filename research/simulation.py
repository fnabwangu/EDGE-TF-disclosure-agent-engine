"""
Simulated disclosure feed - DEVELOPMENT ONLY.

Path: research/simulation.py

Generates synthetic ETF disclosure payloads so the funnel can be exercised
without a live provider. The payloads are fed through the real
`ETFDisclosureIngestor`, so point-in-time availability and q/N normalization
rules apply exactly as they would in production.

Nothing in this module may be imported by a production code path.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence

from core.etf_disclosures import ETFDisclosureIngestor, StaticETFDisclosureProvider
from research.strategy_generation import StrategyCandidate

Regime = Literal["BROAD_ADOPTION", "NARROW_ADOPTION", "DISTRIBUTION", "NOISE"]

BASE_SHARES_OUTSTANDING = 10_000_000.0


@dataclass(frozen=True)
class SimulatedSecurity:
    security_id: str
    raw_identifier: str
    base_weight: float


def default_securities(candidate: StrategyCandidate, count: int = 4) -> List[SimulatedSecurity]:
    stem = candidate.function.upper().replace("_", "")[:4] or "SEC"
    return [
        SimulatedSecurity(security_id=f"SEC-{stem}-{i + 1}", raw_identifier=f"{stem}{i + 1}", base_weight=w)
        for i, w in enumerate([0.09, 0.06, 0.04, 0.02][:count])
    ]


def observation_dates(as_of: date, periods: int = 6, step_days: int = 7) -> List[date]:
    return [as_of - timedelta(days=step_days * (periods - 1 - i)) for i in range(periods)]


def _drift_for(regime: Regime, cluster_index: int, period: int, periods: int) -> float:
    progress = period / max(1, periods - 1)
    if regime == "BROAD_ADOPTION":
        return 1.0 + 0.55 * progress
    if regime == "NARROW_ADOPTION":
        return 1.0 + (0.9 * progress if cluster_index == 0 else 0.02 * progress)
    if regime == "DISTRIBUTION":
        return max(0.15, 1.0 - 0.6 * progress)
    return 1.0


def simulate_payloads(
    candidate: StrategyCandidate,
    *,
    as_of: date,
    regime: Regime = "BROAD_ADOPTION",
    securities: Optional[Sequence[SimulatedSecurity]] = None,
    periods: int = 6,
    seed: int = 7,
) -> Dict[date, Dict[str, Dict[str, Any]]]:
    """Return payloads keyed by observation date, then by ETF ticker."""
    rng = random.Random(seed)
    securities = list(securities or default_securities(candidate))
    dates = observation_dates(as_of, periods=periods)
    clusters = candidate.independent_clusters

    by_date: Dict[date, Dict[str, Dict[str, Any]]] = {}
    for period, effective in enumerate(dates):
        available = datetime.combine(effective, time(21, 0), tzinfo=timezone.utc)
        payloads: Dict[str, Dict[str, Any]] = {}

        for fund in candidate.signal_funds:
            cluster_index = clusters.index(fund.manager_cluster_id) if fund.manager_cluster_id in clusters else 0
            drift = _drift_for(regime, cluster_index, period, periods)
            holdings = []
            positions = []
            for security in securities:
                noise = 1.0 + rng.uniform(-0.04, 0.04)
                weight = security.base_weight * fund.activeness * drift * noise
                shares = round(BASE_SHARES_OUTSTANDING * weight)
                if shares <= 0:
                    continue
                holdings.append(
                    {
                        "etf_ticker": fund.ticker,
                        "fund_id": fund.fund_id,
                        "security_id": security.security_id,
                        "raw_identifier": security.raw_identifier,
                        "shares_held": float(shares),
                        "portfolio_weight": round(weight, 6),
                        "portfolio_effective_date": effective.isoformat(),
                        "information_available_time": available.isoformat().replace("+00:00", "Z"),
                    }
                )
                positions.append(
                    {
                        "security_id": security.security_id,
                        "raw_identifier": security.raw_identifier,
                        "shares": float(shares) / 100.0,
                    }
                )
            if not holdings:
                continue

            payloads[fund.ticker] = {
                "source": "SIMULATED_PROVIDER",
                "source_uri": f"simulated://etf/{fund.ticker}",
                "holdings": holdings,
                "shares_outstanding": [
                    {
                        "etf_ticker": fund.ticker,
                        "fund_id": fund.fund_id,
                        "shares_outstanding": BASE_SHARES_OUTSTANDING,
                        "effective_date": effective.isoformat(),
                        "information_available_time": available.isoformat().replace("+00:00", "Z"),
                    }
                ],
                "baskets": [
                    {
                        "etf_ticker": fund.ticker,
                        "fund_id": fund.fund_id,
                        "side": "CREATION" if regime != "DISTRIBUTION" else "REDEMPTION",
                        "creation_unit_size": 100,
                        "basket_date": effective.isoformat(),
                        "information_available_time": available.isoformat().replace("+00:00", "Z"),
                        "positions": positions,
                    }
                ],
                "manager_relationships": [
                    {
                        "fund_id": fund.fund_id,
                        "manager_id": fund.manager_cluster_id,
                        "adviser": fund.manager_cluster_id,
                        "effective_date": "2026-01-01",
                        "information_available_time": "2026-01-01T00:00:00Z",
                    }
                ],
                "rebalance_events": [],
                "corporate_actions": [],
            }
        by_date[effective] = payloads
    return by_date


def ingest_candidate(
    candidate: StrategyCandidate,
    *,
    as_of: date,
    regime: Regime = "BROAD_ADOPTION",
    storage_dir: Path | str = "data/simulated",
    periods: int = 6,
    seed: int = 7,
) -> List[Dict[str, Any]]:
    """Drive simulated payloads through the real ingestor and return panel rows."""
    storage = Path(storage_dir)
    by_date = simulate_payloads(candidate, as_of=as_of, regime=regime, periods=periods, seed=seed)

    rows: List[Dict[str, Any]] = []
    for effective, payloads in by_date.items():
        if not payloads:
            continue
        # Each snapshot is ingested at its own decision time, so staleness rules bind.
        decision_time = datetime.combine(effective, time(23, 0), tzinfo=timezone.utc)
        ingestor = ETFDisclosureIngestor(
            StaticETFDisclosureProvider(payloads),
            raw_dir=storage / "raw",
            canonical_dir=storage / "canonical",
        )
        for ticker in payloads:
            bundle = ingestor.ingest(ticker, decision_time)
            rows.extend(ingestor.holdings_panel(bundle))
    return rows


__all__ = [
    "BASE_SHARES_OUTSTANDING",
    "Regime",
    "SimulatedSecurity",
    "default_securities",
    "ingest_candidate",
    "observation_dates",
    "simulate_payloads",
]
