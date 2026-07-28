import json
import os
from datetime import datetime, timedelta, timezone

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


def test_link_base_requires_link_originals(tmp_path):
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "--link-base", "../footage"]
    )
    assert res.exit_code != 0
    assert "--link-base requires --link-originals" in res.output


def test_link_originals_allowed_with_fuzz_but_warns(tmp_path):
    """photomap permits the same pair and warns; flightmap matches it. The
    blend is disabled in the viewer instead."""
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    res = CliRunner().invoke(
        main,
        ["flightmap", str(tmp_path), "--3d", "--link-originals", "--redact", "fuzz"],
    )
    assert res.exit_code == 0
    assert "still carry exact GPS" in res.output


def test_link_originals_reaches_the_geojson_media_property(tmp_path):
    """Review I5 (#380): the only place --link-originals connects to the
    written output is `if link_originals: resolve_media(tracks, src,
    link_base)` in cli.py -- deleting it, or moving it below the write loop,
    left every other test in the suite green. This is the guard for that
    seam specifically."""
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    (tmp_path / "DJI_0001.MP4").write_bytes(b"fake video bytes")
    res = CliRunner().invoke(
        main,
        ["flightmap", str(tmp_path), "--format", "geojson", "--link-originals"],
    )
    assert res.exit_code == 0, res.output
    data = json.loads((tmp_path / "flightmap.geojson").read_text(encoding="utf-8"))
    assert data["features"][0]["properties"]["media"] == ["DJI_0001.MP4"]


def test_link_originals_with_flat_html_warns_dead_weight(tmp_path):
    """Review M2 (#380): the flat 2D map embeds the same media/cue_s/seg_i
    arrays the 3D crossfade needs, but nothing in the 2D viewer reads them --
    warn the way photomap does for its analogous case."""
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    (tmp_path / "DJI_0001.MP4").write_bytes(b"fake video bytes")
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "--link-originals"]
    )
    assert res.exit_code == 0, res.output
    assert "only benefits the 3D map" in res.output


def test_link_originals_3d_does_not_warn_dead_weight(tmp_path):
    """The 3D map is exactly the case --link-originals exists for -- no
    'dead weight' note should fire alongside it."""
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    (tmp_path / "DJI_0001.MP4").write_bytes(b"fake video bytes")
    res = CliRunner().invoke(
        main, ["flightmap", str(tmp_path), "--3d", "--link-originals"]
    )
    assert res.exit_code == 0, res.output
    assert "only benefits the 3D map" not in res.output


def test_link_originals_geojson_alone_does_not_warn_dead_weight(tmp_path):
    """GeoJSON is the intended --link-originals target (the media/cue_s/
    seg_i arrays are the deliverable there), so it must not be told they are
    dead weight."""
    _folder(tmp_path, {"DJI_0001.SRT": FLIGHT_A})
    (tmp_path / "DJI_0001.MP4").write_bytes(b"fake video bytes")
    res = CliRunner().invoke(
        main,
        ["flightmap", str(tmp_path), "--format", "geojson", "--link-originals"],
    )
    assert res.exit_code == 0, res.output
    assert "only benefits the 3D map" not in res.output


# --- #374: --flight-log merges gimbal attitude from a decoder CSV export ---


def _dt_srt(start, coords):
    """Datetime-carrying bracket SRT, one block per second."""
    blocks = []
    for i, (lat, lon, alt) in enumerate(coords):
        stamp = (start + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S.000")
        blocks.append(
            f"{i + 1}\n00:00:{i:02d},000 --> 00:00:{i + 1:02d},000\n"
            f'<font size="28">FrameCnt: {i + 1}, DiffTime: 1000ms\n'
            f"{stamp}\n"
            f"[iso: 100] [shutter: 1/500.0] [fnum: 1.8] [ev: 0] "
            f"[focal_len: 24.00] [latitude: {lat}] [longitude: {lon}] "
            f"[rel_alt: 10.000 abs_alt: {alt}] [ct: 5000] </font>\n"
        )
    return "\n".join(blocks)


T0 = datetime(2026, 7, 27, 12, 0, 0)
GIMBAL_LOG = """\
time(millisecond),datetime(utc),latitude,longitude,gimbal_heading(degrees),gimbal_pitch(degrees)
0,2026-07-27 12:00:00.0,59.33459,18.06324,350.0,-60.0
1000,2026-07-27 12:00:01.0,59.33460,18.06325,351.0,-61.0
2000,2026-07-27 12:00:02.0,59.33461,18.06326,352.0,-62.0
"""


def _gimbal_folder(tmp_path):
    srt = _dt_srt(T0, [(59.33459, 18.06324, 100.0),
                       (59.33460, 18.06325, 101.0),
                       (59.33461, 18.06326, 102.0)])
    folder = _folder(tmp_path, {"DJI_0001.SRT": srt})
    # mtime at the recording end so tz auto-detection resolves offset 0
    # (SRT wall-clock == UTC), matching the log's UTC column exactly.
    end = (T0 + timedelta(seconds=3)).replace(tzinfo=timezone.utc).timestamp()
    os.utime(folder / "DJI_0001.SRT", (end, end))
    log = folder / "log.csv"
    log.write_text(GIMBAL_LOG, encoding="utf-8")
    return folder, log


def test_flightmap_flight_log_merges_gimbal_into_the_geojson(tmp_path):
    folder, log = _gimbal_folder(tmp_path)
    out = folder / "out.geojson"
    res = CliRunner().invoke(main, [
        "flightmap", str(folder), "-f", "geojson", "-o", str(out),
        "--flight-log", str(log),
    ])
    assert res.exit_code == 0, res.output
    assert "DJI_0001" in res.output and "gimbal" in res.output.lower()
    assert "exact UTC join" in res.output
    props = json.loads(out.read_text(encoding="utf-8"))[
        "features"][0]["properties"]
    assert props["gyaw_deg"] == [-10.0, -9.0, -8.0]
    assert props["gpitch_deg"] == [-60.0, -61.0, -62.0]


def test_flightmap_flight_log_unmatched_notes_and_still_maps(tmp_path):
    folder, log = _gimbal_folder(tmp_path)
    log.write_text(GIMBAL_LOG.replace("2026-07-27", "2026-01-01"),
                   encoding="utf-8")
    out = folder / "out.geojson"
    res = CliRunner().invoke(main, [
        "flightmap", str(folder), "-f", "geojson", "-o", str(out),
        "--flight-log", str(log),
    ])
    assert res.exit_code == 0, res.output
    assert "did not match any flight" in res.output
    props = json.loads(out.read_text(encoding="utf-8"))[
        "features"][0]["properties"]
    assert "gyaw_deg" not in props


def test_flightmap_flight_log_bad_export_fails_loudly(tmp_path):
    folder, log = _gimbal_folder(tmp_path)
    log.write_text("datetime(utc),latitude\n2026-07-27 12:00:00.0,59.0\n",
                   encoding="utf-8")
    res = CliRunner().invoke(main, [
        "flightmap", str(folder), "--flight-log", str(log),
    ])
    assert res.exit_code != 0
    assert "gimbal" in res.output.lower()
