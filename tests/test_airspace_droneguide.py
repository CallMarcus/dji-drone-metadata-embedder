"""Droneguide (Belgium) provider tests (#562) against the fixture envelope.

The fixture is one cache envelope as ``fetch_zones`` writes it: the
``uaszone`` WFS response for a flight window, the ``notam`` layer response,
and the window itself. Eleven real rows cover every parsing rule the live
layer exhibits.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from dji_metadata_embedder.geo.airspace.droneguide import (
    DRONEGUIDE_FEEDS,
    NOT_ACTIVE_REASON,
    build_envelope,
    cache_name,
    notam_url,
    parse_droneguide,
    zones_url,
)
from dji_metadata_embedder.geo.airspace.model import (
    AirspaceError,
    Applicability,
    SourceInfo,
    VerticalLimit,
)

FIXTURE = Path(__file__).parent.parent / "samples" / "airspace" / "droneguide-be.json"
OWS = "https://map.droneguide.be/ows"
WINDOW = (datetime(2026, 9, 16, 7, 0), datetime(2026, 9, 16, 9, 0))
SOURCE = SourceInfo(
    feed="Belgium UAS geographical zones (Droneguide, skeyes for the BCAA)",
    url=OWS, fetched="2026-09-16T09:29:00Z", license="test", caveat="test",
)


def fixture_zones():
    return parse_droneguide(FIXTURE.read_bytes(), SOURCE)


def zone(zones, ident):
    return next(z for z in zones if z.identifier == ident)


def test_registry_carries_the_bcaa_notices_and_permission_record():
    feed = DRONEGUIDE_FEEDS["BE"]
    assert feed.ows_url == OWS and feed.page_url == "https://map.droneguide.be/"
    assert "G26-187" in feed.license
    for phrase in ("Not an official application of the BCAA",
                   "official publication channels",
                   "remains with the remote pilot and UAS operator",
                   "publisher's evaluation"):
        assert phrase in feed.note, phrase


def test_zones_url_filters_time_zones_and_escapes_the_window():
    q = parse_qs(urlsplit(zones_url(OWS, WINDOW)).query)
    assert q["typeNames"] == ["uaszone"] and q["outputFormat"] == ["application/json"]
    assert q["cql_filter"] == ["type_code<>'TIME_ZONE'"]
    assert q["viewparams"] == [
        ("window_start:2026-09-16T07\\:00\\:00.000Z;"
        "window_end:2026-09-16T09\\:00\\:00.000Z;show_planned:true")
    ]


def test_zones_url_without_a_window_sends_no_viewparams():
    q = parse_qs(urlsplit(zones_url(OWS, None)).query)
    assert "viewparams" not in q and q["cql_filter"] == ["type_code<>'TIME_ZONE'"]


def test_notam_url_asks_for_the_date_fields_only():
    q = parse_qs(urlsplit(notam_url(OWS)).query)
    assert q["typeNames"] == ["notam"]
    assert q["propertyName"] == [
        "identification,start_date,end_date,scheduling,selection_code,location,fir"
    ]


def test_cache_name_is_per_flight_window():
    assert cache_name("BE", WINDOW) == "droneguide-BE-20260916T070000Z-20260916T090000Z.json"
    assert cache_name("BE", None) == "droneguide-BE-nowindow.json"


def test_build_envelope_wraps_both_bodies_and_the_window():
    env = json.loads(build_envelope(b'{"features": []}', b'{"features": []}', WINDOW))
    assert env == {"window": ["2026-09-16T07:00:00Z", "2026-09-16T09:00:00Z"],
                   "zones": {"features": []}, "notam": {"features": []}}
    unwindowed = json.loads(build_envelope(b'{"features": []}', b'{"features": []}', None))
    assert unwindowed["window"] is None


def test_build_envelope_rejects_a_non_json_body():
    with pytest.raises(AirspaceError, match="not JSON"):
        build_envelope(b"<html>maintenance</html>", b'{"features": []}', None)


# --- the parser --------------------------------------------------------------

def test_every_fixture_row_parses_and_shared_codes_get_a_uuid_suffix():
    zones = fixture_zones()
    assert len(zones) == 11
    ids = {z.identifier for z in zones}
    assert {"EBBL:66812c63", "EBBL:d67737fe", "B1468", "G2219/26", "4842917"} <= ids
    assert "EBBL" not in ids


def test_names_pick_english_from_the_language_map_and_pass_plain_text():
    zones = fixture_zones()
    assert zone(zones, "EBBL:66812c63").name == "KLEINE-BROGEL CTR"
    assert zone(zones, "G26142").name == "Werchter 2026"
    assert zone(zones, "G1464/26").name == "G1464/26"


def test_limits_map_units_and_datums():
    zones = fixture_zones()
    ctr = zone(zones, "EBBL:66812c63")
    assert ctr.lower == VerticalLimit(0, "ft", "AGL")
    assert ctr.upper == VerticalLimit(2500, "ft", "AMSL")
    werchter = zone(zones, "G26142")
    assert werchter.lower is None and werchter.upper == VerticalLimit(400, "m", "AGL")
    assert zone(zones, "G26126a").upper == VerticalLimit(400, "ft", "AGL")


def test_a_flight_level_is_always_the_standard_datum():
    # 38 live NOTAM rows say "FL 75 GND"; the unit wins, the row stays native.
    notam = zone(fixture_zones(), "G1464/26")
    assert notam.lower == VerticalLimit(55, "FL", "STD")
    assert notam.upper == VerticalLimit(75, "FL", "STD")
    assert notam.native["upper_limit_reference"] == "GND"


def test_fl_999_means_unlimited_and_renders_not_stated():
    tra = zone(fixture_zones(), "EBTRA WD")
    assert tra.lower == VerticalLimit(195, "FL", "STD") and tra.upper is None


def test_notam_zones_take_their_dates_and_schedule_from_the_notam_layer():
    zones = fixture_zones()
    current = zone(zones, "G2219/26")
    assert current.applicability == [Applicability(
        start=datetime(2026, 9, 16, 12, 15), end=datetime(2026, 9, 20, 14, 30),
        permanent=False,
    )]
    assert current.activation == [
        "16 1215-1730, 17 1200-1730, 18 1130-1730, 19 1330-1730, 20 0945-1430"
    ]
    assert "NOTAM QROLT EBBU" in current.notes
    assert current.native["notam"]["identification"] == "G2219/26"
    expired = zone(zones, "G1464/26")
    assert expired.applicability[0].end == datetime(2026, 6, 15, 15, 0)
    assert expired.activation == []


def test_an_unmatched_notam_zone_keeps_no_window_and_says_so():
    z = zone(fixture_zones(), "F1342/26")
    assert z.applicability == []
    assert "NOTAM validity dates not found in the Droneguide NOTAM layer" in z.notes


def test_publisher_inactive_flag_becomes_the_not_active_reason_only_with_a_window():
    zones = fixture_zones()
    assert zone(zones, "G26142").not_active_reason == NOT_ACTIVE_REASON
    assert zone(zones, "G1464/26").not_active_reason == NOT_ACTIVE_REASON
    assert zone(zones, "G26126a").not_active_reason is None
    env = json.loads(FIXTURE.read_text(encoding="utf-8"))
    env["window"] = None
    unwindowed = parse_droneguide(json.dumps(env).encode(), SOURCE)
    assert all(z.not_active_reason is None for z in unwindowed)


def test_notes_carry_the_type_code_and_the_description():
    zones = fixture_zones()
    assert zone(zones, "B1468").notes == ["Droneguide type: CIV_PRISON"]
    werchter = zone(zones, "G26142")
    assert werchter.notes[0] == "Droneguide type: TEMPORARY-NO-FLY-ZONE"
    assert werchter.notes[1].startswith("A prior flight authorisation")
    assert zone(zones, "G1464/26").notes[1].startswith("TEMPO SEGREGATED AREA")


def test_multipolygon_and_polygon_geometry_both_parse():
    zones = fixture_zones()
    assert len(zone(zones, "4842917").polygons) == 2
    assert len(zone(zones, "B1468").polygons) == 1 and zone(zones, "B1468").holes == []
    # The layer publishes the pre-densification shape as a JSON string;
    # native keeps it exactly as published.
    circle = json.loads(zone(zones, "G26142").native["original_geometry"])
    assert circle["type"] == "Circle" and circle["radius"] > 0


def _env(mutate):
    env = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mutate(env)
    return json.dumps(env).encode()


def _first(env):
    return env["zones"]["features"][0]["properties"]


@pytest.mark.parametrize("mutate, message", [
    (lambda e: _first(e).__setitem__("type_code", "TIME_ZONE"), "TIME_ZONE"),
    (lambda e: _first(e).__setitem__("code", ""), "code"),
    (lambda e: _first(e).__setitem__("name", None), "name"),
    (lambda e: _first(e).__setitem__("restriction", None), "restriction"),
    (lambda e: _first(e).__setitem__("upper_limit_unit", "KM"), "unit"),
    (lambda e: _first(e).__setitem__("upper_limit_reference", "SFC"), "reference"),
    (lambda e: _first(e).__setitem__("upper_limit_altitude", "high"), "not a number"),
    (lambda e: e["zones"]["features"][0].__setitem__(
        "geometry", {"type": "Point", "coordinates": [4, 50]}), "geometry"),
    (lambda e: e.pop("notam"), "envelope"),
    (lambda e: e["notam"]["features"].append(dict(e["notam"]["features"][0])), "duplicate"),
])
def test_malformed_rows_fail_loudly(mutate, message):
    with pytest.raises(AirspaceError, match=message):
        parse_droneguide(_env(mutate), SOURCE)


def test_a_non_json_envelope_fails_loudly():
    with pytest.raises(AirspaceError, match="not JSON"):
        parse_droneguide(b"<html>", SOURCE)
