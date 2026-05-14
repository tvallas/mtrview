from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from mtrview.app import create_app
from mtrview.config import Settings
from mtrview.floorplan import (
    AreaMapping,
    DashboardConfig,
    Point,
    ThresholdProfile,
    load_floorplan_config,
    save_floorplan_config,
)


def test_floorplan_config_load_save_round_trip(tmp_path: Path) -> None:
    config_path = tmp_path / "layout.yml"
    config = DashboardConfig(
        profiles={"room": ThresholdProfile(21, 23, 19, 17, 24, 26)},
        areas=[
            AreaMapping(
                id="living-room",
                name="Living room",
                location="Living room",
                description="Ambient air",
                quantity="Temperature",
                sensor_key="Living room::Ambient air::Temperature",
                profile="room",
                points=[Point(1, 2), Point(3, 4), Point(5, 6)],
            )
        ],
    )

    save_floorplan_config(config_path, config)

    loaded = load_floorplan_config(config_path)
    assert loaded.profiles["room"].to_dict() == config.profiles["room"].to_dict()
    assert loaded.profiles["no_color"].color_enabled is False
    assert [area.to_dict() for area in loaded.areas] == [area.to_dict() for area in config.areas]


def test_floorplan_default_config_includes_no_color_profile() -> None:
    config = DashboardConfig.default()

    assert config.profiles["no_color"].color_enabled is False
    assert config.profiles["no_color"].normal_min < -100
    assert config.profiles["no_color"].normal_max > 100
    assert config.profiles["room"].color_enabled is True
    assert config.profiles["no_color"].to_dict()["color_enabled"] is False


def test_floorplan_config_rejects_area_with_too_few_points() -> None:
    with pytest.raises(ValueError, match="at least three"):
        DashboardConfig.from_dict(
            {
                "profiles": {"room": DashboardConfig.default().profiles["room"].to_dict()},
                "areas": [
                    {
                        "id": "bad",
                        "location": "Bad",
                        "points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}],
                    }
                ],
            }
        )


def test_settings_reads_floorplan_env_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MTRVIEW_FLOORPLAN_CONFIG", "/tmp/mtrview-layout.yml")
    monkeypatch.setenv("MTRVIEW_FLOORPLAN_SVG", "/tmp/floorplan.svg")
    monkeypatch.setenv("MTRVIEW_FLOORPLAN_UPLOAD_PATH", "/tmp/uploaded.svg")
    monkeypatch.setenv("MTRVIEW_FLOORPLAN_EDIT_FLAG", "/tmp/edit.enabled")
    monkeypatch.setenv("MTRVIEW_FLOORPLAN_EDIT_MODE", "always")

    settings = Settings.from_env()

    assert settings.floorplan_config_path == "/tmp/mtrview-layout.yml"
    assert settings.floorplan_svg_path == "/tmp/floorplan.svg"
    assert settings.floorplan_upload_path == "/tmp/uploaded.svg"
    assert settings.floorplan_edit_flag_path == "/tmp/edit.enabled"
    assert settings.floorplan_edit_mode == "always"


def test_dashboard_html_includes_floorplan_view() -> None:
    app = create_app(Settings(mqtt_enabled=False))

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert 'id="floorplanViewButton"' in response.text
    assert 'id="floorplanView"' in response.text
    assert "MTRVIEW_FLOORPLAN_CONFIG" in response.text


def test_floorplan_layout_api_reports_bundled_svg_metadata(tmp_path: Path) -> None:
    asset_path = tmp_path / "floorplan.svg"
    asset_path.write_text(
        '<svg viewBox="0 0 1200 800"><rect width="1200" height="800"/></svg>',
        encoding="utf-8",
    )
    app = create_app(
        Settings(
            mqtt_enabled=False,
            floorplan_svg_path=str(asset_path),
            floorplan_upload_path=str(tmp_path / "uploaded.svg"),
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/floorplan/layout")

    assert response.status_code == 200
    assert response.json()["source"] == "bundled"
    assert response.json()["uploaded"] is False
    assert response.json()["width"] == 1200
    assert response.json()["height"] == 800


def test_floorplan_config_api_falls_back_to_bundled_layout(tmp_path: Path) -> None:
    app = create_app(
        Settings(mqtt_enabled=False, floorplan_config_path=str(tmp_path / "missing.yml"))
    )

    with TestClient(app) as client:
        response = client.get("/api/floorplan/config")

    assert response.status_code == 200
    assert response.json()["areas"][0]["name"] == "Room A"
    assert any(area["name"] == "Room D" for area in response.json()["areas"])
    assert response.json()["profiles"]["no_color"]["color_enabled"] is False
    assert any(
        area["name"] == "Outdoor" and area["profile"] == "no_color"
        for area in response.json()["areas"]
    )


def test_floorplan_layout_api_uploads_and_resets_svg(tmp_path: Path) -> None:
    asset_path = tmp_path / "floorplan.svg"
    uploaded_asset_path = tmp_path / "uploaded.svg"
    edit_flag_path = tmp_path / "edit.enabled"
    asset_path.write_text(
        '<svg viewBox="0 0 1200 800"><rect width="1200" height="800"/></svg>',
        encoding="utf-8",
    )
    app = create_app(
        Settings(
            mqtt_enabled=False,
            floorplan_svg_path=str(asset_path),
            floorplan_upload_path=str(uploaded_asset_path),
            floorplan_edit_flag_path=str(edit_flag_path),
            floorplan_edit_mode="always",
        )
    )

    with TestClient(app) as client:
        upload_response = client.post(
            "/api/floorplan/layout",
            content='<svg viewBox="0 0 500 250"><path d="M0 0"/></svg>',
            headers={"Content-Type": "image/svg+xml"},
        )

        assert upload_response.status_code == 200
        assert upload_response.json()["source"] == "uploaded"
        assert upload_response.json()["width"] == 500
        assert upload_response.json()["height"] == 250
        assert uploaded_asset_path.read_text(encoding="utf-8").startswith("<svg")
        assert "500 250" in client.get("/floorplan.svg").text

        reset_response = client.delete("/api/floorplan/layout")

    assert reset_response.status_code == 200
    assert reset_response.json()["source"] == "bundled"
    assert not uploaded_asset_path.exists()


def test_floorplan_layout_api_rejects_invalid_svg(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            mqtt_enabled=False,
            floorplan_svg_path=str(tmp_path / "missing.svg"),
            floorplan_upload_path=str(tmp_path / "uploaded.svg"),
            floorplan_edit_mode="always",
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/floorplan/layout",
            content="<html></html>",
            headers={"Content-Type": "image/svg+xml"},
        )

    assert response.status_code == 400


def test_floorplan_editing_is_disabled_without_flag_or_env_override(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            mqtt_enabled=False,
            floorplan_config_path=str(tmp_path / "layout.yml"),
            floorplan_svg_path=str(tmp_path / "missing.svg"),
            floorplan_upload_path=str(tmp_path / "uploaded.svg"),
            floorplan_edit_flag_path=str(tmp_path / "edit.enabled"),
        )
    )

    with TestClient(app) as client:
        assert client.get("/api/floorplan/editing").json() == {"enabled": False}
        assert client.get("/floorplan/edit").status_code == 403
        assert (
            client.put(
                "/api/floorplan/config", json=DashboardConfig.default().to_dict()
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/floorplan/layout",
                content="<svg></svg>",
                headers={"Content-Type": "image/svg+xml"},
            ).status_code
            == 403
        )
        assert client.delete("/api/floorplan/layout").status_code == 403


def test_floorplan_editing_can_be_enabled_with_flag_file(tmp_path: Path) -> None:
    flag_path = tmp_path / "edit.enabled"
    flag_path.touch()
    app = create_app(
        Settings(
            mqtt_enabled=False,
            floorplan_config_path=str(tmp_path / "layout.yml"),
            floorplan_edit_flag_path=str(flag_path),
        )
    )

    with TestClient(app) as client:
        assert client.get("/api/floorplan/editing").json() == {"enabled": True}
        assert client.get("/floorplan/edit").status_code == 200
        assert (
            client.put(
                "/api/floorplan/config", json=DashboardConfig.default().to_dict()
            ).status_code
            == 200
        )


def test_floorplan_edit_mode_env_override_takes_precedence_over_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flag_path = tmp_path / "edit.enabled"
    flag_path.touch()
    monkeypatch.setenv("MTRVIEW_FLOORPLAN_EDIT_MODE", "never")
    app = create_app(
        replace(
            Settings.from_env(),
            mqtt_enabled=False,
            floorplan_config_path=str(tmp_path / "layout.yml"),
            floorplan_edit_flag_path=str(flag_path),
        )
    )

    with TestClient(app) as client:
        assert client.get("/floorplan/edit").status_code == 403

    monkeypatch.setenv("MTRVIEW_FLOORPLAN_EDIT_MODE", "always")
    app = create_app(
        replace(
            Settings.from_env(),
            mqtt_enabled=False,
            floorplan_config_path=str(tmp_path / "layout.yml"),
            floorplan_edit_flag_path=str(tmp_path / "missing.enabled"),
        )
    )

    with TestClient(app) as client:
        assert client.get("/floorplan/edit").status_code == 200


def test_floorplan_sensors_api_uses_existing_summary_readings() -> None:
    app = create_app(Settings(mqtt_enabled=False))
    app.state.store.update_from_json(
        "A1",
        """
        {
          "receiver": "A1",
          "transmitters": {
            "15006": {
              "location": "Living room",
              "description": "Ambient air",
              "quantity": "Temperature",
              "measured_at": "2026-04-26T12:03:39Z",
              "status": "online",
              "battery": 2.6,
              "unit": "°C",
              "value": 22.3
            }
          }
        }
        """,
    )

    with TestClient(app) as client:
        response = client.get("/api/floorplan/sensors")

    assert response.status_code == 200
    assert response.json()[0]["key"] == "Living room::Ambient air::Temperature"
    assert response.json()[0]["latest"]["value"] == 22.3


def test_floorplan_editor_html_smoke() -> None:
    app = create_app(Settings(mqtt_enabled=False, floorplan_edit_mode="always"))

    with TestClient(app) as client:
        response = client.get("/floorplan/edit")

    assert response.status_code == 200
    assert re.search(r'id="area-list"', response.text)
    assert 'id="add-profile"' in response.text
    assert 'id="profile-color-enabled"' in response.text
    assert re.search(r"floorplan-shared\.js\?v=\d+", response.text)
    assert re.search(r"floorplan-editor\.js\?v=\d+", response.text)


def test_floorplan_fullscreen_html_smoke() -> None:
    app = create_app(Settings(mqtt_enabled=False))

    with TestClient(app) as client:
        response = client.get("/floorplan")

    assert response.status_code == 200
    assert 'class="floorplan-direct-page"' in response.text
    assert 'aria-label="Fullscreen floorplan"' in response.text
    assert 'id="floorplanStage"' in response.text
    assert 'href="/?view=floorplan"' in response.text
    assert re.search(r"floorplan-shared\.js\?v=\d+", response.text)
    assert re.search(r"floorplan-fullscreen\.js\?v=\d+", response.text)
