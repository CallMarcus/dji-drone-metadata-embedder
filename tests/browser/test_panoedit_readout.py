"""Saved-vs-live numeric readout (#493) in a real headless Chromium.

The editor's readout already shows the live heading/pitch/hFOV; #493 adds
the file's saved opening values beside them, so a view can be lined up
deliberately (e.g. matching headings across panos taken from the same spot)
instead of eyeballed.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

pytest.importorskip("playwright")

from .test_panoedit_editor import _make_pano, _serve  # noqa: E402

pytestmark = pytest.mark.browser

needs_exiftool = pytest.mark.skipif(
    shutil.which("exiftool") is None, reason="ExifTool not installed")


@needs_exiftool
def test_readout_shows_saved_values_beside_live_ones(
        tmp_path, page, monkeypatch):
    monkeypatch.delenv("DJIEMBED_EXIFTOOL_PATH", raising=False)
    pano = tmp_path / "saved.jpg"
    _make_pano(pano, pose=10.0)
    subprocess.run(
        ["exiftool", "-overwrite_original", "-n",
         "-XMP-GPano:InitialViewHeadingDegrees=40",
         "-XMP-GPano:InitialViewPitchDegrees=-5",
         "-XMP-GPano:InitialHorizontalFOVDegrees=90", str(pano)],
        check=True, capture_output=True)
    httpd, url = _serve(tmp_path, page)
    try:
        page.goto(url)
        page.wait_for_function("window.__panoReady === true")
        # The saved line shows compass values: the 40/-5/90 that were written,
        # not the pose-relative yaw the viewer runs on.
        readout = page.inner_text("#readout")
        assert "Saved" in readout
        assert "40.0" in readout and "-5.0" in readout and "90.0" in readout

        # Drag away: the live line moves, the saved line stays put.
        box = page.locator("#viewer").bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.mouse.move(cx, cy)
        page.mouse.down()
        page.mouse.move(cx - 160, cy, steps=10)
        page.mouse.up()
        # Stored yaw is heading - pose = 30; wait until the camera has moved.
        page.wait_for_function("Math.abs(window.__viewer.getYaw() - 30) > 5")
        readout = page.inner_text("#readout")
        assert "Saved" in readout and "40.0" in readout
    finally:
        httpd.shutdown()


@needs_exiftool
def test_readout_stays_plain_without_a_saved_view(tmp_path, page, monkeypatch):
    # No saved view means nothing to show: the readout keeps its old shape
    # rather than inventing a "saved" row from Pannellum's defaults.
    monkeypatch.delenv("DJIEMBED_EXIFTOOL_PATH", raising=False)
    _make_pano(tmp_path / "plain.jpg", pose=0.0)
    httpd, url = _serve(tmp_path, page)
    try:
        page.goto(url)
        page.wait_for_function("window.__panoReady === true")
        assert "Saved" not in page.inner_text("#readout")
    finally:
        httpd.shutdown()
