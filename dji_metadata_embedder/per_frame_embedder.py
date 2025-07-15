import subprocess
from pathlib import Path
from typing import List, Tuple

from .utilities import parse_telemetry_points, iso6709


def embed_flight_path_ffmpeg(
    video: Path, points: List[Tuple[float, float, float, str]], output: Path
) -> bool:
    """Embed per-frame GPS points using FFmpeg. Returns True on success."""
    cmd = [
        "ffmpeg",
        "-i",
        str(video),
        "-c",
        "copy",
        "-movflags",
        "use_metadata_tags",
    ]
    for i, (lat, lon, alt, _ts) in enumerate(points):
        tag = iso6709(lat, lon, alt)
        cmd.extend(["-metadata", f"location.{i}.ISO6709={tag}"])
    cmd.extend([str(output)])

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def embed_flight_path(video: Path, srt: Path, output: Path) -> bool:
    points = parse_telemetry_points(srt)
    return embed_flight_path_ffmpeg(video, points, output)


def extract_frame_locations(path: Path) -> List[str]:
    """Return list of ISO6709 strings extracted via ffprobe frame tags."""
    cmd = [
        "ffprobe",
        "-v",
        "0",
        "-show_entries",
        "frame_tags",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    tags = []
    for line in result.stdout.splitlines():
        if line.startswith("TAG:location.") and "ISO6709" in line:
            _, val = line.split("=", 1)
            tags.append(val)
    return tags
