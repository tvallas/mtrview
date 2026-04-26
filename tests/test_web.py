from __future__ import annotations

from fastapi.testclient import TestClient

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
    assert 'id="tableView" class="table-wrap"' in response.text
    assert 'data-sort="status"' in response.text
