"""Persist and inspect the active serve-git session."""

from __future__ import annotations

import json
import os
import signal
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_STATE_DIR = Path.home() / ".local" / "state" / "serve-git"
STATE_FILENAME = "state.json"


@dataclass
class ServeState:
    """On-disk description of a running serve session."""

    http_pid: int
    ngrok_pid: int
    port: int
    public_url: str
    repo_path: str
    repo_name: str
    clone_url: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServeState:
        return cls(
            http_pid=int(data["http_pid"]),
            ngrok_pid=int(data["ngrok_pid"]),
            port=int(data["port"]),
            public_url=str(data["public_url"]),
            repo_path=str(data["repo_path"]),
            repo_name=str(data["repo_name"]),
            clone_url=str(data["clone_url"]),
        )


def state_file(state_dir: Path | None = None) -> Path:
    return (state_dir or DEFAULT_STATE_DIR) / STATE_FILENAME


def load_state(state_dir: Path | None = None) -> ServeState | None:
    path = state_file(state_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return ServeState.from_dict(data)
    except (KeyError, TypeError, ValueError):
        return None


def save_state(state: ServeState, state_dir: Path | None = None) -> Path:
    directory = state_dir or DEFAULT_STATE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / STATE_FILENAME
    path.write_text(json.dumps(asdict(state), indent=2) + "\n", encoding="utf-8")
    return path


def clear_state(state_dir: Path | None = None) -> None:
    path = state_file(state_dir)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    # If we are the parent of an already-exited child, reap the zombie.
    try:
        waited_pid, _status = os.waitpid(pid, os.WNOHANG)
        if waited_pid == pid:
            return False
    except (ChildProcessError, OSError):
        pass

    # Linux: treat zombies as not alive for session checks.
    status_path = Path(f"/proc/{pid}/status")
    try:
        for line in status_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("State:"):
                state = line.split()[1]
                return state != "Z"
    except FileNotFoundError:
        return False
    except OSError:
        pass

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def is_session_active(state: ServeState | None) -> bool:
    if state is None:
        return False
    return is_pid_alive(state.http_pid) or is_pid_alive(state.ngrok_pid)


def terminate_pid(pid: int, timeout_signal: int = signal.SIGTERM) -> None:
    if not is_pid_alive(pid):
        return
    try:
        os.killpg(pid, timeout_signal)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            os.kill(pid, timeout_signal)
        except ProcessLookupError:
            return
        except PermissionError:
            return


def wait_until_dead(pid: int, timeout_seconds: float = 2.0) -> bool:
    """Return True if ``pid`` is no longer alive within ``timeout_seconds``."""
    import time

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not is_pid_alive(pid):
            return True
        time.sleep(0.05)
    return not is_pid_alive(pid)
