"""Estonia UAS geographical-zone parser (EANS uas.geojson, #511).

EANS's UTM system publishes the national zones as a plain GeoJSON
FeatureCollection whose feature properties embed one ED-269-style
volume: vertical limits live in ``properties.geometry`` under ED-269's
field names (``uomDimensions``/``lowerLimit``/``lowerVerticalReference``/…),
the applicability list uses ED-269 semantics (``permanent: "YES"`` means
always applicable, so no window materializes), and restrictions arrive
natively S-spelled. The display strings (``lower``/``upper``), metre
conversions and per-zone update timestamps ride in ``native`` untouched.

Two features are the publisher's viewer furniture, not zones, and are
skipped by contract rather than parsed: any feature flagged ``hidden``
(live: EEGZS1, the Droonikaart app's above-120 m shade) and ``EERZout``
("Outside Estonia"), a world-spanning PROHIBITED mask with Estonia as
its hole — rendering it would paint the entire planet as an Estonian
prohibition. Everything else malformed still raises; all-or-nothing
like the other providers.

Permission record (issue #511): EANS's UTM development manager confirmed
in writing on 2026-08-19 that the file is public data intended for use
in ground-control and planning tools; attribution to "Estonian Air
Navigation Services". Their own caveat — the file reflects the rules at
download time, not necessarily at flight time — ships in the feed note.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .ed269 import _utc
from .model import Applicability, AirspaceError, SourceInfo, VerticalLimit, Zone


@dataclass(frozen=True)
class EansFeed:
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

EANS_FEEDS: dict[str, EansFeed] = {
    "EE": EansFeed(
        code="EE",
        url="https://utm.eans.ee/avm/utm/uas.geojson",
        feed_name="Estonia UAS geographical zones (EANS)",
        license=(
            "© Estonian Air Navigation Services — public data intended "
            "for use in ground-control and planning tools (confirmed in "
            "writing by EANS UTM development, 2026-08-19)"
        ),
        caveat=_CAVEAT,
        note=(
            "The file reflects the airspace rules at the time of "
            "download, not necessarily at the time of the flight (EANS). "
            "NOTAM-area activation hours appear as text in the zone's "
            "published message and are not evaluated here."
        ),
    ),
}

# The publisher's viewer furniture: EERZout is a world-spanning
# "Outside Estonia" mask with Estonia as its hole.
_MASK_IDENTIFIERS = frozenset({"EERZout"})


def _limit(volume: dict, side: str, unit: str, where: str) -> VerticalLimit | None:
    value = volume.get(f"{side}Limit")
    if value is None:
        return None  # "not stated" — never 0
    ref = volume.get(f"{side}VerticalReference")
    if ref not in ("AGL", "AMSL"):
        raise AirspaceError(
            f"{where}: {side}VerticalReference is {ref!r}, expected AGL/AMSL"
        )
    if not isinstance(value, (int, float)):
        raise AirspaceError(f"{where}: {side}Limit {value!r} is not a number")
    return VerticalLimit(float(value), unit, ref)


def _rings(
    geometry: dict, ident: str, where: str
) -> tuple[list[list[tuple[float, float]]], list[list[tuple[float, float]]]]:
    gtype = geometry.get("type")
    if gtype != "Polygon":
        raise AirspaceError(
            f"{where} ({ident}): geometry type {gtype!r} is not supported"
        )
    polygons: list[list[tuple[float, float]]] = []
    holes: list[list[tuple[float, float]]] = []
    for ring_index, ring in enumerate(geometry.get("coordinates") or []):
        try:
            parsed = [(float(x), float(y)) for x, y in ring]
        except (TypeError, ValueError) as exc:
            raise AirspaceError(
                f"{where} ({ident}): malformed ring coordinates"
            ) from exc
        # GeoJSON ring order: 0 is the exterior, the rest are holes —
        # kept apart so the evaluator subtracts them (#422).
        (polygons if ring_index == 0 else holes).append(parsed)
    return polygons, holes


def parse_eans(raw: bytes, source: SourceInfo) -> list[Zone]:
    """Every zone of the EANS uas.geojson as normalized :class:`Zone`s."""
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except ValueError as exc:
        raise AirspaceError(f"{source.feed}: feed is not JSON ({exc})") from exc
    features = data.get("features") if isinstance(data, dict) else None
    if not isinstance(features, list):
        raise AirspaceError(
            f"{source.feed}: not a GeoJSON document (no 'features' list)"
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
        if not isinstance(ident, str) or not ident:
            raise AirspaceError(f"{where}: missing identifier")
        if props.get("hidden") or ident in _MASK_IDENTIFIERS:
            continue  # publisher viewer masks, by contract (see module doc)
        restriction = props.get("restriction")
        if not isinstance(restriction, str) or not restriction:
            raise AirspaceError(f"{where} ({ident}): missing restriction")
        name = (
            str(props.get("name") or "").strip()
            or str(props.get("airspaceclass") or "").strip()
            or ident
        )
        volume = props.get("geometry")
        lower = upper = None
        if volume is not None:
            if not isinstance(volume, dict):
                raise AirspaceError(
                    f"{where} ({ident}): properties.geometry is not an object"
                )
            unit = (
                "ft"
                if str(volume.get("uomDimensions", "M")).upper() == "FT"
                else "m"
            )
            lower = _limit(volume, "lower", unit, f"{where} ({ident})")
            upper = _limit(volume, "upper", unit, f"{where} ({ident})")
        applicability: list[Applicability] = []
        always_applicable = False
        windows = props.get("applicability")
        if windows is not None:
            if not isinstance(windows, list):
                raise AirspaceError(
                    f"{where} ({ident}): applicability is not a list"
                )
            for win in windows:
                if str(win.get("permanent", "")).upper() == "YES":
                    always_applicable = True
                    continue
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
        if always_applicable:
            applicability = []
        geometry = feat.get("geometry")
        if not isinstance(geometry, dict):
            raise AirspaceError(f"{where} ({ident}): missing geometry")
        polygons, holes = _rings(geometry, ident, where)
        if not polygons:
            raise AirspaceError(f"{where} ({ident}): no polygon geometry")
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
                native=feat,
            )
        )
    return zones
