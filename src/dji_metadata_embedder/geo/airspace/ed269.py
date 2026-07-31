"""ED-269 (EUROCAE) UAS geographical-zone document parser (#413).

One parser covers every state that publishes the common format; the feed
registry pins the live-verified endpoints (Luxembourg CC0, Finland CC BY).
All-or-nothing: any malformed zone raises — a record listing 700 of 720
zones without saying so would be silently wrong. Wire quirks from the live
feeds are contract: UTF-8 BOM (utf-8-sig), absent limits mean "not stated".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from .model import Applicability, AirspaceError, SourceInfo, VerticalLimit, Zone


@dataclass(frozen=True)
class Ed269Feed:
    code: str
    url: str
    feed_name: str
    license: str
    caveat: str
    note: str | None = None


_CAVEAT = (
    "UAS geographical-zone data is informational and is not an "
    "authorization to fly."
)

ED269_FEEDS: dict[str, Ed269Feed] = {
    "LU": Ed269Feed(
        code="LU",
        url="https://drones.geoportail.lu/zones",
        feed_name="Luxembourg UAS geographical zones (ED-269)",
        license="CC0 (data.public.lu)",
        caveat=_CAVEAT,
    ),
    "FI": Ed269Feed(
        code="FI",
        url=(
            "https://eservices.traficom.fi/Ilmatilasovellus/api/"
            "uas-reservations/json?lang=fi"
        ),
        feed_name="Finland UAS geographical zones (ED-269, Traficom)",
        license="CC BY 4.0 (Traficom open data)",
        caveat=_CAVEAT,
        note=(
            "Established zones only — temporary reservations and "
            "activations are not part of this document."
        ),
    ),
}


def _utc(raw: str, where: str) -> datetime:
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AirspaceError(f"{where}: {raw!r} is not an ISO datetime") from exc
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _limit(
    geom: dict, side: str, unit: str, where: str
) -> VerticalLimit | None:
    value = geom.get(f"{side}Limit")
    if value is None:
        return None  # "not stated" — never 0
    ref = geom.get(f"{side}VerticalReference")
    if ref not in ("AGL", "AMSL"):
        raise AirspaceError(
            f"{where}: {side}VerticalReference is {ref!r}, expected AGL/AMSL"
        )
    if not isinstance(value, (int, float)):
        raise AirspaceError(f"{where}: {side}Limit {value!r} is not a number")
    return VerticalLimit(float(value), unit, ref)


def parse_ed269(raw: bytes, source: SourceInfo) -> list[Zone]:
    """Every zone of an ED-269 document as normalized :class:`Zone`s."""
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except ValueError as exc:
        raise AirspaceError(f"{source.feed}: feed is not JSON ({exc})") from exc
    features = data.get("features") if isinstance(data, dict) else data
    if not isinstance(features, list):
        raise AirspaceError(
            f"{source.feed}: not an ED-269 document (no 'features' list)"
        )
    zones: list[Zone] = []
    for i, feat in enumerate(features):
        where = f"{source.feed}: zone {i}"
        if not isinstance(feat, dict):
            raise AirspaceError(f"{where}: not an object")
        ident = feat.get("identifier")
        restriction = feat.get("restriction")
        if not isinstance(ident, str) or not ident:
            raise AirspaceError(f"{where}: missing identifier")
        if not isinstance(restriction, str) or not restriction:
            raise AirspaceError(f"{where} ({ident}): missing restriction")
        applicability: list[Applicability] = []
        always_applicable = False
        for win in feat.get("applicability") or []:
            if str(win.get("permanent", "")).upper() == "YES":
                # A permanent entry makes the whole zone always applicable,
                # even alongside timed windows — collecting only the timed
                # windows here would let the evaluator bucket an
                # always-applicable zone as "not applicable".
                always_applicable = True
                break
            start = win.get("startDateTime")
            end = win.get("endDateTime")
            applicability.append(
                Applicability(
                    start=_utc(start, f"{where}: startDateTime") if start else None,
                    end=_utc(end, f"{where}: endDateTime") if end else None,
                    permanent=False,
                )
            )
        if always_applicable:
            applicability = []
        lower: VerticalLimit | None = None
        upper: VerticalLimit | None = None
        polygons: list[list[tuple[float, float]]] = []
        holes: list[list[tuple[float, float]]] = []
        for geom in feat.get("geometry") or []:
            unit = "ft" if str(geom.get("uomDimensions", "M")).upper() == "FT" else "m"
            geom_lower = _limit(geom, "lower", unit, where)
            geom_upper = _limit(geom, "upper", unit, where)
            if geom_lower is not None:
                if lower is not None and lower != geom_lower:
                    raise AirspaceError(
                        f"{where} ({ident}): differing lowerLimit across "
                        "geometry entries — stratified zones are not supported"
                    )
                lower = geom_lower
            if geom_upper is not None:
                if upper is not None and upper != geom_upper:
                    raise AirspaceError(
                        f"{where} ({ident}): differing upperLimit across "
                        "geometry entries — stratified zones are not supported"
                    )
                upper = geom_upper
            proj = geom.get("horizontalProjection") or {}
            if proj.get("type") != "Polygon":
                raise AirspaceError(
                    f"{where} ({ident}): horizontalProjection type "
                    f"{proj.get('type')!r} is not supported"
                )
            for ring_index, ring in enumerate(proj.get("coordinates") or []):
                try:
                    parsed = [(float(x), float(y)) for x, y in ring]
                except (TypeError, ValueError) as exc:
                    raise AirspaceError(
                        f"{where} ({ident}): malformed ring coordinates"
                    ) from exc
                # GeoJSON Polygon: ring 0 is the exterior, the rest are
                # holes — kept apart so the evaluator subtracts them (#422).
                (polygons if ring_index == 0 else holes).append(parsed)
        if not polygons:
            raise AirspaceError(f"{where} ({ident}): no polygon geometry")
        zones.append(
            Zone(
                identifier=ident,
                name=str(feat.get("name") or ident),
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
