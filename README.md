<p align="center">
  <img src="mtrview/static/mtrview-logo.png" alt="mtrview" width="360">
</p>

# mtrview

[![CI](https://github.com/tvallas/mtrview/actions/workflows/ci.yml/badge.svg)](https://github.com/tvallas/mtrview/actions/workflows/ci.yml)
[![Docker](https://github.com/tvallas/mtrview/actions/workflows/docker.yml/badge.svg)](https://github.com/tvallas/mtrview/actions/workflows/docker.yml)
[![Trivy](https://github.com/tvallas/mtrview/actions/workflows/trivy.yml/badge.svg)](https://github.com/tvallas/mtrview/actions/workflows/trivy.yml)
[![PyPI version](https://img.shields.io/pypi/v/mtrview.svg)](https://pypi.org/project/mtrview/)
[![Python 3.11-3.13](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://github.com/tvallas/mtrview/blob/master/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

mtrview is a small standalone web dashboard for retained JSON summaries published by
[mtr2mqtt](https://github.com/tvallas/mtr2mqtt). mtr2mqtt writes the measurement summaries to MQTT;
mtrview subscribes to those topics and turns the latest values into a simple human-friendly
dashboard.

The app subscribes to summary topics such as `summary/<receiver>`, keeps the latest summary per
receiver in memory, normalizes transmitter readings, and serves a dark auto-updating dashboard at
`http://localhost:8000/`.

## MQTT input

By default mtrview subscribes to:

```text
summary/#
```

Each retained message should be a JSON object with a `receiver`, an `updated_at` timestamp, and a
`transmitters` mapping. Transmitter metadata may be partial; missing `location`, `zone`, `quantity`,
`description`, `unit`, or `battery` fields are displayed with sensible placeholders instead of
failing.

## Configuration

Settings are read from environment variables:

| Variable | Default |
| --- | --- |
| `MTRVIEW_MQTT_HOST` | `localhost` |
| `MTRVIEW_MQTT_PORT` | `1883` |
| `MTRVIEW_MQTT_USERNAME` | unset |
| `MTRVIEW_MQTT_PASSWORD` | unset |
| `MTRVIEW_MQTT_TOPICS` | `summary/#` |
| `MTRVIEW_MQTT_MAX_PAYLOAD_BYTES` | `1048576` |
| `MTRVIEW_MQTT_MAX_RECEIVERS` | `128` |
| `MTRVIEW_MQTT_MAX_TRANSMITTERS_PER_SUMMARY` | `1000` |
| `MTRVIEW_MQTT_MAX_FIELD_LENGTH` | `512` |
| `MTRVIEW_HTTP_HOST` | `0.0.0.0` |
| `MTRVIEW_HTTP_PORT` | `8000` |
| `MTRVIEW_REFRESH_INTERVAL_SECONDS` | `20` |
| `MTRVIEW_DISPLAY_TIMEZONE` | `UTC` |
| `MTRVIEW_UPDATE_CHECK_ENABLED` | `true` |
| `MTRVIEW_UPDATE_CHECK_URL` | GitHub latest release API |
| `MTRVIEW_UPDATE_CHECK_INTERVAL_SECONDS` | `21600` |
| `MTRVIEW_FLOORPLAN_CONFIG` | `config/layout.yml` |
| `MTRVIEW_FLOORPLAN_SVG` | bundled sample floorplan SVG |
| `MTRVIEW_FLOORPLAN_UPLOAD_PATH` | `config/floorplan.svg` |
| `MTRVIEW_FLOORPLAN_EDIT_FLAG` | `config/edit.enabled` |
| `MTRVIEW_FLOORPLAN_EDIT_MODE` | unset |

See `.env.example` for a copyable starting point.

## Local run

```bash
uv sync --group dev
uv run mtrview
```

Then open `http://localhost:8000/`.

Useful endpoints:

- `GET /` - dashboard
- `GET /api/summary` - normalized JSON for all receivers and transmitters
- `GET /health` - health status

## Docker

```bash
docker build -t mtrview .
docker run --rm -p 8000:8000 \
  -e MTRVIEW_MQTT_HOST=host.docker.internal \
  -e MTRVIEW_MQTT_TOPICS=summary/# \
  mtrview
```

Published Docker images support `linux/amd64`, `linux/arm64`, `linux/arm/v7`, and
`linux/arm/v6` for Pi Zero-class 32-bit ARM devices. The image intentionally uses Uvicorn without
optional native performance extras so old Raspberry Pi targets can install dependencies without a
compiler and the runtime image stays small.

## Dashboard

The UI is server-rendered first, with a small vanilla JavaScript refresh loop that fetches
`/api/summary`. It includes summary counts, MQTT connection state, search, status/zone/receiver
filters, card, compact table, and floorplan views, and a priority section for non-online readings.
Transmitter battery state is shown in the card, table, and detail views when present. Battery
labels are derived from voltage: `full` at 3.1 V or higher, `good` at 2.9-3.0 V, `medium` at
2.7-2.8 V, `low` at 2.6 V, and `critical` at 2.5 V or lower.

The floorplan view uses an SVG layout plus a YAML mapping of areas to sensor identities such as
`Room A::Ambient air::Temperature`. mtrview falls back to a bundled generic sample layout when
`MTRVIEW_FLOORPLAN_CONFIG` does not exist. Upload your own SVG from `/floorplan/edit`, then edit
polygons and threshold profiles; saved changes are written to the configured `layout.yml`. The
bundled sample includes a `no_color` preset for seasonal or otherwise variable areas where threshold
coloring is not useful, and the editor can add new presets by copying the currently selected preset.
Editing is locked by default; enable it with `MTRVIEW_FLOORPLAN_EDIT_MODE=always`, or create the flag
file configured by `MTRVIEW_FLOORPLAN_EDIT_FLAG` for temporary write access. Uploaded SVG layouts are
stored at `MTRVIEW_FLOORPLAN_UPLOAD_PATH` and override the bundled sample SVG until reset from the
editor. Local floorplan config, uploads, and edit flag files under `config/` are ignored by git.

MQTT summaries that exceed the configured payload, receiver, transmitter, or string-field limits
are ignored and logged so malformed or oversized retained messages cannot grow dashboard memory and
CPU use without bound.

The dashboard footer shows the running mtrview version. By default the browser asks
`/api/version` for update status, and the server checks the latest GitHub release with a six-hour
cache. Set `MTRVIEW_UPDATE_CHECK_ENABLED=false` to disable outbound update checks, or set
`MTRVIEW_UPDATE_CHECK_URL` to another compatible JSON endpoint that exposes `tag_name` or `name`.

## Development

```bash
make install
make verify
```

Individual checks:

```bash
uv run pytest
uv run ruff check .
```

## Releases

Releases are managed by GitHub Actions using Conventional Commits and semantic-release. Merges to
`master` can create GitHub releases, publish the Python package to PyPI, and publish multi-arch
Docker images to Docker Hub as `tvallas/mtrview`.
