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
| `MTRVIEW_HTTP_HOST` | `0.0.0.0` |
| `MTRVIEW_HTTP_PORT` | `8000` |
| `MTRVIEW_REFRESH_INTERVAL_SECONDS` | `20` |
| `MTRVIEW_DISPLAY_TIMEZONE` | `UTC` |

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
filters, card and compact table views, and a priority section for non-online readings.
Transmitter battery state is shown in the card, table, and detail views when present. Battery
labels are derived from voltage: `full` at 3.1 V or higher, `good` at 2.9-3.0 V, `medium` at
2.7-2.8 V, `low` at 2.6 V, and `critical` at 2.5 V or lower.

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
