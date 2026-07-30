"""Tests for serve-git / stop-serve-git CLI orchestration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from serve_git.cli import cmd_serve, cmd_stop
from serve_git.state import ServeState, is_pid_alive, load_state, save_state
from tests.helpers import init_worktree


def test_serve_without_ngrok_prints_commands(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = init_worktree(tmp_path / "demo")
    state_dir = tmp_path / "state"
    code = cmd_serve(
        str(repo),
        state_dir=state_dir,
        skip_ngrok=True,
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "git -c http.extraHeader=" in out
    assert "clone http://127.0.0.1:" in out
    assert "git remote add serve-git http://127.0.0.1:" in out
    assert "stop-serve-git" in out

    state = load_state(state_dir)
    assert state is not None
    assert is_pid_alive(state.http_pid)

    stop_code = cmd_stop(state_dir=state_dir)
    assert stop_code == 0
    assert load_state(state_dir) is None
    assert not is_pid_alive(state.http_pid)


def test_serve_rejects_when_already_running(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = init_worktree(tmp_path / "demo")
    state_dir = tmp_path / "state"
    save_state(
        ServeState(
            http_pid=os.getpid(),
            ngrok_pid=0,
            port=1,
            public_url="https://example.invalid",
            repo_path=str(repo),
            repo_name="demo.git",
            clone_url="https://example.invalid/demo.git",
        ),
        state_dir,
    )
    code = cmd_serve(str(repo), state_dir=state_dir, skip_ngrok=True)
    assert code == 1
    err = capsys.readouterr().err
    assert "already running" in err


def test_stop_with_no_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cmd_stop(state_dir=tmp_path / "empty-state")
    assert code == 0
    assert "No active" in capsys.readouterr().out


def test_serve_invalid_repo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cmd_serve(str(tmp_path / "nope"), state_dir=tmp_path / "state", skip_ngrok=True)
    assert code == 1
    assert "does not exist" in capsys.readouterr().err


def test_serve_missing_ngrok(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = init_worktree(tmp_path / "demo")
    from serve_git.ngrok import NgrokError

    def boom() -> str:
        raise NgrokError("ngrok not found on PATH")

    monkeypatch.setattr("serve_git.cli.require_ngrok", boom)
    code = cmd_serve(str(repo), state_dir=tmp_path / "state", skip_ngrok=False)
    assert code == 1
    assert "ngrok not found" in capsys.readouterr().err


def test_serve_missing_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("serve_git.cli.shutil.which", lambda _name: None)
    with pytest.raises(SystemExit, match="git not found"):
        cmd_serve(str(tmp_path), state_dir=tmp_path / "state", skip_ngrok=True)
