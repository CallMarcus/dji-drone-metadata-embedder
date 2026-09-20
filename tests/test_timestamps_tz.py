"""Wall-clock stamps that claim a zone must actually be in that zone (#561).

Two sites wrote ``datetime.now()`` (local, naive) where the output format
promised something else: the GPX ``<metadata><time>`` fallback appends a
literal ``Z``, and the validator report's ``timestamp`` is read by people in
any zone.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from dji_metadata_embedder import telemetry_converter
from dji_metadata_embedder.core.validator import validate_directory
from dji_metadata_embedder.telemetry_converter import extract_telemetry_to_gpx


def _write_dateless_srt(path: Path) -> Path:
    """An SRT with GPS but no absolute datetime line, so the GPX falls back."""
    block = (
        "{i}\n"
        "00:00:0{i},000 --> 00:00:0{i},033\n"
        '<font size="28">FrameCnt: {i}, DiffTime: 33ms\n'
        "[iso: 350] [shutter: 1/100.0] [fnum: 2.2] "
        "[latitude: 59.334591] [longitude: 18.063240] "
        "[rel_alt: 10.000 abs_alt: 30.000]</font>"
    )
    srt = path / "dateless.SRT"
    srt.write_text("\n\n".join(block.format(i=i) for i in range(1, 4)) + "\n")
    return srt


class _SplitClock(datetime):
    """``now()`` answers 12:00 for local time and 10:00 for UTC, so the test
    can tell which clock ended up behind the ``Z``."""

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        if tz is None:
            return cls(2026, 1, 1, 12, 0, 0)
        return cls(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc).astimezone(tz)


def test_gpx_fallback_metadata_time_is_utc(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry_converter, "datetime", _SplitClock)
    srt = _write_dateless_srt(tmp_path)
    out = tmp_path / "track.gpx"
    extract_telemetry_to_gpx(srt, out)
    m = re.search(r"<time>([^<]+)</time>", out.read_text())
    assert m is not None
    # The stamp says Z, so it must be the UTC clock, not the local one.
    assert m.group(1) == "2026-01-01T10:00:00Z"


def test_validator_report_timestamp_carries_an_offset(tmp_path):
    result = validate_directory(tmp_path)
    stamp = datetime.fromisoformat(result["timestamp"])
    assert stamp.tzinfo is not None
    assert stamp.utcoffset() is not None
