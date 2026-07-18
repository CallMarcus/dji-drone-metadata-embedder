import json
import re
from datetime import datetime

from dji_metadata_embedder.geo.flightmap_html import flights_to_html, write_flights_html
from dji_metadata_embedder.geo.track import Track, TrackPoint

TRACKS = [
    Track(name="DJI_0001", points=[
        TrackPoint(lat=10.0, lon=20.0, alt=5.0, timestamp="00:00:00,000",
                   utc=datetime(2026, 6, 15, 12, 0, 0)),
        TrackPoint(lat=10.001, lon=20.001, alt=6.5, timestamp="00:00:01,000",
                   utc=datetime(2026, 6, 15, 12, 1, 0)),
    ]),
    Track(name="DJI_0002", points=[
        TrackPoint(lat=11.0, lon=21.0, alt=7.0, timestamp="00:00:00,000"),
        TrackPoint(lat=11.001, lon=21.001, alt=8.0, timestamp="00:00:01,000"),
    ]),
]

_DATA_RE = re.compile(
    r'<script type="application/json" id="flight-data">(.*?)</script>',
    re.DOTALL,
)


def _embedded_geojson(html: str) -> dict:
    match = _DATA_RE.search(html)
    assert match, "flight-data script block not found"
    return json.loads(match.group(1))


def test_html_embeds_one_feature_per_flight():
    html = flights_to_html(TRACKS, title="Summer flights")
    data = _embedded_geojson(html)
    names = [f["properties"]["name"] for f in data["features"]]
    assert names == ["DJI_0001", "DJI_0002"]
    assert all(f["geometry"]["type"] == "LineString" for f in data["features"])


def test_html_is_self_contained_document_with_pinned_libs():
    html = flights_to_html(TRACKS, title="Summer flights")
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert 'id="map"' in html
    assert "leaflet@1.9.4" in html
    # Both remote assets (leaflet css + js) carry SRI pins.
    assert html.count('integrity="sha256-') == 2
    assert "Summer flights" in html


def test_html_escapes_script_close_in_data():
    evil = [Track(name="x</script>y", points=[
        TrackPoint(lat=1.0, lon=2.0, alt=3.0, timestamp="00:00:00,000")])]
    html = flights_to_html(evil, title="t")
    data_block = _DATA_RE.search(html).group(1)
    assert "</script>" not in data_block.lower()
    assert json.loads(data_block)["features"][0]["properties"]["name"] == "x</script>y"


def test_html_popup_js_escapes_text_fields():
    # Popup text (name/start/segments) is inserted via the esc() helper so a
    # hostile filename cannot inject HTML into the popup or the layer control.
    html = flights_to_html(TRACKS, title="t")
    for applied in ("esc(p.name", "esc(p.start", "esc(p.segments[0]"):
        assert applied in html


def test_html_embeds_segments_for_joined_flights():
    joined = [Track(name="DJI_0001", segments=["DJI_0001", "DJI_0002"], points=[
        TrackPoint(lat=1.0, lon=2.0, alt=3.0, timestamp="00:00:00,000"),
        TrackPoint(lat=1.001, lon=2.001, alt=4.0, timestamp="00:00:01,000"),
    ])]
    html = flights_to_html(joined, title="t")
    props = _embedded_geojson(html)["features"][0]["properties"]
    assert props["segments"] == ["DJI_0001", "DJI_0002"]


def test_html_popup_neutral_join_wording():
    # Joins also catch quick stop/start re-records, so the popup must not
    # claim the files were size-splits.
    html = flights_to_html(TRACKS, title="t")
    assert "recorded across" in html
    assert "size-split" not in html


def test_html_popup_prefers_relative_height_and_readable_ranges():
    # The popup JS must show rel-alt height when present and join ranges with
    # " to " so negative abs altitudes don't render as "-125.6--66.8 m".
    html = flights_to_html(TRACKS, title="t")
    assert "p.height_min" in html
    assert "m above takeoff" in html
    assert "}–${" not in html  # old en-dash range join


def test_html_embeds_height_properties_from_rel_alt():
    tracks = [Track(name="f", points=[
        TrackPoint(lat=1.0, lon=2.0, alt=-125.6, timestamp="00:00:00,000",
                   rel_alt=1.2),
        TrackPoint(lat=1.001, lon=2.001, alt=-66.8, timestamp="00:00:01,000",
                   rel_alt=96.4),
    ])]
    props = _embedded_geojson(flights_to_html(tracks, title="t"))["features"][0][
        "properties"
    ]
    assert (props["height_min"], props["height_max"]) == (1.2, 96.4)


def test_html_draws_tracks_with_layer_control():
    html = flights_to_html(TRACKS, title="t")
    assert "L.polyline" in html
    assert "L.control.layers" in html
    assert "PALETTE" in html


# Flight playback (#267): a hand-rolled requestAnimationFrame animator moves
# a marker along each track, driven by the embedded per-point times.


def test_html_embeds_playback_times():
    data = _embedded_geojson(flights_to_html(TRACKS, title="t"))
    assert data["features"][0]["properties"]["times_s"] == [0.0, 60.0]
    assert data["features"][1]["properties"]["times_s"] == [0.0, 1.0]


def test_html_has_playback_control_without_new_dependencies():
    html = flights_to_html(TRACKS, title="t")
    assert "requestAnimationFrame" in html
    assert "playback" in html
    # Hand-rolled animator, not a plugin: the SRI-pinned asset count is
    # unchanged (leaflet css + js only).
    assert html.count('integrity="sha256-') == 2


def test_html_empty_tracks_still_valid_document():
    html = flights_to_html([], title="t")
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert _embedded_geojson(html)["features"] == []


def test_html_title_is_escaped():
    html = flights_to_html(TRACKS, title="<script>x")
    assert "<script>x" not in html


def test_write_flights_html(tmp_path):
    out = tmp_path / "flightmap.html"
    result = write_flights_html(TRACKS, out, title="t")
    assert result == out
    assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")


# Basemap styles (#311): the tile layer is generated from geo.tiles; the
# default stays the standard OSM render.


def test_html_default_tile_style_is_osm():
    html = flights_to_html(TRACKS, title="t")
    assert "tile.openstreetmap.org" in html
    assert "__TILE_LAYER__" not in html


def test_html_alternate_tile_style_swaps_provider():
    html = flights_to_html(TRACKS, title="t", tile_style="opentopomap")
    assert "tile.opentopomap.org" in html
    assert "OpenTopoMap" in html
    assert "maxZoom: 17" in html
    assert "tile.openstreetmap.org" not in html
    assert "__TILE_LAYER__" not in html
