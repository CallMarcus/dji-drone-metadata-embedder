"""Static contract tests for the panoedit editor page."""
from __future__ import annotations

from dji_metadata_embedder.geo.panoedit_html import build_editor_page
from dji_metadata_embedder.geo.photomap_html import (
    _PANNELLUM_CSS_SRI,
    _PANNELLUM_JS_SRI,
    _PANNELLUM_VERSION,
)


def test_page_pins_pannellum_with_sri():
    html = build_editor_page("tok123")
    assert f"pannellum@{_PANNELLUM_VERSION}" in html
    assert _PANNELLUM_CSS_SRI in html and _PANNELLUM_JS_SRI in html


def test_page_embeds_token_and_hooks():
    html = build_editor_page("tok123")
    assert '"tok123"' in html
    assert "__panoReady" in html and "__viewer" in html
    assert "/api/list" in html and "/api/save" in html
    # The save math: compass heading from pose + yaw, normalized.
    assert "pose + " in html and "% 360" in html
    # Originals note (save semantics decision).
    assert "_original" in html


def test_page_token_is_json_escaped():
    html = build_editor_page('</script><script>alert(1)')
    assert "</script><script>alert(1)" not in html
