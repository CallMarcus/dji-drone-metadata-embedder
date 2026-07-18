import json
import logging
import os
from datetime import datetime, timedelta

from dji_metadata_embedder.geo.flightmap import (
    flights_to_geojson,
    flights_to_kml,
    format_duration,
    scan_flights,
    write_flights_geojson,
    write_flights_kml,
)
from dji_metadata_embedder.geo.track import Track, TrackPoint


def _bracket_srt(*coords: tuple[float, float, float]) -> str:
    """Minimal bracket-format SRT with one block per (lat, lon, alt)."""
    blocks = []
    for i, (lat, lon, alt) in enumerate(coords):
        blocks.append(
            f"{i + 1}\n00:00:{i:02d},000 --> 00:00:{i + 1:02d},000\n"
            f'<font size="28">[latitude: {lat}] [longitude: {lon}] '
            f"[rel_alt: 1.000 abs_alt: {alt}]</font>\n"
        )
    return "\n".join(blocks)


FLIGHT_A = _bracket_srt((10.0, 20.0, 5.0), (10.001, 20.001, 6.0))
FLIGHT_B = _bracket_srt((11.0, 21.0, 7.0), (11.001, 21.001, 8.0))
SINGLE_FIX = _bracket_srt((12.0, 22.0, 9.0))
NOT_TELEMETRY = "1\n00:00:00,000 --> 00:00:01,000\nJust a movie subtitle\n"


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_scan_flights_builds_sorted_tracks_and_skips_non_telemetry(tmp_path):
    _write(tmp_path, "DJI_0002.SRT", FLIGHT_B)
    _write(tmp_path, "DJI_0001.SRT", FLIGHT_A)
    _write(tmp_path, "movie.srt", NOT_TELEMETRY)
    tracks, skipped = scan_flights(tmp_path)
    assert [t.name for t in tracks] == ["DJI_0001", "DJI_0002"]
    assert skipped == ["movie"]
    assert tracks[0].points[0].lat == 10.0


def test_scan_flights_non_recursive_ignores_subdirs(tmp_path):
    _write(tmp_path, "sub/DJI_0001.SRT", FLIGHT_A)
    tracks, skipped = scan_flights(tmp_path)
    assert tracks == [] and skipped == []


def test_scan_flights_recursive_labels_include_subdir(tmp_path):
    _write(tmp_path, "session1/DJI_0001.SRT", FLIGHT_A)
    _write(tmp_path, "session2/DJI_0001.SRT", FLIGHT_B)
    tracks, _ = scan_flights(tmp_path, recursive=True)
    assert [t.name for t in tracks] == ["session1/DJI_0001", "session2/DJI_0001"]


def test_scan_flights_fuzz_coarsens_coordinates(tmp_path):
    _write(tmp_path, "DJI_0001.SRT", _bracket_srt((10.123456, 20.654321, 5.0),
                                                  (10.123999, 20.654999, 6.0)))
    tracks, _ = scan_flights(tmp_path, redact="fuzz")
    p = tracks[0].points[0]
    assert (p.lat, p.lon) == (10.123, 20.654)


def _tracks() -> list[Track]:
    return [
        Track(name="DJI_0001", points=[
            TrackPoint(lat=10.0, lon=20.0, alt=5.0, timestamp="00:00:00,000",
                       utc=datetime(2026, 6, 15, 12, 0, 0)),
            TrackPoint(lat=10.001, lon=20.001, alt=6.5, timestamp="00:00:01,000",
                       utc=datetime(2026, 6, 15, 12, 4, 3)),
        ]),
        Track(name="one_fix", points=[
            TrackPoint(lat=12.0, lon=22.0, alt=9.0, timestamp="00:00:00,000")
        ]),
    ]


def test_flights_to_geojson_one_feature_per_flight():
    data = flights_to_geojson(_tracks())
    assert data["type"] == "FeatureCollection"
    line, point = data["features"]
    assert line["geometry"]["type"] == "LineString"
    assert line["geometry"]["coordinates"] == [[20.0, 10.0, 5.0], [20.001, 10.001, 6.5]]
    props = line["properties"]
    assert props["name"] == "DJI_0001"
    assert props["start"] == "2026-06-15 12:00:00 UTC"
    assert props["duration_s"] == 243
    assert (props["alt_min"], props["alt_max"]) == (5.0, 6.5)
    # RFC 7946 forbids a 1-position LineString: single-fix clips become Points.
    assert point["geometry"] == {"type": "Point", "coordinates": [22.0, 12.0, 9.0]}
    assert "start" not in point["properties"]  # no UTC -> no start/duration


def test_flights_to_geojson_embeds_relative_times_from_utc():
    # Playback (#267): every LineString carries times_s — per-point seconds
    # relative to the flight start — so viewers can animate the flight.
    line, point = flights_to_geojson(_tracks())["features"]
    assert line["properties"]["times_s"] == [0.0, 243.0]
    assert "times_s" not in point["properties"]  # a Point cannot animate


def test_times_fall_back_to_cue_seconds_without_utc():
    track = Track(name="f", points=[
        TrackPoint(lat=1.0, lon=2.0, alt=3.0, timestamp="00:00:01,000"),
        TrackPoint(lat=1.001, lon=2.001, alt=4.0, timestamp="00:00:03,500"),
    ])
    props = flights_to_geojson([track])["features"][0]["properties"]
    assert props["times_s"] == [0.0, 2.5]


def test_times_use_cues_when_any_utc_missing():
    # Mixed UTC availability must not mix two time bases inside one flight.
    track = Track(name="f", points=[
        TrackPoint(lat=1.0, lon=2.0, alt=3.0, timestamp="00:00:00,000",
                   utc=datetime(2026, 6, 15, 12, 0, 0)),
        TrackPoint(lat=1.001, lon=2.001, alt=4.0, timestamp="00:00:02,000"),
    ])
    props = flights_to_geojson([track])["features"][0]["properties"]
    assert props["times_s"] == [0.0, 2.0]


def test_times_clamped_monotonic():
    # A cue that jumps backwards (corrupt SRT) must not run the animation
    # backwards; the offending sample pins to the previous time.
    track = Track(name="f", points=[
        TrackPoint(lat=1.0, lon=2.0, alt=3.0, timestamp="00:00:05,000"),
        TrackPoint(lat=1.001, lon=2.001, alt=4.0, timestamp="00:00:04,000"),
        TrackPoint(lat=1.002, lon=2.002, alt=5.0, timestamp="00:00:06,000"),
    ])
    props = flights_to_geojson([track])["features"][0]["properties"]
    assert props["times_s"] == [0.0, 0.0, 1.0]


def test_flights_to_kml_one_placemark_per_flight():
    kml = flights_to_kml(_tracks(), title="My flights")
    assert kml.count("<Placemark>") == 2
    assert "<name>My flights</name>" in kml
    assert "<name>DJI_0001</name>" in kml
    assert "duration: 4:03" in kml
    assert "<LineString>" in kml and "<Point>" in kml
    assert "20.0,10.0,5.0 20.001,10.001,6.5" in kml


def test_flights_to_kml_escapes_names():
    tracks = [Track(name="a<b&c", points=[
        TrackPoint(lat=1.0, lon=2.0, alt=3.0, timestamp="00:00:00,000")])]
    kml = flights_to_kml(tracks, title="t<&>")
    assert "a<b&c" not in kml
    assert "a&lt;b&amp;c" in kml
    assert "t&lt;&amp;&gt;" in kml


def test_flight_properties_prefer_relative_height():
    # DJI's abs_alt reference is unreliable (can sit far below sea level), so
    # when the format carries rel_alt the popup fields use height-above-takeoff.
    track = Track(name="f", points=[
        TrackPoint(lat=1.0, lon=2.0, alt=-125.6, timestamp="00:00:00,000",
                   rel_alt=1.2),
        TrackPoint(lat=1.001, lon=2.001, alt=-66.8, timestamp="00:00:01,000",
                   rel_alt=96.4),
    ])
    props = flights_to_geojson([track])["features"][0]["properties"]
    assert (props["height_min"], props["height_max"]) == (1.2, 96.4)
    # abs alt stays available for GeoJSON consumers
    assert (props["alt_min"], props["alt_max"]) == (-125.6, -66.8)


def test_flight_properties_without_rel_alt_have_no_height():
    props = flights_to_geojson(_tracks())["features"][0]["properties"]
    assert "height_min" not in props


def test_kml_relative_height_preferred_and_readable():
    track = Track(name="f", points=[
        TrackPoint(lat=1.0, lon=2.0, alt=-125.6, timestamp="00:00:00,000",
                   rel_alt=1.2),
        TrackPoint(lat=1.001, lon=2.001, alt=-66.8, timestamp="00:00:01,000",
                   rel_alt=96.4),
    ])
    kml = flights_to_kml([track], title="t")
    assert "height: 1.2 to 96.4 m above takeoff" in kml


def test_kml_negative_altitude_range_readable():
    # Without rel_alt the abs range must not render as "-125.6--66.8 m".
    track = Track(name="f", points=[
        TrackPoint(lat=1.0, lon=2.0, alt=-125.6, timestamp="00:00:00,000"),
        TrackPoint(lat=1.001, lon=2.001, alt=-66.8, timestamp="00:00:01,000"),
    ])
    kml = flights_to_kml([track], title="t")
    assert "altitude: -125.6 to -66.8 m (as logged)" in kml
    assert "--" not in kml.split("<description>")[1].split("</description>")[0]


def test_format_duration():
    assert format_duration(0) == "0:00"
    assert format_duration(243) == "4:03"
    assert format_duration(3723) == "1:02:03"


def _dt_srt(start: datetime, coords: list[tuple[float, float, float]]) -> str:
    """Datetime-carrying bracket SRT (Air 3-style), one block per second."""
    blocks = []
    for i, (lat, lon, alt) in enumerate(coords):
        stamp = (start + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S.000")
        blocks.append(
            f"{i + 1}\n00:00:{i:02d},000 --> 00:00:{i + 1:02d},000\n"
            f'<font size="28">FrameCnt: {i + 1}, DiffTime: 1000ms\n'
            f"{stamp}\n"
            f"[iso: 100] [shutter: 1/500.0] [fnum: 1.8] [ev: 0] "
            f"[focal_len: 24.00] [latitude: {lat}] [longitude: {lon}] "
            f"[rel_alt: 1.000 abs_alt: {alt}] [ct: 5000] </font>\n"
        )
    return "\n".join(blocks)


T0 = datetime(2026, 6, 15, 12, 0, 0)
# Segment A ends at T0+2s / (34.00002, -84); B resumes 1 s later ~1 m away.
SEG_A = _dt_srt(T0, [(34.0, -84.0, 100.0), (34.00001, -84.0, 101.0),
                     (34.00002, -84.0, 102.0)])
SEG_B = _dt_srt(T0 + timedelta(seconds=3),
                [(34.00003, -84.0, 103.0), (34.00004, -84.0, 104.0)])
SEG_C = _dt_srt(T0 + timedelta(seconds=5),
                [(34.00005, -84.0, 105.0), (34.00006, -84.0, 106.0)])


def test_join_chains_size_split_segments(tmp_path):
    _write(tmp_path, "DJI_0001.SRT", SEG_A)
    _write(tmp_path, "DJI_0002.SRT", SEG_B)
    tracks, skipped = scan_flights(tmp_path)
    assert skipped == []
    assert len(tracks) == 1
    flight = tracks[0]
    assert flight.name == "DJI_0001"
    assert flight.segments == ["DJI_0001", "DJI_0002"]
    assert len(flight.points) == 5
    assert flight.points[-1].alt == 104.0  # B's points appended after A's


def test_join_chains_three_segments(tmp_path):
    _write(tmp_path, "DJI_0001.SRT", SEG_A)
    _write(tmp_path, "DJI_0002.SRT", SEG_B)
    _write(tmp_path, "DJI_0003.SRT", SEG_C)
    tracks, _ = scan_flights(tmp_path)
    assert len(tracks) == 1
    assert tracks[0].segments == ["DJI_0001", "DJI_0002", "DJI_0003"]
    assert len(tracks[0].points) == 7


def test_join_skips_nonconsecutive_file_numbers(tmp_path):
    # Photos share DJI's numbering counter, so a split can jump 0001 -> 0003.
    _write(tmp_path, "DJI_0001.SRT", SEG_A)
    _write(tmp_path, "DJI_0003.SRT", SEG_B)
    tracks, _ = scan_flights(tmp_path)
    assert len(tracks) == 1
    assert tracks[0].segments == ["DJI_0001", "DJI_0003"]


def test_no_join_when_time_gap_exceeds_threshold(tmp_path):
    late = _dt_srt(T0 + timedelta(minutes=10), [(34.00003, -84.0, 103.0),
                                                (34.00004, -84.0, 104.0)])
    _write(tmp_path, "DJI_0001.SRT", SEG_A)
    _write(tmp_path, "DJI_0002.SRT", late)
    tracks, _ = scan_flights(tmp_path)
    assert [t.name for t in tracks] == ["DJI_0001", "DJI_0002"]
    assert all(t.segments is None for t in tracks)


def test_no_join_when_position_jumps(tmp_path):
    far = _dt_srt(T0 + timedelta(seconds=3), [(34.1, -84.0, 103.0),
                                              (34.10001, -84.0, 104.0)])  # ~11 km
    _write(tmp_path, "DJI_0001.SRT", SEG_A)
    _write(tmp_path, "DJI_0002.SRT", far)
    tracks, _ = scan_flights(tmp_path)
    assert len(tracks) == 2


def test_no_join_across_directories(tmp_path):
    _write(tmp_path, "card1/DJI_0001.SRT", SEG_A)
    _write(tmp_path, "card2/DJI_0002.SRT", SEG_B)
    tracks, _ = scan_flights(tmp_path, recursive=True)
    assert len(tracks) == 2


def test_no_join_without_srt_datetimes(tmp_path):
    # Formats without a datetime line would leave gaps to be guessed from
    # file mtimes, which copies rewrite — so they are never joined.
    _write(tmp_path, "DJI_0001.SRT", FLIGHT_A)
    _write(tmp_path, "DJI_0002.SRT", FLIGHT_A)
    tracks, _ = scan_flights(tmp_path)
    assert len(tracks) == 2


def test_join_gap_zero_disables_joining(tmp_path):
    _write(tmp_path, "DJI_0001.SRT", SEG_A)
    _write(tmp_path, "DJI_0002.SRT", SEG_B)
    tracks, _ = scan_flights(tmp_path, join_gap=0)
    assert len(tracks) == 2


def test_join_applies_fuzz_after_joining(tmp_path):
    # Fuzz rounds to ~100 m; joining first means the continuity check still
    # sees the precise coordinates.
    _write(tmp_path, "DJI_0001.SRT", SEG_A)
    _write(tmp_path, "DJI_0002.SRT", SEG_B)
    tracks, _ = scan_flights(tmp_path, redact="fuzz")
    assert len(tracks) == 1
    assert all(p.lat == 34.0 and p.lon == -84.0 for p in tracks[0].points)


def test_joined_flight_properties_carry_segments(tmp_path):
    _write(tmp_path, "DJI_0001.SRT", SEG_A)
    _write(tmp_path, "DJI_0002.SRT", SEG_B)
    tracks, _ = scan_flights(tmp_path)
    feature = flights_to_geojson(tracks)["features"][0]
    assert feature["properties"]["segments"] == ["DJI_0001", "DJI_0002"]
    assert feature["properties"]["duration_s"] == 4  # spans both segments
    kml = flights_to_kml(tracks, title="t")
    assert kml.count("<Placemark>") == 1
    # Neutral wording: joins also catch quick stop/start re-records, so the
    # description must not claim the files were size-splits.
    assert "recorded across 2 files (DJI_0001 → DJI_0002)" in kml
    assert "size-split" not in kml


def _hz30_srt(start: datetime, seconds: float, lat0: float = 34.0) -> str:
    """30 Hz datetime-carrying SRT: one block per video frame, drifting north."""
    blocks = []
    n = int(seconds * 30)
    for i in range(n):
        t = start + timedelta(seconds=i / 30)
        stamp = t.strftime("%Y-%m-%d %H:%M:%S.") + f"{t.microsecond // 1000:03d}"
        cue_s, cue_ms = divmod(int(i * 1000 / 30), 1000)
        blocks.append(
            f"{i + 1}\n00:00:{cue_s:02d},{cue_ms:03d} --> 00:00:{cue_s:02d},{cue_ms + 33:03d}\n"
            f'<font size="28">FrameCnt: {i + 1}, DiffTime: 33ms\n'
            f"{stamp}\n"
            f"[latitude: {lat0 + i * 1e-6:.6f}] [longitude: -84.0] "
            f"[rel_alt: 1.000 abs_alt: 100.0]</font>\n"
        )
    return "\n".join(blocks)


def test_scan_flights_decimates_to_one_point_per_second(tmp_path):
    # 5 s of 30 Hz telemetry = 150 raw points; the map keeps ~1 Hz plus the
    # exact first and last fix so archive-scale HTML stays small.
    _write(tmp_path, "DJI_0001.SRT", _hz30_srt(T0, 5.0))
    tracks, _ = scan_flights(tmp_path)
    pts = tracks[0].points
    assert len(pts) <= 7
    assert pts[0].lat == 34.0                       # first fix kept verbatim
    assert pts[-1].lat == 34.0 + 149 * 1e-6         # last fix kept verbatim


def test_decimation_does_not_break_split_joining(tmp_path):
    # Continuity is checked on raw boundary points before decimation.
    _write(tmp_path, "DJI_0001.SRT", _hz30_srt(T0, 2.0))
    _write(tmp_path, "DJI_0002.SRT",
           _hz30_srt(T0 + timedelta(seconds=2), 2.0, lat0=34.0 + 60 * 1e-6))
    tracks, _ = scan_flights(tmp_path)
    assert len(tracks) == 1
    assert tracks[0].segments == ["DJI_0001", "DJI_0002"]
    assert len(tracks[0].points) <= 8               # ~4 s at 1 Hz + endpoints


# mtime far outside any recording window (2000-01-01 UTC) so timezone
# auto-detection is guaranteed to fail for the 2026-dated segments above.
_BOGUS_MTIME = 946684800.0


def test_scan_flights_explicit_tz_offset_resolves_utc(tmp_path):
    path = _write(tmp_path, "DJI_0001.SRT", SEG_A)
    os.utime(path, (_BOGUS_MTIME, _BOGUS_MTIME))
    tracks, _ = scan_flights(tmp_path, tz_offset=timedelta(hours=2))
    # local 12:00:00 at UTC+2 -> 10:00:00 UTC
    assert tracks[0].points[0].utc == T0 - timedelta(hours=2)


def test_scan_flights_aggregates_tz_detection_warnings(tmp_path, caplog):
    # Three distinct flights (hours apart, so never joined), all with mtimes
    # a zip transfer rewrote: one summary warning, not one per file.
    for i in range(3):
        srt = _dt_srt(T0 + timedelta(hours=2 * i),
                      [(10.0 + i, 20.0, 5.0), (10.001 + i, 20.0, 6.0)])
        path = _write(tmp_path, f"DJI_000{i + 1}.SRT", srt)
        os.utime(path, (_BOGUS_MTIME, _BOGUS_MTIME))
    with caplog.at_level(logging.WARNING):
        tracks, _ = scan_flights(tmp_path)
    assert len(tracks) == 3
    tz_warnings = [
        r.message for r in caplog.records
        if "Timezone auto-detection failed" in r.message
    ]
    assert len(tz_warnings) == 1
    assert "3" in tz_warnings[0]
    assert "--tz-offset" in tz_warnings[0]


def test_scan_flights_tz_offset_silences_detection_warnings(tmp_path, caplog):
    path = _write(tmp_path, "DJI_0001.SRT", SEG_A)
    os.utime(path, (_BOGUS_MTIME, _BOGUS_MTIME))
    with caplog.at_level(logging.WARNING):
        scan_flights(tmp_path, tz_offset=timedelta(hours=2))
    assert not any(
        "Timezone auto-detection failed" in r.message for r in caplog.records
    )


def test_writers_create_files(tmp_path):
    tracks = _tracks()
    geo = write_flights_geojson(tracks, tmp_path / "f.geojson")
    kml = write_flights_kml(tracks, tmp_path / "f.kml", title="t")
    assert json.loads(geo.read_text(encoding="utf-8"))["type"] == "FeatureCollection"
    assert "<kml" in kml.read_text(encoding="utf-8")
