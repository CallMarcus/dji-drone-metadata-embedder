"""ED-318 GeoJSON-profile UAS geographical-zone parser (#452).

Ireland's (iaa.ie) and Sweden's (LFV dronechart) official publications are
plain GeoJSON FeatureCollections in the ED-318 shape: zone fields live in
``properties`` (restriction class under ``type``), vertical limits ride in
a non-standard ``layer`` member inside each feature's ``geometry``, and
timed windows are ``properties.limitedApplicability``. All-or-nothing like
the ED-269 parser: any malformed zone raises rather than silently thinning
the set.

Ireland's published filename is dated and versioned
(``20260804_uas_zones_ireland_v1.geojson``), so its registry entry pins the
stable zones *page* and the current href is discovered at fetch time;
Sweden's file URL is itself the stable address and is pinned directly.

Permission record (issue #452): the IAA's Airspace & U-space Inspector
rejected the ArcGIS service and pointed at this published file in reply to
our stated open-source reuse request, 2026-08-11. The page carries no
formal licence; its "reference only, not to be used for navigation"
wording is preserved in the feed note.

Sweden's permission record (issue #510): LFV Operations UTM confirmed in
writing on 2026-08-19 that the ED-318 file is free to download and use —
cite LFV as source, no logos, do not modify the zone content. The file
URL is the stable published address (until LFV system changes expected
around 2027/2028), so the registry pins it directly with no discovery.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from .dronezoner import _circle_ring
from .ed269 import _utc
from .model import Applicability, AirspaceError, SourceInfo, VerticalLimit, Zone


@dataclass(frozen=True)
class Ed318Feed:
    code: str
    page_url: str
    feed_name: str
    license: str
    caveat: str
    note: str | None = None
    # A stable direct file URL; when set, fetch skips page discovery and
    # the record cites this URL (it IS the published address).
    file_url: str | None = None


_CAVEAT = (
    "UAS geographical-zone data is informational and is not an "
    "authorization to fly."
)

ED318_FEEDS: dict[str, Ed318Feed] = {
    "IE": Ed318Feed(
        code="IE",
        page_url=(
            "https://www.iaa.ie/general-aviation/drones/uas-geographic-zones"
        ),
        feed_name="Ireland UAS geographical zones (ED-318, IAA)",
        license=(
            "© Irish Aviation Authority (iaa.ie), official published "
            "UAS geographical-zone dataset"
        ),
        caveat=_CAVEAT,
        # The IAA page's own wording, preserved verbatim in spirit: the
        # published file is a reference product, not a navigation source.
        note=(
            "IAA publication note: reference only — not to be used for "
            "navigation."
        ),
    ),
    "SE": Ed318Feed(
        code="SE",
        page_url="https://dronechart.lfv.se/",
        file_url="https://dronechart.lfv.se/data/uas_zones_ED318.json",
        feed_name="Sweden UAS geographical zones (ED-318, LFV)",
        license=(
            "© LFV — free to download and use, cite LFV as source "
            "(confirmed in writing by LFV Operations UTM, 2026-08-19)"
        ),
        caveat=_CAVEAT,
        note=(
            "Published by LFV with Transportstyrelsen as data provider. "
            "Some zones apply only during scheduled hours within their "
            "validity window; the schedule is in the zone's published "
            "data and is not evaluated here."
        ),
    ),
}

# The current file is the only .geojson href on the zones page whose name
# carries the uas_zones_ireland stem; the leading date and trailing
# Sitefinity version parameter both churn between publications.
_FEED_HREF_RE = re.compile(
    r'href="([^"]*uas_zones_ireland[^"]*\.geojson[^"]*)"', re.IGNORECASE
)


def discover_feed_url(page: bytes, page_url: str) -> str:
    """The current zones-file URL from the IAA page's HTML."""
    match = _FEED_HREF_RE.search(page.decode("utf-8", errors="replace"))
    if not match:
        raise AirspaceError(
            "could not find the UAS zones file on the IAA page "
            f"({page_url}) — the page layout may have changed"
        )
    href = match.group(1).replace("&amp;", "&")
    return urljoin(page_url, href)


def _limit(layer: dict, side: str, unit: str, where: str) -> VerticalLimit | None:
    value = layer.get(side)
    if value is None:
        return None  # "not stated" — never 0
    ref = layer.get(f"{side}Reference")
    if ref not in ("AGL", "AMSL"):
        raise AirspaceError(
            f"{where}: {side}Reference is {ref!r}, expected AGL/AMSL"
        )
    if not isinstance(value, (int, float)):
        raise AirspaceError(f"{where}: {side} limit {value!r} is not a number")
    return VerticalLimit(float(value), unit, ref)


def _zone_name(props: dict, ident: str, where: str) -> str:
    """The zone's display name; multilingual lists pick the English text.

    The Swedish file publishes ``name`` as a list of ``{text, lang}``
    entries (en-GB + se-SE); Ireland publishes a plain string. The
    original list rides untouched in ``native``."""
    raw = props.get("name")
    if raw is None or isinstance(raw, str):
        return str(raw or ident)
    if isinstance(raw, list):
        texts = [
            entry["text"].strip()
            for entry in raw
            if isinstance(entry, dict)
            and isinstance(entry.get("text"), str)
            and entry["text"].strip()
        ]
        english = [
            entry["text"].strip()
            for entry in raw
            if isinstance(entry, dict)
            and entry.get("lang") == "en-GB"
            and isinstance(entry.get("text"), str)
            and entry["text"].strip()
        ]
        if english:
            return english[0]
        if texts:
            return texts[0]
    raise AirspaceError(f"{where} ({ident}): unusable name {raw!r}")


def _rings(
    geometry: dict, ident: str, where: str
) -> tuple[list[list[tuple[float, float]]], list[list[tuple[float, float]]]]:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if gtype == "Polygon":
        polys = [coords]
    elif gtype == "MultiPolygon":
        polys = coords
    else:
        raise AirspaceError(
            f"{where} ({ident}): geometry type {gtype!r} is not supported"
        )
    polygons: list[list[tuple[float, float]]] = []
    holes: list[list[tuple[float, float]]] = []
    for poly in polys:
        for ring_index, ring in enumerate(poly):
            try:
                parsed = [(float(x), float(y)) for x, y in ring]
            except (TypeError, ValueError) as exc:
                raise AirspaceError(
                    f"{where} ({ident}): malformed ring coordinates"
                ) from exc
            # GeoJSON ring order: 0 is an exterior, the rest are holes —
            # kept apart so the evaluator subtracts them (#422).
            (polygons if ring_index == 0 else holes).append(parsed)
    return polygons, holes


def _point_circle(
    geometry: dict, ident: str, where: str
) -> list[tuple[float, float]]:
    """A Point zone's densified ring from its ED-318 Circle extent.

    The profile publishes point zones as centre + ``extent`` of
    ``{"subType": "Circle", "radius": <metres>}`` (the live Swedish file's
    ESU247 radius is 1852.0 — exactly one nautical mile). Anything else is
    a shape this parser has never seen live and fails loudly."""
    extent = geometry.get("extent")
    if not isinstance(extent, dict) or extent.get("subType") != "Circle":
        raise AirspaceError(
            f"{where} ({ident}): Point geometry without a Circle extent "
            "is not supported"
        )
    radius = extent.get("radius")
    if not isinstance(radius, (int, float)) or radius <= 0:
        raise AirspaceError(
            f"{where} ({ident}): Circle radius {radius!r} is not a "
            "positive number of metres"
        )
    coords = geometry.get("coordinates") or []
    try:
        lon, lat = float(coords[0]), float(coords[1])
    except (TypeError, ValueError, IndexError) as exc:
        raise AirspaceError(
            f"{where} ({ident}): malformed Point coordinates {coords!r}"
        ) from exc
    return _circle_ring(lon, lat, float(radius))


def parse_ed318(raw: bytes, source: SourceInfo) -> list[Zone]:
    """Every zone of an ED-318 GeoJSON document as normalized :class:`Zone`s."""
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except ValueError as exc:
        raise AirspaceError(f"{source.feed}: feed is not JSON ({exc})") from exc
    features = data.get("features") if isinstance(data, dict) else None
    if not isinstance(features, list):
        raise AirspaceError(
            f"{source.feed}: not an ED-318 document (no 'features' list)"
        )
    zones: list[Zone] = []
    for i, feat in enumerate(features):
        where = f"{source.feed}: zone {i}"
        if not isinstance(feat, dict):
            raise AirspaceError(f"{where}: not an object")
        props = feat.get("properties")
        if not isinstance(props, dict):
            raise AirspaceError(f"{where}: missing properties")
        ident = props.get("identifier")
        restriction = props.get("type")
        if not isinstance(ident, str) or not ident:
            raise AirspaceError(f"{where}: missing identifier")
        if not isinstance(restriction, str) or not restriction:
            raise AirspaceError(f"{where} ({ident}): missing restriction type")
        # One concept, one label across countries: the ED-269 feeds spell
        # REQ_AUTHORISATION with an S, this profile with a Z. Normalized
        # here at the provider boundary; `native` keeps the feed's spelling.
        if restriction == "REQ_AUTHORIZATION":
            restriction = "REQ_AUTHORISATION"
        applicability: list[Applicability] = []
        windows = props.get("limitedApplicability")
        if windows is not None:
            if not isinstance(windows, list):
                raise AirspaceError(
                    f"{where} ({ident}): limitedApplicability is not a list"
                )
            for win in windows:
                start = win.get("startDateTime")
                end = win.get("endDateTime")
                applicability.append(
                    Applicability(
                        start=_utc(start, f"{where}: startDateTime")
                        if start else None,
                        end=_utc(end, f"{where}: endDateTime") if end else None,
                        permanent=False,
                    )
                )
        geometry = feat.get("geometry")
        if not isinstance(geometry, dict):
            raise AirspaceError(f"{where} ({ident}): missing geometry")
        layer = geometry.get("layer")
        lower = upper = None
        if layer is not None:
            if not isinstance(layer, dict):
                raise AirspaceError(f"{where} ({ident}): layer is not an object")
            unit = "ft" if str(layer.get("uom", "M")).upper() == "FT" else "m"
            lower = _limit(layer, "lower", unit, f"{where} ({ident})")
            upper = _limit(layer, "upper", unit, f"{where} ({ident})")
        if geometry.get("type") == "Point":
            polygons = [_point_circle(geometry, ident, where)]
            holes: list[list[tuple[float, float]]] = []
        else:
            polygons, holes = _rings(geometry, ident, where)
        if not polygons:
            raise AirspaceError(f"{where} ({ident}): no polygon geometry")
        zones.append(
            Zone(
                identifier=ident,
                name=_zone_name(props, ident, where),
                restriction=restriction,
                lower=lower,
                upper=upper,
                applicability=applicability,
                polygons=polygons,
                holes=holes,
                source=source,
                native=feat,
            )
        )
    return zones
