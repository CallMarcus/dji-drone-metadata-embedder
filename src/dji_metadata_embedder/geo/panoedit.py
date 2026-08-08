"""Interactive opening-view editor for GPano panoramas (#440).

Scans a folder for equirectangular panoramas, serves a localhost Pannellum
editor page, and writes the composed view back as the three GPano
initial-view tags via ExifTool (default ``_original`` backup kept). The
compass heading written is ``PoseHeadingDegrees + viewer yaw`` — the exact
inverse of the read-side mapping in :func:`.photomap._pano_view`.
"""

from __future__ import annotations

import hmac
import json
import re
import secrets
import subprocess
import sys
import threading
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path

import click

from ..utils.exiftool import exiftool_exe
from .photomap import _maybe_float, _pano_view
from .serve import _MapServer, _RangeHandler, _shutdown_on_stdin_eof

_EXIFTOOL_INSTALL_HINT = (
    "ExifTool not found. Run: dji-embed doctor --install exiftool "
    "(downloads a pinned, checksum-verified copy; no admin rights needed). "
    "Alternatively install it from https://exiftool.org or set "
    "DJIEMBED_EXIFTOOL_PATH to the executable."
)

# The read half of the editor: pose anchors compass headings to the image
# frame; the three InitialView* tags are what Save writes back.
_SCAN_TAGS = [
    "-XMP-GPano:ProjectionType",
    "-XMP-GPano:PoseHeadingDegrees",
    "-XMP-GPano:InitialViewHeadingDegrees",
    "-XMP-GPano:InitialViewPitchDegrees",
    "-XMP-GPano:InitialHorizontalFOVDegrees",
]
_PANO_EXTS = ("jpg", "jpeg")


class PanoEditError(Exception):
    """A panoedit failure with a user-facing message."""


@dataclass
class PanoFile:
    """One editable panorama: absolute path, display name, pose heading
    (0.0 when the stitcher wrote none), and the current viewer-ready
    initial view (``None`` where tags are absent)."""

    path: Path
    name: str
    pose: float
    yaw: float | None
    pitch: float | None
    hfov: float | None


def compass_heading(pose: float, yaw: float) -> float:
    """Viewer yaw -> the compass ``InitialViewHeadingDegrees`` to write."""
    return (pose + yaw) % 360.0


def _run_scan(directory: Path, recursive: bool) -> list[dict]:
    args = [exiftool_exe(), "-json", "-n"]
    if recursive:
        args.append("-r")
    args += _SCAN_TAGS
    for ext in _PANO_EXTS:
        args += ["-ext", ext]
    args.append(str(directory))
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        raise PanoEditError(_EXIFTOOL_INSTALL_HINT) from None
    out = proc.stdout.strip()
    if not out:
        if proc.returncode != 0:
            stderr = proc.stderr.strip()[-300:]
            raise PanoEditError(
                f"ExifTool scan of {directory} failed "
                f"(exit {proc.returncode}): {stderr or 'no error output'}"
            )
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise PanoEditError(f"Could not parse ExifTool JSON: {exc}") from exc
    if not isinstance(data, list):
        raise PanoEditError("Unexpected ExifTool JSON shape (expected a list)")
    return data


def scan_panos(directory: Path, recursive: bool = False) -> list[PanoFile]:
    """Scan *directory* and return its equirectangular panoramas, sorted.

    Raises :class:`PanoEditError` when the folder holds no panoramas — the
    editor has nothing to edit, and a blank page would look like a bug.
    """
    entries = _run_scan(directory, recursive)
    files: list[PanoFile] = []
    for entry in entries:
        proj = entry.get("ProjectionType")
        if not (isinstance(proj, str)
                and proj.strip().lower() == "equirectangular"):
            continue
        path = Path(str(entry.get("SourceFile", "?")))
        yaw, pitch, hfov = _pano_view(entry)
        files.append(PanoFile(
            path=path,
            name=path.name,
            pose=_maybe_float(entry.get("PoseHeadingDegrees")) or 0.0,
            yaw=yaw, pitch=pitch, hfov=hfov,
        ))
    if not files:
        raise PanoEditError(
            f"No 360-degree panoramas found in {directory} "
            f"({len(entries)} JPEGs scanned; a panorama carries "
            "XMP-GPano:ProjectionType=equirectangular)"
        )
    files.sort(key=lambda f: f.name)
    return files


def write_initial_view(
    path: Path, heading: float, pitch: float, hfov: float
) -> dict:
    """Write the three initial-view tags to *path* and read them back.

    ExifTool's default sidecar backup (``<name>_original``) is deliberately
    kept — batch editing must never be able to destroy an original. The
    read-back is the write verification: what the map will see is what the
    caller gets.
    """
    exe = exiftool_exe()
    write_args = [
        exe, "-n",
        f"-XMP-GPano:InitialViewHeadingDegrees={heading}",
        f"-XMP-GPano:InitialViewPitchDegrees={pitch}",
        f"-XMP-GPano:InitialHorizontalFOVDegrees={hfov}",
        str(path),
    ]
    try:
        proc = subprocess.run(
            write_args, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        raise PanoEditError(_EXIFTOOL_INSTALL_HINT) from None
    if proc.returncode != 0:
        stderr = proc.stderr.strip()[-300:]
        raise PanoEditError(
            f"ExifTool could not write {path.name}: "
            f"{stderr or 'no error output'}"
        )
    read_args = [exe, "-json", "-n", *_SCAN_TAGS[1:], str(path)]
    proc = subprocess.run(
        read_args, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    try:
        entry = json.loads(proc.stdout)[0]
    except (json.JSONDecodeError, IndexError) as exc:
        raise PanoEditError(
            f"Could not verify the write to {path.name}: {exc}"
        ) from exc
    return {
        "heading": _maybe_float(entry.get("InitialViewHeadingDegrees")),
        "pitch": _maybe_float(entry.get("InitialViewPitchDegrees")),
        "hfov": _maybe_float(entry.get("InitialHorizontalFOVDegrees")),
        "pose": _maybe_float(entry.get("PoseHeadingDegrees")) or 0.0,
    }


# Server ---------------------------------------------------------------

_IMG_RE = re.compile(r"^/img/(\d+)$")

# Cap on the /api/save request body: a heading/pitch/hfov triple plus the
# token never comes close, so anything larger is not this page talking.
_MAX_SAVE_BODY = 4096


def _view_payload(f: PanoFile, index: int) -> dict:
    return {
        "index": index, "name": f.name, "pose": f.pose,
        "yaw": f.yaw, "pitch": f.pitch, "hfov": f.hfov,
        "hasView": f.yaw is not None,
    }


class _EditorHandler(_RangeHandler):
    """Routes: the editor page, the JSON API, and ranged pano images.

    Images are addressed by index into the scanned list — the client can
    never name a path. POSTs require the per-session token: pages on other
    origins can reach 127.0.0.1, the token is what stops them writing.
    """

    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/":
            body = self.server.pano_page          # type: ignore[attr-defined]
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/list":
            files = self.server.pano_files        # type: ignore[attr-defined]
            self._send_json(HTTPStatus.OK, [
                _view_payload(f, i) for i, f in enumerate(files)
            ])
            return
        if _IMG_RE.match(path):
            super().do_GET()          # ranged serving via translate_path
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def translate_path(self, path: str) -> str:
        # Only /img/<index> resolves to a real file. Anything else maps to
        # a file that cannot exist, so the base handler's open() raises
        # FileNotFoundError and answers 404. (Not a NUL-byte sentinel:
        # open("\0...") raises ValueError, which SimpleHTTPRequestHandler
        # does not catch.)
        m = _IMG_RE.match(path.split("?", 1)[0])
        if m:
            files = self.server.pano_files        # type: ignore[attr-defined]
            i = int(m.group(1))
            if i < len(files):
                return str(files[i].path)
        return str(Path(self.directory) / ".panoedit-404-not-a-real-file")

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/api/save":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 0 < length <= _MAX_SAVE_BODY:
            self._send_json(HTTPStatus.BAD_REQUEST,
                            {"error": "bad request body"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST,
                            {"error": "invalid JSON"})
            return
        token = self.server.pano_token            # type: ignore[attr-defined]
        sent = payload.get("token")
        if not (isinstance(sent, str)
                and hmac.compare_digest(sent, token)):
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "bad token"})
            return
        files = self.server.pano_files            # type: ignore[attr-defined]
        index = payload.get("index")
        heading = _maybe_float(payload.get("heading"))
        pitch = _maybe_float(payload.get("pitch"))
        hfov = _maybe_float(payload.get("hfov"))
        if (not isinstance(index, int) or not 0 <= index < len(files)
                or heading is None or pitch is None or hfov is None
                or not -90.0 <= pitch <= 90.0
                or not 10.0 <= hfov <= 170.0):
            self._send_json(HTTPStatus.BAD_REQUEST,
                            {"error": "invalid index or view values"})
            return
        heading %= 360.0
        f = files[index]
        try:
            with self.server.pano_lock:           # type: ignore[attr-defined]
                verified = write_initial_view(f.path, heading, pitch, hfov)
        except PanoEditError as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR,
                            {"error": str(exc)})
            return
        # The verified read is the new truth for /api/list and the client.
        f.pose = verified["pose"]
        f.yaw, f.pitch, f.hfov = _pano_view({
            "InitialViewHeadingDegrees": verified["heading"],
            "PoseHeadingDegrees": verified["pose"],
            "InitialViewPitchDegrees": verified["pitch"],
            "InitialHorizontalFOVDegrees": verified["hfov"],
        })
        self._send_json(HTTPStatus.OK, {**verified,
                                        **_view_payload(f, index)})

    def _send_json(self, status: HTTPStatus, obj: object) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_editor_server(
    directory: Path, *, recursive: bool = False, port: int = 0
) -> tuple[ThreadingHTTPServer, str]:
    """Scan *directory* and return a ready (server, url) pair.

    Binds 127.0.0.1 only. Raises :class:`PanoEditError` when the folder
    holds no panoramas (see :func:`scan_panos`).
    """
    from functools import partial

    from .panoedit_html import build_editor_page

    files = scan_panos(directory, recursive=recursive)
    token = secrets.token_urlsafe(32)
    handler = partial(_EditorHandler, directory=str(directory))
    server = _MapServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    server.pano_files = files                     # type: ignore[attr-defined]
    server.pano_token = token                     # type: ignore[attr-defined]
    server.pano_lock = threading.Lock()           # type: ignore[attr-defined]
    server.pano_page = build_editor_page(token).encode(  # type: ignore[attr-defined]
        "utf-8")
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    return server, url


def run_editor(
    directory: Path,
    *,
    recursive: bool = False,
    port: int = 0,
    open_browser: bool = True,
    bare_url: bool = False,
    stop_on_stdin_eof: bool = False,
) -> None:
    """Serve the editor until Ctrl+C (same contract as ``serve_directory``)."""
    server, url = make_editor_server(directory, recursive=recursive, port=port)
    with server:
        if bare_url:
            click.echo(url)
            sys.stdout.flush()
        else:
            n = len(server.pano_files)            # type: ignore[attr-defined]
            click.echo(
                f"Editing {n} panorama{'s' if n != 1 else ''} at {url} "
                "— press Ctrl+C to stop"
            )
        if open_browser:
            webbrowser.open(url)
        if stop_on_stdin_eof:
            threading.Thread(
                target=_shutdown_on_stdin_eof, args=(server,), daemon=True
            ).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
