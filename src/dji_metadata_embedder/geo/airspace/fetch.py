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
from .arcgis_faa import FAA_FEED, FAA_QUERY_URL, fetch_faa_pages, parse_faa, snap_bbox
from .ed269 import ED269_FEEDS, parse_ed269
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


def _read_cache(body_path: Path) -> tuple[bytes, str] | None:
    meta_path = body_path.with_name(body_path.name + ".meta.json")
    if not (body_path.exists() and meta_path.exists()):
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return body_path.read_bytes(), str(meta.get("fetched", "unknown time"))
    except (OSError, ValueError):
        # A corrupt cache (bad JSON, bad encoding, unreadable file) is a
        # cache miss, not a crash — the caller will refetch.
        return None


def _write_cache(body_path: Path, body: bytes, url: str) -> str:
    body_path.parent.mkdir(parents=True, exist_ok=True)
    fetched = _now_iso()
    body_path.write_bytes(body)
    body_path.with_name(body_path.name + ".meta.json").write_text(
        json.dumps({"url": url, "fetched": fetched}), encoding="utf-8"
    )
    return fetched


def _load_faa_doc(body: bytes) -> dict:
    try:
        return json.loads(body)
    except ValueError as exc:
        raise AirspaceError(f"FAA cache/response is not JSON ({exc})") from exc


def _fetch_ed269(url: str, transport) -> bytes:
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
    else:
        feed = ED269_FEEDS[code]
        body_path = cache_dir / f"ed269-{code}.json"
        feed_name, license_line, caveat = feed.feed_name, feed.license, feed.caveat
        url = feed.url
        note = feed.note

    cached = None if refresh else _read_cache(body_path)
    try:
        if cached is not None:
            body, fetched = cached
            from_cache = True
        else:
            host = url.split("/")[2]
            announce(
                f"Fetching {feed_name} from {host} — the only network "
                "access in this command..."
            )
            if code == "US":
                pages = fetch_faa_pages(_bbox(track), transport)
                body = json.dumps(
                    {"pages": [json.loads(p) for p in pages]}
                ).encode("utf-8")
            else:
                body = _fetch_ed269(url, transport)
            fetched = _write_cache(body_path, body, url)
            from_cache = False

        source = SourceInfo(
            feed=feed_name, url=url, fetched=fetched,
            license=license_line, caveat=caveat, note=note,
        )
        if code == "US":
            doc = _load_faa_doc(body)
            pages_raw = [
                json.dumps(p).encode("utf-8") for p in doc.get("pages", [])
            ]
            zones = parse_faa(pages_raw, source)
        else:
            zones = parse_ed269(body, source)
        if from_cache:
            # Only claim the cache was usable once it has actually
            # parsed — an announce made before this point could be a lie.
            announce(
                f"Using cached {feed_name} from {fetched} ({body_path})"
            )
    except AirspaceError as exc:
        stale = _read_cache(body_path) if refresh else None
        if stale is not None:
            body, fetched = stale
            source = SourceInfo(
                feed=feed_name, url=url, fetched=fetched,
                license=license_line, caveat=caveat, note=note,
            )
            try:
                if code == "US":
                    doc = _load_faa_doc(body)
                    pages_raw = [
                        json.dumps(p).encode("utf-8")
                        for p in doc.get("pages", [])
                    ]
                    zones = parse_faa(pages_raw, source)
                else:
                    zones = parse_ed269(body, source)
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
        return AirspaceData(gap_reason=f"airspace data unavailable: {exc}")
    return AirspaceData(zones=zones, source=source, from_cache=from_cache)
