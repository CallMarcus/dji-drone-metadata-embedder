"""Flight-relevant jurisdiction from the track's coordinates (#413).

Never a user setting: one flight, one jurisdiction, chosen from the data
(maintainer decision on #413). Conservative core/hull boxes per supported
jurisdiction: a track entirely inside a hull AND its core resolves; inside
a hull but outside the core sits too close to a land border to decide from
coordinates alone and gaps honestly; anywhere else is the no-provider gap.
The boxes are deliberately coarse v1 constants — the failure mode they
must exclude is borrowing another jurisdiction's framing, not coverage.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..track import Track

Box = tuple[float, float, float, float]  # lon_min, lat_min, lon_max, lat_max

MEASURE_US = (
    "Where this flight took place, 14 CFR 107.51(b) limits small-UAS "
    "altitude to 400 ft above ground level (AGL), with a structure "
    "exception that telemetry cannot evaluate. This record states "
    "measurements and their datums; it makes no determination."
)
MEASURE_EU = (
    "Where this flight took place, Regulation (EU) 2019/947 "
    "(UAS.OPEN.010(2)) requires staying within 120 m of the closest point "
    "of the surface of the earth, with obstacle exceptions that telemetry "
    "cannot evaluate. This record states measurements and their datums; "
    "it makes no determination."
)

_CORE: dict[str, list[Box]] = {
    "US": [
        (-124.6, 33.1, -95.0, 48.7),   # West + Plains, above the border's northernmost reach (Tijuana 32.7)
        (-111.2, 31.9, -108.3, 33.1),  # southern Arizona (Tucson); border is the 31.33N line here
        (-106.4, 31.9, -103.0, 33.1),  # southern New Mexico; border ~31.78N, El Paso itself gaps honestly
        (-103.0, 30.0, -100.0, 33.1),  # west Texas, north of the Big Bend river bend (~29.2N)
        (-100.0, 28.8, -97.4, 33.1),   # south-central Texas (San Antonio); Rio Grande well south
        (-97.4, 26.1, -95.0, 33.1),    # Texas Gulf coast (Houston, Corpus Christi); Matamoros is west of -97.4
        (-95.0, 25.8, -84.5, 46.5),    # central-east (unchanged; only Gulf water below Florida latitudes)
        (-84.5, 24.4, -79.8, 31.0),    # Florida; east bound keeps Bimini (-79.3) and Grand Bahama out
        (-84.5, 31.0, -74.0, 40.9),    # Southeast + mid-Atlantic
        (-75.5, 40.0, -69.8, 43.5),    # Northeast (unchanged)
        (-165.0, 55.5, -141.5, 70.5),  # Alaska interior (unchanged)
        (-160.5, 18.5, -154.5, 22.5),  # Hawaii (unchanged)
    ],
    "LU": [
        (5.9, 49.55, 6.3, 49.8),       # south (Luxembourg City, Findel); Moselle border ~6.36E
        (5.95, 49.8, 6.25, 49.88),     # centre; border ~6.28E at Wallendorf (49.877)
        # Bettendorf band; the Our bows west to ~6.226 near Roth/Gentingen
        # just above 49.9N; border verified in (6.230, 6.235) at 49.90, so
        # 6.2 keeps >=2 km margin on the whole edge.
        (5.95, 49.88, 6.2, 49.9),
        (5.95, 49.9, 6.1, 50.0),       # north; Our-river border ~6.13E (Vianden excluded), tip above 50.0 gaps
    ],
    "FI": [
        (22.8, 59.8, 26.5, 64.5),
        (24.5, 64.5, 29.0, 66.8),
        (25.0, 66.8, 27.5, 68.3),
    ],
    # Plateau-focused (#456): Geneva, Basel, Ticino, Valais and Grisons sit
    # against five neighbours and gap honestly as border bands. Every edge
    # and outside-margin point Nominatim-verified CH on 2026-08-05, >=5 km
    # of buffer to the nearest border throughout.
    "CH": [
        (7.05, 46.6, 7.9, 47.05),   # Bern / Fribourg / Thun / Interlaken
        (7.3, 47.0, 8.0, 47.3),     # Biel / Solothurn / Zofingen
        (8.0, 46.8, 8.9, 47.42),    # Lucerne / Zug / Zurich
    ],
}
_HULL: dict[str, list[Box]] = {
    "US": [
        (-125.5, 24.0, -66.5, 49.5),
        (-170.0, 51.0, -129.0, 71.8),
        (-161.0, 18.0, -154.0, 23.0),
    ],
    "LU": [(5.70, 49.44, 6.60, 50.20)],
    "FI": [(19.0, 59.5, 31.6, 70.1)],
    "CH": [(5.9, 45.8, 10.5, 47.85)],
}
# CH takes the EU measure: Regulation (EU) 2019/947 applies in Switzerland
# since 2023-01-01 under the CH-EU air transport agreement.
_MEASURE = {"US": MEASURE_US, "LU": MEASURE_EU, "FI": MEASURE_EU, "CH": MEASURE_EU}


@dataclass(frozen=True)
class Jurisdiction:
    code: str
    measure_note: str


@dataclass(frozen=True)
class Resolution:
    jurisdiction: Jurisdiction | None
    gap_reason: str | None


def _all_inside(track: Track, boxes: list[Box]) -> bool:
    return all(
        any(x1 <= p.lon <= x2 and y1 <= p.lat <= y2 for x1, y1, x2, y2 in boxes)
        for p in track.points
    )


def resolve_jurisdiction(track: Track) -> Resolution:
    if not track.points:
        return Resolution(None, "the track has no GPS points")
    hulls = [code for code, boxes in _HULL.items() if _all_inside(track, boxes)]
    if len(hulls) != 1:
        return Resolution(
            None,
            "no supported airspace data source for this location "
            "(covered: the US, Luxembourg, Finland and Switzerland)",
        )
    code = hulls[0]
    if not _all_inside(track, _CORE[code]):
        return Resolution(
            None,
            "the flight sits too close to a jurisdiction boundary to "
            "choose an airspace source from coordinates alone; airspace "
            "lookup skipped",
        )
    return Resolution(Jurisdiction(code, _MEASURE[code]), None)
