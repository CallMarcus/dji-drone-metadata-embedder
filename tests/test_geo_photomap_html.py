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
    assert "photoCluster.addLayers(photoMarkers)" in html
    assert "panoCluster.addLayers(panoMarkers)" in html


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


def _tooltip_builder(html: str) -> str:
    match = re.search(r"function buildTooltip\(f\) \{(.*?)\n\}", html, re.DOTALL)
    assert match, "buildTooltip function not found"
    return match.group(1)


def test_html_markers_bind_hover_tooltip():
    # Hover preview (issue #273): every marker gets a sticky tooltip so the
    # map can be skimmed without clicking each pin.
    html = photos_to_html(POINTS, title="t")
    assert "bindTooltip(" in html
    assert "sticky: true" in html


def test_html_tooltip_shows_thumbnail_and_escaped_name():
    # The tooltip carries the EXIF thumbnail plus the filename; the filename
    # goes through the esc() helper so hostile names cannot inject HTML.
    body = _tooltip_builder(photos_to_html(POINTS, title="t"))
    assert "esc(p.thumb" in body
    assert "esc(p.name" in body
    assert "data:image/jpeg;base64," in body


def test_html_tooltip_degrades_without_thumbnail():
    # Points without a thumb fall back to a filename-only tooltip: the <img>
    # sits inside an `if (p.thumb)` guard while the name is unconditional.
    body = _tooltip_builder(photos_to_html(POINTS, title="t"))
    assert "if (p.thumb)" in body
    assert "esc(p.name" in body


def test_html_tooltip_css_limits_thumbnail_size():
    html = photos_to_html(POINTS, title="t")
    assert ".photo-tooltip img" in html
    assert "max-width: 160px" in html


def test_html_tooltip_does_not_replace_click_popup():
    # The hover preview is additive: markers still bind the full click popup.
    html = photos_to_html(POINTS, title="t")
    assert "bindPopup(" in html
    assert "bindTooltip(" in html


PANO_POINTS = POINTS + [
    PhotoPoint(lat=60.1686, lon=24.9539, alt=12.0, name="pano.jpg",
               thumbnail_b64="/9j/PANO", is_pano=True),
]


def test_html_no_pannellum_without_panos():
    html = photos_to_html(POINTS, title="t", link_base="")
    assert "pannellum" not in html
    assert 'id="pano-overlay"' not in html


def test_html_no_pannellum_without_links():
    # A pano without --link-originals has nothing the viewer could load, but
    # the pano flag itself is still embedded for marker styling (#283).
    html = photos_to_html(PANO_POINTS, title="t")
    assert "pannellum" not in html
    by_name = {
        f["properties"]["name"]: f["properties"]
        for f in _embedded_geojson(html)["features"]
    }
    assert by_name["pano.jpg"]["pano"] is True
    assert all("link" not in p for p in by_name.values())


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


def test_html_pano_file_protocol_shows_help_instead_of_viewer():
    html = photos_to_html(PANO_POINTS, title="t", link_base="")
    # Maps opened from disk cannot feed WebGL: openPano branches on the
    # protocol and shows guidance instead of launching Pannellum.
    assert "location.protocol === 'file:'" in html
    assert "pano-blocked" in html
    assert "--serve" in html
    assert "open original" in html


def test_html_pano_container_reset_on_every_open():
    html = photos_to_html(PANO_POINTS, title="t", link_base="")
    # The container's content is set on each open so a stale file:// message
    # can never linger under a later Pannellum instance.
    assert "panoContainer.innerHTML = ''" in html


def test_html_file_protocol_help_absent_without_panos():
    html = photos_to_html(POINTS, title="t", link_base="")
    assert "pano-blocked" not in html
    assert "location.protocol" not in html


# Per-type markers (issue #283): photos and 360° panoramas get distinct,
# individually toggleable markers so mixed folders stay readable.


def test_html_markers_use_type_colored_divicons():
    html = photos_to_html(PANO_POINTS, title="t")
    assert "L.divIcon" in html
    # Shared dot CSS plus one color class per type; the JS picks the icon
    # from the feature's pano property.
    assert ".photo-pin" in html
    assert "pin-photo" in html and "pin-pano" in html


def test_html_type_pure_cluster_groups():
    # One markerClusterGroup per type, so cluster blobs never mix types and
    # each type can be toggled as a whole.
    html = photos_to_html(PANO_POINTS, title="t")
    assert "photoCluster.addLayers(photoMarkers)" in html
    assert "panoCluster.addLayers(panoMarkers)" in html


def test_html_layer_control_gated_on_both_types():
    # The expanded layer control doubles as the legend; it only appears when
    # the folder actually mixes types (runtime check on the embedded data).
    html = photos_to_html(PANO_POINTS, title="t")
    assert "L.control.layers" in html
    assert "collapsed: false" in html
    assert "Photos" in html and "panoramas" in html
    assert "photoMarkers.length && panoMarkers.length" in html


def test_html_both_cluster_types_tinted():
    # Both groups override markercluster's default color ramp: its "large"
    # orange is nearly identical to the pano tint, so photo clusters are
    # tinted blue and pano clusters orange to keep the legend truthful.
    html = photos_to_html(PANO_POINTS, title="t")
    assert "iconCreateFunction" in html
    assert ".photo-cluster div" in html
    assert ".pano-cluster div" in html


def test_html_pin_colors_defined_once():
    # The two type colors live in CSS custom properties; every other use
    # (pins, cluster tints) derives from them, so a recolor is a 1-line edit.
    html = photos_to_html(PANO_POINTS, title="t")
    assert "--pin-photo:" in html
    assert "--pin-pano:" in html
    assert "color-mix(" in html
    assert "rgba(246" not in html  # no parallel hand-converted copy


def test_html_pano_cluster_anchor_offset_against_occlusion():
    # Coincident photo and pano clusters (routine under --redact fuzz, which
    # rounds both types to the same 3-decimal grid) must not fully occlude
    # each other: the pano blob anchors slightly off-center so the photo blob
    # underneath stays visible and clickable.
    html = photos_to_html(PANO_POINTS, title="t")
    assert "PANO_CLUSTER_ANCHOR" in html
