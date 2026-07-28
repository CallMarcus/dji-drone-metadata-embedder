"""Flight-log CSV ingestion: true gimbal attitude for SRT-only drones (#374).

Mini-series drones write no gimbal attitude anywhere on the SD card; it
lives in the encrypted phone/RC flight record, which every decoder
(Flight Reader, Airdata, PhantomHelp, ...) can export as CSV. This module
ingests that CSV and merges per-sample gimbal pitch/yaw into a flight's
track points, upgrading the 3D map's labelled estimates to measurements.

Vendor-neutral by design — no decoder is endorsed or special-cased:

* Columns are matched **by semantics, never by position or exact header**:
  at least one producer lets users rename and reorder every field, and its
  own developer advises against relying on a stable schema.
* Numbers are **locale-aware** (decimal comma or dot): exports use the
  Windows locale of whoever produced them, permanently.
* Unparseable values **fail loudly, never silently as missing** — the #374
  spike proved a skip-on-error parser degrades a complete dataset into a
  plausible-looking sparse one with no exception raised anywhere.
"""

from __future__ import annotations

import csv
import re
from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

from .geometry import haversine_m
from .track import Track

__all__ = [
    "FlightLog",
    "FlightLogError",
    "LogRow",
    "MergeReport",
    "merge_gimbal",
    "merge_into_flights",
    "parse_flight_log",
]


class FlightLogError(ValueError):
    """A flight-log CSV that cannot be used, with the reason said plainly."""


@dataclass
class LogRow:
    """One flight-log sample: a clock plus whatever attitude it carried."""

    utc: datetime | None
    local: datetime | None
    pitch: float | None
    yaw: float | None
    lat: float | None
    lon: float | None


@dataclass
class FlightLog:
    """A parsed flight-log export: rows on one declared time base."""

    name: str
    time_base: str  # "utc" (exact join) or "local" (offset must be derived)
    rows: list[LogRow]
    columns: dict[str, str] = field(default_factory=dict)


@dataclass
class MergeReport:
    """What :func:`merge_gimbal` did, for the CLI to say out loud."""

    merged: bool
    matched: int = 0
    mode: str | None = None  # "utc" | "derived"
    offset: timedelta | None = None
    gps_median_m: float | None = None
    reason: str | None = None


# Columns that look like coordinates but are not the aircraft's position.
_NOT_AIRCRAFT = ("home", "rc", "remote", "tablet")

_ADVICE = (
    "enable the UTC timestamp and the gimbal pitch/yaw fields in the "
    "decoder's export settings (in Flight Reader: GIMBAL.pitch and "
    "GIMBAL.yaw, plus the UTC option under Logs/Reports)"
)


def _tokens(header: str) -> set[str]:
    """A header's semantic word set: ``CUSTOM.updateTime [local]`` ->
    ``{custom, update, time, local}``.

    Tokenised (camelCase and punctuation split) rather than substring-
    matched, because substrings lie: ``updateTime`` *contains* both
    ``date`` and ``datetime`` yet is neither.
    """
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", header)
    return {t.lower() for t in re.split(r"[^A-Za-z0-9]+", spaced) if t}


def _find(
    headers: Sequence[str],
    *needles: str,
    exclude: tuple[str, ...] = (),
) -> str | None:
    """First header whose tokens carry every needle and no exclusion."""
    for h in headers:
        toks = _tokens(h)
        if any(x in toks for x in exclude):
            continue
        if all(n in toks for n in needles):
            return h
    return None


def _number(raw: str, column: str, line: int) -> float | None:
    """Locale-aware float: empty is missing, garbage is an error.

    Accepts ``.`` or ``,`` as the decimal separator (the export follows the
    producing machine's Windows locale). A value carrying both separators
    is refused rather than guessed at.
    """
    s = raw.strip()
    if not s:
        return None
    if "," in s and "." in s:
        raise FlightLogError(
            f"column {column!r}, line {line}: {raw!r} mixes '.' and ',' — "
            "cannot tell the decimal separator apart"
        )
    try:
        return float(s.replace(",", "."))
    except ValueError:
        raise FlightLogError(
            f"column {column!r}, line {line}: {raw!r} is not a number. "
            "Values are never skipped silently — fix the export or remove "
            "the broken row."
        ) from None


_TIME_RE = re.compile(
    r"^(\d{1,2}):(\d{2}):(\d{2})(?:[.,](\d+))?\s*([ap]m)?$", re.IGNORECASE
)


def _parse_clock(raw: str, column: str, line: int) -> tuple[int, int, int, int]:
    """A wall-clock time, 24-hour or 12-hour, locale-decimal fraction OK."""
    m = _TIME_RE.match(raw.strip())
    if not m:
        raise FlightLogError(
            f"column {column!r}, line {line}: {raw!r} is not a time of day"
        )
    hour, minute, sec = int(m.group(1)), int(m.group(2)), int(m.group(3))
    frac = m.group(4) or ""
    micro = int(frac.ljust(6, "0")[:6]) if frac else 0
    half = (m.group(5) or "").lower()
    if half == "pm" and hour != 12:
        hour += 12
    elif half == "am" and hour == 12:
        hour = 0
    return hour, minute, sec, micro


def _parse_date(raw: str, column: str, line: int) -> tuple[int, int, int]:
    """A calendar date; ambiguous day/month orders are refused, not guessed."""
    s = raw.strip()
    if m := re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$", s):
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    if m := re.match(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{4})$", s):
        a, b, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a > 12 and b <= 12:
            return year, b, a  # unambiguously D/M/Y
        if b > 12 and a <= 12:
            return year, a, b  # unambiguously M/D/Y
        if a == b:
            return year, a, b
        raise FlightLogError(
            f"column {column!r}, line {line}: {raw!r} is ambiguous (day and "
            f"month cannot be told apart); {_ADVICE} for an exact join"
        )
    raise FlightLogError(
        f"column {column!r}, line {line}: {raw!r} is not a date"
    )


def _parse_datetime(raw: str, column: str, line: int) -> datetime:
    """A combined date + wall-clock value (``2026-07-27 12:00:00.0``)."""
    s = raw.strip().removesuffix("Z").replace("T", " ")
    date_part, _, time_part = s.partition(" ")
    if not time_part:
        raise FlightLogError(
            f"column {column!r}, line {line}: {raw!r} has no time of day"
        )
    year, month, day = _parse_date(date_part, column, line)
    hour, minute, sec, micro = _parse_clock(time_part, column, line)
    return datetime(year, month, day, hour, minute, sec, micro)


def _normalize_yaw(deg: float) -> float:
    """Fold any yaw/heading into signed [-180, 180] true-north degrees."""
    return (deg + 180.0) % 360.0 - 180.0


def parse_flight_log(path: Path | str) -> FlightLog:
    """Parse a flight-log CSV export into a :class:`FlightLog`.

    Raises :class:`FlightLogError` — always with the concrete fix spelled
    out — when the export lacks the columns this feature needs or carries
    a value that cannot be parsed.
    """
    src = Path(path)
    # utf-8-sig eats the BOM Windows exporters prepend.
    text = src.read_text(encoding="utf-8-sig")
    delimiter = ";" if text.split("\n", 1)[0].count(";") >= 2 else ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    headers = reader.fieldnames or []

    pitch_col = _find(headers, "gimbal", "pitch")
    yaw_col = _find(headers, "gimbal", "yaw", exclude=("360",)) or _find(
        headers, "gimbal", "heading"
    )
    yaw_360_col = None if yaw_col else _find(headers, "gimbal", "yaw")
    if pitch_col is None or (yaw_col is None and yaw_360_col is None):
        raise FlightLogError(
            f"{src.name}: no gimbal pitch/yaw columns found — {_ADVICE}. "
            f"Columns present: {', '.join(headers) or '(none)'}"
        )
    yaw_col = yaw_col or yaw_360_col
    assert yaw_col is not None

    utc_col = _find(headers, "utc")
    datetime_col = _find(headers, "datetime", exclude=("utc",))
    date_col = _find(headers, "date", exclude=("datetime",))
    time_col = _find(headers, "time", "local", exclude=("date",)) or _find(
        headers, "time", exclude=("date", "datetime", "fly")
    )
    if utc_col is None and datetime_col is None and (
        date_col is None or time_col is None
    ):
        raise FlightLogError(
            f"{src.name}: no timestamp columns found — the merge is aligned "
            f"by time, so {_ADVICE}. A UTC timestamp gives an exact join."
        )

    lat_col = _find(headers, "latitude", exclude=_NOT_AIRCRAFT)
    lon_col = _find(headers, "longitude", exclude=_NOT_AIRCRAFT)

    columns = {
        "pitch": pitch_col,
        "yaw": yaw_col,
        **({"utc": utc_col} if utc_col else {}),
        **({"latitude": lat_col} if lat_col else {}),
    }

    rows: list[LogRow] = []
    for line_no, rec in enumerate(reader, start=2):
        if all(not (v or "").strip() for v in rec.values()):
            continue  # a structurally blank line, not data
        utc = local = None
        if utc_col:
            utc = _parse_datetime(rec[utc_col], utc_col, line_no)
        elif datetime_col:
            local = _parse_datetime(rec[datetime_col], datetime_col, line_no)
        else:
            assert date_col is not None and time_col is not None
            year, month, day = _parse_date(rec[date_col], date_col, line_no)
            hour, minute, sec, micro = _parse_clock(
                rec[time_col], time_col, line_no
            )
            local = datetime(year, month, day, hour, minute, sec, micro)
        yaw = _number(rec[yaw_col], yaw_col, line_no)
        rows.append(
            LogRow(
                utc=utc,
                local=local,
                pitch=_number(rec[pitch_col], pitch_col, line_no),
                yaw=None if yaw is None else _normalize_yaw(yaw),
                lat=_number(rec[lat_col], lat_col, line_no) if lat_col else None,
                lon=_number(rec[lon_col], lon_col, line_no) if lon_col else None,
            )
        )
    if not rows:
        raise FlightLogError(f"{src.name}: the export contains no data rows")
    time_base = "utc" if utc_col else "local"
    rows.sort(key=lambda r: (r.utc or r.local or datetime.min))
    return FlightLog(name=src.name, time_base=time_base, rows=rows,
                     columns=columns)


# A track point pairs with the nearest log row inside this window. Flight
# logs sample at ~5 Hz and display tracks at ~1 Hz, so a second of slack
# tolerates both cadences without ever bridging distinct flights.
_TOLERANCE_S = 1.0

# The derived-offset join snaps to 15-minute steps (covers :30/:45 zones);
# it therefore assumes recording started within ~7 minutes of the log.
_OFFSET_STEP_S = 900

# Wider than --redact fuzz's ~100 m coarsening, far tighter than "a
# different flight": a log whose GPS track sits beyond this is refused.
_GPS_LIMIT_M = 500.0


def merge_gimbal(track: Track, log: FlightLog) -> MergeReport:
    """Merge *log*'s gimbal attitude into *track*, aligned by time.

    SRT-borne gimbal values always win — only ``None`` fields are filled,
    so a log can upgrade an estimate but never overwrite a measurement.
    The report says which join was used: ``utc`` (exact) or ``derived``
    (offset inferred by snapping the start difference to 15 minutes).
    """
    pts = [p for p in track.points if p.utc is not None]
    if not pts:
        return MergeReport(
            merged=False,
            reason="the flight has no resolved UTC to align by",
        )
    if log.time_base == "utc":
        mode, offset = "utc", timedelta(0)
        stamped = [(r.utc, r) for r in log.rows if r.utc is not None]
    else:
        first_local = next(
            (r.local for r in log.rows if r.local is not None), None
        )
        if first_local is None:
            return MergeReport(merged=False, reason="the log has no timestamps")
        raw = (first_local - pts[0].utc).total_seconds()  # type: ignore[operator]
        offset = timedelta(
            seconds=round(raw / _OFFSET_STEP_S) * _OFFSET_STEP_S
        )
        mode = "derived"
        stamped = [
            (r.local - offset, r) for r in log.rows if r.local is not None
        ]
    if not stamped:
        return MergeReport(merged=False, reason="the log has no timestamps")
    stamped.sort(key=lambda tr: tr[0])
    times = [t for t, _ in stamped]

    t0, t1 = pts[0].utc, pts[-1].utc
    assert t0 is not None and t1 is not None
    if times[-1] < t0 - timedelta(seconds=_TOLERANCE_S) or times[0] > (
        t1 + timedelta(seconds=_TOLERANCE_S)
    ):
        return MergeReport(
            merged=False,
            mode=mode,
            offset=offset,
            reason="the log covers a different time window than this flight",
        )

    pairs: list[tuple[int, LogRow]] = []
    dists: list[float] = []
    for i, p in enumerate(track.points):
        if p.utc is None:
            continue
        k = bisect_left(times, p.utc)
        best: tuple[float, LogRow] | None = None
        for j in (k - 1, k):
            if 0 <= j < len(times):
                dt = abs((times[j] - p.utc).total_seconds())
                if best is None or dt < best[0]:
                    best = (dt, stamped[j][1])
        if best is None or best[0] > _TOLERANCE_S:
            continue
        row = best[1]
        pairs.append((i, row))
        if row.lat is not None and row.lon is not None:
            dists.append(haversine_m(p.lat, p.lon, row.lat, row.lon))

    if not pairs:
        return MergeReport(
            merged=False,
            mode=mode,
            offset=offset,
            reason="no log samples land within a second of the flight's points",
        )
    gps_median = round(median(dists), 1) if dists else None
    if gps_median is not None and gps_median > _GPS_LIMIT_M:
        return MergeReport(
            merged=False,
            mode=mode,
            offset=offset,
            gps_median_m=gps_median,
            reason=(
                f"GPS mismatch: the log's track sits a median {gps_median:.0f} m "
                "from this flight — it looks like a different flight"
            ),
        )
    for i, row in pairs:
        p = track.points[i]
        if p.gimbal_yaw is None and row.yaw is not None:
            p.gimbal_yaw = row.yaw
        if p.gimbal_pitch is None and row.pitch is not None:
            p.gimbal_pitch = row.pitch
    return MergeReport(
        merged=True,
        matched=len(pairs),
        mode=mode,
        offset=offset,
        gps_median_m=gps_median,
    )


def merge_into_flights(
    tracks: list[Track], log: FlightLog
) -> tuple[MergeReport, Track | None]:
    """Merge *log* into the closest-aligned flight of *tracks*.

    Candidates are tried nearest-clock-first, so when a local-only log's
    snapped offset would let it align with more than one same-day flight,
    the one whose start actually agrees wins; :func:`merge_gimbal`'s
    overlap and GPS refusals still apply to each attempt. Returns the
    winning report and track, or the last refusal and ``None``.
    """
    candidates = [
        t for t in tracks if any(p.utc is not None for p in t.points)
    ]
    if not candidates:
        return (
            MergeReport(
                merged=False,
                reason="no flight has a resolved clock to align by",
            ),
            None,
        )
    first = log.rows[0]
    log_start = first.utc or first.local
    assert log_start is not None  # parse_flight_log guarantees a time base

    def closeness(t: Track) -> float:
        t0 = next(p.utc for p in t.points if p.utc is not None)
        assert t0 is not None
        raw = (log_start - t0).total_seconds()
        if log.time_base == "utc":
            return abs(raw)
        return abs(raw - round(raw / _OFFSET_STEP_S) * _OFFSET_STEP_S)

    last: MergeReport | None = None
    for t in sorted(candidates, key=closeness):
        report = merge_gimbal(t, log)
        if report.merged:
            return report, t
        last = report
    assert last is not None
    return last, None
