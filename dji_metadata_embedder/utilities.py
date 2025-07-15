import re
from pathlib import Path
from typing import List, Tuple

def iso6709(lat: float, lon: float, alt: float = 0.0) -> str:
    """Return an ISO 6709 location string for QuickTime metadata."""
    return f"{lat:+08.4f}{lon:+09.4f}{alt:+07.1f}/"

def parse_telemetry_points(srt_path: Path) -> List[Tuple[float, float, float, str]]:
    """Parse an SRT file into a list of (lat, lon, alt, timestamp)."""
    content = srt_path.read_text(encoding="utf-8")
    blocks = content.strip().split("\n\n")
    points: List[Tuple[float, float, float, str]] = []
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        ts_line = lines[1]
        ts_match = re.search(r"(\d{2}:\d{2}:\d{2},\d{3})", ts_line)
        timestamp = ts_match.group(1) if ts_match else ""
        tele_line = " ".join(lines[2:])
        if "<font" in tele_line:
            tele_line = re.sub(r"<[^>]+>", "", tele_line)
        lat_match = re.search(r"\[latitude:\s*([+-]?\d+\.?\d*)\]", tele_line)
        lon_match = re.search(r"\[longitude:\s*([+-]?\d+\.?\d*)\]", tele_line)
        alt_match = re.search(r"abs_alt:\s*([+-]?\d+\.?\d*)\]", tele_line)
        if not (lat_match and lon_match):
            gps = re.search(r"GPS\(([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)\)", tele_line)
            if gps:
                lat_match, lon_match = gps, gps
                alt_match = gps
        if lat_match and lon_match:
            lat = float(lat_match.group(1))
            lon = float(lon_match.group(2) if len(lon_match.groups()) > 1 else lon_match.group(1))
            alt = float(alt_match.group(3) if alt_match and len(alt_match.groups()) > 1 else (alt_match.group(1) if alt_match else 0.0))
            points.append((lat, lon, alt, timestamp))
    return points
