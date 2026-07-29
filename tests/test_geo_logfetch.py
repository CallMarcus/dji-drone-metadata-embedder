"""Unit tests for geo/logfetch.py — no network, ever."""
import csv
import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from dji_metadata_embedder.geo.flightlog import parse_flight_log
from dji_metadata_embedder.geo.logfetch import (
    LogFetchError,
    _field_names,
    cache_path,
    fetch_log,
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


# One plausible value per known header, for building throwaway exports.
_ROW_VALUES = {
    "CUSTOM.date [local]": "2026-07-27",
    "CUSTOM.updateTime [local]": "17:28:49.5",
    "CUSTOM.updateTime [utc]": "2026-07-27 15:28:49.0",
    "OSD.flyTime [s]": "12.3",
    "OSD.latitude": "59.3",
    "OSD.longitude": "18.1",
    "HOME.latitude": "59.0",
    "HOME.longitude": "18.0",
    "GIMBAL.pitch": "-45.0",
    "GIMBAL.yaw": "123.4",
    "GIMBAL.yaw [360]": "303.4",
    "GIMBAL.heading": "123.4",
    "GIMBAL.roll": "0.0",
}


def _one_row_csv(headers: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerow([_ROW_VALUES[h] for h in headers])
    return buf.getvalue()


@pytest.mark.parametrize(
    "headers",
    [
        FR_FIELDS,
        FR_FIELDS + ["CUSTOM.updateTime [utc]"],
        ["GIMBAL.pitch", "GIMBAL.heading",
         "CUSTOM.date [local]", "CUSTOM.updateTime [local]"],
        ["GIMBAL.pitch", "GIMBAL.yaw [360]",
         "CUSTOM.date [local]", "CUSTOM.updateTime [local]"],
    ],
)
def test_select_fields_stays_in_sync_with_the_parser(tmp_path, headers):
    """The contract with parse_flight_log: a CSV limited to the picked
    fields must parse to exactly the rows the full export would give —
    otherwise the API was asked for less than the merge consumes."""
    picked = select_fields(headers)
    assert picked is not None
    full = tmp_path / "full.csv"
    full.write_text(_one_row_csv(headers), encoding="utf-8")
    sub = tmp_path / "picked.csv"
    sub.write_text(
        _one_row_csv([h for h in headers if h in picked]), encoding="utf-8"
    )
    assert parse_flight_log(sub).rows == parse_flight_log(full).rows
    assert parse_flight_log(sub).time_base == parse_flight_log(full).time_base


def test_field_names_accepts_a_list_of_strings():
    assert _field_names(json.dumps(FR_FIELDS).encode()) == FR_FIELDS


def test_field_names_accepts_objects_with_a_name_key():
    payload = json.dumps([{"name": "GIMBAL.pitch"}, {"name": "GIMBAL.yaw"}])
    assert _field_names(payload.encode()) == ["GIMBAL.pitch", "GIMBAL.yaw"]


def test_field_names_returns_empty_on_surprises():
    assert _field_names(b"not json at all") == []
    assert _field_names(json.dumps({"unexpected": 1}).encode()) == []


# Flight Reader-shaped CSV (same shape test_geo_flightlog.py validates):
# quoted decimal-comma values, 12-hour local clock.
CSV_BODY = (
    '"CUSTOM.date [local]","CUSTOM.updateTime [local]","OSD.latitude",'
    '"OSD.longitude","GIMBAL.pitch","GIMBAL.yaw"\n'
    '"2026-07-27","2:00:00,0 pm","59,33459","18,06324","-60,0","-10,0"\n'
    '"2026-07-27","2:00:01,0 pm","59,33460","18,06325","-61,0","-9,0"\n'
).encode()

FIELDS_BODY = json.dumps([
    "CUSTOM.date [local]", "CUSTOM.updateTime [local]",
    "OSD.latitude", "OSD.longitude", "GIMBAL.pitch", "GIMBAL.yaw",
]).encode()


class FakeTransport:
    """urlopen-shaped: records every Request, replays queued responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, req, *, timeout=None):
        self.requests.append(req)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return io.BytesIO(result)


def _txt(tmp_path):
    txt = tmp_path / "DJIFlightRecord_2026-07-27_[17-28-49].txt"
    txt.write_bytes(b"\x0a encrypted-record-bytes")
    return txt


def test_fetch_log_happy_path_writes_the_cache(tmp_path):
    transport = FakeTransport([FIELDS_BODY, CSV_BODY])
    out = fetch_log(_txt(tmp_path), "sk_test", transport=transport)
    assert out.read_bytes() == CSV_BODY
    assert out.name == "DJIFlightRecord_2026-07-27_[17-28-49].flightreader.csv"
    fields_req, post_req = transport.requests
    assert fields_req.full_url == "https://api.flightreader.com/v1/fields"
    assert fields_req.get_header("Authorization") == "Bearer sk_test"
    assert post_req.full_url == "https://api.flightreader.com/v1/logs"
    assert post_req.get_method() == "POST"
    assert b"GIMBAL.pitch" in post_req.data          # fields preselection
    assert b"encrypted-record-bytes" in post_req.data  # the file itself
    assert "sk_test" not in repr(post_req.data)


def test_fetch_log_cache_hit_makes_no_network_calls(tmp_path):
    txt = _txt(tmp_path)
    cache = txt.with_name(txt.stem + ".flightreader.csv")
    cache.write_bytes(CSV_BODY)
    transport = FakeTransport([])
    out = fetch_log(txt, "sk_test", transport=transport)
    assert out == cache
    assert transport.requests == []


def test_fetch_log_falls_back_to_full_csv_when_fields_are_odd(tmp_path):
    transport = FakeTransport([b"weird payload", CSV_BODY])
    fetch_log(_txt(tmp_path), "sk_test", transport=transport)
    post_req = transport.requests[1]
    assert b'name="fields"' not in post_req.data  # no preselection sent


def _http_error(code, reason, body=b""):
    return HTTPError("https://api.flightreader.com/v1/x", code, reason,
                     None, io.BytesIO(body))


def test_401_on_fields_aborts_before_the_billable_call(tmp_path):
    transport = FakeTransport([_http_error(401, "Unauthorized")])
    with pytest.raises(LogFetchError, match="FLIGHTREADER_API_KEY"):
        fetch_log(_txt(tmp_path), "sk_bad", transport=transport)
    assert len(transport.requests) == 1  # POST /v1/logs never happened


def test_post_http_error_carries_status_and_provider_message(tmp_path):
    transport = FakeTransport(
        [FIELDS_BODY, _http_error(402, "Payment Required",
                                  b"insufficient balance")]
    )
    with pytest.raises(LogFetchError, match="HTTP 402.*insufficient balance"):
        fetch_log(_txt(tmp_path), "sk_test", transport=transport)


def test_network_error_says_rerunning_is_safe(tmp_path):
    transport = FakeTransport([FIELDS_BODY, URLError("timed out")])
    with pytest.raises(LogFetchError, match="re-running is safe"):
        fetch_log(_txt(tmp_path), "sk_test", transport=transport)


def test_non_csv_response_writes_nothing(tmp_path):
    txt = _txt(tmp_path)
    transport = FakeTransport([FIELDS_BODY, b'{"error": "oops"}'])
    with pytest.raises(LogFetchError, match="other than CSV"):
        fetch_log(txt, "sk_test", transport=transport)
    assert not (txt.with_name(txt.stem + ".flightreader.csv")).exists()


def test_verification_failure_keeps_the_paid_file(tmp_path):
    txt = _txt(tmp_path)
    no_gimbal = b'"OSD.latitude","OSD.longitude"\n"59,3","18,0"\n'
    transport = FakeTransport([FIELDS_BODY, no_gimbal])
    with pytest.raises(LogFetchError, match="fetched and kept"):
        fetch_log(txt, "sk_test", transport=transport)
    cache = txt.with_name(txt.stem + ".flightreader.csv")
    assert cache.read_bytes() == no_gimbal  # kept — it cost money


def test_requests_carry_the_dji_embed_user_agent(tmp_path):
    transport = FakeTransport([FIELDS_BODY, CSV_BODY])
    fetch_log(_txt(tmp_path), "sk_test", transport=transport)
    for req in transport.requests:
        assert req.get_header("User-agent") == "dji-embed"
