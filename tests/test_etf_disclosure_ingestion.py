from datetime import datetime, timezone

import pytest

from core.etf_disclosures import ETFDisclosureIngestor, StaticETFDisclosureProvider


AS_OF = datetime(2026, 8, 18, 14, 0, tzinfo=timezone.utc)


def fixture_payload():
    return {
        "source": "PROVIDER_FIXTURE",
        "source_uri": "fixture://etf/EDGE",
        "holdings": [{
            "etf_ticker": "EDGE",
            "fund_id": "EDGE-FUND",
            "security_id": "SEC-ABC",
            "raw_identifier": "ABC",
            "shares_held": 2500,
            "portfolio_weight": 0.10,
            "portfolio_effective_date": "2026-08-17",
            "information_available_time": "2026-08-18T13:00:00Z",
        }],
        "shares_outstanding": [{
            "etf_ticker": "EDGE",
            "fund_id": "EDGE-FUND",
            "shares_outstanding": 10000,
            "effective_date": "2026-08-17",
            "information_available_time": "2026-08-18T12:00:00Z",
        }],
        "baskets": [{
            "etf_ticker": "EDGE",
            "fund_id": "EDGE-FUND",
            "side": "CREATION",
            "creation_unit_size": 100,
            "basket_date": "2026-08-18",
            "information_available_time": "2026-08-18T13:30:00Z",
            "positions": [{"security_id": "SEC-ABC", "raw_identifier": "ABC", "shares": 2500}],
        }],
        "manager_relationships": [{
            "fund_id": "EDGE-FUND",
            "manager_id": "MANAGER-A",
            "adviser": "Adviser A",
            "effective_date": "2026-01-01",
            "information_available_time": "2026-01-01T00:00:00Z",
        }],
        "rebalance_events": [{
            "etf_ticker": "EDGE",
            "fund_id": "EDGE-FUND",
            "event_type": "REBALANCE",
            "effective_date": "2026-08-18",
            "information_available_time": "2026-08-10T00:00:00Z",
            "details": {"reason": "quarterly"},
        }],
        "corporate_actions": [],
    }


def test_provider_ingestion_preserves_required_etf_observations(tmp_path):
    provider = StaticETFDisclosureProvider({"EDGE": fixture_payload()})
    ingestor = ETFDisclosureIngestor(provider, tmp_path / "raw", tmp_path / "canonical")

    bundle = ingestor.ingest("EDGE", AS_OF)
    panel = ingestor.holdings_panel(bundle)

    assert panel[0]["etf_shares_outstanding"] == 10000
    assert panel[0]["u_normalized"] == 0.25
    assert bundle.baskets[0].creation_unit_size == 100
    assert bundle.manager_relationships[0].manager_id == "MANAGER-A"
    assert bundle.holdings[0].information_available_time < AS_OF
    assert list((tmp_path / "raw").glob("*.json"))
    assert list((tmp_path / "canonical").glob("*.json"))


def test_provider_ingestion_blocks_missing_shares_denominator(tmp_path):
    payload = fixture_payload()
    payload["shares_outstanding"] = []
    ingestor = ETFDisclosureIngestor(
        StaticETFDisclosureProvider({"EDGE": payload}),
        tmp_path / "raw",
        tmp_path / "canonical",
    )

    with pytest.raises(ValueError, match="ETF_DISCLOSURE_BLOCKED"):
        ingestor.ingest("EDGE", AS_OF)
