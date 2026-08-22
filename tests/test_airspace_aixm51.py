"""AIXM 5.1 provider tests (#499): UK NATS AIS UAS flight restrictions.

The authoritative product is an AIXM 5.1 BasicMessage inside a zip with
its own SHA-256 sidecar, published per AIRAC cycle with dated filenames;
the current AND next cycle are both listed, so discovery is date-aware.
"""
import hashlib
import io
import math
import re
import zipfile
from datetime import date
from pathlib import Path

import pytest

from dji_metadata_embedder.geo.airspace import AirspaceError, SourceInfo
from dji_metadata_embedder.geo.airspace.aixm51 import (
    AIXM_FEEDS,
    discover_feed_url,
    extract_xml,
    parse_aixm51,
)

FIXTURES = Path(__file__).parent.parent / "samples" / "airspace"
SRC = SourceInfo(
    feed="test", url="https://example.invalid/datasets",
    fetched="2026-08-15T12:00:00Z",
    license="test", caveat="informational only",
)

PAGE = (
    b'<a href="/x/UAS_AREA_1/EG_UAS_FR_DS_AREA1_FULL_20260806_KML.zip">k</a>'
    b'<a href="/x/UAS_AREA_1/EG_UAS_FR_DS_AREA1_FULL_20260806_XML.zip">x</a>'
    b'<a href="/x/UAS_AREA_1/EG_UAS_FR_DS_AREA1_FULL_20260903_KML.zip">k</a>'
    b'<a href="/x/UAS_AREA_1/EG_UAS_FR_DS_AREA1_FULL_20260903_XML.zip">x</a>'
)
BASE = "https://nats-uk.ead-it.com/cms-nats/opencms/en/Publications/digital-datasets/"


def test_discovery_picks_the_effective_cycle_not_the_next_one():
    # Both the current and the NEXT AIRAC cycle are on the page; a cycle
    # takes effect at 00:00 UTC on its filename date.
    url, effective = discover_feed_url(PAGE, BASE, today=date(2026, 8, 15))
    assert url.endswith("EG_UAS_FR_DS_AREA1_FULL_20260806_XML.zip")
    assert url.startswith("https://nats-uk.ead-it.com/x/")
    # #502: the cycle's effective date travels with the URL so the record
    # can state which cycle the zones reflect, not just when we fetched.
    assert effective == "2026-08-06"


def test_discovery_rolls_over_on_the_cycle_date():
    url, effective = discover_feed_url(PAGE, BASE, today=date(2026, 9, 3))
    assert "20260903_XML" in url and effective == "2026-09-03"


def test_discovery_falls_back_to_the_oldest_when_all_dates_are_future():
    url, effective = discover_feed_url(PAGE, BASE, today=date(2026, 8, 1))
    assert "20260806_XML" in url and effective == "2026-08-06"


def test_discovery_never_picks_the_kml_product():
    kml_only = PAGE.replace(b"_XML.zip", b"_XKL.zip")
    with pytest.raises(AirspaceError, match="NATS"):
        discover_feed_url(kml_only, BASE, today=date(2026, 8, 15))


def _zip(xml: bytes, *, sha: str | None = None,
         xml_name: str = "EG_UAS_FR_DS_AREA1_FULL_20260806.xml") -> bytes:
    digest = sha if sha is not None else hashlib.sha256(xml).hexdigest()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(xml_name, xml)
        zf.writestr(
            "EG_UAS_FR_DS_AREA1_FULL_20260806.sha256",
            f"{digest} *{xml_name}",
        )
    return buf.getvalue()


def test_extract_verifies_the_archives_own_sha256():
    assert extract_xml(_zip(b"<xml/>")) == b"<xml/>"


def test_a_sha_mismatch_is_an_error_not_a_silent_accept():
    with pytest.raises(AirspaceError, match="SHA-256"):
        extract_xml(_zip(b"<xml/>", sha="0" * 64))


def test_an_archive_without_the_dataset_xml_is_an_error():
    with pytest.raises(AirspaceError, match="dataset XML"):
        extract_xml(_zip(b"<xml/>", xml_name="export-filter.xml"))


def test_a_non_zip_body_is_an_error():
    with pytest.raises(AirspaceError, match="zip"):
        extract_xml(b"<html>login wall</html>")


def test_gb_feed_registry_states_source_rights_and_honesty_note():
    feed = AIXM_FEEDS["GB"]
    assert feed.page_url.startswith("https://nats-uk.ead-it.com/")
    assert "NATS" in feed.license and "ISO 19115" in feed.license
    assert "not for resale" in feed.license
    note = feed.note or ""
    assert "Activation hours" in note and "Temporary restrictions" in note


def _gb() -> bytes:
    return (FIXTURES / "aixm51-gb.xml").read_bytes()


def _dist_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    # (lon, lat) points, small separations
    return math.hypot(
        (a[1] - b[1]) * 111_320,
        (a[0] - b[0]) * 111_320 * math.cos(math.radians(a[1])),
    )


def test_parses_the_fixture_and_maps_uk_type_codes():
    zones = parse_aixm51(_gb(), SRC)
    assert [z.identifier for z in zones] == [
        "EGTEST1", "EGD901", "EGP901", "EGD902", "EGD903", "EGD904",
    ]
    assert [z.restriction for z in zones] == [
        "RESTRICTED", "DANGER", "PROHIBITED", "DANGER", "DANGER", "DANGER",
    ]
    # FRZ/RPZ is the most drone-meaningful bit of the dataset — it rides
    # in the display name; zones without a localType stay untouched.
    assert zones[0].name == "TESTFIELD RWY 09 (RPZ)"
    assert zones[1].name == "TEST DANGER"


def test_vertical_limits_map_sfc_msl_std_and_units():
    zones = parse_aixm51(_gb(), SRC)
    rpz = zones[0]
    assert rpz.lower is not None and rpz.lower.label() == "0 ft AGL"
    assert rpz.upper is not None and rpz.upper.label() == "2000 ft AGL"
    prohib = zones[2]
    assert prohib.upper is not None and prohib.upper.label() == "2000 ft AMSL"
    rev = zones[4]
    assert rev.upper is not None and rev.upper.label() == "FL 100"


def test_fl999_upper_is_the_unlimited_sentinel_never_a_number():
    danger = parse_aixm51(_gb(), SRC)[1]
    assert danger.upper is None                # renders "not stated"
    assert danger.lower is not None and danger.lower.label() == "FL 50"


def test_activation_rides_in_native_and_never_becomes_applicability():
    # An Applicability entry's presence means machine-evaluable
    # time-bounding to the evaluator; NOTAM activation prose is not that.
    zones = parse_aixm51(_gb(), SRC)
    assert all(z.applicability == [] for z in zones)
    act = zones[0].native["activation"]
    assert act == [{"status": "AVBL_FOR_ACTIVATION",
                    "notes": ["Mon-Sat SR to SS."]}]
    assert zones[0].native["type"] == "R"
    assert zones[0].native["localType"] == "RPZ"


def test_coordinates_come_out_lon_lat_and_rings_close():
    zones = parse_aixm51(_gb(), SRC)
    square = zones[2].polygons[0]
    assert square[0] == (-0.5, 51.5)            # file says "51.5 -0.5"
    assert square[0] == square[-1]
    for z in zones:
        assert z.polygons[0][0] == z.polygons[0][-1]
        assert not z.holes


def test_circles_and_arcs_densify_at_the_published_radius():
    zones = parse_aixm51(_gb(), SRC)
    circle = zones[1].polygons[0]
    assert len(circle) == 129                    # 128 points + closure
    centre = (-1.5, 51.2)
    for p in circle:
        assert abs(_dist_m(p, centre) - 2 * 1852) < 5
    arc_ring = zones[0].polygons[0]
    assert len(arc_ring) > 30                    # ~32 arc points + corners
    arc_centre = (-1.0, 51.0)
    on_arc = [p for p in arc_ring if abs(_dist_m(p, arc_centre) - 1852) < 5]
    assert len(on_arc) >= 30


def test_a_border_reference_is_spliced_forward_and_reversed():
    zones = parse_aixm51(_gb(), SRC)
    mid = (0.005, 52.01)                         # the coast's middle vertex
    # The GeoBorder polyline has a fourth tail vertex past the ring's far
    # neighbouring endpoint; a ring must trim to its own stretch, not
    # splice the whole coastline.
    tail = (-0.01, 52.03)
    for z in (zones[3], zones[4]):
        assert any(_dist_m(p, mid) < 1 for p in z.polygons[0])
        assert z.polygons[0][0] == z.polygons[0][-1]
        assert all(_dist_m(p, tail) > 500 for p in z.polygons[0])


def _mutated(old: str, new: str) -> bytes:
    text = _gb().decode("utf-8")
    assert old in text, f"fixture no longer contains {old!r}"
    return text.replace(old, new).encode("utf-8")


def test_an_unknown_airspace_type_invalidates_the_document():
    with pytest.raises(AirspaceError, match="EGD901.*not P/R/D"):
        parse_aixm51(_mutated(">D</aixm:type>", ">Q</aixm:type>"), SRC)


def test_an_unknown_radius_unit_raises():
    with pytest.raises(AirspaceError, match="radius unit"):
        parse_aixm51(_mutated('uom="[nmi_i]">2<', 'uom="KM">2<'), SRC)


def test_an_unknown_vertical_reference_raises():
    with pytest.raises(AirspaceError, match="SFC/MSL/STD"):
        parse_aixm51(
            _mutated(">MSL</aixm:upperLimitReference>",
                     ">W84</aixm:upperLimitReference>"),
            SRC,
        )


def test_fl_without_std_raises():
    with pytest.raises(AirspaceError, match="pairs"):
        parse_aixm51(
            _mutated('<aixm:lowerLimit uom="FL">50</aixm:lowerLimit>',
                     '<aixm:lowerLimit uom="FT">50</aixm:lowerLimit>'),
            SRC,
        )


def test_an_unresolvable_border_reference_raises():
    with pytest.raises(AirspaceError, match="GeoBorder"):
        parse_aixm51(
            _mutated('href="urn:uuid:99999999-9999-9999-9999-999999999999"',
                     'href="urn:uuid:00000000-0000-0000-0000-000000000000"'),
            SRC,
        )


def test_a_discontinuous_ring_raises():
    # Move the straight segment's start ~3 km off the arc's end: junction
    # tolerance is 160 m.
    with pytest.raises(AirspaceError, match="EGTEST1"):
        parse_aixm51(
            _mutated("50.9999970 -0.9735822", "50.9700000 -0.9735822"), SRC
        )


def test_an_unsupported_segment_type_raises():
    broken = _mutated(
        "<gml:LineStringSegment>", "<gml:CubicSpline>"
    ).replace(b"</gml:LineStringSegment>", b"</gml:CubicSpline>")
    with pytest.raises(AirspaceError, match="CubicSpline"):
        parse_aixm51(broken, SRC)


def test_a_document_without_airspaces_raises():
    empty = (
        b'<?xml version="1.0"?><message:AIXMBasicMessage '
        b'xmlns:message="http://www.aixm.aero/schema/5.1/message"/>'
    )
    with pytest.raises(AirspaceError, match="no airspace"):
        parse_aixm51(empty, SRC)


def test_non_xml_raises():
    with pytest.raises(AirspaceError, match="not XML"):
        parse_aixm51(b"{}", SRC)


def test_a_dtd_is_refused_before_parsing():
    # The dataset never declares one; refusing DTDs up front closes the
    # stdlib parser's entity-expansion surface (defusedxml's own core
    # defence, without the dependency).
    evil = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "b">]><r/>'
    with pytest.raises(AirspaceError, match="DTD"):
        parse_aixm51(evil, SRC)


def test_the_direction_search_flips_a_wrong_shorter_sweep():
    # EGD904's arc must bulge south (the longer sweep); the shorter
    # sweep would rise through the zone's shallow top edge and
    # self-intersect, so the search has to flip it.
    zones = parse_aixm51(_gb(), SRC)
    flip = next(z for z in zones if z.identifier == "EGD904")
    ring = flip.polygons[0]
    assert any(lat < 52.99 for _, lat in ring)      # southern bulge chosen
    assert all(lat < 53.0145 for _, lat in ring)    # never above the top edge


def test_multiple_time_slices_invalidate_the_document():
    text = _gb().decode("utf-8")
    a2_match = re.search(
        r'<aixm:Airspace gml:id="a2">.*?</aixm:Airspace>', text, re.S
    )
    assert a2_match is not None
    a2 = a2_match.group(0)
    ts_match = re.search(r"<aixm:timeSlice>.*?</aixm:timeSlice>", a2, re.S)
    assert ts_match is not None
    ts = ts_match.group(0)
    broken = text.replace(a2, a2.replace(ts, ts + ts))
    with pytest.raises(AirspaceError, match="one time slice"):
        parse_aixm51(broken.encode("utf-8"), SRC)


def test_a_modest_closure_gap_is_an_implied_closure_not_an_error():
    # Drop zone a3's explicit closing vertex: the ~2.2 km remainder is
    # within the closure cap, so the ring closes by appending the start.
    no_close = _mutated(
        '<gml:pointProperty><aixm:Point gml:id="a3p5">'
        '<gml:pos>51.5 -0.5</gml:pos></aixm:Point></gml:pointProperty>',
        "",
    )
    zone = parse_aixm51(no_close, SRC)[2]
    assert zone.polygons[0][0] == zone.polygons[0][-1]


def test_a_truncated_ring_is_an_error_not_a_silent_bridge():
    torn = _mutated(
        '<gml:pointProperty><aixm:Point gml:id="a3p5">'
        '<gml:pos>51.5 -0.5</gml:pos></aixm:Point></gml:pointProperty>',
        "",
    ).replace(b">51.48 -0.5<", b">51.9 -0.5<")
    with pytest.raises(AirspaceError, match="truncated"):
        parse_aixm51(torn, SRC)


def test_a_utf16_document_cannot_slip_past_the_dtd_guard():
    evil = '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "b">]><r/>'
    with pytest.raises(AirspaceError, match="encoding"):
        parse_aixm51(evil.encode("utf-16"), SRC)


def test_a_zero_extent_export_noop_segment_is_dropped():
    # EGD012 in the live file ends with a GeodesicString whose two
    # points both duplicate the ring's start — a NATS export no-op.
    # It must not trip the junction check or distort the ring.
    anchor = (
        '<gml:pointProperty><aixm:Point gml:id="a3p5">'
        '<gml:pos>51.5 -0.5</gml:pos></aixm:Point></gml:pointProperty>'
    )
    degenerate = anchor + (
        '</gml:GeodesicString>'
        '<gml:GeodesicString interpolation="geodesic">'
        '<gml:pointProperty><aixm:Point gml:id="a3d1">'
        '<gml:pos>51.5 -0.5</gml:pos></aixm:Point></gml:pointProperty>'
        '<gml:pointProperty><aixm:Point gml:id="a3d2">'
        '<gml:pos>51.5 -0.5</gml:pos></aixm:Point></gml:pointProperty>'
    )
    zones = parse_aixm51(_mutated(anchor, degenerate), SRC)
    baseline = parse_aixm51(_gb(), SRC)
    assert zones[2].polygons == baseline[2].polygons
