"""Read-only Git smart HTTP server backed by git-http-backend."""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


def find_git_http_backend() -> str:
    """Locate the git-http-backend executable."""
    candidates = [
        shutil.which("git-http-backend"),
        "/usr/lib/git-core/git-http-backend",
        "/usr/libexec/git-core/git-http-backend",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise FileNotFoundError(
        "git-http-backend not found; install Git with http-backend support"
    )


def find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def prepare_project_root(git_dir: Path, export_name: str) -> Path:
    """
    Build a temporary GIT_PROJECT_ROOT containing a symlink to ``git_dir``.

    Git clients then clone ``http://host:port/{export_name}``.
    """
    root = Path(tempfile.mkdtemp(prefix="serve-git-"))
    link_path = root / export_name
    link_path.symlink_to(git_dir.resolve(), target_is_directory=True)
    return root


class GitHTTPRequestHandler(BaseHTTPRequestHandler):
    """CGI-style bridge to git-http-backend (upload-pack only)."""

    backend_path: str = ""
    project_root: str = ""

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def do_GET(self) -> None:  # noqa: N802
        self._handle()

    def do_POST(self) -> None:  # noqa: N802
        self._handle()

    def _handle(self) -> None:
        parsed = urlparse(self.path)
        path_info = parsed.path
        query = parsed.query

        # Reject receive-pack explicitly (read-only serve).
        if "git-receive-pack" in path_info or "service=git-receive-pack" in query:
            self.send_error(403, "Push is disabled (read-only serve)")
            return

        content_length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(content_length) if content_length > 0 else b""

        env = os.environ.copy()
        env.update(
            {
                "GIT_PROJECT_ROOT": self.project_root,
                "GIT_HTTP_EXPORT_ALL": "1",
                "PATH_INFO": path_info,
                "QUERY_STRING": query,
                "REQUEST_METHOD": self.command,
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                "CONTENT_LENGTH": str(len(body)),
                "SERVER_PROTOCOL": self.request_version,
                "REMOTE_ADDR": self.client_address[0],
                "GATEWAY_INTERFACE": "CGI/1.1",
                "SCRIPT_NAME": "",
            }
        )
        # Ensure anonymous push stays disabled even if repo config enables it.
        env["GIT_HTTP_RECEIVE_PACK"] = "false"

        try:
            completed = subprocess.run(
                [self.backend_path],
                input=body,
                capture_output=True,
                env=env,
                check=False,
            )
        except OSError as exc:
            self.send_error(500, f"Failed to run git-http-backend: {exc}")
            return

        if completed.returncode != 0 and not completed.stdout:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            self.send_error(500, detail or "git-http-backend failed")
            return

        self._write_cgi_response(completed.stdout)

    def _write_cgi_response(self, raw: bytes) -> None:
        header_blob, _, body = raw.partition(b"\r\n\r\n")
        if header_blob == raw:
            header_blob, _, body = raw.partition(b"\n\n")

        status_code = 200
        headers: list[tuple[str, str]] = []
        for line in header_blob.split(b"\n"):
            line = line.rstrip(b"\r")
            if not line:
                continue
            if b":" not in line:
                continue
            key, value = line.split(b":", 1)
            key_s = key.decode("latin-1")
            value_s = value.decode("latin-1").strip()
            if key_s.lower() == "status":
                try:
                    status_code = int(value_s.split(" ", 1)[0])
                except ValueError:
                    status_code = 500
            else:
                headers.append((key_s, value_s))

        self.send_response(status_code)
        for key_s, value_s in headers:
            self.send_header(key_s, value_s)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)


def make_handler(backend_path: str, project_root: Path) -> type[GitHTTPRequestHandler]:
    class BoundHandler(GitHTTPRequestHandler):
        pass

    BoundHandler.backend_path = backend_path
    BoundHandler.project_root = str(project_root)
    return BoundHandler


def serve_forever(
    host: str,
    port: int,
    project_root: Path,
    backend_path: str | None = None,
) -> ThreadingHTTPServer:
    backend = backend_path or find_git_http_backend()
    handler = make_handler(backend, project_root)
    httpd = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def main(argv: list[str] | None = None) -> int:
    """CLI entry used by the background HTTP worker process."""
    parser = argparse.ArgumentParser(description="serve-git HTTP worker")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--git-dir", required=True)
    parser.add_argument("--export-name", required=True)
    args = parser.parse_args(argv)

    git_dir = Path(args.git_dir)
    project_root = prepare_project_root(git_dir, args.export_name)
    backend = find_git_http_backend()
    handler = make_handler(backend, project_root)
    httpd = ThreadingHTTPServer((args.host, args.port), handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        shutil.rmtree(project_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
