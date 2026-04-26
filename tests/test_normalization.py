from __future__ import annotations

from datetime import UTC, datetime

from mtrview.config import Settings
from mtrview.normalization import normalize_summary


def test_normalizes_summary_with_full_metadata() -> None:
    payload = {
        "receiver": "A118636",
        "transmitters": {
            "15006": {
                "description": "Ambient air",
                "location": "Kids room",
                "measured_at": "2026-04-26T12:03:39Z",
                "quantity": "Temperature",
                "status": "online",
                "status_code": 1,
                "unit": "°C",
                "value": 22.3,
                "zone": "Indoor",
            }
        },
        "updated_at": "2026-04-26T12:04:03Z",
    }

    readings = normalize_summary(
        "ignored",
        payload,
        Settings(stale_after_seconds=3600),
        now=datetime(2026, 4, 26, 12, 5, tzinfo=UTC),
    )

    assert len(readings) == 1
    reading = readings[0]
    assert reading.receiver == "A118636"
    assert reading.transmitter_id == "15006"
    assert reading.display_name == "Kids room Temperature"
    assert reading.age_seconds == 81
    assert reading.stale is False
    assert reading.status_label == "ok"


def test_normalizes_partial_metadata_with_placeholders() -> None:
    readings = normalize_summary(
        "A1",
        {
            "transmitters": {
                "42": {
                    "measured_at": "2026-04-26T11:00:00Z",
                    "status": "online",
                    "status_code": 1,
                    "value": 12,
                }
            }
        },
        Settings(stale_after_seconds=3600),
        now=datetime(2026, 4, 26, 11, 1, tzinfo=UTC),
    )

    reading = readings[0]
    assert reading.display_name == "Transmitter 42"
    assert reading.location == "Unknown location"
    assert reading.zone == "Unknown zone"
    assert reading.quantity == "Unknown measurement"
    assert reading.unit == ""


def test_stale_and_missing_timestamp_are_problem_states() -> None:
    settings = Settings(stale_after_seconds=10, critical_stale_after_seconds=20)
    stale = normalize_summary(
        "A1",
        {"transmitters": {"1": {"measured_at": "2026-04-26T10:00:00Z", "status": "online"}}},
        settings,
        now=datetime(2026, 4, 26, 10, 0, 30, tzinfo=UTC),
    )[0]
    missing = normalize_summary(
        "A1",
        {"transmitters": {"2": {"status": "online"}}},
        settings,
        now=datetime(2026, 4, 26, 10, 0, 30, tzinfo=UTC),
    )[0]

    assert stale.stale is True
    assert stale.critical_stale is True
    assert stale.status_label == "critical stale"
    assert missing.stale is True
    assert missing.age_seconds is None
    assert missing.problem is True
