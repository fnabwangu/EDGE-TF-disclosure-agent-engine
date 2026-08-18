from datetime import date, datetime, timezone

import pandas as pd
import pytest

from normalization.normalizer import DisclosureNormalizer
from risk.kill_switch import EmergencyKillSwitchEngine


def base_frame():
    return pd.DataFrame({
        "fund_id": ["FUND-A", "FUND-A"],
        "canonical_id": ["SEC-A", "SEC-A"],
        "shares_held": [100.0, 120.0],
        "etf_shares_outstanding": [1000.0, 1100.0],
        "effective_date": [date(2026, 8, 17), date(2026, 8, 18)],
    })


def test_first_observation_has_no_aqd_evidence():
    result = DisclosureNormalizer().compute_active_quantity_deviation(base_frame())
    first = result.iloc[0]
    assert pd.isna(first["aqd"])
    assert bool(first["aqd_valid"]) is False
    assert first["aqd_reason"] == "NO_PRIOR_OBSERVATION"
    assert bool(result.iloc[1]["aqd_valid"]) is True


def test_point_in_time_filter_requires_availability_timestamp():
    frame = base_frame()
    with pytest.raises(ValueError, match="POINT_IN_TIME_BLOCKED"):
        DisclosureNormalizer().enforce_point_in_time(frame, datetime(2026, 8, 18, tzinfo=timezone.utc))


def test_point_in_time_filter_rejects_invalid_timestamp():
    frame = base_frame()
    frame["information_available_time"] = ["not-a-time", "2026-08-18T00:00:00Z"]
    with pytest.raises(ValueError, match="POINT_IN_TIME_BLOCKED"):
        DisclosureNormalizer().enforce_point_in_time(frame, datetime(2026, 8, 18, tzinfo=timezone.utc))


def test_production_kill_switch_requires_durable_controls():
    with pytest.raises(ValueError, match="Production kill switch requires"):
        EmergencyKillSwitchEngine(environment="production")
