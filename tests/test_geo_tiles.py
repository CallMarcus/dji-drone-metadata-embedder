import pytest

from dji_metadata_embedder.geo.tiles import (
    DEFAULT_TILE_STYLE,
    TILE_STYLES,
    tile_layer_js,
)


def test_default_style_is_a_known_style():
    assert DEFAULT_TILE_STYLE in TILE_STYLES


def test_every_style_is_a_complete_leaflet_layer():
    for name, ts in TILE_STYLES.items():
        assert ts.url.startswith("https://"), name
        # Leaflet template placeholders must survive into the page verbatim.
        for placeholder in ("{z}", "{x}", "{y}"):
            assert placeholder in ts.url, name
        # All styles are OSM-data renders; the ODbL credit is mandatory.
        assert "OpenStreetMap" in ts.attribution, name
        assert 16 <= ts.max_zoom <= 21, name


def test_tile_layer_js_emits_the_style_verbatim():
    js = tile_layer_js("opentopomap")
    ts = TILE_STYLES["opentopomap"]
    assert js.startswith('L.tileLayer("https://')
    assert ts.url in js
    assert f"maxZoom: {ts.max_zoom}" in js
    assert "OpenTopoMap" in js
    assert js.endswith(".addTo(map);")


def test_tile_layer_js_unknown_style_raises():
    # The CLI's click.Choice guards this; a KeyError here means a programming
    # error, not bad user input.
    with pytest.raises(KeyError):
        tile_layer_js("watercolor")
