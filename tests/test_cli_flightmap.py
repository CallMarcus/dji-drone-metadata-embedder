import json

from click.testing import CliRunner

from dji_metadata_embedder.cli import main

FLIGHT_A = (
    "1\n00:00:00,000 --> 00:00:01,000\n"
    '<font size="28">[latitude: 10.0] [longitude: 20.0] '
    "[rel_alt: 1.000 abs_alt: 5.0]</font>\n\n"
    "2\n00:00:01,000 --> 00:00:02,000\n"
    '<font size="28">[latitude: 10.001] [longitude: 20.001] '
    "[rel_alt: 1.000 abs_alt: 6.0]</font>\n"
)
FLIGHT_B = FLIGHT_A.replace("10.0", "11.0").replace("20.0", "21.0")
NOT_TELEMETRY = "1\n00:00:00,000 --> 00:00:01,000\nJust a movie subtitle\n"


def _folder(tmp_path, files):
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


def test_flightmap_default_writes_html_into_directory(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A, "DJI_0002.SRT": FLIGHT_B})
    res = CliRunner().invoke(main, ["flightmap", str(tmp_path)])
    assert res.exit_code == 0, res.output
    out = tmp_path / "flightmap.html"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "leaflet@1.9.4" in text
    assert tmp_path.resolve().name in text  # default title = directory name
    assert "DJI_0001" in text and "DJI_0002" in text
    assert "Mapped 2 flights" in res.output


def test_flightmap_skips_non_telemetry_srt_with_summary(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A, "movie.srt": NOT_TELEMETRY})
    res = CliRunner().invoke(main, ["flightmap", str(tmp_path), "-v"])
    assert res.exit_code == 0, res.output
    assert "Mapped 1 of 2 flights" in res.output
    assert "movie" in res.output  # -v lists the skipped file


def test_flightmap_all_formats_share_base_name(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    out_base = tmp_path / "trip.html"
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "-f", "all", "-o", str(out_base)]
    )
    assert res.exit_code == 0, res.output
    for suffix in (".html", ".kml", ".geojson"):
        assert out_base.with_suffix(suffix).exists(), suffix
    data = json.loads(out_base.with_suffix(".geojson").read_text(encoding="utf-8"))
    assert data["features"][0]["properties"]["name"] == "DJI_0001"


def test_flightmap_recursive_scans_subdirectories(tmp_path):
    _folder(tmp_path, {"session1/DJI_0001.SRT": FLIGHT_A,
                       "session2/DJI_0001.SRT": FLIGHT_B})
    res = CliRunner().invoke(main, ["flightmap", str(tmp_path)])
    assert res.exit_code != 0  # non-recursive scan finds nothing
    res = CliRunner().invoke(main, ["flightmap", str(tmp_path), "-r"])
    assert res.exit_code == 0, res.output
    text = (tmp_path / "flightmap.html").read_text(encoding="utf-8")
    assert "session1/DJI_0001" in text and "session2/DJI_0001" in text


def test_flightmap_kml_format_and_title(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "-f", "kml", "--title", "Lennot"]
    )
    assert res.exit_code == 0, res.output
    text = (tmp_path / "flightmap.kml").read_text(encoding="utf-8")
    assert "<kml" in text and "Lennot" in text


def test_flightmap_redact_fuzz_coarsens_output(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A.replace("10.001", "10.123456")})
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "-f", "geojson", "--redact", "fuzz"]
    )
    assert res.exit_code == 0, res.output
    data = json.loads((tmp_path / "flightmap.geojson").read_text(encoding="utf-8"))
    coords = data["features"][0]["geometry"]["coordinates"]
    assert coords[1][1] == 10.123  # fuzzed to 3 decimals (~100 m)


def test_flightmap_no_srt_is_clean_error(tmp_path):
    res = CliRunner().invoke(main, ["flightmap", str(tmp_path)])
    assert res.exit_code != 0
    assert "No .SRT" in res.output
    assert res.exception is None or isinstance(res.exception, SystemExit)


def test_flightmap_no_gps_srt_is_clean_error(tmp_path):
    _folder(tmp_path, {"movie.srt": NOT_TELEMETRY})
    res = CliRunner().invoke(main, ["flightmap", str(tmp_path)])
    assert res.exit_code != 0
    assert "GPS" in res.output


def test_flightmap_single_format_output_honored_verbatim(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    out = tmp_path / "report.json"
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "-f", "geojson", "-o", str(out)]
    )
    assert res.exit_code == 0, res.output
    assert out.exists()  # extension NOT rewritten
    assert not (tmp_path / "report.geojson").exists()


def test_flightmap_write_failure_is_clean_error(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    res = CliRunner().invoke(
        main,
        ["flightmap", str(tmp_path), "-o", str(tmp_path / "no_such_dir" / "m.html")],
    )
    assert res.exit_code != 0
    assert "Could not write" in res.output
    assert res.exception is None or isinstance(res.exception, SystemExit)


def test_flightmap_quiet_suppresses_stdout(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    res = CliRunner().invoke(main, ["flightmap", str(tmp_path), "-q"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == ""


# Two size-split segments: B's telemetry resumes 1 s after A ends, ~1 m away.
SPLIT_A = (
    "1\n00:00:00,000 --> 00:00:01,000\n"
    '<font size="28">FrameCnt: 1, DiffTime: 1000ms\n'
    "2026-06-15 12:00:00.000\n"
    "[latitude: 34.0] [longitude: -84.0] [rel_alt: 1.000 abs_alt: 100.0]</font>\n\n"
    "2\n00:00:01,000 --> 00:00:02,000\n"
    '<font size="28">FrameCnt: 2, DiffTime: 1000ms\n'
    "2026-06-15 12:00:01.000\n"
    "[latitude: 34.00001] [longitude: -84.0] [rel_alt: 1.000 abs_alt: 101.0]</font>\n"
)
SPLIT_B = SPLIT_A.replace("12:00:00", "12:00:02").replace("12:00:01", "12:00:03")


def test_flightmap_tz_offset_option_sets_start_times(tmp_path):
    import os

    _folder(tmp_path, {"DJI_0001.SRT": SPLIT_A})
    # mtime a zip transfer rewrote: auto-detection would fail without the flag
    os.utime(tmp_path / "DJI_0001.SRT", (946684800.0, 946684800.0))
    res = CliRunner().invoke(
        main,
        ["flightmap", str(tmp_path), "-f", "geojson", "--tz-offset", "+2"],
    )
    assert res.exit_code == 0, res.output
    data = json.loads((tmp_path / "flightmap.geojson").read_text(encoding="utf-8"))
    # local 2026-06-15 12:00:00 at UTC+2 -> 10:00:00 UTC
    assert data["features"][0]["properties"]["start"] == "2026-06-15 10:00:00 UTC"


def test_flightmap_invalid_tz_offset_is_clean_error(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "--tz-offset", "nope"]
    )
    assert res.exit_code != 0
    assert "Invalid UTC offset" in res.output
    assert res.exception is None or isinstance(res.exception, SystemExit)


def test_flightmap_joins_size_split_recordings(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": SPLIT_A, "DJI_0002.SRT": SPLIT_B})
    res = CliRunner().invoke(main, ["flightmap", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "Mapped 1 flight" in res.output
    assert "Joined 2 files into 1 flight" in res.output
    text = (tmp_path / "flightmap.html").read_text(encoding="utf-8")
    assert '"segments": ["DJI_0001", "DJI_0002"]' in text


def test_flightmap_join_gap_zero_disables(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": SPLIT_A, "DJI_0002.SRT": SPLIT_B})
    res = CliRunner().invoke(main, ["flightmap", str(tmp_path), "--join-gap", "0"])
    assert res.exit_code == 0, res.output
    assert "Mapped 2 flights" in res.output
    assert "Joined" not in res.output


def test_flightmap_tile_style_selects_basemap(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "--tile-style", "opentopomap"]
    )
    assert res.exit_code == 0, res.output
    text = (tmp_path / "flightmap.html").read_text(encoding="utf-8")
    assert "tile.opentopomap.org" in text
    assert "tile.openstreetmap.org" not in text


def test_flightmap_tile_style_rejects_unknown(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "--tile-style", "watercolor"]
    )
    assert res.exit_code != 0
    assert "watercolor" in res.output


def test_flightmap_3d_writes_sibling_file(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A, "DJI_0002.SRT": FLIGHT_B})
    res = CliRunner().invoke(main, ["flightmap", str(tmp_path), "--3d"])
    assert res.exit_code == 0, res.output
    out = tmp_path / "flightmap-3d.html"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "maplibre-gl@5.24.0" in text
    assert "leaflet" not in text.lower()
    assert not (tmp_path / "flightmap.html").exists()  # 2D untouched


def test_flightmap_3d_output_override(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    out = tmp_path / "custom.html"
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "--3d", "-o", str(out)]
    )
    assert res.exit_code == 0, res.output
    assert out.exists()


def test_flightmap_3d_rejects_non_html_formats(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    for fmt in ("kml", "geojson", "all"):
        res = CliRunner().invoke(
            main, ["flightmap", str(tmp_path), "--3d", "-f", fmt]
        )
        assert res.exit_code != 0
        assert "--3d" in res.output


def test_flightmap_3d_warns_on_tile_style(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    res = CliRunner().invoke(
        main,
        ["flightmap", str(tmp_path), "--3d", "--tile-style", "opentopomap"],
    )
    assert res.exit_code == 0, res.output
    assert "--tile-style is ignored" in res.output
    assert (tmp_path / "flightmap-3d.html").exists()


def test_flightmap_3d_jsonl_reports_output(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "--3d", "--progress", "jsonl"]
    )
    assert res.exit_code == 0, res.output
    events = [json.loads(line) for line in res.output.splitlines() if line]
    result = next(e for e in events if e["event"] == "result")
    assert result["outputs"][0].endswith("flightmap-3d.html")
