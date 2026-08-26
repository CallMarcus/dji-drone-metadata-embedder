"""CSV camera columns from the SRT text, incl. the Mavic 4 Pro ``tint`` token."""

import csv

from dji_metadata_embedder.telemetry_converter import extract_telemetry_to_csv

_M4P_SRT = (
    "1\n00:00:00,000 --> 00:00:00,016\n"
    '<font size="28">FrameCnt: 1, DiffTime: 16ms\n'
    "2026-08-23 17:22:01.253\n"
    "[iso: 160] [shutter: 1/1000.0] [fnum: 2.8] [ev: -0.3] [color_md: default] "
    "[focal_len: 28.00] [latitude: 59.329400] [longitude: 18.068600] "
    "[rel_alt: 59.764 abs_alt: 92.670] [ct: 5574, tint: 8] </font>\n"
)

_AIR3S_SRT = (
    "1\n00:00:00,000 --> 00:00:00,016\n"
    '<font size="28">FrameCnt: 1, DiffTime: 16ms\n'
    "2026-05-17 08:28:30.219\n"
    "[iso: 180] [shutter: 1/640.0] [fnum: 1.8] [ev: 0] [color_md: hlg] "
    "[focal_len: 24.00] [latitude: 34.270373] [longitude: -84.176160] "
    "[rel_alt: 0.000 abs_alt: 302.208] [ct: 5419] </font>\n"
)


def _rows(tmp_path, text):
    srt = tmp_path / "clip.SRT"
    srt.write_text(text, encoding="utf-8")
    out = tmp_path / "clip.csv"
    extract_telemetry_to_csv(srt, out)
    lines = out.read_text(encoding="utf-8").splitlines()
    return lines[0].split(","), list(csv.DictReader(lines))


def test_csv_ct_numeric_and_tint_column(tmp_path):
    header, rows = _rows(tmp_path, _M4P_SRT)
    assert rows[0]["ct"] == "5574"
    assert rows[0]["tint"] == "8"
    # tint sits right after ct so existing column order is preserved.
    assert header.index("tint") == header.index("ct") + 1


def test_csv_tint_blank_when_absent(tmp_path):
    _header, rows = _rows(tmp_path, _AIR3S_SRT)
    assert rows[0]["ct"] == "5419"
    assert rows[0]["tint"] == ""
