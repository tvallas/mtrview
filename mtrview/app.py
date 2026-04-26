from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from mtrview.config import Settings
from mtrview.mqtt import MqttStatus, MqttSubscriber
from mtrview.store import SummaryStore

PACKAGE_DIR = Path(__file__).parent


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = SummaryStore(settings)
    mqtt_subscriber: MqttSubscriber | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal mqtt_subscriber
        if settings.mqtt_enabled:
            mqtt_subscriber = MqttSubscriber(settings, store)
            mqtt_subscriber.start()
        yield
        if mqtt_subscriber is not None:
            mqtt_subscriber.stop()

    app = FastAPI(title="mtrview", lifespan=lifespan)
    app.state.settings = settings
    app.state.store = store
    app.state.mqtt_status = lambda: (
        mqtt_subscriber.status if mqtt_subscriber is not None else MqttStatus(False, "disabled")
    )

    templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
    app.mount("/static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "settings": settings,
                "snapshot": store.snapshot(),
                "mqtt_status": app.state.mqtt_status(),
            },
        )

    @app.get("/api/summary")
    async def api_summary() -> dict[str, object]:
        snapshot = store.snapshot()
        status = app.state.mqtt_status()
        snapshot["mqtt"] = {
            "connected": status.connected,
            "error": status.error,
            "last_message_at": snapshot["last_message_at"],
        }
        return snapshot

    @app.get("/health")
    async def health() -> dict[str, object]:
        status = app.state.mqtt_status()
        return {"ok": True, "mqtt_connected": status.connected, "mqtt_error": status.error}

    return app


app = create_app()
