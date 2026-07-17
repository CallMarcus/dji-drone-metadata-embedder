"""Serve a generated map folder over local HTTP.

Browsers refuse WebGL pixel access to images on ``file://`` pages, so the
photomap 360-degree viewer only works when the map is served over HTTP.
This module is the loopback-only server behind ``dji-embed photomap --serve``.
"""

from __future__ import annotations

import sys
import threading
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


def _shutdown_on_stdin_eof(httpd: ThreadingHTTPServer) -> None:
    """Block until stdin reaches EOF, then stop the server.

    A wrapper app (the desktop GUI) holds the child's stdin pipe open for
    the child's lifetime; when the wrapper exits — cleanly or not — the pipe
    closes and the server goes down with it, so no orphaned server can
    outlive the app that started it.
    """
    try:
        sys.stdin.buffer.read()
    except (OSError, ValueError):
        pass
    httpd.shutdown()


def serve_directory(
    directory: Path,
    filename: str,
    *,
    quiet: bool = False,
    log_requests: bool = False,
    open_browser: bool = True,
    bare_url: bool = False,
    stop_on_stdin_eof: bool = False,
) -> None:
    """Serve *directory* until Ctrl+C, opening *filename* in the browser.

    ``bare_url`` prints the URL alone as the first stdout line — the stable
    contract wrapper apps parse (dji-embed serve --url-only). Flushed
    explicitly: under a pipe, stdout is block-buffered and the wrapper
    needs the line before the server settles in to run forever.
    ``stop_on_stdin_eof`` additionally stops serving when stdin closes
    (see :func:`_shutdown_on_stdin_eof`).
    """
    with _make_server(directory, log_requests=log_requests) as httpd:
        port = httpd.server_address[1]
        url = f"http://127.0.0.1:{port}/{filename}"
        # The URL is the product of the command: printed even under --quiet.
        if bare_url:
            click.echo(url)
            sys.stdout.flush()
        else:
            click.echo(f"Serving map at {url} — press Ctrl+C to stop")
        if open_browser:
            webbrowser.open(url)
        if stop_on_stdin_eof:
            threading.Thread(
                target=_shutdown_on_stdin_eof, args=(httpd,), daemon=True
            ).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    if not quiet:
        click.echo("Stopped.")
