"""ExifTool-backed extractor for DJI MP4 timed metadata (djmd/dbgi).

Reads the per-sample protobuf telemetry ExifTool decodes from a DJI MP4/MOV and
normalises it to the canonical :class:`~dji_metadata_embedder.utilities.TelemetrySample`
model, so the convert exporters and verify-sun work on sidecar-less footage.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from .utilities import TelemetrySample, is_gps_fix
from .utils.exiftool import decode_floor, exiftool_exe, exiftool_version

# Back-compat alias: this private name predates the shared resolver in
# utils/exiftool.py. Kept so any external importer of the old symbol still works.
_exiftool_exe = exiftool_exe


class Mp4TelemetryError(RuntimeError):
    """Raised when an MP4's timed metadata cannot be read or decoded."""


VIDEO_SUFFIXES = {".mp4", ".mov"}


def is_video(path: Path) -> bool:
    """True when ``path`` is a video we can probe for embedded telemetry."""
    return Path(path).suffix.lower() in VIDEO_SUFFIXES


def _sample_time_to_cue(seconds: float) -> str:
    """Format elapsed ``SampleTime`` seconds as an SRT-style ``HH:MM:SS,mmm`` cue."""
    total_ms = int(float(seconds) * 1000)
    ms = total_ms % 1000
    total_s = total_ms // 1000
    h, rem = divmod(total_s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _parse_gps_datetime(value: str) -> datetime | None:
    """Parse ExifTool ``GPSDateTime`` (``2026:05:16 23:55:53.017Z``) as naive UTC.

    Returns ``None`` when the string is missing or unparseable. The result is
    timezone-naive to match the SRT ``dt`` convention; for video sources it is
    already UTC, so consumers apply a zero offset.
    """
    if not value:
        return None
    text = value.strip().rstrip("Z").strip()
    for fmt in ("%Y:%m:%d %H:%M:%S.%f", "%Y:%m:%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


# Mapped per-sample tags other than SampleTime. Presence of any of these on any
# Doc means ExifTool decoded the protobuf (vs. an unsupported model where only
# SampleTime survives).
_TELEMETRY_KEYS = (
    "GPSLatitude",
    "GPSLongitude",
    "AbsoluteAltitude",
    "RelativeAltitude",
    "GimbalYaw",
    "GimbalPitch",
)

_DOC_KEY_RE = re.compile(r"^Doc(\d+)$")


def _samples_from_exiftool(data: list) -> tuple[list[TelemetrySample], bool]:
    """Map ExifTool ``-g3 -j`` JSON to samples and whether telemetry was decoded.

    ``data`` is ExifTool's JSON: a one-element list whose object holds ``Doc1 …
    DocN`` per-sample sub-documents. Returns ``(samples, saw_telemetry)`` where
    ``saw_telemetry`` is True if any sample carried a recognised telemetry field.
    Samples without a GPS fix (missing or ``(0, 0)``) are dropped.
    """
    if not data:
        return [], False
    root = data[0]
    docs = sorted(
        ((m.group(1), v) for k, v in root.items() if (m := _DOC_KEY_RE.match(k))),
        key=lambda kv: int(kv[0]),
    )
    samples: list[TelemetrySample] = []
    saw_telemetry = False
    for _, doc in docs:
        if any(key in doc for key in _TELEMETRY_KEYS):
            saw_telemetry = True
        lat = doc.get("GPSLatitude")
        lon = doc.get("GPSLongitude")
        if lat is None or lon is None:
            continue
        lat, lon = float(lat), float(lon)
        if not is_gps_fix(lat, lon):
            continue
        alt = float(doc.get("AbsoluteAltitude", 0.0))
        rel = doc.get("RelativeAltitude")
        gy = doc.get("GimbalYaw")
        gp = doc.get("GimbalPitch")
        samples.append(
            TelemetrySample(
                lat,
                lon,
                alt,
                _sample_time_to_cue(doc.get("SampleTime", 0.0)),
                _parse_gps_datetime(doc.get("GPSDateTime", "")),
                rel_alt=float(rel) if rel is not None else None,
                focal_len=None,
                gimbal_yaw=float(gy) if gy is not None else None,
                gimbal_pitch=float(gp) if gp is not None else None,
            )
        )
    return samples, saw_telemetry


_EXIFTOOL_INSTALL_HINT = (
    "ExifTool not found. Run: dji-embed doctor --install exiftool "
    "(downloads a pinned, checksum-verified copy; no admin rights needed). "
    "Alternatively install it from https://exiftool.org or set "
    "DJIEMBED_EXIFTOOL_PATH to the executable."
)


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [exiftool_exe(), *args], capture_output=True, text=True
        )
    except FileNotFoundError:
        raise Mp4TelemetryError(_EXIFTOOL_INSTALL_HINT) from None


def _run_exiftool_json(path: Path) -> list:
    """Run the embedded-metadata extraction and return parsed JSON (one element)."""
    proc = _run(
        ["-ee", "-j", "-g3", "-n", "-api", "LargeFileSupport=1", str(path)]
    )
    if proc.returncode != 0:
        raise Mp4TelemetryError(
            f"ExifTool failed on {path.name}: {proc.stderr.strip()[-300:]}"
        )
    try:
        return json.loads(proc.stdout) if proc.stdout.strip() else []
    except json.JSONDecodeError as exc:
        raise Mp4TelemetryError(f"Could not parse ExifTool JSON for {path.name}: {exc}") from exc


def probe(path: Path) -> str | None:
    """Cheaply detect an embedded telemetry track without extracting samples.

    Returns the schema descriptor (e.g. ``dvtm_Air3s.proto;model_name:FC9113;…``)
    when the MP4 carries a ``djmd``/``dbgi`` metadata track, else ``None``.
    """
    proc = _run(
        ["-s", "-api", "LargeFileSupport=1", "-MetaFormat", "-Category", str(path)]
    )
    out = proc.stdout
    if "djmd" not in out and "dbgi" not in out:
        return None
    m = re.search(r"pb_file:\s*([^\s;]+\.proto[^\n]*)", out)
    return m.group(1).strip() if m else "djmd"


def extract_samples(path: Path) -> list[TelemetrySample]:
    """Extract GPS-fixed telemetry samples from an MP4/MOV via ExifTool.

    Raises :class:`Mp4TelemetryError` when there is no telemetry track, or a
    track is present but this ExifTool cannot decode the model. A clip that
    decodes but never acquired a GPS fix yields an empty list (not an error).
    """
    path = Path(path)
    samples, saw_telemetry = _samples_from_exiftool(_run_exiftool_json(path))
    if samples:
        return samples
    schema = probe(path)
    if schema is None:
        raise Mp4TelemetryError(
            f"No embedded telemetry found in {path.name}; is there a sidecar "
            f".SRT for this clip?"
        )
    if not saw_telemetry:
        floor = decode_floor(schema)
        ver = exiftool_version() or "unknown"
        raise Mp4TelemetryError(
            f"Telemetry stream ({schema}) in {path.name} needs ExifTool >= "
            f"{floor}; you have {ver}, which decoded no GPS for this model. "
            f"Run: dji-embed doctor --install exiftool "
            f"(see docs/MP4_TIMED_METADATA.md)."
        )
    return []  # decoded, but no GPS fix in this clip
