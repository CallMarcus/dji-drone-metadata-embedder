"""Utilities for creating placeholder MP4 and SRT files for testing.

Sample usage:
    from pathlib import Path
    from tests.generate_test_data import (
        create_placeholder_mp4,
        create_mini_srt,
        create_avata2_srt,
        create_edge_case_srts,
    )

    output = Path("tmp")
    create_placeholder_mp4(output / "video.mp4")
    create_mini_srt(output / "mini.srt")
    create_avata2_srt(output / "avata.srt")
    create_edge_case_srts(output / "edge")

Run ``python tests/generate_test_data.py <output_dir>`` to generate all
files into ``<output_dir>``.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List


MP4_HEADER = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42mp41"

logging.basicConfig(level=logging.INFO)


def create_placeholder_mp4(path: Path, size: int = 1024) -> Path:
    """Create a tiny MP4 placeholder file.

    Parameters
    ----------
    path : Path
        Destination path of the file.
    size : int
        Target file size in bytes. Defaults to 1024 bytes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(MP4_HEADER)
        if size > len(MP4_HEADER):
            fh.write(b"\0" * (size - len(MP4_HEADER)))
    logging.info("Created placeholder MP4: %s", path)
    return path


def create_mini_srt(path: Path) -> Path:
    """Create a DJI Mini 3/4 style SRT file."""
    content = """1
00:00:00,000 --> 00:00:00,033
[latitude: 59.0000] [longitude: 18.0000] [rel_alt: 1.0 abs_alt: 100.0] [iso : 100] [shutter : 1/30] [fnum : 170]

2
00:00:00,033 --> 00:00:00,066
[latitude: 59.0001] [longitude: 18.0001] [rel_alt: 2.0 abs_alt: 101.0] [iso : 100] [shutter : 1/30] [fnum : 170]
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    logging.info("Created Mini 3/4 SRT: %s", path)
    return path


def create_avata2_srt(path: Path) -> Path:
    """Create an Avata 2 style SRT file."""
    content = """1
00:00:00,000 --> 00:00:00,033
GPS(39.906217,116.391305,69.800) BAROMETER(91.2) HOME(39.906206,116.391400)

2
00:00:00,033 --> 00:00:00,066
GPS(39.906218,116.391306,69.900) BAROMETER(91.2) HOME(39.906206,116.391400)
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    logging.info("Created Avata 2 SRT: %s", path)
    return path


def create_edge_case_srts(directory: Path) -> List[Path]:
    """Generate SRT files with problematic formatting for parser testing."""
    directory.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []

    missing_gps = directory / "missing_gps.srt"
    missing_gps.write_text(
        """1
00:00:00,000 --> 00:00:00,033
[rel_alt: 1.0 abs_alt: 100.0]
""",
        encoding="utf-8",
    )
    paths.append(missing_gps)

    bad_timestamp = directory / "bad_timestamp.srt"
    bad_timestamp.write_text(
        """1
00:00:00 --> 00:00:00,033
[latitude: 59.0] [longitude: 18.0] [rel_alt: 1.0 abs_alt: 100.0]
""",
        encoding="utf-8",
    )
    paths.append(bad_timestamp)

    split_lines = directory / "split_lines.srt"
    split_lines.write_text(
        """1
00:00:00,000 --> 00:00:00,033
GPS(39.906217, 116.391305, 69.800)
BAROMETER(91.2) HOME(39.906206,116.391400)
""",
        encoding="utf-8",
    )
    paths.append(split_lines)

    for p in paths:
        logging.info("Created edge-case SRT: %s", p)

    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sample test data.")
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=Path("generated_samples"),
        help="Directory to store generated files",
    )
    args = parser.parse_args()
    out_dir = args.output
    create_placeholder_mp4(out_dir / "placeholder.mp4")
    create_mini_srt(out_dir / "mini.srt")
    create_avata2_srt(out_dir / "avata2.srt")
    create_edge_case_srts(out_dir / "edge_cases")
    logging.info("All test data generated in %s", out_dir)


if __name__ == "__main__":
    main()
