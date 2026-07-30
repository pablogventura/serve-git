"""Tests for command formatting helpers."""

from __future__ import annotations

from serve_git import NGROK_SKIP_HEADER, REMOTE_NAME
from serve_git.commands import (
    clone_url,
    format_clone_command,
    format_fetch_command,
    format_peer_instructions,
    format_remote_add_command,
)


def test_clone_url_joins_base_and_name() -> None:
    assert (
        clone_url("https://abc.ngrok-free.app", "demo.git")
        == "https://abc.ngrok-free.app/demo.git"
    )


def test_clone_url_strips_trailing_slash() -> None:
    assert (
        clone_url("https://abc.ngrok-free.app/", "demo.git")
        == "https://abc.ngrok-free.app/demo.git"
    )


def test_format_clone_command_includes_ngrok_header() -> None:
    url = "https://abc.ngrok-free.app/demo.git"
    command = format_clone_command(url)
    assert NGROK_SKIP_HEADER in command
    assert command.endswith(f"clone {url}")


def test_format_remote_add_command() -> None:
    url = "https://abc.ngrok-free.app/demo.git"
    assert format_remote_add_command(url) == f"git remote add {REMOTE_NAME} {url}"


def test_format_fetch_command() -> None:
    command = format_fetch_command()
    assert NGROK_SKIP_HEADER in command
    assert command.endswith(f"fetch {REMOTE_NAME}")


def test_format_peer_instructions_contains_both_flows() -> None:
    url = "https://abc.ngrok-free.app/demo.git"
    text = format_peer_instructions(url)
    assert format_clone_command(url) in text
    assert format_remote_add_command(url) in text
    assert "stop-serve-git" in text
