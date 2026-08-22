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


# Single-flight playback (#327): with several flights, "play" must animate one
# selected flight by default, not every flight at once. A selector switches the
# active flight and offers an "All flights" opt-in for the #267 compare mode.
# (The selector is built in the browser from the constant app JS, so these
# assert the mechanism is present; the runtime behaviour is verified manually.)


def test_html_playback_has_flight_selector():
    html = flights_to_html(TRACKS, title="t")
    assert "pb-flight" in html          # the flight <select> in the playback bar
    assert "All flights" in html        # opt-in #267 compare mode


def test_html_playback_scopes_to_selected_flight():
    html = flights_to_html(TRACKS, title="t")
    # The animator drives only the selected flight(s) and scopes the timeline to
    # that flight's own duration — not the global maxT over every flight.
    assert "selRuns" in html
    assert "selMax" in html


def test_html_playback_selector_only_for_multiple_flights():
    html = flights_to_html(TRACKS, title="t")
    # A lone flight needs no selector; the widget is gated behind >1 run.
    assert "runs.length > 1" in html


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


# Airspace overlay (#413, PR 2): flights_to_html/write_flights_html gain an
# airspace_json param that embeds the Task 1 overlay dict as a second data
# block plus the zone-drawing JS. None (the default) must leave the map
# byte-identical to before this feature existed.


def _mini_track(name="F1"):
    from dji_metadata_embedder.geo.track import Track, TrackPoint
    return Track(name=name, points=[
        TrackPoint(lat=49.6, lon=6.1, alt=300.0, timestamp="00:00:00"),
        TrackPoint(lat=49.61, lon=6.11, alt=310.0, timestamp="00:00:01"),
    ])


_OVERLAY = {
    "zones": [{
        "id": "LU-1", "name": "Test zone", "restriction": "PROHIBITED",
        "lower": None, "upper": "120 m AGL", "applicability": [],
        "polygons": [[(6.0, 49.5), (6.2, 49.5), (6.2, 49.7), (6.0, 49.5)]],
        "source": {"feed": "Feed", "license": "CC0", "fetched": "2026-07-30T10:00:00Z"},
        "entered": [{"flight": "F1", "entry_utc": "2026-07-30 12:00:00 UTC",
                     "exit_utc": "2026-07-30 12:00:02 UTC",
                     "max_rel_alt_m": 80.0, "max_amsl_m": 300.0,
                     "time_note": None}],
    }],
    "notes": ["Airspace: Feed, fetched 2026-07-30T10:00:00Z"],
    "covered": True,
}


def test_no_airspace_json_means_no_airspace_bytes():
    from dji_metadata_embedder.geo.flightmap_html import flights_to_html
    html = flights_to_html([_mini_track()], "t")
    assert "airspace" not in html.lower()


def test_airspace_popup_renders_activation_text_as_published_not_evaluated():
    # #503: the popup shows a zone's activation status/schedule text
    # verbatim, labelled as published information the record did not
    # evaluate — and nothing at all for zones without it.
    from dji_metadata_embedder.geo.flightmap_html import flights_to_html
    html = flights_to_html([_mini_track()], "t", airspace_json=_OVERLAY)
    assert "if (z.activation && z.activation.length)" in html
    assert "activation (published, not evaluated): " in html
    assert "z.activation.map(esc).join('; ')" in html


def test_airspace_json_embeds_block_layer_and_note():
    from dji_metadata_embedder.geo.flightmap_html import flights_to_html
    html = flights_to_html([_mini_track()], "t", airspace_json=_OVERLAY)
    assert 'id="airspace-data"' in html
    assert "Airspace zones" in html
    assert "airspace-note" in html
    assert "zonePopupHtml" in html


def test_airspace_popup_states_the_edition_date_only_when_published():
    # #502: the popup JS renders "effective <date>" from the zone's
    # source block when present and nothing when the feed is undated.
    from dji_metadata_embedder.geo.flightmap_html import flights_to_html
    html = flights_to_html([_mini_track()], "t", airspace_json=_OVERLAY)
    assert "if (z.source.effective) html += `<br>effective " in html
    assert "`<br>fetched ${esc(z.source.fetched)}`" in html


def test_airspace_json_escapes_script_breakout():
    from dji_metadata_embedder.geo.flightmap_html import flights_to_html
    evil = dict(_OVERLAY)
    evil["notes"] = ["</script><script>alert(1)</script>"]
    html = flights_to_html([_mini_track()], "t", airspace_json=evil)
    start = html.index('id="airspace-data"')
    end = html.index("</script>", start)
    assert "<script" not in html[start:end]
