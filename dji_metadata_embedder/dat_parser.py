import struct
from pathlib import Path
from typing import Dict, List


_RECORD_STRUCT = struct.Struct("<IIfff")
_HEADER = b"DAT13"


def parse_v13(path: Path) -> Dict:
    """Parse a very small subset of DJI DAT v13 logs.

    This parser expects a simplified binary layout used by the tests:
    - Header ``b'DAT13'``
    - Repeating records of ``<gps_time:uint32><frame:uint32><lat:float><lon:float><alt:float>``

    Returns a dictionary containing a list of record dictionaries.
    """
    data = path.read_bytes()
    if not data.startswith(_HEADER):
        raise ValueError("Unsupported DAT file")
    records: List[Dict] = []
    offset = len(_HEADER)
    while offset + _RECORD_STRUCT.size <= len(data):
        gps_time, frame, lat, lon, alt = _RECORD_STRUCT.unpack_from(data, offset)
        records.append(
            {
                "gps_time": gps_time,
                "frame": frame,
                "latitude": lat,
                "longitude": lon,
                "altitude": alt,
            }
        )
        offset += _RECORD_STRUCT.size
    return {"records": records}
