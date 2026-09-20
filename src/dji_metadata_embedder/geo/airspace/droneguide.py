"""Belgium UAS geographical-zone provider: the Droneguide WFS (#562).

Belgium publishes its UAS geographical zones through the Droneguide
platform (Unifly's DroneWeb, operated by skeyes for the BCAA/DGLV). The
public map's own GeoServer answers OGC WFS requests anonymously; this
provider reads the ``uaszone`` feature type with the publisher's
flight-window parameters, so the server drops zones that had already
expired when the flight began and flags, per zone, whether it was active
during the window (``active_within_window``: 0 = active, 1 = not). The
zone rows carry no dates themselves; NOTAM-type zones get their validity
from the separate ``notam`` layer, joined on the NOTAM id.

Permission record: BCAA letter ref G26-187 (2026-09-16): no individual
authorisation is required, reuse falls under the public-sector-information
framework, and Droneguide is an official publication channel. The BCAA
asked for four notices to stay visible and permanently accessible; they
ride in the feed note, so every record and popup carries them.

Two traps the live layer has: 420 world time-zone polygons leak into the
zone feature type (96 % of the bytes; filtered server-side and rejected
here if one ever gets through), and 38 NOTAM rows publish a flight level
against a GND or MSL reference — a flight level is a pressure datum by
definition, so the unit wins and the row's own words stay in ``native``.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

from .model import (
    AirspaceError,
    Applicability,
    SourceInfo,
    VerticalLimit,
    Zone,
    iso_utc,
)

Window = tuple[datetime, datetime]
Ring = list[tuple[float, float]]


@dataclass(frozen=True)
class DroneguideFeed:
    code: str
    page_url: str
    ows_url: str
    feed_name: str
    license: str
    caveat: str
    note: str


_CAVEAT = (
    "UAS geographical-zone data is informational and is not an authorization to fly."
)

NO_TIMESTAMPS_NOTE = (
    "Validity for this flight was not evaluated by the publisher (the "
    "track has no complete timestamps)."
)
NOT_ACTIVE_REASON = "not active during the flight window (publisher's evaluation)"

DRONEGUIDE_FEEDS: dict[str, DroneguideFeed] = {
    "BE": DroneguideFeed(
        code="BE",
        page_url="https://map.droneguide.be/",
        ows_url="https://map.droneguide.be/ows",
        feed_name="Belgium UAS geographical zones (Droneguide, skeyes for the BCAA)",
        license=(
            "© Belgian Civil Aviation Authority (BCAA/DGLV, FPS Mobility and "
            "Transport), published through the Droneguide platform operated "
            "by skeyes; reuse under the public-sector-information framework, "
            "no individual authorisation required (BCAA ref. G26-187, "
            "2026-09-16)"
        ),
        caveat=_CAVEAT,
        # The BCAA's four notices (letter G26-187), in substance and in this
        # order: source, not official, official channels only, pilot's
        # responsibility — followed by what the feed does and does not carry.
        note=(
            "Not an official application of the BCAA or the Belgian "
            "authorities. Only the official publication channels (Droneguide, "
            "the AIP and NOTAM service, and the CIS API) are authoritative "
            "regulatory sources; responsibility for verifying regulatory "
            "compliance remains with the remote pilot and UAS operator. Zone "
            "validity for the flight window is the publisher's evaluation; "
            "NOTAM zone dates come from the Droneguide NOTAM layer; other "
            "schedules are not in the feed."
        ),
    ),
}

_WFS = {
    "service": "WFS",
    "version": "2.0.0",
    "request": "GetFeature",
    "outputFormat": "application/json",
}
_NOTAM_FIELDS = (
    "identification,start_date,end_date,scheduling,selection_code,location,fir"
)
_LANGS = ("en", "nl", "fr", "de")
_UNITS = {"F": "ft", "M": "m", "FL": "FL"}
_REFS = {"GND": "AGL", "MSL": "AMSL", "STD": "STD"}
_UNLIMITED_FL = 999.0
_UNMATCHED_NOTAM = "NOTAM validity dates not found in the Droneguide NOTAM layer"


def _instant(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def zones_url(ows_url: str, window: Window | None) -> str:
    """The ``uaszone`` GetFeature URL, with the publisher's window parameters
    when the flight has one (GeoServer viewparams: colons inside a value are
    escaped as ``\\:``; the public map builds exactly this string)."""
    params = dict(_WFS, typeNames="uaszone", cql_filter="type_code<>'TIME_ZONE'")
    if window is not None:
        start, end = (_instant(d).replace(":", "\\:") for d in window)
        params["viewparams"] = (
            f"window_start:{start};window_end:{end};show_planned:true"
        )
    return f"{ows_url}?{urlencode(params)}"


def notam_url(ows_url: str) -> str:
    params = dict(_WFS, typeNames="notam", propertyName=_NOTAM_FIELDS)
    return f"{ows_url}?{urlencode(params)}"


def cache_name(code: str, window: Window | None) -> str:
    if window is None:
        return f"droneguide-{code}-nowindow.json"
    # Second resolution: the same instants the request names, so two
    # flights a few seconds apart never share one publisher evaluation.
    start, end = (d.strftime("%Y%m%dT%H%M%SZ") for d in window)
    return f"droneguide-{code}-{start}-{end}.json"


def _json_body(body: bytes, what: str) -> object:
    try:
        return json.loads(body.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise AirspaceError(f"Droneguide {what} response is not JSON ({exc})") from exc


def build_envelope(
    zones_body: bytes, notam_body: bytes, window: Window | None
) -> bytes:
    """One cacheable document holding both responses and the window they
    were asked for, so cached and fresh bodies parse identically."""
    doc = {
        "window": None
        if window is None
        else [d.strftime("%Y-%m-%dT%H:%M:%SZ") for d in window],
        "zones": _json_body(zones_body, "zones"),
        "notam": _json_body(notam_body, "notam"),
    }
    return json.dumps(doc).encode("utf-8")


def _text(raw: object) -> str | None:
    """A Droneguide text field: plain, or a JSON object of language → text
    (en, then nl, fr, de). Live 2026-09-16: 706 en-only maps, 34 four-
    language maps, 277 plain NOTAM ids."""
    if raw is None:
        return None
    text = str(raw).strip()
    if text.startswith("{"):
        try:
            mapping = json.loads(text)
        except ValueError:
            return text or None
        if isinstance(mapping, dict):
            for lang in _LANGS:
                value = mapping.get(lang)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return None
    return text or None


def _limit(props: dict, side: str, where: str) -> VerticalLimit | None:
    value = props.get(f"{side}_limit_altitude")
    if value is None:
        # "not stated" — never 0 (33 temporary zones publish no lower limit).
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AirspaceError(f"{where}: {side} limit {value!r} is not a number")
    unit_raw = props.get(f"{side}_limit_unit")
    unit = _UNITS.get(str(unit_raw))
    if unit is None:
        raise AirspaceError(f"{where}: {side} limit unit {unit_raw!r} is not F/M/FL")
    if unit == "FL":
        # A flight level is a pressure datum whatever the row says (38 live
        # NOTAM rows publish "FL 75 GND"); the row's own reference stays in
        # native.
        reference = "STD"
    else:
        ref_raw = props.get(f"{side}_limit_reference")
        reference = _REFS.get(str(ref_raw), "")
        if not reference:
            raise AirspaceError(
                f"{where}: {side} limit reference {ref_raw!r} is not GND/MSL/STD"
            )
    return VerticalLimit(float(value), unit, reference)


def _ring(raw: object, where: str) -> Ring:
    if not isinstance(raw, list):
        raise AirspaceError(f"{where}: malformed ring coordinates")
    try:
        return [(float(x), float(y)) for x, y in raw]
    except (TypeError, ValueError) as exc:
        raise AirspaceError(f"{where}: malformed ring coordinates") from exc


def _geometry(geometry: object, where: str) -> tuple[list[Ring], list[Ring]]:
    gtype = geometry.get("type") if isinstance(geometry, dict) else None
    coords = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if gtype == "Polygon":
        polygons_raw = [coords or []]
    elif gtype == "MultiPolygon":
        polygons_raw = list(coords or [])
    else:
        raise AirspaceError(
            f"{where}: geometry type {gtype!r} is not Polygon/MultiPolygon"
        )
    polygons: list[Ring] = []
    holes: list[Ring] = []
    for rings in polygons_raw:
        for index, ring in enumerate(rings or []):
            # GeoJSON: ring 0 is the exterior, the rest are holes (#422).
            (polygons if index == 0 else holes).append(_ring(ring, where))
    if not polygons:
        raise AirspaceError(f"{where}: no polygon geometry")
    return polygons, holes


def _features(collection: object, what: str, feed: str) -> list:
    features = collection.get("features") if isinstance(collection, dict) else None
    if not isinstance(features, list):
        raise AirspaceError(f"{feed}: {what} response has no 'features' list")
    return features


def _notam_index(collection: object, feed: str) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for feature in _features(collection, "notam", feed):
        props = feature.get("properties") if isinstance(feature, dict) else None
        if not isinstance(props, dict):
            raise AirspaceError(f"{feed}: notam row is not a feature object")
        ident = props.get("identification")
        if not isinstance(ident, str) or not ident:
            raise AirspaceError(f"{feed}: notam row without an identification")
        if ident in index:
            raise AirspaceError(f"{feed}: duplicate NOTAM identification {ident!r}")
        index[ident] = props
    return index


def parse_droneguide(raw: bytes, source: SourceInfo) -> list[Zone]:
    """Every zone of a cached Droneguide envelope as normalized :class:`Zone`s."""
    feed = source.feed
    try:
        env = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise AirspaceError(f"{feed}: cache/response is not JSON ({exc})") from exc
    if not isinstance(env, dict) or not {"window", "zones", "notam"} <= env.keys():
        raise AirspaceError(f"{feed}: not a Droneguide envelope (window/zones/notam)")
    windowed = env["window"] is not None
    notams = _notam_index(env["notam"], feed)

    rows: list[tuple[dict, dict]] = []
    for index, feature in enumerate(_features(env["zones"], "zones", feed)):
        props = feature.get("properties") if isinstance(feature, dict) else None
        if not isinstance(props, dict):
            raise AirspaceError(f"{feed}: zone {index}: not a feature object")
        rows.append((feature, props))
    # A published code is the identifier; live 2026-09-16 four codes are
    # shared (EBBL/EBFS/EBBE across CTR/CTA/TMA, "Temporary" ×6), so those
    # rows carry a uuid suffix — deterministic and still readable.
    shared = {
        code for code, n in Counter(p.get("code") for _, p in rows).items() if n > 1
    }

    zones: list[Zone] = []
    for index, (feature, props) in enumerate(rows):
        where = f"{feed}: zone {index}"
        type_code = str(props.get("type_code") or "")
        if type_code == "TIME_ZONE":
            raise AirspaceError(
                f"{where}: TIME_ZONE row reached the parser (server filter ignored?)"
            )
        code = props.get("code")
        uuid = props.get("unique_identifier")
        if not isinstance(code, str) or not code:
            raise AirspaceError(f"{where}: missing code")
        if not isinstance(uuid, str) or not uuid:
            raise AirspaceError(f"{where} ({code}): missing unique_identifier")
        ident = f"{code}:{uuid[:8]}" if code in shared else code
        where = f"{feed}: zone {ident}"
        name = _text(props.get("name"))
        if not name:
            raise AirspaceError(f"{where}: missing name")
        restriction = props.get("restriction")
        if not isinstance(restriction, str) or not restriction:
            raise AirspaceError(f"{where}: missing restriction")
        lower = _limit(props, "lower", where)
        upper = _limit(props, "upper", where)
        if upper is not None and upper.unit == "FL" and upper.value == _UNLIMITED_FL:
            # FL 999 = unlimited (25 live rows): "not stated", as for the UK.
            upper = None
        polygons, holes = _geometry(feature.get("geometry"), where)

        native = dict(props)
        applicability: list[Applicability] = []
        activation: list[str] = []
        notes = [f"Droneguide type: {type_code}"] if type_code else []
        description = _text(props.get("description"))
        if description:
            notes.append(description)
        if type_code == "NOTAM":
            row = notams.get(name)
            if row is None:
                notes.append(_UNMATCHED_NOTAM)
            else:
                native["notam"] = row
                start = row.get("start_date")
                end = row.get("end_date")
                applicability.append(
                    Applicability(
                        start=iso_utc(start, f"{where}: start_date") if start else None,
                        end=iso_utc(end, f"{where}: end_date") if end else None,
                        permanent=False,
                    )
                )
                if row.get("scheduling"):
                    activation.append(str(row["scheduling"]))
                tag = " ".join(
                    str(row[k]) for k in ("selection_code", "location") if row.get(k)
                )
                if tag:
                    notes.append(f"NOTAM {tag}")
        not_active = (
            NOT_ACTIVE_REASON
            if windowed and props.get("active_within_window") == 1
            else None
        )
        zones.append(
            Zone(
                identifier=ident,
                name=name,
                restriction=restriction,
                lower=lower,
                upper=upper,
                applicability=applicability,
                polygons=polygons,
                holes=holes,
                source=source,
                native=native,
                activation=activation,
                notes=notes,
                not_active_reason=not_active,
            )
        )
    return zones
