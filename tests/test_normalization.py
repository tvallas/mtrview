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
                "battery": 2.6,
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
        Settings(),
        now=datetime(2026, 4, 26, 12, 5, tzinfo=UTC),
    )

    assert len(readings) == 1
    reading = readings[0]
    assert reading.receiver == "A118636"
    assert reading.transmitter_id == "15006"
    assert reading.display_name == "Kids room Temperature"
    assert reading.age_seconds == 81
    assert reading.problem is False
    assert reading.status_label == "online"
    assert reading.battery == 2.6


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
        Settings(),
        now=datetime(2026, 4, 26, 11, 1, tzinfo=UTC),
    )

    reading = readings[0]
    assert reading.display_name == "Transmitter 42"
    assert reading.location == "Unknown location"
    assert reading.zone == "Unknown zone"
    assert reading.quantity == "Unknown measurement"
    assert reading.unit == ""
    assert reading.battery is None


def test_old_or_missing_timestamps_do_not_change_status() -> None:
    settings = Settings()
    old = normalize_summary(
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

    assert old.problem is False
    assert old.status_label == "online"
    assert missing.age_seconds is None
    assert missing.problem is False
    assert missing.status_label == "online"


def test_non_online_status_is_problem_state() -> None:
    reading = normalize_summary(
        "A1",
        {"transmitters": {"1": {"status": "offline", "status_code": 0}}},
        Settings(),
        now=datetime(2026, 4, 26, 10, 0, 30, tzinfo=UTC),
    )[0]

    assert reading.problem is True
    assert reading.status_label == "offline"
