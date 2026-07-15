"""Unit tests for the JSONL progress emitter (docs/PROGRESS_JSONL.md)."""

import io
import json
from pathlib import Path

import jsonschema

from dji_metadata_embedder.progress import (
    JsonlProgress,
    NullProgress,
    make_progress,
)

SCHEMA = json.loads(
    (Path(__file__).parent.parent / "docs" / "progress_jsonl.schema.json")
    .read_text(encoding="utf-8")
)


def _events(buf: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in buf.getvalue().splitlines()]


def test_jsonl_events_match_schema():
    buf = io.StringIO()
    p = JsonlProgress(buf)
    p.start("flightmap", total=2)
    p.advance(1, 2, item="DJI_0001.SRT")
    p.warning("no GPS", item="movie.srt")
    p.result(
        ok=True,
        outputs=["/tmp/flightmap.html"],
        summary={"flights": 1, "skipped": 1, "joined_files": 0},
    )
    p.error("boom")
    events = _events(buf)
    assert [e["event"] for e in events] == [
        "start", "progress", "warning", "result", "error",
    ]
    for e in events:
        jsonschema.validate(e, SCHEMA)
        assert e["v"] == 1


def test_start_omits_unknown_total():
    buf = io.StringIO()
    JsonlProgress(buf).start("photomap")
    (event,) = _events(buf)
    assert "total" not in event
    jsonschema.validate(event, SCHEMA)


def test_false_and_empty_result_fields_are_kept():
    buf = io.StringIO()
    JsonlProgress(buf).result(ok=False, outputs=[], summary={})
    (event,) = _events(buf)
    assert event["ok"] is False
    assert event["outputs"] == []
    assert event["summary"] == {}
    jsonschema.validate(event, SCHEMA)


def test_lines_are_compact_single_line_json():
    buf = io.StringIO()
    JsonlProgress(buf).advance(1, 3, item="å.JPG")  # non-ASCII stays literal
    raw = buf.getvalue()
    assert raw.endswith("\n") and raw.count("\n") == 1
    assert ": " not in raw and "å" in raw


def test_null_progress_writes_nothing(capsys):
    p = NullProgress()
    p.start("x")
    p.advance(1, 1)
    p.warning("w")
    p.result(True, [], {})
    p.error("e")
    assert capsys.readouterr().out == ""
    assert p.active is False


def test_make_progress_factory():
    assert isinstance(make_progress("jsonl"), JsonlProgress)
    assert make_progress("jsonl").active is True
    null = make_progress(None)
    assert isinstance(null, NullProgress)
    assert not isinstance(null, JsonlProgress)
