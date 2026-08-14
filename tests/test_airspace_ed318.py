"""ED-318 GeoJSON-profile parser tests (#452) against the real-shape fixture.

Ireland's published file is a plain GeoJSON FeatureCollection whose
vertical limits ride in a non-standard ``layer`` member inside each
feature's geometry, with timed windows in ``limitedApplicability`` and the
restriction class under ``type`` (with the Z-spelling
``REQ_AUTHORIZATION`` the ED-269 feeds spell with an S).
"""
import json
from datetime import datetime
from pathlib import Path

import pytest

from dji_metadata_embedder.geo.airspace import AirspaceError, SourceInfo
from dji_metadata_embedder.geo.airspace.ed318 import (
    ED318_FEEDS,
    discover_feed_url,
    parse_ed318,
)

FIXTURES = Path(__file__).parent.parent / "samples" / "airspace"
SRC = SourceInfo(
    feed="test", url="https://example.invalid/zones",
    fetched="2026-08-14T12:00:00Z",
    license="test", caveat="informational only",
)


def _ie() -> bytes:
    return (FIXTURES / "ed318-ie.json").read_bytes()


def test_parses_the_ireland_fixture():
    zones = parse_ed318(_ie(), SRC)
    assert [z.identifier for z in zones] == ["U901", "T901", "U902", "U903"]
    z = zones[0]
    assert z.name == "Example Control Zone - Red Zone"
    # Mixed datums are the Irish norm: floor AGL, ceiling AMSL, both feet.
    assert z.lower is not None and z.lower.label() == "0 ft AGL"
    assert z.upper is not None and z.upper.label() == "2500 ft AMSL"
    assert z.applicability == []          # no windows -> always applicable
    assert z.polygons[0][0] == (-8.50, 51.60)
    assert len(z.holes) == 1              # the inner ring is a hole (#422)
    assert z.native["properties"]["reason"] == "AIR_TRAFFIC"


def test_z_spelling_is_normalized_at_the_provider_boundary():
    # ED-269 feeds publish REQ_AUTHORISATION; Ireland publishes the
    # Z-spelling. One concept must render as one label across countries,
    # while the native block keeps what the feed actually said.
    zones = parse_ed318(_ie(), SRC)
    assert zones[0].restriction == "REQ_AUTHORISATION"
    assert zones[0].native["properties"]["type"] == "REQ_AUTHORIZATION"
    assert zones[2].restriction == "CONDITIONAL"     # others pass through


def test_limited_applicability_windows_are_utc():
    timed = parse_ed318(_ie(), SRC)[1]
    assert len(timed.applicability) == 2
    win = timed.applicability[0]
    assert win.permanent is False
    assert win.start == datetime(2026, 8, 5, 11, 0)
    assert win.end == datetime(2026, 8, 5, 22, 59)


def test_missing_layer_means_not_stated_never_zero():
    unlimited = parse_ed318(_ie(), SRC)[3]
    assert unlimited.lower is None
    assert unlimited.upper is None


def test_bom_is_tolerated():
    with_bom = b"\xef\xbb\xbf" + _ie()
    assert len(parse_ed318(with_bom, SRC)) == 4


def test_one_malformed_zone_invalidates_the_whole_document():
    broken = json.loads(_ie().decode("utf-8"))
    del broken["features"][0]["properties"]["identifier"]
    with pytest.raises(AirspaceError, match="zone 0.*identifier"):
        parse_ed318(json.dumps(broken).encode(), SRC)


def test_unexpected_vertical_reference_raises():
    broken = json.loads(_ie().decode("utf-8"))
    broken["features"][0]["geometry"]["layer"]["upperReference"] = "FL"
    with pytest.raises(AirspaceError, match="upperReference"):
        parse_ed318(json.dumps(broken).encode(), SRC)


def test_unsupported_geometry_type_raises():
    broken = json.loads(_ie().decode("utf-8"))
    broken["features"][0]["geometry"]["type"] = "Point"
    with pytest.raises(AirspaceError, match="Point"):
        parse_ed318(json.dumps(broken).encode(), SRC)


def test_plain_polygon_geometry_is_accepted():
    # The live file is all MultiPolygon today; a Polygon sibling must not
    # invalidate a future revision of the feed.
    doc = json.loads(_ie().decode("utf-8"))
    geom = doc["features"][2]["geometry"]
    geom["type"] = "Polygon"
    geom["coordinates"] = geom["coordinates"][0]
    zones = parse_ed318(json.dumps(doc).encode(), SRC)
    assert zones[2].polygons and not zones[2].holes


def test_ie_feed_registry_states_source_and_reference_only_note():
    feed = ED318_FEEDS["IE"]
    assert feed.page_url.startswith("https://www.iaa.ie/")
    assert "Irish Aviation Authority" in feed.license
    assert "navigation" in (feed.note or "")


def test_discover_feed_url_finds_the_dated_file_on_the_page():
    # The published filename is dated and versioned, so the page is the
    # stable entry point and the current href is discovered at fetch time.
    page = (
        b'<html><a href="/docs/default-source/default-document-library/uas/'
        b'20260804_uas_zones_ireland_v1.geojson?sfvrsn=f9d5eff3_188&amp;'
        b'download=true">Download</a></html>'
    )
    url = discover_feed_url(page, "https://www.iaa.ie/x/y")
    assert url == (
        "https://www.iaa.ie/docs/default-source/default-document-library/"
        "uas/20260804_uas_zones_ireland_v1.geojson"
        "?sfvrsn=f9d5eff3_188&download=true"
    )


def test_discover_feed_url_raises_when_the_page_changed_shape():
    with pytest.raises(AirspaceError, match="zones file"):
        discover_feed_url(b"<html>redesigned</html>", "https://www.iaa.ie/")
