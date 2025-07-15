import struct
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dji_metadata_embedder import parse_dat_v13


def _create_sample(path: Path):
    data = b"DAT13"
    data += struct.pack("<IIfff", 1, 1, 59.1, 18.2, 10.0)
    data += struct.pack("<IIfff", 2, 2, 59.2, 18.3, 10.5)
    path.write_bytes(data)


def test_parse_dat_v13(tmp_path):
    dat = tmp_path / "flight.DAT"
    _create_sample(dat)
    out = parse_dat_v13(dat)
    assert len(out["records"]) == 2
    assert out["records"][0]["frame"] == 1
    assert abs(out["records"][1]["longitude"] - 18.3) < 1e-6
