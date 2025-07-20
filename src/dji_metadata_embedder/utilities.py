import logging
import re
from pathlib import Path
from typing import List, Tuple
import subprocess

from rich.logging import RichHandler


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
            gps = re.search(
                r"GPS\(([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)\)",
                tele_line,
            )
            if gps:
                lat_match, lon_match = gps, gps
                alt_match = gps
        if lat_match and lon_match:
            lat = float(lat_match.group(1))
            lon = float(
                lon_match.group(2)
                if len(lon_match.groups()) > 1
                else lon_match.group(1)
            )
            alt = float(
                alt_match.group(3)
                if alt_match and len(alt_match.groups()) > 1
                else (alt_match.group(1) if alt_match else 0.0)
            )
            points.append((lat, lon, alt, timestamp))
    return points


def redact_coords(
    coords: List[Tuple[float, float]], mode: str
) -> List[Tuple[float, float]]:
    """Redact or fuzz coordinate list based on ``mode``."""
    if mode == "drop":
        return []
    if mode == "fuzz":
        return [(round(lat, 3), round(lon, 3)) for lat, lon in coords]
    return coords


def apply_redaction(telemetry: dict, mode: str) -> None:
    """Modify ``telemetry`` in place according to the redaction ``mode``."""
    telemetry["gps_coords"] = redact_coords(telemetry.get("gps_coords", []), mode)

    if mode == "drop":
        telemetry["first_gps"] = None
        telemetry["avg_gps"] = None
    elif mode == "fuzz":
        if telemetry.get("first_gps"):
            lat, lon = telemetry["first_gps"]
            telemetry["first_gps"] = (round(lat, 3), round(lon, 3))
        if telemetry.get("avg_gps"):
            lat, lon = telemetry["avg_gps"]
            telemetry["avg_gps"] = (round(lat, 3), round(lon, 3))


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure application wide logging."""
    level = logging.INFO
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )


def check_dependencies() -> Tuple[bool, list[str]]:
    """Return ``(True, [])`` if external tools are available."""
    import os
    import platform
    from pathlib import Path

    tools = {"ffmpeg": ["ffmpeg", "-version"], "exiftool": ["exiftool", "-ver"]}
    missing: list[str] = []

    # Add dji-embed bin directory to PATH temporarily (Windows only)
    original_path = os.environ.get("PATH", "")
    path_modified = False
    
    if platform.system() == "Windows":
        bin_dir = Path.home() / "AppData" / "Local" / "dji-embed" / "bin"
        if bin_dir.exists() and str(bin_dir) not in original_path:
            os.environ["PATH"] = str(bin_dir) + os.pathsep + original_path
            path_modified = True
    
    try:
        for name, cmd in tools.items():
            # Check environment variables first (set by bootstrap script)
            env_var = f"DJIEMBED_{name.upper()}_PATH"
            tool_path = os.environ.get(env_var)
            
            if tool_path and Path(tool_path).exists():
                # Use the explicit path from environment variable
                test_cmd = [tool_path] + cmd[1:]
                try:
                    subprocess.run(test_cmd, capture_output=True, check=True)
                    continue  # Tool found, skip to next
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass  # Fall through to normal check
            
            # Normal check
            try:
                # Use shell=True on Windows to find executables in PATH
                subprocess.run(cmd, capture_output=True, check=True, 
                              shell=(platform.system() == "Windows"))
            except (subprocess.CalledProcessError, FileNotFoundError):
                missing.append(name)
    finally:
        # Restore original PATH if we modified it
        if path_modified:
            os.environ["PATH"] = original_path

    return (not missing), missing


def parse_dji_srt(srt_path: Path) -> dict:
    """Standalone wrapper around :class:`DJIMetadataEmbedder` parsing."""
    from .embedder import DJIMetadataEmbedder

    embedder = DJIMetadataEmbedder(str(srt_path.parent))
    return embedder.parse_dji_srt(srt_path)
