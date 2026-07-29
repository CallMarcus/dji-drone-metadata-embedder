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

from .flightlog import _find

logger = logging.getLogger(__name__)

_BASE = "https://api.flightreader.com/v1"
_TIMEOUT_S = 120

# What the merge consumes (see flightlog.parse_flight_log), as _find
# needle sets. Everything that matches gets requested; roll, battery,
# and the rest stay on the server.
_WANTED: tuple[tuple[str, ...], ...] = (
    ("gimbal", "pitch"),
    ("gimbal", "yaw"),
    ("utc",),
    ("datetime",),
    ("date",),
    ("time",),
    ("latitude",),
    ("longitude",),
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
    for needles in _WANTED:
        hit = _find(available, *needles)
        if hit and hit not in picked:
            picked.append(hit)
    have = set(picked)
    has_gimbal = _find(sorted(have), "gimbal", "pitch") and _find(
        sorted(have), "gimbal", "yaw"
    )
    has_time = (
        _find(sorted(have), "utc")
        or _find(sorted(have), "datetime")
        or (_find(sorted(have), "date") and _find(sorted(have), "time"))
    )
    if not has_gimbal or not has_time:
        return None
    return picked
