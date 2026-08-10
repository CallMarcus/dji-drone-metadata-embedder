"""Serve a generated map folder over local HTTP.

Browsers refuse WebGL pixel access to images on ``file://`` pages, so the
photomap 360-degree viewer only works when the map is served over HTTP.
Media seeking needs HTTP Range (``206 Partial Content``), which Python's
stock handler does not implement, so this module supplies it.
"""

from __future__ import annotations

import os
import re
import socket
import sys
import threading
import webbrowser
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import BinaryIO

import click

_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _parse_range(header: str, size: int) -> tuple[int, int] | None:
    """Return an inclusive ``(first, last)`` byte range for *header*.

    ``None`` means "serve the whole file": a unit other than bytes, a
    multi-range request (which no browser needs for media playback and which
    would cost a multipart body), or anything unparseable. Raises
    :class:`ValueError` when the syntax is fine but the range cannot be
    satisfied, so the caller can answer 416 rather than guessing.
    """
    m = _RANGE_RE.match(header.strip())
    if m is None:
        return None
    first_s, last_s = m.group(1), m.group(2)
    if not first_s and not last_s:
        return None
    if not first_s:                       # bytes=-N : the final N bytes
        n = int(last_s)
        if n == 0:
            raise ValueError("zero-length suffix range")
        if size == 0:
            # A suffix range has nothing to select from an empty file. This
            # is unsatisfiable *because of the file's size* -- the same
            # category as `first >= size` below -- not a malformed header,
            # so it gets 416 rather than the "ignore" treatment below.
            # (Left uncaught, max(0, size - n) would compute (0, -1): a
            # reversed pair, but for a different reason than the
            # explicit-range case, so it doesn't belong under that guard.)
            raise ValueError("empty file has no satisfiable range")
        return (max(0, size - n), size - 1)
    first = int(first_s)
    if first >= size:
        raise ValueError("range starts at or past end of file")
    last = int(last_s) if last_s else size - 1
    last = min(last, size - 1)
    if last < first:
        # A reversed range ("bytes=100-50") is syntactically valid but
        # semantically backwards. RFC 9110 has a server ignore a
        # ranges-specifier it can't use rather than reject it -- 416 means
        # "outside the file," which a reversed-but-in-bounds range isn't.
        # Treating it as "not a shape we understand" (-> None, whole file)
        # matches how a foreign unit or a multi-range request is already
        # handled above: one rule for "this header is not usable," not two.
        return None
    return (first, last)


class _RangeHandler(SimpleHTTPRequestHandler):
    """``SimpleHTTPRequestHandler`` with single-range GET support.

    The stock handler ignores ``Range`` completely. The 3D map's video
    crossfade is a seek, so without this Chrome re-downloads from byte zero
    every time the clock moves and Safari refuses to play at all.
    """

    _range: tuple[int, int] | None = None

    def end_headers(self) -> None:
        # Advertised on every response: a media element checks for it before
        # it will attempt a seek at all.
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def send_head(self) -> BinaryIO | None:
        self._range = None
        header = self.headers.get("Range")
        path = self.translate_path(self.path)
        if not header or os.path.isdir(path):
            return super().send_head()
        try:
            fs = os.stat(path)
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None
        size = fs.st_size
        last_modified = self.date_time_string(int(fs.st_mtime))
        # If-Range: serve the range only when the validator still matches the
        # file, else fall back to the whole body -- a stale range spliced into
        # a changed file is silent corruption. The only validator this server
        # ever issues is Last-Modified (below), so an entity-tag can never
        # match and the comparison is string equality with what we would send.
        if_range = self.headers.get("If-Range")
        if if_range is not None and if_range.strip() != last_modified:
            return super().send_head()
        try:
            rng = _parse_range(header, size)
        except ValueError:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        if rng is None:
            # Whole-file response: let the base handler open and serve it.
            # Opening it ourselves here too would mean two file opens for
            # one request.
            return super().send_head()
        first, last = rng
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None
        try:
            self._range = rng
            f.seek(first)
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Range", f"bytes {first}-{last}/{size}")
            self.send_header("Content-Length", str(last - first + 1))
            # The base handler sends this on every 200; a 206 needs it just as
            # much or the client has no validator for its next If-Range.
            self.send_header("Last-Modified", last_modified)
            self.end_headers()
            return f
        except Exception:
            f.close()
            raise

    # mypy sees the base `copyfile` as generic over AnyStr (str or bytes);
    # this handler only ever deals in bytes, which mypy's LSP check can't
    # express as a narrowing override.
    def copyfile(self, source: BinaryIO, outputfile: BinaryIO) -> None:  # type: ignore[override]
        if self._range is None:
            super().copyfile(source, outputfile)
            return
        first, last = self._range
        remaining = last - first + 1
        while remaining > 0:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)


class _QuietHandler(_RangeHandler):
    """Range-capable handler without per-request stderr logging."""

    def log_message(self, format: str, *args: object) -> None:
        pass


class _MapServer(ThreadingHTTPServer):
    """``ThreadingHTTPServer`` that treats a vanished client as normal.

    Seeking media aborts in-flight range transfers as a matter of course, and
    the stock ``handle_error`` prints a full traceback for each one — a
    working server looks broken precisely when it is being used as intended.
    Anything outside the connection-reset family keeps the stock report.
    """

    def handle_error(
        self,
        request: socket.socket | tuple[bytes, socket.socket],
        client_address: object,
    ) -> None:
        if isinstance(sys.exc_info()[1], ConnectionError):
            return
        super().handle_error(request, client_address)


def _make_server(directory: Path, *, log_requests: bool = False) -> ThreadingHTTPServer:
    """Build a threading HTTP server for *directory* on a free loopback port.

    Binds 127.0.0.1 only — the map must never be exposed beyond this machine.
    """
    handler_cls = _RangeHandler if log_requests else _QuietHandler
    handler = partial(handler_cls, directory=str(directory))
    server = _MapServer(("127.0.0.1", 0), handler)
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
            click.echo(f"Serving map at {url} - press Ctrl+C to stop")
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
