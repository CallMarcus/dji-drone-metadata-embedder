"""Interactive opening-view editor for GPano panoramas (#440).

Scans a folder for equirectangular panoramas, serves a localhost Pannellum
editor page, and writes the composed view back as the three GPano
initial-view tags via ExifTool (default ``_original`` backup kept). The
compass heading written is ``PoseHeadingDegrees + viewer yaw`` — the exact
inverse of the read-side mapping in :func:`.photomap._pano_view`.

Oversized panoramas are served downscaled (#471); see
:data:`DEFAULT_MAX_SERVE_WIDTH`.
"""

from __future__ import annotations

import hmac
import json
import logging
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

import click

from ..utils.exiftool import exiftool_exe
from .photomap import _maybe_float, _pano_view
from .serve import _MapServer, _RangeHandler, _shutdown_on_stdin_eof

logger = logging.getLogger(__name__)

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

# Pixel dimensions come from the same scan: they decide whether a panorama
# is served downscaled (#471).
_SIZE_TAGS = ["-ImageWidth", "-ImageHeight"]

# Panoramas wider than this are served downscaled to it. Measured, not
# queried: on the weakest reported hardware (#471 — GTX 670, 2 GB VRAM,
# final Kepler driver) 12000 px and 8000 px panoramas failed to load
# erratically after the first, while the same folder downscaled to
# 6000x3000 opened every image reliably. The GPU's advertised maximum
# texture size (16384 px there) is not the limit that bites; VRAM pressure
# across viewer teardown and rebuild is, and that is not something the page
# can ask about. 6000 px is still far more detail than the editor viewport
# resolves, and the saved heading/pitch/FOV are resolution-independent.
DEFAULT_MAX_SERVE_WIDTH = 6000

# Below this a "downscaled" rendition would be too coarse to compose a view
# in; anything smaller (but non-zero) is raised to it.
_MIN_SERVE_WIDTH = 512


class PanoEditError(Exception):
    """A panoedit failure with a user-facing message."""


@dataclass
class PanoFile:
    """One editable panorama: absolute path, display name, pose heading
    (0.0 when the stitcher wrote none), the current viewer-ready initial
    view (``None`` where tags are absent), and the pixel dimensions
    (``0`` when ExifTool reported none)."""

    path: Path
    name: str
    pose: float
    yaw: float | None
    pitch: float | None
    hfov: float | None
    width: int = 0
    height: int = 0


def compass_heading(pose: float, yaw: float) -> float:
    """Viewer yaw -> the compass ``InitialViewHeadingDegrees`` to write."""
    return (pose + yaw) % 360.0


def _run_scan(directory: Path, recursive: bool) -> list[dict]:
    args = [exiftool_exe(), "-json", "-n"]
    if recursive:
        args.append("-r")
    args += _SCAN_TAGS + _SIZE_TAGS
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
            width=int(_maybe_float(entry.get("ImageWidth")) or 0),
            height=int(_maybe_float(entry.get("ImageHeight")) or 0),
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


# Renditions -----------------------------------------------------------

_PILLOW_HINT = (
    "Pillow is not installed, so oversized panoramas are served at full "
    "size. Install it to have the editor downscale them: "
    "pip install 'dji-drone-metadata-embedder[terrain]' "
    "(pipx: pipx inject dji-drone-metadata-embedder pillow)"
)


def _pil_image():
    """Pillow's ``Image`` module, or ``None`` when Pillow is absent.

    Imported lazily, like :mod:`.panorender` and :mod:`.terrain`: Pillow
    ships in the ``[terrain]`` extra, and a bare install must still be able
    to run the editor — just without downscaled renditions.
    """
    try:
        from PIL import Image  # type: ignore[import-untyped]
    except ImportError:
        return None
    return Image


def renditions_available() -> bool:
    """Whether downscaled renditions can be produced on this install."""
    return _pil_image() is not None


def downscale_pano(src: Path, dest: Path, max_width: int) -> Path | None:
    """Write a JPEG copy of *src* at most *max_width* wide to *dest*.

    Returns *dest*, or ``None`` when no rendition could be produced — the
    caller then serves the original, because a missing preview is a worse
    outcome than a large one. The source file is only ever read.

    The XMP packet is carried across verbatim and its survival is verified:
    Pannellum derives the panorama's angular extent from the GPano crop
    tags as *ratios* (``CroppedAreaImageWidthPixels / FullPanoWidthPixels``
    and friends), so the original numbers stay correct at any scale — but a
    rendition that lost them would be framed differently from the original
    for any cropped panorama, and the saved view would inherit that error.
    """
    Image = _pil_image()
    if Image is None:
        return None
    try:
        with Image.open(src) as im:
            xmp = im.info.get("xmp")
            exif = im.info.get("exif")
            # JPEG DCT scaling: decoding straight to a smaller size skips
            # most of the work (a 12000 px source halves for free).
            im.draft("RGB", (max_width, max(1, max_width // 2)))
            rgb = im.convert("RGB")
        if rgb.width > max_width:
            height = max(1, round(rgb.height * max_width / rgb.width))
            rgb = rgb.resize((max_width, height), Image.LANCZOS)
        params: dict[str, object] = {"quality": 88}
        if exif:
            params["exif"] = exif
        if xmp:
            params["xmp"] = xmp
        try:
            rgb.save(dest, "JPEG", **params)
        except TypeError:  # Pillow too old for the xmp= save parameter
            params.pop("xmp", None)
            rgb.save(dest, "JPEG", **params)
        if xmp:
            with Image.open(dest) as check:   # header read only, no decode
                if not check.info.get("xmp"):
                    raise ValueError("GPano metadata did not survive")
    except Exception as exc:                  # noqa: BLE001 - never fatal
        logger.warning("Could not downscale %s: %s", src.name, exc)
        dest.unlink(missing_ok=True)
        return None
    return dest


# Server ---------------------------------------------------------------

_IMG_RE = re.compile(r"^/img/(\d+)$")

# Cap on the /api/save request body: a heading/pitch/hfov triple plus the
# token never comes close, so anything larger is not this page talking.
_MAX_SAVE_BODY = 4096


def _view_payload(
    f: PanoFile, index: int, *, max_width: int = 0, renditions: bool = True
) -> dict:
    return {
        "index": index, "name": f.name, "pose": f.pose,
        "yaw": f.yaw, "pitch": f.pitch, "hfov": f.hfov,
        "hasView": f.yaw is not None,
        "width": f.width, "height": f.height,
        "downscaled": bool(renditions and max_width and f.width > max_width),
    }


class _EditorServer(_MapServer):
    """Editor server: owns the scanned files, the save lock, and the
    rendition cache for oversized panoramas (#471).

    Renditions are built on first request and cached in a temporary
    directory that lives exactly as long as the server. Building is
    serialized: two viewers racing on the same image would otherwise pay
    for the same multi-second JPEG re-encode twice, on precisely the
    machines that can least afford it.
    """

    pano_files: list[PanoFile]
    pano_token: str
    pano_page: bytes
    pano_max_width: int = 0
    pano_renditions: bool = True

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.pano_lock = threading.Lock()
        self._rendition_lock = threading.Lock()
        self._renditions: dict[int, Path | None] = {}
        self._cache: tempfile.TemporaryDirectory | None = None

    def image_path(self, index: int) -> Path:
        """Path to serve for ``/img/<index>``: a cached downscaled
        rendition when the panorama is oversized, else the original."""
        f = self.pano_files[index]
        if not (self.pano_max_width and f.width > self.pano_max_width):
            return f.path
        with self._rendition_lock:
            if index not in self._renditions:
                if self._cache is None:
                    self._cache = tempfile.TemporaryDirectory(
                        prefix="djiembed-panoedit-")
                self._renditions[index] = downscale_pano(
                    f.path, Path(self._cache.name) / f"{index}.jpg",
                    self.pano_max_width,
                )
            rendition = self._renditions[index]
        return rendition or f.path

    def payload(self, index: int) -> dict:
        return _view_payload(
            self.pano_files[index], index,
            max_width=self.pano_max_width, renditions=self.pano_renditions,
        )

    def server_close(self) -> None:
        try:
            super().server_close()
        finally:
            if self._cache is not None:
                self._cache.cleanup()
                self._cache = None


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
            server = self.server                  # type: ignore[assignment]
            self._send_json(HTTPStatus.OK, [
                server.payload(i)                 # type: ignore[attr-defined]
                for i in range(len(server.pano_files))  # type: ignore[attr-defined]
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
                # May build a downscaled rendition on the way (#471);
                # cached, so the second call within a request is free.
                return str(
                    self.server.image_path(i))    # type: ignore[attr-defined]
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
        self._send_json(
            HTTPStatus.OK,
            {**verified,
             **self.server.payload(index)},       # type: ignore[attr-defined]
        )

    def _send_json(self, status: HTTPStatus, obj: object) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_editor_server(
    directory: Path,
    *,
    recursive: bool = False,
    port: int = 0,
    max_width: int = DEFAULT_MAX_SERVE_WIDTH,
) -> tuple[_EditorServer, str]:
    """Scan *directory* and return a ready (server, url) pair.

    Binds 127.0.0.1 only. Raises :class:`PanoEditError` when the folder
    holds no panoramas (see :func:`scan_panos`).

    ``max_width`` caps the width of the images handed to the viewer;
    ``0`` disables downscaling entirely and anything between 1 and
    :data:`_MIN_SERVE_WIDTH` is raised to that floor.
    """
    from functools import partial

    from .panoedit_html import build_editor_page

    files = scan_panos(directory, recursive=recursive)
    max_width = 0 if max_width <= 0 else max(_MIN_SERVE_WIDTH, max_width)
    renditions = renditions_available() if max_width else True
    token = secrets.token_urlsafe(32)
    handler = partial(_EditorHandler, directory=str(directory))
    server = _EditorServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    server.pano_files = files
    server.pano_token = token
    server.pano_max_width = max_width
    server.pano_renditions = renditions
    server.pano_page = build_editor_page(
        token, max_width=max_width, renditions=renditions,
        hint=_PILLOW_HINT).encode("utf-8")
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    return server, url


def _oversize_notice(server: _EditorServer) -> str | None:
    """One line about downscaled serving, or ``None`` when it never applies."""
    max_width = server.pano_max_width
    if not max_width:
        return None
    n = sum(1 for f in server.pano_files if f.width > max_width)
    if not n:
        return None
    plural = "s" if n != 1 else ""
    if not server.pano_renditions:
        return f"{n} panorama{plural} wider than {max_width} px. " + _PILLOW_HINT
    return (
        f"Showing {n} panorama{plural} wider than {max_width} px downscaled "
        f"to {max_width} px - older graphics hardware cannot display them at "
        "full size. The files on disk are not modified."
    )


def run_editor(
    directory: Path,
    *,
    recursive: bool = False,
    port: int = 0,
    open_browser: bool = True,
    bare_url: bool = False,
    stop_on_stdin_eof: bool = False,
    max_width: int = DEFAULT_MAX_SERVE_WIDTH,
) -> None:
    """Serve the editor until Ctrl+C (same contract as ``serve_directory``)."""
    server, url = make_editor_server(
        directory, recursive=recursive, port=port, max_width=max_width)
    with server:
        if bare_url:
            click.echo(url)
            sys.stdout.flush()
        else:
            n = len(server.pano_files)
            click.echo(
                f"Editing {n} panorama{'s' if n != 1 else ''} at {url} "
                "- press Ctrl+C to stop"
            )
        notice = _oversize_notice(server)
        if notice:
            # stderr: --url-only promises the URL as the first stdout line,
            # and the GUI parses exactly that.
            click.echo(notice, err=True)
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
