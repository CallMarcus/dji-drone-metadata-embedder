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


def test_page_reports_load_failures_honestly():
    # Pannellum blames the file for every load failure ("could not be
    # accessed"), which sent a field tester hunting a corrupt image when
    # his GPU was the problem (#471). The page must say what it knows.
    html = build_editor_page("tok123", max_width=6000)
    assert 'viewer.on("error", showPanoError)' in html
    assert '"maxWidth": 6000' in html
    # The overlay names the panorama's real dimensions and a next step.
    assert 'f.width + " x " + f.height' in html
    assert "--max-width" in html


def test_page_carries_the_pillow_hint_only_when_it_applies():
    with_pillow = build_editor_page("t", max_width=6000, renditions=True,
                                    hint="install Pillow")
    without = build_editor_page("t", max_width=6000, renditions=False,
                                hint="install Pillow")
    assert "install Pillow" not in with_pillow
    assert "install Pillow" in without


def test_caption_overlays_have_a_backdrop():
    # Field report (2026-08-09): the counter and the backup note float over
    # the panorama and were bare grey text — unreadable against bright
    # skies. Both need the readout's backdrop-box treatment.
    html = build_editor_page("tok123")
    for elem in ("#counter", "#note"):
        rule = html.split(elem, 1)[1].split("}", 1)[0]
        assert "background: rgba(0,0,0" in rule, elem
