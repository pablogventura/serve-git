"""Resolve Git repository paths and export names."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class RepoError(ValueError):
    """Raised when a path is not a usable Git repository."""


@dataclass(frozen=True)
class ResolvedRepo:
    """A local Git repository ready to be served."""

    path: Path
    git_dir: Path
    export_name: str
    is_bare: bool


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "git command failed").strip()
        raise RepoError(message)
    return result.stdout.strip()


def export_name_for(path: Path) -> str:
    """Return the URL path segment used when serving this repository."""
    name = path.name
    if name.endswith(".git"):
        return name
    return f"{name}.git"


def resolve_repo(path: Path | str) -> ResolvedRepo:
    """
    Resolve ``path`` to a worktree or bare repository.

    Raises ``RepoError`` if the path is not a Git repository.
    """
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise RepoError(f"Path does not exist: {resolved}")

    probe_cwd = resolved if resolved.is_dir() else resolved.parent
    try:
        git_dir_raw = _run_git(["rev-parse", "--git-dir"], probe_cwd)
    except RepoError as exc:
        raise RepoError(f"Not a Git repository: {resolved}") from exc

    git_dir = Path(git_dir_raw)
    if not git_dir.is_absolute():
        git_dir = (probe_cwd / git_dir).resolve()
    else:
        git_dir = git_dir.resolve()

    is_bare = _run_git(["rev-parse", "--is-bare-repository"], probe_cwd) == "true"
    if is_bare:
        repo_path = git_dir
    else:
        toplevel = _run_git(["rev-parse", "--show-toplevel"], probe_cwd)
        repo_path = Path(toplevel).resolve()

    return ResolvedRepo(
        path=repo_path,
        git_dir=git_dir,
        export_name=export_name_for(repo_path),
        is_bare=is_bare,
    )
