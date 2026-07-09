import json
from datetime import datetime

from dji_metadata_embedder.geo.flightmap import (
    flights_to_geojson,
    flights_to_kml,
    format_duration,
    scan_flights,
    write_flights_geojson,
    write_flights_kml,
)
from dji_metadata_embedder.geo.track import Track, TrackPoint


def _bracket_srt(*coords: tuple[float, float, float]) -> str:
    """Minimal bracket-format SRT with one block per (lat, lon, alt)."""
    blocks = []
    for i, (lat, lon, alt) in enumerate(coords):
        blocks.append(
            f"{i + 1}\n00:00:{i:02d},000 --> 00:00:{i + 1:02d},000\n"
            f'<font size="28">[latitude: {lat}] [longitude: {lon}] '
            f"[rel_alt: 1.000 abs_alt: {alt}]</font>\n"
        )
    return "\n".join(blocks)


FLIGHT_A = _bracket_srt((10.0, 20.0, 5.0), (10.001, 20.001, 6.0))
FLIGHT_B = _bracket_srt((11.0, 21.0, 7.0), (11.001, 21.001, 8.0))
SINGLE_FIX = _bracket_srt((12.0, 22.0, 9.0))
NOT_TELEMETRY = "1\n00:00:00,000 --> 00:00:01,000\nJust a movie subtitle\n"


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_scan_flights_builds_sorted_tracks_and_skips_non_telemetry(tmp_path):
    _write(tmp_path, "DJI_0002.SRT", FLIGHT_B)
    _write(tmp_path, "DJI_0001.SRT", FLIGHT_A)
    _write(tmp_path, "movie.srt", NOT_TELEMETRY)
    tracks, skipped = scan_flights(tmp_path)
    assert [t.name for t in tracks] == ["DJI_0001", "DJI_0002"]
    assert skipped == ["movie"]
    assert tracks[0].points[0].lat == 10.0


def test_scan_flights_non_recursive_ignores_subdirs(tmp_path):
    _write(tmp_path, "sub/DJI_0001.SRT", FLIGHT_A)
    tracks, skipped = scan_flights(tmp_path)
    assert tracks == [] and skipped == []


def test_scan_flights_recursive_labels_include_subdir(tmp_path):
    _write(tmp_path, "session1/DJI_0001.SRT", FLIGHT_A)
    _write(tmp_path, "session2/DJI_0001.SRT", FLIGHT_B)
    tracks, _ = scan_flights(tmp_path, recursive=True)
    assert [t.name for t in tracks] == ["session1/DJI_0001", "session2/DJI_0001"]


def test_scan_flights_fuzz_coarsens_coordinates(tmp_path):
    _write(tmp_path, "DJI_0001.SRT", _bracket_srt((10.123456, 20.654321, 5.0),
                                                  (10.123999, 20.654999, 6.0)))
    tracks, _ = scan_flights(tmp_path, redact="fuzz")
    p = tracks[0].points[0]
    assert (p.lat, p.lon) == (10.123, 20.654)


def _tracks() -> list[Track]:
    return [
        Track(name="DJI_0001", points=[
            TrackPoint(lat=10.0, lon=20.0, alt=5.0, timestamp="00:00:00,000",
                       utc=datetime(2026, 6, 15, 12, 0, 0)),
            TrackPoint(lat=10.001, lon=20.001, alt=6.5, timestamp="00:00:01,000",
                       utc=datetime(2026, 6, 15, 12, 4, 3)),
        ]),
        Track(name="one_fix", points=[
            TrackPoint(lat=12.0, lon=22.0, alt=9.0, timestamp="00:00:00,000")
        ]),
    ]


def test_flights_to_geojson_one_feature_per_flight():
    data = flights_to_geojson(_tracks())
    assert data["type"] == "FeatureCollection"
    line, point = data["features"]
    assert line["geometry"]["type"] == "LineString"
    assert line["geometry"]["coordinates"] == [[20.0, 10.0, 5.0], [20.001, 10.001, 6.5]]
    props = line["properties"]
    assert props["name"] == "DJI_0001"
    assert props["start"] == "2026-06-15 12:00:00 UTC"
    assert props["duration_s"] == 243
    assert (props["alt_min"], props["alt_max"]) == (5.0, 6.5)
    # RFC 7946 forbids a 1-position LineString: single-fix clips become Points.
    assert point["geometry"] == {"type": "Point", "coordinates": [22.0, 12.0, 9.0]}
    assert "start" not in point["properties"]  # no UTC -> no start/duration


def test_flights_to_kml_one_placemark_per_flight():
    kml = flights_to_kml(_tracks(), title="My flights")
    assert kml.count("<Placemark>") == 2
    assert "<name>My flights</name>" in kml
    assert "<name>DJI_0001</name>" in kml
    assert "duration: 4:03" in kml
    assert "<LineString>" in kml and "<Point>" in kml
    assert "20.0,10.0,5.0 20.001,10.001,6.5" in kml


def test_flights_to_kml_escapes_names():
    tracks = [Track(name="a<b&c", points=[
        TrackPoint(lat=1.0, lon=2.0, alt=3.0, timestamp="00:00:00,000")])]
    kml = flights_to_kml(tracks, title="t<&>")
    assert "a<b&c" not in kml
    assert "a&lt;b&amp;c" in kml
    assert "t&lt;&amp;&gt;" in kml


def test_format_duration():
    assert format_duration(0) == "0:00"
    assert format_duration(243) == "4:03"
    assert format_duration(3723) == "1:02:03"


def test_writers_create_files(tmp_path):
    tracks = _tracks()
    geo = write_flights_geojson(tracks, tmp_path / "f.geojson")
    kml = write_flights_kml(tracks, tmp_path / "f.kml", title="t")
    assert json.loads(geo.read_text(encoding="utf-8"))["type"] == "FeatureCollection"
    assert "<kml" in kml.read_text(encoding="utf-8")
