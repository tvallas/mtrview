from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_LAYOUT_SIZE = (2507.0, 1107.0)
SVG_LENGTH_PATTERN = re.compile(r"^-?\d+(?:\.\d+)?")


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Point:
        return cls(x=float(data["x"]), y=float(data["y"]))

    def to_dict(self) -> dict[str, float]:
        return {"x": float(self.x), "y": float(self.y)}


@dataclass(frozen=True)
class ThresholdProfile:
    normal_min: float
    normal_max: float
    cool: float
    cold: float
    warm: float
    hot: float
    color_enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThresholdProfile:
        return cls(
            normal_min=float(data["normal_min"]),
            normal_max=float(data["normal_max"]),
            cool=float(data["cool"]),
            cold=float(data["cold"]),
            warm=float(data["warm"]),
            hot=float(data["hot"]),
            color_enabled=_bool(data.get("color_enabled", True)),
        )

    def to_dict(self) -> dict[str, float | bool]:
        return {
            "normal_min": float(self.normal_min),
            "normal_max": float(self.normal_max),
            "cool": float(self.cool),
            "cold": float(self.cold),
            "warm": float(self.warm),
            "hot": float(self.hot),
            "color_enabled": self.color_enabled,
        }


@dataclass(frozen=True)
class AreaMapping:
    id: str
    name: str
    location: str
    description: str | None
    quantity: str
    sensor_key: str
    profile: str
    points: list[Point]
    label_position: Point | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AreaMapping:
        points = [Point.from_dict(point) for point in data.get("points", [])]
        if len(points) < 3:
            raise ValueError("area mappings must contain at least three polygon points")
        label_position = (
            Point.from_dict(data["label_position"]) if data.get("label_position") else None
        )
        location = str(data["location"])
        description = str(data["description"]) if data.get("description") else None
        quantity = str(data.get("quantity") or "Temperature")
        return cls(
            id=str(data["id"]),
            name=str(data.get("name") or data["id"]),
            location=location,
            description=description,
            quantity=quantity,
            sensor_key=str(data.get("sensor_key") or sensor_key(location, description, quantity)),
            profile=str(data.get("profile") or "room"),
            points=points,
            label_position=label_position,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "description": self.description,
            "quantity": self.quantity,
            "sensor_key": self.sensor_key,
            "profile": self.profile,
            "points": [point.to_dict() for point in self.points],
            "label_position": self.label_position.to_dict() if self.label_position else None,
        }


@dataclass(frozen=True)
class DashboardConfig:
    profiles: dict[str, ThresholdProfile]
    areas: list[AreaMapping]

    @classmethod
    def default(cls) -> DashboardConfig:
        return cls(
            profiles={
                "room": ThresholdProfile(21, 23, 19, 17, 24, 26),
                "fridge": ThresholdProfile(2, 6, 1, -1, 7, 10),
                "freezer": ThresholdProfile(-24, -16, -28, -32, -14, -10),
                "cold_storage": ThresholdProfile(4, 10, 2, 0, 12, 16),
                "outside": ThresholdProfile(-5, 22, -15, -25, 26, 32),
                "no_color": ThresholdProfile(
                    -999, 999, -999, -999, 999, 999, color_enabled=False
                ),
            },
            areas=[],
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DashboardConfig:
        default_profiles = cls.default().profiles
        profiles = {
            name: ThresholdProfile.from_dict(profile)
            for name, profile in data.get("profiles", {}).items()
        }
        profiles = default_profiles | profiles
        return cls(
            profiles=profiles,
            areas=[AreaMapping.from_dict(area) for area in data.get("areas", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "profiles": {name: profile.to_dict() for name, profile in self.profiles.items()},
            "areas": [area.to_dict() for area in self.areas],
        }


def sensor_key(location: str, description: str | None = None, quantity: str | None = None) -> str:
    parts = [location]
    if description:
        parts.append(description)
    if quantity:
        parts.append(quantity)
    return "::".join(parts)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", "disabled"}
    return bool(value)


def load_floorplan_config(path: Path) -> DashboardConfig:
    if not path.exists():
        return DashboardConfig.default()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return DashboardConfig.default()
    return DashboardConfig.from_dict(data)


def save_floorplan_config(path: Path, config: DashboardConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config.to_dict(), sort_keys=False), encoding="utf-8")


def dark_floorplan_svg(asset_path: Path) -> str:
    svg = asset_path.read_text(encoding="utf-8")
    replacements = {
        "background: #ffffff;": "background: #121212;",
        "background-color: light-dark(#ffffff, var(--ge-dark-color, #121212));": (
            "background-color: #121212;"
        ),
        "color-scheme: light dark;": "color-scheme: dark;",
        "light-dark(rgb(0, 0, 0), rgb(237, 237, 237))": "rgb(237, 237, 237)",
        "light-dark(rgb(0, 0, 0), rgb(255, 255, 255))": "rgb(255, 255, 255)",
    }
    for old, new in replacements.items():
        svg = svg.replace(old, new)
    return svg


def active_asset_path(asset_path: Path, uploaded_asset_path: Path) -> Path:
    if uploaded_asset_path.exists():
        return uploaded_asset_path
    return asset_path


def layout_metadata(asset_path: Path, uploaded_asset_path: Path) -> dict[str, Any]:
    active_path = active_asset_path(asset_path, uploaded_asset_path)
    width, height = svg_size(active_path.read_text(encoding="utf-8"))
    source = "uploaded" if uploaded_asset_path.exists() else "bundled"
    stat = active_path.stat()
    return {
        "source": source,
        "uploaded": source == "uploaded",
        "url": "/floorplan.svg",
        "width": width,
        "height": height,
        "updated_at": stat.st_mtime,
    }


def svg_size(svg: str) -> tuple[float, float]:
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as error:
        raise ValueError("layout file must be valid SVG") from error

    if local_name(root.tag) != "svg":
        raise ValueError("layout file must be an SVG document")

    view_box = root.attrib.get("viewBox")
    if view_box:
        try:
            values = [float(value) for value in re.split(r"[\s,]+", view_box.strip()) if value]
        except ValueError:
            values = []
        if len(values) == 4 and values[2] > 0 and values[3] > 0:
            return values[2], values[3]

    width = parse_svg_length(root.attrib.get("width"))
    height = parse_svg_length(root.attrib.get("height"))
    if width and height:
        return width, height
    return DEFAULT_LAYOUT_SIZE


def parse_svg_length(value: str | None) -> float | None:
    if not value:
        return None
    match = SVG_LENGTH_PATTERN.match(value.strip())
    if not match:
        return None
    parsed = float(match.group(0))
    return parsed if parsed > 0 else None


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def floorplan_sensor_views(readings: list[dict[str, object | None]]) -> list[dict[str, object]]:
    sensors = []
    for reading in sorted(readings, key=lambda item: str(item.get("sort_key") or "")):
        key = sensor_key(
            str(reading.get("location") or ""),
            str(reading.get("description") or "") or None,
            str(reading.get("quantity") or "") or None,
        )
        sensors.append(
            {
                "key": key,
                "label": floorplan_sensor_label(reading),
                "location": reading.get("location"),
                "description": reading.get("description") or None,
                "quantity": reading.get("quantity"),
                "duplicate": False,
                "topics": [f"summary/{reading.get('receiver')}/{reading.get('transmitter_id')}"],
                "sensor_ids": [str(reading.get("transmitter_id"))],
                "latest": floorplan_measurement(reading, key),
            }
        )
    return sensors


def floorplan_measurement(
    reading: dict[str, object | None], key: str
) -> dict[str, object | None]:
    return {
        "key": key,
        "label": floorplan_sensor_label(reading),
        "location": reading.get("location"),
        "description": reading.get("description") or None,
        "quantity": reading.get("quantity"),
        "value": reading.get("value"),
        "topic": f"summary/{reading.get('receiver')}/{reading.get('transmitter_id')}",
        "sensor_id": reading.get("transmitter_id"),
        "unit": reading.get("unit"),
        "observed_at": reading.get("measured_at"),
        "received_at": reading.get("updated_at") or reading.get("measured_at"),
    }


def floorplan_sensor_label(reading: dict[str, object | None]) -> str:
    parts = [
        str(reading.get("location") or ""),
        str(reading.get("description") or ""),
        str(reading.get("quantity") or ""),
    ]
    label = " - ".join(part for part in parts if part)
    return label or str(reading.get("display_name") or "No sensor")
