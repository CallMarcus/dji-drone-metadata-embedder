"""HTTP Range support in the local map server (#380, #385).

The video crossfade is a seek, and Python's stock SimpleHTTPRequestHandler
ignores Range entirely: Chrome re-requests from byte zero on every seek and
Safari refuses to play at all.
"""

import socket
import struct
import threading
import time
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


def _get(url, rng=None, if_range=None):
    req = urllib.request.Request(url)
    if rng is not None:
        req.add_header("Range", rng)
    if if_range is not None:
        req.add_header("If-Range", if_range)
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


def test_reversed_range_falls_back_to_whole_file(server):
    """`bytes=100-50` is syntactically valid but backwards. A reversed range
    is ignored rather than rejected -- see the comment in _parse_range."""
    status, _, body = _get(server, "bytes=100-50")
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
    ("bytes=100-50", 2048, None),            # reversed -> ignored, not 416
])
def test_parse_range(header, size, expected):
    assert _parse_range(header, size) == expected


def test_parse_range_rejects_start_past_end():
    with pytest.raises(ValueError):
        _parse_range("bytes=2048-", 2048)


# ---------------------------------------------------------------------------
# Validators on partial content (#385). A 206 without Last-Modified gives the
# client nothing to revalidate against, and ignoring If-Range would splice a
# stale byte range into a changed file. Files rarely change under this
# loopback server, but "rarely" is not the standard the rest of the tool
# holds itself to.

def test_206_carries_the_same_last_modified_as_200(server):
    _, whole, _ = _get(server)
    status, partial, _ = _get(server, "bytes=0-99")
    assert status == 206
    assert "Last-Modified" in whole
    assert partial.get("Last-Modified") == whole["Last-Modified"]


def test_if_range_with_current_validator_gets_206(server):
    _, whole, _ = _get(server)
    status, _, body = _get(server, "bytes=0-99",
                           if_range=whole["Last-Modified"])
    assert status == 206
    assert body == BODY[:100]


def test_if_range_with_stale_validator_gets_the_whole_file(server):
    """A changed file must not have an old range spliced into it: If-Range
    that no longer matches downgrades to the full 200 by design."""
    status, _, body = _get(server, "bytes=0-99",
                           if_range="Wed, 21 Oct 2015 07:28:00 GMT")
    assert status == 200
    assert body == BODY


def test_if_range_with_an_etag_gets_the_whole_file(server):
    """This server never issues ETags, so an entity-tag validator can never
    match anything we sent -- the safe answer is the whole file."""
    status, _, body = _get(server, "bytes=0-99", if_range='"deadbeef"')
    assert status == 200
    assert body == BODY


# ---------------------------------------------------------------------------
# Aborted transfers (#385). Seeking media aborts in-flight range requests as
# a matter of course; each one used to print a full traceback to the serve
# console, making a working server look broken.

def test_client_disconnect_is_not_reported(tmp_path, capsys):
    """The connection-reset family is the normal end of an aborted seek."""
    httpd = _make_server(tmp_path)
    try:
        raise ConnectionResetError(104, "peer reset")
    except ConnectionResetError:
        httpd.handle_error(None, ("127.0.0.1", 54321))
    finally:
        httpd.server_close()
    assert capsys.readouterr().err == ""


def test_genuine_errors_are_still_reported(tmp_path, capsys):
    """Swallowing must be scoped: a real bug keeps its traceback."""
    httpd = _make_server(tmp_path)
    try:
        raise ValueError("a real bug in the handler")
    except ValueError:
        httpd.handle_error(None, ("127.0.0.1", 54321))
    finally:
        httpd.server_close()
    assert "ValueError" in capsys.readouterr().err


def test_aborted_range_transfer_leaves_a_clean_console(tmp_path, capsys):
    """End to end: abort a large range transfer mid-flight, then check the
    server both survives and says nothing about it."""
    (tmp_path / "big.bin").write_bytes(b"\0" * (8 * 1024 * 1024))
    httpd = _make_server(tmp_path)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=10)
        s.sendall(b"GET /big.bin HTTP/1.1\r\nHost: t\r\n"
                  b"Range: bytes=0-\r\n\r\n")
        s.recv(1024)               # the transfer is genuinely under way
        # SO_LINGER 0 turns close() into an RST, so the server's next write
        # fails immediately instead of filling socket buffers into the void.
        s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                     struct.pack("ii", 1, 0))
        s.close()
        time.sleep(0.5)            # let the write loop hit the reset
        # The server must shrug it off and keep serving.
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/big.bin", timeout=10) as resp:
            assert resp.status == 200
            resp.read(1024)
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()
    assert capsys.readouterr().err == ""
