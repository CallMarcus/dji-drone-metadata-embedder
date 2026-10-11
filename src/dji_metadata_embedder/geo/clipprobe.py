"""Clip facts for the editor timeline: exact frame rate, frame count,
displayed size, audio, creation time, timecode start and telemetry schema.

One ExifTool header read per clip, group-qualified (``-G1``): DJI MP4s carry
three tracks (video, djmd, dbgi) and ungrouped ``-j`` output lets a later
track's tags shadow the video track's (a plain ``-HandlerType`` on Air 3S
returns the metadata handler).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any

from ..mp4_telemetry import _PARROT_META_TYPE, _run

STANDARD_RATES: tuple[Fraction, ...] = (
    Fraction(24000, 1001),
    Fraction(24),
    Fraction(25),
    Fraction(30000, 1001),
    Fraction(30),
    Fraction(48000, 1001),
    Fraction(48),
    Fraction(50),
    Fraction(60000, 1001),
    Fraction(60),
    Fraction(100),
    Fraction(120000, 1001),
    Fraction(120),
)
RATE_TOLERANCE = 0.01  # fps; 29.97 and 30 are 0.03 apart

_PROBE_TAGS = (
    "-HandlerType",
    "-VideoFrameRate",
    "-TrackDuration",
    "-MediaDuration",
    "-Duration",
    "-ImageWidth",
    "-ImageHeight",
    "-Rotation",
    "-CreateDate",
    "-TimeCode",
    "-MetaFormat",
    "-MetaType",
    "-Category",
)

# "2026:08:15 12:19:32", optional fraction, optional "Z" or "+02:00".
_QT_DATE_RE = re.compile(
    r"(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})(?:\.\d+)?\s*(Z|[+-]\d{2}:\d{2})?$"
)
# "HH:MM:SS:FF" (non-drop) or "HH:MM:SS;FF" (drop-frame separator).
_TIMECODE_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[:;](\d{2})$")
# Same pattern mp4_telemetry.probe uses for the djmd protobuf schema.
_PB_FILE_RE = re.compile(r"pb_file:\s*([^\s;]+\.proto[^\n]*)")


class ClipProbeError(RuntimeError):
    """The clip cannot be placed on a timeline."""


@dataclass(frozen=True)
class ClipFacts:
    path: Path
    rate: Fraction  # exact frames per second
    frames: int
    width: int  # as displayed (rotation applied)
    height: int
    has_audio: bool
    created_utc: datetime | None  # naive UTC
    tc_start: Fraction | None  # seconds; None = starts at zero
    schema: str | None
    tc_note: str | None = None

    @property
    def duration(self) -> Fraction:
        return Fraction(self.frames) / self.rate


def exact_rate(fps: float) -> Fraction:
    """The standard rate ``fps`` approximates, or ClipProbeError. Never rounds
    an unknown rate to a near one: a wrong frame grid misplaces every marker."""
    for rate in STANDARD_RATES:
        if abs(float(rate) - fps) <= RATE_TOLERANCE:
            return rate
    raise ClipProbeError(f"unsupported frame rate {fps:.3f} fps")


def parse_qt_date(value: object) -> datetime | None:
    """QuickTime date (UTC per the spec) as naive UTC; offsets are applied."""
    if not value:
        return None
    m = _QT_DATE_RE.match(str(value).strip())
    if not m:
        return None
    year, month, day, hour, minute, second = (int(g) for g in m.groups()[:6])
    try:
        dt = datetime(year, month, day, hour, minute, second)  # noqa: DTZ001  # naive UTC by contract
    except ValueError:  # 0000:00:00 and other placeholders
        return None
    zone = m.group(7)
    if zone and zone != "Z":
        sign = 1 if zone[0] == "+" else -1
        dt -= sign * timedelta(hours=int(zone[1:3]), minutes=int(zone[4:6]))
    return dt


def _groups(tags: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key, value in tags.items():
        group, sep, name = key.partition(":")
        if sep:
            out.setdefault(group, {})[name] = value
    return out


def _first(
    groups: dict[str, dict[str, Any]], name: str, prefer: str | None = None
) -> Any:
    if prefer is not None and name in groups.get(prefer, {}):
        return groups[prefer][name]
    for values in groups.values():
        if name in values:
            return values[name]
    return None


def _timecode_seconds(value: object, rate: Fraction) -> Fraction | None:
    m = _TIMECODE_RE.match(str(value or "").strip())
    if not m:
        return None
    h, mi, s, f = (int(g) for g in m.groups())
    nominal = round(rate)
    return Fraction((h * 3600 + mi * 60 + s) * nominal + f) / rate


def _schema(groups: dict[str, dict[str, Any]]) -> str | None:
    text = "\n".join(
        str(v)
        for values in groups.values()
        for k, v in values.items()
        if k in ("MetaFormat", "MetaType", "Category")
    )
    if "djmd" in text or "dbgi" in text:
        m = _PB_FILE_RE.search(text)
        return m.group(1).strip() if m else "djmd"
    m = re.search(re.escape(_PARROT_META_TYPE) + r"(\w*)", text)
    if m:
        return f"parrot:videometadata{m.group(1)}"
    return None


def facts_from_tags(path: Path, tags: dict[str, Any]) -> ClipFacts:
    """Build ClipFacts from one ``exiftool -j -G1 -n`` object."""
    groups = _groups(tags)
    handlers = {
        g: str(v.get("HandlerType", "")).lower()
        for g, v in groups.items()
        if g.startswith("Track")
    }
    video = next((g for g in sorted(handlers) if handlers[g].startswith("vide")), None)
    if video is None:
        raise ClipProbeError("no video track")
    fps = _first(groups, "VideoFrameRate", video)
    if fps is None:
        raise ClipProbeError("no frame rate")
    rate = exact_rate(float(fps))
    duration = (
        _first(groups, "TrackDuration", video)
        or _first(groups, "MediaDuration", video)
        or _first(groups, "Duration", "QuickTime")
    )
    if duration is None or float(duration) <= 0:
        raise ClipProbeError("no duration")
    # Round, not floor: float durations land a hair under whole frames.
    frames = round(float(duration) * float(rate))
    width = int(_first(groups, "ImageWidth", video) or 0)
    height = int(_first(groups, "ImageHeight", video) or 0)
    if not width or not height:
        raise ClipProbeError("no frame size")
    rotation = _first(groups, "Rotation", "Composite")
    if rotation is not None and int(float(rotation)) % 180 == 90:
        width, height = height, width
    tc_start: Fraction | None = None
    tc_note: str | None = None
    if any(h.startswith("tmcd") for h in handlers.values()):
        tc_start = _timecode_seconds(_first(groups, "TimeCode"), rate)
        if tc_start is None:
            tc_note = (
                "has a timecode track that could not be read; markers assume "
                "it starts at 00:00:00:00"
            )
    return ClipFacts(
        path=path,
        rate=rate,
        frames=frames,
        width=width,
        height=height,
        has_audio=any(h.startswith("soun") for h in handlers.values()),
        created_utc=parse_qt_date(_first(groups, "CreateDate", "QuickTime")),
        tc_start=tc_start,
        schema=_schema(groups),
        tc_note=tc_note,
    )


def probe_clip(path: Path) -> ClipFacts:
    """Read ClipFacts with one ExifTool header call (no ``-ee`` walk)."""
    path = Path(path)
    proc = _run(
        ["-j", "-G1", "-n", "-api", "LargeFileSupport=1", *_PROBE_TAGS, str(path)]
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise ClipProbeError(
            f"ExifTool could not read it: {proc.stderr.strip()[-200:]}"
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ClipProbeError("ExifTool output was not valid JSON") from exc
    return facts_from_tags(path, data[0])
