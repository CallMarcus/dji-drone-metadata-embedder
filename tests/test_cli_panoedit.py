"""CLI wiring tests for `dji-embed panoedit` (run_editor is monkeypatched:
the server itself is covered by tests/test_geo_panoedit_server.py)."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from dji_metadata_embedder import cli as cli_mod
from dji_metadata_embedder.geo.panoedit import (
    DEFAULT_MAX_SERVE_WIDTH,
    PanoEditError,
)


def test_panoedit_forwards_options(monkeypatch, tmp_path):
    calls = {}

    def fake_run(directory, **kwargs):
        calls["directory"] = directory
        calls.update(kwargs)
    monkeypatch.setattr(cli_mod, "run_editor", fake_run)
    result = CliRunner().invoke(cli_mod.main, [
        "panoedit", str(tmp_path), "--recursive", "--no-browser",
        "--url-only", "--exit-with-stdin", "--port", "7777"])
    assert result.exit_code == 0, result.output
    assert calls == {
        "directory": Path(tmp_path), "recursive": True, "port": 7777,
        "open_browser": False, "bare_url": True, "stop_on_stdin_eof": True,
        "max_width": DEFAULT_MAX_SERVE_WIDTH}


def test_panoedit_max_width_is_overridable(monkeypatch, tmp_path):
    # The ceiling is a measured default, not a law: a machine with a
    # capable GPU can ask for full-size serving (#471).
    calls = {}
    monkeypatch.setattr(cli_mod, "run_editor",
                        lambda directory, **kw: calls.update(kw))
    result = CliRunner().invoke(cli_mod.main, [
        "panoedit", str(tmp_path), "--max-width", "0"])
    assert result.exit_code == 0, result.output
    assert calls["max_width"] == 0


def test_panoedit_makes_logging_nonblocking(monkeypatch, tmp_path):
    # The GUI redirects this command's stderr to a pipe it never reads; a
    # blocking log write inside the save chain froze every later save
    # (#490). The command must hand its logging to the queue wrapper.
    assert hasattr(cli_mod, "make_logging_nonblocking")
    calls = []
    monkeypatch.setattr(cli_mod, "make_logging_nonblocking",
                        lambda *a, **kw: calls.append(True))
    monkeypatch.setattr(cli_mod, "run_editor", lambda directory, **kw: None)
    result = CliRunner().invoke(cli_mod.main, ["panoedit", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert calls == [True]


def test_panoedit_error_is_clean(monkeypatch, tmp_path):
    def fake_run(directory, **kwargs):
        raise PanoEditError("No 360-degree panoramas found")
    monkeypatch.setattr(cli_mod, "run_editor", fake_run)
    result = CliRunner().invoke(cli_mod.main, ["panoedit", str(tmp_path)])
    assert result.exit_code != 0
    assert "No 360-degree panoramas found" in result.output
    assert "Traceback" not in result.output


def test_panoedit_listed_in_help():
    result = CliRunner().invoke(cli_mod.main, ["--help"])
    assert "panoedit" in result.output
