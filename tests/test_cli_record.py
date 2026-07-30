"""CLI tests for flightmap -f record (#413). Uses the repo SRT samples."""
import io
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import URLError

from click.testing import CliRunner

from dji_metadata_embedder.cli import main

SAMPLES = Path(__file__).parent.parent / "samples"


def _dt_srt(start, coords):
    """Datetime-carrying bracket SRT, one block per second — mirrors the
    fixture helper in tests/test_cli_flightmap.py so this parses under the
    same SRT parser (load_samples)."""
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
    """A folder with one Luxembourg-coordinates SRT (jurisdiction LU, so it
    resolves against samples/airspace/ed269-lu.json)."""
    d = tmp_path / "flights"
    d.mkdir()
    coords = [(49.615 + i * 0.001, 6.19, 300.0 + i) for i in range(4)]
    (d / "LUX0001.SRT").write_text(_dt_srt(T0, coords), encoding="utf-8")
    return d


class FakeTransport:
    """Queued fake HTTP responses. Once exhausted, raises URLError — the
    same failure mode a real dead server produces — so terrain fetches that
    outrun the queue degrade into a stated note instead of crashing on a
    test-only IndexError."""

    def __init__(self, bodies):
        self.bodies = list(bodies)

    def __call__(self, req, timeout=None):
        if not self.bodies:
            raise URLError("no more fake responses queued")
        resp = io.BytesIO(self.bodies.pop(0))
        resp.__enter__ = lambda *a: resp  # type: ignore[method-assign]
        resp.__exit__ = lambda *a: False  # type: ignore[method-assign]
        return resp


def test_record_format_writes_the_html(tmp_path, monkeypatch):
    from dji_metadata_embedder.geo import record as record_mod

    lux = (SAMPLES / "airspace" / "ed269-lu.json").read_bytes()
    monkeypatch.setattr(record_mod, "urlopen", FakeTransport([lux]))
    d = _srt_dir(tmp_path)
    result = CliRunner().invoke(main, ["flightmap", str(d), "-f", "record"])
    assert result.exit_code == 0, result.output
    out = d / "flight-record.html"
    assert out.exists()
    assert "factual record" in out.read_text(encoding="utf-8")


def test_record_refuses_redacted_coordinates(tmp_path):
    d = _srt_dir(tmp_path)
    result = CliRunner().invoke(
        main, ["flightmap", str(d), "-f", "record", "--redact", "fuzz"]
    )
    assert result.exit_code != 0
    assert "redact" in result.output.lower()


def test_all_under_redact_skips_the_record_with_a_note(tmp_path):
    d = _srt_dir(tmp_path)
    result = CliRunner().invoke(
        main, ["flightmap", str(d), "-f", "all", "--redact", "fuzz"]
    )
    assert result.exit_code == 0, result.output
    assert not (d / "flight-record.html").exists()
    assert "skipped under --redact" in result.output


def test_3d_and_record_conflict(tmp_path):
    d = _srt_dir(tmp_path)
    result = CliRunner().invoke(
        main, ["flightmap", str(d), "-f", "record", "--3d"]
    )
    assert result.exit_code != 0


def test_airspace_refresh_without_record_warns(tmp_path):
    d = _srt_dir(tmp_path)
    result = CliRunner().invoke(
        main, ["flightmap", str(d), "-f", "html", "--airspace-refresh"]
    )
    assert result.exit_code == 0, result.output
    assert "airspace-refresh" in result.output


def test_airspace_refresh_with_all_and_redact_warns(tmp_path):
    """--format all under --redact skips the record entirely (fix #4): the
    --airspace-refresh note must fire here too, not just for non-record
    formats — the flag genuinely does nothing in this combination."""
    d = _srt_dir(tmp_path)
    result = CliRunner().invoke(
        main,
        [
            "flightmap", str(d), "-f", "all", "--redact", "fuzz",
            "--airspace-refresh",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "airspace-refresh" in result.output


def test_record_cache_dir_is_beside_the_output(tmp_path, monkeypatch):
    from dji_metadata_embedder.geo import record as record_mod

    lux = (SAMPLES / "airspace" / "ed269-lu.json").read_bytes()
    monkeypatch.setattr(record_mod, "urlopen", FakeTransport([lux]))
    d = _srt_dir(tmp_path)
    out_path = tmp_path / "out" / "custom-record.html"
    out_path.parent.mkdir()
    result = CliRunner().invoke(
        main,
        ["flightmap", str(d), "-f", "record", "-o", str(out_path)],
    )
    assert result.exit_code == 0, result.output
    assert out_path.exists()
    assert (out_path.parent / "airspace-cache").is_dir()


def test_record_announces_gap_reason_note(tmp_path, monkeypatch):
    """A track outside the v1 jurisdictions gets a gap_reason on airspace,
    which the CLI must surface as a Note: line after writing."""
    from dji_metadata_embedder.geo import record as record_mod

    monkeypatch.setattr(record_mod, "urlopen", FakeTransport([]))
    d = tmp_path / "flights"
    d.mkdir()
    # Middle of the Pacific: outside all v1 jurisdictions (US/LU/FI).
    coords = [(0.0 + i * 0.001, -160.0, 300.0 + i) for i in range(4)]
    (d / "PAC0001.SRT").write_text(_dt_srt(T0, coords), encoding="utf-8")
    result = CliRunner().invoke(main, ["flightmap", str(d), "-f", "record"])
    assert result.exit_code == 0, result.output
    assert "Note: PAC0001:" in result.output
