from datetime import datetime

from dji_metadata_embedder.geo.map_html import mixed_to_geojson
from dji_metadata_embedder.geo.photomap import PhotoPoint
from dji_metadata_embedder.geo.track import Track, TrackPoint

POINTS = [
    PhotoPoint(lat=60.17, lon=24.95, alt=95.3, name="church.jpg",
               timestamp="2026-06-15 12:30:45", model="FC8482",
               thumbnail_b64="/9j/THUMB1"),
    PhotoPoint(lat=60.18, lon=24.96, alt=None, name="sphere.jpg",
               is_pano=True, pano_yaw=45.0),
]

TRACKS = [
    Track(name="DJI_0001", points=[
        TrackPoint(lat=60.19, lon=24.97, alt=5.0, timestamp="00:00:00,000",
                   utc=datetime(2026, 6, 15, 12, 0, 0)),
        TrackPoint(lat=60.191, lon=24.971, alt=6.5, timestamp="00:00:01,000",
                   utc=datetime(2026, 6, 15, 12, 1, 0)),
    ]),
]


def test_mixed_geojson_tags_every_feature_by_type():
    data = mixed_to_geojson(POINTS, TRACKS)
    types = [f["properties"]["type"] for f in data["features"]]
    assert types == ["photo", "pano", "track"]
    assert data["type"] == "FeatureCollection"


def test_mixed_geojson_keeps_photo_thumbnails_and_track_playback():
    data = mixed_to_geojson(POINTS, TRACKS)
    photo, pano, track = data["features"]
    assert photo["properties"]["thumb"] == "/9j/THUMB1"
    assert track["geometry"]["type"] == "LineString"
    assert track["properties"]["times_s"] == [0.0, 60.0]


def test_mixed_geojson_records_redaction_mode():
    assert mixed_to_geojson(POINTS, TRACKS)["redacted"] == "none"
    assert mixed_to_geojson(POINTS, TRACKS, redact="fuzz")["redacted"] == "fuzz"


def test_mixed_geojson_links_are_opt_in():
    no_links = mixed_to_geojson(POINTS, TRACKS)
    assert all("link" not in f["properties"] for f in no_links["features"])
    linked = mixed_to_geojson(POINTS, TRACKS, link_base="")
    assert linked["features"][0]["properties"]["link"] == "church.jpg"


def test_mixed_geojson_single_type_folders():
    assert [f["properties"]["type"]
            for f in mixed_to_geojson(POINTS, [])["features"]] == ["photo", "pano"]
    assert [f["properties"]["type"]
            for f in mixed_to_geojson([], TRACKS)["features"]] == ["track"]
