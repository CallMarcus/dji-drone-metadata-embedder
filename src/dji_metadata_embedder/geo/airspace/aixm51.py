"""AIXM 5.1 UAS-restriction parser (#499): the UK NATS AIS dataset.

The authoritative product is an AIXM 5.1 BasicMessage: one
``aixm:Airspace`` per zone (single time slice, single volume), geometry
as GML curve segments — geodesic/line point runs, arcs and circles by
centre point, plus xlink references to in-document ``aixm:GeoBorder``
curves for coast/river-following boundaries. A GeoBorder curve is the
full coastline polyline; a ring's reference to it is trimmed to the
sub-path between its neighbouring segments' endpoints, not spliced
whole. Arcs and circles are
densified here, deliberately: the sibling KML product ships pre-densified
with visual gaps between abutting volumes, the exact flaw a consistent
in-house densification avoids.

Arc sweep direction is untrustworthy in the wild (the 20260806 cycle
mixes clockwise and anticlockwise arcs), so each arc defaults to its
shorter sweep and the assembled ring is checked for self-intersection;
on failure every direction combination is tried until a simple ring
emerges (probe 2026-08-15: 543 of 548 arc-bearing zones take the shorter
sweep, 5 need the search, none unsolved).

Vertical limits arrive in feet and flight levels against SFC/MSL/STD
datums. An upper limit of FL 999 is the UK "unlimited" convention — a
sentinel mapped to "not stated", never rendered as a number (the Swiss
99999 lesson). Activation blocks (NOTAM-activated danger areas, prose
schedules) ride in ``native`` but never become applicability windows:
the evaluator treats a window's presence as machine-evaluable
time-bounding, and these are not.

Rights (issue #499): the dataset's own ISO 19115 metadata states
"Unrestricted" access and usage (not for resale; for aviation use only),
which governs over the site's copyright boilerplate.
"""

from __future__ import annotations

import hashlib
import io
import itertools
import math
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urljoin
from xml.etree import ElementTree

from .model import AirspaceError, SourceInfo, VerticalLimit, Zone

_AIXM = "{http://www.aixm.aero/schema/5.1}"
_GML = "{http://www.opengis.net/gml/3.2}"
_XLINK = "{http://www.w3.org/1999/xlink}"
_XSI = "{http://www.w3.org/2001/XMLSchema-instance}"


@dataclass(frozen=True)
class Aixm51Feed:
    code: str
    page_url: str
    feed_name: str
    license: str
    caveat: str
    note: str | None = None


_CAVEAT = (
    "UAS flight-restriction data is informational and is not an "
    "authorization to fly."
)

AIXM_FEEDS: dict[str, Aixm51Feed] = {
    "GB": Aixm51Feed(
        code="GB",
        page_url=(
            "https://nats-uk.ead-it.com/cms-nats/opencms/en/Publications/"
            "digital-datasets/"
        ),
        feed_name="UK UAS flight restrictions (AIXM 5.1, NATS AIS)",
        license=(
            "© NATS Limited — UK UAS Flight Restrictions dataset; usage "
            "unrestricted per the product's ISO 19115 metadata (not for "
            "resale; for aviation use only)"
        ),
        caveat=_CAVEAT,
        note=(
            "Activation status and schedule text are shown as published "
            "and are not evaluated here (many danger areas are part-time; "
            "the AIP and NOTAM service hold the authoritative hours). "
            "Temporary restrictions live in NOTAMs and AIP Supplements, "
            "not in this record."
        ),
    ),
}

# The page lists the current AND next AIRAC cycle as dated zips; only
# the XML product is authoritative (the KML sibling is visualisation).
_ZIP_HREF_RE = re.compile(
    r'href="([^"]*UAS_AREA_1/EG_UAS_FR_DS_AREA1_FULL_(\d{8})_XML\.zip)"',
    re.IGNORECASE,
)


def discover_feed_url(page: bytes, page_url: str, *, today: date) -> str:
    """The currently-effective dataset zip URL from the datasets page.

    A cycle takes effect at 00:00 UTC on its filename date, so the
    newest listed date that is not in the future wins; a page listing
    only future cycles falls back to the oldest one."""
    dated: list[tuple[date, str]] = []
    for href, ymd in _ZIP_HREF_RE.findall(
        page.decode("utf-8", errors="replace")
    ):
        try:
            effective = datetime.strptime(ymd, "%Y%m%d").date()
        except ValueError:
            continue
        dated.append((effective, href.replace("&amp;", "&")))
    if not dated:
        raise AirspaceError(
            "could not find the UAS flight-restrictions dataset on the "
            f"NATS page ({page_url}) — the page layout may have changed"
        )
    current = [(d, h) for d, h in dated if d <= today]
    _, href = max(current) if current else min(dated)
    return urljoin(page_url, href)


_XML_MEMBER_RE = re.compile(r"EG_UAS_FR_DS_AREA1_FULL_\d{8}\.xml$")


def extract_xml(zip_bytes: bytes) -> bytes:
    """The dataset XML out of the downloaded archive, verified against
    the archive's own SHA-256 sidecar."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise AirspaceError(f"dataset archive is not a zip ({exc})") from exc
    with archive:
        names = archive.namelist()
        xml_names = [n for n in names if _XML_MEMBER_RE.search(n)]
        if len(xml_names) != 1:
            raise AirspaceError(
                f"expected one dataset XML in the archive, found "
                f"{len(xml_names)}"
            )
        body = archive.read(xml_names[0])
        sha_names = [n for n in names if n.endswith(".sha256")]
        if len(sha_names) != 1:
            raise AirspaceError(
                "expected one SHA-256 sidecar in the dataset archive, "
                f"found {len(sha_names)}"
            )
        sidecar = archive.read(sha_names[0]).decode("ascii", "replace")
        expected = sidecar.split()[0].lower() if sidecar.split() else ""
    if hashlib.sha256(body).hexdigest() != expected:
        raise AirspaceError(
            "dataset XML failed the archive's own SHA-256 integrity check"
        )
    return body


# --- geometry -------------------------------------------------------------

# WGS84
_A = 6378137.0
_F = 1 / 298.257223563
_E2 = _F * (2 - _F)

# Radius unit spellings are UCUM (probe-verified: [nmi_i], m, [ft_i]).
_RADIUS_M = {"[nmi_i]": 1852.0, "m": 1.0, "[ft_i]": 0.3048}

# Points per full circle: chord sagitta ~1 m at the 2-2.5 NM norm and
# ~14 m at the file's single 27 NM outlier — under the dataset's own
# stated 30 m horizontal accuracy.
_CIRCLE_POINTS = 128

# Junction tolerance between consecutive ring segments: the live file's
# arc endpoints sit up to ~77 m from the neighbouring published vertices
# (data imprecision); a gap beyond this is a broken ring.
_JUNCTION_M = 160.0

# Implied GML Ring closure is honest only at coastline resolution: the
# live file's largest real closure remainder (EGD012's coast-to-corner
# gap) is ~967 m. Beyond this cap a "closure" is a truncated ring, and
# rendering it silently would bridge the tear — gap instead.
_CLOSURE_M = 5000.0

# Bounds the simple-ring search over arc directions (2^8 assemblies);
# the live file's worst zone has 5 arcs.
_MAX_ARC_SEARCH = 8

LatLon = tuple[float, float]


def _gaussian_radius_m(lat_deg: float) -> float:
    """Radius of the sphere that locally best fits the ellipsoid, keeping
    densification error ~0.05% of the arc radius."""
    s = math.sin(math.radians(lat_deg))
    d = 1 - _E2 * s * s
    meridional = _A * (1 - _E2) / d**1.5
    normal = _A / math.sqrt(d)
    return math.sqrt(meridional * normal)


def _destination(origin: LatLon, bearing_deg: float, dist_m: float) -> LatLon:
    lat1 = math.radians(origin[0])
    lon1 = math.radians(origin[1])
    d = dist_m / _gaussian_radius_m(origin[0])
    br = math.radians(bearing_deg)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(d)
        + math.cos(lat1) * math.sin(d) * math.cos(br)
    )
    lon2 = lon1 + math.atan2(
        math.sin(br) * math.sin(d) * math.cos(lat1),
        math.cos(d) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), math.degrees(lon2)


def _dist_m(p: LatLon, q: LatLon) -> float:
    return math.hypot(
        (p[0] - q[0]) * 111_320,
        (p[1] - q[1]) * 111_320 * math.cos(math.radians(p[0])),
    )


def _pos(el: ElementTree.Element, where: str) -> LatLon:
    parts = (el.text or "").split()
    if len(parts) != 2:
        raise AirspaceError(f"{where}: malformed gml:pos {el.text!r}")
    try:
        lat, lon = (float(p) for p in parts)
    except ValueError as exc:
        raise AirspaceError(
            f"{where}: malformed gml:pos {el.text!r}"
        ) from exc
    return lat, lon  # EPSG::4326 URN axis order: latitude first


def _point_run(seg: ElementTree.Element, where: str) -> list[LatLon]:
    return [_pos(p, where) for p in seg.iter(f"{_GML}pos")]


def _centre_radius(
    seg: ElementTree.Element, where: str
) -> tuple[LatLon, float]:
    pos = seg.find(f"{_GML}pointProperty/{_AIXM}Point/{_GML}pos")
    if pos is None:
        raise AirspaceError(f"{where}: arc/circle has no centre point")
    radius = seg.find(f"{_GML}radius")
    uom = radius.get("uom") if radius is not None else None
    if radius is None or uom not in _RADIUS_M:
        raise AirspaceError(f"{where}: unsupported radius unit {uom!r}")
    try:
        r = float(radius.text or "") * _RADIUS_M[uom]
    except ValueError as exc:
        raise AirspaceError(f"{where}: malformed radius") from exc
    return _pos(pos, where), r


def _angle(seg: ElementTree.Element, name: str, where: str) -> float:
    el = seg.find(f"{_GML}{name}")
    if el is None:
        raise AirspaceError(f"{where}: arc has no {name}")
    try:
        return float(el.text or "")
    except ValueError as exc:
        raise AirspaceError(f"{where}: malformed {name}") from exc


def _circle(seg: ElementTree.Element, where: str) -> list[LatLon]:
    centre, r = _centre_radius(seg, where)
    step = 360.0 / _CIRCLE_POINTS
    return [
        _destination(centre, k * step, r)
        for k in range(_CIRCLE_POINTS + 1)
    ]


def _arc(
    seg: ElementTree.Element, clockwise: bool, where: str
) -> list[LatLon]:
    centre, r = _centre_radius(seg, where)
    start = _angle(seg, "startAngle", where)
    end = _angle(seg, "endAngle", where)
    sweep = (end - start) % 360 if clockwise else (start - end) % 360
    n = max(2, math.ceil(_CIRCLE_POINTS * sweep / 360))
    step = sweep / n if clockwise else -sweep / n
    return [_destination(centre, start + k * step, r) for k in range(n + 1)]


# A ring is a sequence of pieces: fixed point runs (geodesic/line
# strings, circles, GeoBorder splices) and arcs whose sweep direction is
# chosen at assembly time.
_Piece = tuple[str, object]


def _ring_pieces(
    ring: ElementTree.Element, borders: dict[str, list[LatLon]], where: str
) -> list[_Piece]:
    pieces: list[_Piece] = []
    members = ring.findall(f"{_GML}curveMember")
    if not members:
        raise AirspaceError(f"{where}: ring has no curve members")
    for member in members:
        href = member.get(f"{_XLINK}href")
        if href is not None:
            uuid = href.removeprefix("urn:uuid:")
            if uuid not in borders:
                raise AirspaceError(
                    f"{where}: unresolvable GeoBorder reference {href}"
                )
            pieces.append(("border", borders[uuid]))
            continue
        segments = member.find(f"{_GML}Curve/{_GML}segments")
        if segments is None:
            raise AirspaceError(f"{where}: curve member has no segments")
        for seg in segments:
            if seg.tag in (
                f"{_GML}GeodesicString", f"{_GML}LineStringSegment"
            ):
                points = _point_run(seg, where)
                if len(set(points)) <= 1:
                    # A zero-length "closing" segment: some real zones
                    # (e.g. EGD012) end their ring with a curve whose
                    # points all repeat the ring's own start coordinate
                    # instead of an actual closing edge. It contributes
                    # no geometry, so it is dropped rather than forced
                    # through the junction check — the ring's own
                    # closure step (which never errors) finishes it off.
                    continue
                pieces.append(("fixed", points))
            elif seg.tag == f"{_GML}CircleByCenterPoint":
                pieces.append(("fixed", _circle(seg, where)))
            elif seg.tag == f"{_GML}ArcByCenterPoint":
                pieces.append(("arc", seg))
            else:
                raise AirspaceError(
                    f"{where}: unsupported curve segment "
                    f"{seg.tag.rpartition('}')[2]}"
                )
    return pieces


def _leading_point(piece: _Piece, where: str) -> LatLon:
    kind, payload = piece
    if kind == "arc":
        assert isinstance(payload, ElementTree.Element)
        centre, r = _centre_radius(payload, where)
        # An arc's start point is the same for both sweep directions.
        return _destination(centre, _angle(payload, "startAngle", where), r)
    assert isinstance(payload, list)
    return payload[0]


def _trailing_point(piece: _Piece, where: str) -> LatLon:
    kind, payload = piece
    if kind == "arc":
        assert isinstance(payload, ElementTree.Element)
        centre, r = _centre_radius(payload, where)
        # An arc's end point is the same for both sweep directions.
        return _destination(centre, _angle(payload, "endAngle", where), r)
    assert isinstance(payload, list)
    return payload[-1]


def _assemble(
    pieces: list[_Piece], arc_dirs: list[bool], where: str
) -> list[LatLon]:
    pts: list[LatLon] = []
    arc_i = 0
    for i, (kind, payload) in enumerate(pieces):
        if kind == "arc":
            assert isinstance(payload, ElementTree.Element)
            run = _arc(payload, arc_dirs[arc_i], where)
            arc_i += 1
        elif kind == "border":
            assert isinstance(payload, list)
            border = payload
            if len(pieces) == 1:
                # A border-only ring: keep the whole polyline as-is.
                run = list(border)
            else:
                # A GeoBorder curve is the full coastline/river polyline;
                # a ring only follows the stretch BETWEEN its neighbouring
                # segments' endpoints, not the whole thing.
                prev_pt = _trailing_point(
                    pieces[(i - 1) % len(pieces)], where
                )
                next_pt = _leading_point(
                    pieces[(i + 1) % len(pieces)], where
                )
                start_idx = min(
                    range(len(border)),
                    key=lambda j: _dist_m(border[j], prev_pt),
                )
                end_idx = min(
                    range(len(border)),
                    key=lambda j: _dist_m(border[j], next_pt),
                )
                if start_idx <= end_idx:
                    run = list(border[start_idx : end_idx + 1])
                else:
                    run = list(reversed(border[end_idx : start_idx + 1]))
        else:
            assert isinstance(payload, list)
            run = list(payload)
        if pts:
            gap = _dist_m(pts[-1], run[0])
            if gap > _JUNCTION_M:
                raise AirspaceError(
                    f"{where}: ring is discontinuous ({gap:.0f} m gap)"
                )
            run = run[1:]  # snap the junction
        pts.extend(run)
    if len(pts) < 3:
        raise AirspaceError(f"{where}: ring has too few points")
    gap = _dist_m(pts[0], pts[-1])
    if gap <= _JUNCTION_M:
        pts[-1] = pts[0]
    elif gap <= _CLOSURE_M:
        pts.append(pts[0])  # GML Ring closure may be implied
    else:
        raise AirspaceError(
            f"{where}: ring closure gap is {gap:.0f} m — the ring looks "
            "truncated"
        )
    return pts


def _crosses(p1: LatLon, p2: LatLon, p3: LatLon, p4: LatLon) -> bool:
    def ccw(a: LatLon, b: LatLon, c: LatLon) -> bool:
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(
        p1, p2, p4
    )


def _self_intersects(ring: list[LatLon]) -> bool:
    n = len(ring)
    for i in range(n - 1):
        for j in range(i + 2, n - 1):
            if i == 0 and j == n - 2:
                continue
            if _crosses(ring[i], ring[i + 1], ring[j], ring[j + 1]):
                return True
    return False


def _ring_points(
    ring: ElementTree.Element, borders: dict[str, list[LatLon]], where: str
) -> list[LatLon]:
    pieces = _ring_pieces(ring, borders, where)
    arc_segs = [seg for kind, seg in pieces if kind == "arc"]
    # Per-arc default: the shorter way round. Continuity cannot pick the
    # direction (both sweeps share endpoints) and no uniform convention
    # fits the live file, but the shorter sweep + a simplicity check
    # covers it: 543/548 arc-bearing zones directly, 5 via the search.
    dirs: list[bool] = []
    for seg in arc_segs:
        assert isinstance(seg, ElementTree.Element)
        start = _angle(seg, "startAngle", where)
        end = _angle(seg, "endAngle", where)
        dirs.append((end - start) % 360 <= 180)
    pts = _assemble(pieces, dirs, where)
    if not arc_segs or not _self_intersects(pts):
        return pts
    if len(arc_segs) > _MAX_ARC_SEARCH:
        raise AirspaceError(f"{where}: too many arcs to disambiguate")
    for combo in itertools.product((True, False), repeat=len(arc_segs)):
        pts = _assemble(pieces, list(combo), where)
        if not _self_intersects(pts):
            return pts
    raise AirspaceError(
        f"{where}: no arc interpretation yields a simple ring"
    )


# --- zones ----------------------------------------------------------------

_TYPES = {"P": "PROHIBITED", "R": "RESTRICTED", "D": "DANGER"}
_LIMIT_REFS = {"SFC": "AGL", "MSL": "AMSL", "STD": "STD"}
_LIMIT_UNITS = {"FT": "ft", "M": "m", "FL": "FL"}


def _limit(
    vol: ElementTree.Element, side: str, where: str
) -> VerticalLimit | None:
    el = vol.find(f"{_AIXM}{side}Limit")
    if (
        el is None
        or el.get(f"{_XSI}nil") == "true"
        or not (el.text or "").strip()
    ):
        return None  # "not stated" — never 0
    uom = (el.get("uom") or "").upper()
    if uom not in _LIMIT_UNITS:
        raise AirspaceError(
            f"{where}: unsupported {side} limit unit {uom!r}"
        )
    ref_el = vol.find(f"{_AIXM}{side}LimitReference")
    ref_raw = (ref_el.text or "").strip() if ref_el is not None else ""
    if ref_raw not in _LIMIT_REFS:
        raise AirspaceError(
            f"{where}: {side} limit reference {ref_raw!r} is not "
            "SFC/MSL/STD"
        )
    if (uom == "FL") != (ref_raw == "STD"):
        raise AirspaceError(f"{where}: {side} limit pairs {uom} with {ref_raw}")
    try:
        value = float(el.text or "")
    except ValueError as exc:
        raise AirspaceError(f"{where}: malformed {side} limit") from exc
    return VerticalLimit(value, _LIMIT_UNITS[uom], _LIMIT_REFS[ref_raw])


# AIXM 5.1 CodeStatusAirspaceType values seen or expected in the UK
# product, in plain words; anything else passes through as published.
_ACTIVATION_STATUS = {
    "ACTIVE": "active",
    "AVBL_FOR_ACTIVATION": "available for activation",
    "INACTIVE": "inactive",
    "INTERMITTENT": "intermittent",
    "IN_USE": "in use",
}


def _activation_lines(activations: list[dict]) -> list[str]:
    """Reader-facing lines for the activation blocks (#503): the status
    code in plain words, then the published notes joined — exactly what
    the dataset says, never an evaluation."""
    lines = []
    for act in activations:
        status = act.get("status")
        words = _ACTIVATION_STATUS.get(status, status) if status else None
        notes = "; ".join(act.get("notes") or [])
        if words and notes:
            lines.append(f"{words} — {notes}")
        elif words or notes:
            lines.append(words or notes)
    return lines


def _native(
    ts: ElementTree.Element, type_code: str, local_type: str
) -> dict:
    activations = []
    for act in ts.findall(f"{_AIXM}activation/{_AIXM}AirspaceActivation"):
        notes = [
            (n.text or "").strip()
            for n in act.iter(f"{_AIXM}note")
            if (n.text or "").strip()
        ]
        activations.append({
            "status": (act.findtext(f"{_AIXM}status") or "").strip() or None,
            "notes": notes,
        })
    return {
        "type": type_code,
        "localType": local_type or None,
        "activation": activations,
    }


def parse_aixm51(raw: bytes, source: SourceInfo) -> list[Zone]:
    """Every airspace of an AIXM 5.1 message as normalized :class:`Zone`s."""
    # The scan below is byte-wise; a UTF-16/32 body would slip past it.
    # The dataset is UTF-8, so any BOM or NUL in the prologue is refused.
    if raw[:1] in (b"\xff", b"\xfe") or b"\x00" in raw[:4096]:
        raise AirspaceError(
            f"{source.feed}: refusing non-UTF-8 XML encoding"
        )
    # The dataset never declares a DTD; refusing them up front closes
    # the stdlib parser's entity-expansion/XXE surface without a
    # defusedxml dependency (whose core defence is exactly this).
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise AirspaceError(
            f"{source.feed}: document declares a DTD; refusing to parse"
        )
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise AirspaceError(
            f"{source.feed}: feed is not XML ({exc})"
        ) from exc
    borders: dict[str, list[LatLon]] = {}
    for gb in root.iter(f"{_AIXM}GeoBorder"):
        ident = (gb.findtext(f"{_GML}identifier") or "").strip()
        if not ident:
            raise AirspaceError(
                f"{source.feed}: GeoBorder without identifier"
            )
        borders[ident] = [
            _pos(p, f"{source.feed}: GeoBorder {ident}")
            for p in gb.iter(f"{_GML}pos")
        ]
    zones: list[Zone] = []
    for i, asp in enumerate(root.iter(f"{_AIXM}Airspace")):
        where = f"{source.feed}: zone {i}"
        slices = asp.findall(f"{_AIXM}timeSlice/{_AIXM}AirspaceTimeSlice")
        if len(slices) != 1:
            raise AirspaceError(
                f"{where}: expected one time slice, found {len(slices)}"
            )
        ts = slices[0]
        designator = (ts.findtext(f"{_AIXM}designator") or "").strip()
        if not designator:
            raise AirspaceError(f"{where}: missing designator")
        where = f"{where} ({designator})"
        type_code = (ts.findtext(f"{_AIXM}type") or "").strip()
        if type_code not in _TYPES:
            raise AirspaceError(
                f"{where}: airspace type {type_code!r} is not P/R/D"
            )
        name = (ts.findtext(f"{_AIXM}name") or "").strip() or designator
        local_type = (ts.findtext(f"{_AIXM}localType") or "").strip()
        if local_type in ("FRZ", "RPZ"):
            # The most drone-meaningful classification in the dataset.
            name = f"{name} ({local_type})"
        components = ts.findall(
            f"{_AIXM}geometryComponent/{_AIXM}AirspaceGeometryComponent"
        )
        if len(components) != 1:
            raise AirspaceError(
                f"{where}: expected one geometry component, found "
                f"{len(components)}"
            )
        vol = components[0].find(
            f"{_AIXM}theAirspaceVolume/{_AIXM}AirspaceVolume"
        )
        if vol is None:
            raise AirspaceError(f"{where}: missing airspace volume")
        lower = _limit(vol, "lower", where)
        upper = _limit(vol, "upper", where)
        if upper is not None and upper.unit == "FL" and upper.value >= 999:
            # FL 999 is the UK "unlimited" convention — a sentinel,
            # never a number to render (the Swiss 99999 lesson).
            upper = None
        patches = vol.findall(
            f"{_AIXM}horizontalProjection/{_AIXM}Surface/"
            f"{_GML}patches/{_GML}PolygonPatch"
        )
        if len(patches) != 1:
            raise AirspaceError(
                f"{where}: expected one polygon patch, found {len(patches)}"
            )
        exterior = patches[0].find(f"{_GML}exterior/{_GML}Ring")
        if exterior is None:
            raise AirspaceError(f"{where}: patch has no exterior ring")
        ring = _ring_points(exterior, borders, where)
        holes: list[list[tuple[float, float]]] = []
        for interior in patches[0].findall(f"{_GML}interior"):
            inner = interior.find(f"{_GML}Ring")
            if inner is not None:
                holes.append([
                    (lon, lat)
                    for lat, lon in _ring_points(inner, borders, where)
                ])
        native = _native(ts, type_code, local_type)
        zones.append(
            Zone(
                identifier=designator,
                name=name,
                restriction=_TYPES[type_code],
                lower=lower,
                upper=upper,
                applicability=[],
                polygons=[[(lon, lat) for lat, lon in ring]],
                holes=holes,
                source=source,
                native=native,
                activation=_activation_lines(native["activation"]),
            )
        )
    if not zones:
        raise AirspaceError(f"{source.feed}: no airspace features found")
    return zones
