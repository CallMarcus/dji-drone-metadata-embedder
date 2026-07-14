"""Serve a generated map folder over local HTTP.

Browsers refuse WebGL pixel access to images on ``file://`` pages, so the
photomap 360-degree viewer only works when the map is served over HTTP.
This module is the loopback-only server behind ``dji-embed photomap --serve``.
"""

from __future__ import annotations

import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import click


class _QuietHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler without per-request stderr logging."""

    def log_message(self, format: str, *args: object) -> None:
        pass


def _make_server(directory: Path, *, log_requests: bool = False) -> ThreadingHTTPServer:
    """Build a threading HTTP server for *directory* on a free loopback port.

    Binds 127.0.0.1 only — the map must never be exposed beyond this machine.
    """
    handler_cls = SimpleHTTPRequestHandler if log_requests else _QuietHandler
    handler = partial(handler_cls, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    # Don't let an in-flight transfer keep the process alive after Ctrl+C.
    server.daemon_threads = True
    return server


def serve_directory(
    directory: Path,
    filename: str,
    *,
    quiet: bool = False,
    log_requests: bool = False,
    open_browser: bool = True,
) -> None:
    """Serve *directory* until Ctrl+C, opening *filename* in the browser."""
    with _make_server(directory, log_requests=log_requests) as httpd:
        port = httpd.server_address[1]
        url = f"http://127.0.0.1:{port}/{filename}"
        # The URL is the product of the command: printed even under --quiet.
        click.echo(f"Serving map at {url} — press Ctrl+C to stop")
        if open_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    if not quiet:
        click.echo("Stopped.")
