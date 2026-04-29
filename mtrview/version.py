from __future__ import annotations

import json
import re
import tomllib
import urllib.request
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from time import monotonic, time
from typing import Any

DEFAULT_UPDATE_CHECK_URL = "https://api.github.com/repos/tvallas/mtrview/releases/latest"


@dataclass(frozen=True)
class VersionCheckResult:
    current_version: str
    latest_version: str | None
    update_available: bool | None
    checked_at: float | None
    error: str | None = None
    release_url: str | None = None


class VersionChecker:
    def __init__(
        self,
        *,
        current_version: str,
        enabled: bool,
        url: str,
        interval_seconds: int,
        timeout_seconds: float = 3.0,
    ) -> None:
        self.current_version = current_version
        self.enabled = enabled
        self.url = url
        self.interval_seconds = interval_seconds
        self.timeout_seconds = timeout_seconds
        self._cached: VersionCheckResult | None = None
        self._cached_at = 0.0

    def status(self) -> VersionCheckResult:
        if not self.enabled:
            return VersionCheckResult(
                current_version=self.current_version,
                latest_version=None,
                update_available=None,
                checked_at=None,
                error="disabled",
            )

        now = monotonic()
        if self._cached is not None and now - self._cached_at < self.interval_seconds:
            return self._cached

        self._cached = self._fetch()
        self._cached_at = now
        return self._cached

    def _fetch(self) -> VersionCheckResult:
        try:
            request = urllib.request.Request(
                self.url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": f"mtrview/{self.current_version}",
                },
            )
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            return VersionCheckResult(
                current_version=self.current_version,
                latest_version=None,
                update_available=None,
                checked_at=time(),
                error=str(error),
            )

        latest_version = _version_from_payload(payload)
        release_url = payload.get("html_url") if isinstance(payload, dict) else None
        update_available = (
            _version_key(latest_version) > _version_key(self.current_version)
            if latest_version
            else None
        )
        return VersionCheckResult(
            current_version=self.current_version,
            latest_version=latest_version,
            update_available=update_available,
            checked_at=time(),
            release_url=release_url,
        )


def get_current_version() -> str:
    try:
        return metadata.version("mtrview")
    except metadata.PackageNotFoundError:
        return _version_from_pyproject()


def _version_from_pyproject() -> str:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    try:
        return str(tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"])
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "0.0.0"


def _version_from_payload(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("tag_name") or payload.get("name")
    return str(value).lstrip("vV") if value else None


def _version_key(version: str | None) -> tuple[int, ...]:
    if not version:
        return ()
    return tuple(int(part) for part in re.findall(r"\d+", version))
