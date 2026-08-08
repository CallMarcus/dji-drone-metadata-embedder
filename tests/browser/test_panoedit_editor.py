"""End-to-end editor test: a real panoedit server, real exiftool writes,
headless Chromium driving the page. Waits are on renderedness
(window.__panoReady), never on element existence."""
from __future__ import annotations

import shutil
import subprocess
import threading

import pytest

pytest.importorskip("playwright")
from PIL import Image  # noqa: E402

from dji_metadata_embedder.geo import panoedit as pe  # noqa: E402
from dji_metadata_embedder.geo.panoedit_html import build_editor_page  # noqa: E402

from .conftest import _ASSET_RE, _fetch_asset  # noqa: E402

needs_exiftool = pytest.mark.skipif(
    shutil.which("exiftool") is None, reason="ExifTool not installed")


def _make_pano(path, pose: float) -> None:
    im = Image.new("RGB", (256, 128), (30, 60, 200))
    for x in range(128, 256):
        for y in range(128):
            im.putpixel((x, y), (200, 60, 30))
    im.save(path, "JPEG")
    subprocess.run(
        ["exiftool", "-overwrite_original",
         "-XMP-GPano:ProjectionType=equirectangular",
         f"-XMP-GPano:PoseHeadingDegrees={pose}", str(path)],
        check=True, capture_output=True)


@pytest.fixture
def editor(tmp_path, page, monkeypatch):
    monkeypatch.delenv("DJIEMBED_EXIFTOOL_PATH", raising=False)
    _make_pano(tmp_path / "a.jpg", pose=90.0)
    _make_pano(tmp_path / "b.jpg", pose=0.0)
    httpd, url = pe.make_editor_server(tmp_path)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    assets = {u: _fetch_asset(u, sri)
              for u, sri in _ASSET_RE.findall(build_editor_page("x"))}

    def route(r):
        u = r.request.url
        if u.startswith("http://127.0.0.1"):
            return r.continue_()
        if u in assets:
            ctype = ("text/css" if u.endswith(".css")
                     else "application/javascript")
            return r.fulfill(path=str(assets[u]), content_type=ctype)
        return r.abort()

    page.route("**/*", route)
    yield url, tmp_path
    httpd.shutdown()


@needs_exiftool
def test_edit_save_advance_and_reopen(editor, page):
    url, folder = editor
    page.goto(url)
    page.wait_for_function("window.__panoReady === true")
    assert "a.jpg" in page.inner_text("#readout")
    # Pose 90 + yaw 0 => the readout heading starts at 90.
    assert "Heading 90.0" in page.inner_text("#readout")

    # Drag the sphere: readout heading must move off 90.
    box = page.locator("#viewer").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(cx, cy)
    page.mouse.down()
    page.mouse.move(cx - 200, cy, steps=10)
    page.mouse.up()
    page.wait_for_function(
        "!document.querySelector('#readout').innerText.includes"
        "('Heading 90.0')")
    heading_line = page.inner_text("#readout")

    with page.expect_response("**/api/save") as resp_info:
        page.click("#save")
    assert resp_info.value.status == 200

    # Auto-advance to b.jpg, and the tags landed on disk for a.jpg.
    page.wait_for_function(
        "document.querySelector('#readout').innerText.includes('b.jpg')")
    out = subprocess.run(
        ["exiftool", "-json", "-n",
         "-XMP-GPano:InitialViewHeadingDegrees",
         "-XMP-GPano:InitialHorizontalFOVDegrees",
         str(folder / "a.jpg")],
        check=True, capture_output=True, text=True).stdout
    assert "InitialViewHeadingDegrees" in out
    assert "InitialHorizontalFOVDegrees" in out
    assert (folder / "a.jpg_original").exists()   # backup kept

    # Reload: a.jpg reopens at the saved heading (round-trip through
    # _pano_view on the server side). Compare as floats: the value
    # survives a float -> exiftool -> float round trip.
    page.goto(url)
    page.wait_for_function("window.__panoReady === true")
    saved = float(heading_line.split("Heading ")[1].split("°")[0])
    shown = float(
        page.inner_text("#readout").split("Heading ")[1].split("°")[0])
    assert shown == pytest.approx(saved, abs=0.2)
