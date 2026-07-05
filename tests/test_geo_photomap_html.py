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
