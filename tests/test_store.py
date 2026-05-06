from __future__ import annotations

import json

from mtrview.config import Settings
from mtrview.store import SummaryStore


def test_rejects_payloads_larger_than_configured_limit() -> None:
    store = SummaryStore(Settings(mqtt_max_payload_bytes=64))

    store.update_from_json(
        "A1",
        json.dumps(
            {
                "receiver": "A1",
                "transmitters": {
                    "1": {
                        "status": "online",
                        "value": 10,
                        "description": "x" * 128,
                    }
                },
            }
        ),
    )

    assert store.snapshot()["counts"]["total"] == 0


def test_rejects_new_receiver_when_receiver_limit_is_reached() -> None:
    store = SummaryStore(Settings(mqtt_max_receivers=1))
    store.update_from_json("A1", _summary("A1", {"1": {"status": "online", "value": 10}}))

    store.update_from_json("A2", _summary("A2", {"1": {"status": "online", "value": 11}}))

    snapshot = store.snapshot()
    assert snapshot["counts"]["total"] == 1
    assert snapshot["receivers"] == ["A1"]


def test_allows_existing_receiver_update_when_receiver_limit_is_reached() -> None:
    store = SummaryStore(Settings(mqtt_max_receivers=1))
    store.update_from_json("A1", _summary("A1", {"1": {"status": "online", "value": 10}}))

    store.update_from_json("A1", _summary("A1", {"1": {"status": "online", "value": 11}}))

    reading = store.snapshot()["readings"][0]
    assert reading["value"] == 11


def test_rejects_summary_with_too_many_transmitters() -> None:
    store = SummaryStore(Settings(mqtt_max_transmitters_per_summary=1))
    store.update_from_json("A1", _summary("A1", {"1": {"status": "online", "value": 10}}))

    store.update_from_json(
        "A1",
        _summary(
            "A1",
            {
                "1": {"status": "online", "value": 11},
                "2": {"status": "online", "value": 12},
            },
        ),
    )

    reading = store.snapshot()["readings"][0]
    assert reading["transmitter_id"] == "1"
    assert reading["value"] == 10


def test_rejects_summary_with_overlong_display_field() -> None:
    store = SummaryStore(Settings(mqtt_max_field_length=16))

    store.update_from_json(
        "A1",
        _summary(
            "A1",
            {
                "1": {
                    "location": "x" * 17,
                    "status": "online",
                    "value": 10,
                }
            },
        ),
    )

    assert store.snapshot()["counts"]["total"] == 0


def _summary(receiver: str, transmitters: dict[str, dict[str, object]]) -> str:
    return json.dumps({"receiver": receiver, "transmitters": transmitters})
