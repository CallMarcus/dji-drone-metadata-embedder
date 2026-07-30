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

from .flightlog import _COLUMN_SPEC, _tokens, FlightLogError, parse_flight_log

logger = logging.getLogger(__name__)

_BASE = "https://api.flightreader.com/v1"
_TIMEOUT_S = 120


class LogFetchError(ValueError):
    """A fetch failed; the message states the concrete problem and fix."""


def cache_path(txt: Path) -> Path:
    """Where *txt*'s decoded CSV lives: beside it, provider-named."""
    return txt.with_name(txt.stem + ".flightreader.csv")


def _field_names(payload: bytes) -> list[str]:
    """Field names from a ``/v1/fields`` response body.

    The live API wraps the list in ``{"statusCode", "message", "result"}``
    (E2E-verified 2026-07-30); the other keys stay as leniency, and a
    wrong guess must degrade to the full-CSV fallback, never to a crash.
    """
    try:
        data = json.loads(payload)
    except ValueError:
        return []
    if isinstance(data, dict):
        for key in ("result", "fields", "data", "items"):
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


def _closest(
    available: list[str], needles: tuple[str, ...], exclude: tuple[str, ...]
) -> str | None:
    """The matching name carrying the fewest tokens beyond *needles*.

    The ``/v1/fields`` catalog lists every field the API can produce, in
    an order that carries no preference (alphabetical in practice) — so
    first-hit, which is right for a real export's column order, picks
    ``GIMBAL.isPitchAtLimit`` over ``GIMBAL.pitch`` and
    ``ADSB.currentLatitude`` over ``OSD.latitude`` here (E2E-verified
    2026-07-30). The closest name wins instead; ties keep catalog order.
    """
    best: str | None = None
    best_extra = 0
    for h in available:
        toks = _tokens(h)
        if any(x in toks for x in exclude):
            continue
        if all(n in toks for n in needles):
            extra = len(toks - set(needles))
            if best is None or extra < best_extra:
                best, best_extra = h, extra
    return best


def select_fields(available: list[str]) -> list[str] | None:
    """The subset of *available* the merge needs, or ``None`` for "all".

    ``None`` (not an error) when gimbal or timestamp columns cannot be
    identified — the full CSV plus :func:`parse_flight_log`'s own
    detection then judges the result.
    """
    # Unlike parse_flight_log's first-hit-per-slot, every alternative's
    # hit is requested — the CSV then carries each candidate column and
    # the parser applies its own preference order to the result.
    picked: list[str] = []
    hits: set[str] = set()
    for slot, alternatives in _COLUMN_SPEC.items():
        for needles, exclude in alternatives:
            hit = _closest(available, needles, exclude)
            if hit:
                hits.add(slot)
                if hit not in picked:
                    picked.append(hit)
    has_time = "epoch" in hits or "utc" in hits or "datetime" in hits or (
        "utc_date" in hits and "utc_time" in hits
    ) or ("date" in hits and "time" in hits)
    if "pitch" not in hits or "yaw" not in hits or not has_time:
        return None
    return picked


def _multipart(
    filename: str, data: bytes, form: list[tuple[str, str]]
) -> tuple[bytes, str]:
    """A multipart/form-data body: *form* parts plus one file part.

    *form* is a list, not a dict: the API's field preselection expects one
    ``fields`` part PER field name (the docs' ``formData.append`` loop) —
    a single comma-joined value is silently ignored and the full CSV comes
    back (E2E-verified 2026-07-30).
    """
    boundary = "----dji-embed-" + secrets.token_hex(12)
    parts: list[bytes] = []
    for name, value in form:
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
    form = [("fields", f) for f in fields] if fields else []
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
