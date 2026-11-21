import logging
import logging.handlers
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

logger = logging.getLogger(__name__)

# Seconds in a quarter hour — the granularity real-world UTC offsets use
# (whole hours plus the :30 and :45 zones like India and Nepal).
_QUARTER_HOUR = 15 * 60

# Real-world UTC offsets span UTC-12 to UTC+14; a detected offset outside
# +/-14h is proof the file mtime is not the recording time (#259).
_MAX_PLAUSIBLE_OFFSET = timedelta(hours=14)

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
    # Naive on purpose: SRT timestamps are the camera's wall-clock; the UTC
    # offset is applied downstream where the flight's zone is known.
    return datetime(  # noqa: DTZ001
        year, month, day, hour, minute, second, millis * 1000
    )


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
) -> timedelta | None:
    """Estimate the UTC offset of naive DJI SRT timestamps.

    DJI SRT wall-clock timestamps are local with no timezone, while the source
    file's mtime is UTC. We don't know whether the mtime marks the start or the
    end of the recording, so both hypotheses are tested: for each anchor the
    raw offset ``anchor - file_mtime_utc`` is rounded to the nearest quarter
    hour (covering offsets such as UTC+5:30 and UTC+5:45), and the residual
    distance from that boundary is kept. The hypothesis with the smaller
    residual wins, since a genuine offset lands cleanly on a quarter hour.

    Returns ``None`` when the best hypothesis falls outside the plausible
    UTC-12..UTC+14 range (clamped symmetrically to +/-14h): the mtime then
    cannot be the recording time — typically reset by a zip or cloud transfer
    (#259). Callers fall back to raw cue timestamps.

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
    if abs(best_offset) > _MAX_PLAUSIBLE_OFFSET:
        logger.warning(
            "Timezone auto-detection failed: the file mtime does not match the "
            "recording window (implied offset %+.1fh; real timezones are within "
            "UTC-12..UTC+14). This is common after zip/cloud transfers. Pass "
            "--tz-offset for absolute UTC times.",
            best_offset.total_seconds() / 3600,
        )
        return None
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
    """One GPS-fixed telemetry record.

    Position, raw cue time, absolute datetime, and the optional footprint
    inputs (relative altitude, 35mm-equivalent focal length, gimbal yaw/pitch)
    when the format carries them. ``real_s`` is the real recording clock when
    the source has one (DJI djmd ``TimeStamp``).
    """

    lat: float
    lon: float
    alt: float
    cue: str
    dt: datetime | None
    rel_alt: float | None = None
    focal_len: float | None = None
    gimbal_yaw: float | None = None
    gimbal_pitch: float | None = None
    # Real elapsed seconds, arbitrary origin: only spans are meaningful. On
    # slow-motion clips it advances slower than ``cue`` (playback time).
    real_s: float | None = None


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


def parse_telemetry_samples(srt_path: Path) -> list[TelemetrySample]:
    """Parse an SRT file into :class:`TelemetrySample` records.

    Same GPS extraction as the legacy 4-tuple parser (bracket format, ``GPS(...)``
    compact form, M300 altitude unit suffix, ``(0,0)`` no-fix filtering) plus the
    block's absolute wall-clock datetime when present.
    """
    content = srt_path.read_text(encoding="utf-8")
    blocks = content.strip().split("\n\n")
    samples: list[TelemetrySample] = []
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
        if lat_match and lon_match and alt_match is None:
            # Every documented bracket format carries abs_alt right after the
            # coordinates, so its absence means the block was cut mid-write
            # (drone powered off while flushing the final block). Drop the
            # sample rather than fabricate alt=0.0. The GPS(...) compact form
            # (no abs_alt token at all) takes the branch below instead.
            continue
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


def load_samples(path: Path) -> list[TelemetrySample]:
    """Load telemetry samples from an SRT, an Autel ``.ass``, or a video.

    SRT and ``.ass`` files are parsed directly. Videos are read via the
    ExifTool-backed :mod:`dji_metadata_embedder.mp4_telemetry` extractor.
    Imported lazily to avoid a module-load cycle (``mp4_telemetry`` imports
    from this module).
    """
    from .mp4_telemetry import extract_samples, is_video

    path = Path(path)
    if path.suffix.lower() == ".ass":
        return parse_autel_ass_text(path.read_text(encoding="utf-8-sig"))
    if is_video(path):
        return extract_samples(path)
    return parse_telemetry_samples(path)


def parse_telemetry_points(srt_path: Path) -> list[tuple[float, float, float, str]]:
    """Parse an SRT file into a list of (lat, lon, alt, timestamp).

    Backwards-compatible 4-tuple view over :func:`parse_telemetry_samples`.
    """
    return [(s.lat, s.lon, s.alt, s.cue) for s in parse_telemetry_samples(srt_path)]


def redact_coords(
    coords: list[tuple[float, float]], mode: str
) -> list[tuple[float, float]]:
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


# Autel number: optional fraction, and the 2019 firmware bug that writes a
# second minus immediately after the decimal (``-117.-9605``). The sign in
# front of the integer is the real sign; the extra minus is dropped by
# :func:`_normalize_autel_number`.
_AUTEL_NUM = r"([+-]?\d+(?:\.-?\d*)?)"
_AUTEL_HEMI = rf"([NSEW])\s*:\s*{_AUTEL_NUM}"
# Letter form, either axis first: HOME(W: 109.3, N: 40.7) / HOME(S: 33.9, E: 18.4).
_AUTEL_HOME_HEMI_RE = re.compile(rf"HOME\s*\(\s*{_AUTEL_HEMI}\s*,\s*{_AUTEL_HEMI}\s*\)")
# Signed two-component form, longitude first when it is Autel:
# HOME(-117.9606, 33.6324). A closing paren (no third altitude component)
# leaves DJI's ``HOME (lat, lon, altm)`` to the lat-first regex below.
_AUTEL_HOME_SIGNED_RE = re.compile(rf"HOME\s*\(\s*{_AUTEL_NUM}\s*,\s*{_AUTEL_NUM}\s*\)")
# GPS with hemisphere letters, then altitude (optional ``m``).
_AUTEL_GPS_HEMI_RE = re.compile(
    rf"GPS\s*\(\s*{_AUTEL_HEMI}\s*,\s*{_AUTEL_HEMI}\s*,\s*{_AUTEL_NUM}\s*m?"
)
# GPS(lon, lat, alt) with no letters. Only used inside an .ass cue, where
# longitude-first is the Autel convention; DJI SRT GPS is lat-first and is
# parsed elsewhere.
_AUTEL_GPS_SIGNED_RE = re.compile(
    rf"GPS\s*\(\s*{_AUTEL_NUM}\s*,\s*{_AUTEL_NUM}\s*,\s*{_AUTEL_NUM}\s*m?"
)
# G.PRY (pitch, roll, yaw) — same component order as DJI's token. The degree
# symbol is optional. Roll is not stored; footprints use pitch and yaw.
_AUTEL_GPRY_RE = re.compile(
    r"G\.PRY\s*\(\s*([+-]?\d+\.?\d*)\s*°?\s*,\s*"
    r"([+-]?\d+\.?\d*)\s*°?\s*,\s*([+-]?\d+\.?\d*)"
)
_AUTEL_REH_RE = re.compile(r"ReH\s*:\s*([+-]?\d+\.?\d*)")
# 2019.9.8 16:49:24 and 2023-09-12 10:28:07. Not DJI's millisecond form.
_AUTEL_DT_RE = re.compile(
    r"(?<!\d)(\d{4})[.-](\d{1,2})[.-](\d{1,2})[ T](\d{1,2}):(\d{2}):(\d{2})"
)
_ASS_TIME_RE = re.compile(r"(\d+):(\d{2}):(\d{2})\.(\d{1,3})")
# A two-component signed HOME whose magnitudes both fit in a latitude is
# indistinguishable from DJI Format 2 unless the rest of the cue is Autel.
# DJI never writes a hemisphere letter inside GPS(), a ReH token, or a minus
# sign after the decimal point. F.PRY is intentionally absent: DJI Format 2c
# uses it on a latitude-first HOME.
_AUTEL_CONTEXT_RE = re.compile(r"GPS\s*\(\s*[NSEW]\s*:|ReH\s*:|\d+\.-\d+")
_BROKEN_DECIMAL_RE = re.compile(r"(\d)\.-(\d)")


def _normalize_autel_number(raw: str) -> float:
    """Parse an Autel coordinate or altitude, repairing ``-117.-9605``.

    The extra minus sits after the decimal and is not a second sign. The
    sign in front of the integer part is kept.
    """
    return float(_BROKEN_DECIMAL_RE.sub(r"\1.\2", raw.strip()))


def _signed_by_hemisphere(letter: str | None, raw: str) -> float:
    """Apply an ``N``/``S``/``E``/``W`` letter, or keep the numeric sign.

    When a letter is present it wins: ``W: -117.-9605`` and ``W: 109.3``
    are both west. The 2019 letters repeat the sign; the 2023 letters are
    the only sign.
    """
    value = _normalize_autel_number(raw)
    if letter is None:
        return value
    magnitude = abs(value)
    if letter.upper() in ("S", "W"):
        return -magnitude
    return magnitude


def _pair_by_hemisphere(
    letter_a: str, raw_a: str, letter_b: str, raw_b: str
) -> tuple[float, float] | None:
    """Return ``(lat, lon)`` from two lettered components, in either order."""
    coords: dict[str, float] = {}
    for letter, raw in ((letter_a, raw_a), (letter_b, raw_b)):
        if letter.upper() in ("N", "S"):
            axis = "lat"
        elif letter.upper() in ("E", "W"):
            axis = "lon"
        else:
            return None
        if axis in coords:
            return None
        coords[axis] = _signed_by_hemisphere(letter, raw)
    if "lat" not in coords or "lon" not in coords:
        return None
    return coords["lat"], coords["lon"]


def _parse_autel_home(text: str) -> "Home | None":
    """Longitude-first Autel HOME, or ``None`` when the line is DJI's.

    Letter form is unambiguous. The signed two-component form is Autel when
    the first magnitude cannot be a latitude (``|lon| > 90``) or the
    surrounding text carries an Autel marker. Anything else is left for the
    DJI latitude-first regex, including ``HOME (lat, lon, altm)``.
    """
    hemi = _AUTEL_HOME_HEMI_RE.search(text)
    if hemi:
        pair = _pair_by_hemisphere(
            hemi.group(1), hemi.group(2), hemi.group(3), hemi.group(4)
        )
        if pair is None:
            return None
        lat, lon = pair
        return Home(lat=lat, lon=lon)
    signed = _AUTEL_HOME_SIGNED_RE.search(text)
    if signed is None:
        return None
    first = _normalize_autel_number(signed.group(1))
    second = _normalize_autel_number(signed.group(2))
    if abs(second) > 90.0:
        return None
    if abs(first) > 90.0 or _AUTEL_CONTEXT_RE.search(text):
        return Home(lat=second, lon=first)
    return None


def _ass_time_to_cue(value: str) -> str:
    """ASS ``H:MM:SS.cs`` (1–3 fractional digits) to an SRT ``HH:MM:SS,mmm`` cue."""
    match = _ASS_TIME_RE.fullmatch(value.strip())
    if match is None:
        return ""
    hours, minutes, seconds, frac = match.groups()
    millis = int(frac) * (10 ** (3 - len(frac)))
    return f"{int(hours):02d}:{minutes}:{seconds},{millis:03d}"


def _iter_ass_dialogues(text: str):
    """Yield ``(start, end, payload)`` for Dialogue lines inside ``[Events]``."""
    in_events = False
    for raw in text.splitlines():
        line = raw.strip()
        lowered = line.lower()
        if lowered == "[events]":
            in_events = True
            continue
        if in_events and line.startswith("[") and line.endswith("]"):
            break
        if not in_events or not lowered.startswith("dialogue:"):
            continue
        body = line.split(":", 1)[1].lstrip()
        # The text field is last and may itself contain commas.
        parts = body.split(",", 9)
        if len(parts) < 10:
            continue
        yield parts[1].strip(), parts[2].strip(), parts[9]


def _autel_datetime(text: str) -> datetime | None:
    match = _AUTEL_DT_RE.search(text)
    if match is None:
        return None
    year, month, day, hour, minute, second = (int(group) for group in match.groups())
    try:
        # Naive on purpose: Autel writes the camera's wall clock, not UTC.
        return datetime(year, month, day, hour, minute, second)  # noqa: DTZ001
    except ValueError:
        return None


def parse_autel_ass_text(text: str) -> list[TelemetrySample]:
    """Parse an Autel ``.ass`` document into GPS-fixed samples.

    Dialogue payloads are split on the ASS hard break ``\\N``. Both the
    2019 signed style (``GPS(W: -117.-9605, N: 33.6323, -37)``, longitude
    first, broken decimals) and the later letter style (``GPS(W: 109.3, N:
    40.7, 2371.76m)``, unsigned magnitudes) are accepted. Timestamps are
    local. Gimbal ``G.PRY`` is pitch, roll, yaw.
    """
    samples: list[TelemetrySample] = []
    for start, _end, payload in _iter_ass_dialogues(text):
        body = payload.replace("\\N", "\n").replace("\\n", "\n")
        lat: float | None = None
        lon: float | None = None
        alt: float | None = None
        hemi = _AUTEL_GPS_HEMI_RE.search(body)
        if hemi:
            pair = _pair_by_hemisphere(
                hemi.group(1), hemi.group(2), hemi.group(3), hemi.group(4)
            )
            if pair is None:
                continue
            lat, lon = pair
            alt = _normalize_autel_number(hemi.group(5))
        else:
            signed = _AUTEL_GPS_SIGNED_RE.search(body)
            if signed is None:
                continue
            lon = _normalize_autel_number(signed.group(1))
            lat = _normalize_autel_number(signed.group(2))
            alt = _normalize_autel_number(signed.group(3))
        if abs(lat) > 90.0 or abs(lon) > 180.0 or not is_gps_fix(lat, lon):
            continue
        relative = _AUTEL_REH_RE.search(body)
        pry = _AUTEL_GPRY_RE.search(body)
        samples.append(
            TelemetrySample(
                lat,
                lon,
                alt,
                _ass_time_to_cue(start),
                _autel_datetime(body),
                rel_alt=float(relative.group(1)) if relative else None,
                gimbal_pitch=float(pry.group(1)) if pry else None,
                gimbal_yaw=float(pry.group(3)) if pry else None,
            )
        )
    return samples


# Every Autel cue carries a GPS( token; ordinary captions never do.
_AUTEL_GPS_TOKEN_RE = re.compile(r"GPS\s*\(")


def is_autel_ass(path: Path) -> bool:
    """True when an ``.ass`` file is Autel telemetry, not ordinary captions.

    ``.ass`` is a general subtitle format, so a folder of edited clips can
    hold caption files that are nobody's flight log. A file that cannot be
    read or decoded counts as telemetry: the loader then reports it, which
    is better than dropping a real sidecar without a word.
    """
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return True
    return any(
        _AUTEL_GPS_TOKEN_RE.search(payload)
        for _start, _end, payload in _iter_ass_dialogues(text)
    )


def autel_ass_to_srt(text: str) -> str:
    """Render Autel ASS dialogue cues as an SRT document.

    Cue times become ``HH:MM:SS,mmm`` and ``\\N`` hard breaks become real
    newlines. The payload text is kept as the drone wrote it (including a
    broken decimal); this is the subtitle track, not the parsed track.
    """
    blocks: list[str] = []
    for index, (start, end, payload) in enumerate(_iter_ass_dialogues(text), start=1):
        body = payload.replace("\\N", "\n").replace("\\n", "\n").strip()
        cue_start = _ass_time_to_cue(start)
        cue_end = _ass_time_to_cue(end) or cue_start
        blocks.append(f"{index}\n{cue_start} --> {cue_end}\n{body}\n")
    return "\n".join(blocks)


# Two documented SRT variants (docs/SRT_FORMATS.md):
#   HOME(39.906206,116.391400) D=5.2m H=1.5m            -> no space, no altitude
#   HOME (-58.847509, -34.232707, -57.98m), D 698.70m,  -> space, altitude with trailing m
# Latitude first. Autel HOME is longitude-first and is handled by
# :func:`_parse_autel_home` before this regex runs; applying this pattern to
# ``HOME(-117.9606, 33.6324)`` would swap the axes.
_HOME_RE = re.compile(
    r"HOME\s*\(\s*([+-]?\d+\.?\d*)\s*,\s*([+-]?\d+\.?\d*)"
    r"(?:\s*,\s*([+-]?\d+\.?\d*)\s*m?)?\s*\)"
)


def parse_home(text: str) -> "Home | None":
    """Return the first HOME point in *text*, or ``None``.

    Autel lines are tried first. They are longitude-first (the opposite of
    every DJI family), so the DJI regex above would swap their axes. The
    caller is responsible for gating on the opt-in flag; this function does
    not check it. HOME is constant within a file, so the first match is used.
    """
    autel = _parse_autel_home(text)
    if autel is not None:
        return autel
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
    if "home" in telemetry:
        telemetry["home"] = redact_home(telemetry["home"], mode)

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


def setup_logging(
    verbose: bool = False,
    quiet: bool = False,
    json_logs: bool = False,
) -> None:
    """Configure application wide logging.

    All log output goes to stderr (issue #282): stdout is reserved for real
    command output — summaries, exported data, ``--progress jsonl`` events.
    The json_logs branch already logs to stderr (logging's default); the
    Rich branch needs an explicit stderr console because RichHandler's
    default console writes to stdout.
    """
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
            handlers=[
                RichHandler(
                    rich_tracebacks=True,
                    console=Console(stderr=True),
                )
            ],
        )


def make_logging_nonblocking(
    target: logging.Logger | None = None,
) -> logging.handlers.QueueListener | None:
    """Move *target*'s handler I/O onto a sacrificial listener thread.

    A long-lived server command launched by the GUI logs to a stderr pipe
    the GUI may never read; once the pipe fills, the next log write blocks
    the thread that made it — inside panoedit's save chain that froze every
    later save until the app was closed (#490). After this call the calling
    thread only ever enqueues; the listener thread does the real writes,
    and if those wedge, only the listener wedges.

    The listener thread is a daemon and is deliberately never joined at
    exit: joining would trade the save deadlock for a shutdown hang on the
    same wedged pipe. (``logging.shutdown`` may still flush the wrapped
    handlers at exit via ``logging._handlerList`` — acceptable, since by
    then nothing is holding application locks.) Two known costs of the
    stock ``QueueHandler``: records cross the queue pre-formatted with
    ``exc_info`` stripped, so RichHandler renders plain rather than rich
    tracebacks, and ``args`` are burned into the message string. Both are
    cosmetic here. Returns the listener, or ``None`` when there was
    nothing to wrap (no handlers, or already fully wrapped).
    """
    import queue

    log = target if target is not None else logging.getLogger()
    queued = [h for h in log.handlers if isinstance(h, logging.handlers.QueueHandler)]
    handlers = [h for h in log.handlers if h not in queued]
    if not handlers:
        return None
    q: queue.SimpleQueue = queue.SimpleQueue()
    listener = logging.handlers.QueueListener(q, *handlers, respect_handler_level=True)
    # Existing queue handlers stay wired: dropping one would orphan its
    # listener and silently cut off every handler behind it.
    log.handlers = [*queued, logging.handlers.QueueHandler(q)]
    listener.start()
    return listener


def get_tool_versions() -> dict[str, str]:
    """Get versions of external tools if available."""
    import os
    import platform
    from pathlib import Path

    tools = {"ffmpeg": ["ffmpeg", "-version"], "exiftool": ["exiftool", "-ver"]}
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

            if name == "exiftool":
                # Shared resolver: env override → provisioned copy → PATH
                from .utils.exiftool import exiftool_exe

                test_cmd = [exiftool_exe()] + cmd[1:]
            elif tool_path and Path(tool_path).exists():
                test_cmd = [tool_path] + cmd[1:]
            else:
                test_cmd = cmd

            try:
                result = subprocess.run(
                    test_cmd,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
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
            except (
                subprocess.TimeoutExpired,
                subprocess.SubprocessError,
                FileNotFoundError,
            ):
                versions[name] = "not available"
    finally:
        # Restore original PATH
        if path_modified:
            os.environ["PATH"] = original_path

    return versions


def check_dependencies() -> tuple[bool, list[str]]:
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

            # Copy provisioned via `dji-embed doctor --install exiftool`
            if name == "exiftool":
                from .utils.provision import provisioned_exiftool

                prov = provisioned_exiftool()
                if prov is not None:
                    try:
                        subprocess.run(
                            [str(prov), "-ver"], capture_output=True, check=True
                        )
                        continue  # Tool found, skip to next
                    except (subprocess.CalledProcessError, OSError):
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
