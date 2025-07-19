"""Conversion utilities for DJI SRT telemetry files.

This module contains helper functions for extracting telemetry data from DJI
subtitle (SRT) files. The data can be converted to GPX tracks or CSV logs, and
directories of SRT files can be processed in batch. A small CLI wrapper is
provided for convenience.
"""

from pathlib import Path
from datetime import datetime
import re
import logging

from rich.progress import Progress
from .utilities import setup_logging

logger = logging.getLogger(__name__)


def extract_telemetry_to_gpx(
    srt_file: Path | str, output_file: Path | str | None = None
) -> Path:
    """
    Extract GPS telemetry from DJI SRT file and create GPX file.
    """
    srt_path = Path(srt_file)
    output_path = Path(output_file) if output_file else srt_path.with_suffix(".gpx")

    gps_points = []

    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = content.strip().split("\n\n")

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            # Parse timestamp
            timestamp_line = lines[1]
            timestamp_match = re.search(r"(\d{2}:\d{2}:\d{2},\d{3})", timestamp_line)

            # Parse telemetry data
            telemetry_line = " ".join(lines[2:])
            if "<font" in telemetry_line:
                telemetry_line = re.sub(r"<[^>]+>", "", telemetry_line)

            # Extract GPS coordinates
            lat_match = re.search(r"\[latitude:\s*([+-]?\d+\.?\d*)\]", telemetry_line)
            lon_match = re.search(r"\[longitude:\s*([+-]?\d+\.?\d*)\]", telemetry_line)
            alt_match = re.search(r"abs_alt:\s*([+-]?\d+\.?\d*)\]", telemetry_line)

            if lat_match and lon_match:
                point = {
                    "lat": float(lat_match.group(1)),
                    "lon": float(lon_match.group(1)),
                    "ele": float(alt_match.group(1)) if alt_match else 0,
                    "time": timestamp_match.group(1) if timestamp_match else None,
                }
                gps_points.append(point)

    # Write GPX file
    gpx_header = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="DJI SRT to GPX Converter"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns="http://www.topografix.com/GPX/1/1"
    xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">
<metadata>
    <name>{}</name>
    <time>{}</time>
</metadata>
<trk>
    <name>DJI Flight Path</name>
    <trkseg>
""".format(
        Path(srt_file).stem, datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    gpx_footer = """    </trkseg>
</trk>
</gpx>"""

    with open(output_path, "w") as f:
        f.write(gpx_header)
        for point in gps_points:
            f.write(f'        <trkpt lat="{point["lat"]}" lon="{point["lon"]}">\n')
            f.write(f'            <ele>{point["ele"]}</ele>\n')
            if point["time"]:
                f.write(f'            <time>{point["time"]}</time>\n')
            f.write("        </trkpt>\n")
        f.write(gpx_footer)

    logger.info("GPX file created: %s", output_path)
    return output_path


def batch_convert_to_gpx(directory: Path | str) -> None:
    """
    Convert all SRT files in a directory to GPX files.
    """
    directory = Path(directory)
    srt_files = list(directory.glob("*.srt")) + list(directory.glob("*.SRT"))

    if not srt_files:
        logger.warning("No SRT files found in %s", directory)
        return

    gpx_dir = directory / "gpx_tracks"
    gpx_dir.mkdir(exist_ok=True)

    logger.info("Found %d SRT files to convert", len(srt_files))
    with Progress() as progress:
        task = progress.add_task("Converting", total=len(srt_files))
        for srt_file in srt_files:
            output_file = gpx_dir / f"{srt_file.stem}.gpx"
            try:
                extract_telemetry_to_gpx(srt_file, output_file)
            except Exception as e:
                logger.error("Error converting %s: %s", srt_file.name, e)
            progress.advance(task)

    logger.info("GPX files saved to: %s", gpx_dir)


def batch_convert_to_csv(directory: Path | str) -> None:
    """
    Convert all SRT files in a directory to CSV files.
    """
    directory = Path(directory)
    srt_files = list(directory.glob("*.srt")) + list(directory.glob("*.SRT"))

    if not srt_files:
        logger.warning("No SRT files found in %s", directory)
        return

    csv_dir = directory / "csv_logs"
    csv_dir.mkdir(exist_ok=True)

    logger.info("Found %d SRT files to convert", len(srt_files))
    with Progress() as progress:
        task = progress.add_task("Converting", total=len(srt_files))
        for srt_file in srt_files:
            output_file = csv_dir / f"{srt_file.stem}.csv"
            try:
                extract_telemetry_to_csv(srt_file, output_file)
            except Exception as e:
                logger.error("Error converting %s: %s", srt_file.name, e)
            progress.advance(task)

    logger.info("CSV files saved to: %s", csv_dir)


def extract_telemetry_to_csv(
    srt_file: Path | str, output_file: Path | str | None = None
) -> Path:
    """
    Extract all telemetry data from DJI SRT file to CSV.
    """
    srt_path = Path(srt_file)
    output_path = Path(output_file) if output_file else srt_path.with_suffix(".csv")

    rows = []

    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = content.strip().split("\n\n")

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            # Parse timestamp
            timestamp_line = lines[1]
            timestamp_match = re.search(r"(\d{2}:\d{2}:\d{2},\d{3})", timestamp_line)

            # Parse telemetry data
            telemetry_line = " ".join(lines[2:])
            if "<font" in telemetry_line:
                telemetry_line = re.sub(r"<[^>]+>", "", telemetry_line)

            # Extract all data
            row = {
                "timestamp": timestamp_match.group(1) if timestamp_match else "",
                "latitude": "",
                "longitude": "",
                "rel_altitude": "",
                "abs_altitude": "",
                "iso": "",
                "shutter": "",
                "fnum": "",
                "ev": "",
                "ct": "",
                "color_md": "",
                "focal_len": "",
            }

            # GPS coordinates
            lat_match = re.search(r"\[latitude:\s*([+-]?\d+\.?\d*)\]", telemetry_line)
            lon_match = re.search(r"\[longitude:\s*([+-]?\d+\.?\d*)\]", telemetry_line)
            if lat_match and lon_match:
                row["latitude"] = lat_match.group(1)
                row["longitude"] = lon_match.group(1)

            # Altitude
            alt_match = re.search(
                r"\[rel_alt:\s*([+-]?\d+\.?\d*)\s*abs_alt:\s*([+-]?\d+\.?\d*)\]",
                telemetry_line,
            )
            if alt_match:
                row["rel_altitude"] = alt_match.group(1)
                row["abs_altitude"] = alt_match.group(2)

            # Camera settings
            iso_match = re.search(r"\[iso\s*:\s*(\d+)\]", telemetry_line)
            shutter_match = re.search(r"\[shutter\s*:\s*([^\]]+)\]", telemetry_line)
            fnum_match = re.search(r"\[fnum\s*:\s*(\d+)\]", telemetry_line)
            ev_match = re.search(r"\[ev\s*:\s*([^\]]+)\]", telemetry_line)
            ct_match = re.search(r"\[ct\s*:\s*([^\]]+)\]", telemetry_line)
            color_md_match = re.search(r"\[color_md\s*:\s*([^\]]+)\]", telemetry_line)
            focal_len_match = re.search(r"\[focal_len\s*:\s*([^\]]+)\]", telemetry_line)

            if iso_match:
                row["iso"] = iso_match.group(1)
            if shutter_match:
                row["shutter"] = shutter_match.group(1)
            if fnum_match:
                row["fnum"] = fnum_match.group(1)
            if ev_match:
                row["ev"] = ev_match.group(1)
            if ct_match:
                row["ct"] = ct_match.group(1)
            if color_md_match:
                row["color_md"] = color_md_match.group(1)
            if focal_len_match:
                row["focal_len"] = focal_len_match.group(1)

            rows.append(row)

    # Write CSV
    import csv

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    logger.info("CSV file created: %s", output_path)
    return output_path


def convert_to_gpx(srt_file: str | Path, output_file: str | Path | None = None) -> Path:
    """Wrapper for backwards compatibility.

    Converts ``srt_file`` to GPX using :func:`extract_telemetry_to_gpx`.
    """
    return extract_telemetry_to_gpx(srt_file, output_file)


def convert_to_csv(srt_file: str | Path, output_file: str | Path | None = None) -> Path:
    """Wrapper for backwards compatibility.

    Converts ``srt_file`` to CSV using :func:`extract_telemetry_to_csv`.
    """
    return extract_telemetry_to_csv(srt_file, output_file)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="DJI SRT telemetry converter utilities"
    )
    parser.add_argument("command", choices=["gpx", "csv"], help="Conversion type")
    parser.add_argument("input", help="Input SRT file or directory")
    parser.add_argument(
        "-o", "--output", help="Output file (for single file conversion)"
    )
    parser.add_argument(
        "-b", "--batch", action="store_true", help="Batch process directory"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress info output"
    )

    args = parser.parse_args()
    setup_logging(args.verbose, args.quiet)

    if args.batch:
        if args.command == "gpx":
            batch_convert_to_gpx(args.input)
        elif args.command == "csv":
            batch_convert_to_csv(args.input)
    else:
        if args.command == "gpx":
            extract_telemetry_to_gpx(args.input, args.output)
        elif args.command == "csv":
            extract_telemetry_to_csv(args.input, args.output)
