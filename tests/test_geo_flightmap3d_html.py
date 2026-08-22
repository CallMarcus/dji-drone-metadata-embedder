import json
import re

from dji_metadata_embedder.geo.flightmap3d_html import (
    flights_to_3d_html,
    write_flights_3d_html,
)
from dji_metadata_embedder.geo.track import Track, TrackPoint


def _track(name="DJI_0001", lat=10.0, lon=20.0, n=2):
    pts = [
        TrackPoint(
            lat=lat + i * 0.001,
            lon=lon + i * 0.001,
            alt=5.0 + i,
            timestamp=f"00:00:{i:02d},000",
        )
        for i in range(n)
    ]
    return Track(name=name, points=pts)


def _embedded_data(html: str) -> dict:
    m = re.search(
        r'<script type="application/json" id="flight-data">\s*(.*?)\s*</script>',
        html, re.S,
    )
    assert m, "embedded data block missing"
    return json.loads(m.group(1))


def test_3d_html_embeds_one_feature_per_flight():
    html = flights_to_3d_html([_track("A"), _track("B", lat=11.0)], "trip")
    data = _embedded_data(html)
    assert len(data["features"]) == 2


def test_3d_html_pins_maplibre_with_sri():
    html = flights_to_3d_html([_track()], "t")
    assert 'src="https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.js" integrity="sha256-' in html
    assert 'href="https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.css" integrity="sha256-' in html
    assert "leaflet" not in html.lower()


def test_3d_html_uses_mapterhorn_terrain_with_attribution():
    html = flights_to_3d_html([_track()], "t")
    assert "https://tiles.mapterhorn.com/tilejson.json" in html
    assert "raster-dem" in html
    assert "OpenStreetMap contributors" in html
    assert "Mapterhorn" in html


def test_3d_html_escapes_script_close_in_data():
    t = _track(name="</script><script>alert(1)")
    html = flights_to_3d_html([t], "t")
    assert "</script><script>alert(1)" not in html
    assert _embedded_data(html)["features"][0]["properties"]["name"].startswith("</script>")


def test_3d_html_title_is_escaped():
    html = flights_to_3d_html([_track()], "<b>trip</b>")
    assert "<b>trip</b>" not in html
    assert "&lt;b&gt;trip&lt;/b&gt;" in html


def test_3d_single_fix_flight_survives():
    html = flights_to_3d_html([_track(n=1)], "t")
    data = _embedded_data(html)
    assert data["features"][0]["geometry"]["type"] == "Point"
    assert "circle" in html  # degenerate flights render as a circle layer


def test_3d_html_has_degradation_paths():
    html = flights_to_3d_html([_track()], "t")
    assert "Terrain tiles unavailable" in html   # flat-view banner text
    assert "WebGL" in html                        # no-WebGL fallback message


def test_3d_html_has_flight_toggle_panel():
    html = flights_to_3d_html([_track()], "t")
    assert "flights-panel" in html


def test_3d_html_caps_the_panel_width_and_offers_a_collapse_toggle():
    # #542: the panel has no natural width limit, and airspace notes are
    # long single sentences, so without a cap it stretched to the width
    # of the longest note. The toggle is a <button>, never a checkbox --
    # the checkboxes in this panel are the flight rows.
    html = flights_to_3d_html([_track()], "t")
    assert "max-width: min(360px, 70vw)" in html
    assert "toggle.id = 'panel-toggle'" in html
    assert "toggle.type = 'button'" in html
    assert ".flights-panel.collapsed > :not(.panel-head) { display: none; }" in html


def test_3d_html_does_not_render_at_altitude():
    # Spec amendment: draped tracks only — line geometry never anchors at
    # elevation. Ghost Camera (#372) legitimately calls
    # queryTerrainElevation for camera placement (see
    # tests/browser/test_flightmap_ghost.py); that's a separate concern
    # from how track *lines* render, which this still guards.
    html = flights_to_3d_html([_track()], "t")
    assert "line-z-offset" not in html


def test_3d_empty_tracks_still_valid_document():
    html = flights_to_3d_html([], "t")
    assert html.startswith("<!DOCTYPE html>")
    assert _embedded_data(html)["features"] == []


def test_3d_html_carries_the_sculpture_layers():
    html = flights_to_3d_html([_track()], "trip")
    assert "sculpt-" in html
    assert "fill-extrusion-vertical-gradient" in html
    assert "sculpture-toggle" in html


def test_template_carries_the_gaze_and_playback_app():
    html = flights_to_3d_html([_track()], "trip")
    for needle in ("function gazeRing(", "function beamFor(",
                   "function gazeLookup(", "'gaze-fill'", "'beam-ray'",
                   "'gaze-hits-line'", "id: 'gaze-cursor-dot'",
                   "pb-play", "pb-slider", "GAZE_FALLBACK_HFOV"):
        assert needle in html, needle


def test_template_carries_the_crossfade_app():
    html = flights_to_3d_html([_track()], "trip")
    for needle in ("function mountCrossfade(", "function renderCrossfade(",
                   "function syncCrossfadePlayback(", "v.id = 'ghost-video'",
                   "ghost-blend", "CROSSFADE_MAX_RATE"):
        assert needle in html, needle


def test_gaze_js_lives_in_its_own_module_and_is_spliced():
    """#383: the gaze/playback block moved to flightmap3d_gaze_js.GAZE_JS,
    spliced over a __GAZE_JS__ placeholder the same way __SHARED_JS__ is.
    app_js reaches the template as a .format() VALUE, so no brace doubling."""
    from dji_metadata_embedder.geo.flightmap3d_gaze_js import GAZE_JS
    from dji_metadata_embedder.geo.flightmap3d_html import _APP_JS

    assert "__GAZE_JS__" in _APP_JS
    assert "function gazePasses" in GAZE_JS
    assert "function gazePasses" not in _APP_JS
    html = flights_to_3d_html([_track()], "trip")
    assert "function gazePasses" in html
    assert "__GAZE_JS__" not in html


def test_emitted_js_is_ascii_only():
    """The emitted JS's own convention is \\uXXXX escapes; a literal multiply
    sign and em dash predating the arc relied on <meta charset> surviving
    every copy and serve path instead (#383)."""
    from dji_metadata_embedder.geo.flightmap3d_gaze_js import GAZE_JS
    from dji_metadata_embedder.geo.flightmap3d_html import _APP_JS

    bad = sorted({c for c in _APP_JS + GAZE_JS if not c.isascii()})
    assert bad == [], f"non-ASCII in emitted JS: {bad!r}"


def test_write_flights_3d_html(tmp_path):
    out = tmp_path / "flightmap-3d.html"
    result = write_flights_3d_html([_track()], out, "trip")
    assert result == out
    assert out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
