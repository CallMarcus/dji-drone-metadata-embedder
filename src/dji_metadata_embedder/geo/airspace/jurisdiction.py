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
        (-124.6, 25.8, -95.0, 48.7),
        (-95.0, 25.8, -84.5, 46.5),
        (-84.5, 24.4, -74.0, 40.9),
        (-75.5, 40.0, -69.8, 43.5),
        (-165.0, 55.5, -141.5, 70.5),   # Alaska interior
        (-160.5, 18.5, -154.5, 22.5),   # Hawaii
    ],
    "LU": [(5.85, 49.55, 6.35, 50.05)],
    "FI": [
        (22.8, 59.8, 26.5, 64.5),
        (24.5, 64.5, 29.0, 66.8),
        (25.0, 66.8, 27.5, 68.3),
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
}
_MEASURE = {"US": MEASURE_US, "LU": MEASURE_EU, "FI": MEASURE_EU}


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
            "(v1 covers the US, Luxembourg and Finland)",
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
