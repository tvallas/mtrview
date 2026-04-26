from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from typing import Any

from mtrview.config import Settings
from mtrview.models import ReadingView
from mtrview.normalization import normalize_summary

LOGGER = logging.getLogger(__name__)


class SummaryStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.RLock()
        self._raw_by_receiver: dict[str, dict[str, Any]] = {}
        self._last_message_at: datetime | None = None

    def update_from_json(self, receiver_hint: str, payload: bytes | str) -> None:
        try:
            decoded = payload.decode("utf-8") if isinstance(payload, bytes) else payload
            data = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError):
            LOGGER.exception("Failed to decode MQTT summary payload for %s", receiver_hint)
            return

        if not isinstance(data, dict):
            LOGGER.warning("Ignoring non-object MQTT summary payload for %s", receiver_hint)
            return

        receiver = str(data.get("receiver") or receiver_hint or "unknown")
        with self._lock:
            self._raw_by_receiver[receiver] = data
            self._last_message_at = datetime.now(UTC)

    def readings(self, now: datetime | None = None) -> list[ReadingView]:
        now = now or datetime.now(UTC)
        with self._lock:
            snapshots = list(self._raw_by_receiver.items())
        readings: list[ReadingView] = []
        for receiver, payload in snapshots:
            readings.extend(normalize_summary(receiver, payload, self._settings, now=now))
        return sorted(readings, key=lambda item: item.sort_key)

    def snapshot(self) -> dict[str, object]:
        readings = self.readings()
        receivers = sorted({reading.receiver for reading in readings})
        zones = sorted({reading.zone for reading in readings})
        counts = _counts(readings, len(receivers))
        return {
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "last_message_at": self.last_message_at,
            "mqtt": {"last_message_at": self.last_message_at},
            "counts": counts,
            "receivers": receivers,
            "zones": zones,
            "readings": [reading.to_dict() for reading in readings],
        }

    @property
    def last_message_at(self) -> str | None:
        with self._lock:
            if self._last_message_at is None:
                return None
            return self._last_message_at.isoformat().replace("+00:00", "Z")


def _counts(readings: list[ReadingView], receiver_count: int) -> dict[str, int]:
    return {
        "total": len(readings),
        "online": sum(1 for reading in readings if reading.status == "online"),
        "offline": sum(1 for reading in readings if reading.status != "online"),
        "receivers": receiver_count,
    }
