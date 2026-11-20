"""ExifTool-backed extractor for timed GPS in MP4-family video.

Reads the per-sample telemetry ExifTool decodes — DJI ``djmd``/``dbgi``,
Parrot ``mett``, GoPro GPMF (``gpmd``), and Insta360 trailer / ``camm`` —
and normalises it to the canonical
:class:`~dji_metadata_embedder.utilities.TelemetrySample` model, so the
convert exporters and verify-sun work on sidecar-less footage.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
from datetime import datetime, timedelta
from importlib.resources import files
from pathlib import Path

from .utilities import TelemetrySample, is_gps_fix
from .utils.exiftool import decode_floor, exiftool_exe, exiftool_version

# Back-compat alias: this private name predates the shared resolver in
# utils/exiftool.py. Kept so any external importer of the old symbol still works.
_exiftool_exe = exiftool_exe


class Mp4TelemetryError(RuntimeError):
    """Raised when an MP4's timed metadata cannot be read or decoded."""


# ``.360`` is GoPro Max, ``.insv`` is Insta360, ``.lrv`` is GoPro's low-res
# proxy. All three are ISO BMFF; ExifTool reads GPMF from ``.360``/``.lrv``
# and Insta360 GPS from the ``.insv`` trailer.
VIDEO_SUFFIXES = {".mp4", ".mov", ".360", ".insv", ".lrv"}

# Full-res containers before the ``.lrv`` proxy, so a proxy never wins a
# same-stem choice (playback href or a second flightmap track).
VIDEO_SUFFIX_PREFERENCE = (".mp4", ".mov", ".360", ".insv", ".lrv")

_PROXY_SUFFIXES = {".lrv"}


def is_video(path: Path) -> bool:
    """True when ``path`` is a video we can probe for embedded telemetry."""
    return Path(path).suffix.lower() in VIDEO_SUFFIXES


def video_globs() -> tuple[str, ...]:
    """Case variants of :data:`VIDEO_SUFFIX_PREFERENCE` for directory scans."""
    globs: list[str] = []
    for suffix in VIDEO_SUFFIX_PREFERENCE:
        for pattern in (f"*{suffix}", f"*{suffix.upper()}"):
            if pattern not in globs:
                globs.append(pattern)
    return tuple(globs)


def drop_proxy_duplicates(paths: list[Path]) -> list[Path]:
    """Drop a ``.lrv`` proxy when a full-res file of the same stem is present.

    A lone ``.lrv`` is kept: it carries the same GPMF track as the missing
    full-res file. Input order is preserved.
    """
    primaries = {
        path.with_suffix("")
        for path in paths
        if path.suffix.lower() not in _PROXY_SUFFIXES
    }
    return [
        path
        for path in paths
        if path.suffix.lower() not in _PROXY_SUFFIXES
        or path.with_suffix("") not in primaries
    ]


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
            return datetime.strptime(text, fmt)  # noqa: DTZ007  # naive UTC by contract, see docstring
        except ValueError:
            continue
    return None


def quat_to_heading_pitch(quat: str) -> tuple[float, float]:
    """Camera heading and pitch from a Parrot ``FrameView`` quaternion.

    ExifTool prints it as ``"W X Y Z"`` in Parrot's NED world frame
    (libvideo-metadata: "frame view quaternion in the global frame of
    reference"). Aerospace ZYX Euler angles: heading in degrees clockwise
    from north in ``[0, 360)``, pitch in degrees with negative pointing
    down. Roll is dropped, the stabilised frame view carries none.
    Verified on Anafi 4K footage (2026-09-18): heading tracked the GPS
    course while moving, pitch read -88.5 with the camera straight down
    and 0 when level.
    """
    parts = quat.split()
    if len(parts) != 4:
        raise ValueError(f"expected four quaternion components, got {quat!r}")
    w, x, y, z = (float(part) for part in parts)
    heading = (
        math.degrees(math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))) % 360.0
    )
    sin_pitch = max(-1.0, min(1.0, 2 * (w * y - z * x)))
    pitch = math.degrees(math.asin(sin_pitch))
    return heading, pitch


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

# ExifTool ``-g3`` numbers each embedded sample ``Doc1``, ``Doc2``, … and
# splits a multi-value GPMF GPS5/GPS9 burst into ``Doc1-1``, ``Doc1-2``, …
# under that parent. The parent carries the burst's fix quality.
_DOC_KEY_RE = re.compile(r"^Doc(\d+)(?:-(\d+))?$")

# GoPro stores GPSP on a 0–9999 centimetre scale. ExifTool divides by 100
# and reports ``GPSHPositioningError``, so a missing lock is 99.99. Locked
# Hero 5 samples sit around 4–6, so the cut is that sentinel rather than a
# quality score. GPS9 reports the same sentinel as ``GPSDOP``.
_NO_FIX_POSITION_ERROR = 99.0

# Last 32 bytes of an Insta360 ``.insv`` / ``.mp4`` trailer. ExifTool
# recognises the same magic before it will parse record 0x700 (GPS).
_INSTA360_TRAILER_MAGIC = b"8db42d694ccc418790edff439fe026bf"

# Osmo Action 4/5/6 protobuf schemas (ExifTool DJI.pm). They reuse ``djmd``
# but write ``GPSAltitude``, and only when a GPS remote or the app is paired.
_OSMO_ACTION_SCHEMAS = ("dvtm_ac203", "dvtm_ac204", "dvtm_ac206")


# Optional scalar fields protobuf drops at their default (see the defaults
# comment inside :func:`_samples_from_exiftool`).
_DEFAULTED_KEYS = ("GimbalYaw", "GimbalPitch", "RelativeAltitude")

# Tags that mean ExifTool decoded a sample, including action-cam GPS that
# never writes the DJI absolute-altitude / gimbal keys.
_DECODED_MARKERS = _TELEMETRY_KEYS + (
    "GPSAltitude",
    "GPSMeasureMode",
    "GPSHPositioningError",
    "GPSDOP",
)

# A per-sample document carrying this tag is a Parrot V3 record (ExifTool
# Parrot.pm). Other vendors use the DJI / action-cam tag set below it.
_PARROT_KEY = "FrameView"

# Sample-description MIME type of a Parrot Anafi `mett` metadata track:
# `application/octet-stream;type=com.parrot.videometadata3` (V3, verified on
# Anafi 4K fw 1.8.2); the Anafi Ai writes `...videometadataproto` (untested).
_PARROT_META_TYPE = "com.parrot.videometadata"


def _parrot_sample(doc: dict) -> TelemetrySample | None:
    """Map one Parrot V3 record (ExifTool ``Parrot.pm`` tag names) to a sample.

    Parrot writes every field in every record, so unlike the DJI branch the
    optional fields are never zero-defaulted: a missing ``Elevation`` is
    unknown (``None``), not 0.0. Only ``alt`` falls back to 0.0, because
    :class:`TelemetrySample` requires a float there; the same fallback the
    DJI branch uses.
    ``GPSAltitude`` is EGM96 mean sea level (libvideo-metadata's V3 reader
    stores it as ``altitude_egm96amsl``), ``Elevation`` the drone's estimated
    distance to ground. Returns ``None`` for a record without a fix: the
    ``(0, 0)`` sentinel or Parrot's out-of-range ``500`` marker.
    """
    lat = doc.get("GPSLatitude")
    lon = doc.get("GPSLongitude")
    if lat is None or lon is None:
        return None
    lat, lon = float(lat), float(lon)
    if abs(lat) > 90.0 or abs(lon) > 180.0 or not is_gps_fix(lat, lon):
        return None
    heading, pitch = quat_to_heading_pitch(str(doc[_PARROT_KEY]))
    rel = doc.get("Elevation")
    return TelemetrySample(
        lat,
        lon,
        float(doc.get("GPSAltitude", 0.0)),
        _sample_time_to_cue(doc.get("SampleTime", 0.0)),
        _parse_gps_datetime(doc.get("GPSDateTime", "")),
        rel_alt=float(rel) if rel is not None else None,
        focal_len=None,
        gimbal_yaw=heading,
        gimbal_pitch=pitch,
    )


def _as_float(value: object) -> float | None:
    """``float(value)`` for a JSON number or numeric string, else ``None``."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _measure_mode_locked(mode: object) -> bool:
    """False for measure mode 0 (GoPro GPSF / Insta360 camm "no measurement").

    A missing mode is unknown, not a rejection: DJI and Parrot samples do
    not carry the tag.
    """
    if isinstance(mode, str) and mode.strip().lower() in {"no measurement", "no fix"}:
        return False
    number = _as_float(mode)
    if number is None:
        return True
    return number != 0.0


def _precision_locked(error: object) -> bool:
    """False for the GoPro 99.99 no-lock sentinel. A missing value is unknown."""
    number = _as_float(error)
    if number is None:
        return True
    return number < _NO_FIX_POSITION_ERROR


def _first_present(docs: list[dict], *keys: str) -> object:
    """The first ``keys`` value carried by any document, in document order."""
    for doc in docs:
        for key in keys:
            if key in doc:
                return doc[key]
    return None


def _shift_datetime(value: object, seconds: float) -> datetime | None:
    """Parse ``value`` as GPS time and add ``seconds`` (0 keeps it unchanged)."""
    parsed = _parse_gps_datetime(str(value or ""))
    if parsed is None or seconds == 0.0:
        return parsed
    return parsed + timedelta(seconds=seconds)


def _doc_groups(root: dict) -> list[list[dict]]:
    """Per-sample documents grouped so ``DocN-k`` stays with ``DocN``.

    Sort is by parent index, then the sub-index (the parent itself is 0).
    """
    parsed: list[tuple[int, int, dict]] = []
    for key, value in root.items():
        match = _DOC_KEY_RE.match(key)
        if match is None or not isinstance(value, dict):
            continue
        parsed.append((int(match.group(1)), int(match.group(2) or 0), value))
    parsed.sort(key=lambda item: (item[0], item[1]))
    groups: list[list[dict]] = []
    current_parent: int | None = None
    for parent, sub, doc in parsed:
        if sub == 0 or parent != current_parent or not groups:
            groups.append([doc])
            current_parent = parent
        else:
            groups[-1].append(doc)
    return groups


def _samples_from_exiftool(data: list) -> tuple[list[TelemetrySample], bool]:
    """Map ExifTool ``-g3 -j`` JSON to samples and whether telemetry was decoded.

    ``data`` is ExifTool's JSON: a one-element list whose object holds ``Doc1 …
    DocN`` per-sample sub-documents. A GPMF burst also has ``DocN-1``, ``DocN-2``,
    … for the other GPS5/GPS9 fixes in that second; they inherit the parent's
    fix quality and are spaced across its ``SampleDuration``. Returns
    ``(samples, saw_telemetry)`` where ``saw_telemetry`` is True if any sample
    carried a recognised telemetry field. Samples without a GPS fix — missing
    coordinates, the ``(0, 0)`` sentinel, measure mode 0, or the 99.99
    precision sentinel — are dropped.
    """
    if not data:
        return [], False
    root = data[0]
    groups = _doc_groups(root)
    flat = [doc for group in groups for doc in group]
    # Protobuf omits fields at their default value, so ExifTool emits no tag
    # for a level gimbal (pitch 0), one pointing true north (yaw 0), or an
    # aircraft still on the ground (relative altitude 0). A field the stream
    # carries anywhere is therefore 0.0 where a sample lacks it, not unknown;
    # a field the stream never carries stays None (#546: Air 3S clips run
    # 3 minutes without GimbalPitch and then report 0.2, a minute without
    # RelativeAltitude and then 0.1; GimbalRoll never appears because it is
    # always 0).
    defaults: dict[str, float | None] = {
        key: 0.0 if any(key in doc for doc in flat) else None for key in _DEFAULTED_KEYS
    }
    samples: list[TelemetrySample] = []
    saw_telemetry = False
    for group in groups:
        if any(_PARROT_KEY in doc for doc in group):
            saw_telemetry = True
            for doc in group:
                if _PARROT_KEY not in doc:
                    continue
                sample = _parrot_sample(doc)
                if sample is not None:
                    samples.append(sample)
            continue
        if any(key in doc for doc in group for key in _DECODED_MARKERS):
            saw_telemetry = True
        inherited_mode = _first_present(group, "GPSMeasureMode")
        inherited_error = _first_present(group, "GPSHPositioningError", "GPSDOP")
        base_time = _as_float(_first_present(group, "SampleTime")) or 0.0
        duration = _as_float(_first_present(group, "SampleDuration")) or 0.0
        base_dt = _first_present(group, "GPSDateTime")
        located = [
            doc
            for doc in group
            if doc.get("GPSLatitude") is not None
            and doc.get("GPSLongitude") is not None
        ]
        count = len(located)
        for index, doc in enumerate(located):
            mode = doc.get("GPSMeasureMode", inherited_mode)
            error = doc.get("GPSHPositioningError", doc.get("GPSDOP", inherited_error))
            lat = float(doc["GPSLatitude"])
            lon = float(doc["GPSLongitude"])
            if (
                not is_gps_fix(lat, lon)
                or not _measure_mode_locked(mode)
                or not _precision_locked(error)
            ):
                continue
            if "AbsoluteAltitude" in doc:
                alt = float(doc["AbsoluteAltitude"])
            else:
                alt = float(doc.get("GPSAltitude", 0.0))
            offset = (duration * index / count) if count else 0.0
            if "SampleTime" in doc:
                cue_s = float(doc["SampleTime"])
            else:
                cue_s = base_time + offset
            if "GPSDateTime" in doc:
                when = _parse_gps_datetime(str(doc.get("GPSDateTime", "")))
            else:
                when = _shift_datetime(base_dt, offset)
            rel = doc.get("RelativeAltitude", defaults["RelativeAltitude"])
            gy = doc.get("GimbalYaw", defaults["GimbalYaw"])
            gp = doc.get("GimbalPitch", defaults["GimbalPitch"])
            ts = doc.get("TimeStamp")
            samples.append(
                TelemetrySample(
                    lat,
                    lon,
                    alt,
                    _sample_time_to_cue(cue_s),
                    when,
                    rel_alt=float(rel) if rel is not None else None,
                    focal_len=None,
                    gimbal_yaw=float(gy) if gy is not None else None,
                    gimbal_pitch=float(gp) if gp is not None else None,
                    real_s=float(ts) if ts is not None else None,
                )
            )
    return samples, saw_telemetry


_EXIFTOOL_INSTALL_HINT = (
    "ExifTool not found. Run: dji-embed doctor --install exiftool "
    "(downloads a pinned, checksum-verified copy; no admin rights needed). "
    "Alternatively install it from https://exiftool.org or set "
    "DJIEMBED_EXIFTOOL_PATH to the executable."
)


def exiftool_config_path() -> Path | None:
    """The ExifTool user config bundled with dji-embed, or ``None`` if absent.

    ``data/exiftool.config`` adds tag mappings ExifTool lacks (today: the
    Mavic 4 Pro gimbal block). It is passed with ``-config`` on every call so
    probe and extraction agree; an ExifTool too old to know the table it
    extends simply ignores it.
    """
    try:
        path = Path(str(files(__package__) / "data" / "exiftool.config"))
    except (ModuleNotFoundError, TypeError, ValueError):
        return None
    return path if path.is_file() else None


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    config = exiftool_config_path()
    # ``-config`` must be the very first argument (ExifTool reads it before
    # anything else).
    prefix = ["-config", str(config)] if config is not None else []
    try:
        return subprocess.run(
            [exiftool_exe(), *prefix, *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise Mp4TelemetryError(_EXIFTOOL_INSTALL_HINT) from None


def _run_exiftool_json(path: Path) -> list:
    """Run the embedded-metadata extraction and return parsed JSON (one element)."""
    proc = _run(
        [
            "-ee",
            "-j",
            "-g3",
            "-n",
            "-api",
            "LargeFileSupport=1",
            # QuickTime CreateDate is UTC by spec. A stream without its own
            # wall-clock time (Parrot) gets GPSDateTime synthesised as
            # CreateDate + SampleTime, and without this option ExifTool
            # shifts it by the machine's local zone (#323). DJI protobuf
            # streams carry GPSDateTime themselves and are unaffected.
            "-api",
            "QuickTimeUTC=1",
            str(path),
        ]
    )
    if proc.returncode != 0:
        raise Mp4TelemetryError(
            f"ExifTool failed on {path.name}: {proc.stderr.strip()[-300:]}"
        )
    try:
        return json.loads(proc.stdout) if proc.stdout.strip() else []
    except json.JSONDecodeError as exc:
        raise Mp4TelemetryError(
            f"Could not parse ExifTool JSON for {path.name}: {exc}"
        ) from exc


def _has_insta360_trailer(path: Path) -> bool:
    """True when ``path`` ends with the Insta360 trailer magic.

    ExifTool only emits the GPS record once ``-ee`` walks the trailer, so a
    header probe would otherwise report no telemetry for an ``.insv``.
    """
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            if handle.tell() < len(_INSTA360_TRAILER_MAGIC):
                return False
            handle.seek(-len(_INSTA360_TRAILER_MAGIC), 2)
            return handle.read(len(_INSTA360_TRAILER_MAGIC)) == _INSTA360_TRAILER_MAGIC
    except OSError:
        return False


def probe(path: Path) -> str | None:
    """Cheaply detect an embedded telemetry track without extracting samples.

    Returns a schema descriptor, or ``None`` when the file has no telemetry
    track. DJI: the ``Category`` string of a ``djmd``/``dbgi`` track (e.g.
    ``dvtm_Air3s.proto;model_name:FC9113;…``), or ``"djmd"`` when it has none.
    Parrot: ``parrot:videometadata3`` (the suffix is whatever follows
    :data:`_PARROT_META_TYPE` in the track's MIME type). GoPro GPMF:
    ``gopro:gpmd``. Insta360: ``insta360:camm`` for a ``camm`` handler, or
    ``insta360`` when the file ends with the trailer magic.
    """
    proc = _run(
        [
            "-s",
            # ``-a`` keeps every track. GoPro writes ``gpmd`` and then ``fdsc``;
            # without it ExifTool prints only ``fdsc`` and the GPS track vanishes.
            "-a",
            "-api",
            "LargeFileSupport=1",
            "-MetaFormat",
            "-MetaType",
            "-Category",
            "-HandlerType",
            str(path),
        ]
    )
    out = proc.stdout
    if "djmd" in out or "dbgi" in out:
        m = re.search(r"pb_file:\s*([^\s;]+\.proto[^\n]*)", out)
        return m.group(1).strip() if m else "djmd"
    m = re.search(re.escape(_PARROT_META_TYPE) + r"(\w*)", out)
    if m:
        return f"parrot:videometadata{m.group(1)}"
    if re.search(r"\bgpmd\b", out):
        return "gopro:gpmd"
    if re.search(r"\bcamm\b", out):
        return "insta360:camm"
    if _has_insta360_trailer(path):
        return "insta360"
    return None


def extract_samples(path: Path) -> list[TelemetrySample]:
    """Extract GPS-fixed telemetry samples from a video via ExifTool.

    Raises :class:`Mp4TelemetryError` when there is no telemetry track, or a
    DJI track is present but this ExifTool cannot decode the model, or a
    Parrot, GoPro, Insta360 or Osmo Action track yields nothing. A clip that
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
        if schema.startswith("parrot:"):
            ver = exiftool_version() or "unknown"
            raise Mp4TelemetryError(
                f"Parrot telemetry track ({schema}) in {path.name} decoded no "
                f"samples with ExifTool {ver}. Only the Anafi V3 format "
                f"(parrot:videometadata3) is verified; please open an issue "
                f"with the output of 'exiftool -ee -G1 -s -n FILE'."
            )
        if schema.startswith("gopro:"):
            ver = exiftool_version() or "unknown"
            raise Mp4TelemetryError(
                f"GoPro GPMF track ({schema}) in {path.name} decoded no GPS "
                f"with ExifTool {ver}. Hero 12 has no GPS receiver; Hero 5-11, "
                f"13 and Max record GPS in this track once the camera has a "
                f"fix (see docs/MP4_TIMED_METADATA.md)."
            )
        if schema.startswith("insta360"):
            ver = exiftool_version() or "unknown"
            raise Mp4TelemetryError(
                f"Insta360 metadata ({schema}) in {path.name} decoded no GPS "
                f"with ExifTool {ver}. These cameras record a GPS track only "
                f"when paired with the GPS Action Remote or the phone app "
                f"(see docs/MP4_TIMED_METADATA.md)."
            )
        if any(key in schema for key in _OSMO_ACTION_SCHEMAS):
            raise Mp4TelemetryError(
                f"Osmo Action telemetry ({schema}) in {path.name} decoded no "
                f"GPS. Action cameras record a GPS track only with the GPS "
                f"remote or the DJI app (see docs/MP4_TIMED_METADATA.md)."
            )
        floor = decode_floor(schema)
        ver = exiftool_version() or "unknown"
        raise Mp4TelemetryError(
            f"Telemetry stream ({schema}) in {path.name} needs ExifTool >= "
            f"{floor}; you have {ver}, which decoded no GPS for this model. "
            f"Run: dji-embed doctor --install exiftool "
            f"(see docs/MP4_TIMED_METADATA.md)."
        )
    return []  # decoded, but no GPS fix in this clip
