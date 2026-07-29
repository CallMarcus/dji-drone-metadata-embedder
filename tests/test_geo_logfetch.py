"""Unit tests for geo/logfetch.py — no network, ever."""
import json
from pathlib import Path

from dji_metadata_embedder.geo.logfetch import (
    _field_names,
    cache_path,
    select_fields,
)

# The header set of a real Flight Reader export (mirrors the FLIGHT_READER
# fixture in test_geo_flightlog.py).
FR_FIELDS = [
    "CUSTOM.date [local]", "CUSTOM.updateTime [local]", "OSD.flyTime [s]",
    "OSD.latitude", "OSD.longitude", "HOME.latitude", "HOME.longitude",
    "GIMBAL.pitch", "GIMBAL.yaw", "GIMBAL.yaw [360]", "GIMBAL.roll",
]


def test_cache_path_sits_beside_the_txt():
    txt = Path("/x/DJIFlightRecord_2026-07-27_[17-28-49].txt")
    assert cache_path(txt) == Path(
        "/x/DJIFlightRecord_2026-07-27_[17-28-49].flightreader.csv"
    )


def test_select_fields_picks_the_merge_columns():
    picked = select_fields(FR_FIELDS)
    assert picked is not None
    assert "GIMBAL.pitch" in picked
    assert "GIMBAL.yaw" in picked
    assert "CUSTOM.date [local]" in picked
    assert "CUSTOM.updateTime [local]" in picked
    assert "OSD.latitude" in picked and "OSD.longitude" in picked
    # No duplicates, and nothing the merge does not use.
    assert len(picked) == len(set(picked))
    assert "GIMBAL.roll" not in picked


def test_select_fields_prefers_utc_when_offered():
    picked = select_fields(FR_FIELDS + ["CUSTOM.updateTime [utc]"])
    assert picked is not None
    assert "CUSTOM.updateTime [utc]" in picked


def test_select_fields_returns_none_without_gimbal():
    assert select_fields(["OSD.latitude", "CUSTOM.date [local]"]) is None


def test_select_fields_returns_none_without_a_timestamp():
    assert select_fields(["GIMBAL.pitch", "GIMBAL.yaw"]) is None


def test_select_fields_skips_home_and_rc_coordinates():
    fields = [
        "HOME.latitude", "HOME.longitude", "RC.latitude",
        "OSD.latitude", "OSD.longitude",
        "CUSTOM.date [local]", "CUSTOM.updateTime [local]",
        "GIMBAL.pitch", "GIMBAL.yaw",
    ]
    picked = select_fields(fields)
    assert picked is not None
    assert "OSD.latitude" in picked and "OSD.longitude" in picked
    assert "HOME.latitude" not in picked
    assert "RC.latitude" not in picked


def test_select_fields_finds_signed_yaw_behind_the_360_variant():
    fields = [
        "GIMBAL.yaw [360]", "GIMBAL.yaw", "GIMBAL.pitch",
        "CUSTOM.date [local]", "CUSTOM.updateTime [local]",
    ]
    picked = select_fields(fields)
    assert picked is not None
    assert "GIMBAL.yaw" in picked  # signed yaw, despite [360] listed first


def test_select_fields_does_not_mistake_flytime_for_the_clock():
    fields = [
        "OSD.flyTime [s]", "CUSTOM.date [local]",
        "CUSTOM.updateTime [local]", "GIMBAL.pitch", "GIMBAL.yaw",
    ]
    picked = select_fields(fields)
    assert picked is not None
    assert "CUSTOM.updateTime [local]" in picked
    assert "OSD.flyTime [s]" not in picked


def test_field_names_accepts_a_list_of_strings():
    assert _field_names(json.dumps(FR_FIELDS).encode()) == FR_FIELDS


def test_field_names_accepts_objects_with_a_name_key():
    payload = json.dumps([{"name": "GIMBAL.pitch"}, {"name": "GIMBAL.yaw"}])
    assert _field_names(payload.encode()) == ["GIMBAL.pitch", "GIMBAL.yaw"]


def test_field_names_returns_empty_on_surprises():
    assert _field_names(b"not json at all") == []
    assert _field_names(json.dumps({"unexpected": 1}).encode()) == []
