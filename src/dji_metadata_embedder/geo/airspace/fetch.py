"""Fetch + cache orchestration for airspace zones (#413).

Never raises: every failure — no provider, dead feed, malformed document —
becomes a stated ``gap_reason`` so the record renders the gap instead of
dying. Every network touch is announced BEFORE it happens (the tool's
baseline promise is local-only processing; the airspace flags are the
opt-in), and cache reuse is announced with its timestamp.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from ..track import Track
from .aixm51 import (
    AIXM_FEEDS,
    discover_feed_url as discover_aixm_url,
    extract_xml,
    parse_aixm51,
)
from .arcgis_faa import FAA_FEED, FAA_QUERY_URL, fetch_faa_pages, parse_faa, snap_bbox
from .dronezoner import (
    DRONEZONER_FEEDS,
    discover_feed_url as discover_dronezoner_url,
    parse_dronezoner,
)
from .eans import EANS_FEEDS, parse_eans
from .ed269 import ED269_FEEDS, parse_ed269
from .ed318 import ED318_FEEDS, discover_feed_url, ed318_effective, parse_ed318
from .jurisdiction import resolve_jurisdiction
from .model import AirspaceError, SourceInfo, Zone

_TIMEOUT_S = 60


@dataclass
class AirspaceData:
    zones: list[Zone] = field(default_factory=list)
    source: SourceInfo | None = None
    gap_reason: str | None = None
    from_cache: bool = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bbox(track: Track) -> tuple[float, float, float, float]:
    lons = [p.lon for p in track.points]
    lats = [p.lat for p in track.points]
    return min(lons), min(lats), max(lons), max(lats)


def _read_cache(body_path: Path) -> tuple[bytes, str, str | None] | None:
    """``(body, fetched, effective)`` — ``effective`` is the dataset's own
    edition date when the sidecar recorded one (#502); sidecars written
    before that, or for undated feeds, yield None and the record simply
    omits the line."""
    meta_path = body_path.with_name(body_path.name + ".meta.json")
    if not (body_path.exists() and meta_path.exists()):
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        effective = meta.get("effective")
        return (
            body_path.read_bytes(),
            str(meta.get("fetched", "unknown time")),
            str(effective) if effective is not None else None,
        )
    except (OSError, ValueError, AttributeError):
        # A corrupt cache (bad JSON, bad encoding, unreadable file, or a
        # sidecar that is not an object) is a cache miss, not a crash —
        # the caller will refetch.
        return None


def _write_cache(
    body_path: Path, body: bytes, url: str, fetched: str,
    effective: str | None,
) -> None:
    body_path.parent.mkdir(parents=True, exist_ok=True)
    body_path.write_bytes(body)
    meta: dict[str, str] = {"url": url, "fetched": fetched}
    if effective is not None:
        meta["effective"] = effective
    body_path.with_name(body_path.name + ".meta.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )


def _load_faa_doc(body: bytes) -> dict:
    try:
        return json.loads(body)
    except ValueError as exc:
        raise AirspaceError(f"FAA cache/response is not JSON ({exc})") from exc


def _faa_pages_from_doc(doc: dict) -> list[bytes]:
    """Re-split the cached FAA wrapper's ``pages`` list into page bodies.

    A missing ``pages`` list (e.g. a cached body of ``{}``) must not
    silently resolve to zero zones — that reads as "no restrictions here"
    when it actually means the cache never held a real document.
    """
    pages = doc.get("pages") if isinstance(doc, dict) else None
    if not isinstance(pages, list):
        raise AirspaceError("FAA cache/response has no 'pages' list")
    return [json.dumps(p).encode("utf-8") for p in pages]


def _fetch_url(url: str, transport) -> bytes:
    req = Request(url, headers={"User-Agent": "dji-embed"})
    try:
        with transport(req, timeout=_TIMEOUT_S) as resp:
            return resp.read()
    except (URLError, OSError) as exc:
        raise AirspaceError(f"feed fetch failed: {exc}") from exc


def fetch_zones(
    track: Track,
    cache_dir: Path,
    *,
    refresh: bool = False,
    transport=urlopen,
    announce=lambda msg: None,
) -> AirspaceData:
    """Zones for *track*'s jurisdiction, cached beside the output."""
    resolution = resolve_jurisdiction(track)
    if resolution.jurisdiction is None:
        return AirspaceData(gap_reason=resolution.gap_reason)
    code = resolution.jurisdiction.code

    if code == "US":
        x1, y1, x2, y2 = snap_bbox(_bbox(track))
        key = f"{x1:g}_{y1:g}_{x2:g}_{y2:g}".replace("-", "m")
        body_path = cache_dir / f"faa-{key}.json"
        feed_name, license_line, caveat = FAA_FEED
        url = FAA_QUERY_URL
        note = None
    elif code in ED269_FEEDS:
        feed = ED269_FEEDS[code]
        body_path = cache_dir / f"ed269-{code}.json"
        feed_name, license_line, caveat = feed.feed_name, feed.license, feed.caveat
        url = feed.url
        note = feed.note
    elif code in ED318_FEEDS:
        feed318 = ED318_FEEDS[code]
        body_path = cache_dir / f"ed318-{code}.json"
        feed_name = feed318.feed_name
        license_line, caveat = feed318.license, feed318.caveat
        # IE's published filename is dated and churns, so its registry
        # pins the stable zones page and the current href is discovered
        # per fetch. SE's file URL is itself the stable published
        # address (LFV, 2026-08-19), fetched and cited directly.
        url = feed318.file_url or feed318.page_url
        note = feed318.note
    elif code in DRONEZONER_FEEDS:
        feed_dz = DRONEZONER_FEEDS[code]
        body_path = cache_dir / f"dronezoner-{code}.json"
        feed_name = feed_dz.feed_name
        license_line, caveat = feed_dz.license, feed_dz.caveat
        # Same churning-link pattern as ED-318: the droneregler.dk page
        # is the stable entry point the record cites; the current ArcGIS
        # item href is discovered per fetch.
        url = feed_dz.page_url
        note = feed_dz.note
    elif code in EANS_FEEDS:
        feed_ee = EANS_FEEDS[code]
        body_path = cache_dir / f"eans-{code}.json"
        feed_name = feed_ee.feed_name
        license_line, caveat = feed_ee.license, feed_ee.caveat
        # The UTM system's file URL is the stable published address —
        # fetched and cited directly, like Sweden's ED-318 file.
        url = feed_ee.url
        note = feed_ee.note
    else:
        feed_aixm = AIXM_FEEDS[code]
        body_path = cache_dir / f"aixm-{code}.xml"
        feed_name = feed_aixm.feed_name
        license_line, caveat = feed_aixm.license, feed_aixm.caveat
        # Same dated-filename pattern as ED-318, with a zip around the
        # XML; the cache holds the extracted, sha-verified XML so cached
        # and fresh bodies parse identically.
        url = feed_aixm.page_url
        note = feed_aixm.note

    def parse_body(body: bytes, source: SourceInfo) -> list[Zone]:
        if code == "US":
            doc = _load_faa_doc(body)
            return parse_faa(_faa_pages_from_doc(doc), source)
        if code in ED269_FEEDS:
            return parse_ed269(body, source, no_ceiling_m=feed.no_ceiling_m)
        if code in ED318_FEEDS:
            return parse_ed318(body, source)
        if code in DRONEZONER_FEEDS:
            return parse_dronezoner(body, source)
        if code in EANS_FEEDS:
            return parse_eans(body, source)
        return parse_aixm51(body, source)

    cached = None if refresh else _read_cache(body_path)
    effective: str | None = None
    try:
        if cached is not None:
            body, fetched, effective = cached
            from_cache = True
        else:
            host = url.split("/")[2]
            announce(f"Fetching {feed_name} from {host}...")
            if code == "US":
                pages = fetch_faa_pages(_bbox(track), transport)
                body = json.dumps(
                    {"pages": [json.loads(p) for p in pages]}
                ).encode("utf-8")
            elif code in ED269_FEEDS:
                body = _fetch_url(url, transport)
            elif code in ED318_FEEDS:
                if feed318.file_url:
                    body = _fetch_url(url, transport)
                else:
                    page = _fetch_url(url, transport)
                    body = _fetch_url(discover_feed_url(page, url), transport)
                # The file states its own edition (#563); it rides in the
                # record and the cache sidecar like the UK's cycle date.
                effective = ed318_effective(body)
            elif code in DRONEZONER_FEEDS:
                page = _fetch_url(url, transport)
                body = _fetch_url(
                    discover_dronezoner_url(page, url), transport
                )
            elif code in EANS_FEEDS:
                body = _fetch_url(url, transport)
            else:
                page = _fetch_url(url, transport)
                zip_url, effective = discover_aixm_url(
                    page, url, today=datetime.now(timezone.utc).date()
                )
                body = extract_xml(_fetch_url(zip_url, transport))
            fetched = _now_iso()
            from_cache = False

        source = SourceInfo(
            feed=feed_name, url=url, fetched=fetched,
            license=license_line, caveat=caveat, note=note,
            effective=effective,
        )
        zones = parse_body(body, source)
        if from_cache:
            # Only claim the cache was usable once it has actually
            # parsed — an announce made before this point could be a lie.
            announce(
                f"Using cached {feed_name} from {fetched} ({body_path})"
            )
        else:
            # Cache only what parsed (#518): a maintenance page served
            # with HTTP 200 must never become the body every later run
            # trusts.
            _write_cache(body_path, body, url, fetched, effective)
    except AirspaceError as exc:
        stale = _read_cache(body_path) if refresh else None
        if stale is not None:
            body, fetched, effective = stale
            source = SourceInfo(
                feed=feed_name, url=url, fetched=fetched,
                license=license_line, caveat=caveat, note=note,
                effective=effective,
            )
            try:
                zones = parse_body(body, source)
            except AirspaceError as exc2:
                return AirspaceData(
                    gap_reason=f"airspace data unavailable: {exc2}"
                )
            # Only claim the cache was usable once it has actually parsed —
            # an announce made before this point could be a lie.
            announce(
                f"Fetch failed ({exc}); using cached {feed_name} "
                f"from {fetched}"
            )
            return AirspaceData(zones=zones, source=source, from_cache=True)
        reason = f"airspace data unavailable: {exc}"
        if cached is not None:
            # The body that failed came from the cache (poisoned before
            # the write-after-parse fix, or corrupted on disk) — the live
            # feed may be fine, so name the way out (#518). A fresh-fetch
            # failure never gets this hint: refreshing cannot help there.
            reason += (
                f" — the cached copy at {body_path} may be bad; rerun "
                "with --airspace-refresh to refetch"
            )
        return AirspaceData(gap_reason=reason)
    return AirspaceData(zones=zones, source=source, from_cache=from_cache)
