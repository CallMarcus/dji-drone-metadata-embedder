"""Denmark drone-zone parser (Trafikstyrelsen Dronezoner GeoJSON).

The official dataset behind droneregler.dk: a GeoJSON FeatureCollection
whose zones come in three colour classes named by the KMZ export's own
layers — RØD (flight-safety-critical: airports, HEMS, military air
stations), BLÅ (security-critical: police, military, embassies, prisons)
and ORANGE (awareness: recreational airfields). All-or-nothing like the
other providers: any malformed feature raises rather than silently
thinning the set.

Two dataset quirks are contract, both probed on the live file 2026-08-15:

- Most zones appear twice — once as the buffered Polygon and once as a
  Point map marker (the "Signatur" KMZ layers). Points that duplicate a
  polygon feature are dropped — matched on (title, colour) only, because
  ``typeId`` spelling churns between the twins ("Retsvæsen" point vs
  "Restvæsen" polygon in the live file). Orphan points (police stations,
  HEMS sites published as centre + buffer only) become densified circles
  from their published buffer distance; awareness-class (ORANGE) orphans
  with no buffer at all — model-club and parachute site markers, 84 in
  the live file — are dimensionless site markers, not crossable zones,
  and are skipped. A bufferless orphan in either restrictive class still
  raises: those all carry buffers today, and losing them would be a
  regression worth failing loudly on.
- ``Elevation_fod``/``Elevation_meter`` is the aerodrome site elevation,
  not a zone limit, and no vertical limits are published at all — zones
  render "not stated", never an invented 0.

The download page's ArcGIS item IDs churn (an ``_old``-suffixed item and
a dead KML ID were both observed), so the stable droneregler.dk page is
what the registry pins and the record cites; the current GeoJSON href is
discovered from it per fetch. The page says "exclusively for personal
use", but the dataset's own embedded metadata grants "Data kan frit
anvendes med kildeangivelse" (free use with attribution) — the
NATS/BAZL pattern of the licence living inside the data.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

from .aixm51 import _CIRCLE_POINTS, _destination
from .model import Applicability, AirspaceError, SourceInfo, Zone


@dataclass(frozen=True)
class DronezonerFeed:
    code: str
    page_url: str
    feed_name: str
    license: str
    caveat: str
    note: str | None = None


_CAVEAT = (
    "UAS geographical-zone data is informational and is not an "
    "authorization to fly."
)

DRONEZONER_FEEDS: dict[str, DronezonerFeed] = {
    "DK": DronezonerFeed(
        code="DK",
        # The Danish-language twin of this page 404s; the English page is
        # the canonical, stable entry point.
        page_url=(
            "https://www.en.droneregler.dk/uas-geographical-zones/"
            "data-for-download"
        ),
        feed_name="Denmark drone zones (Trafikstyrelsen)",
        license=(
            "© Trafikstyrelsen — \"Data kan frit anvendes med "
            "kildeangivelse\" (free use with attribution, stated in the "
            "dataset metadata)"
        ),
        caveat=_CAVEAT,
        note=(
            "Static zones only — NOTAM-driven temporary restrictions are "
            "not part of this dataset."
        ),
    ),
}

# The page links five export formats as ArcGIS item /data URLs; only the
# link whose anchor text says GeoJson is wanted. Item IDs churn, so the
# href itself is never pinned.
_GEOJSON_LINK_RE = re.compile(
    r'href="(https://trafikstyrelsen\.maps\.arcgis\.com/sharing/rest/'
    r'content/items/[0-9a-f]+/data)"[^>]*>\s*(?:<[^>]+>\s*)*GeoJson',
    re.IGNORECASE,
)

# The official colour classes, named after the dataset's own KMZ layers.
_RESTRICTION_BY_FARVE = {
    "1": "Flight-safety-critical (RØD)",
    "4": "Security-critical (BLÅ)",
    "5": "Awareness (ORANGE)",
}

# Bare numbers in the Bufferzone fallback: every observed pairing with
# Lovkrav/Enhed reads small numbers as kilometres ("3" ↔ "3 km") and
# large ones as metres ("150" ↔ "150 m").
_KM_THRESHOLD = 10.0


def discover_feed_url(page: bytes, page_url: str) -> str:
    """The current GeoJSON item URL from the droneregler.dk page's HTML."""
    match = _GEOJSON_LINK_RE.search(page.decode("utf-8", errors="replace"))
    if not match:
        raise AirspaceError(
            "could not find the GeoJson download on the droneregler.dk "
            f"page ({page_url}) — the page layout may have changed"
        )
    return urljoin(page_url, match.group(1))


def _dedup_key(props: dict) -> tuple[str, str]:
    # typeId is deliberately absent: the live file spells it differently
    # between a zone's point marker and its polygon ("Retsvæsen" vs
    # "Restvæsen"), while title and colour agree.
    return (
        str(props.get("title") or "").strip(),
        str(props.get("Farve") or "").strip(),
    )


def _buffer_m(props: dict, where: str) -> float | None:
    """The published buffer distance of a point-only zone, in metres.

    ``None`` for an awareness-class point with no distance anywhere —
    a site marker, not a zone. Restrictive classes must carry one."""
    lovkrav = props.get("Lovkrav")
    enhed = str(props.get("Enhed") or "").strip()
    if isinstance(lovkrav, (int, float)) and lovkrav > 0 and enhed in (
        "1", "1000"
    ):
        # Enhed "1" pairs with kilometre distances, "1000" with metres —
        # probed against the human-readable Bufferzone strings.
        return float(lovkrav) * (1000.0 if enhed == "1" else 1.0)
    text = str(props.get("Bufferzone") or "").strip().lower()
    match = re.match(r"^(\d+(?:[.,]\d+)?)\s*(km|m(?:eter)?)?$", text)
    if match:
        value = float(match.group(1).replace(",", "."))
        unit = match.group(2)
        if unit == "km":
            return value * 1000.0
        if unit is not None:
            return value
        return value * 1000.0 if value <= _KM_THRESHOLD else value
    if str(props.get("Farve") or "").strip() == "5":
        return None
    raise AirspaceError(
        f"{where}: point zone has no usable buffer distance "
        f"(Lovkrav={lovkrav!r}, Enhed={enhed!r}, Bufferzone={text!r})"
    )


def _circle_ring(
    lon: float, lat: float, radius_m: float
) -> list[tuple[float, float]]:
    step = 360.0 / _CIRCLE_POINTS
    ring = []
    for k in range(_CIRCLE_POINTS + 1):
        p_lat, p_lon = _destination((lat, lon), k * step, radius_m)
        ring.append((p_lon, p_lat))
    return ring


def _position(pos, where: str) -> tuple[float, float]:
    # Positions are [lon, lat] or [lon, lat, z]; only the first two count.
    try:
        return float(pos[0]), float(pos[1])
    except (TypeError, ValueError, IndexError) as exc:
        raise AirspaceError(f"{where}: malformed position {pos!r}") from exc


def _rings(
    geometry: dict, where: str
) -> tuple[list[list[tuple[float, float]]], list[list[tuple[float, float]]]]:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    polys = [coords] if gtype == "Polygon" else coords
    polygons: list[list[tuple[float, float]]] = []
    holes: list[list[tuple[float, float]]] = []
    for poly in polys:
        for ring_index, ring in enumerate(poly):
            parsed = [_position(pos, where) for pos in ring]
            # GeoJSON ring order: 0 is an exterior, the rest are holes —
            # kept apart so the evaluator subtracts them (#422).
            (polygons if ring_index == 0 else holes).append(parsed)
    return polygons, holes


def _applicability(props: dict, where: str) -> list[Applicability]:
    start_raw = props.get("datoTidSTART")
    end_raw = props.get("datoTidSLUT")
    if not start_raw and not end_raw:
        return []

    def parse(raw, label):
        if not raw:
            return None
        try:
            parsed = parsedate_to_datetime(str(raw))
        except (TypeError, ValueError) as exc:
            raise AirspaceError(
                f"{where}: unparseable {label} {raw!r}"
            ) from exc
        # Naive UTC, like ed269._utc: Track.utc is naive, and the
        # evaluator's window comparison must never mix awareness (#520).
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    return [
        Applicability(
            start=parse(start_raw, "datoTidSTART"),
            end=parse(end_raw, "datoTidSLUT"),
            permanent=False,
        )
    ]


def parse_dronezoner(raw: bytes, source: SourceInfo) -> list[Zone]:
    """Every zone of the Danish Dronezoner GeoJSON as normalized Zones."""
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except ValueError as exc:
        raise AirspaceError(f"{source.feed}: feed is not JSON ({exc})") from exc
    features = data.get("features") if isinstance(data, dict) else None
    if not isinstance(features, list):
        raise AirspaceError(
            f"{source.feed}: not a Dronezoner document (no 'features' list)"
        )

    polygon_keys = {
        _dedup_key(feat.get("properties") or {})
        for feat in features
        if isinstance(feat, dict)
        and isinstance(feat.get("geometry"), dict)
        and feat["geometry"].get("type") in ("Polygon", "MultiPolygon")
    }

    zones: list[Zone] = []
    for i, feat in enumerate(features):
        where = f"{source.feed}: feature {i}"
        if not isinstance(feat, dict):
            raise AirspaceError(f"{where}: not an object")
        props = feat.get("properties")
        if not isinstance(props, dict):
            raise AirspaceError(f"{where}: missing properties")
        title = str(props.get("title") or "").strip()
        where = f"{where} ({title or 'untitled'})"
        # The authority's own inactive flag (e.g. a finished event zone).
        if str(props.get("Aktiv") or "").strip().upper() == "NEJ":
            continue
        farve = str(props.get("Farve") or "").strip()
        restriction = _RESTRICTION_BY_FARVE.get(farve)
        if restriction is None:
            raise AirspaceError(
                f"{where}: unknown zone colour class Farve={farve!r}"
            )
        geometry = feat.get("geometry")
        if not isinstance(geometry, dict):
            raise AirspaceError(f"{where}: missing geometry")
        gtype = geometry.get("type")
        if gtype in ("Polygon", "MultiPolygon"):
            polygons, holes = _rings(geometry, where)
            if not polygons:
                raise AirspaceError(f"{where}: no polygon geometry")
        elif gtype == "Point":
            # A point duplicating a polygon feature is that zone's map
            # marker; a point with no polygon twin IS the zone, published
            # as centre + buffer distance.
            if _dedup_key(props) in polygon_keys:
                continue
            radius_m = _buffer_m(props, where)
            if radius_m is None:
                continue  # an extent-less site marker, not a zone
            lon, lat = _position(geometry.get("coordinates"), where)
            polygons = [_circle_ring(lon, lat, radius_m)]
            holes = []
        else:
            raise AirspaceError(
                f"{where}: geometry type {gtype!r} is not supported"
            )
        object_id = props.get("OBJECTID")
        if not isinstance(object_id, int):
            raise AirspaceError(f"{where}: missing OBJECTID")
        zones.append(
            Zone(
                identifier=f"DK-{object_id}",
                name=title or f"DK-{object_id}",
                restriction=restriction,
                # The dataset publishes no vertical limits; Elevation_* is
                # the aerodrome site elevation and stays in `native`.
                lower=None,
                upper=None,
                applicability=_applicability(props, where),
                polygons=polygons,
                holes=holes,
                source=source,
                native=feat,
            )
        )
    return zones
