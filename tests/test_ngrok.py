"""Tests for ngrok URL discovery helpers."""

from __future__ import annotations

import json
from typing import Any

import pytest

from serve_git.ngrok import NgrokError, fetch_public_url, require_ngrok, wait_for_public_url


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_fetch_public_url_prefers_https() -> None:
    payload = {
        "tunnels": [
            {"public_url": "http://abc.ngrok-free.app"},
            {"public_url": "https://abc.ngrok-free.app"},
        ]
    }

    def opener(_url: str) -> _FakeResponse:
        return _FakeResponse(payload)

    assert fetch_public_url(opener=opener) == "https://abc.ngrok-free.app"


def test_fetch_public_url_empty() -> None:
    def opener(_url: str) -> _FakeResponse:
        return _FakeResponse({"tunnels": []})

    assert fetch_public_url(opener=opener) is None


def test_wait_for_public_url_success() -> None:
    calls = {"n": 0}

    def opener(_url: str) -> _FakeResponse:
        calls["n"] += 1
        if calls["n"] < 3:
            return _FakeResponse({"tunnels": []})
        return _FakeResponse(
            {"tunnels": [{"public_url": "https://ready.ngrok-free.app"}]}
        )

    sleeps: list[float] = []

    url = wait_for_public_url(
        opener=opener,
        sleeper=sleeps.append,
        timeout_seconds=5,
        poll_interval_seconds=0.01,
    )
    assert url == "https://ready.ngrok-free.app"
    assert sleeps


def test_wait_for_public_url_timeout() -> None:
    def opener(_url: str) -> _FakeResponse:
        return _FakeResponse({"tunnels": []})

    with pytest.raises(NgrokError, match="Timed out"):
        wait_for_public_url(
            opener=opener,
            sleeper=lambda _s: None,
            timeout_seconds=0.01,
            poll_interval_seconds=0.01,
        )


def test_require_ngrok_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("serve_git.ngrok.shutil.which", lambda _name: None)
    with pytest.raises(NgrokError, match="ngrok not found"):
        require_ngrok()
