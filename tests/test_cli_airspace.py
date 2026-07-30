"""CLI tests for flightmap --airspace (#413 PR 2)."""
import io
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import URLError

from click.testing import CliRunner

from dji_metadata_embedder.cli import main
from dji_metadata_embedder.geo.airspace import fetch as airspace_fetch

SAMPLES = Path(__file__).parent.parent / "samples"


def _dt_srt(start, coords):
    blocks = []
    for i, (lat, lon, alt) in enumerate(coords):
        stamp = (start + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S.000")
        blocks.append(
            f"{i + 1}\n00:00:{i:02d},000 --> 00:00:{i + 1:02d},000\n"
            f'<font size="28">FrameCnt: {i + 1}, DiffTime: 1000ms\n'
            f"{stamp}\n"
            f"[iso: 100] [shutter: 1/500.0] [fnum: 1.8] [ev: 0] "
            f"[focal_len: 24.00] [latitude: {lat}] [longitude: {lon}] "
            f"[rel_alt: 10.000 abs_alt: {alt}] [ct: 5000] </font>\n"
        )
    return "\n".join(blocks)


T0 = datetime(2026, 7, 30, 12, 0, 0)


def _srt_dir(tmp_path):
    d = tmp_path / "flights"
    d.mkdir()
    coords = [(49.615 + i * 0.001, 6.19, 300.0 + i) for i in range(4)]
    (d / "LUX0001.SRT").write_text(_dt_srt(T0, coords), encoding="utf-8")
    return d


class FakeTransport:
    def __init__(self, bodies):
        self.bodies = list(bodies)
        self.calls = 0

    def __call__(self, req, timeout=None):
        self.calls += 1
        if not self.bodies:
            raise URLError("no more fake responses queued")
        resp = io.BytesIO(self.bodies.pop(0))
        resp.__enter__ = lambda *a: resp  # type: ignore[method-assign]
        resp.__exit__ = lambda *a: False  # type: ignore[method-assign]
        return resp


def _lux_body():
    return (SAMPLES / "airspace" / "ed269-lu.json").read_bytes()


def test_airspace_overlays_the_html_map(tmp_path, monkeypatch):
    fake = FakeTransport([_lux_body()])
    monkeypatch.setattr(airspace_fetch, "urlopen", fake)
    d = _srt_dir(tmp_path)
    result = CliRunner().invoke(main, ["flightmap", str(d), "--airspace"])
    assert result.exit_code == 0, result.output
    html = (d / "flightmap.html").read_text(encoding="utf-8")
    assert 'id="airspace-data"' in html
    assert "Airspace zones" in html
    assert (d / "airspace-cache").is_dir()
    assert fake.calls == 1


def test_all_plus_airspace_fetches_once_record_hits_cache(tmp_path, monkeypatch):
    from dji_metadata_embedder.geo import record as record_mod

    fake = FakeTransport([_lux_body()])          # exactly ONE network body
    monkeypatch.setattr(airspace_fetch, "urlopen", fake)
    # the record path resolves record.urlopen; terrain outruns the empty
    # queue and degrades to a stated note, airspace must hit the cache
    monkeypatch.setattr(record_mod, "urlopen", FakeTransport([]))
    d = _srt_dir(tmp_path)
    result = CliRunner().invoke(
        main, ["flightmap", str(d), "-f", "all", "--airspace"]
    )
    assert result.exit_code == 0, result.output
    assert (d / "flightmap.html").exists()
    assert (d / "flight-record.html").exists()
    assert fake.calls == 1
    assert "cached" in result.output.lower()


def test_airspace_refuses_redact(tmp_path):
    d = _srt_dir(tmp_path)
    result = CliRunner().invoke(
        main, ["flightmap", str(d), "--airspace", "--redact", "fuzz"]
    )
    assert result.exit_code != 0
    assert "exact coordinates" in result.output


def test_airspace_refuses_3d(tmp_path):
    d = _srt_dir(tmp_path)
    result = CliRunner().invoke(main, ["flightmap", str(d), "--airspace", "--3d"])
    assert result.exit_code != 0


def test_airspace_refuses_non_map_formats(tmp_path):
    d = _srt_dir(tmp_path)
    for fmt in ("kml", "geojson", "record"):
        result = CliRunner().invoke(
            main, ["flightmap", str(d), "--airspace", "-f", fmt]
        )
        assert result.exit_code != 0, fmt


def test_refresh_note_not_shown_with_airspace(tmp_path, monkeypatch):
    fake = FakeTransport([_lux_body()])
    monkeypatch.setattr(airspace_fetch, "urlopen", fake)
    d = _srt_dir(tmp_path)
    result = CliRunner().invoke(
        main, ["flightmap", str(d), "--airspace", "--airspace-refresh"]
    )
    assert result.exit_code == 0, result.output
    assert "does nothing" not in result.output


def test_gap_track_still_renders_map_with_note(tmp_path, monkeypatch):
    monkeypatch.setattr(airspace_fetch, "urlopen", FakeTransport([]))
    d = tmp_path / "flights"
    d.mkdir()
    coords = [(0.0 + i * 0.001, -160.0, 300.0 + i) for i in range(4)]
    (d / "PAC0001.SRT").write_text(_dt_srt(T0, coords), encoding="utf-8")
    result = CliRunner().invoke(main, ["flightmap", str(d), "--airspace"])
    assert result.exit_code == 0, result.output
    assert "Note: PAC0001:" in result.output
    html = (d / "flightmap.html").read_text(encoding="utf-8")
    assert 'id="airspace-data"' in html      # gap note embedded in the map
    assert "airspace-note" in html
