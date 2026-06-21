"""Conversion utilities for DJI SRT telemetry files.

This module contains helper functions for extracting telemetry data from DJI
subtitle (SRT) files. The data can be converted to GPX tracks or CSV logs, and
directories of SRT files can be processed in batch. A small CLI wrapper is
provided for convenience.
"""

from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any
import re
import logging

from rich.progress import Progress
from .utilities import TelemetrySample, is_gps_fix, setup_logging
from .utilities import _parse_srt_datetime, resolve_utc_offset
from .utilities import parse_home, redact_home
# Re-exported for backwards compatibility — cli.py and tests/test_timezone.py
# import these from here:
from .utilities import parse_utc_offset, estimate_utc_offset  # noqa: F401
from .geo.solar import sun_position

logger = logging.getLogger(__name__)

# Peak solar elevation (degrees) below which a clip is flagged "very low sun".
_VERY_LOW_SUN_DEG = 5


def _parse_gps_points(content: str) -> list[dict[str, Any]]:
    """Parse SRT text into GPS points: lat, lon, ele, cue time, abs datetime.

    Shared by :func:`extract_telemetry_to_gpx` and :func:`summarize_sun` so the
    GPS/datetime extraction lives in one place.
    """
    gps_points: list[dict[str, Any]] = []
    for block in content.strip().split("\n\n"):
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        timestamp_match = re.search(r"(\d{2}:\d{2}:\d{2},\d{3})", lines[1])
        telemetry_line = " ".join(lines[2:])
        if "<font" in telemetry_line:
            telemetry_line = re.sub(r"<[^>]+>", "", telemetry_line)
        lat_match = re.search(r"\[latitude:\s*([+-]?\d+\.?\d*)\]", telemetry_line)
        lon_match = re.search(r"\[longitude:\s*([+-]?\d+\.?\d*)\]", telemetry_line)
        alt_match = re.search(r"abs_alt:\s*([+-]?\d+\.?\d*)\]", telemetry_line)
        if lat_match and lon_match:
            gps_points.append(
                {
                    "lat": float(lat_match.group(1)),
                    "lon": float(lon_match.group(1)),
                    "ele": float(alt_match.group(1)) if alt_match else 0,
                    "time": timestamp_match.group(1) if timestamp_match else None,
                    "datetime": _parse_srt_datetime(telemetry_line),
                }
            )
    return gps_points


def load_gps_points(path: Path) -> tuple[list[dict[str, Any]], bool]:
    """Return GPS points (``_parse_gps_points`` shape) and whether they are UTC.

    SRT: parse the text (datetimes are local wall-clock) -> ``is_utc=False``.
    Video: read via ``load_samples`` (ExifTool ``GPSDateTime`` is absolute UTC)
    -> ``is_utc=True``, so callers apply a zero local->UTC offset.
    """
    from .mp4_telemetry import is_video
    from .utilities import load_samples

    if is_video(path):
        points = [
            {"lat": s.lat, "lon": s.lon, "ele": s.alt, "time": s.cue, "datetime": s.dt}
            for s in load_samples(path)
        ]
        return points, True
    return _parse_gps_points(path.read_text(encoding="utf-8")), False


def extract_telemetry_to_gpx(
    srt_file: Path | str,
    output_file: Path | str | None = None,
    tz_offset: timedelta | None = None,
    extract_home: bool = False,
    redact: str = "none",
) -> Path:
    """Extract GPS telemetry from a DJI SRT file and create a GPX file.

    DJI SRT timestamps are local wall-clock time with no timezone. When a block
    carries an absolute datetime, its ``<time>`` is emitted as proper UTC
    ISO 8601. The local-to-UTC offset is taken from *tz_offset* when given,
    otherwise auto-detected from the SRT file's mtime (see
    :func:`estimate_utc_offset`). Formats without an absolute datetime fall back
    to the raw subtitle cue timestamp, as before.
    """
    srt_path = Path(srt_file)
    output_path = Path(output_file) if output_file else srt_path.with_suffix(".gpx")

    gps_points, is_utc = load_gps_points(srt_path)

    # Needed by the metadata <time> block below regardless of source.
    abs_times = [p["datetime"] for p in gps_points if p["datetime"] is not None]
    offset: timedelta | None
    if is_utc:
        # Video GPSDateTime is already UTC -> zero offset.
        offset = timedelta(0)
    else:
        # Resolve the local->UTC offset for points that carry an absolute datetime.
        mtime_utc = datetime.fromtimestamp(
            srt_path.stat().st_mtime, tz=timezone.utc
        ).replace(tzinfo=None)
        offset = resolve_utc_offset(abs_times, tz_offset, mtime_utc)

    def _point_time(point: dict) -> str | None:
        """Return the GPX <time> string for a point (UTC if datetime known)."""
        if point["datetime"] is not None and offset is not None:
            utc = point["datetime"] - offset
            return utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        return point["time"]

    # The metadata <time> is the first point's UTC time when known, otherwise
    # the current time (legacy behaviour for datetime-less formats).
    if abs_times and offset is not None:
        metadata_time = (abs_times[0] - offset).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        metadata_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

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
""".format(Path(srt_file).stem, metadata_time)

    trk_open = """<trk>
    <name>DJI Flight Path</name>
    <trkseg>
"""

    gpx_footer = """    </trkseg>
</trk>
</gpx>"""

    home_wpt = ""
    if extract_home:
        home = redact_home(parse_home(srt_path.read_text(encoding="utf-8")), redact)
        if home is not None:
            ele = f"        <ele>{home.alt}</ele>\n" if home.alt is not None else ""
            home_wpt = (
                f'    <wpt lat="{home.lat}" lon="{home.lon}">\n'
                f"{ele}"
                f"        <name>HOME</name>\n"
                f"    </wpt>\n"
            )

    with open(output_path, "w") as f:
        f.write(gpx_header)
        f.write(home_wpt)
        f.write(trk_open)
        for point in gps_points:
            f.write(f'        <trkpt lat="{point["lat"]}" lon="{point["lon"]}">\n')
            f.write(f'            <ele>{point["ele"]}</ele>\n')
            time_str = _point_time(point)
            if time_str:
                f.write(f'            <time>{time_str}</time>\n')
            f.write("        </trkpt>\n")
        f.write(gpx_footer)

    logger.info("GPX file created: %s", output_path)
    return output_path


def summarize_sun(
    srt_file: Path | str, tz_offset: timedelta | None = None
) -> dict[str, Any]:
    """Summarise the sun's track over a clip for footage verification.

    Resolves each GPS point's UTC time (via *tz_offset* or mtime auto-detect),
    computes solar azimuth/elevation, and returns aggregate stats plus flags:
    ``night`` (peak elevation below the horizon), ``very_low_sun`` (peak under
    5 degrees), or ``sun_not_computable`` (no resolvable UTC time). Angular stats
    are ``None`` when nothing could be computed.
    """
    srt_path = Path(srt_file)
    points, is_utc = load_gps_points(srt_path)

    offset: timedelta | None
    if is_utc:
        offset = timedelta(0)
    else:
        abs_times = [p["datetime"] for p in points if p["datetime"] is not None]
        mtime_utc = datetime.fromtimestamp(
            srt_path.stat().st_mtime, tz=timezone.utc
        ).replace(tzinfo=None)
        offset = resolve_utc_offset(abs_times, tz_offset, mtime_utc)

    track: list[tuple[datetime, float, float]] = []  # (utc, azimuth, elevation)
    if offset is not None:
        for p in points:
            if p["datetime"] is None or not is_gps_fix(p["lat"], p["lon"]):
                continue
            utc = p["datetime"] - offset
            az, el = sun_position(p["lat"], p["lon"], utc)
            track.append((utc, az, el))

    summary: dict[str, Any] = {
        "file": srt_path.name,
        "points": len(points),
        "sun_computed": len(track),
        "utc_start": None,
        "utc_end": None,
        "elevation_min": None,
        "elevation_max": None,
        "azimuth_start": None,
        "azimuth_end": None,
        "flags": [],
    }
    if not track:
        summary["flags"] = ["sun_not_computable"]
        return summary

    elevations = [el for _, _, el in track]
    summary["utc_start"] = track[0][0].strftime("%Y-%m-%dT%H:%M:%SZ")
    summary["utc_end"] = track[-1][0].strftime("%Y-%m-%dT%H:%M:%SZ")
    summary["elevation_min"] = round(min(elevations), 3)
    summary["elevation_max"] = round(max(elevations), 3)
    summary["azimuth_start"] = round(track[0][1], 3)
    summary["azimuth_end"] = round(track[-1][1], 3)
    if summary["elevation_max"] < 0:
        summary["flags"] = ["night"]
    elif summary["elevation_max"] < _VERY_LOW_SUN_DEG:
        summary["flags"] = ["very_low_sun"]
    return summary


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


# CSV columns, in output order. Shared by the SRT and video paths so the header
# is identical regardless of source.
_CSV_COLUMNS = (
    "timestamp", "latitude", "longitude", "rel_altitude", "abs_altitude",
    "iso", "shutter", "fnum", "ev", "ct", "color_md", "focal_len",
    "datetime_utc", "sun_azimuth", "sun_elevation",
)


def _csv_from_samples(samples: list[TelemetrySample], output_path: Path) -> Path:
    """Write CSV rows from video-sourced samples (UTC is intrinsic).

    Fills geo, altitude, ``datetime_utc`` and solar columns; camera columns that
    only the SRT text carries (iso/shutter/fnum/ev/ct/color_md/focal_len) stay
    blank.
    """
    import csv

    rows = []
    for s in samples:
        row = {c: "" for c in _CSV_COLUMNS}
        row["timestamp"] = s.cue
        row["latitude"] = f"{s.lat}"
        row["longitude"] = f"{s.lon}"
        if s.rel_alt is not None:
            row["rel_altitude"] = f"{s.rel_alt}"
        row["abs_altitude"] = f"{s.alt}"
        if s.dt is not None:
            row["datetime_utc"] = s.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            if is_gps_fix(s.lat, s.lon):
                az, el = sun_position(s.lat, s.lon, s.dt)
                row["sun_azimuth"] = f"{az:.3f}"
                row["sun_elevation"] = f"{el:.3f}"
        rows.append(row)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(_CSV_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    logger.info("CSV file created: %s", output_path)
    return output_path


def extract_telemetry_to_csv(
    srt_file: Path | str,
    output_file: Path | str | None = None,
    tz_offset: timedelta | None = None,
) -> Path:
    """Extract all telemetry data from a DJI SRT file to CSV.

    When blocks carry an absolute wall-clock datetime, three extra columns are
    filled: ``datetime_utc`` (ISO 8601; local->UTC via *tz_offset* or mtime
    auto-detect) and the solar ``sun_azimuth`` / ``sun_elevation`` for that
    instant and position. Formats without an absolute datetime leave those three
    columns blank.
    """
    srt_path = Path(srt_file)
    output_path = Path(output_file) if output_file else srt_path.with_suffix(".csv")

    from .mp4_telemetry import is_video
    from .utilities import load_samples

    if is_video(srt_path):
        return _csv_from_samples(load_samples(srt_path), output_path)

    rows = []
    # Per-row solar inputs, index-aligned with ``rows``: (abs_dt, lat, lon).
    solar_inputs: list[tuple[datetime | None, float | None, float | None]] = []

    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = content.strip().split("\n\n")

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            timestamp_line = lines[1]
            timestamp_match = re.search(r"(\d{2}:\d{2}:\d{2},\d{3})", timestamp_line)

            telemetry_line = " ".join(lines[2:])
            if "<font" in telemetry_line:
                telemetry_line = re.sub(r"<[^>]+>", "", telemetry_line)

            row = {c: "" for c in _CSV_COLUMNS}
            row["timestamp"] = timestamp_match.group(1) if timestamp_match else ""

            # GPS coordinates
            lat_match = re.search(r"\[latitude:\s*([+-]?\d+\.?\d*)\]", telemetry_line)
            lon_match = re.search(r"\[longitude:\s*([+-]?\d+\.?\d*)\]", telemetry_line)
            lat_val: float | None = None
            lon_val: float | None = None
            if lat_match and lon_match:
                row["latitude"] = lat_match.group(1)
                row["longitude"] = lon_match.group(1)
                lat_val = float(lat_match.group(1))
                lon_val = float(lon_match.group(1))

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
            solar_inputs.append(
                (_parse_srt_datetime(telemetry_line), lat_val, lon_val)
            )

    # Resolve the single local->UTC offset, then fill UTC + solar columns.
    abs_times = [dt for dt, _, _ in solar_inputs if dt is not None]
    mtime_utc = datetime.fromtimestamp(
        srt_path.stat().st_mtime, tz=timezone.utc
    ).replace(tzinfo=None)
    offset = resolve_utc_offset(abs_times, tz_offset, mtime_utc)
    if offset is not None:
        for row, (abs_dt, lat_val, lon_val) in zip(rows, solar_inputs):
            if abs_dt is None or lat_val is None or lon_val is None:
                continue
            utc = abs_dt - offset
            row["datetime_utc"] = utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            if not is_gps_fix(lat_val, lon_val):
                continue
            az, el = sun_position(lat_val, lon_val, utc)
            row["sun_azimuth"] = f"{az:.3f}"
            row["sun_elevation"] = f"{el:.3f}"

    # Write CSV
    import csv

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=list(_CSV_COLUMNS))
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
