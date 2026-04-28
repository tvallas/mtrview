from __future__ import annotations

import json
import re

from starlette.testclient import TestClient

from mtrview.app import create_app
from mtrview.config import Settings


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


def test_dashboard_html_smoke() -> None:
    app = create_app(Settings(mqtt_enabled=False))
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "mtrview" in response.text
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
