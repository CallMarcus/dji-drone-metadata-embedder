"""Fetch decrypted flight-log CSVs from the Flight Reader API (#390).

A thin, polite client in front of :mod:`.flightlog`: the returned CSV is
byte-for-byte what a hand-exported one would be, cached beside the TXT so
the same record is never uploaded twice. Pure stdlib, matching the rest
of :mod:`geo`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .flightlog import _NOT_AIRCRAFT, _find

logger = logging.getLogger(__name__)

_BASE = "https://api.flightreader.com/v1"
_TIMEOUT_S = 120

# Each wanted column: (slot, needles, excludes) — mirroring the _find
# calls in flightlog.parse_flight_log. Keep the two in sync, or the API
# gets asked for a column the merge itself would reject (HOME.latitude,
# OSD.flyTime as the clock). "time" appears twice: preferred form first,
# parse_flight_log's fallback second.
_WANTED: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("pitch", ("gimbal", "pitch"), ()),
    ("yaw", ("gimbal", "yaw"), ("360",)),
    ("yaw", ("gimbal", "heading"), ()),
    ("yaw", ("gimbal", "yaw"), ()),  # the [360] fallback variant
    ("utc", ("utc",), ()),
    ("datetime", ("datetime",), ("utc",)),
    ("date", ("date",), ("datetime",)),
    ("time", ("time", "local"), ("date",)),
    ("time", ("time",), ("date", "datetime", "fly")),
    ("latitude", ("latitude",), _NOT_AIRCRAFT),
    ("longitude", ("longitude",), _NOT_AIRCRAFT),
)


class LogFetchError(ValueError):
    """A fetch failed; the message states the concrete problem and fix."""


def cache_path(txt: Path) -> Path:
    """Where *txt*'s decoded CSV lives: beside it, provider-named."""
    return txt.with_name(txt.stem + ".flightreader.csv")


def _field_names(payload: bytes) -> list[str]:
    """Field names from a ``/v1/fields`` response body.

    Lenient by design: the exact schema is unverified until E2E, and a
    wrong guess must degrade to the full-CSV fallback, never to a crash.
    """
    try:
        data = json.loads(payload)
    except ValueError:
        return []
    if isinstance(data, dict):
        for key in ("fields", "data", "items"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            return []
    if not isinstance(data, list):
        return []
    names: list[str] = []
    for item in data:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    return names


def select_fields(available: list[str]) -> list[str] | None:
    """The subset of *available* the merge needs, or ``None`` for "all".

    ``None`` (not an error) when gimbal or timestamp columns cannot be
    identified — the full CSV plus :func:`parse_flight_log`'s own
    detection then judges the result.
    """
    picked: list[str] = []
    hits: set[str] = set()
    for slot, needles, excludes in _WANTED:
        hit = _find(available, *needles, exclude=excludes)
        if hit:
            hits.add(slot)
            if hit not in picked:
                picked.append(hit)
    has_time = "utc" in hits or "datetime" in hits or (
        "date" in hits and "time" in hits
    )
    if "pitch" not in hits or "yaw" not in hits or not has_time:
        return None
    return picked
