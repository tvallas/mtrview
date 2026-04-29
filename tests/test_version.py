from __future__ import annotations

import json
import urllib.request
from typing import Any

from mtrview.version import VersionChecker


def test_version_checker_reports_available_update(monkeypatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen({"tag_name": "v0.4.0"}))
    checker = VersionChecker(
        current_version="0.3.3",
        enabled=True,
        url="https://example.test/latest",
        interval_seconds=60,
    )

    status = checker.status()

    assert status.latest_version == "0.4.0"
    assert status.update_available is True
    assert status.error is None


def test_version_checker_caches_result(monkeypatch) -> None:
    calls = []

    def urlopen(request, timeout):
        calls.append((request, timeout))
        return FakeResponse({"tag_name": "v0.3.3"})

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    checker = VersionChecker(
        current_version="0.3.3",
        enabled=True,
        url="https://example.test/latest",
        interval_seconds=60,
    )

    assert checker.status().update_available is False
    assert checker.status().update_available is False
    assert len(calls) == 1


def fake_urlopen(payload: dict[str, Any]):
    def urlopen(request, timeout):
        return FakeResponse(payload)

    return urlopen


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")
