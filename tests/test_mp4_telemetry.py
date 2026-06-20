from datetime import datetime

import pytest

from dji_metadata_embedder import mp4_telemetry as mt


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (0, "00:00:00,000"),
        (0.0166833333333333, "00:00:00,016"),
        (41.5248166666667, "00:00:41,524"),
        (3661.5, "01:01:01,500"),
    ],
)
def test_sample_time_to_cue(seconds, expected):
    assert mt._sample_time_to_cue(seconds) == expected


def test_parse_gps_datetime_utc_naive():
    dt = mt._parse_gps_datetime("2026:05:16 23:55:53.017Z")
    assert dt == datetime(2026, 5, 16, 23, 55, 53, 17000)
    assert dt.tzinfo is None  # naive, matches the SRT dt convention


def test_parse_gps_datetime_none_on_garbage():
    assert mt._parse_gps_datetime("") is None
    assert mt._parse_gps_datetime("not-a-date") is None
