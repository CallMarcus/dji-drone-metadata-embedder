"""Denmark Dronezoner provider (Trafikstyrelsen GeoJSON)."""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import pytest

from dji_metadata_embedder.geo.airspace.dronezoner import (
    DRONEZONER_FEEDS,
    discover_feed_url,
    parse_dronezoner,
)
from dji_metadata_embedder.geo.airspace.model import AirspaceError, SourceInfo

FIXTURE = (
    Path(__file__).parent.parent / "samples" / "airspace" / "dronezoner-dk.json"
)

SOURCE = SourceInfo(
    feed="Denmark drone zones (Trafikstyrelsen)",
    url="https://example.test/page",
    fetched="2026-08-15T12:00:00Z",
    license="test",
    caveat="test",
)

PAGE = b"""
<html><body>
<a href="https://trafikstyrelsen.maps.arcgis.com/sharing/rest/content/items/1a629c73da354790b7501091354a3943/data">GeoPackage</a>
<a href="https://trafikstyrelsen.maps.arcgis.com/sharing/rest/content/items/f049a65ae2f34bd1b747895d555dac71/data">GeoJson</a>
<a href="https://trafikstyrelsen.maps.arcgis.com/sharing/rest/content/items/c92fcd162f9346ae818858b1640a565f/data">KML</a>
</body></html>
"""


def fixture_zones():
    return parse_dronezoner(FIXTURE.read_bytes(), SOURCE)


def zone(zones, ident):
    return next(z for z in zones if z.identifier == ident)


def dist_m(a, b):
    # Small-angle equirectangular distance, plenty for circle radii.
    lat = math.radians((a[1] + b[1]) / 2)
    dx = math.radians(b[0] - a[0]) * math.cos(lat) * 6371000
    dy = math.radians(b[1] - a[1]) * 6371000
    return math.hypot(dx, dy)


class TestDiscovery:
    def test_picks_the_geojson_link_among_the_five_formats(self):
        url = discover_feed_url(PAGE, DRONEZONER_FEEDS["DK"].page_url)
        assert url == (
            "https://trafikstyrelsen.maps.arcgis.com/sharing/rest/content/"
            "items/f049a65ae2f34bd1b747895d555dac71/data"
        )

    def test_page_without_a_geojson_link_raises(self):
        with pytest.raises(AirspaceError, match="droneregler.dk"):
            discover_feed_url(b"<html>redesigned</html>", "https://x.test/")


class TestParsing:
    def test_marker_points_and_inactive_zones_are_dropped(self):
        zones = fixture_zones()
        # 11 features: the polygon-twin Point markers (one via the
        # live file's Retsvæsen/Restvæsen typeId typo — dedup must not
        # look at typeId), the Aktiv NEJ feature and the bufferless
        # awareness-class site marker all drop; the rest are zones.
        assert len(zones) == 7
        assert {z.identifier for z in zones} == {
            "DK-1", "DK-2", "DK-3", "DK-4", "DK-6", "DK-7", "DK-8"
        }

    def test_a_typo_divergent_typeid_still_dedups_the_marker(self):
        # The point twin spells "Retsvæsen", the polygon "Restvæsen":
        # the polygon zone survives, the buffer-less point drops as its
        # marker instead of raising.
        zones = fixture_zones()
        z = zone(zones, "DK-8")
        assert z.native["properties"]["typeId"] == "Restvæsen"

    def test_a_bufferless_awareness_site_marker_is_skipped(self):
        # Model-club markers carry no extent at all in the live file —
        # a dimensionless point cannot be crossed, so it is not a zone.
        zones = fixture_zones()
        assert not any("Test Modelflyveklub" in z.name for z in zones)

    def test_colour_classes_map_to_the_official_layer_names(self):
        zones = fixture_zones()
        assert zone(zones, "DK-1").restriction == "Flight-safety-critical (RØD)"
        assert zone(zones, "DK-2").restriction == "Security-critical (BLÅ)"
        assert zone(zones, "DK-4").restriction == "Awareness (ORANGE)"

    def test_three_element_positions_lose_only_the_z(self):
        z = zone(fixture_zones(), "DK-1")
        assert z.polygons[0][0] == (12.50, 55.60)

    def test_multipolygon_keeps_parts_and_holes_apart(self):
        z = zone(fixture_zones(), "DK-2")
        assert len(z.polygons) == 2
        assert len(z.holes) == 1
        assert z.holes[0][0] == (12.31, 55.71)

    def test_orphan_point_with_metre_units_becomes_a_150_m_circle(self):
        z = zone(fixture_zones(), "DK-3")
        ring = z.polygons[0]
        assert len(ring) == 129  # 128 steps + closure
        assert ring[0] == ring[-1]
        for pos in ring[:8]:
            assert dist_m((12.20, 55.50), pos) == pytest.approx(150, rel=0.01)

    def test_orphan_point_with_km_lovkrav_becomes_a_3_km_circle(self):
        z = zone(fixture_zones(), "DK-7")
        assert dist_m((12.00, 55.40), z.polygons[0][0]) == pytest.approx(
            3000, rel=0.01
        )

    def test_orphan_point_falls_back_to_the_bufferzone_string(self):
        z = zone(fixture_zones(), "DK-4")
        assert dist_m((12.10, 55.45), z.polygons[0][0]) == pytest.approx(
            2000, rel=0.01
        )

    def test_no_vertical_limits_are_ever_invented(self):
        for z in fixture_zones():
            assert z.lower is None and z.upper is None

    def test_temporary_zone_carries_its_window(self):
        z = zone(fixture_zones(), "DK-6")
        assert len(z.applicability) == 1
        win = z.applicability[0]
        assert not win.permanent
        # Naive UTC, matching ed269._utc and Track.utc (#520): tz-aware
        # windows crashed the evaluator on any timestamped flight.
        assert win.start == datetime(2026, 9, 7, 6, 0)
        assert win.end == datetime(2026, 9, 11, 18, 0)

    def test_permanent_zones_have_no_applicability_entries(self):
        assert zone(fixture_zones(), "DK-2").applicability == []

    def test_native_keeps_the_full_feature(self):
        z = zone(fixture_zones(), "DK-1")
        assert z.native["properties"]["ICAO"] == "EKTS"
        assert z.native["properties"]["Elevation_fod"] == 17


def _one_feature(props, geometry):
    return json.dumps(
        {"type": "FeatureCollection",
         "features": [{"type": "Feature", "geometry": geometry,
                       "properties": props}]}
    ).encode()


class TestAllOrNothing:
    def test_not_json_raises(self):
        with pytest.raises(AirspaceError, match="not JSON"):
            parse_dronezoner(b"<html>", SOURCE)

    def test_no_features_list_raises(self):
        with pytest.raises(AirspaceError, match="features"):
            parse_dronezoner(b"{}", SOURCE)

    def test_unknown_colour_class_raises(self):
        body = _one_feature(
            {"OBJECTID": 9, "title": "X", "typeId": "Y", "Farve": "2"},
            {"type": "Point", "coordinates": [12.0, 55.0]},
        )
        with pytest.raises(AirspaceError, match="Farve='2'"):
            parse_dronezoner(body, SOURCE)

    def test_point_without_any_buffer_raises(self):
        body = _one_feature(
            {"OBJECTID": 9, "title": "X", "typeId": "Politi", "Farve": "4"},
            {"type": "Point", "coordinates": [12.0, 55.0]},
        )
        with pytest.raises(AirspaceError, match="buffer distance"):
            parse_dronezoner(body, SOURCE)

    def test_unparseable_window_raises(self):
        body = _one_feature(
            {"OBJECTID": 9, "title": "X", "typeId": "MGZ", "Farve": "4",
             "datoTidSTART": "next Tuesday-ish"},
            {"type": "Polygon", "coordinates": [
                [[12.0, 55.0], [12.1, 55.0], [12.1, 55.1], [12.0, 55.0]]
            ]},
        )
        with pytest.raises(AirspaceError, match="datoTidSTART"):
            parse_dronezoner(body, SOURCE)

    def test_unsupported_geometry_raises(self):
        body = _one_feature(
            {"OBJECTID": 9, "title": "X", "typeId": "Y", "Farve": "4"},
            {"type": "LineString", "coordinates": [[12.0, 55.0], [12.1, 55.1]]},
        )
        with pytest.raises(AirspaceError, match="LineString"):
            parse_dronezoner(body, SOURCE)

    def test_missing_objectid_raises(self):
        body = _one_feature(
            {"title": "X", "typeId": "Y", "Farve": "4"},
            {"type": "Polygon", "coordinates": [
                [[12.0, 55.0], [12.1, 55.0], [12.1, 55.1], [12.0, 55.0]]
            ]},
        )
        with pytest.raises(AirspaceError, match="OBJECTID"):
            parse_dronezoner(body, SOURCE)


class TestEvaluateIntegration:
    def test_windowed_zone_evaluates_against_a_timestamped_track(self):
        # #520 regression: zone windows must be naive UTC like every other
        # provider's (ed269._utc semantics) — Track.utc is naive, and a
        # tz-aware window made evaluate() die with a TypeError instead of
        # an AirspaceError on any normal timestamped Danish flight.
        from dji_metadata_embedder.geo.airspace.evaluate import evaluate
        from dji_metadata_embedder.geo.track import Track, TrackPoint

        z = zone(fixture_zones(), "DK-6")
        lon, lat = z.polygons[0][0]
        pts = [TrackPoint(lat=lat, lon=lon, alt=50, timestamp="c",
                          utc=datetime(2026, 9, 8, 12, 0), rel_alt=20)]
        report = evaluate(Track(name="dk", points=pts), [z])
        assert z not in report.not_applicable

    def test_windowed_zone_outside_its_window_is_not_applicable(self):
        from dji_metadata_embedder.geo.airspace.evaluate import evaluate
        from dji_metadata_embedder.geo.track import Track, TrackPoint

        z = zone(fixture_zones(), "DK-6")
        lon, lat = z.polygons[0][0]
        pts = [TrackPoint(lat=lat, lon=lon, alt=50, timestamp="c",
                          utc=datetime(2026, 10, 1, 12, 0), rel_alt=20)]
        report = evaluate(Track(name="dk", points=pts), [z])
        assert z in report.not_applicable
