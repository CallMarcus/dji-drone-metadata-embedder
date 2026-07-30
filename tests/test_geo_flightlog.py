"""Flight-log CSV ingestion (#374): parsing, alignment, and gimbal merge.

The mapping layer is vendor-neutral by design — columns are matched by
semantics, numbers are locale-aware, and unparseable values fail loudly
(the spike proved a skip-on-error parser silently degrades a complete
dataset into a plausible-looking sparse one). Fixtures mirror the two
known producers: a Flight Reader-shaped export in a decimal-comma locale
and an Airdata-shaped export with a UTC column.
"""

from datetime import datetime, timedelta

import pytest

from dji_metadata_embedder.geo.flightlog import (
    FlightLogError,
    merge_gimbal,
    parse_flight_log,
)
from dji_metadata_embedder.geo.track import Track, TrackPoint


def _write(tmp_path, name, content, encoding="utf-8"):
    path = tmp_path / name
    path.write_text(content, encoding=encoding)
    return path


# Airdata-shaped: dot decimals, combined UTC datetime column, 0-360 heading.
AIRDATA = """\
time(millisecond),datetime(utc),latitude,longitude,gimbal_heading(degrees),gimbal_pitch(degrees)
0,2026-07-27 12:00:00.0,59.33459,18.06324,350.0,-60.0
1000,2026-07-27 12:00:01.0,59.33460,18.06325,351.0,-61.0
2000,2026-07-27 12:00:02.0,59.33461,18.06326,352.0,-62.0
3000,2026-07-27 12:00:03.0,59.33462,18.06327,353.0,-63.0
4000,2026-07-27 12:00:04.0,59.33463,18.06328,354.0,-64.0
"""

# Flight Reader-shaped: quoted decimal-comma values, 12-hour local clock
# with a comma seconds-fraction, both yaw variants, HOME columns present.
FLIGHT_READER = """\
"CUSTOM.date [local]","CUSTOM.updateTime [local]","OSD.flyTime [s]","OSD.latitude","OSD.longitude","HOME.latitude","HOME.longitude","GIMBAL.pitch","GIMBAL.yaw","GIMBAL.yaw [360]","GIMBAL.roll"
"2026-07-27","2:00:00,0 pm","0,2","59,33459","18,06324","59,33459","18,06324","-60,0","-10,0","350,0","0,0"
"2026-07-27","2:00:01,0 pm","1,2","59,33460","18,06325","59,33459","18,06324","-61,0","-9,0","351,0","0,0"
"2026-07-27","2:00:02,0 pm","2,2","59,33461","18,06326","59,33459","18,06324","-62,0","-8,0","352,0","0,0"
"2026-07-27","2:00:03,0 pm","3,2","59,33462","18,06327","59,33459","18,06324","-63,0","-7,0","353,0","0,0"
"2026-07-27","2:00:04,0 pm","4,2","59,33463","18,06328","59,33459","18,06324","-64,0","-6,0","354,0","0,0"
"""


def test_parses_an_airdata_shaped_export_with_utc(tmp_path):
    log = parse_flight_log(_write(tmp_path, "log.csv", AIRDATA))
    assert log.time_base == "utc"
    assert len(log.rows) == 5
    first = log.rows[0]
    assert first.utc == datetime(2026, 7, 27, 12, 0, 0)
    assert first.pitch == -60.0
    assert first.yaw == -10.0  # 350 in the 0-360 frame, normalised signed
    assert first.lat == 59.33459
    assert first.lon == 18.06324


# Flight Reader with the UTC option on: UTC arrives as a date + clock
# PAIR, never one combined column (live API E2E, 2026-07-30; the clock
# is 12-hour with a dot fraction, e.g. "3:28:49.49 pm" for 15:28:49Z).
FLIGHT_READER_UTC = """\
"CUSTOM.date [UTC]","CUSTOM.updateTime [UTC]","CUSTOM.date [local]","CUSTOM.updateTime [local]","OSD.latitude","OSD.longitude","GIMBAL.pitch","GIMBAL.yaw"
"2026-07-27","3:28:49.49 pm","2026-07-27","5:28:49,49 pm","59,33459","18,06324","-60,0","-10,0"
"2026-07-27","3:28:50.49 pm","2026-07-27","5:28:50,49 pm","59,33460","18,06325","-61,0","-9,0"
"""


def test_parses_an_epoch_timestamp_column(tmp_path):
    # CUSTOM.updateTime [epoch] from the API: immune to date-order
    # ambiguity and locale; magnitude tells seconds from milliseconds.
    csv = (
        "CUSTOM.updateTime [epoch],GIMBAL.pitch,GIMBAL.yaw\n"
        "1785510529.49,-60.0,-10.0\n"
        "1785510530490,-61.0,-9.0\n"
    )
    log = parse_flight_log(_write(tmp_path, "log.csv", csv))
    assert log.time_base == "utc"
    assert log.rows[0].utc == datetime(2026, 7, 31, 15, 8, 49, 490000)
    assert log.rows[1].utc == datetime(2026, 7, 31, 15, 8, 50, 490000)
    assert log.columns["utc"] == "CUSTOM.updateTime [epoch]"


def test_epoch_column_refuses_an_empty_value(tmp_path):
    csv = (
        "CUSTOM.updateTime [epoch],GIMBAL.pitch,GIMBAL.yaw\n"
        ",-60.0,-10.0\n"
    )
    with pytest.raises(FlightLogError, match="empty epoch"):
        parse_flight_log(_write(tmp_path, "log.csv", csv))


def test_parses_flight_reader_utc_as_a_date_and_clock_pair(tmp_path):
    log = parse_flight_log(_write(tmp_path, "log.csv", FLIGHT_READER_UTC))
    assert log.time_base == "utc"
    first = log.rows[0]
    assert first.utc == datetime(2026, 7, 27, 15, 28, 49, 490000)
    assert first.pitch == -60.0
    assert log.columns["utc"] == "CUSTOM.date [UTC] + CUSTOM.updateTime [UTC]"


def test_parses_a_flight_reader_shaped_export_with_comma_decimals(tmp_path):
    log = parse_flight_log(_write(tmp_path, "log.csv", FLIGHT_READER))
    assert log.time_base == "local"
    first = log.rows[0]
    assert first.local == datetime(2026, 7, 27, 14, 0, 0)
    assert first.utc is None
    assert first.pitch == -60.0
    assert first.yaw == -10.0  # the signed GIMBAL.yaw column, verbatim
    assert first.lat == 59.33459


def test_prefers_the_signed_yaw_column_over_the_360_variant(tmp_path):
    # FLIGHT_READER carries both; the signed one must win (no reprojection).
    log = parse_flight_log(_write(tmp_path, "log.csv", FLIGHT_READER))
    assert [r.yaw for r in log.rows] == [-10.0, -9.0, -8.0, -7.0, -6.0]


def test_normalises_a_360_only_yaw_column(tmp_path):
    csv = (
        '"CUSTOM.date [local]","CUSTOM.updateTime [local]",'
        '"GIMBAL.pitch","GIMBAL.yaw [360]"\n'
        '"2026-07-27","2:00:00,0 pm","-60,0","182,5"\n'
    )
    log = parse_flight_log(_write(tmp_path, "log.csv", csv))
    assert log.rows[0].yaw == -177.5


def test_home_coordinates_are_not_the_aircraft(tmp_path):
    csv = (
        '"CUSTOM.date [local]","CUSTOM.updateTime [local]",'
        '"HOME.latitude","HOME.longitude","GIMBAL.pitch","GIMBAL.yaw"\n'
        '"2026-07-27","2:00:00,0 pm","59,0","18,0","-60,0","-10,0"\n'
    )
    log = parse_flight_log(_write(tmp_path, "log.csv", csv))
    assert log.rows[0].lat is None
    assert log.rows[0].lon is None


def test_missing_gimbal_columns_error_names_what_to_enable(tmp_path):
    csv = "datetime(utc),latitude\n2026-07-27 12:00:00.0,59.0\n"
    with pytest.raises(FlightLogError) as e:
        parse_flight_log(_write(tmp_path, "log.csv", csv))
    msg = str(e.value)
    assert "gimbal" in msg.lower()
    assert "pitch" in msg.lower() and "yaw" in msg.lower()


def test_no_time_columns_error_recommends_the_utc_option(tmp_path):
    csv = "GIMBAL.pitch,GIMBAL.yaw\n-60.0,-10.0\n"
    with pytest.raises(FlightLogError) as e:
        parse_flight_log(_write(tmp_path, "log.csv", csv))
    assert "UTC" in str(e.value)


def test_unparseable_number_fails_loudly_with_its_location(tmp_path):
    bad = AIRDATA.replace("352.0", "three-five-two")
    with pytest.raises(FlightLogError) as e:
        parse_flight_log(_write(tmp_path, "log.csv", bad))
    msg = str(e.value)
    assert "gimbal_heading(degrees)" in msg
    assert "three-five-two" in msg


def test_empty_cells_are_missing_not_errors(tmp_path):
    sparse = AIRDATA.replace("352.0", "")
    log = parse_flight_log(_write(tmp_path, "log.csv", sparse))
    assert log.rows[2].yaw is None
    assert log.rows[1].yaw == -9.0


def test_a_value_with_both_separators_is_an_error(tmp_path):
    bad = AIRDATA.replace("350.0", '"1.234,5"')
    with pytest.raises(FlightLogError):
        parse_flight_log(_write(tmp_path, "log.csv", bad))


def test_bom_and_semicolon_delimiters_are_tolerated(tmp_path):
    semi = (
        "datetime(utc);GIMBAL.pitch;GIMBAL.yaw\n"
        "2026-07-27 12:00:00.0;-60.0;-10.0\n"
    )
    log = parse_flight_log(
        _write(tmp_path, "log.csv", semi, encoding="utf-8-sig"))
    assert log.rows[0].pitch == -60.0


def test_an_ambiguous_local_date_is_refused(tmp_path):
    csv = (
        '"CUSTOM.date [local]","CUSTOM.updateTime [local]",'
        '"GIMBAL.pitch","GIMBAL.yaw"\n'
        '"07/06/2026","2:00:00,0 pm","-60,0","-10,0"\n'
    )
    with pytest.raises(FlightLogError) as e:
        parse_flight_log(_write(tmp_path, "log.csv", csv))
    assert "UTC" in str(e.value)  # points at the unambiguous fix


def test_an_unambiguous_slash_date_is_accepted(tmp_path):
    csv = (
        '"CUSTOM.date [local]","CUSTOM.updateTime [local]",'
        '"GIMBAL.pitch","GIMBAL.yaw"\n'
        '"7/27/2026","2:00:00,0 pm","-60,0","-10,0"\n'
    )
    log = parse_flight_log(_write(tmp_path, "log.csv", csv))
    assert log.rows[0].local == datetime(2026, 7, 27, 14, 0, 0)


def _track(start: datetime, n: int = 5) -> Track:
    return Track(name="DJI_0001", points=[
        TrackPoint(lat=59.33459 + i * 1e-5, lon=18.06324 + i * 1e-5,
                   alt=100.0 + i, timestamp=f"00:00:0{i},000",
                   utc=start + timedelta(seconds=i))
        for i in range(n)
    ])


def test_exact_utc_join_fills_gimbal_and_reports(tmp_path):
    log = parse_flight_log(_write(tmp_path, "log.csv", AIRDATA))
    track = _track(datetime(2026, 7, 27, 12, 0, 0))
    report = merge_gimbal(track, log)
    assert report.merged
    assert report.mode == "utc"
    assert report.matched == 5
    assert [p.gimbal_yaw for p in track.points] == [
        -10.0, -9.0, -8.0, -7.0, -6.0]
    assert [p.gimbal_pitch for p in track.points] == [
        -60.0, -61.0, -62.0, -63.0, -64.0]
    assert report.gps_median_m is not None and report.gps_median_m < 50


def test_srt_borne_gimbal_wins(tmp_path):
    log = parse_flight_log(_write(tmp_path, "log.csv", AIRDATA))
    track = _track(datetime(2026, 7, 27, 12, 0, 0))
    track.points[0].gimbal_yaw = 42.0
    track.points[0].gimbal_pitch = -5.0
    merge_gimbal(track, log)
    assert track.points[0].gimbal_yaw == 42.0
    assert track.points[0].gimbal_pitch == -5.0
    assert track.points[1].gimbal_yaw == -9.0


def test_local_log_derives_the_offset_and_says_so(tmp_path):
    log = parse_flight_log(_write(tmp_path, "log.csv", FLIGHT_READER))
    track = _track(datetime(2026, 7, 27, 12, 0, 0))  # local is UTC+2
    report = merge_gimbal(track, log)
    assert report.merged
    assert report.mode == "derived"
    assert report.offset == timedelta(hours=2)
    assert track.points[2].gimbal_pitch == -62.0


def test_gps_mismatch_refuses_even_with_a_matching_clock(tmp_path):
    elsewhere = AIRDATA.replace("59.334", "40.712")  # different city
    log = parse_flight_log(_write(tmp_path, "log.csv", elsewhere))
    track = _track(datetime(2026, 7, 27, 12, 0, 0))
    report = merge_gimbal(track, log)
    assert not report.merged
    assert report.matched == 0
    assert "GPS" in report.reason
    assert all(p.gimbal_yaw is None for p in track.points)


def test_no_time_overlap_is_refused(tmp_path):
    log = parse_flight_log(_write(tmp_path, "log.csv", AIRDATA))
    track = _track(datetime(2026, 7, 28, 9, 0, 0))  # next day
    report = merge_gimbal(track, log)
    assert not report.merged
    assert all(p.gimbal_yaw is None for p in track.points)


def test_points_beyond_the_tolerance_are_not_filled(tmp_path):
    log = parse_flight_log(_write(tmp_path, "log.csv", AIRDATA))
    track = _track(datetime(2026, 7, 27, 12, 0, 0), n=5)
    track.points.append(TrackPoint(
        lat=59.335, lon=18.064, alt=110.0, timestamp="00:00:30,000",
        utc=datetime(2026, 7, 27, 12, 0, 30)))  # log ends at 12:00:04
    report = merge_gimbal(track, log)
    assert report.merged
    assert report.matched == 5
    assert track.points[-1].gimbal_yaw is None
