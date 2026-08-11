"""HTTP contract tests for the panoedit server (no browser, no exiftool:
scan and write are monkeypatched; the server logic is what's under test)."""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from dji_metadata_embedder.geo import panoedit as pe


@pytest.fixture
def editor(monkeypatch, tmp_path):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8" + b"J" * 500)
    files = [pe.PanoFile(path=img, name="a.jpg", pose=90.0,
                         yaw=None, pitch=None, hfov=None)]
    monkeypatch.setattr(pe, "scan_panos", lambda d, recursive=False: files)
    writes: list[tuple] = []

    def fake_write(path, heading, pitch, hfov):
        writes.append((path, heading, pitch, hfov))
        return {"heading": heading, "pitch": pitch, "hfov": hfov,
                "pose": 90.0}
    monkeypatch.setattr(pe, "write_initial_view", fake_write)
    httpd, url = pe.make_editor_server(tmp_path)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield url, httpd, writes
    httpd.shutdown()


def _get(url: str):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.read()


def _post(url: str, payload: dict):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_page_and_list(editor):
    url, httpd, _ = editor
    status, body = _get(url)
    assert status == 200 and b"<!DOCTYPE html" in body
    status, body = _get(url + "api/list")
    data = json.loads(body)
    assert status == 200
    assert data == [{"index": 0, "name": "a.jpg", "pose": 90.0,
                     "yaw": None, "pitch": None, "hfov": None,
                     "hasView": False, "width": 0, "height": 0,
                     "downscaled": False}]


def test_image_by_index_only(editor):
    url, _, _ = editor
    status, body = _get(url + "img/0")
    assert status == 200 and body.startswith(b"\xff\xd8")
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(url + "img/1")
    assert e.value.code == 404
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(url + "img/../../etc/passwd")
    assert e.value.code == 404


def test_save_happy_path_updates_list(editor):
    url, httpd, writes = editor
    token = httpd.pano_token
    status, body = _post(url + "api/save", {
        "index": 0, "heading": 135.5, "pitch": -3.0, "hfov": 100.0,
        "token": token})
    assert status == 200
    assert body["heading"] == 135.5
    assert writes and writes[0][1] == 135.5
    _, listing = _get(url + "api/list")
    entry = json.loads(listing)[0]
    assert entry["hasView"] is True
    assert entry["yaw"] == pytest.approx(45.5)   # 135.5 - pose 90
    assert entry["pitch"] == -3.0


def test_save_rejects_bad_token_and_input(editor):
    url, httpd, writes = editor
    token = httpd.pano_token
    ok = {"index": 0, "heading": 10.0, "pitch": 0.0, "hfov": 90.0}
    assert _post(url + "api/save", {**ok, "token": "wrong"})[0] == 403
    assert _post(url + "api/save", {**ok, "token": token, "index": 9})[0] == 400
    assert _post(url + "api/save",
                 {**ok, "token": token, "pitch": 91.0})[0] == 400
    assert _post(url + "api/save",
                 {**ok, "token": token, "hfov": 5.0})[0] == 400
    assert _post(url + "api/save",
                 {**ok, "token": token, "heading": "x"})[0] == 400
    assert writes == []


def test_save_returns_503_while_another_save_holds_the_lock(editor, monkeypatch):
    # A wedged save must surface as an honest error on the next attempt,
    # not as a request that waits forever on the lock (#490).
    url, httpd, writes = editor
    monkeypatch.setattr(pe, "_SAVE_LOCK_TIMEOUT", 0.2)
    httpd.pano_lock.acquire()
    try:
        status, body = _post(url + "api/save", {
            "index": 0, "heading": 1.0, "pitch": 0.0, "hfov": 90.0,
            "token": httpd.pano_token})
        assert status == 503
        assert "save" in body["error"].lower()
        assert writes == []                   # ExifTool was never reached
    finally:
        httpd.pano_lock.release()


def test_save_write_failure_is_500(editor, monkeypatch):
    url, httpd, _ = editor

    def boom(path, heading, pitch, hfov):
        raise pe.PanoEditError("disk on fire")
    monkeypatch.setattr(pe, "write_initial_view", boom)
    status, body = _post(url + "api/save", {
        "index": 0, "heading": 1.0, "pitch": 0.0, "hfov": 90.0,
        "token": httpd.pano_token})
    assert status == 500 and "disk on fire" in body["error"]
