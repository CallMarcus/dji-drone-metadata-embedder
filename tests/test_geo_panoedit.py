"""Tests for the panoedit scan + write core."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dji_metadata_embedder.geo import panoedit as pe
from dji_metadata_embedder.geo.photomap import _pano_view


def test_compass_heading_inverts_pano_view():
    # For every (pose, yaw): writing compass_heading(pose, yaw) and reading
    # it back through _pano_view must return the original yaw.
    for pose in (0.0, 37.5, 180.0, 359.9):
        for yaw in (-179.9, -90.0, 0.0, 45.25, 179.9):
            heading = pe.compass_heading(pose, yaw)
            assert 0.0 <= heading < 360.0
            got_yaw, _, _ = _pano_view({
                "InitialViewHeadingDegrees": heading,
                "PoseHeadingDegrees": pose,
            })
            assert got_yaw == pytest.approx(yaw, abs=1e-6)


def test_compass_heading_missing_pose_is_north():
    # pose 0.0 (the "stitcher wrote none" default) -> heading == yaw mod 360
    assert pe.compass_heading(0.0, -90.0) == pytest.approx(270.0)


def test_scan_panos_filters_and_sorts(monkeypatch, tmp_path):
    def fake_scan(directory, recursive):
        return [
            {"SourceFile": str(tmp_path / "b.jpg"),
             "ProjectionType": "equirectangular",
             "PoseHeadingDegrees": 90.0,
             "InitialViewHeadingDegrees": 100.0,
             "InitialViewPitchDegrees": -5.0,
             "InitialHorizontalFOVDegrees": 95.0},
            {"SourceFile": str(tmp_path / "a.jpg"),
             "ProjectionType": "equirectangular"},
            {"SourceFile": str(tmp_path / "flat.jpg")},   # not a pano
        ]
    monkeypatch.setattr(pe, "_run_scan", fake_scan)
    files = pe.scan_panos(tmp_path)
    assert [f.name for f in files] == ["a.jpg", "b.jpg"]
    a, b = files
    assert a.pose == 0.0 and a.yaw is None and a.pitch is None and a.hfov is None
    assert b.pose == 90.0
    assert b.yaw == pytest.approx(10.0)      # 100 - 90
    assert b.pitch == pytest.approx(-5.0)
    assert b.hfov == pytest.approx(95.0)


def test_scan_panos_no_panos_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pe, "_run_scan", lambda d, r: [{"SourceFile": str(tmp_path / "x.jpg")}])
    with pytest.raises(pe.PanoEditError, match="No 360"):
        pe.scan_panos(tmp_path)


def _fake_exiftool(monkeypatch, read_json: str,
                   returncode: int = 0, stderr: str = "") -> list[list[str]]:
    """Fake ``subprocess.run`` inside panoedit, recording every argv.

    A monkeypatch rather than an on-disk shim script: a ``#!/bin/sh`` file
    is not executable on the Windows CI leg (WinError 193), and the write
    path's real-exiftool behaviour is covered end-to-end by
    tests/browser/test_panoedit_editor.py.
    """
    calls: list[list[str]] = []

    class _Result:
        def __init__(self, args: list[str]):
            self.returncode = returncode
            self.stderr = stderr
            self.stdout = read_json if "-json" in args else ""

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return _Result(args)

    monkeypatch.setattr(pe.subprocess, "run", fake_run)
    return calls


def test_write_initial_view_argv_and_verify(monkeypatch, tmp_path):
    target = tmp_path / "pano.jpg"
    target.write_bytes(b"\xff\xd8fake")
    verified = json.dumps([{
        "InitialViewHeadingDegrees": 123.456,
        "InitialViewPitchDegrees": -4.0,
        "InitialHorizontalFOVDegrees": 100.0,
        "PoseHeadingDegrees": 90.0,
    }])
    calls = _fake_exiftool(monkeypatch, verified)
    result = pe.write_initial_view(target, heading=123.456, pitch=-4.0, hfov=100.0)
    argv = [a for call in calls for a in call]
    assert "-XMP-GPano:InitialViewHeadingDegrees=123.456" in argv
    assert "-XMP-GPano:InitialViewPitchDegrees=-4.0" in argv
    assert "-XMP-GPano:InitialHorizontalFOVDegrees=100.0" in argv
    assert "-overwrite_original" not in argv          # backup stays
    assert not any("VerticalFOV" in a for a in argv)  # the wrong tag, banned
    assert result == {"heading": 123.456, "pitch": -4.0, "hfov": 100.0,
                      "pose": 90.0}


def test_write_initial_view_failure_raises(monkeypatch, tmp_path):
    target = tmp_path / "pano.jpg"
    target.write_bytes(b"\xff\xd8fake")
    _fake_exiftool(monkeypatch, "", returncode=1,
                   stderr="Error: not writable")
    with pytest.raises(pe.PanoEditError, match="not writable"):
        pe.write_initial_view(target, heading=1.0, pitch=0.0, hfov=90.0)


# Save timeouts (#475): no layer of the save chain was bounded, so an
# ExifTool run stalled behind a virus scanner left the page waiting on a
# request that never returned and a Save button that stayed dead until the
# app was restarted.


def test_write_bounds_both_exiftool_runs(monkeypatch, tmp_path):
    target = tmp_path / "pano.jpg"
    target.write_bytes(b"\xff\xd8fake")
    timeouts: list[object] = []
    verified = json.dumps([{"InitialViewHeadingDegrees": 1.0,
                            "InitialViewPitchDegrees": 0.0,
                            "InitialHorizontalFOVDegrees": 90.0,
                            "PoseHeadingDegrees": 0.0}])

    class _Result:
        def __init__(self, args):
            self.returncode = 0
            self.stderr = ""
            self.stdout = verified if "-json" in args else ""

    def fake_run(args, **kwargs):
        timeouts.append(kwargs.get("timeout"))
        return _Result(args)

    monkeypatch.setattr(pe.subprocess, "run", fake_run)
    pe.write_initial_view(target, heading=1.0, pitch=0.0, hfov=90.0)
    assert timeouts == [pe._WRITE_TIMEOUT, pe._WRITE_TIMEOUT]


def test_write_timeout_is_an_actionable_error(monkeypatch, tmp_path):
    target = tmp_path / "pano.jpg"
    target.write_bytes(b"\xff\xd8fake")

    def hang(args, **kwargs):
        raise pe.subprocess.TimeoutExpired(args, kwargs.get("timeout", 0))

    monkeypatch.setattr(pe.subprocess, "run", hang)
    with pytest.raises(pe.PanoEditError) as exc:
        pe.write_initial_view(target, heading=1.0, pitch=0.0, hfov=90.0)
    message = str(exc.value)
    assert "did not finish writing pano.jpg" in message
    assert "Antivirus" in message
    # ExifTool renames the original out of the way before moving its
    # rewritten copy in, so the message must not promise an untouched
    # file — it must say where to look for the image.
    assert "pano.jpg_original" in message
    assert "pano.jpg_exiftool_tmp" in message


def test_write_timeout_message_carries_the_triage_numbers(monkeypatch,
                                                          tmp_path):
    # #531: field reports arrive as screenshots of the error text, so the
    # text itself must carry the measured elapsed time and the ExifTool
    # version — the numbers a triage would otherwise have to ask for.
    target = tmp_path / "pano.jpg"
    target.write_bytes(b"\xff\xd8fake")

    def hang(args, **kwargs):
        raise pe.subprocess.TimeoutExpired(args, kwargs.get("timeout", 0))

    monkeypatch.setattr(pe.subprocess, "run", hang)
    monkeypatch.setattr(pe, "_version_cache", ["13.36"])
    clock = iter([0.0, 61.2])
    monkeypatch.setattr(pe.time, "monotonic", lambda: next(clock))
    with pytest.raises(pe.PanoEditError) as exc:
        pe.write_initial_view(target, heading=1.0, pitch=0.0, hfov=90.0)
    message = str(exc.value)
    assert "ExifTool 13.36" in message
    assert "stopped after 61.2 s" in message


def test_exiftool_version_is_cached_and_optional(monkeypatch):
    # One subprocess ever; a missing ExifTool degrades to the bare name.
    calls: list[int] = []

    def fake_version():
        calls.append(1)
        return None

    monkeypatch.setattr(pe, "exiftool_version", fake_version)
    monkeypatch.setattr(pe, "_version_cache", [])
    assert pe._cached_exiftool_version() is None
    assert pe._cached_exiftool_version() is None
    assert len(calls) == 1
    assert pe._slow_write_message(Path("p.jpg"), 62.0).startswith(
        "ExifTool did not finish")


def test_readback_timeout_says_the_write_happened(monkeypatch, tmp_path):
    target = tmp_path / "pano.jpg"
    target.write_bytes(b"\xff\xd8fake")

    class _Result:
        returncode = 0
        stderr = ""
        stdout = ""

    def run(args, **kwargs):
        if "-json" in args:
            raise pe.subprocess.TimeoutExpired(args, kwargs.get("timeout", 0))
        return _Result()

    monkeypatch.setattr(pe.subprocess, "run", run)
    with pytest.raises(pe.PanoEditError) as exc:
        pe.write_initial_view(target, heading=1.0, pitch=0.0, hfov=90.0)
    assert "were written" in str(exc.value)
    assert "could not be verified" in str(exc.value)


def test_slow_save_is_logged_as_a_warning(monkeypatch, tmp_path, caplog):
    # The difference between "slow disk" and "hung" is a number, and the
    # next field report should be able to quote it.
    target = tmp_path / "pano.jpg"
    target.write_bytes(b"\xff\xd8fake")
    _fake_exiftool(monkeypatch, json.dumps([{
        "InitialViewHeadingDegrees": 1.0, "InitialViewPitchDegrees": 0.0,
        "InitialHorizontalFOVDegrees": 90.0, "PoseHeadingDegrees": 0.0}]))
    clock = iter([0.0, float(pe._SLOW_WRITE_SECONDS + 5)])
    monkeypatch.setattr(pe.time, "monotonic", lambda: next(clock))
    with caplog.at_level("INFO", logger=pe.logger.name):
        pe.write_initial_view(target, heading=1.0, pitch=0.0, hfov=90.0)
    record = next(r for r in caplog.records if "ExifTool wrote" in r.message)
    assert record.levelname == "WARNING"
    assert "pano.jpg" in record.getMessage()


def test_scan_is_bounded_and_scales_with_the_folder(monkeypatch, tmp_path):
    # A scan stalls for the same reasons a save does, but earlier: it runs
    # before the URL is printed, and the GUI waits for that line.
    for i in range(5):
        (tmp_path / f"p{i}.jpg").write_bytes(b"\xff\xd8")
    (tmp_path / "notes.txt").write_text("not a panorama")
    expected = pe._WRITE_TIMEOUT + 5 * pe._SCAN_SECONDS_PER_FILE
    assert pe._scan_timeout(tmp_path, recursive=False) == expected
    # The allowance is per file, but bounded: a wedged scan still ends.
    monkeypatch.setattr(pe, "_SCAN_TIMEOUT_CAP", 1.0)
    assert pe._scan_timeout(tmp_path, recursive=False) == 1.0

    seen: dict = {}

    def fake_run(args, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        raise pe.subprocess.TimeoutExpired(args, kwargs.get("timeout", 0))

    monkeypatch.setattr(pe.subprocess, "run", fake_run)
    with pytest.raises(pe.PanoEditError) as exc:
        pe.scan_panos(tmp_path)
    assert seen["timeout"] == 1.0
    assert "did not finish reading" in str(exc.value)
    assert "Antivirus" in str(exc.value)


def test_write_timeout_is_logged_as_well_as_returned(monkeypatch, tmp_path,
                                                     caplog):
    # The page tells the user to check the terminal, so the terminal has
    # to have something in it.
    target = tmp_path / "pano.jpg"
    target.write_bytes(b"\xff\xd8fake")
    monkeypatch.setattr(
        pe.subprocess, "run",
        lambda args, **kw: (_ for _ in ()).throw(
            pe.subprocess.TimeoutExpired(args, kw.get("timeout", 0))))
    with caplog.at_level("WARNING", logger=pe.logger.name):
        with pytest.raises(pe.PanoEditError):
            pe.write_initial_view(target, heading=1.0, pitch=0.0, hfov=90.0)
    assert any("did not finish writing pano.jpg" in r.getMessage()
               for r in caplog.records)


# --- #492: backups become optional -----------------------------------------


def test_write_initial_view_no_backup_overwrites_in_place(monkeypatch, tmp_path):
    target = tmp_path / "pano.jpg"
    target.write_bytes(b"\xff\xd8fake")
    verified = json.dumps([{
        "InitialViewHeadingDegrees": 1.0,
        "InitialViewPitchDegrees": 0.0,
        "InitialHorizontalFOVDegrees": 90.0,
        "PoseHeadingDegrees": 0.0,
    }])
    calls = _fake_exiftool(monkeypatch, verified)
    pe.write_initial_view(target, heading=1.0, pitch=0.0, hfov=90.0,
                          backup=False)
    # The flag belongs to the write; the verification read never rewrites
    # anything, so it must not carry it.
    assert "-overwrite_original" in calls[0]
    assert "-overwrite_original" not in calls[1]


def test_clean_backups_deletes_only_confirmed_edits(tmp_path):
    # Deleted: a backup whose edited sibling still exists.
    (tmp_path / "a.jpg").write_bytes(b"\xff\xd8new")
    (tmp_path / "a.jpg_original").write_bytes(b"\xff\xd8old")
    # Kept: an orphan backup is the only copy left — never touch it.
    (tmp_path / "orphan.jpg_original").write_bytes(b"\xff\xd8only")
    # Kept: not a JPEG backup, so not something panoedit ever wrote.
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / "notes.txt_original").write_text("x")
    deleted, freed = pe.clean_backups(tmp_path)
    assert [p.name for p in deleted] == ["a.jpg_original"]
    assert freed == len(b"\xff\xd8old")
    assert not (tmp_path / "a.jpg_original").exists()
    assert (tmp_path / "a.jpg").exists()
    assert (tmp_path / "orphan.jpg_original").exists()
    assert (tmp_path / "notes.txt_original").exists()


def test_clean_backups_recursive_matches_the_editor_scan(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.JPG").write_bytes(b"\xff\xd8new")
    (sub / "b.JPG_original").write_bytes(b"\xff\xd8old")
    deleted, _ = pe.clean_backups(tmp_path)
    assert deleted == []                       # non-recursive stays shallow
    deleted, _ = pe.clean_backups(tmp_path, recursive=True)
    assert [p.name for p in deleted] == ["b.JPG_original"]
    assert not (sub / "b.JPG_original").exists()
