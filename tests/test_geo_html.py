import json
import re
from pathlib import Path

from dji_metadata_embedder.geo.html_viewer import (
    convert_to_html,
    track_to_html,
)
from dji_metadata_embedder.geo.track import Track, build_track

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
CLIP = SAMPLES / "air3S" / "clip.SRT"

# Pull the JSON out of <script type="application/json" id="flight-data">...</script>
_DATA_RE = re.compile(
    r'<script type="application/json" id="flight-data">(.*?)</script>',
    re.DOTALL,
)


def _embedded_geojson(html: str) -> dict:
    match = _DATA_RE.search(html)
    assert match, "flight-data script block not found"
    return json.loads(match.group(1))


def test_html_embeds_wellformed_geojson():
    html = track_to_html(build_track(CLIP))
    data = _embedded_geojson(html)
    assert data["type"] == "FeatureCollection"
    points = [f for f in data["features"] if f["geometry"]
              and f["geometry"]["type"] == "Point"]
    assert len(points) == 5
    assert points[0]["properties"]["abs_alt"] == 302.208


def test_html_is_self_contained_document():
    html = track_to_html(build_track(CLIP))
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert 'id="map"' in html
    assert "leaflet@1.9.4" in html  # pinned CDN version


def test_html_escapes_script_close_in_data():
    # No literal "</script>" may appear inside the embedded JSON, or it would
    # break out of the data block. The serializer escapes "<" to "<".
    html = track_to_html(build_track(CLIP))
    data_block = _DATA_RE.search(html).group(1)
    assert "</script>" not in data_block.lower()


def test_empty_track_still_renders_valid_document():
    html = track_to_html(Track(name="empty", points=[]))
    assert html.lstrip().startswith("<!DOCTYPE html>")
    data = _embedded_geojson(html)
    # Null-geometry line feature, no points.
    assert data["features"][0]["geometry"] is None
