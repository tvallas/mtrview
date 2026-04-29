from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from mtrview import __version__
from mtrview.config import Settings
from mtrview.mqtt import MqttStatus, MqttSubscriber
from mtrview.store import SummaryStore
from mtrview.version import VersionChecker

PACKAGE_DIR = Path(__file__).parent


def create_app(settings: Settings | None = None) -> Starlette:
    settings = settings or Settings.from_env()
    store = SummaryStore(settings)
    mqtt_subscriber: MqttSubscriber | None = None

    @asynccontextmanager
    async def lifespan(app: Starlette):
        nonlocal mqtt_subscriber
        if settings.mqtt_enabled:
            mqtt_subscriber = MqttSubscriber(settings, store)
            mqtt_subscriber.start()
        yield
        if mqtt_subscriber is not None:
            mqtt_subscriber.stop()

    templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))

    async def favicon(request: Request) -> FileResponse:
        return FileResponse(PACKAGE_DIR / "static" / "favicon.ico", media_type="image/x-icon")

    async def dashboard(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "settings": settings,
                "snapshot": _snapshot_with_mqtt(request),
                "mqtt_status": request.app.state.mqtt_status(),
                "app_info": {"version": __version__},
            },
        )

    async def api_summary(request: Request) -> JSONResponse:
        return JSONResponse(_snapshot_with_mqtt(request))

    async def api_version(request: Request) -> JSONResponse:
        status = await run_in_threadpool(request.app.state.version_checker.status)
        return JSONResponse(
            {
                "current_version": status.current_version,
                "latest_version": status.latest_version,
                "update_available": status.update_available,
                "checked_at": status.checked_at,
                "error": status.error,
                "release_url": status.release_url,
            }
        )

    def _snapshot_with_mqtt(request: Request) -> dict[str, object]:
        snapshot = store.snapshot()
        status = request.app.state.mqtt_status()
        snapshot["mqtt"] = {
            "connected": status.connected,
            "error": status.error,
            "last_message_at": snapshot["last_message_at"],
        }
        return snapshot

    async def health(request: Request) -> JSONResponse:
        status = request.app.state.mqtt_status()
        return JSONResponse(
            {"ok": True, "mqtt_connected": status.connected, "mqtt_error": status.error}
        )

    app = Starlette(
        lifespan=lifespan,
        routes=[
            Route("/favicon.ico", favicon, methods=["GET"]),
            Route("/", dashboard, methods=["GET"]),
            Route("/api/summary", api_summary, methods=["GET"]),
            Route("/api/version", api_version, methods=["GET"]),
            Route("/health", health, methods=["GET"]),
            Mount("/static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="static"),
        ],
    )
    app.state.settings = settings
    app.state.store = store
    app.state.version_checker = VersionChecker(
        current_version=__version__,
        enabled=settings.update_check_enabled,
        url=settings.update_check_url,
        interval_seconds=settings.update_check_interval_seconds,
    )
    app.state.mqtt_status = lambda: (
        mqtt_subscriber.status if mqtt_subscriber is not None else MqttStatus(False, "disabled")
    )

    return app


app = create_app()
