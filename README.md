<p align="center">
  <img src="mtrview/static/mtrview-logo.png" alt="mtrview" width="360">
</p>

# mtrview

mtrview is a small standalone web dashboard for retained JSON summaries published by
[mtr2mqtt](https://github.com/tvallas/mtr2mqtt). It is a sibling project, not a change inside
mtr2mqtt: MQTT remains the backend data source, and mtrview focuses only on a human-friendly latest
state view.

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
`description`, or `unit` fields are displayed with sensible placeholders instead of failing.

## Configuration

Settings are read from environment variables:

| Variable | Default |
| --- | --- |
| `MTRVIEW_MQTT_HOST` | `localhost` |
| `MTRVIEW_MQTT_PORT` | `1883` |
| `MTRVIEW_MQTT_USERNAME` | unset |
| `MTRVIEW_MQTT_PASSWORD` | unset |
| `MTRVIEW_MQTT_TOPICS` | `summary/#` |
| `MTRVIEW_STALE_AFTER_SECONDS` | `3600` |
| `MTRVIEW_CRITICAL_STALE_AFTER_SECONDS` | `21600` |
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

## Dashboard

The UI is server-rendered first, with a small vanilla JavaScript refresh loop that fetches
`/api/summary`. It includes summary counts, MQTT connection state, search, status/zone/receiver
filters, card and compact table views, and a priority section for stale or offline readings.

## Development

```bash
uv run pytest
uv run ruff check .
```
