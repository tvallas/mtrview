from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PACKAGE_DIR = Path(__file__).parent


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
    http_host: str = "0.0.0.0"
    http_port: int = 8000
    display_timezone: str = "UTC"
    refresh_interval_seconds: int = 20
    mqtt_enabled: bool = True
    mqtt_max_payload_bytes: int = 1_048_576
    mqtt_max_receivers: int = 128
    mqtt_max_transmitters_per_summary: int = 1_000
    mqtt_max_field_length: int = 512
    update_check_enabled: bool = True
    update_check_url: str = "https://api.github.com/repos/tvallas/mtrview/releases/latest"
    update_check_interval_seconds: int = 21600
    floorplan_config_path: str = "config/layout.yml"
    floorplan_svg_path: str = str(PACKAGE_DIR / "assets" / "sample-floorplan.svg")
    floorplan_upload_path: str = "config/floorplan.svg"
    floorplan_edit_flag_path: str = "config/edit.enabled"
    floorplan_edit_mode: str | None = None

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
            http_host=os.getenv("MTRVIEW_HTTP_HOST", cls.http_host),
            http_port=_get_int("MTRVIEW_HTTP_PORT", cls.http_port),
            display_timezone=os.getenv("MTRVIEW_DISPLAY_TIMEZONE", cls.display_timezone),
            refresh_interval_seconds=_get_int(
                "MTRVIEW_REFRESH_INTERVAL_SECONDS",
                cls.refresh_interval_seconds,
            ),
            mqtt_enabled=_get_bool("MTRVIEW_MQTT_ENABLED", cls.mqtt_enabled),
            mqtt_max_payload_bytes=_get_int(
                "MTRVIEW_MQTT_MAX_PAYLOAD_BYTES",
                cls.mqtt_max_payload_bytes,
            ),
            mqtt_max_receivers=_get_int(
                "MTRVIEW_MQTT_MAX_RECEIVERS",
                cls.mqtt_max_receivers,
            ),
            mqtt_max_transmitters_per_summary=_get_int(
                "MTRVIEW_MQTT_MAX_TRANSMITTERS_PER_SUMMARY",
                cls.mqtt_max_transmitters_per_summary,
            ),
            mqtt_max_field_length=_get_int(
                "MTRVIEW_MQTT_MAX_FIELD_LENGTH",
                cls.mqtt_max_field_length,
            ),
            update_check_enabled=_get_bool(
                "MTRVIEW_UPDATE_CHECK_ENABLED",
                cls.update_check_enabled,
            ),
            update_check_url=os.getenv("MTRVIEW_UPDATE_CHECK_URL", cls.update_check_url),
            update_check_interval_seconds=_get_int(
                "MTRVIEW_UPDATE_CHECK_INTERVAL_SECONDS",
                cls.update_check_interval_seconds,
            ),
            floorplan_config_path=os.getenv("MTRVIEW_FLOORPLAN_CONFIG", cls.floorplan_config_path),
            floorplan_svg_path=os.getenv("MTRVIEW_FLOORPLAN_SVG", cls.floorplan_svg_path),
            floorplan_upload_path=os.getenv(
                "MTRVIEW_FLOORPLAN_UPLOAD_PATH", cls.floorplan_upload_path
            ),
            floorplan_edit_flag_path=os.getenv(
                "MTRVIEW_FLOORPLAN_EDIT_FLAG", cls.floorplan_edit_flag_path
            ),
            floorplan_edit_mode=os.getenv("MTRVIEW_FLOORPLAN_EDIT_MODE") or None,
        )
