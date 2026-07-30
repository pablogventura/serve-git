"""Tests for repository path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from serve_git.repo import RepoError, export_name_for, resolve_repo
from tests.helpers import init_bare, init_worktree


def test_export_name_for_worktree() -> None:
    assert export_name_for(Path("/tmp/my-project")) == "my-project.git"


def test_export_name_for_already_git_suffix() -> None:
    assert export_name_for(Path("/tmp/my-project.git")) == "my-project.git"


def test_resolve_worktree(tmp_path: Path) -> None:
    repo = init_worktree(tmp_path / "demo")
    resolved = resolve_repo(repo)
    assert resolved.path == repo.resolve()
    assert resolved.git_dir == (repo / ".git").resolve()
    assert resolved.export_name == "demo.git"
    assert resolved.is_bare is False


def test_resolve_bare(tmp_path: Path) -> None:
    worktree = init_worktree(tmp_path / "src")
    bare = init_bare(tmp_path / "src.git", worktree)
    resolved = resolve_repo(bare)
    assert resolved.is_bare is True
    assert resolved.export_name == "src.git"
    assert resolved.git_dir == bare.resolve()


def test_resolve_missing_path(tmp_path: Path) -> None:
    with pytest.raises(RepoError, match="does not exist"):
        resolve_repo(tmp_path / "missing")


def test_resolve_non_git(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(RepoError, match="Not a Git repository"):
        resolve_repo(plain)
