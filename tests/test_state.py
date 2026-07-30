"""Tests for serve-git session state."""

from __future__ import annotations

import os
from pathlib import Path

from serve_git.state import (
    ServeState,
    clear_state,
    is_pid_alive,
    is_session_active,
    load_state,
    save_state,
)


def _sample_state(**overrides: object) -> ServeState:
    data = {
        "http_pid": os.getpid(),
        "ngrok_pid": 0,
        "port": 1234,
        "public_url": "https://example.ngrok-free.app",
        "repo_path": "/tmp/repo",
        "repo_name": "repo.git",
        "clone_url": "https://example.ngrok-free.app/repo.git",
    }
    data.update(overrides)
    return ServeState(**data)  # type: ignore[arg-type]


def test_save_and_load_state(tmp_path: Path) -> None:
    state = _sample_state()
    save_state(state, tmp_path)
    loaded = load_state(tmp_path)
    assert loaded is not None
    assert loaded.http_pid == state.http_pid
    assert loaded.clone_url == state.clone_url


def test_load_missing_state(tmp_path: Path) -> None:
    assert load_state(tmp_path) is None


def test_clear_state(tmp_path: Path) -> None:
    save_state(_sample_state(), tmp_path)
    clear_state(tmp_path)
    assert load_state(tmp_path) is None


def test_is_pid_alive_current_process() -> None:
    assert is_pid_alive(os.getpid()) is True


def test_is_pid_alive_bogus() -> None:
    assert is_pid_alive(999_999_999) is False


def test_is_session_active_with_live_http(tmp_path: Path) -> None:
    state = _sample_state(http_pid=os.getpid(), ngrok_pid=0)
    assert is_session_active(state) is True


def test_is_session_active_none() -> None:
    assert is_session_active(None) is False


def test_is_session_active_dead_pids() -> None:
    state = _sample_state(http_pid=999_999_999, ngrok_pid=999_999_998)
    assert is_session_active(state) is False
