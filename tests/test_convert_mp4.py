import json
from pathlib import Path

from dji_metadata_embedder import mp4_telemetry as mt
from dji_metadata_embedder.telemetry_converter import (
    extract_telemetry_to_gpx,
    summarize_sun,
)

_FIX = Path(__file__).parent / "fixtures" / "mp4_telemetry" / "air3s_g3j.json"


def _patch(monkeypatch):
    monkeypatch.setattr(mt, "_run_exiftool_json", lambda p: json.loads(_FIX.read_text()))


def test_gpx_from_mp4_uses_true_utc(monkeypatch, tmp_path):
    _patch(monkeypatch)
    mp4 = tmp_path / "clip.mp4"
    mp4.write_bytes(b"\x00")
    out = extract_telemetry_to_gpx(mp4, tmp_path / "clip.gpx")
    text = out.read_text()
    # true UTC from GPSDateTime, not shifted by mtime
    assert "2026-05-16T23:55:53Z" in text
    assert text.count("<trkpt") == 4


def test_verify_sun_from_mp4(monkeypatch, tmp_path):
    _patch(monkeypatch)
    mp4 = tmp_path / "clip.mp4"
    mp4.write_bytes(b"\x00")
    summary = summarize_sun(mp4)
    assert summary["points"] == 4
    assert summary["sun_computed"] == 4
    assert summary["utc_start"].startswith("2026-05-16T23:55:53")
