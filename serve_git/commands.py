"""Format copy-pasteable Git commands for peers."""

from __future__ import annotations

from serve_git import NGROK_SKIP_HEADER, REMOTE_NAME


def clone_url(public_base: str, export_name: str) -> str:
    return f"{public_base.rstrip('/')}/{export_name}"


def format_clone_command(url: str) -> str:
    return (
        f'git -c http.extraHeader="{NGROK_SKIP_HEADER}" clone {url}'
    )


def format_remote_add_command(url: str, remote_name: str = REMOTE_NAME) -> str:
    return f"git remote add {remote_name} {url}"


def format_fetch_command(remote_name: str = REMOTE_NAME) -> str:
    return (
        f'git -c http.extraHeader="{NGROK_SKIP_HEADER}" fetch {remote_name}'
    )


def format_peer_instructions(url: str) -> str:
    lines = [
        "Share these commands with your peer:",
        "",
        "# Clone into a new directory",
        format_clone_command(url),
        "",
        "# Or add as a remote on an existing clone",
        format_remote_add_command(url),
        format_fetch_command(),
        "",
        "When finished on your machine, run: stop-serve-git",
    ]
    return "\n".join(lines) + "\n"
