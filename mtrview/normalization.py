from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from mtrview.config import Settings
from mtrview.models import ReadingView

LOGGER = logging.getLogger(__name__)


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        LOGGER.warning("Invalid timestamp in summary payload: %r", value)
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def normalize_summary(
    receiver_hint: str,
    payload: dict[str, Any],
    settings: Settings,
    now: datetime | None = None,
) -> list[ReadingView]:
    now = now or datetime.now(UTC)
    receiver = str(payload.get("receiver") or receiver_hint or "unknown")
    updated_at = _string_or_none(payload.get("updated_at"))
    transmitters = payload.get("transmitters")
    if not isinstance(transmitters, dict):
        LOGGER.warning("Summary for receiver %s has no transmitter mapping", receiver)
        return []

    readings: list[ReadingView] = []
    for transmitter_id, raw_reading in transmitters.items():
        if not isinstance(raw_reading, dict):
            LOGGER.warning(
                "Skipping malformed transmitter %s for receiver %s", transmitter_id, receiver
            )
            continue
        readings.append(
            normalize_transmitter(
                receiver=receiver,
                transmitter_id=str(transmitter_id),
                raw=raw_reading,
                summary_updated_at=updated_at,
                settings=settings,
                now=now,
            )
        )
    return readings


def normalize_transmitter(
    receiver: str,
    transmitter_id: str,
    raw: dict[str, Any],
    summary_updated_at: str | None,
    settings: Settings,
    now: datetime,
) -> ReadingView:
    location = _clean(raw.get("location"), "Unknown location")
    zone = _clean(raw.get("zone"), "Unknown zone")
    quantity = _clean(raw.get("quantity"), "Unknown measurement")
    description = _clean(raw.get("description"), "")
    unit = _clean(raw.get("unit"), "")
    status = _clean(raw.get("status"), "unknown").lower()
    status_code = _int_or_none(raw.get("status_code"))
    measured_at = _string_or_none(raw.get("measured_at"))
    measured_dt = parse_timestamp(measured_at)
    age_seconds = None
    if measured_dt is not None:
        age_seconds = max(0, int((now - measured_dt).total_seconds()))

    stale = age_seconds is None or age_seconds >= settings.stale_after_seconds
    critical_stale = age_seconds is None or age_seconds >= settings.critical_stale_after_seconds
    online = status == "online"
    problem = (not online) or stale
    status_label = _status_label(status, stale, critical_stale)
    display_name = _display_name(location, quantity, description, transmitter_id)
    sort_key = "|".join(
        [
            "0" if problem else "1",
            zone.casefold(),
            location.casefold(),
            quantity.casefold(),
            transmitter_id,
        ]
    )

    return ReadingView(
        receiver=receiver,
        transmitter_id=transmitter_id,
        display_name=display_name,
        location=location,
        zone=zone,
        quantity=quantity,
        description=description,
        value=raw.get("value"),
        unit=unit,
        measured_at=measured_at,
        updated_at=summary_updated_at,
        status=status,
        status_code=status_code,
        age_seconds=age_seconds,
        stale=stale,
        critical_stale=critical_stale,
        problem=problem,
        status_label=status_label,
        sort_key=sort_key,
    )


def _display_name(location: str, quantity: str, description: str, transmitter_id: str) -> str:
    if location != "Unknown location" and quantity != "Unknown measurement":
        return f"{location} {quantity}"
    if description:
        return description
    if location != "Unknown location":
        return location
    if quantity != "Unknown measurement":
        return quantity
    return f"Transmitter {transmitter_id}"


def _status_label(status: str, stale: bool, critical_stale: bool) -> str:
    if status != "online":
        return "offline"
    if critical_stale:
        return "critical stale"
    if stale:
        return "stale"
    return "ok"


def _clean(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
