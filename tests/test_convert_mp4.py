import csv
import json
from pathlib import Path

from dji_metadata_embedder import mp4_telemetry as mt
from dji_metadata_embedder.telemetry_converter import (
    extract_telemetry_to_csv,
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


def test_csv_from_mp4_fills_geo_and_sun(monkeypatch, tmp_path):
    _patch(monkeypatch)
    mp4 = tmp_path / "clip.mp4"
    mp4.write_bytes(b"\x00")
    out = extract_telemetry_to_csv(mp4, tmp_path / "clip.csv")
    rows = list(csv.DictReader(out.open()))
    assert len(rows) == 4
    r0, r3 = rows[0], rows[3]
    assert round(float(r0["latitude"]), 4) == 51.4778
    assert r0["datetime_utc"] == "2026-05-16T23:55:53Z"
    assert r0["sun_azimuth"] and r0["sun_elevation"]   # computed from true UTC
    assert r3["rel_altitude"] == "5.4"
    assert r0["iso"] == "" and r0["shutter"] == ""      # SRT-only cols blank
