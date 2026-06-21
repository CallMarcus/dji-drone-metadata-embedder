import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple
import subprocess

from rich.logging import RichHandler


# Seconds in a quarter hour — the granularity real-world UTC offsets use
# (whole hours plus the :30 and :45 zones like India and Nepal).
_QUARTER_HOUR = 15 * 60

# DJI SRT blocks carry an absolute wall-clock datetime on their own line, with
# the milliseconds separated by either a comma (older firmware) or a dot
# (newer firmware): "2024-01-15 14:30:22,123" / "2026-05-27 13:14:22.911".
_ABS_DATETIME_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})[.,](\d{3})"
)


def _parse_srt_datetime(text: str) -> datetime | None:
    """Return the absolute wall-clock datetime in *text*, or None if absent."""
    m = _ABS_DATETIME_RE.search(text)
    if not m:
        return None
    year, month, day, hour, minute, second, millis = (int(g) for g in m.groups())
    return datetime(year, month, day, hour, minute, second, millis * 1000)


def parse_utc_offset(value: str | None) -> timedelta | None:
    """Parse a CLI UTC-offset string into a :class:`timedelta`.

    Returns ``None`` (meaning "auto-detect") for ``None``, an empty string, or
    ``"auto"``. Otherwise accepts a signed ``HH`` or ``HH:MM`` form such as
    ``"+05:30"``, ``"5:45"`` or ``"-8"``. Raises :class:`ValueError` on any
    other input.
    """
    if value is None:
        return None
    value = value.strip()
    if value == "" or value.lower() == "auto":
        return None
    m = re.fullmatch(r"([+-]?)(\d{1,2})(?::(\d{2}))?", value)
    if not m:
        raise ValueError(f"Invalid UTC offset: {value!r}")
    sign = -1 if m.group(1) == "-" else 1
    hours = int(m.group(2))
    minutes = int(m.group(3) or 0)
    return sign * timedelta(hours=hours, minutes=minutes)


def estimate_utc_offset(
    first_local: datetime,
    last_local: datetime,
    file_mtime_utc: datetime,
) -> timedelta:
    """Estimate the UTC offset of naive DJI SRT timestamps.

    DJI SRT wall-clock timestamps are local with no timezone, while the source
    file's mtime is UTC. We don't know whether the mtime marks the start or the
    end of the recording, so both hypotheses are tested: for each anchor the
    raw offset ``anchor - file_mtime_utc`` is rounded to the nearest quarter
    hour (covering offsets such as UTC+5:30 and UTC+5:45), and the residual
    distance from that boundary is kept. The hypothesis with the smaller
    residual wins, since a genuine offset lands cleanly on a quarter hour.

    All three datetimes must be naive (``file_mtime_utc`` expressed in UTC).

    Re-implemented from the heuristic described in GPStitch
    (https://github.com/Romancha/GPStitch, GPLv3) — idea only, no code copied.
    """
    best_offset = timedelta(0)
    best_residual: float | None = None
    for anchor in (first_local, last_local):
        raw = (anchor - file_mtime_utc).total_seconds()
        rounded = round(raw / _QUARTER_HOUR) * _QUARTER_HOUR
        residual = abs(raw - rounded)
        if best_residual is None or residual < best_residual:
            best_residual = residual
            best_offset = timedelta(seconds=rounded)
    return best_offset


def resolve_utc_offset(
    abs_datetimes: list[datetime],
    tz_offset: timedelta | None,
    file_mtime_utc: datetime,
) -> timedelta | None:
    """Resolve the single local->UTC offset for an SRT file.

    Returns ``None`` when the file carries no absolute datetime (callers then
    fall back to the raw cue time). An explicit *tz_offset* wins; otherwise the
    offset is auto-detected from the file mtime via :func:`estimate_utc_offset`.
    """
    if not abs_datetimes:
        return None
    if tz_offset is not None:
        return tz_offset
    return estimate_utc_offset(abs_datetimes[0], abs_datetimes[-1], file_mtime_utc)


@dataclass
class TelemetrySample:
    """One GPS-fixed SRT block: position, raw cue time, absolute datetime, and
    optional footprint inputs (relative altitude, 35mm-equivalent focal length,
    gimbal yaw/pitch) when the format carries them."""

    lat: float
    lon: float
    alt: float
    cue: str
    dt: datetime | None
    rel_alt: float | None = None
    focal_len: float | None = None
    gimbal_yaw: float | None = None
    gimbal_pitch: float | None = None


def iso6709(lat: float, lon: float, alt: float = 0.0) -> str:
    """Return an ISO 6709 location string for QuickTime metadata."""
    return f"{lat:+08.4f}{lon:+09.4f}{alt:+07.1f}/"


def is_gps_fix(lat: float, lon: float) -> bool:
    """Return ``True`` when ``(lat, lon)`` is a real GPS fix.

    DJI firmware emits ``[latitude: 0.000000] [longitude: 0.000000]`` for every
    frame recorded before the receiver acquires a fix. That exact ``(0, 0)``
    sentinel (Null Island) is never a genuine drone location, so it must be
    excluded from geotagging and exported tracks.
    """
    return not (lat == 0.0 and lon == 0.0)


def _normalize_focal_len(raw: str) -> float | None:
    """Normalize a DJI ``focal_len`` token to a 35mm-equivalent in mm.

    DJI writes it two ways: legacy ``240`` (== 24 mm, x10) and newer literal
    ``24.00``. Values >= 100 are treated as the x10 form. The one ambiguous
    case (a real >= 100 mm-equivalent literal, i.e. a long tele) is rare on the
    supported models; documented in docs/SRT_FORMATS.md.
    """
    try:
        value = float(raw)
    except ValueError:
        return None
    return value / 10.0 if value >= 100.0 else value


def parse_telemetry_samples(srt_path: Path) -> List[TelemetrySample]:
    """Parse an SRT file into :class:`TelemetrySample` records.

    Same GPS extraction as the legacy 4-tuple parser (bracket format, ``GPS(...)``
    compact form, M300 altitude unit suffix, ``(0,0)`` no-fix filtering) plus the
    block's absolute wall-clock datetime when present.
    """
    content = srt_path.read_text(encoding="utf-8")
    blocks = content.strip().split("\n\n")
    samples: List[TelemetrySample] = []
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        ts_line = lines[1]
        ts_match = re.search(r"(\d{2}:\d{2}:\d{2},\d{3})", ts_line)
        timestamp = ts_match.group(1) if ts_match else ""
        tele_line = " ".join(lines[2:])
        if "<font" in tele_line:
            tele_line = re.sub(r"<[^>]+>", "", tele_line)
        dt = _parse_srt_datetime(tele_line)
        rel_match = re.search(r"rel_alt:\s*([+-]?\d+\.?\d*)", tele_line)
        focal_match = re.search(r"\[focal_len\s*:\s*([+-]?\d+\.?\d*)", tele_line)
        gb_yaw_match = re.search(r"gb_yaw:\s*([+-]?\d+\.?\d*)", tele_line)
        gb_pitch_match = re.search(r"gb_pitch:\s*([+-]?\d+\.?\d*)", tele_line)
        rel_alt = float(rel_match.group(1)) if rel_match else None
        focal_len = _normalize_focal_len(focal_match.group(1)) if focal_match else None
        gimbal_yaw = float(gb_yaw_match.group(1)) if gb_yaw_match else None
        gimbal_pitch = float(gb_pitch_match.group(1)) if gb_pitch_match else None
        lat_match = re.search(r"\[latitude:\s*([+-]?\d+\.?\d*)\]", tele_line)
        lon_match = re.search(r"\[longitude:\s*([+-]?\d+\.?\d*)\]", tele_line)
        alt_match = re.search(r"abs_alt:\s*([+-]?\d+\.?\d*)\]", tele_line)
        if not (lat_match and lon_match):
            # Tolerate optional altitude unit suffix (M300 ``0.0M``) and an
            # optional space before ``(`` used by the P4 RTK compact format.
            gps = re.search(
                r"GPS\s*\(([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)[A-Za-z]*\)",
                tele_line,
            )
            if gps:
                lat_match, lon_match = gps, gps
                alt_match = gps
        if lat_match and lon_match:
            lat = float(lat_match.group(1))
            lon = float(
                lon_match.group(2)
                if len(lon_match.groups()) > 1
                else lon_match.group(1)
            )
            alt = float(
                alt_match.group(3)
                if alt_match and len(alt_match.groups()) > 1
                else (alt_match.group(1) if alt_match else 0.0)
            )
            # Skip pre-GPS-lock ``(0, 0)`` no-fix frames so exported tracks do
            # not include Null Island points.
            if is_gps_fix(lat, lon):
                samples.append(
                    TelemetrySample(
                        lat,
                        lon,
                        alt,
                        timestamp,
                        dt,
                        rel_alt=rel_alt,
                        focal_len=focal_len,
                        gimbal_yaw=gimbal_yaw,
                        gimbal_pitch=gimbal_pitch,
                    )
                )
    return samples


def load_samples(path: Path) -> List[TelemetrySample]:
    """Load telemetry samples from a DJI ``.SRT`` or a video (MP4/MOV) source.

    SRT files are parsed directly; videos are read via the ExifTool-backed
    :mod:`dji_metadata_embedder.mp4_telemetry` extractor. Imported lazily to
    avoid a module-load cycle (``mp4_telemetry`` imports from this module).
    """
    from .mp4_telemetry import extract_samples, is_video

    path = Path(path)
    if is_video(path):
        return extract_samples(path)
    return parse_telemetry_samples(path)


def parse_telemetry_points(srt_path: Path) -> List[Tuple[float, float, float, str]]:
    """Parse an SRT file into a list of (lat, lon, alt, timestamp).

    Backwards-compatible 4-tuple view over :func:`parse_telemetry_samples`.
    """
    return [(s.lat, s.lon, s.alt, s.cue) for s in parse_telemetry_samples(srt_path)]


def redact_coords(
    coords: List[Tuple[float, float]], mode: str
) -> List[Tuple[float, float]]:
    """Redact or fuzz coordinate list based on ``mode``."""
    if mode == "drop":
        return []
    if mode == "fuzz":
        return [(round(lat, 3), round(lon, 3)) for lat, lon in coords]
    return coords


@dataclass
class Home:
    """The drone's recorded HOME (launch) point — the operator's location.

    Extracted only on explicit opt-in (``--extract-home``) and always passed
    through :func:`redact_home`. Never written into the embedded MP4.
    """

    lat: float
    lon: float
    alt: float | None = None


# Two documented SRT variants (docs/SRT_FORMATS.md):
#   HOME(39.906206,116.391400) D=5.2m H=1.5m            -> no space, no altitude
#   HOME (-58.847509, -34.232707, -57.98m), D 698.70m,  -> space, altitude with trailing m
_HOME_RE = re.compile(
    r"HOME\s*\(\s*([+-]?\d+\.?\d*)\s*,\s*([+-]?\d+\.?\d*)"
    r"(?:\s*,\s*([+-]?\d+\.?\d*)\s*m?)?\s*\)"
)


def parse_home(text: str) -> "Home | None":
    """Return the first HOME point in SRT *text*, or ``None``.

    The caller is responsible for gating on the opt-in flag; this function does
    not check it. HOME is constant within a file, so the first match is used.
    """
    m = _HOME_RE.search(text)
    if not m:
        return None
    alt = float(m.group(3)) if m.group(3) is not None else None
    return Home(lat=float(m.group(1)), lon=float(m.group(2)), alt=alt)


def redact_home(home: "Home | None", mode: str) -> "Home | None":
    """Apply GPS redaction to a HOME point: ``drop`` -> ``None``; ``fuzz`` ->
    coordinates rounded to 3 decimals (~100 m); ``none`` -> unchanged."""
    if home is None or mode == "drop":
        return None
    if mode == "fuzz":
        return Home(
            lat=round(home.lat, 3),
            lon=round(home.lon, 3),
            alt=round(home.alt, 3) if home.alt is not None else None,
        )
    return home


def apply_redaction(telemetry: dict, mode: str) -> None:
    """Modify ``telemetry`` in place according to the redaction ``mode``."""
    telemetry["gps_coords"] = redact_coords(telemetry.get("gps_coords", []), mode)

    if mode == "drop":
        telemetry["first_gps"] = None
        telemetry["avg_gps"] = None
    elif mode == "fuzz":
        if telemetry.get("first_gps"):
            lat, lon = telemetry["first_gps"]
            telemetry["first_gps"] = (round(lat, 3), round(lon, 3))
        if telemetry.get("avg_gps"):
            lat, lon = telemetry["avg_gps"]
            telemetry["avg_gps"] = (round(lat, 3), round(lon, 3))


def setup_logging(verbose: bool = False, quiet: bool = False, json_logs: bool = False) -> None:
    """Configure application wide logging."""
    level = logging.INFO
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.WARNING

    if json_logs:
        # Use standard logging for JSON output
        logging.basicConfig(
            level=level,
            format="%(message)s",
            datefmt="[%X]",
        )
    else:
        # Use Rich for pretty output
        logging.basicConfig(
            level=level,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(rich_tracebacks=True)],
        )


def get_tool_versions() -> dict[str, str]:
    """Get versions of external tools if available."""
    import os
    import platform
    from pathlib import Path
    
    tools = {
        "ffmpeg": ["ffmpeg", "-version"],
        "exiftool": ["exiftool", "-ver"]
    }
    versions: dict[str, str] = {}
    
    # Add dji-embed bin directory to PATH temporarily (Windows only)
    original_path = os.environ.get("PATH", "")
    path_modified = False
    
    if platform.system() == "Windows":
        bin_dir = Path.home() / "AppData" / "Local" / "dji-embed" / "bin"
        if bin_dir.exists() and str(bin_dir) not in original_path:
            os.environ["PATH"] = str(bin_dir) + os.pathsep + original_path
            path_modified = True
    
    try:
        for name, cmd in tools.items():
            # Check environment variables first (set by bootstrap script)
            env_var = f"DJIEMBED_{name.upper()}_PATH"
            tool_path = os.environ.get(env_var)
            
            if tool_path and Path(tool_path).exists():
                test_cmd = [tool_path] + cmd[1:]
            else:
                test_cmd = cmd
            
            try:
                result = subprocess.run(
                    test_cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                if result.returncode == 0:
                    output = result.stdout or result.stderr
                    # Parse version from output
                    if name == "ffmpeg":
                        # Extract version from "ffmpeg version X.Y.Z" line
                        import re
                        match = re.search(r"ffmpeg version ([^\s]+)", output)
                        if match:
                            versions[name] = match.group(1)
                        else:
                            versions[name] = "unknown"
                    elif name == "exiftool":
                        # ExifTool returns just the version number
                        versions[name] = output.strip()
                    else:
                        versions[name] = "detected"
                else:
                    versions[name] = "not available"
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
                versions[name] = "not available"
    finally:
        # Restore original PATH
        if path_modified:
            os.environ["PATH"] = original_path
    
    return versions


def check_dependencies() -> Tuple[bool, list[str]]:
    """Return ``(True, [])`` if external tools are available."""
    import os
    import platform
    from pathlib import Path

    tools = {"ffmpeg": ["ffmpeg", "-version"], "exiftool": ["exiftool", "-ver"]}
    missing: list[str] = []

    # Add dji-embed bin directory to PATH temporarily (Windows only)
    original_path = os.environ.get("PATH", "")
    path_modified = False

    if platform.system() == "Windows":
        bin_dir = Path.home() / "AppData" / "Local" / "dji-embed" / "bin"
        if bin_dir.exists() and str(bin_dir) not in original_path:
            os.environ["PATH"] = str(bin_dir) + os.pathsep + original_path
            path_modified = True

    try:
        for name, cmd in tools.items():
            # Check environment variables first (set by bootstrap script)
            env_var = f"DJIEMBED_{name.upper()}_PATH"
            tool_path = os.environ.get(env_var)

            if tool_path and Path(tool_path).exists():
                # Use the explicit path from environment variable
                test_cmd = [tool_path] + cmd[1:]
                try:
                    subprocess.run(test_cmd, capture_output=True, check=True)
                    continue  # Tool found, skip to next
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass  # Fall through to normal check

            # Normal check
            try:
                # Use shell=True on Windows to find executables in PATH
                subprocess.run(
                    cmd,
                    capture_output=True,
                    check=True,
                    shell=(platform.system() == "Windows"),
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                missing.append(name)
    finally:
        # Restore original PATH if we modified it
        if path_modified:
            os.environ["PATH"] = original_path

    return (not missing), missing


def parse_dji_srt(srt_path: Path) -> dict:
    """Standalone wrapper around :class:`DJIMetadataEmbedder` parsing."""
    from .embedder import DJIMetadataEmbedder

    embedder = DJIMetadataEmbedder(str(srt_path.parent))
    return embedder.parse_dji_srt(srt_path)
