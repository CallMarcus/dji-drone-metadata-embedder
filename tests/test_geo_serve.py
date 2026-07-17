import threading
import urllib.request
import webbrowser
from http.server import ThreadingHTTPServer

from dji_metadata_embedder.geo.serve import _make_server, serve_directory


def _fixture_dir(tmp_path):
    (tmp_path / "photomap.html").write_text("<!DOCTYPE html><p>map</p>", encoding="utf-8")
    (tmp_path / "pano.jpg").write_bytes(b"\xff\xd8\xff\xdbJPEGDATA")
    return tmp_path


def test_make_server_binds_loopback_free_port_and_serves_files(tmp_path):
    served = _fixture_dir(tmp_path)
    server = _make_server(served)
    thread = None
    try:
        host, port = server.server_address[0], server.server_address[1]
        assert host == "127.0.0.1"
        assert port != 0  # OS assigned a real free port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(f"{base}/photomap.html", timeout=5) as resp:
            assert resp.status == 200
            assert b"map" in resp.read()
        with urllib.request.urlopen(f"{base}/pano.jpg", timeout=5) as resp:
            assert resp.status == 200
            assert resp.read() == (served / "pano.jpg").read_bytes()
    finally:
        server.shutdown()
        server.server_close()
        if thread is not None:
            thread.join(timeout=5)
            assert not thread.is_alive()


def test_make_server_is_quiet_by_default(tmp_path, capsys):
    # Request logging (BaseHTTPRequestHandler.log_message -> stderr) is
    # silenced unless log_requests=True.
    server = _make_server(_fixture_dir(tmp_path))
    thread = None
    try:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        urllib.request.urlopen(f"http://127.0.0.1:{port}/photomap.html", timeout=5).read()
    finally:
        server.shutdown()
        server.server_close()
        if thread is not None:
            thread.join(timeout=5)
            assert not thread.is_alive()
    assert "GET /photomap.html" not in capsys.readouterr().err


def test_make_server_logs_requests_when_enabled(tmp_path, capsys):
    server = _make_server(_fixture_dir(tmp_path), log_requests=True)
    thread = None
    try:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        urllib.request.urlopen(f"http://127.0.0.1:{port}/photomap.html", timeout=5).read()
    finally:
        server.shutdown()
        server.server_close()
        if thread is not None:
            thread.join(timeout=5)
            assert not thread.is_alive()
    assert "GET /photomap.html" in capsys.readouterr().err


def test_serve_directory_prints_url_opens_browser_and_stops_on_interrupt(
    tmp_path, monkeypatch, capsys
):
    served = _fixture_dir(tmp_path)
    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url) or True)

    def fake_serve_forever(self, poll_interval=0.5):
        raise KeyboardInterrupt

    monkeypatch.setattr(ThreadingHTTPServer, "serve_forever", fake_serve_forever)
    serve_directory(served, "photomap.html")
    out = capsys.readouterr().out
    assert "http://127.0.0.1:" in out
    assert "photomap.html" in out
    assert "Ctrl+C" in out
    assert "Stopped." in out
    assert opened and opened[0].endswith("/photomap.html")


def test_serve_directory_open_browser_false_and_quiet(tmp_path, monkeypatch, capsys):
    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url) or True)

    def fake_serve_forever(self, poll_interval=0.5):
        raise KeyboardInterrupt

    monkeypatch.setattr(ThreadingHTTPServer, "serve_forever", fake_serve_forever)
    serve_directory(_fixture_dir(tmp_path), "photomap.html", quiet=True, open_browser=False)
    out = capsys.readouterr().out
    # The URL is the product of the command: printed even under quiet.
    assert "http://127.0.0.1:" in out
    assert "Stopped." not in out
    assert opened == []


# Wrapper contract (#305): --url-only / --exit-with-stdin let the desktop
# GUI manage a server child whose lifetime is tied to the app.


def test_serve_directory_bare_url_prints_only_the_url_first(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(webbrowser, "open", lambda url: True)

    def fake_serve_forever(self, poll_interval=0.5):
        raise KeyboardInterrupt

    monkeypatch.setattr(ThreadingHTTPServer, "serve_forever", fake_serve_forever)
    serve_directory(
        _fixture_dir(tmp_path), "photomap.html",
        quiet=True, open_browser=False, bare_url=True,
    )
    first = capsys.readouterr().out.splitlines()[0]
    assert first.startswith("http://127.0.0.1:")
    assert first.endswith("/photomap.html")


def test_serve_directory_stops_when_stdin_closes(tmp_path, monkeypatch):
    import io
    import sys

    # Simulated wrapper exit: stdin already at EOF must take the server down
    # without any signal or kill.
    class _ClosedStdin:
        buffer = io.BytesIO(b"")

    monkeypatch.setattr(sys, "stdin", _ClosedStdin())
    monkeypatch.setattr(webbrowser, "open", lambda url: True)
    done = threading.Event()

    def run():
        serve_directory(
            _fixture_dir(tmp_path), "photomap.html",
            quiet=True, open_browser=False, stop_on_stdin_eof=True,
        )
        done.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert done.wait(timeout=10), "server did not stop on stdin EOF"
