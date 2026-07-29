"""Fetch decrypted flight-log CSVs from the Flight Reader API (#390).

A thin, polite client in front of :mod:`.flightlog`: the returned CSV is
byte-for-byte what a hand-exported one would be, cached beside the TXT so
the same record is never uploaded twice. Pure stdlib, matching the rest
of :mod:`geo`.
"""

from __future__ import annotations

import json
import logging
import secrets
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .flightlog import _NOT_AIRCRAFT, _find, FlightLogError, parse_flight_log

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


def _multipart(
    filename: str, data: bytes, form: dict[str, str]
) -> tuple[bytes, str]:
    """A multipart/form-data body: *form* fields plus one file part."""
    boundary = "----dji-embed-" + secrets.token_hex(12)
    parts: list[bytes] = []
    for name, value in form.items():
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")
        )
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; '
            f'filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8")
        + data
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _list_fields(key: str, transport) -> list[str]:
    """Names from ``GET /v1/fields`` (free), or ``[]`` on soft failure.

    A 401 raises — the very next call would bill against a bad key.
    Everything else degrades to the full-CSV fallback.
    """
    req = Request(
        f"{_BASE}/fields",
        headers={"Authorization": f"Bearer {key}", "User-Agent": "dji-embed"},
    )
    try:
        with transport(req, timeout=_TIMEOUT_S) as resp:
            return _field_names(resp.read())
    except HTTPError as exc:
        if exc.code == 401:
            raise LogFetchError(
                "the API rejected the key (HTTP 401) — check "
                "FLIGHTREADER_API_KEY"
            ) from exc
        logger.info("GET /v1/fields failed (%s); requesting the full CSV", exc)
        return []
    except (URLError, OSError) as exc:
        logger.info("GET /v1/fields failed (%s); requesting the full CSV", exc)
        return []


def _post_log(
    txt: Path, key: str, fields: list[str] | None, transport
) -> bytes:
    """``POST /v1/logs`` (billable): upload *txt*, return the CSV bytes."""
    form = {"fields": ",".join(fields)} if fields else {}
    body, content_type = _multipart(txt.name, txt.read_bytes(), form)
    req = Request(
        f"{_BASE}/logs",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": content_type,
            "User-Agent": "dji-embed",
        },
    )
    try:
        with transport(req, timeout=_TIMEOUT_S) as resp:
            return resp.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").splitlines()
        hint = " — check FLIGHTREADER_API_KEY" if exc.code == 401 else ""
        raise LogFetchError(
            f"{txt.name}: the API answered HTTP {exc.code}"
            f"{': ' + detail[0] if detail and detail[0] else ''}{hint}"
        ) from exc
    except (URLError, OSError) as exc:
        raise LogFetchError(
            f"{txt.name}: network error ({exc}) — nothing was consumed; "
            "re-running is safe"
        ) from exc


def _check_csv(body: bytes, txt: Path) -> None:
    """Refuse to cache a body that is plainly not CSV."""
    first = body.decode("utf-8-sig", errors="replace").split("\n", 1)[0].strip()
    if not first or first[0] in "{<" or ("," not in first and ";" not in first):
        raise LogFetchError(
            f"{txt.name}: the API returned something other than CSV "
            f"(first line: {first[:120]!r}); nothing was written"
        )


def fetch_log(txt: Path, key: str, *, transport=urlopen) -> Path:
    """Decrypt *txt* through the API; return the cached CSV's path.

    Cache hit = no network. One attempt per request, no retries. The
    written CSV is verified with :func:`parse_flight_log` immediately —
    a verification failure keeps the file (it cost money) and raises.
    """
    out = cache_path(txt)
    if out.exists():
        return out
    names = _list_fields(key, transport)
    fields = select_fields(names) if names else None
    body = _post_log(txt, key, fields, transport)
    _check_csv(body, txt)
    out.write_bytes(body)
    try:
        parse_flight_log(out)
    except FlightLogError as exc:
        raise LogFetchError(
            f"{out.name} was fetched and kept, but cannot drive the "
            f"merge: {exc}"
        ) from exc
    return out
