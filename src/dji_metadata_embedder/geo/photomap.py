"""Still-photo location model and exporters (GeoJSON, KML).

One batch ExifTool scan of a photo directory (JPG/JPEG/DNG) yields a
:class:`PhotoPoint` list — the single model every photomap writer consumes:
GeoJSON and KML here, the clustered HTML map in :mod:`.photomap_html`.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

from ..utilities import is_gps_fix, redact_coords
from ..utils.exiftool import exiftool_exe

logger = logging.getLogger(__name__)


class PhotomapError(RuntimeError):
    """Raised when a photo directory cannot be scanned."""


_EXIFTOOL_INSTALL_HINT = (
    "ExifTool not found. Run: dji-embed doctor --install exiftool "
    "(downloads a pinned, checksum-verified copy; no admin rights needed). "
    "Alternatively install it from https://exiftool.org or set "
    "DJIEMBED_EXIFTOOL_PATH to the executable."
)

# One batch call reads GPS, capture metadata, and the EXIF-embedded thumbnail
# for every photo in a single subprocess. -n makes the Composite GPS tags
# signed decimal degrees; -b returns ThumbnailImage as "base64:..." in JSON.
_SCAN_TAGS = [
    "-Composite:GPSLatitude",
    "-Composite:GPSLongitude",
    "-Composite:GPSAltitude",
    "-EXIF:DateTimeOriginal",
    "-EXIF:Model",
    "-EXIF:ISO",
    "-EXIF:ExposureTime",
    "-EXIF:FNumber",
    "-EXIF:ThumbnailImage",
    # DJI DNGs carry no EXIF:ThumbnailImage; their preview is PreviewImage
    # (IFD0/SubIFD). Requested for all photos, used only as a fallback below.
    "-PreviewImage",
    # XMP GPano marks stitched panoramas (DJI, Insta360, Google Camera, ...).
    # equirectangular => the HTML map can open the photo in a 360 viewer.
    "-XMP-GPano:ProjectionType",
]
_PHOTO_EXTS = ("jpg", "jpeg", "dng")

# Ingestion-enforced invariant: thumbnail_b64 only ever holds base64 text, so
# writers may embed it in CDATA/data URIs without further escaping.
_BASE64_RE = re.compile(r"[A-Za-z0-9+/=\s]+")

# Cap on the PreviewImage fallback so a DNG-heavy archive doesn't blow the
# ~15-40 KB/photo embed budget (raw previews can be multi-MB). ~225 KB decoded.
# UNVERIFIED against a real DJI DNG: the JSON shape is assumed identical to
# ThumbnailImage ("base64:...") — the tag differs, the encoding does not.
_MAX_PREVIEW_B64_CHARS = 300_000


@dataclass
class PhotoPoint:
    """One GPS-tagged photo: WGS84 lat/lon, altitude (m, ``None`` when the EXIF
    has no ``GPSAltitude``), source filename, and optional capture metadata for
    popups. ``None`` altitude is kept distinct from a real 0 m fix so writers
    can clamp such placemarks to the ground rather than burying them.
    ``is_pano`` marks GPano equirectangular panoramas (360 viewer candidates)."""

    lat: float
    lon: float
    alt: float | None
    name: str
    timestamp: str | None = None
    model: str | None = None
    iso: int | None = None
    exposure: float | None = None
    fnum: float | None = None
    thumbnail_b64: str | None = None
    is_pano: bool = False


def _display_datetime(value: object) -> str | None:
    """EXIF ``2026:06:15 12:30:45`` -> ``2026-06-15 12:30:45`` (display only)."""
    if not isinstance(value, str) or not value:
        return None
    date, _, time = value.partition(" ")
    return f"{date.replace(':', '-')} {time}".strip()


def _maybe_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None


def _maybe_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _maybe_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _clean_base64(raw: object) -> str | None:
    """Return the base64 payload of an ExifTool ``-b`` blob (``base64:...``), else None."""
    if isinstance(raw, str) and raw.startswith("base64:"):
        candidate = raw[len("base64:"):]
        if _BASE64_RE.fullmatch(candidate):
            return candidate
    return None


def _extract_thumbnail_b64(entry: dict) -> str | None:
    """Pick a preview blob: the small EXIF thumbnail, else a size-capped PreviewImage.

    The EXIF thumbnail is always preferred (small, present on JPGs). PreviewImage
    is the DNG fallback, taken only when it stays under ``_MAX_PREVIEW_B64_CHARS``.
    """
    thumb = _clean_base64(entry.get("ThumbnailImage"))
    if thumb is not None:
        return thumb
    preview = _clean_base64(entry.get("PreviewImage"))
    if preview is not None and len(preview) <= _MAX_PREVIEW_B64_CHARS:
        return preview
    return None


def format_exposure(exposure: float | None) -> str | None:
    """Format ExposureTime seconds for display: ``0.001`` -> ``1/1000 s``."""
    if not exposure or exposure <= 0:
        return None
    if exposure < 1:
        denom = round(1 / exposure)
        if denom >= 2 and abs(1 / denom - exposure) / exposure < 0.05:
            return f"1/{denom} s"
    return f"{exposure:g} s"


def camera_summary(p: PhotoPoint) -> str:
    """One display line, e.g. ``FC8482 · ISO 100 · 1/1000 s · f/1.7``.

    Missing parts are omitted; all-missing yields an empty string."""
    parts = [
        p.model,
        f"ISO {p.iso}" if p.iso is not None else None,
        format_exposure(p.exposure),
        f"f/{p.fnum:g}" if p.fnum is not None else None,
    ]
    return " · ".join(x for x in parts if x)


def _display_name(source: str, root: Path | None) -> str:
    """Display name for a scanned photo.

    Basename by default. When *root* is given (recursive scans), use the path
    relative to the scan root so per-session archives don't collapse to
    indistinguishable ``DJI_0001.JPG`` pins — DJI restarts numbering per card.
    ExifTool echoes the directory argument's separators, so both sides are
    normalised to ``/`` before stripping; a SourceFile outside *root*
    (unexpected) falls back to the basename.
    """
    if root is None:
        return Path(source).name
    src = source.replace("\\", "/")
    prefix = str(root).replace("\\", "/").rstrip("/") + "/"
    if src.startswith(prefix):
        return src[len(prefix):]
    return Path(source).name


def points_from_exiftool_json(
    data: list[dict], *, root: Path | None = None
) -> tuple[list[PhotoPoint], list[str]]:
    """Map an ExifTool ``-json`` scan to ``(points, skipped_names)``.

    Photos without a usable GPS fix (missing tags, or the (0, 0) no-fix
    placeholder) go to ``skipped_names``. Both lists are sorted by filename so
    output is deterministic regardless of scan order. When *root* is supplied,
    display names are relative to it (see :func:`_display_name`).
    """
    points: list[PhotoPoint] = []
    skipped: list[str] = []
    for entry in data:
        name = _display_name(str(entry.get("SourceFile", "?")), root)
        lat = _maybe_float(entry.get("GPSLatitude"))
        lon = _maybe_float(entry.get("GPSLongitude"))
        if lat is None or lon is None or not is_gps_fix(lat, lon):
            skipped.append(name)
            continue
        thumb_b64 = _extract_thumbnail_b64(entry)
        proj = entry.get("ProjectionType")
        is_pano = isinstance(proj, str) and proj.strip().lower() == "equirectangular"
        points.append(
            PhotoPoint(
                lat=lat,
                lon=lon,
                alt=_maybe_float(entry.get("GPSAltitude")),
                name=name,
                timestamp=_display_datetime(entry.get("DateTimeOriginal")),
                model=_maybe_str(entry.get("Model")),
                iso=_maybe_int(entry.get("ISO")),
                exposure=_maybe_float(entry.get("ExposureTime")),
                fnum=_maybe_float(entry.get("FNumber")),
                thumbnail_b64=thumb_b64,
                is_pano=is_pano,
            )
        )
    points.sort(key=lambda p: p.name)
    skipped.sort()
    return points, skipped


def _run_exiftool_scan(directory: Path, recursive: bool) -> list[dict]:
    """Run one batch ExifTool scan over *directory* and return its JSON.

    ExifTool exits 0 with empty stdout when no photo matches ``-ext``; that is
    "no photos", not an error. A non-zero exit with no JSON at all is a real
    failure (unreadable directory, broken install) and raises.
    """
    args = [exiftool_exe(), "-json", "-n", "-b"]
    if recursive:
        args.append("-r")
    args += _SCAN_TAGS
    for ext in _PHOTO_EXTS:
        args += ["-ext", ext]
    args.append(str(directory))
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    except FileNotFoundError:
        raise PhotomapError(_EXIFTOOL_INSTALL_HINT) from None
    out = proc.stdout.strip()
    if not out:
        if proc.returncode != 0:
            stderr = proc.stderr.strip()[-300:]
            raise PhotomapError(
                f"ExifTool scan of {directory} failed (exit {proc.returncode}): "
                f"{stderr or 'no error output'}"
            )
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise PhotomapError(f"Could not parse ExifTool JSON: {exc}") from exc
    if not isinstance(data, list):
        raise PhotomapError("Unexpected ExifTool JSON shape (expected a list)")
    return data


def scan_photos(
    directory: Path | str, recursive: bool = False
) -> tuple[list[PhotoPoint], list[str]]:
    """Scan *directory* for photos and return ``(gps_points, skipped_names)``."""
    directory = Path(directory)
    return points_from_exiftool_json(
        _run_exiftool_scan(directory, recursive),
        root=directory if recursive else None,
    )


def redact_photo_points(points: list[PhotoPoint], mode: str) -> list[PhotoPoint]:
    """Return *points* with coordinates coarsened per *mode*.

    ``fuzz`` rounds through the shared :func:`redact_coords` (3 decimals,
    ~100 m) so the privacy guarantee stays single-sourced with flightmap and
    convert. Any other mode returns the list unchanged. ``drop`` is not
    offered for photos — it would simply empty the map.
    """
    if mode != "fuzz" or not points:
        return points
    coords = redact_coords([(p.lat, p.lon) for p in points], "fuzz")
    return [replace(p, lat=lat, lon=lon) for p, (lat, lon) in zip(points, coords)]


def _link_href(name: str, base: str) -> str:
    """Href to the original photo: percent-encoded *name* under *base*.

    Each ``/``-separated segment of *name* is fully percent-encoded (spaces,
    ``#``, quotes) while the separators survive, so relative subdirectory
    links from recursive scans still resolve. *base* is taken as-is apart
    from separator normalisation — it may be a relative folder or an absolute
    URL, and encoding it would corrupt ``https://``.
    """
    encoded = "/".join(quote(seg, safe="") for seg in name.split("/"))
    base = base.replace("\\", "/").rstrip("/")
    return f"{base}/{encoded}" if base else encoded


def photos_to_geojson(
    points: list[PhotoPoint],
    *,
    include_thumbnails: bool = False,
    link_base: str | None = None,
) -> dict:
    """Return a GeoJSON ``FeatureCollection`` of photo ``Point`` features.

    Thumbnails are excluded by default — base64 blobs do not belong in the GIS
    interchange file. The HTML viewer opts in for its embedded copy.

    ``link_base`` (issue #253) is equally opt-in: when not ``None``, each
    feature gains a ``link`` property pointing at the original photo file
    (``""`` = alongside the map, else a folder/URL prefix). The standalone
    GeoJSON writer never passes it — a shared map must not accumulate fragile
    file references by default. Panoramic photos additionally get
    ``"pano": true`` so the HTML viewer can open them in 360°.
    """
    features: list[dict] = []
    for p in points:
        props: dict = {"name": p.name}
        if link_base is not None:
            props["link"] = _link_href(p.name, link_base)
            if p.is_pano:
                props["pano"] = True
        if p.timestamp:
            props["timestamp"] = p.timestamp
        # Missing altitude is omitted entirely (no property, 2D coordinate)
        # rather than reported as a spurious 0 m.
        coords = [p.lon, p.lat] if p.alt is None else [p.lon, p.lat, p.alt]
        if p.alt is not None:
            props["alt"] = p.alt
        camera = camera_summary(p)
        if camera:
            props["camera"] = camera
        if include_thumbnails and p.thumbnail_b64:
            props["thumb"] = p.thumbnail_b64
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": coords},
                "properties": props,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def write_photos_geojson(points: list[PhotoPoint], output_path: Path) -> Path:
    """Write *points* as GeoJSON to *output_path* and return it."""
    output_path.write_text(
        json.dumps(photos_to_geojson(points), indent=2), encoding="utf-8"
    )
    logger.info("GeoJSON file created: %s", output_path)
    return output_path


_KML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{name}</name>{placemarks}
  </Document>
</kml>
"""


def photos_to_kml(points: list[PhotoPoint], title: str) -> str:
    """Return a KML document with one placemark per photo.

    The balloon description carries the EXIF thumbnail as a data URI (shown by
    Google Earth Pro; Google My Maps import may strip images but keeps the
    placemark). CDATA is safe here: base64 and the escaped text parts cannot
    contain the ``]]>`` terminator.
    """
    placemarks = []
    for p in points:
        desc: list[str] = []
        if p.thumbnail_b64:
            desc.append(
                f'<img src="data:image/jpeg;base64,{p.thumbnail_b64}" '
                'style="max-width:320px" />'
            )
        if p.timestamp:
            desc.append(escape(p.timestamp))
        camera = camera_summary(p)
        if camera:
            desc.append(escape(camera))
        # No EXIF altitude -> clamp to terrain (a 0 m absolute placemark buries
        # the pin below ground in Google Earth); the altitude value is ignored
        # in that mode, so emit a placeholder 0.
        if p.alt is None:
            alt_mode, alt_coord = "clampToGround", "0"
        else:
            alt_mode, alt_coord = "absolute", f"{p.alt}"
            desc.append(f"altitude: {p.alt:g} m")
        placemarks.append(
            "\n    <Placemark>"
            f"<name>{escape(p.name)}</name>"
            f"<description><![CDATA[{'<br/>'.join(desc)}]]></description>"
            f"<Point><altitudeMode>{alt_mode}</altitudeMode>"
            f"<coordinates>{p.lon},{p.lat},{alt_coord}</coordinates></Point>"
            "</Placemark>"
        )
    return _KML_TEMPLATE.format(name=escape(title), placemarks="".join(placemarks))


def write_photos_kml(points: list[PhotoPoint], output_path: Path, title: str) -> Path:
    """Write *points* as KML to *output_path* and return it."""
    output_path.write_text(photos_to_kml(points, title), encoding="utf-8")
    logger.info("KML file created: %s", output_path)
    return output_path
