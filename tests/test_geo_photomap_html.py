import json
import re

from dji_metadata_embedder.geo.photomap import PhotoPoint
from dji_metadata_embedder.geo.photomap_html import photos_to_html, write_photos_html

POINTS = [
    PhotoPoint(lat=60.170278, lon=24.952222, alt=95.3, name="church1.jpg",
               timestamp="2026-06-15 12:30:45", model="FC8482", iso=100,
               exposure=0.001, fnum=1.7),
    PhotoPoint(lat=60.173047, lon=24.92515, alt=88.1, name="church2.jpg",
               thumbnail_b64="/9j/THUMB2"),
]

_DATA_RE = re.compile(
    r'<script type="application/json" id="photo-data">(.*?)</script>',
    re.DOTALL,
)


def _embedded_geojson(html: str) -> dict:
    match = _DATA_RE.search(html)
    assert match, "photo-data script block not found"
    return json.loads(match.group(1))


def test_html_embeds_geojson_with_thumbnails():
    html = photos_to_html(POINTS, title="Finnish churches")
    data = _embedded_geojson(html)
    assert data["type"] == "FeatureCollection"
    by_name = {f["properties"]["name"]: f for f in data["features"]}
    assert by_name["church2.jpg"]["properties"]["thumb"] == "/9j/THUMB2"
    assert "thumb" not in by_name["church1.jpg"]["properties"]


def test_html_is_self_contained_document_with_pinned_libs():
    html = photos_to_html(POINTS, title="Finnish churches")
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert 'id="map"' in html
    assert "leaflet@1.9.4" in html
    assert "leaflet.markercluster@1.5.3" in html
    # All five remote assets carry SRI pins: leaflet css+js, cluster js+2css.
    assert html.count('integrity="sha256-') == 5
    assert "Finnish churches" in html


def test_html_escapes_script_close_in_data():
    evil = [PhotoPoint(lat=1.0, lon=2.0, alt=0.0, name="x</script>y.jpg")]
    html = photos_to_html(evil, title="t")
    data_block = _DATA_RE.search(html).group(1)
    assert "</script>" not in data_block.lower()
    assert json.loads(data_block)["features"][0]["properties"]["name"] == "x</script>y.jpg"


def test_html_popup_js_escapes_text_fields():
    # Popup text (name/timestamp/camera) is inserted via the esc() helper so a
    # hostile filename cannot inject HTML into the popup.
    html = photos_to_html(POINTS, title="t")
    for applied in ("esc(p.thumb", "esc(p.name", "esc(p.timestamp", "esc(p.camera"):
        assert applied in html


def test_html_uses_cluster_bulk_path():
    html = photos_to_html(POINTS, title="t")
    assert "chunkedLoading: true" in html
    assert "cluster.addLayers(markers)" in html


def test_html_empty_points_still_valid_document():
    html = photos_to_html([], title="t")
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert _embedded_geojson(html)["features"] == []


def test_html_title_is_escaped():
    html = photos_to_html(POINTS, title="<script>x")
    assert "<script>x" not in html


def test_write_photos_html(tmp_path):
    out = tmp_path / "photomap.html"
    result = write_photos_html(POINTS, out, title="t")
    assert result == out
    assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")


def test_html_no_links_by_default():
    data = _embedded_geojson(photos_to_html(POINTS, title="t"))
    assert all("link" not in f["properties"] for f in data["features"])


def test_html_link_base_embeds_link_properties():
    html = photos_to_html(POINTS, title="t", link_base="")
    data = _embedded_geojson(html)
    by_name = {f["properties"]["name"]: f for f in data["features"]}
    assert by_name["church1.jpg"]["properties"]["link"] == "church1.jpg"


def test_html_popup_anchor_is_escaped_and_noopener():
    html = photos_to_html(POINTS, title="t", link_base="")
    # The href goes through the esc() helper and opens in a new tab without
    # window.opener access.
    assert "esc(p.link" in html
    assert 'target="_blank" rel="noopener"' in html


PANO_POINTS = POINTS + [
    PhotoPoint(lat=60.1686, lon=24.9539, alt=12.0, name="pano.jpg",
               thumbnail_b64="/9j/PANO", is_pano=True),
]


def test_html_no_pannellum_without_panos():
    html = photos_to_html(POINTS, title="t", link_base="")
    assert "pannellum" not in html
    assert 'id="pano-overlay"' not in html


def test_html_no_pannellum_without_links():
    # A pano without --link-originals has nothing the viewer could load.
    html = photos_to_html(PANO_POINTS, title="t")
    assert "pannellum" not in html
    data = _embedded_geojson(html)
    assert all("pano" not in f["properties"] for f in data["features"])


def test_html_pano_with_links_embeds_pinned_viewer():
    html = photos_to_html(PANO_POINTS, title="t", link_base="")
    assert "pannellum@2.5.6/build/pannellum.js" in html
    assert "pannellum@2.5.6/build/pannellum.css" in html
    # 5 existing SRI pins (leaflet css+js, cluster js+2css) + pannellum css+js.
    assert html.count('integrity="sha256-') == 7
    assert 'id="pano-overlay"' in html
    assert 'id="pano-close"' in html
    by_name = {
        f["properties"]["name"]: f["properties"]
        for f in _embedded_geojson(html)["features"]
    }
    assert by_name["pano.jpg"]["pano"] is True
    assert "pano" not in by_name["church1.jpg"]


def test_html_pano_popup_keeps_plain_fallback_link():
    html = photos_to_html(PANO_POINTS, title="t", link_base="")
    # Pano popups: main click opens the viewer, plus an escaped plain link
    # ("open original") as fallback; Escape and the close button tear down.
    assert 'class="pano-open"' in html
    assert "open original" in html
    assert "pannellum.viewer(" in html
    assert "panoViewer.destroy()" in html
