"""Downscale-serving for oversized panoramas (#471).

Field evidence: on a 2 GB-VRAM GPU, 8000 px and 12000 px equirects failed
to load erratically after the first while the same folder at 6000x3000
opened every image. The editor therefore serves a downscaled rendition and
keeps the original untouched — these tests pin both halves of that promise.
"""
from __future__ import annotations

import io
import json
import threading
import urllib.request
from pathlib import Path

import pytest
from PIL import Image

from dji_metadata_embedder.geo import panoedit as pe

# A minimal GPano packet: the tags Pannellum reads to decide the
# panorama's angular extent. They are ratios, so they stay correct after a
# downscale — but only if they survive the re-encode at all.
_XMP = (
    b'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    b'<rdf:Description'
    b' xmlns:GPano="http://ns.google.com/photos/1.0/panorama/"'
    b' GPano:ProjectionType="equirectangular"'
    b' GPano:FullPanoWidthPixels="1200"'
    b' GPano:CroppedAreaImageWidthPixels="1200"'
    b' GPano:FullPanoHeightPixels="600"'
    b' GPano:CroppedAreaImageHeightPixels="600"'
    b' GPano:CroppedAreaTopPixels="0"'
    b' GPano:PoseHeadingDegrees="90"/>'
    b"</rdf:RDF></x:xmpmeta><?xpacket end=\"w\"?>"
)


def _pano(path, width=1200, height=600, xmp=_XMP):
    im = Image.new("RGB", (width, height), (30, 60, 200))
    for x in range(width // 2, width):
        for y in range(height // 2):
            im.putpixel((x, y), (200, 60, 30))
    im.save(path, "JPEG", quality=90, **({"xmp": xmp} if xmp else {}))
    return path


# downscale_pano ---------------------------------------------------------


def test_rendition_caps_width_and_carries_gpano(tmp_path):
    src = _pano(tmp_path / "big.jpg")
    dest = tmp_path / "small.jpg"
    assert pe.downscale_pano(src, dest, 600) == dest
    with Image.open(dest) as im:
        assert im.size == (600, 300)          # aspect ratio preserved
        assert im.info.get("xmp") == _XMP     # angles still derivable
    with Image.open(src) as im:
        assert im.size == (1200, 600)         # source only ever read


def test_rendition_without_pillow_is_none(tmp_path, monkeypatch):
    src = _pano(tmp_path / "big.jpg")
    monkeypatch.setattr(pe, "_pil_image", lambda: None)
    assert pe.downscale_pano(src, tmp_path / "out.jpg", 600) is None


def test_rendition_refused_when_gpano_would_be_lost(tmp_path, monkeypatch):
    # A rendition without the GPano packet would be framed differently
    # from the original for any cropped panorama, and the view saved from
    # it would inherit that error. Better no rendition than a wrong one.
    src = _pano(tmp_path / "big.jpg")
    dest = tmp_path / "out.jpg"
    real_save = Image.Image.save

    def save_without_xmp(self, fp, fmt=None, **kwargs):
        kwargs.pop("xmp", None)
        return real_save(self, fp, fmt, **kwargs)

    monkeypatch.setattr(Image.Image, "save", save_without_xmp)
    assert pe.downscale_pano(src, dest, 600) is None
    assert not dest.exists()                  # no half-built leftovers


def test_rendition_of_unreadable_file_is_none(tmp_path):
    broken = tmp_path / "broken.jpg"
    broken.write_bytes(b"\xff\xd8not-a-jpeg")
    assert pe.downscale_pano(broken, tmp_path / "out.jpg", 600) is None


# Server -----------------------------------------------------------------


@pytest.fixture
def editor(monkeypatch, tmp_path):
    """Editor server over one oversized and one small panorama."""
    big = _pano(tmp_path / "big.jpg", 1200, 600)
    small = _pano(tmp_path / "small.jpg", 400, 200, xmp=None)
    files = [
        pe.PanoFile(path=big, name="big.jpg", pose=0.0, yaw=None,
                    pitch=None, hfov=None, width=1200, height=600),
        pe.PanoFile(path=small, name="small.jpg", pose=0.0, yaw=None,
                    pitch=None, hfov=None, width=400, height=200),
    ]
    monkeypatch.setattr(pe, "scan_panos", lambda d, recursive=False: files)

    def start(**kwargs):
        httpd, url = pe.make_editor_server(tmp_path, **kwargs)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        started.append(httpd)
        return httpd, url

    started: list = []
    yield start, tmp_path
    for httpd in started:
        httpd.shutdown()
        httpd.server_close()


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.read()


def test_oversized_is_served_downscaled_small_is_untouched(editor):
    start, folder = editor
    _, url = start(max_width=600)
    with Image.open(io.BytesIO(_get(url + "img/0"))) as im:
        assert im.size == (600, 300)
        assert im.info.get("xmp") == _XMP
    assert _get(url + "img/1") == (folder / "small.jpg").read_bytes()
    # The originals are what the editor writes tags to: never rewritten.
    with Image.open(folder / "big.jpg") as im:
        assert im.size == (1200, 600)


def test_rendition_is_built_once_and_cleaned_up(editor, monkeypatch):
    # Re-encoding a large JPEG costs seconds on the machines that need
    # this, so the second view of the same panorama must be free.
    start, _ = editor
    httpd, url = start(max_width=600)
    builds = []
    real = pe.downscale_pano
    monkeypatch.setattr(pe, "downscale_pano", lambda src, dest, mw: (
        builds.append(src) or real(src, dest, mw)))
    _get(url + "img/0")
    _get(url + "img/0")
    assert len(builds) == 1

    cache = Path(httpd._cache.name)
    assert list(cache.iterdir())              # the rendition lives here
    httpd.server_close()
    assert not cache.exists()                 # and dies with the server


def test_list_reports_size_and_downscaling(editor):
    start, _ = editor
    _, url = start(max_width=600)
    data = json.loads(_get(url + "api/list"))
    assert [(f["width"], f["height"], f["downscaled"]) for f in data] == [
        (1200, 600, True), (400, 200, False)]


def test_max_width_zero_serves_originals(editor):
    start, folder = editor
    _, url = start(max_width=0)
    assert _get(url + "img/0") == (folder / "big.jpg").read_bytes()
    assert json.loads(_get(url + "api/list"))[0]["downscaled"] is False


def test_without_pillow_the_editor_still_serves(editor, monkeypatch):
    # Pillow is an extra. Its absence degrades the preview, never the
    # editor: the original is served and the page is told why.
    monkeypatch.setattr(pe, "_pil_image", lambda: None)
    start, folder = editor
    httpd, url = start(max_width=600)
    assert _get(url + "img/0") == (folder / "big.jpg").read_bytes()
    assert json.loads(_get(url + "api/list"))[0]["downscaled"] is False
    assert httpd.pano_renditions is False
    assert b"Pillow is not installed" in httpd.pano_page


def test_tiny_max_width_is_raised_to_the_floor(editor):
    start, _ = editor
    httpd, _url = start(max_width=10)
    assert httpd.pano_max_width == pe._MIN_SERVE_WIDTH


# Terminal notice --------------------------------------------------------


def test_notice_reports_downscaling(editor):
    start, _ = editor
    httpd, _url = start(max_width=600)
    notice = pe._oversize_notice(httpd)
    assert notice is not None
    assert "1 panorama wider than 600 px" in notice
    assert "not modified" in notice


def test_notice_names_pillow_when_renditions_are_impossible(
        editor, monkeypatch):
    monkeypatch.setattr(pe, "_pil_image", lambda: None)
    start, _ = editor
    httpd, _url = start(max_width=600)
    assert "Pillow is not installed" in (pe._oversize_notice(httpd) or "")


def test_no_notice_when_nothing_is_oversized(editor):
    start, _ = editor
    httpd, _url = start(max_width=6000)
    assert pe._oversize_notice(httpd) is None
