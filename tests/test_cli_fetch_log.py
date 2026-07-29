"""CLI tests for fetch-log — fetch_log itself is always monkeypatched."""
import json
from pathlib import Path

from click.testing import CliRunner

import dji_metadata_embedder.cli as cli_mod
from dji_metadata_embedder.cli import main
from dji_metadata_embedder.geo.logfetch import LogFetchError, cache_path

KEY_ENV = {"FLIGHTREADER_API_KEY": "sk_test"}


def _record(tmp_path, name="DJIFlightRecord_2026-07-27_[17-28-49].txt"):
    txt = tmp_path / name
    txt.write_bytes(b"\x0a record")
    return txt


def _fake_ok(calls):
    def fake(txt, key):
        calls.append((Path(txt), key))
        out = cache_path(Path(txt))
        out.write_bytes(b"csv")
        return out
    return fake


def test_consent_shown_then_fetches(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli_mod, "fetch_log", _fake_ok(calls))
    txt = _record(tmp_path)
    res = CliRunner().invoke(
        main, ["fetch-log", str(txt)], input="y\n", env=KEY_ENV
    )
    assert res.exit_code == 0, res.output
    assert "uploads your entire flight log to Flight Reader" in res.output
    assert "deleted immediately" in res.output
    assert "Wrote DJIFlightRecord_2026-07-27_[17-28-49].flightreader.csv" \
        in res.output
    assert calls == [(txt, "sk_test")]


def test_declining_consent_sends_nothing_and_exits_zero(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli_mod, "fetch_log", _fake_ok(calls))
    txt = _record(tmp_path)
    res = CliRunner().invoke(
        main, ["fetch-log", str(txt)], input="n\n", env=KEY_ENV
    )
    assert res.exit_code == 0, res.output
    assert "Nothing sent." in res.output
    assert calls == []


def test_cache_hit_skips_consent_entirely(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli_mod, "fetch_log", _fake_ok(calls))
    txt = _record(tmp_path)
    cache_path(txt).write_bytes(b"already here")
    res = CliRunner().invoke(main, ["fetch-log", str(txt)], env=KEY_ENV)
    assert res.exit_code == 0, res.output
    assert "already exists" in res.output
    assert "delete it to refetch" in res.output
    assert "uploads your entire flight log" not in res.output
    assert calls == []


def test_yes_skips_the_prompt(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli_mod, "fetch_log", _fake_ok(calls))
    txt = _record(tmp_path)
    res = CliRunner().invoke(
        main, ["fetch-log", "--yes", str(txt)], env=KEY_ENV
    )
    assert res.exit_code == 0, res.output
    assert calls and calls[0][0] == txt


def test_jsonl_without_yes_is_a_usage_error(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_mod, "fetch_log", _fake_ok([]))
    txt = _record(tmp_path)
    res = CliRunner().invoke(
        main, ["fetch-log", "--progress", "jsonl", str(txt)], env=KEY_ENV
    )
    assert res.exit_code == 2
    assert "--yes" in res.output


def test_jsonl_without_env_key_names_the_variable(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_mod, "fetch_log", _fake_ok([]))
    monkeypatch.delenv("FLIGHTREADER_API_KEY", raising=False)
    txt = _record(tmp_path)
    res = CliRunner().invoke(
        main, ["fetch-log", "--progress", "jsonl", "--yes", str(txt)]
    )
    assert res.exit_code != 0
    assert "FLIGHTREADER_API_KEY" in res.output


def test_missing_env_key_prompts_hidden(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli_mod, "fetch_log", _fake_ok(calls))
    monkeypatch.delenv("FLIGHTREADER_API_KEY", raising=False)
    txt = _record(tmp_path)
    res = CliRunner().invoke(
        main, ["fetch-log", str(txt)], input="y\nsk_prompted\n"
    )
    assert res.exit_code == 0, res.output
    assert calls == [(txt, "sk_prompted")]
    assert "sk_prompted" not in res.output  # hidden input never echoes


def test_one_failure_continues_and_exits_nonzero(tmp_path, monkeypatch):
    good = _record(tmp_path, "DJIFlightRecord_A.txt")
    bad = _record(tmp_path, "DJIFlightRecord_B.txt")

    def fake(txt, key):
        if Path(txt) == bad:
            raise LogFetchError("DJIFlightRecord_B.txt: the API answered "
                                "HTTP 402: insufficient balance")
        out = cache_path(Path(txt))
        out.write_bytes(b"csv")
        return out

    monkeypatch.setattr(cli_mod, "fetch_log", fake)
    res = CliRunner().invoke(
        main, ["fetch-log", "--yes", str(good), str(bad)], env=KEY_ENV
    )
    assert res.exit_code != 0
    assert "Wrote DJIFlightRecord_A.flightreader.csv" in res.output
    assert "HTTP 402" in res.output
    assert "1 of 2 records failed" in res.output


def test_jsonl_stdout_is_pure_json_and_ends_in_result(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli_mod, "fetch_log", _fake_ok(calls))
    fresh = _record(tmp_path, "DJIFlightRecord_A.txt")
    cached = _record(tmp_path, "DJIFlightRecord_B.txt")
    cache_path(cached).write_bytes(b"already here")
    res = CliRunner().invoke(
        main,
        ["fetch-log", "--progress", "jsonl", "--yes", str(fresh), str(cached)],
        env=KEY_ENV,
    )
    assert res.exit_code == 0, res.output
    lines = [ln for ln in res.output.splitlines() if ln.strip()]
    events = [json.loads(ln) for ln in lines]  # every line must parse
    assert events[-1]["event"] == "result"


def test_jsonl_cache_hit_only_run_still_ends_in_result(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_mod, "fetch_log", _fake_ok([]))
    txt = _record(tmp_path)
    cache_path(txt).write_bytes(b"already here")
    res = CliRunner().invoke(
        main, ["fetch-log", "--progress", "jsonl", "--yes", str(txt)],
        env=KEY_ENV,
    )
    assert res.exit_code == 0, res.output
    events = [json.loads(ln) for ln in res.output.splitlines() if ln.strip()]
    assert events[-1]["event"] == "result"
