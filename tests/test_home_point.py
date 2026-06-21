import csv as _csv
from pathlib import Path

from click.testing import CliRunner
from dji_metadata_embedder.embedder import DJIMetadataEmbedder
from dji_metadata_embedder.cli import main
from dji_metadata_embedder.utilities import Home, apply_redaction, parse_home, redact_home
from dji_metadata_embedder.telemetry_converter import extract_telemetry_to_gpx, extract_telemetry_to_csv

# Variant 1: HOME(lat,lon) no space, no altitude
SRT_V1 = "HOME(39.906206,116.391400) D=5.2m H=1.5m"
# Variant 2: HOME (lat, lon, altm) leading space + altitude with trailing m
SRT_V2 = "HOME (-58.847509, -34.232707, -57.98m), D 698.70m, H 85.80m,"


def test_parse_home_variant1_no_alt():
    home = parse_home(SRT_V1)
    assert home == Home(lat=39.906206, lon=116.391400, alt=None)


def test_parse_home_variant2_with_alt():
    home = parse_home(SRT_V2)
    assert home == Home(lat=-58.847509, lon=-34.232707, alt=-57.98)


def test_parse_home_absent_returns_none():
    assert parse_home("[latitude: 1.0] [longitude: 2.0]") is None


def test_redact_home_drop():
    assert redact_home(Home(1.23456, 2.34567, 10.0), "drop") is None


def test_redact_home_fuzz_rounds_to_3dp():
    assert redact_home(Home(1.23456, 2.34567, 10.12345), "fuzz") == Home(1.235, 2.346, 10.123)


def test_redact_home_none_passthrough():
    h = Home(1.23456, 2.34567, None)
    assert redact_home(h, "none") == h


def test_redact_home_handles_none_input():
    assert redact_home(None, "fuzz") is None


def test_apply_redaction_drops_home():
    tel = {"gps_coords": [(1.0, 2.0)], "first_gps": (1.0, 2.0), "avg_gps": (1.0, 2.0),
           "home": Home(1.23456, 2.34567, 10.0)}
    apply_redaction(tel, "drop")
    assert tel["home"] is None


def test_apply_redaction_fuzzes_home():
    tel = {"gps_coords": [(1.0, 2.0)], "first_gps": (1.0, 2.0), "avg_gps": (1.0, 2.0),
           "home": Home(1.23456, 2.34567, 10.0)}
    apply_redaction(tel, "fuzz")
    assert tel["home"] == Home(1.235, 2.346, 10.0)


def test_apply_redaction_no_home_key_is_noop():
    tel = {"gps_coords": [(1.0, 2.0)], "first_gps": (1.0, 2.0), "avg_gps": (1.0, 2.0)}
    apply_redaction(tel, "drop")  # must not raise
    assert "home" not in tel


SRT_BLOCK = (
    "1\n"
    "00:00:00,000 --> 00:00:00,033\n"
    "HOME(39.906206,116.391400) D=5.2m H=1.5m [latitude: 39.900000] "
    "[longitude: 116.400000] [rel_alt: 1.500 abs_alt: 100.000]\n"
)


def _embedder(tmp_path: Path, **kw) -> DJIMetadataEmbedder:
    (tmp_path / "out").mkdir(exist_ok=True)
    return DJIMetadataEmbedder(str(tmp_path), output_dir=str(tmp_path / "out"), **kw)


def test_parse_omits_home_when_flag_off(tmp_path):
    srt = tmp_path / "f.SRT"
    srt.write_text(SRT_BLOCK, encoding="utf-8")
    tel = _embedder(tmp_path).parse_dji_srt(srt)
    assert "home" not in tel


def test_parse_extracts_home_when_flag_on(tmp_path):
    srt = tmp_path / "f.SRT"
    srt.write_text(SRT_BLOCK, encoding="utf-8")
    tel = _embedder(tmp_path, extract_home=True).parse_dji_srt(srt)
    assert tel["home"] == Home(lat=39.906206, lon=116.391400, alt=None)


def test_parse_home_none_when_flag_on_but_absent(tmp_path):
    srt = tmp_path / "f.SRT"
    srt.write_text(SRT_BLOCK.replace("HOME(39.906206,116.391400) D=5.2m H=1.5m ", ""),
                   encoding="utf-8")
    tel = _embedder(tmp_path, extract_home=True).parse_dji_srt(srt)
    assert tel["home"] is None


def test_embed_help_lists_extract_home():
    res = CliRunner().invoke(main, ["embed", "--help"])
    assert res.exit_code == 0
    assert "--extract-home" in res.output


GPX_SRT = (
    "1\n00:00:00,000 --> 00:00:00,033\n"
    "HOME(39.906206,116.391400) [latitude: 39.900000] [longitude: 116.400000] "
    "[rel_alt: 1.5 abs_alt: 100.0]\n"
)


def test_gpx_no_home_when_flag_off(tmp_path):
    srt = tmp_path / "f.SRT"
    srt.write_text(GPX_SRT, encoding="utf-8")
    out = extract_telemetry_to_gpx(srt, tmp_path / "f.gpx")
    assert "<wpt" not in out.read_text(encoding="utf-8")


def test_gpx_home_waypoint_when_flag_on(tmp_path):
    srt = tmp_path / "f.SRT"
    srt.write_text(GPX_SRT, encoding="utf-8")
    out = extract_telemetry_to_gpx(srt, tmp_path / "f.gpx", extract_home=True)
    text = out.read_text(encoding="utf-8")
    assert '<wpt lat="39.906206" lon="116.3914">' in text
    assert "<name>HOME</name>" in text


def test_gpx_home_dropped_under_redact(tmp_path):
    srt = tmp_path / "f.SRT"
    srt.write_text(GPX_SRT, encoding="utf-8")
    out = extract_telemetry_to_gpx(srt, tmp_path / "f.gpx", extract_home=True, redact="drop")
    assert "<wpt" not in out.read_text(encoding="utf-8")


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(_csv.DictReader(f))


def test_csv_no_home_columns_when_flag_off(tmp_path):
    srt = tmp_path / "f.SRT"
    srt.write_text(GPX_SRT, encoding="utf-8")
    out = extract_telemetry_to_csv(srt, tmp_path / "f.csv")
    rows = _read_csv(out)
    assert "home_lat" not in rows[0]


def test_csv_home_columns_when_flag_on(tmp_path):
    srt = tmp_path / "f.SRT"
    srt.write_text(GPX_SRT, encoding="utf-8")
    out = extract_telemetry_to_csv(srt, tmp_path / "f.csv", extract_home=True)
    rows = _read_csv(out)
    assert rows[0]["home_lat"] == "39.906206"
    assert rows[0]["home_lon"] == "116.3914"


def test_csv_home_dropped_under_redact(tmp_path):
    srt = tmp_path / "f.SRT"
    srt.write_text(GPX_SRT, encoding="utf-8")
    out = extract_telemetry_to_csv(srt, tmp_path / "f.csv", extract_home=True, redact="drop")
    rows = _read_csv(out)
    assert rows[0]["home_lat"] == ""
