from __future__ import annotations

import os
from dataclasses import dataclass


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _get_topics(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if not value:
        return default
    return tuple(topic.strip() for topic in value.split(",") if topic.strip())


@dataclass(frozen=True)
class Settings:
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_topics: tuple[str, ...] = ("summary/#",)
    mqtt_client_id: str = "mtrview"
    mqtt_keepalive: int = 60
    stale_after_seconds: int = 3600
    critical_stale_after_seconds: int = 21600
    http_host: str = "0.0.0.0"
    http_port: int = 8000
    display_timezone: str = "UTC"
    refresh_interval_seconds: int = 20
    mqtt_enabled: bool = True

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            mqtt_host=os.getenv("MTRVIEW_MQTT_HOST", cls.mqtt_host),
            mqtt_port=_get_int("MTRVIEW_MQTT_PORT", cls.mqtt_port),
            mqtt_username=os.getenv("MTRVIEW_MQTT_USERNAME") or None,
            mqtt_password=os.getenv("MTRVIEW_MQTT_PASSWORD") or None,
            mqtt_topics=_get_topics("MTRVIEW_MQTT_TOPICS", cls.mqtt_topics),
            mqtt_client_id=os.getenv("MTRVIEW_MQTT_CLIENT_ID", cls.mqtt_client_id),
            mqtt_keepalive=_get_int("MTRVIEW_MQTT_KEEPALIVE", cls.mqtt_keepalive),
            stale_after_seconds=_get_int("MTRVIEW_STALE_AFTER_SECONDS", cls.stale_after_seconds),
            critical_stale_after_seconds=_get_int(
                "MTRVIEW_CRITICAL_STALE_AFTER_SECONDS",
                cls.critical_stale_after_seconds,
            ),
            http_host=os.getenv("MTRVIEW_HTTP_HOST", cls.http_host),
            http_port=_get_int("MTRVIEW_HTTP_PORT", cls.http_port),
            display_timezone=os.getenv("MTRVIEW_DISPLAY_TIMEZONE", cls.display_timezone),
            refresh_interval_seconds=_get_int(
                "MTRVIEW_REFRESH_INTERVAL_SECONDS",
                cls.refresh_interval_seconds,
            ),
            mqtt_enabled=_get_bool("MTRVIEW_MQTT_ENABLED", cls.mqtt_enabled),
        )
