"""Drag-a-folder-onto-the-EXE flow (#264 stage 1).

Windows passes a dragged folder as a bare argv[1]; the CLI maps it and
opens the result in the default browser. These tests drive the same path
through CliRunner with a bare directory argument.
"""

import sys

from click.testing import CliRunner

from dji_metadata_embedder import cli
from dji_metadata_embedder.cli import main
from dji_metadata_embedder.geo import photomap as pm
from dji_metadata_embedder.geo.photomap import PhotomapError

FLIGHT_A = (
    "1\n00:00:00,000 --> 00:00:01,000\n"
    '<font size="28">[latitude: 10.0] [longitude: 20.0] '
    "[rel_alt: 1.000 abs_alt: 5.0]</font>\n\n"
    "2\n00:00:01,000 --> 00:00:02,000\n"
    '<font size="28">[latitude: 10.001] [longitude: 20.001] '
    "[rel_alt: 1.000 abs_alt: 6.0]</font>\n"
)

GEOTAGGED = [
    {
        "SourceFile": "photos/church1.jpg",
        "GPSLatitude": 60.170278,
        "GPSLongitude": 24.952222,
        "GPSAltitude": 95.3,
    },
]


def _capture_browser(monkeypatch):
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: opened.append(url))
    return opened


def _mock_photo_scan(monkeypatch, data=None, error=None):
    def fake(directory, recursive):
        if error is not None:
            raise error
        return data

    monkeypatch.setattr(pm, "_run_exiftool_scan", fake)


def test_bare_directory_maps_flights_and_opens_browser(monkeypatch, tmp_path):
    opened = _capture_browser(monkeypatch)
    (tmp_path / "DJI_0001.SRT").write_text(FLIGHT_A, encoding="utf-8")
    res = CliRunner().invoke(main, [str(tmp_path)])
    assert res.exit_code == 0, res.output
    out = tmp_path / "flightmap.html"
    assert out.exists()
    assert opened == [out.resolve().as_uri()]


def test_bare_directory_scans_subdirectories(monkeypatch, tmp_path):
    opened = _capture_browser(monkeypatch)
    sub = tmp_path / "DCIM" / "100MEDIA"
    sub.mkdir(parents=True)
    (sub / "DJI_0001.SRT").write_text(FLIGHT_A, encoding="utf-8")
    res = CliRunner().invoke(main, [str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert (tmp_path / "flightmap.html").exists()
    assert len(opened) == 1


def test_bare_directory_with_photos_writes_photomap_too(monkeypatch, tmp_path):
    opened = _capture_browser(monkeypatch)
    _mock_photo_scan(monkeypatch, data=GEOTAGGED)
    (tmp_path / "DJI_0001.SRT").write_text(FLIGHT_A, encoding="utf-8")
    (tmp_path / "church1.jpg").write_bytes(b"\xff\xd8fake")
    res = CliRunner().invoke(main, [str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert (tmp_path / "flightmap.html").exists()
    assert (tmp_path / "photomap.html").exists()
    assert len(opened) == 2


def test_bare_directory_photos_only(monkeypatch, tmp_path):
    opened = _capture_browser(monkeypatch)
    _mock_photo_scan(monkeypatch, data=GEOTAGGED)
    (tmp_path / "church1.jpg").write_bytes(b"\xff\xd8fake")
    res = CliRunner().invoke(main, [str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert not (tmp_path / "flightmap.html").exists()
    out = tmp_path / "photomap.html"
    assert out.exists()
    assert opened == [out.resolve().as_uri()]


def test_bare_directory_photomap_failure_still_opens_flightmap(
    monkeypatch, tmp_path
):
    opened = _capture_browser(monkeypatch)
    _mock_photo_scan(monkeypatch, error=PhotomapError("exiftool not found"))
    (tmp_path / "DJI_0001.SRT").write_text(FLIGHT_A, encoding="utf-8")
    (tmp_path / "church1.jpg").write_bytes(b"\xff\xd8fake")
    res = CliRunner().invoke(main, [str(tmp_path)])
    assert res.exit_code == 0, res.output
    out = tmp_path / "flightmap.html"
    assert opened == [out.resolve().as_uri()]
    assert "exiftool not found" in res.output


def test_bare_directory_without_photos_never_runs_exiftool(
    monkeypatch, tmp_path
):
    _capture_browser(monkeypatch)
    _mock_photo_scan(monkeypatch, error=AssertionError("must not be called"))
    (tmp_path / "DJI_0001.SRT").write_text(FLIGHT_A, encoding="utf-8")
    res = CliRunner().invoke(main, [str(tmp_path)])
    assert res.exit_code == 0, res.output


def test_bare_directory_with_nothing_mappable_is_clean_error(
    monkeypatch, tmp_path
):
    opened = _capture_browser(monkeypatch)
    res = CliRunner().invoke(main, [str(tmp_path)])
    assert res.exit_code != 0
    assert res.exception is None or isinstance(res.exception, SystemExit)
    assert "Nothing to map" in res.output
    assert opened == []


def test_multiple_dragged_directories_each_get_a_map(monkeypatch, tmp_path):
    opened = _capture_browser(monkeypatch)
    for name in ("trip1", "trip2"):
        d = tmp_path / name
        d.mkdir()
        (d / "DJI_0001.SRT").write_text(FLIGHT_A, encoding="utf-8")
    res = CliRunner().invoke(
        main, [str(tmp_path / "trip1"), str(tmp_path / "trip2")]
    )
    assert res.exit_code == 0, res.output
    assert (tmp_path / "trip1" / "flightmap.html").exists()
    assert (tmp_path / "trip2" / "flightmap.html").exists()
    assert len(opened) == 2


def test_unknown_command_error_unchanged(tmp_path):
    res = CliRunner().invoke(main, ["definitely-not-a-command"])
    assert res.exit_code != 0
    assert "No such command" in res.output


def test_dragged_file_hints_at_dragging_the_folder(tmp_path):
    video = tmp_path / "DJI_0001.MP4"
    video.write_bytes(b"fake")
    res = CliRunner().invoke(main, [str(video)])
    assert res.exit_code != 0
    assert res.exception is None or isinstance(res.exception, SystemExit)
    assert "folder" in res.output.lower()
    assert "No such command" not in res.output


def test_mixed_drop_maps_the_folder_and_skips_the_file(monkeypatch, tmp_path):
    opened = _capture_browser(monkeypatch)
    trip = tmp_path / "trip"
    trip.mkdir()
    (trip / "DJI_0001.SRT").write_text(FLIGHT_A, encoding="utf-8")
    stray = tmp_path / "DJI_0002.MP4"
    stray.write_bytes(b"fake")
    res = CliRunner().invoke(main, [str(trip), str(stray)])
    assert res.exit_code == 0, res.output
    assert (trip / "flightmap.html").exists()
    assert len(opened) == 1
    assert "Skipping" in res.output and "DJI_0002.MP4" in res.output


def test_multiple_dragged_files_get_the_folder_hint(tmp_path):
    files = []
    for name in ("DJI_0001.MP4", "DJI_0002.MP4"):
        f = tmp_path / name
        f.write_bytes(b"fake")
        files.append(str(f))
    res = CliRunner().invoke(main, files)
    assert res.exit_code != 0
    assert "folder" in res.output.lower()
    assert "No such command" not in res.output


def test_directory_with_options_gets_guidance(tmp_path):
    (tmp_path / "DJI_0001.SRT").write_text(FLIGHT_A, encoding="utf-8")
    res = CliRunner().invoke(main, [str(tmp_path), "-v"])
    assert res.exit_code != 0
    assert "flightmap" in res.output
    assert "No such command" not in res.output


def test_partial_failure_exits_nonzero_but_still_opens_good_map(
    monkeypatch, tmp_path
):
    opened = _capture_browser(monkeypatch)
    good = tmp_path / "good"
    good.mkdir()
    (good / "DJI_0001.SRT").write_text(FLIGHT_A, encoding="utf-8")
    empty = tmp_path / "empty"
    empty.mkdir()
    res = CliRunner().invoke(main, [str(good), str(empty)])
    assert res.exit_code != 0
    assert (good / "flightmap.html").exists()
    assert len(opened) == 1
    assert "Nothing to map" in res.output and "empty" in res.output


def test_frozen_no_args_double_click_shows_drag_hint_not_help(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(cli, "_launched_from_explorer", lambda: True)
    res = CliRunner().invoke(main, [])
    assert res.exit_code == 0, res.output
    assert "drag" in res.output.lower()
    assert "Commands:" not in res.output  # not the click help dump


def test_frozen_no_args_in_terminal_still_shows_help(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(cli, "_launched_from_explorer", lambda: False)
    res = CliRunner().invoke(main, [])
    assert "Usage:" in res.output


def test_unfrozen_no_args_still_shows_help():
    res = CliRunner().invoke(main, [])
    assert "Usage:" in res.output


def test_frozen_double_click_error_pauses_before_window_closes(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(cli, "_launched_from_explorer", lambda: True)
    paused = []
    monkeypatch.setattr("click.pause", lambda info: paused.append(info))
    video = tmp_path / "DJI_0001.MP4"
    video.write_bytes(b"fake")
    res = CliRunner().invoke(main, [str(video)])
    assert res.exit_code != 0
    assert "folder" in res.output.lower()
    assert len(paused) == 1


def test_terminal_error_does_not_pause(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(cli, "_launched_from_explorer", lambda: False)
    paused = []
    monkeypatch.setattr("click.pause", lambda info: paused.append(info))
    video = tmp_path / "DJI_0001.MP4"
    video.write_bytes(b"fake")
    res = CliRunner().invoke(main, [str(video)])
    assert res.exit_code != 0
    assert paused == []


def test_group_passes_none_args_through_for_windows_expansion(monkeypatch):
    """Click only glob-expands on Windows when main() receives args=None."""
    received = []

    def spy_main(self, args=None, *pargs, **extra):
        received.append(args)
        raise SystemExit(0)

    monkeypatch.setattr("click.Group.main", spy_main)
    monkeypatch.setattr(sys, "argv", ["dji-embed", "--help"])
    try:
        main()
    except SystemExit:
        pass
    assert received == [None]
