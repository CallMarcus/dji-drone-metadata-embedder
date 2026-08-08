"""Tests for the panoedit scan + write core."""
from __future__ import annotations

import json

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
