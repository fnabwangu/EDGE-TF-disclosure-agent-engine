"""Provider-specific ETF disclosure ingestion and canonicalization.

The adapter accepts provider payloads with explicit source and availability
metadata. It does not infer missing denominators or timestamps.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Protocol

from core.schemas import ETFDisclosureBundle


class ETFDisclosureProvider(Protocol):
    """Provider boundary for daily ETF disclosure feeds."""

    name: str

    def fetch(self, etf_ticker: str, as_of: datetime) -> Mapping[str, Any]:
        """Return one raw provider payload for the requested ETF/date."""
        ...


class StaticETFDisclosureProvider:
    """Deterministic fixture/provider adapter for JSON payloads."""

    name = "STATIC_JSON"

    def __init__(self, payloads: Mapping[str, Mapping[str, Any]]):
        self.payloads = payloads

    def fetch(self, etf_ticker: str, as_of: datetime) -> Mapping[str, Any]:
        try:
            return self.payloads[etf_ticker]
        except KeyError as exc:
            raise KeyError(f"No ETF disclosure payload for {etf_ticker}") from exc


class ETFDisclosureIngestor:
    """Fetch, validate, persist, and flatten provider ETF observations."""

    def __init__(self, provider: ETFDisclosureProvider, raw_dir: str | Path = "data/raw/etf_disclosures", canonical_dir: str | Path = "data/canonical/etf_disclosures"):
        self.provider = provider
        self.raw_dir = Path(raw_dir)
        self.canonical_dir = Path(canonical_dir)

    def ingest(self, etf_ticker: str, as_of: datetime) -> ETFDisclosureBundle:
        payload = dict(self.provider.fetch(etf_ticker, as_of))
        payload.setdefault("source", self.provider.name)
        if not payload.get("shares_outstanding"):
            raise ValueError(
                f"ETF_DISCLOSURE_BLOCKED: shares outstanding missing for {etf_ticker}"
            )
        bundle = ETFDisclosureBundle.model_validate(self._apply_source_defaults(payload))
        self._persist(etf_ticker, as_of, payload, bundle)
        return bundle

    @staticmethod
    def _apply_source_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Copy bundle-level source metadata into records without inventing times."""
        source = payload.get("source", "UNKNOWN")
        source_uri = payload.get("source_uri")
        normalized = dict(payload)
        for collection in (
            "holdings", "shares_outstanding", "baskets", "manager_relationships",
            "rebalance_events", "corporate_actions",
        ):
            records = []
            for record in payload.get(collection, []):
                item = dict(record)
                item.setdefault("source", source)
                if source_uri is not None:
                    item.setdefault("source_uri", source_uri)
                records.append(item)
            normalized[collection] = records
        return normalized

    def _persist(self, etf_ticker: str, as_of: datetime, raw: Mapping[str, Any], bundle: ETFDisclosureBundle) -> None:
        stamp = as_of.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        raw_text = json.dumps(raw, sort_keys=True, default=str)
        digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.canonical_dir.mkdir(parents=True, exist_ok=True)
        (self.raw_dir / f"{etf_ticker}_{stamp}_{digest[:12]}.json").write_text(raw_text, encoding="utf-8")
        (self.canonical_dir / f"{etf_ticker}_{stamp}.json").write_text(bundle.model_dump_json(indent=2), encoding="utf-8")

    @staticmethod
    def holdings_panel(bundle: ETFDisclosureBundle):
        """Return normalized holdings rows with an explicit q/N denominator."""
        shares_by_fund_date = {
            (item.fund_id, item.effective_date): item.shares_outstanding
            for item in bundle.shares_outstanding
        }
        rows = []
        for holding in bundle.holdings:
            denominator = shares_by_fund_date.get((holding.fund_id, holding.portfolio_effective_date))
            if denominator is None:
                raise ValueError(
                    f"ETF_DISCLOSURE_BLOCKED: missing shares outstanding for {holding.fund_id} on {holding.portfolio_effective_date}"
                )
            row = holding.model_dump()
            row["etf_shares_outstanding"] = denominator
            row["u_normalized"] = holding.shares_held / denominator
            rows.append(row)
        return rows


__all__ = ["ETFDisclosureProvider", "StaticETFDisclosureProvider", "ETFDisclosureIngestor"]
