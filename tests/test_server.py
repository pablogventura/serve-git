"""Integration tests for the smart HTTP server (no ngrok)."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from serve_git.repo import resolve_repo
from serve_git.server import (
    find_free_port,
    find_git_http_backend,
    prepare_project_root,
    serve_forever,
)
from tests.helpers import init_worktree, run_git


@pytest.fixture
def http_server(tmp_path: Path):
    repo_path = init_worktree(tmp_path / "project")
    resolved = resolve_repo(repo_path)
    project_root = prepare_project_root(resolved.git_dir, resolved.export_name)
    port = find_free_port()
    backend = find_git_http_backend()
    httpd = serve_forever("127.0.0.1", port, project_root, backend_path=backend)
    # Give the thread a moment to bind.
    time.sleep(0.1)
    try:
        yield {
            "port": port,
            "export_name": resolved.export_name,
            "repo_path": repo_path,
            "project_root": project_root,
            "httpd": httpd,
        }
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_find_git_http_backend() -> None:
    path = find_git_http_backend()
    assert Path(path).is_file()


def test_clone_over_localhost(http_server: dict, tmp_path: Path) -> None:
    port = http_server["port"]
    export_name = http_server["export_name"]
    dest = tmp_path / "clone"
    url = f"http://127.0.0.1:{port}/{export_name}"
    result = subprocess.run(
        ["git", "clone", url, str(dest)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (dest / "README.md").read_text(encoding="utf-8") == "hello\n"


def test_push_is_rejected(http_server: dict, tmp_path: Path) -> None:
    port = http_server["port"]
    export_name = http_server["export_name"]
    dest = tmp_path / "clone"
    url = f"http://127.0.0.1:{port}/{export_name}"
    subprocess.run(
        ["git", "clone", url, str(dest)],
        check=True,
        capture_output=True,
        text=True,
    )
    run_git(["config", "user.email", "test@example.com"], dest)
    run_git(["config", "user.name", "Test User"], dest)
    (dest / "extra.txt").write_text("nope\n", encoding="utf-8")
    run_git(["add", "extra.txt"], dest)
    run_git(["commit", "-m", "extra"], dest)
    push = subprocess.run(
        ["git", "push", "origin", "HEAD"],
        cwd=dest,
        capture_output=True,
        text=True,
        check=False,
    )
    assert push.returncode != 0
