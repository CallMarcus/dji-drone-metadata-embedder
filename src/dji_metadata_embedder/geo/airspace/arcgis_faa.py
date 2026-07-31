"""FAA UAS Facility Map provider (#413): keyless ArcGIS bbox query.

The bbox is padded and snapped outward to a 0.1-degree grid before it goes
on the wire, so the endpoint learns no more about the flight than a DEM
tile fetch already reveals. Paging follows ``exceededTransferLimit`` until
complete — a truncated grid must never present itself as full coverage.
"""

from __future__ import annotations

import hashlib
import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from .model import AirspaceError, SourceInfo, VerticalLimit, Zone

FAA_QUERY_URL = (
    "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest/services/"
    "FAA_UAS_FacilityMap_Data/FeatureServer/0/query"
)
FAA_FEED = (
    "FAA UAS Facility Maps",
    "U.S. Government work (FAA UAS Data Delivery System)",
    "UAS Facility Map data is informational and does not constitute an "
    "airspace authorization (LAANC or otherwise).",
)
_GRID = 0.1
_PAD = 0.05
_TIMEOUT_S = 60


def snap_bbox(
    bbox: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    """Pad by 0.05 deg, then snap outward to the 0.1-deg privacy grid."""
    x1, y1, x2, y2 = bbox
    return (
        round(math.floor((x1 - _PAD) / _GRID) * _GRID, 1),
        round(math.floor((y1 - _PAD) / _GRID) * _GRID, 1),
        round(math.ceil((x2 + _PAD) / _GRID) * _GRID, 1),
        round(math.ceil((y2 + _PAD) / _GRID) * _GRID, 1),
    )


def _query(bbox: tuple[float, float, float, float], offset: int) -> str:
    x1, y1, x2, y2 = bbox
    params = {
        "geometry": f"{x1},{y1},{x2},{y2}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "f": "geojson",
    }
    if offset:
        params["resultOffset"] = str(offset)
    return f"{FAA_QUERY_URL}?{urlencode(params)}"


def fetch_faa_pages(
    bbox: tuple[float, float, float, float], transport
) -> list[bytes]:
    """All response pages for the snapped *bbox*; raises on any failure."""
    snapped = snap_bbox(bbox)
    pages: list[bytes] = []
    offset = 0
    while True:
        req = Request(_query(snapped, offset), headers={"User-Agent": "dji-embed"})
        try:
            with transport(req, timeout=_TIMEOUT_S) as resp:
                body = resp.read()
        except HTTPError as exc:
            raise AirspaceError(
                f"FAA facility-map query answered HTTP {exc.code}"
            ) from exc
        except (URLError, OSError) as exc:
            raise AirspaceError(
                f"FAA facility-map query failed: {exc}"
            ) from exc
        pages.append(body)
        try:
            doc = json.loads(body)
        except ValueError as exc:
            raise AirspaceError(
                "FAA facility-map response is not JSON"
            ) from exc
        if isinstance(doc, dict) and "error" in doc:
            err = doc["error"]
            message = err.get("message") if isinstance(err, dict) else err
            raise AirspaceError(
                f"FAA facility-map query returned an error: {message}"
            )
        if not isinstance(doc, dict) or "features" not in doc:
            raise AirspaceError(
                "FAA facility-map response has no 'features' list"
            )
        exceeded = doc.get("exceededTransferLimit") or (
            isinstance(doc.get("properties"), dict)
            and doc["properties"].get("exceededTransferLimit")
        )
        if not exceeded:
            return pages
        features = doc.get("features") or []
        if not features:
            raise AirspaceError(
                "FAA facility-map paging cannot establish completeness "
                "(transfer limit flagged on an empty page)"
            )
        # Advance by the real feature count returned by this page — the
        # server's page size may be under the ArcGIS default of 1000, and
        # guessing a fixed stride would silently skip records.
        offset += len(features)


def parse_faa(pages: list[bytes], source: SourceInfo) -> list[Zone]:
    """Normalize UASFM grid cells: CEILING feet AGL -> Zone. All-or-nothing."""
    zones: list[Zone] = []
    # One running index across pages so error messages carry the true
    # position ("cell 1043", not a second "cell 0") — the identifier
    # fallback below is content-derived, not index-based (#424).
    index = 0
    for page in pages:
        doc = json.loads(page)
        for feat in doc.get("features") or []:
            props = feat.get("properties") or {}
            where = f"{source.feed}: cell {index}"
            ceiling = props.get("CEILING")
            if not isinstance(ceiling, (int, float)):
                raise AirspaceError(f"{where}: CEILING is {ceiling!r}")
            geom = feat.get("geometry") or {}
            if geom.get("type") != "Polygon":
                raise AirspaceError(
                    f"{where}: geometry type {geom.get('type')!r} unsupported"
                )
            rings = [
                [(float(x), float(y)) for x, y in ring]
                for ring in geom.get("coordinates") or []
            ]
            if not rings:
                raise AirspaceError(f"{where}: no polygon coordinates")
            # GeoJSON Polygon: ring 0 is the exterior, the rest are holes —
            # kept apart so the evaluator subtracts them (#422).
            polygons = rings[:1]
            holes = rings[1:]
            apt = props.get("APT1_NAME") or props.get("APT1_ICAO") or "UASFM"
            oid = props.get("OBJECTID")
            if oid is None:
                # Content-derived fallback, stable across pages, fetches
                # and reruns: any counter restarts somewhere (per page, or
                # per parse_faa call when each track fetches its own bbox)
                # and collides on the overlay's (feed, identifier) dedupe
                # key, silently dropping a zone. Identical geometry+ceiling
                # hashing identically is correct — that IS the same cell,
                # and collapsing it is deduplication, not loss (#424).
                digest = hashlib.sha1(
                    f"{ceiling}:{rings!r}".encode()
                ).hexdigest()[:10]
                ident = f"cell-{digest}"
            else:
                ident = str(oid)
            index += 1
            zones.append(
                Zone(
                    identifier=f"UASFM-{ident}",
                    name=f"UASFM grid cell ({apt})",
                    restriction="CEILING",
                    lower=VerticalLimit(0, "ft", "AGL"),
                    upper=VerticalLimit(float(ceiling), "ft", "AGL"),
                    applicability=[],
                    polygons=polygons,
                    holes=holes,
                    source=source,
                    native=props,
                )
            )
    return zones
