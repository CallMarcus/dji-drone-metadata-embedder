"""ENAIRE (Spain) UAS geographical-zone provider (#451).

The documented servAIS V2 ArcGIS service answers keyless. Its GeoJSON is
the ED-318 vocabulary flattened into feature ``properties`` (limits as
``lower``/``upper`` + ``*Reference`` + ``uom``), with empties published as
"", the string "None" or null, and ``type`` spelled REQ_AUTHORIZATION.
The infrastructure layer refuses whole-country pulls (HTTP 500), so zones
are fetched per flight by a padded, grid-snapped bbox like the FAA grid.

Identifiers are not unique in this feed: the infrastructure layer uses one
identifier for hundreds of protection pieces, and the aerodrome layer
reuses a few identifiers for different ultralight fields. Pieces sharing
an identifier AND the same published attributes merge into one multi-
polygon zone; different zones under one identifier are kept apart with
the publisher's GUID appended, so none is dropped by the overlay's
(feed, identifier) dedupe.

Layer 3 (ZGUAS_Urbano) is deliberately not fetched: it is four territory-
wide polygons carrying one reminder ("check whether the flight area is an
urban environment"), not a place; every flight would "enter" it. The
reminder rides as the feed note instead.

Permission record (issue #451): ENAIRE AIS helpdesk, caso 44348,
2026-09-29: use is public, no agreement needed, provided it is stated
expressly that ENAIRE holds the intellectual and industrial property
rights (Aviso Legal §6). That email is the written authorisation §6 asks
for. ENAIRE's own "Uso y limitaciones" page: the geometry is informative,
the AIP is normative.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from functools import partial
from urllib.parse import urlencode

from .arcgis import fetch_arcgis_pages
from .arcgis_faa import snap_bbox
from .ed318 import _rings
from .model import (
    AirspaceError,
    Applicability,
    SourceInfo,
    VerticalLimit,
    Zone,
    iso_utc,
)

ENAIRE_BASE = (
    "https://servais.enaire.es/insigniads/rest/services/NSF_SRV/"
    "SRV_UAS_ZG_data_V2/FeatureServer"
)
# Published layer ids: 2 = ZGUAS_Aero (aerodromes, CTR/ATZ/TMA, restricted
# areas, RVF), 0 = ZGUAS_Infraestructuras (infrastructure protection).
# 3 = ZGUAS_Urbano is excluded on purpose (see the module docstring); 1 is
# promised by the spec and not published.
ENAIRE_LAYERS: tuple[int, ...] = (2, 0)


@dataclass(frozen=True)
class EnaireFeed:
    code: str
    feed_name: str
    license: str
    caveat: str
    note: str | None = None


_CAVEAT = (
    "UAS geographical-zone data is informational and is not an authorization to fly."
)

ENAIRE_FEED = EnaireFeed(
    code="ES",
    feed_name="Spain UAS geographical zones (ED-318, ENAIRE)",
    license=(
        "© ENAIRE, titular de los derechos de propiedad intelectual e "
        "industrial de estos datos (Aviso Legal, apartado 6); reuse "
        "authorised in writing by ENAIRE AIS, caso 44348, 2026-09-29"
    ),
    caveat=_CAVEAT,
    note=(
        "ENAIRE publishes this geometry as informative; the AIP (PDF/HTML) "
        "is the normative reference. The service is refreshed on the 28-day "
        "AIRAC cycle and states no edition date, so only the fetch time is "
        "shown. Zones are fetched for the flight's area only. The service's "
        "ZGUAS_Urbano layer is not drawn as a zone: it is ENAIRE's "
        "territory-wide reminder that flights in an urban environment "
        "(built-up areas, serviced residential, commercial or industrial "
        "areas, public recreation areas including qualifying beaches, parks "
        "and gardens) must be notified to the Ministerio del Interior at "
        "least five calendar days ahead by operators subject to "
        "registration, and that overflying or approaching buildings in the "
        "Open category needs the permission of the responsible party; see "
        "AESA's UAS-OPS-DT01 on UAS geographical zones."
    ),
)


def query_url(layer: int, bbox: tuple[float, float, float, float], offset: int) -> str:
    """One page of *layer* for *bbox* (already snapped), GeoJSON out."""
    x1, y1, x2, y2 = bbox
    params = {
        "where": "1=1",
        "geometry": f"{x1},{y1},{x2},{y2}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "f": "geojson",
    }
    if offset:
        params["resultOffset"] = str(offset)
    return f"{ENAIRE_BASE}/{layer}/query?{urlencode(params)}"


def fetch_enaire_body(bbox: tuple[float, float, float, float], transport) -> bytes:
    """Every layer's pages for the snapped *bbox* as one cacheable JSON body."""
    snapped = snap_bbox(bbox)
    layers: dict[str, list] = {}
    for layer in ENAIRE_LAYERS:
        pages = fetch_arcgis_pages(
            partial(query_url, layer, snapped),
            f"ENAIRE ZGUAS layer {layer}",
            transport,
        )
        layers[str(layer)] = [json.loads(page) for page in pages]
    return json.dumps({"layers": layers}).encode("utf-8")


# Markup in the published messages: <elem>, <b>, <p>, <font ...>, </...>.
_TAG = re.compile(r"<[^>]+>")
# The service caps messages at 2000 characters, so a long one can end inside
# a tag (`<a href='https://...` with no closing `>`): drop that dangling tag.
_OPEN_TAG_AT_END = re.compile(r"<[^>]*$")
_WS = re.compile(r"\s+")


def _text(value: object) -> str | None:
    """A published string, or None for the service's three spellings of
    empty: "", the string "None", and null."""
    # The live service publishes the limits as JSON numbers.
    if isinstance(value, int | float) and not isinstance(value, bool):
        return str(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    return None if text in ("", "None") else text


def _plain(value: object) -> str | None:
    """Published prose with its markup stripped and whitespace collapsed.
    Shown as published: the messages carry ENAIRE's own coordination
    contacts, which are part of the text."""
    text = _text(value)
    if text is None:
        return None
    return (
        _WS.sub(
            " ", html.unescape(_TAG.sub(" ", _OPEN_TAG_AT_END.sub("", text)))
        ).strip()
        or None
    )


def _limit(props: dict, side: str, where: str) -> VerticalLimit | None:
    raw = _text(props.get(side))
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise AirspaceError(f"{where}: {side} {raw!r} is not a number") from exc
    reference = _text(props.get(f"{side}Reference"))
    if reference not in ("AGL", "AMSL"):
        raise AirspaceError(f"{where}: {side}Reference {reference!r} is not supported")
    uom = (_text(props.get("uom")) or "M").upper()
    if uom not in ("M", "FT"):
        raise AirspaceError(f"{where}: uom {uom!r} is not supported")
    unit = "ft" if uom == "FT" else "m"
    return VerticalLimit(value=value, unit=unit, reference=reference)


@dataclass
class _Piece:
    identifier: str
    guid: str
    name: str
    restriction: str
    lower: VerticalLimit | None
    upper: VerticalLimit | None
    applicability: list[Applicability]
    polygons: list[list[tuple[float, float]]]
    holes: list[list[tuple[float, float]]]
    notes: list[str]
    native: dict = field(default_factory=dict)

    @property
    def key(self) -> tuple:
        windows = tuple((w.start, w.end, w.permanent) for w in self.applicability)
        return (
            self.name,
            self.restriction,
            self.lower,
            self.upper,
            tuple(self.notes),
            windows,
        )


def _piece(feat: object, where: str) -> _Piece:
    if not isinstance(feat, dict):
        raise AirspaceError(f"{where}: not an object")
    props = feat.get("properties")
    if not isinstance(props, dict):
        raise AirspaceError(f"{where}: missing properties")
    ident = _text(props.get("identifier"))
    if ident is None:
        # The live Aero layer publishes at least one feature (an ENR 5.5 area
        # south-east of Madrid) with an empty identifier and name. Parsing is
        # all-or-nothing, so raising here would blank every flight whose box
        # reaches it. Synthesise a stable id from the subtype and the GUID;
        # only a feature with no identity at all is malformed.
        raw_guid = (
            _text(props.get("GFID")) or _text(props.get("OBJECTID")) or ""
        ).strip("{}")[:8]
        if not raw_guid:
            raise AirspaceError(f"{where}: missing identifier")
        subtype = _text(props.get("extendedProperties")) or "zone"
        ident = f"{subtype} [{raw_guid}]"
    restriction = _text(props.get("type"))
    if restriction is None:
        raise AirspaceError(f"{where} ({ident}): missing restriction type")
    # One concept, one label across countries: ED-269 feeds spell
    # REQ_AUTHORISATION with an S, this service with a Z (native keeps it).
    if restriction == "REQ_AUTHORIZATION":
        restriction = "REQ_AUTHORISATION"
    guid = (_text(props.get("GFID")) or _text(props.get("OBJECTID")) or "").strip("{}")[
        :8
    ]
    start = _text(props.get("startDateTime"))
    end = _text(props.get("endDateTime"))
    applicability: list[Applicability] = []
    if start or end:
        applicability.append(
            Applicability(
                start=iso_utc(start, f"{where} ({ident}): startDateTime")
                if start
                else None,
                end=iso_utc(end, f"{where} ({ident}): endDateTime") if end else None,
                permanent=False,
            )
        )
    notes = [
        text
        for text in (
            _text(props.get("extendedProperties")),
            _plain(props.get("message")),
            _plain(props.get("description")),
        )
        if text
    ]
    polygons, holes = _rings(feat.get("geometry") or {}, ident, where)
    if not polygons:
        raise AirspaceError(f"{where} ({ident}): no polygon geometry")
    return _Piece(
        identifier=ident,
        guid=guid,
        name=_text(props.get("name")) or ident,
        restriction=restriction,
        lower=_limit(props, "lower", f"{where} ({ident})"),
        upper=_limit(props, "upper", f"{where} ({ident})"),
        applicability=applicability,
        polygons=polygons,
        holes=holes,
        notes=notes,
        native=feat,
    )


def parse_enaire(raw: bytes, source: SourceInfo) -> list[Zone]:
    """Every zone in a cache body: pieces merged or disambiguated per
    identifier (module docstring). All-or-nothing."""
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        raise AirspaceError(f"{source.feed}: body is not JSON ({exc})") from exc
    layers = doc.get("layers") if isinstance(doc, dict) else None
    if not isinstance(layers, dict):
        raise AirspaceError(f"{source.feed}: body has no 'layers' object")
    groups: dict[str, list[_Piece]] = {}
    index = 0
    for layer_id in sorted(layers):
        pages = layers[layer_id]
        if not isinstance(pages, list):
            raise AirspaceError(f"{source.feed}: layer {layer_id} pages are not a list")
        for page in pages:
            feats = page.get("features") if isinstance(page, dict) else None
            if not isinstance(feats, list):
                raise AirspaceError(
                    f"{source.feed}: layer {layer_id} page has no 'features' list"
                )
            for feat in feats:
                piece = _piece(feat, f"{source.feed}: layer {layer_id} feature {index}")
                index += 1
                groups.setdefault(piece.identifier, []).append(piece)
    zones: list[Zone] = []
    for ident, pieces in groups.items():
        buckets: dict[tuple, list[_Piece]] = {}
        for n, piece in enumerate(pieces):
            # Holes are zone-wide (the evaluator and renderers apply every
            # hole to every polygon), so a holed piece merged with a piece
            # lying inside its hole would under-report. A holed piece always
            # gets its own bucket.
            key = piece.key + (("holed", n),) if piece.holes else piece.key
            buckets.setdefault(key, []).append(piece)
        for group in buckets.values():
            first = group[0]
            if len(buckets) == 1:
                zone_id = ident
            else:
                # min() keeps the suffix independent of publisher order.
                guid = min(piece.guid for piece in group)
                if not guid:
                    raise AirspaceError(
                        f"{source.feed}: identifier {ident!r} is published for "
                        "different zones without a GFID/OBJECTID to tell them apart"
                    )
                zone_id = f"{ident} [{guid}]"
            zones.append(
                Zone(
                    identifier=zone_id,
                    name=first.name,
                    restriction=first.restriction,
                    lower=first.lower,
                    upper=first.upper,
                    applicability=list(first.applicability),
                    polygons=[ring for piece in group for ring in piece.polygons],
                    holes=[ring for piece in group for ring in piece.holes],
                    source=source,
                    native=first.native
                    if len(group) == 1
                    else {"pieces": [piece.native for piece in group]},
                    notes=list(first.notes),
                )
            )
    return zones
