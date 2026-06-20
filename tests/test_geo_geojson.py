import json
from pathlib import Path

from dji_metadata_embedder.geo.geojson import convert_to_geojson, track_to_geojson
from dji_metadata_embedder.geo.track import Track, build_track

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
CLIP = SAMPLES / "air3S" / "clip.SRT"


def test_empty_track_uses_null_geometry_not_empty_linestring():
    # RFC 7946 forbids a LineString with fewer than two positions, so an empty
    # track must serialize to a null geometry rather than an invalid empty one.
    fc = track_to_geojson(Track(name="empty", points=[]))
    assert fc["features"][0]["geometry"] is None
    assert all(f["geometry"] is None for f in fc["features"])


def test_track_to_geojson_structure():
    fc = track_to_geojson(build_track(CLIP))
    assert fc["type"] == "FeatureCollection"

    line = fc["features"][0]
    assert line["geometry"]["type"] == "LineString"
    # GeoJSON is [lon, lat, alt] order, the reverse of DJI's printed lat/lon.
    assert line["geometry"]["coordinates"][0] == [-84.176160, 34.270373, 302.208]

    points = [f for f in fc["features"] if f["geometry"]["type"] == "Point"]
    assert len(points) == 5
    assert points[0]["properties"]["abs_alt"] == 302.208
    assert "timestamp" in points[0]["properties"]


def test_convert_to_geojson_writes_valid_file(tmp_path):
    out = tmp_path / "clip.geojson"
    result = convert_to_geojson(CLIP, out)
    assert result == out
    data = json.loads(out.read_text())
    assert data["type"] == "FeatureCollection"


def test_convert_to_geojson_default_output_path(tmp_path):
    srt = tmp_path / "flight.SRT"
    srt.write_text(CLIP.read_text(encoding="utf-8"), encoding="utf-8")
    result = convert_to_geojson(srt)
    assert result == srt.with_suffix(".geojson")
    assert result.exists()


def test_geojson_includes_footprint_polygons():
    from pathlib import Path
    from dji_metadata_embedder.geo.track import build_track
    from dji_metadata_embedder.geo.footprint import build_footprints
    from dji_metadata_embedder.geo.geojson import track_to_geojson

    samples = Path(__file__).resolve().parents[1] / "samples"
    track = build_track(samples / "air3" / "clip.SRT")
    fps = build_footprints(track, interval=0.0)
    gj = track_to_geojson(track, footprints=fps)
    polys = [f for f in gj["features"]
             if f["geometry"] and f["geometry"]["type"] == "Polygon"]
    assert polys, "expected at least one footprint polygon"
    assert polys[0]["properties"]["kind"] == "footprint"
    assert "agl" in polys[0]["properties"]


def test_geojson_without_footprints_unchanged():
    from pathlib import Path
    from dji_metadata_embedder.geo.track import build_track
    from dji_metadata_embedder.geo.geojson import track_to_geojson

    samples = Path(__file__).resolve().parents[1] / "samples"
    track = build_track(samples / "air3" / "clip.SRT")
    gj = track_to_geojson(track)
    assert not [f for f in gj["features"]
                if f["geometry"] and f["geometry"]["type"] == "Polygon"]
