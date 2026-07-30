"""CLI entry points for serve-git and stop-serve-git."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from serve_git.commands import clone_url, format_peer_instructions
from serve_git.ngrok import NgrokError, require_ngrok, start_ngrok, wait_for_public_url
from serve_git.repo import RepoError, resolve_repo
from serve_git.server import find_free_port
from serve_git.state import (
    ServeState,
    clear_state,
    is_pid_alive,
    is_session_active,
    load_state,
    save_state,
    terminate_pid,
    wait_until_dead,
)


def require_git() -> str:
    path = shutil.which("git")
    if not path:
        raise SystemExit("git not found on PATH")
    return path


def start_http_worker(
    *,
    host: str,
    port: int,
    git_dir: Path,
    export_name: str,
) -> subprocess.Popen[bytes]:
    command = [
        sys.executable,
        "-m",
        "serve_git.server",
        "--host",
        host,
        "--port",
        str(port),
        "--git-dir",
        str(git_dir),
        "--export-name",
        export_name,
    ]
    return subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def wait_for_port(host: str, port: int, timeout_seconds: float = 10.0) -> None:
    import socket

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            try:
                sock.connect((host, port))
                return
            except OSError:
                time.sleep(0.1)
    raise RuntimeError(f"HTTP server did not open {host}:{port} in time")


def cmd_serve(
    repo_path: str,
    *,
    state_dir: Path | None = None,
    host: str = "127.0.0.1",
    skip_ngrok: bool = False,
    public_base_url: str | None = None,
    ngrok_api_url: str = "http://127.0.0.1:4040/api/tunnels",
) -> int:
    require_git()
    if not skip_ngrok:
        try:
            require_ngrok()
        except NgrokError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    existing = load_state(state_dir)
    if is_session_active(existing):
        print(
            "A serve-git session is already running. "
            "Run stop-serve-git first.",
            file=sys.stderr,
        )
        return 1

    if existing is not None:
        clear_state(state_dir)

    try:
        repo = resolve_repo(repo_path)
    except RepoError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    port = find_free_port(host)
    http_proc = start_http_worker(
        host=host,
        port=port,
        git_dir=repo.git_dir,
        export_name=repo.export_name,
    )

    try:
        wait_for_port(host, port)
    except RuntimeError as exc:
        terminate_pid(http_proc.pid)
        print(str(exc), file=sys.stderr)
        return 1

    ngrok_pid = 0
    if skip_ngrok:
        if not public_base_url:
            public_base_url = f"http://{host}:{port}"
        public_url = public_base_url.rstrip("/")
    else:
        try:
            ngrok_proc = start_ngrok(port)
            ngrok_pid = ngrok_proc.pid
            public_url = wait_for_public_url(api_url=ngrok_api_url)
        except NgrokError as exc:
            terminate_pid(http_proc.pid)
            if ngrok_pid:
                terminate_pid(ngrok_pid)
            print(str(exc), file=sys.stderr)
            return 1

    url = clone_url(public_url, repo.export_name)
    state = ServeState(
        http_pid=http_proc.pid,
        ngrok_pid=ngrok_pid,
        port=port,
        public_url=public_url,
        repo_path=str(repo.path),
        repo_name=repo.export_name,
        clone_url=url,
    )
    save_state(state, state_dir)
    print(format_peer_instructions(url), end="")
    return 0


def cmd_stop(*, state_dir: Path | None = None) -> int:
    state = load_state(state_dir)
    if state is None:
        print("No active serve-git session.")
        return 0

    stopped_any = False
    for pid in (state.ngrok_pid, state.http_pid):
        if pid and is_pid_alive(pid):
            terminate_pid(pid)
            stopped_any = True

    for pid in (state.ngrok_pid, state.http_pid):
        if pid and is_pid_alive(pid):
            wait_until_dead(pid, timeout_seconds=1.0)
        if pid and is_pid_alive(pid):
            terminate_pid(pid, timeout_signal=9)
            wait_until_dead(pid, timeout_seconds=1.0)
            stopped_any = True

    clear_state(state_dir)
    if stopped_any:
        print("Stopped serve-git session.")
    else:
        print("Cleared stale serve-git state (processes were already gone).")
    return 0


def build_serve_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="serve-git",
        description=(
            "Expose a local Git repository over smart HTTP behind ngrok "
            "and print clone / remote-add commands for a peer."
        ),
    )
    parser.add_argument(
        "repo",
        help="Path to a local Git worktree or bare repository",
    )
    return parser


def build_stop_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="stop-serve-git",
        description="Stop the active serve-git HTTP server and ngrok tunnel.",
    )


def main_serve(argv: list[str] | None = None) -> int:
    parser = build_serve_parser()
    args = parser.parse_args(argv)
    return cmd_serve(args.repo)


def main_stop(argv: list[str] | None = None) -> int:
    parser = build_stop_parser()
    parser.parse_args(argv)
    return cmd_stop()


if __name__ == "__main__":
    raise SystemExit(main_serve())
