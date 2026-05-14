from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from mtrview import __version__
from mtrview.config import Settings
from mtrview.floorplan import (
    DashboardConfig,
    active_asset_path,
    dark_floorplan_svg,
    floorplan_sensor_views,
    layout_metadata,
    load_floorplan_config,
    save_floorplan_config,
    svg_size,
)
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
                "static_version": request.app.state.static_version,
            },
        )

    async def floorplan_editor(request: Request) -> HTMLResponse:
        _require_floorplan_editing(settings)
        return templates.TemplateResponse(
            request,
            "floorplan_edit.html",
            {"settings": settings, "static_version": request.app.state.static_version},
        )

    async def floorplan_fullscreen(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "floorplan.html",
            {"settings": settings, "static_version": request.app.state.static_version},
        )

    async def floorplan_svg(request: Request) -> Response:
        asset_path = _floorplan_asset_path(settings)
        uploaded_asset_path = _floorplan_uploaded_asset_path(settings)
        active_path = active_asset_path(asset_path, uploaded_asset_path)
        if not active_path.exists():
            return JSONResponse({"detail": "floorplan SVG not found"}, status_code=404)
        return Response(dark_floorplan_svg(active_path), media_type="image/svg+xml")

    async def api_summary(request: Request) -> JSONResponse:
        return JSONResponse(_snapshot_with_mqtt(request))

    async def api_floorplan_config(request: Request) -> JSONResponse:
        if request.method == "GET":
            return JSONResponse(_load_floorplan_config(settings).to_dict())
        _require_floorplan_editing(settings)
        payload = await request.json()
        try:
            config = DashboardConfig.from_dict(payload)
        except (KeyError, TypeError, ValueError) as error:
            return JSONResponse({"detail": str(error)}, status_code=400)
        save_floorplan_config(_floorplan_config_path(settings), config)
        return JSONResponse(config.to_dict())

    async def api_floorplan_layout(request: Request) -> JSONResponse:
        asset_path = _floorplan_asset_path(settings)
        uploaded_asset_path = _floorplan_uploaded_asset_path(settings)
        if request.method == "GET":
            if not active_asset_path(asset_path, uploaded_asset_path).exists():
                return JSONResponse({"detail": "floorplan SVG not found"}, status_code=404)
            return JSONResponse(layout_metadata(asset_path, uploaded_asset_path))
        _require_floorplan_editing(settings)
        if request.method == "DELETE":
            if uploaded_asset_path.exists():
                uploaded_asset_path.unlink()
            if not active_asset_path(asset_path, uploaded_asset_path).exists():
                return JSONResponse({"detail": "floorplan SVG not found"}, status_code=404)
            return JSONResponse(layout_metadata(asset_path, uploaded_asset_path))

        try:
            svg = (await request.body()).decode("utf-8")
            svg_size(svg)
        except (UnicodeDecodeError, ValueError) as error:
            return JSONResponse({"detail": str(error)}, status_code=400)
        uploaded_asset_path.parent.mkdir(parents=True, exist_ok=True)
        uploaded_asset_path.write_text(svg, encoding="utf-8")
        return JSONResponse(layout_metadata(asset_path, uploaded_asset_path))

    async def api_floorplan_editing(request: Request) -> JSONResponse:
        return JSONResponse({"enabled": _floorplan_editing_enabled(settings)})

    async def api_floorplan_sensors(request: Request) -> JSONResponse:
        snapshot = store.snapshot()
        readings = snapshot.get("readings")
        if not isinstance(readings, list):
            readings = []
        return JSONResponse(floorplan_sensor_views(readings))

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
            Route("/floorplan", floorplan_fullscreen, methods=["GET"]),
            Route("/floorplan.svg", floorplan_svg, methods=["GET"]),
            Route("/floorplan/edit", floorplan_editor, methods=["GET"]),
            Route("/api/summary", api_summary, methods=["GET"]),
            Route("/api/floorplan/config", api_floorplan_config, methods=["GET", "PUT"]),
            Route(
                "/api/floorplan/layout",
                api_floorplan_layout,
                methods=["GET", "POST", "DELETE"],
            ),
            Route("/api/floorplan/editing", api_floorplan_editing, methods=["GET"]),
            Route("/api/floorplan/sensors", api_floorplan_sensors, methods=["GET"]),
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
    app.state.static_version = _static_version()
    app.state.mqtt_status = lambda: (
        mqtt_subscriber.status if mqtt_subscriber is not None else MqttStatus(False, "disabled")
    )

    return app


def _floorplan_config_path(settings: Settings) -> Path:
    return Path(settings.floorplan_config_path)


def _static_version() -> int:
    paths = [
        PACKAGE_DIR / "static" / "app.js",
        PACKAGE_DIR / "static" / "app.css",
        PACKAGE_DIR / "static" / "floorplan-shared.js",
        PACKAGE_DIR / "static" / "floorplan-fullscreen.js",
        PACKAGE_DIR / "static" / "floorplan-editor.js",
    ]
    return int(max(path.stat().st_mtime for path in paths if path.exists()))


def _bundled_floorplan_config_path() -> Path:
    return PACKAGE_DIR / "assets" / "layout.yml"


def _load_floorplan_config(settings: Settings) -> DashboardConfig:
    config_path = _floorplan_config_path(settings)
    if config_path.exists():
        return load_floorplan_config(config_path)
    return load_floorplan_config(_bundled_floorplan_config_path())


def _floorplan_asset_path(settings: Settings) -> Path:
    return Path(settings.floorplan_svg_path)


def _floorplan_uploaded_asset_path(settings: Settings) -> Path:
    return Path(settings.floorplan_upload_path)


def _floorplan_edit_flag_path(settings: Settings) -> Path:
    return Path(settings.floorplan_edit_flag_path)


def _require_floorplan_editing(settings: Settings) -> None:
    if not _floorplan_editing_enabled(settings):
        raise HTTPException(status_code=403, detail="floorplan editing is disabled")


def _floorplan_editing_enabled(settings: Settings) -> bool:
    mode = (settings.floorplan_edit_mode or "").strip().lower()
    if mode:
        if mode in {"1", "true", "yes", "on", "always", "enabled"}:
            return True
        if mode in {"0", "false", "no", "off", "never", "disabled"}:
            return False
        if mode != "flag":
            return False
    return _floorplan_edit_flag_path(settings).exists()


app = create_app()
