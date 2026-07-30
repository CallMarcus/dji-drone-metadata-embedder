"""ED-269 parser tests (#413) against the real-shape fixtures."""
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
