"""Start ngrok and discover the public HTTPS URL."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from typing import Callable


DEFAULT_API_URL = "http://127.0.0.1:4040/api/tunnels"


class NgrokError(RuntimeError):
    """Raised when ngrok cannot be started or the public URL is unavailable."""


def require_ngrok() -> str:
    path = shutil.which("ngrok")
    if not path:
        raise NgrokError(
            "ngrok not found on PATH; install ngrok and authenticate it first"
        )
    return path


def start_ngrok(
    port: int,
    *,
    ngrok_path: str | None = None,
    log_path: str | None = None,
) -> subprocess.Popen[bytes]:
    binary = ngrok_path or require_ngrok()
    command = [binary, "http", str(port), "--log=stdout"]
    stdout = subprocess.DEVNULL
    stderr = subprocess.DEVNULL
    if log_path:
        log_file = open(log_path, "ab")  # noqa: SIM115
        stdout = log_file
        stderr = subprocess.STDOUT
    return subprocess.Popen(
        command,
        stdout=stdout,
        stderr=stderr,
        start_new_session=True,
    )


def fetch_public_url(
    api_url: str = DEFAULT_API_URL,
    *,
    opener: Callable[[str], object] | None = None,
) -> str | None:
    """
    Return the first public https tunnel URL from the local ngrok API, if any.
    """

    def _default_open(url: str) -> object:
        return urllib.request.urlopen(url, timeout=2)

    open_url = opener or _default_open
    try:
        with open_url(api_url) as response:  # type: ignore[attr-defined]
            raw = response.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return None

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return None

    tunnels = payload.get("tunnels") if isinstance(payload, dict) else None
    if not isinstance(tunnels, list):
        return None

    https_url: str | None = None
    for tunnel in tunnels:
        if not isinstance(tunnel, dict):
            continue
        public_url = tunnel.get("public_url")
        if not isinstance(public_url, str):
            continue
        if public_url.startswith("https://"):
            return public_url
        if public_url.startswith("http://") and https_url is None:
            https_url = public_url
    return https_url


def wait_for_public_url(
    *,
    api_url: str = DEFAULT_API_URL,
    timeout_seconds: float = 30.0,
    poll_interval_seconds: float = 0.25,
    opener: Callable[[str], object] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> str:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        url = fetch_public_url(api_url, opener=opener)
        if url:
            return url
        sleeper(poll_interval_seconds)
    raise NgrokError(
        f"Timed out waiting for ngrok public URL from {api_url}"
    )
