"""CLI wiring tests for `dji-embed panoedit` (run_editor is monkeypatched:
the server itself is covered by tests/test_geo_panoedit_server.py)."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from dji_metadata_embedder import cli as cli_mod
from dji_metadata_embedder.geo.panoedit import PanoEditError


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
        "open_browser": False, "bare_url": True, "stop_on_stdin_eof": True}


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
