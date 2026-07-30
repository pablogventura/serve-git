"""Helpers for creating temporary Git repositories in tests."""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def init_worktree(path: Path, *, commit: bool = True) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    run_git(["init"], path)
    run_git(["config", "user.email", "test@example.com"], path)
    run_git(["config", "user.name", "Test User"], path)
    if commit:
        (path / "README.md").write_text("hello\n", encoding="utf-8")
        run_git(["add", "README.md"], path)
        run_git(["commit", "-m", "initial"], path)
    return path


def init_bare(path: Path, source: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    run_git(["clone", "--bare", str(source), str(path)], cwd=source.parent)
    return path
