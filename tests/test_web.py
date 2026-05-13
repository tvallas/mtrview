from __future__ import annotations

import json
import re
from pathlib import Path

from starlette.testclient import TestClient

from mtrview import __version__
from mtrview.app import create_app
from mtrview.config import Settings
from mtrview.version import VersionCheckResult


def test_health_endpoint() -> None:
    app = create_app(Settings(mqtt_enabled=False))
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_api_summary_shape() -> None:
    app = create_app(Settings(mqtt_enabled=False))
    app.state.store.update_from_json(
        "A1",
        """
        {
          "receiver": "A1",
          "transmitters": {
            "15006": {
              "location": "Kids room",
              "quantity": "Temperature",
              "measured_at": "2026-04-26T12:03:39Z",
              "status": "online",
              "status_code": 1,
              "battery": 2.6,
              "unit": "°C",
              "value": 22.3,
              "zone": "Indoor"
            }
          },
          "updated_at": "2026-04-26T12:04:03Z"
        }
        """,
    )

    with TestClient(app) as client:
        response = client.get("/api/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["counts"]["total"] == 1
    assert data["receivers"] == ["A1"]
    assert data["readings"][0]["display_name"] == "Kids room Temperature"
    assert data["readings"][0]["battery"] == 2.6


def test_malformed_payload_does_not_replace_existing_state() -> None:
    app = create_app(Settings(mqtt_enabled=False))
    app.state.store.update_from_json(
        "A1",
        '{"receiver":"A1","transmitters":{"1":{"status":"online","value":10}}}',
    )
    app.state.store.update_from_json("A1", "{not-json")

    with TestClient(app) as client:
        response = client.get("/api/summary")

    assert response.status_code == 200
    assert response.json()["counts"]["total"] == 1


def test_transmitter_update_without_reading_preserves_latest_reading() -> None:
    app = create_app(Settings(mqtt_enabled=False))
    app.state.store.update_from_json(
        "A1",
        """
        {
          "receiver": "A1",
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
              "zone": "Indoor"
            }
          },
          "updated_at": "2026-04-26T12:04:03Z"
        }
        """,
    )
    app.state.store.update_from_json(
        "A1",
        """
        {
          "receiver": "A1",
          "transmitters": {
            "15006": {
              "description": "Calibration date",
              "status": "online",
              "status_code": 1,
              "battery": 2.7
            }
          },
          "updated_at": "2026-04-26T12:05:03Z"
        }
        """,
    )

    with TestClient(app) as client:
        response = client.get("/api/summary")

    assert response.status_code == 200
    reading = response.json()["readings"][0]
    assert reading["display_name"] == "Kids room Temperature"
    assert reading["value"] == 22.3
    assert reading["unit"] == "°C"
    assert reading["measured_at"] == "2026-04-26T12:03:39Z"
    assert reading["battery"] == 2.7
    assert reading["updated_at"] == "2026-04-26T12:05:03Z"


def test_dashboard_html_smoke() -> None:
    app = create_app(Settings(mqtt_enabled=False))
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "mtrview" in response.text
    assert f"mtrview {__version__}" in response.text
    assert 'id="versionStatus"' in response.text
    assert "MTRVIEW_INITIAL_DATA" in response.text
    initial_data_match = re.search(r"window\.MTRVIEW_INITIAL_DATA = (.*);", response.text)
    assert initial_data_match is not None
    initial_data = json.loads(initial_data_match.group(1))
    assert initial_data["mqtt"] == {
        "connected": False,
        "error": "disabled",
        "last_message_at": None,
    }
    assert "/favicon.ico" in response.text
    assert "favicon.png" in response.text
    assert "apple-touch-icon.png" in response.text
    assert "mtrview-logo.png" in response.text
    assert re.search(r"app\.css\?v=\d+", response.text)
    assert re.search(r"floorplan-shared\.js\?v=\d+", response.text)
    assert re.search(r"app\.js\?v=\d+", response.text)
    assert "Latest mtr2mqtt summaries from MQTT" not in response.text
    assert "Not online" not in response.text
    assert "Offline" in response.text
    assert 'id="controlsToggle"' in response.text
    assert 'class="controls-collapsed"' in response.text
    assert "Filters" in response.text
    assert 'id="prioritySection" class="priority-section hidden"' in response.text
    assert 'id="tableView" class="table-wrap"' in response.text
    assert 'id="sensorDetailOverlay"' in response.text
    assert 'role="dialog"' in response.text
    assert 'data-sort="location"' in response.text
    assert 'data-sort="status"' not in response.text


def test_mobile_detail_styles_use_compact_rows() -> None:
    css = Path("mtrview/static/app.css").read_text()

    mobile_detail_match = re.search(
        r"@media \(max-width: 950px\) \{.*?\.detail-grid \{(?P<rules>.*?)\n  \}",
        css,
        re.DOTALL,
    )

    assert mobile_detail_match is not None
    assert "grid-template-columns: minmax(6rem, 34%) 1fr;" in mobile_detail_match.group("rules")
    assert "gap: 0;" in mobile_detail_match.group("rules")


def test_warning_styles_do_not_override_battery_icons() -> None:
    css = Path("mtrview/static/app.css").read_text()

    assert "\n.warning {" not in css
    assert ".editor-panel .warning {" in css


def test_no_color_floorplan_areas_are_transparent() -> None:
    js = Path("mtrview/static/floorplan-shared.js").read_text()
    css = Path("mtrview/static/app.css").read_text()

    assert 'band: "no_color", color: "transparent"' in js
    assert ".area-fill.no-color {" in css


def test_floorplan_mobile_and_fullscreen_hooks() -> None:
    html = create_app(Settings(mqtt_enabled=False)).state
    css = Path("mtrview/static/app.css").read_text()
    js = Path("mtrview/static/app.js").read_text()
    mobile_start = css.index("@media (max-width: 950px)")
    mobile_end = css.index("@media (max-width: 780px)")
    mobile_rules = css[mobile_start:mobile_end]
    landscape_start = css.index("@media (max-height: 520px) and (orientation: landscape)")
    landscape_end = css.index("@media (max-width: 640px)")
    landscape_rules = css[landscape_start:landscape_end]

    template = Path("mtrview/templates/index.html").read_text()

    assert "floorplanStage" in template
    assert "floorplanFullscreenButton" not in template
    assert 'aria-label="Toggle fullscreen floorplan"' in template
    assert 'role="button"' in template
    assert "requestFullscreen" in js
    assert "floorplan-expanded" in js
    assert "view-floorplan" in js
    assert "els.floorplanStage.addEventListener(\"click\"" in js
    assert 'event.key === "Enter" || event.key === " "' in js
    assert "floorplanFullscreenButton" not in js
    assert "@media (max-height: 520px) and (orientation: landscape)" in css
    assert ":fullscreen" in css
    assert "body.floorplan-expanded" in css
    assert ".metric-tile > span {\n    display: block;" in landscape_rules
    assert ".metric-tile strong {\n    display: flex;" in landscape_rules
    assert ".connection-tile strong {\n    flex-direction: row;" in landscape_rules
    assert ".metric-tile span {\n    display: none;" not in landscape_rules
    assert "if (view !== \"floorplan\")" in js
    assert (
        ".header-metrics {\n    grid-template-columns: repeat(4, minmax(0, 1fr));"
        in mobile_rules
    )
    assert ".summary-tile {\n    grid-column: 1 / 3;" in mobile_rules
    assert ".status-tile {\n    grid-column: 3 / 5;" in mobile_rules
    assert ".summary-tile {\n    min-width: 0;" in mobile_rules
    assert ".header-view-toggle {\n    grid-column: 1 / 4;" in mobile_rules
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in mobile_rules
    assert ".icon-button {\n    grid-column: 4 / 5;" in mobile_rules
    assert "width: 100%;" in mobile_rules
    assert "grid-column: 1 / -1;" not in mobile_rules
    assert ".topbar {\n    position: static;\n    display: grid;" in landscape_rules
    assert (
        "minmax(5.4rem, 0.55fr) minmax(5.4rem, 0.55fr) "
        "minmax(12rem, 1fr)"
    ) in landscape_rules
    assert (
        ".summary-tile,\n  .status-tile,\n  .header-view-toggle,\n  .icon-button"
        in landscape_rules
    )
    assert ".header-view-toggle {\n    grid-column: auto;" in landscape_rules
    assert ".icon-button {\n    min-width: 0;" in landscape_rules
    assert 'const statusText = connected ? "online" : mqttStatusLabel(message);' in js
    assert "body.floorplan-expanded .floorplan-actions" in css
    assert ".floorplan-view:fullscreen .floorplan-actions {\n  display: none;" in css
    assert ".floorplan-action," not in css
    assert ".floorplan-action:hover" not in css
    assert html is not None


def test_dashboard_view_is_persisted_across_refreshes() -> None:
    js = Path("mtrview/static/app.js").read_text()

    assert "MTRVIEW_VIEW_STORAGE_KEY" in js
    assert "initialView()" in js
    assert 'params.set("view", view)' in js
    assert "localStorage.setItem(MTRVIEW_VIEW_STORAGE_KEY, view)" in js


def test_api_version_uses_cached_checker_status() -> None:
    app = create_app(Settings(mqtt_enabled=False))
    app.state.version_checker = StubVersionChecker(
        VersionCheckResult(
            current_version="0.3.3",
            latest_version="0.4.0",
            update_available=True,
            checked_at=12.3,
            release_url="https://github.com/tvallas/mtrview/releases/tag/v0.4.0",
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/version")

    assert response.status_code == 200
    assert response.json() == {
        "current_version": "0.3.3",
        "latest_version": "0.4.0",
        "update_available": True,
        "checked_at": 12.3,
        "error": None,
        "release_url": "https://github.com/tvallas/mtrview/releases/tag/v0.4.0",
    }


def test_api_version_can_be_disabled() -> None:
    app = create_app(Settings(mqtt_enabled=False, update_check_enabled=False))

    with TestClient(app) as client:
        response = client.get("/api/version")

    assert response.status_code == 200
    assert response.json()["current_version"] == __version__
    assert response.json()["update_available"] is None
    assert response.json()["error"] == "disabled"


def test_api_summary_exposes_age_seconds_for_client_side_ticking() -> None:
    app = create_app(Settings(mqtt_enabled=False))
    app.state.store.update_from_json(
        "A1",
        """
        {
          "receiver": "A1",
          "transmitters": {
            "15006": {
              "measured_at": "2026-04-26T12:03:39Z",
              "status": "online",
              "value": 22.3
            }
          }
        }
        """,
    )

    with TestClient(app) as client:
        response = client.get("/api/summary")

    assert response.status_code == 200
    assert "age_seconds" in response.json()["readings"][0]


def test_favicon_ico_route() -> None:
    app = create_app(Settings(mqtt_enabled=False))
    with TestClient(app) as client:
        response = client.get("/favicon.ico")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/x-icon"


class StubVersionChecker:
    def __init__(self, result: VersionCheckResult) -> None:
        self.result = result

    def status(self) -> VersionCheckResult:
        return self.result
