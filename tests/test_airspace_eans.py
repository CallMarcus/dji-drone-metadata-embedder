"""EANS Estonia uas.geojson parser tests (#511) against the synthetic fixture.

The live file is GeoJSON features whose properties embed one ED-269-style
volume dict (ED-269 field names, S-spelled restrictions, permanent-YES
applicability semantics). Two publisher viewer masks are skipped by
contract; everything else malformed raises.
"""
import json
from datetime import datetime
from pathlib import Path

import pytest

from dji_metadata_embedder.geo.airspace import AirspaceError, SourceInfo
from dji_metadata_embedder.geo.airspace.eans import EANS_FEEDS, parse_eans

FIXTURES = Path(__file__).parent.parent / "samples" / "airspace"
SRC = SourceInfo(
    feed="test", url="https://example.invalid/uas.geojson",
    fetched="2026-08-19T12:00:00Z",
    license="test", caveat="informational only",
)


def _ee() -> bytes:
    return (FIXTURES / "eans-ee.json").read_bytes()


def test_parses_the_fixture_and_skips_exactly_the_two_masks():
    zones = parse_eans(_ee(), SRC)
    # 5 features in, 3 zones out: the hidden shade and EERZout are the
    # publisher's viewer furniture, skipped by contract — never silently.
    assert [z.identifier for z in zones] == ["EE901", "EE902", "A990126"]
    assert all(z.identifier != "EERZout" for z in zones)


def test_metric_zone_limits_and_permanent_applicability():
    z = parse_eans(_ee(), SRC)[0]
    assert z.name == "Example aerodrome zone"
    assert z.restriction == "REQ_AUTHORISATION"   # natively S-spelled
    assert z.lower is not None and z.lower.label() == "0 m AGL"
    assert z.upper is not None and z.upper.label() == "120 m AGL"
    assert z.applicability == []                  # permanent YES -> always
    assert z.native["properties"]["upper"] == "120 M AGL"


def test_feet_zone_with_hole_and_seasonal_window():
    z = parse_eans(_ee(), SRC)[1]
    assert z.upper is not None and z.upper.label() == "6000 ft AGL"
    assert len(z.polygons) == 1 and len(z.holes) == 1   # inner ring (#422)
    assert len(z.applicability) == 1
    win = z.applicability[0]
    assert win.permanent is False
    assert win.start == datetime(2026, 4, 1, 0, 0)
    assert win.end == datetime(2026, 11, 30, 0, 0)


def test_notam_zone_keeps_schedule_text_in_native_only():
    z = parse_eans(_ee(), SRC)[2]
    assert z.name == "A9901/26"                   # display name, with slash
    assert z.applicability[0].start == datetime(2026, 8, 18, 5, 0)
    assert "[Schedule:" in z.native["properties"]["message"]


def test_empty_name_falls_back_to_airspaceclass_then_identifier():
    doc = json.loads(_ee().decode("utf-8"))
    doc["features"][0]["properties"]["name"] = ""
    zones = parse_eans(json.dumps(doc).encode(), SRC)
    assert zones[0].name == "EEGZ901"             # airspaceclass fallback
    doc["features"][0]["properties"]["airspaceclass"] = ""
    zones = parse_eans(json.dumps(doc).encode(), SRC)
    assert zones[0].name == "EE901"               # identifier fallback


def test_a_new_hidden_feature_still_skips():
    doc = json.loads(_ee().decode("utf-8"))
    doc["features"][1]["properties"]["hidden"] = True
    zones = parse_eans(json.dumps(doc).encode(), SRC)
    assert [z.identifier for z in zones] == ["EE901", "A990126"]


def test_one_malformed_zone_invalidates_the_whole_document():
    broken = json.loads(_ee().decode("utf-8"))
    del broken["features"][0]["properties"]["identifier"]
    with pytest.raises(AirspaceError, match="zone 0.*identifier"):
        parse_eans(json.dumps(broken).encode(), SRC)


def test_unexpected_vertical_reference_raises():
    broken = json.loads(_ee().decode("utf-8"))
    broken["features"][0]["properties"]["geometry"]["upperVerticalReference"] = "STD"
    with pytest.raises(AirspaceError, match="upperVerticalReference"):
        parse_eans(json.dumps(broken).encode(), SRC)


def test_non_polygon_geometry_raises():
    broken = json.loads(_ee().decode("utf-8"))
    broken["features"][0]["geometry"]["type"] = "Point"
    with pytest.raises(AirspaceError, match="Point"):
        parse_eans(json.dumps(broken).encode(), SRC)


def test_missing_volume_dict_means_not_stated_never_zero():
    doc = json.loads(_ee().decode("utf-8"))
    del doc["features"][0]["properties"]["geometry"]
    zones = parse_eans(json.dumps(doc).encode(), SRC)
    assert zones[0].lower is None and zones[0].upper is None


def test_bom_is_tolerated():
    with_bom = b"\xef\xbb\xbf" + _ee()
    assert len(parse_eans(with_bom, SRC)) == 3


def test_ee_feed_registry_states_the_eans_terms():
    feed = EANS_FEEDS["EE"]
    assert feed.url == "https://utm.eans.ee/avm/utm/uas.geojson"
    assert "Estonian Air Navigation Services" in feed.license
    assert "2026-08-19" in feed.license
    assert "time of download" in (feed.note or "")
    assert "not evaluated" in (feed.note or "")
