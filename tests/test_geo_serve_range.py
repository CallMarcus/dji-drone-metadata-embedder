"""HTTP Range support in the local map server (#380).

The video crossfade is a seek, and Python's stock SimpleHTTPRequestHandler
ignores Range entirely: Chrome re-requests from byte zero on every seek and
Safari refuses to play at all.
"""

import threading
import urllib.error
import urllib.request

import pytest

from dji_metadata_embedder.geo.serve import _make_server, _parse_range

BODY = bytes(range(256)) * 8       # 2048 bytes, every value distinguishable


@pytest.fixture
def server(tmp_path):
    (tmp_path / "clip.bin").write_bytes(BODY)
    httpd = _make_server(tmp_path)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/clip.bin"
    httpd.shutdown()
    thread.join(timeout=5)


def _get(url, rng=None):
    req = urllib.request.Request(url)
    if rng is not None:
        req.add_header("Range", rng)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, dict(resp.headers), resp.read()


def test_whole_file_advertises_range_support(server):
    status, headers, body = _get(server)
    assert status == 200
    assert headers["Accept-Ranges"] == "bytes"
    assert body == BODY


def test_leading_range(server):
    status, headers, body = _get(server, "bytes=0-99")
    assert status == 206
    assert headers["Content-Range"] == f"bytes 0-99/{len(BODY)}"
    assert headers["Content-Length"] == "100"
    assert body == BODY[:100]


def test_open_ended_range(server):
    status, headers, body = _get(server, "bytes=2000-")
    assert status == 206
    assert headers["Content-Range"] == f"bytes 2000-2047/{len(BODY)}"
    assert body == BODY[2000:]


def test_suffix_range(server):
    """`bytes=-100` means the LAST 100 bytes, not the first 100."""
    status, headers, body = _get(server, "bytes=-100")
    assert status == 206
    assert headers["Content-Range"] == f"bytes 1948-2047/{len(BODY)}"
    assert body == BODY[-100:]


def test_range_past_end_is_416(server):
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "bytes=9000-9100")
    assert exc.value.code == 416
    assert exc.value.headers["Content-Range"] == f"bytes */{len(BODY)}"


def test_multi_range_falls_back_to_whole_file(server):
    """No browser needs multipart ranges for media; serving the whole file is
    a legal and much simpler answer than building a multipart body."""
    status, _, body = _get(server, "bytes=0-99,200-299")
    assert status == 200
    assert body == BODY


def test_garbage_range_is_ignored(server):
    status, _, body = _get(server, "furlongs=0-99")
    assert status == 200
    assert body == BODY


@pytest.mark.parametrize("header,size,expected", [
    ("bytes=0-99", 2048, (0, 99)),
    ("bytes=100-", 2048, (100, 2047)),
    ("bytes=-100", 2048, (1948, 2047)),
    ("bytes=0-99999", 2048, (0, 2047)),      # clamped to the file
    ("bytes=-99999", 2048, (0, 2047)),       # suffix longer than the file
    ("bytes=0-99,200-299", 2048, None),      # multi-range -> whole file
    ("furlongs=0-9", 2048, None),
    ("bytes=-", 2048, None),
])
def test_parse_range(header, size, expected):
    assert _parse_range(header, size) == expected


def test_parse_range_rejects_start_past_end():
    with pytest.raises(ValueError):
        _parse_range("bytes=2048-", 2048)
