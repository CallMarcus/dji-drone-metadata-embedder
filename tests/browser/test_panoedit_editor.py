"""End-to-end editor test: a real panoedit server, real exiftool writes,
headless Chromium driving the page. Waits are on renderedness
(window.__panoReady), never on element existence."""
from __future__ import annotations

import shutil
import subprocess
import threading
import time

import pytest

pytest.importorskip("playwright")
from PIL import Image  # noqa: E402

from dji_metadata_embedder.geo import panoedit as pe  # noqa: E402
from dji_metadata_embedder.geo.panoedit_html import build_editor_page  # noqa: E402

from .conftest import _ASSET_RE, _fetch_asset  # noqa: E402

needs_exiftool = pytest.mark.skipif(
    shutil.which("exiftool") is None, reason="ExifTool not installed")


def _make_pano(path, pose: float, size=(256, 128), crop_tags=False) -> None:
    w, h = size
    im = Image.new("RGB", (w, h), (30, 60, 200))
    for x in range(w // 2, w):
        for y in range(h // 2):
            im.putpixel((x, y), (200, 60, 30))
    im.save(path, "JPEG")
    tags = ["-XMP-GPano:ProjectionType=equirectangular",
            f"-XMP-GPano:PoseHeadingDegrees={pose}"]
    if crop_tags:
        # The full set Pannellum needs before it will read any of it —
        # including the pose that becomes the viewer's north offset.
        tags += [f"-XMP-GPano:FullPanoWidthPixels={w}",
                 f"-XMP-GPano:CroppedAreaImageWidthPixels={w}",
                 f"-XMP-GPano:FullPanoHeightPixels={h}",
                 f"-XMP-GPano:CroppedAreaImageHeightPixels={h}",
                 "-XMP-GPano:CroppedAreaTopPixels=0"]
    subprocess.run(
        ["exiftool", "-overwrite_original", *tags, str(path)],
        check=True, capture_output=True)


def _serve(tmp_path, page, **kwargs):
    """Start an editor over *tmp_path* with unpkg assets stubbed."""
    httpd, url = pe.make_editor_server(tmp_path, **kwargs)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

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
    return httpd, url


@pytest.fixture
def editor(tmp_path, page, monkeypatch):
    monkeypatch.delenv("DJIEMBED_EXIFTOOL_PATH", raising=False)
    _make_pano(tmp_path / "a.jpg", pose=90.0)
    _make_pano(tmp_path / "b.jpg", pose=0.0)
    httpd, url = _serve(tmp_path, page)
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


@needs_exiftool
def test_oversized_panorama_is_served_downscaled(tmp_path, page, monkeypatch):
    # #471: the viewer gets a smaller copy, and it must be a copy the
    # viewer reads exactly like the original — the GPano packet decides
    # the panorama's angular extent and its north offset, so if the
    # re-encode dropped it, the saved view would be wrong.
    monkeypatch.delenv("DJIEMBED_EXIFTOOL_PATH", raising=False)
    _make_pano(tmp_path / "wide.jpg", pose=90.0, size=(1200, 600),
               crop_tags=True)
    original = (tmp_path / "wide.jpg").read_bytes()
    httpd, url = _serve(tmp_path, page, max_width=600)
    try:
        page.goto(url)
        page.wait_for_function("window.__panoReady === true")

        served = page.evaluate(
            """() => new Promise((res, rej) => {
                 const im = new Image();
                 im.onload = () => res([im.naturalWidth, im.naturalHeight]);
                 im.onerror = rej;
                 im.src = "/img/0";
               })""")
        assert served == [600, 300]
        # Pose 90 survived the re-encode as Pannellum's north offset.
        assert page.evaluate("window.__viewer.getNorthOffset()") == 90
        assert "shown downscaled to 600 px" in page.inner_text("#note")
        # The editor's own math is unaffected by the rendition.
        assert "Heading 90.0" in page.inner_text("#readout")
    finally:
        httpd.shutdown()
    assert (tmp_path / "wide.jpg").read_bytes() == original


@needs_exiftool
def test_reset_and_compare_against_the_saved_view(tmp_path, page, monkeypatch):
    # #473: Reset snaps back to the file's opening view without a write,
    # and Compare flips between the saved view and the one being composed.
    monkeypatch.delenv("DJIEMBED_EXIFTOOL_PATH", raising=False)
    pano = tmp_path / "saved.jpg"
    _make_pano(pano, pose=0.0)
    subprocess.run(
        ["exiftool", "-overwrite_original", "-n",
         "-XMP-GPano:InitialViewHeadingDegrees=40",
         "-XMP-GPano:InitialViewPitchDegrees=0",
         "-XMP-GPano:InitialHorizontalFOVDegrees=90", str(pano)],
        check=True, capture_output=True)
    before = pano.read_bytes()
    httpd, url = _serve(tmp_path, page)
    try:
        page.goto(url)
        page.wait_for_function("window.__panoReady === true")
        page.wait_for_function("window.__viewer.getYaw() !== 0")
        saved_yaw = page.evaluate("window.__viewer.getYaw()")

        def drag(dx):
            box = page.locator("#viewer").bounding_box()
            cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            page.mouse.move(cx, cy)
            page.mouse.down()
            page.mouse.move(cx + dx, cy, steps=10)
            page.mouse.up()

        drag(-160)
        page.wait_for_function(
            f"Math.abs(window.__viewer.getYaw() - {saved_yaw}) > 5")
        composed = page.evaluate("window.__viewer.getYaw()")

        # Compare: the saved view comes back, and saving is refused while
        # it is on screen (that write would change nothing).
        page.keyboard.press("c")
        page.wait_for_function(
            f"Math.abs(window.__viewer.getYaw() - {saved_yaw}) < 1")
        assert page.locator("#save").is_disabled()
        assert "saved view" in page.inner_text("#readout")

        # ...and back to the composed view, with saving live again.
        page.keyboard.press("c")
        page.wait_for_function(
            f"Math.abs(window.__viewer.getYaw() - {composed}) < 1")
        assert page.locator("#save").is_enabled()

        # Reset: back to the opening view, still with nothing written.
        drag(-160)
        page.wait_for_function(
            f"Math.abs(window.__viewer.getYaw() - {saved_yaw}) > 5")
        page.keyboard.press("Escape")
        page.wait_for_function(
            f"Math.abs(window.__viewer.getYaw() - {saved_yaw}) < 1")
    finally:
        httpd.shutdown()
    assert pano.read_bytes() == before
    assert not (tmp_path / "saved.jpg_original").exists()


@needs_exiftool
def test_compare_is_off_for_files_with_no_saved_view(editor, page):
    url, _folder = editor
    page.goto(url)
    page.wait_for_function("window.__panoReady === true")
    # a.jpg carries no initial-view tags: there is nothing to compare to.
    assert page.locator("#compare").is_disabled()
    assert page.locator("#reset").is_enabled()


@needs_exiftool
def test_navigation_is_blocked_while_a_save_is_in_flight(
        tmp_path, page, monkeypatch):
    # Review finding: `save()` used the post-await `idx`, and N was live
    # during the save, so a save that landed after navigating wrote its
    # answer onto a different file's entry — leaving the second panorama
    # showing the first one's name and unreachable for the session.
    monkeypatch.delenv("DJIEMBED_EXIFTOOL_PATH", raising=False)
    _make_pano(tmp_path / "a.jpg", pose=0.0)
    _make_pano(tmp_path / "b.jpg", pose=0.0)
    release = threading.Event()

    def slow(path, heading, pitch, hfov, backup=True):
        release.wait(10)
        return {"heading": heading, "pitch": pitch, "hfov": hfov, "pose": 0.0}

    monkeypatch.setattr(pe, "write_initial_view", slow)
    httpd, url = _serve(tmp_path, page)
    try:
        page.goto(url)
        page.wait_for_function("window.__panoReady === true")
        page.click("#save")
        page.wait_for_function(
            "document.querySelector('#status').innerText.includes('Saving')")
        page.keyboard.press("n")            # ignored: the save owns a.jpg
        assert "a.jpg" in page.inner_text("#readout")
        release.set()
        # The save advances to b.jpg itself, and b.jpg is still b.jpg.
        page.wait_for_function(
            "document.querySelector('#readout').innerText.includes('b.jpg')")
        names = page.evaluate(
            "Array.from(document.querySelectorAll('.chip'))"
            ".map(c => c.textContent)")
        assert names == ["a.jpg", "b.jpg"]
    finally:
        release.set()
        httpd.shutdown()


@needs_exiftool
def test_zooming_while_comparing_returns_control_to_the_user(
        tmp_path, page, monkeypatch):
    # Review finding: only mousedown/touchstart retired the comparison, so
    # a wheel zoom left Save disabled on a view the user had visibly
    # changed, with only a small line of text to explain it.
    monkeypatch.delenv("DJIEMBED_EXIFTOOL_PATH", raising=False)
    pano = tmp_path / "saved.jpg"
    _make_pano(pano, pose=0.0)
    subprocess.run(
        ["exiftool", "-overwrite_original", "-n",
         "-XMP-GPano:InitialViewHeadingDegrees=40",
         "-XMP-GPano:InitialViewPitchDegrees=0",
         "-XMP-GPano:InitialHorizontalFOVDegrees=90", str(pano)],
        check=True, capture_output=True)
    httpd, url = _serve(tmp_path, page)
    try:
        page.goto(url)
        page.wait_for_function("window.__panoReady === true")
        page.keyboard.press("c")
        page.wait_for_function("document.querySelector('#save').disabled")
        box = page.locator("#viewer").bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2,
                        box["y"] + box["height"] / 2)
        page.mouse.wheel(0, -300)           # zoom: no mousedown anywhere
        page.wait_for_function(
            "!document.querySelector('#save').disabled")
        assert "saved view" not in page.inner_text("#readout")
    finally:
        httpd.shutdown()


@needs_exiftool
def test_save_timeout_frees_the_button(tmp_path, page, monkeypatch):
    # #475: a save that stalls used to leave the button disabled and
    # unresponsive until the app was restarted. It must always come back,
    # with a message that says what happened.
    monkeypatch.delenv("DJIEMBED_EXIFTOOL_PATH", raising=False)
    _make_pano(tmp_path / "a.jpg", pose=0.0)

    def stalls(path, heading, pitch, hfov, backup=True):
        time.sleep(5)
        return {"heading": heading, "pitch": pitch, "hfov": hfov, "pose": 0.0}

    monkeypatch.setattr(pe, "write_initial_view", stalls)
    httpd, url = _serve(tmp_path, page)
    # Same page, with the backstop pulled in so the test is seconds long.
    httpd.pano_page = build_editor_page(
        httpd.pano_token, save_timeout_ms=800).encode("utf-8")
    try:
        page.goto(url)
        page.wait_for_function("window.__panoReady === true")
        page.click("#save")
        page.wait_for_function(
            "document.querySelector('#status').innerText"
            ".includes('Save timed out')")
        assert page.locator("#save").is_enabled()
    finally:
        httpd.shutdown()


@needs_exiftool
def test_no_backup_save_leaves_no_original_copy(tmp_path, page, monkeypatch):
    # #492: with backups declined, a save writes in place — no *_original —
    # and the footer note stops promising one.
    monkeypatch.delenv("DJIEMBED_EXIFTOOL_PATH", raising=False)
    _make_pano(tmp_path / "a.jpg", pose=0.0)
    httpd, url = _serve(tmp_path, page, backup=False)
    try:
        page.goto(url)
        page.wait_for_function("window.__panoReady === true")
        assert "no backup" in page.inner_text("#note")
        page.keyboard.press("Enter")
        page.wait_for_function(
            "document.getElementById('status').textContent.includes('Saved')")
    finally:
        httpd.shutdown()
    assert not (tmp_path / "a.jpg_original").exists()
    out = subprocess.run(
        ["exiftool", "-n", "-XMP-GPano:InitialViewHeadingDegrees",
         str(tmp_path / "a.jpg")], capture_output=True, text=True, check=True)
    assert "Initial View Heading" in out.stdout   # the write still landed
