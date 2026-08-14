"""CLI wiring tests for `dji-embed panoedit` (run_editor is monkeypatched:
the server itself is covered by tests/test_geo_panoedit_server.py)."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from dji_metadata_embedder import cli as cli_mod
from dji_metadata_embedder.geo.panoedit import (
    DEFAULT_MAX_SERVE_WIDTH,
    PanoEditError,
)


@pytest.fixture(autouse=True)
def _stub_nonblocking_logging(monkeypatch):
    """Keep the real make_logging_nonblocking away from pytest's root logger.

    The command wires it for real, and under pytest that would swap out the
    logging plugin's caplog/report handlers for a QueueHandler and leak one
    listener thread per invocation (#490 review).
    """
    calls: list[bool] = []
    monkeypatch.setattr(cli_mod, "make_logging_nonblocking",
                        lambda *a, **kw: calls.append(True))
    return calls


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
        "max_width": DEFAULT_MAX_SERVE_WIDTH, "backup": True}


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


def test_panoedit_makes_logging_nonblocking(
        _stub_nonblocking_logging, monkeypatch, tmp_path):
    # The GUI redirects this command's stderr to a pipe it never reads; a
    # blocking log write inside the save chain froze every later save
    # (#490). The command must hand its logging to the queue wrapper.
    monkeypatch.setattr(cli_mod, "run_editor", lambda directory, **kw: None)
    result = CliRunner().invoke(cli_mod.main, ["panoedit", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert _stub_nonblocking_logging == [True]


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


def test_panoedit_no_backup_reaches_run_editor(monkeypatch, tmp_path):
    calls = {}
    monkeypatch.setattr(cli_mod, "run_editor",
                        lambda directory, **kw: calls.update(kw))
    result = CliRunner().invoke(cli_mod.main, [
        "panoedit", str(tmp_path), "--no-backup"])
    assert result.exit_code == 0, result.output
    assert calls["backup"] is False


def test_panoedit_clean_backups_deletes_and_never_serves(monkeypatch, tmp_path):
    # #492: cleanup is a terminal action — report and exit, no server.
    (tmp_path / "a.jpg").write_bytes(b"\xff\xd8new")
    (tmp_path / "a.jpg_original").write_bytes(b"\xff\xd8old" * 100)
    monkeypatch.setattr(cli_mod, "run_editor",
                        lambda *a, **kw: pytest.fail("server must not start"))
    result = CliRunner().invoke(cli_mod.main, [
        "panoedit", str(tmp_path), "--clean-backups"])
    assert result.exit_code == 0, result.output
    assert not (tmp_path / "a.jpg_original").exists()
    assert "1 backup" in result.output


def test_panoedit_clean_backups_reports_nothing_to_do(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_mod, "run_editor",
                        lambda *a, **kw: pytest.fail("server must not start"))
    result = CliRunner().invoke(cli_mod.main, [
        "panoedit", str(tmp_path), "--clean-backups"])
    assert result.exit_code == 0, result.output
    assert "No backup copies" in result.output
