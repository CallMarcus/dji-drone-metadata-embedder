"""Golden contract tests for --progress jsonl (docs/PROGRESS_JSONL.md).

Every stdout line of a command running in jsonl mode must be a JSON object
that validates against docs/progress_jsonl.schema.json; a stream starts with
``start`` and ends with exactly one terminal event (``result`` or ``error``).
"""

import json
from pathlib import Path

import jsonschema
from click.testing import CliRunner

from dji_metadata_embedder.cli import main

SCHEMA = json.loads(
    (Path(__file__).parent.parent / "docs" / "progress_jsonl.schema.json")
    .read_text(encoding="utf-8")
)

FLIGHT_A = (
    "1\n00:00:00,000 --> 00:00:01,000\n"
    '<font size="28">[latitude: 10.0] [longitude: 20.0] '
    "[rel_alt: 1.000 abs_alt: 5.0]</font>\n\n"
    "2\n00:00:01,000 --> 00:00:02,000\n"
    '<font size="28">[latitude: 10.001] [longitude: 20.001] '
    "[rel_alt: 1.000 abs_alt: 6.0]</font>\n"
)
NOT_TELEMETRY = "1\n00:00:00,000 --> 00:00:01,000\nJust a movie subtitle\n"


def _events(stdout: str) -> list[dict]:
    events = [json.loads(line) for line in stdout.splitlines()]
    for e in events:
        jsonschema.validate(e, SCHEMA)
    assert events, "expected at least one event on stdout"
    assert events[0]["event"] == "start"
    terminal = [e for e in events if e["event"] in ("result", "error")]
    assert len(terminal) == 1 and events[-1] is terminal[0]
    return events


def test_flightmap_jsonl_happy_path(tmp_path):
    (tmp_path / "DJI_0001.SRT").write_text(FLIGHT_A, encoding="utf-8")
    (tmp_path / "DJI_0002.SRT").write_text(
        FLIGHT_A.replace("10.0", "11.0"), encoding="utf-8"
    )
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "--progress", "jsonl"]
    )
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    assert events[0]["command"] == "flightmap"
    progress = [e for e in events if e["event"] == "progress"]
    assert [p["item"] for p in progress] == ["DJI_0001", "DJI_0002"]
    assert progress[-1]["current"] == progress[-1]["total"] == 2
    last = events[-1]
    assert last["event"] == "result" and last["ok"] is True
    assert last["outputs"] == [str((tmp_path / "flightmap.html").resolve())]
    assert last["summary"] == {"flights": 2, "skipped": 0, "joined_files": 0}


def test_flightmap_jsonl_warns_per_skipped_file(tmp_path):
    (tmp_path / "DJI_0001.SRT").write_text(FLIGHT_A, encoding="utf-8")
    (tmp_path / "movie.srt").write_text(NOT_TELEMETRY, encoding="utf-8")
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "--progress", "jsonl"]
    )
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    warnings = [e for e in events if e["event"] == "warning"]
    assert len(warnings) == 1 and warnings[0]["item"] == "movie"
    assert events[-1]["summary"]["skipped"] == 1


def test_flightmap_jsonl_fatal_error_event(tmp_path):
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "--progress", "jsonl"]
    )
    assert res.exit_code != 0
    events = _events(res.stdout)
    assert events[-1]["event"] == "error"
    assert "No .SRT" in events[-1]["message"]


GEOTAGGED = [
    {
        "SourceFile": "photos/church1.jpg",
        "GPSLatitude": 60.170278,
        "GPSLongitude": 24.952222,
        "GPSAltitude": 95.3,
    },
    {"SourceFile": "photos/no_gps.jpg"},
]


def _mock_photo_scan(monkeypatch, data=None, error=None):
    from dji_metadata_embedder.geo import photomap as pm

    def fake(directory, recursive):
        if error is not None:
            raise error
        return data

    monkeypatch.setattr(pm, "_run_exiftool_scan", fake)


def test_photomap_jsonl_happy_path(monkeypatch, tmp_path):
    _mock_photo_scan(monkeypatch, data=GEOTAGGED)
    res = CliRunner().invoke(
        main, ["photomap", str(tmp_path), "--progress", "jsonl"]
    )
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    assert events[0]["command"] == "photomap"
    assert "total" not in events[0]  # batch scan: count unknown up front
    assert not any(e["event"] == "progress" for e in events)
    warnings = [e for e in events if e["event"] == "warning"]
    assert len(warnings) == 1 and warnings[0]["item"] == "no_gps.jpg"
    last = events[-1]
    assert last["ok"] is True
    assert last["outputs"] == [str((tmp_path / "photomap.html").resolve())]
    assert last["summary"] == {"photos": 1, "skipped": 1}


def test_photomap_jsonl_fatal_error_event(monkeypatch, tmp_path):
    from dji_metadata_embedder.geo.photomap import PhotomapError

    _mock_photo_scan(monkeypatch, error=PhotomapError("ExifTool not found"))
    res = CliRunner().invoke(
        main, ["photomap", str(tmp_path), "--progress", "jsonl"]
    )
    assert res.exit_code != 0
    events = _events(res.stdout)
    assert events[-1]["event"] == "error"
    assert "ExifTool" in events[-1]["message"]


def test_photomap_jsonl_rejects_serve(tmp_path):
    res = CliRunner().invoke(
        main, ["photomap", str(tmp_path), "--serve", "--progress", "jsonl"]
    )
    assert res.exit_code != 0
    assert "--serve" in res.output and "--progress" in res.output


def test_check_jsonl_events(monkeypatch, tmp_path):
    from dji_metadata_embedder import cli as cli_mod

    canned = {"subtitle_telemetry": True, "gps_metadata": False}
    monkeypatch.setattr(cli_mod, "check_metadata", lambda target: dict(canned))
    a = tmp_path / "DJI_0001.MP4"
    b = tmp_path / "DJI_0002.MP4"
    a.write_bytes(b"fake")
    b.write_bytes(b"fake")
    res = CliRunner().invoke(
        main, ["check", str(a), str(b), "--progress", "jsonl"]
    )
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    assert events[0]["command"] == "check" and events[0]["total"] == 2
    progress = [e for e in events if e["event"] == "progress"]
    assert [p["item"] for p in progress] == [str(a), str(b)]
    last = events[-1]
    assert last["ok"] is True and last["outputs"] == []
    assert last["summary"]["checked"] == 2
    assert last["summary"]["files"] == {str(a): canned, str(b): canned}


def test_embed_jsonl_events(monkeypatch, tmp_path):
    from dji_metadata_embedder import cli as cli_mod

    monkeypatch.setattr(cli_mod, "check_dependencies", lambda: (True, []))
    canned = {
        "processed": 1,
        "total_files": 2,
        "warnings": ["No SRT file found for: DJI_0002.MP4"],
        "errors": [],
        "output_directory": str(tmp_path / "processed"),
    }

    def fake_process(self, use_exiftool=False, on_progress=None):
        if on_progress is not None:
            on_progress(1, 2, "DJI_0001.MP4")
            on_progress(2, 2, "DJI_0002.MP4")
        return canned

    monkeypatch.setattr(
        cli_mod.DJIMetadataEmbedder, "process_directory", fake_process
    )
    res = CliRunner().invoke(
        main, ["embed", str(tmp_path), "--progress", "jsonl"]
    )
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    kinds = [e["event"] for e in events]
    assert events[0]["command"] == "embed"
    assert kinds.count("progress") == 2
    assert kinds.count("warning") == 1
    last = events[-1]
    assert last["ok"] is True
    assert last["outputs"] == [canned["output_directory"]]
    assert last["summary"] == {
        "processed": 1,
        "total": 2,
        "warnings": 1,
        "errors": 0,
        "output_directory": canned["output_directory"],
    }


def test_embed_jsonl_per_file_errors_mean_ok_false(monkeypatch, tmp_path):
    from dji_metadata_embedder import cli as cli_mod

    monkeypatch.setattr(cli_mod, "check_dependencies", lambda: (True, []))
    canned = {
        "processed": 0,
        "total_files": 1,
        "warnings": [],
        "errors": ["FFmpeg failed for DJI_0001.MP4"],
        "output_directory": str(tmp_path / "processed"),
    }
    monkeypatch.setattr(
        cli_mod.DJIMetadataEmbedder,
        "process_directory",
        lambda self, use_exiftool=False, on_progress=None: canned,
    )
    res = CliRunner().invoke(
        main, ["embed", str(tmp_path), "--progress", "jsonl"]
    )
    assert res.exit_code == 0, res.output  # exit semantics unchanged in v1
    events = _events(res.stdout)
    assert events[-1]["event"] == "result" and events[-1]["ok"] is False
    warnings = [e for e in events if e["event"] == "warning"]
    assert any("FFmpeg failed" in w["message"] for w in warnings)


def test_embed_jsonl_missing_dependencies_is_error_event(monkeypatch, tmp_path):
    from dji_metadata_embedder import cli as cli_mod

    monkeypatch.setattr(
        cli_mod, "check_dependencies", lambda: (False, ["ffmpeg"])
    )
    res = CliRunner().invoke(
        main, ["embed", str(tmp_path), "--progress", "jsonl"]
    )
    assert res.exit_code != 0
    events = _events(res.stdout)
    assert events[-1]["event"] == "error"
    assert "ffmpeg" in events[-1]["message"]


def test_process_directory_accepts_on_progress_callback(tmp_path):
    """Real plumbing: empty dir returns early, callback stays uncalled."""
    from dji_metadata_embedder.embedder import DJIMetadataEmbedder

    calls: list[tuple] = []
    embedder = DJIMetadataEmbedder(str(tmp_path))
    result = embedder.process_directory(on_progress=lambda *a: calls.append(a))
    assert result["total_files"] == 0
    assert calls == []


def test_jsonl_stdout_stays_pure_even_with_verbose(tmp_path):
    (tmp_path / "DJI_0001.SRT").write_text(FLIGHT_A, encoding="utf-8")
    (tmp_path / "movie.srt").write_text(NOT_TELEMETRY, encoding="utf-8")
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "-v", "--progress", "jsonl"]
    )
    assert res.exit_code == 0, res.output
    _events(res.stdout)  # every stdout line must be a valid schema event
    assert "Skipped" in res.stderr  # the -v detail went to stderr


def test_jsonl_stdout_survives_logger_warnings_in_real_process(tmp_path):
    """logging output (RichHandler) must not leak into the event stream.

    Must run in a subprocess: under pytest the logging plugin already owns
    the root logger, so setup_logging's basicConfig no-ops and the leak is
    invisible to CliRunner. An SRT with absolute datetimes plus a rewritten
    mtime triggers the aggregated timezone logger.warning in scan_flights.
    """
    import os
    import subprocess
    import sys

    srt = (
        "1\n00:00:00,000 --> 00:00:01,000\n"
        '<font size="28">FrameCnt: 1, DiffTime: 1000ms\n'
        "2026-06-15 12:00:00.000\n"
        "[latitude: 34.0] [longitude: -84.0] "
        "[rel_alt: 1.000 abs_alt: 100.0]</font>\n"
    )
    path = tmp_path / "DJI_0001.SRT"
    path.write_text(srt, encoding="utf-8")
    os.utime(path, (946684800.0, 946684800.0))  # mtime a transfer rewrote
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from dji_metadata_embedder.cli import main; main()",
            "flightmap",
            str(tmp_path),
            "--progress",
            "jsonl",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    events = [json.loads(line) for line in proc.stdout.splitlines()]
    for e in events:
        jsonschema.validate(e, SCHEMA)
    assert events[-1]["event"] == "result"
    assert "Timezone" in proc.stderr  # the warning still reaches the user


def test_unexpected_exception_still_ends_stream_with_error_event(
    monkeypatch, tmp_path
):
    """The terminal rule must hold for non-ClickException failures too
    (PermissionError from mkdir, UnicodeDecodeError from a corrupt SRT...)."""
    from dji_metadata_embedder import cli as cli_mod

    def boom(*args, **kwargs):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(cli_mod, "scan_flights", boom)
    (tmp_path / "DJI_0001.SRT").write_text(FLIGHT_A, encoding="utf-8")
    res = CliRunner().invoke(
        main,
        ["flightmap", str(tmp_path), "--progress", "jsonl"],
        standalone_mode=False,
    )
    assert res.exit_code != 0
    events = _events(res.stdout)
    assert events[-1]["event"] == "error"
    assert "disk on fire" in events[-1]["message"]


def test_embed_jsonl_outputs_are_absolute(monkeypatch, tmp_path):
    from dji_metadata_embedder import cli as cli_mod

    monkeypatch.setattr(cli_mod, "check_dependencies", lambda: (True, []))
    canned = {
        "processed": 1,
        "total_files": 1,
        "warnings": [],
        "errors": [],
        "output_directory": "footage/processed",  # relative, as embedder builds it
    }
    monkeypatch.setattr(
        cli_mod.DJIMetadataEmbedder,
        "process_directory",
        lambda self, use_exiftool=False, on_progress=None: canned,
    )
    res = CliRunner().invoke(
        main, ["embed", str(tmp_path), "--progress", "jsonl"]
    )
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    (out,) = events[-1]["outputs"]
    assert Path(out).is_absolute()


def test_check_jsonl_warns_on_missing_path(monkeypatch, tmp_path):
    res = CliRunner().invoke(
        main,
        ["check", str(tmp_path / "nope.mp4"), "--progress", "jsonl"],
    )
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    warnings = [e for e in events if e["event"] == "warning"]
    assert len(warnings) == 1
    assert warnings[0]["item"] == str(tmp_path / "nope.mp4")


def test_check_jsonl_expands_directories(monkeypatch, tmp_path):
    from dji_metadata_embedder import cli as cli_mod

    canned = {"gps": True, "altitude": True, "creation_time": True}
    monkeypatch.setattr(cli_mod, "check_metadata", lambda target: dict(canned))
    (tmp_path / "DJI_0001.MP4").write_bytes(b"fake")
    (tmp_path / "IMG_0002.JPG").write_bytes(b"fake")
    (tmp_path / "notes.txt").write_text("not media", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "DJI_0003.MP4").write_bytes(b"fake")  # below top level: excluded
    res = CliRunner().invoke(
        main, ["check", str(tmp_path), "--progress", "jsonl"]
    )
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    assert events[0]["total"] == 2
    expected = [str(tmp_path / "DJI_0001.MP4"), str(tmp_path / "IMG_0002.JPG")]
    progress = [e for e in events if e["event"] == "progress"]
    assert [p["item"] for p in progress] == expected
    assert events[-1]["summary"]["checked"] == 2
    assert sorted(events[-1]["summary"]["files"]) == expected


def test_check_jsonl_warns_on_empty_directory(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    res = CliRunner().invoke(
        main, ["check", str(empty), "--progress", "jsonl"]
    )
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    assert events[0]["total"] == 0
    warnings = [e for e in events if e["event"] == "warning"]
    assert len(warnings) == 1
    assert warnings[0]["item"] == str(empty)
    assert warnings[0]["message"] == "No media files found"
    last = events[-1]
    assert last["ok"] is True
    assert last["summary"] == {"checked": 0, "files": {}}


def test_check_jsonl_warns_on_unreadable_directory(monkeypatch, tmp_path):
    from dji_metadata_embedder import cli as cli_mod

    unreadable = tmp_path / "unreadable"
    unreadable.mkdir()
    monkeypatch.setattr(
        cli_mod,
        "media_files_in",
        lambda p: (_ for _ in ()).throw(PermissionError("denied")),
    )
    res = CliRunner().invoke(
        main, ["check", str(unreadable), "--progress", "jsonl"]
    )
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    assert events[0]["total"] == 0
    warnings = [e for e in events if e["event"] == "warning"]
    assert len(warnings) == 1
    assert warnings[0]["item"] == str(unreadable)
    assert warnings[0]["message"] == "Not found or unreadable"
    last = events[-1]
    assert last["ok"] is True
    assert last["summary"] == {"checked": 0, "files": {}}


def test_flightmap_jsonl_all_formats_lists_every_output(tmp_path):
    (tmp_path / "DJI_0001.SRT").write_text(FLIGHT_A, encoding="utf-8")
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "-f", "all", "--progress", "jsonl"]
    )
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    outputs = events[-1]["outputs"]
    assert [Path(o).suffix for o in outputs] == [".html", ".kml", ".geojson"]


# --- doctor (issue #264 stage 3d: the GUI's "Check my setup" screen) ------


def _patch_doctor_env(monkeypatch, *, ffmpeg=True, exiftool=True):
    from dji_metadata_embedder import cli
    from dji_metadata_embedder.utils import exiftool as exiftool_utils

    missing = [
        t for t, ok in (("ffmpeg", ffmpeg), ("exiftool", exiftool)) if not ok
    ]
    monkeypatch.setattr(cli, "check_dependencies", lambda: (not missing, missing))
    if exiftool:
        monkeypatch.setattr(exiftool_utils, "exiftool_version", lambda: "13.30")
        monkeypatch.setattr(exiftool_utils, "exiftool_source", lambda: "path")
        monkeypatch.setattr(
            exiftool_utils, "exiftool_exe", lambda: "/usr/bin/exiftool"
        )
        monkeypatch.setattr(
            exiftool_utils, "describe_decode_capability", lambda v: "full"
        )


def test_doctor_jsonl_all_present(monkeypatch):
    _patch_doctor_env(monkeypatch)
    res = CliRunner().invoke(main, ["doctor", "--progress", "jsonl"])
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    assert events[0]["event"] == "start"
    assert events[0]["command"] == "doctor"
    result = events[-1]
    assert result["event"] == "result"
    assert result["ok"] is True
    tools = result["summary"]["tools"]
    assert tools["ffmpeg"]["present"] is True
    assert tools["exiftool"]["present"] is True
    assert tools["exiftool"]["version"] == "13.30"


def test_doctor_jsonl_missing_tool_warns_but_exits_zero(monkeypatch):
    # Missing dependencies are a report, not a crash: ok=false + exit 0,
    # mirroring embed's per-file-failure nuance.
    _patch_doctor_env(monkeypatch, ffmpeg=False)
    res = CliRunner().invoke(main, ["doctor", "--progress", "jsonl"])
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    warnings = [e for e in events if e["event"] == "warning"]
    assert [w["item"] for w in warnings] == ["ffmpeg"]
    result = events[-1]
    assert result["ok"] is False
    assert result["summary"]["tools"]["ffmpeg"]["present"] is False


# --- convert / validate / verify-sun (GUI 2.0 M4 prerequisite) ------------

FLIGHT_TIMED = (
    "1\n00:00:00,000 --> 00:00:01,000\n"
    '<font size="28">FrameCnt: 1, DiffTime: 1000ms\n'
    "2026-06-15 16:00:00.000\n"
    "[latitude: 34.0] [longitude: -84.0] "
    "[rel_alt: 1.000 abs_alt: 100.0]</font>\n\n"
    "2\n00:00:01,000 --> 00:00:02,000\n"
    '<font size="28">FrameCnt: 2, DiffTime: 1000ms\n'
    "2026-06-15 16:00:01.000\n"
    "[latitude: 34.001] [longitude: -84.001] "
    "[rel_alt: 1.000 abs_alt: 101.0]</font>\n"
)


def test_convert_jsonl_happy_single_file(tmp_path):
    src = tmp_path / "DJI_0001.SRT"
    src.write_text(FLIGHT_A, encoding="utf-8")
    res = CliRunner().invoke(
        main, ["convert", "gpx", str(src), "--progress", "jsonl"]
    )
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    assert events[0]["command"] == "convert" and events[0]["total"] == 1
    progress = [e for e in events if e["event"] == "progress"]
    assert len(progress) == 1 and progress[0]["item"] == "DJI_0001.SRT"
    assert progress[0]["current"] == progress[0]["total"] == 1
    last = events[-1]
    assert last["ok"] is True
    assert last["outputs"] == [str((tmp_path / "DJI_0001.gpx").resolve())]
    assert last["summary"] == {"converted": 1, "skipped": 0, "format": "gpx"}


def test_convert_jsonl_batch_warns_per_skipped_file(monkeypatch, tmp_path):
    from dji_metadata_embedder import cli as cli_mod
    from dji_metadata_embedder.mp4_telemetry import Mp4TelemetryError

    def fake_gpx(srt_file, output_file=None, **kwargs):
        path = Path(srt_file)
        if path.suffix.upper() == ".MP4":
            raise Mp4TelemetryError("no djmd stream")
        out = path.with_suffix(".gpx")
        out.write_text("<gpx/>", encoding="utf-8")
        return out

    monkeypatch.setattr(cli_mod, "extract_telemetry_to_gpx", fake_gpx)
    (tmp_path / "DJI_0001.SRT").write_text(FLIGHT_A, encoding="utf-8")
    (tmp_path / "DJI_0002.MP4").write_bytes(b"fake")
    res = CliRunner().invoke(
        main, ["convert", "gpx", str(tmp_path), "-b", "--progress", "jsonl"]
    )
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    assert "total" not in events[0]  # batch: count unknown until scanned
    progress = [e for e in events if e["event"] == "progress"]
    assert {p["item"] for p in progress} == {"DJI_0001.SRT", "DJI_0002.MP4"}
    assert progress[-1]["total"] == 2
    warnings = [e for e in events if e["event"] == "warning"]
    assert len(warnings) == 1 and warnings[0]["item"] == "DJI_0002.MP4"
    last = events[-1]
    assert last["ok"] is True
    assert last["outputs"] == [str((tmp_path / "DJI_0001.gpx").resolve())]
    assert last["summary"] == {"converted": 1, "skipped": 1, "format": "gpx"}


def test_convert_jsonl_fatal_error_event(tmp_path):
    src = tmp_path / "DJI_0001.SRT"
    src.write_text(FLIGHT_A, encoding="utf-8")
    res = CliRunner().invoke(
        main,
        ["convert", "gpx", str(src), "--tz-offset", "banana",
         "--progress", "jsonl"],
    )
    assert res.exit_code != 0
    events = _events(res.stdout)
    assert events[-1]["event"] == "error"
    assert "tz-offset" in events[-1]["message"]


def _mock_validate_directory(monkeypatch, canned):
    from dji_metadata_embedder.core import validator

    monkeypatch.setattr(
        validator, "validate_directory", lambda directory, drift_threshold: canned
    )


def test_validate_jsonl_happy_directory(monkeypatch, tmp_path):
    canned = {
        "total_files": 2,
        "valid_pairs": 2,
        "issues": [],
        "warnings": [],
        "file_analyses": [],
    }
    _mock_validate_directory(monkeypatch, canned)
    res = CliRunner().invoke(
        main, ["validate", str(tmp_path), "--progress", "jsonl"]
    )
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    assert events[0]["command"] == "validate"
    assert "total" not in events[0]
    assert not any(e["event"] == "warning" for e in events)
    last = events[-1]
    assert last["ok"] is True and last["outputs"] == []
    assert last["summary"] == canned


def test_validate_jsonl_issues_become_warnings_and_exit_zero(
    monkeypatch, tmp_path
):
    canned = {
        "total_files": 2,
        "valid_pairs": 1,
        "issues": ["No SRT file found for DJI_0002.mp4"],
        "warnings": ["Drift above threshold in DJI_0001.mp4"],
        "file_analyses": [],
    }
    _mock_validate_directory(monkeypatch, canned)
    res = CliRunner().invoke(
        main, ["validate", str(tmp_path), "--progress", "jsonl"]
    )
    # Findings are a report, not a command failure: exit 0 in progress mode
    # (text mode keeps ExitCode.VALIDATION_ERROR for scripts).
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    warnings = [e for e in events if e["event"] == "warning"]
    assert [w["message"] for w in warnings] == canned["issues"]
    last = events[-1]
    assert last["ok"] is True
    assert last["summary"] == canned


def test_validate_jsonl_rejects_format_json(tmp_path):
    res = CliRunner().invoke(
        main,
        ["validate", str(tmp_path), "--format", "json", "--progress", "jsonl"],
    )
    assert res.exit_code != 0
    assert "--format" in res.output and "--progress" in res.output


def test_verify_sun_jsonl_happy_path(tmp_path):
    src = tmp_path / "DJI_0001.SRT"
    src.write_text(FLIGHT_TIMED, encoding="utf-8")
    res = CliRunner().invoke(
        main,
        ["verify-sun", str(src), "--tz-offset", "+0", "--progress", "jsonl"],
    )
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    assert events[0]["command"] == "verify-sun"
    assert not any(e["event"] == "warning" for e in events)
    last = events[-1]
    assert last["ok"] is True and last["outputs"] == []
    assert last["summary"]["file"] == "DJI_0001.SRT"
    assert last["summary"]["points"] == 2
    assert last["summary"]["sun_computed"] == 2
    assert last["summary"]["flags"] == []


def test_verify_sun_jsonl_flags_become_warnings(tmp_path):
    src = tmp_path / "DJI_0001.SRT"
    src.write_text(FLIGHT_A, encoding="utf-8")  # no absolute datetimes
    res = CliRunner().invoke(
        main,
        ["verify-sun", str(src), "--tz-offset", "+0", "--progress", "jsonl"],
    )
    assert res.exit_code == 0, res.output
    events = _events(res.stdout)
    warnings = [e for e in events if e["event"] == "warning"]
    assert len(warnings) == 1
    assert "sun_not_computable" in warnings[0]["message"]
    last = events[-1]
    assert last["ok"] is True
    assert last["summary"]["flags"] == ["sun_not_computable"]


def test_verify_sun_jsonl_rejects_format_json(tmp_path):
    src = tmp_path / "DJI_0001.SRT"
    src.write_text(FLIGHT_A, encoding="utf-8")
    res = CliRunner().invoke(
        main,
        ["verify-sun", str(src), "--format", "json", "--progress", "jsonl"],
    )
    assert res.exit_code != 0
    assert "--format" in res.output and "--progress" in res.output


def test_doctor_jsonl_never_runs_the_online_update_check(monkeypatch):
    # Consent for going online is interactive-only; a machine consumer of
    # the event stream must never trigger the network path.
    _patch_doctor_env(monkeypatch)
    from dji_metadata_embedder.utils import update_check

    def _boom(*a, **k):
        raise AssertionError("update check must not run under --progress jsonl")

    monkeypatch.setattr(update_check, "update_report", _boom)
    res = CliRunner().invoke(main, ["doctor", "--progress", "jsonl", "--online"])
    assert res.exit_code == 0, res.output
    assert _events(res.stdout)[-1]["event"] == "result"
