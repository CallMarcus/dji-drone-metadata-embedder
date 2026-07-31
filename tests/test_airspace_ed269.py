"""ED-269 parser tests (#413) against the real-shape fixtures."""
import json
from datetime import datetime
from pathlib import Path

import pytest

from dji_metadata_embedder.geo.airspace import AirspaceError, SourceInfo
from dji_metadata_embedder.geo.airspace.ed269 import ED269_FEEDS, parse_ed269

FIXTURES = Path(__file__).parent.parent / "samples" / "airspace"
SRC = SourceInfo(
    feed="test", url="https://example.invalid/zones", fetched="2026-07-30T12:00:00Z",
    license="CC0", caveat="informational only",
)


def _lu() -> bytes:
    return (FIXTURES / "ed269-lu.json").read_bytes()


def _lu_data() -> dict:
    return json.loads((FIXTURES / "ed269-lu.json").read_text(encoding="utf-8-sig"))


def test_parses_the_luxembourg_fixture_through_the_bom():
    zones = parse_ed269(_lu(), SRC)
    assert [z.identifier for z in zones] == ["LU-P-001", "LU-T-002"]
    z = zones[0]
    assert z.restriction == "PROHIBITED"
    assert z.upper is not None and z.upper.label() == "120 m AGL"
    assert z.lower is not None and z.lower.label() == "0 m AGL"
    assert z.applicability == []  # permanent -> always applicable
    assert z.polygons[0][0] == (6.18, 49.61)
    assert z.native["reason"] == ["AIR_TRAFFIC"]


def test_time_bounded_applicability_is_parsed_as_utc():
    timed = parse_ed269(_lu(), SRC)[1]
    assert len(timed.applicability) == 1
    win = timed.applicability[0]
    assert win.permanent is False
    assert win.start == datetime(2026, 8, 1, 6, 0)
    assert win.end == datetime(2026, 8, 1, 18, 0)
    assert timed.upper is not None and timed.upper.reference == "AMSL"


def test_missing_limits_stay_none_never_zero():
    zones = parse_ed269((FIXTURES / "ed269-fi.json").read_bytes(), SRC)
    unlimited = next(z for z in zones if z.identifier == "FI-N-KESKUSPUISTO")
    assert unlimited.upper is None
    assert unlimited.lower is None


def test_one_malformed_zone_invalidates_the_whole_document():
    broken = _lu().decode("utf-8-sig").replace('"PROHIBITED"', "null")
    with pytest.raises(AirspaceError, match="zone 0 .*restriction"):
        parse_ed269(broken.encode("utf-8"), SRC)


def test_non_ed269_json_is_refused_loudly():
    with pytest.raises(AirspaceError, match="not an ED-269"):
        parse_ed269(b'{"hello": "world"}', SRC)


def test_feed_registry_pins_luxembourg_and_finland():
    assert ED269_FEEDS["LU"].url == "https://drones.geoportail.lu/zones"
    assert "traficom.fi" in ED269_FEEDS["FI"].url
    assert ED269_FEEDS["FI"].note is not None  # established-zones-only
    assert ED269_FEEDS["LU"].note is None


def test_a_second_geometry_entrys_malformed_vertical_reference_is_caught():
    data = _lu_data()
    zone = data["features"][0]
    second = json.loads(json.dumps(zone["geometry"][0]))
    second["lowerVerticalReference"] = "XXX"
    zone["geometry"].append(second)
    with pytest.raises(AirspaceError, match="lowerVerticalReference"):
        parse_ed269(json.dumps(data).encode(), SRC)


def test_differing_upper_limits_across_geometry_entries_are_rejected():
    data = _lu_data()
    zone = data["features"][0]
    second = json.loads(json.dumps(zone["geometry"][0]))
    second["upperLimit"] = 999
    zone["geometry"].append(second)
    with pytest.raises(AirspaceError, match="differing"):
        parse_ed269(json.dumps(data).encode(), SRC)


def test_matching_restated_limits_merge_both_geometry_entries_polygons():
    data = _lu_data()
    zone = data["features"][0]
    second = json.loads(json.dumps(zone["geometry"][0]))
    second["horizontalProjection"]["coordinates"] = [[
        [7.0, 50.0], [7.1, 50.0], [7.1, 50.1], [7.0, 50.1], [7.0, 50.0],
    ]]
    zone["geometry"].append(second)
    zones = parse_ed269(json.dumps(data).encode(), SRC)
    parsed = next(z for z in zones if z.identifier == "LU-P-001")
    assert len(parsed.polygons) == 2
    assert parsed.polygons[0][0] == (6.18, 49.61)
    assert parsed.polygons[1][0] == (7.0, 50.0)


def test_malformed_start_date_time_names_the_field():
    data = _lu_data()
    zone = next(f for f in data["features"] if f["identifier"] == "LU-T-002")
    zone["applicability"][0]["startDateTime"] = "not-a-date"
    with pytest.raises(AirspaceError, match="startDateTime"):
        parse_ed269(json.dumps(data).encode(), SRC)


def test_a_permanent_entry_alongside_timed_windows_wins_always_applicable():
    data = _lu_data()
    zone = next(f for f in data["features"] if f["identifier"] == "LU-T-002")
    assert zone["applicability"]  # already has a timed window in the fixture
    zone["applicability"].append({"permanent": "YES"})
    zones = parse_ed269(json.dumps(data).encode(), SRC)
    parsed = next(z for z in zones if z.identifier == "LU-T-002")
    assert parsed.applicability == []


def test_offset_applicability_start_is_normalized_to_naive_utc():
    data = _lu_data()
    zone = next(f for f in data["features"] if f["identifier"] == "LU-T-002")
    zone["applicability"][0]["startDateTime"] = "2026-08-01T08:00:00+02:00"
    zones = parse_ed269(json.dumps(data).encode(), SRC)
    parsed = next(z for z in zones if z.identifier == "LU-T-002")
    assert parsed.applicability[0].start == datetime(2026, 8, 1, 6, 0)


def test_interior_rings_parse_into_holes():
    # GeoJSON Polygon: coordinates[0] is the exterior, the rest are holes
    # (#422 review) — they must not land in Zone.polygons, where the
    # evaluator would treat them as more zone.
    data = _lu_data()
    proj = data["features"][0]["geometry"][0]["horizontalProjection"]
    x, y = proj["coordinates"][0][0]
    hole = [[x, y], [x + 0.001, y], [x + 0.001, y + 0.001], [x, y]]
    proj["coordinates"].append(hole)
    zones = parse_ed269(json.dumps(data).encode(), SRC)
    z = zones[0]
    assert len(z.holes) == 1
    assert z.holes[0] == [(float(cx), float(cy)) for cx, cy in hole]
    assert z.holes[0] not in z.polygons
    assert z.polygons  # the exterior stayed where it was
