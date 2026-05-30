import argparse
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from rich.progress import Progress

from .dat_parser import parse_v13 as parse_dat_v13
from .utilities import apply_redaction, setup_logging
from .utils import system_info

logger = logging.getLogger(__name__)

# Suffix for temporary output files (before atomic move to final path).
_TEMP_SUFFIX = ".tmp"


def _ffprobe_duration(path: Path) -> Optional[float]:
    """Return media duration in seconds via ffprobe, or None if unreadable."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(path),
            ],
            capture_output=True, text=True, timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    raw = (result.stdout or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _validate_embedded_output(original_path: Path, temp_path: Path) -> bool:
    """Validate temp output before moving to final destination.

    Confirms the embed completed cleanly by comparing media durations — the
    output's duration must be within 1 second of the source's. A size check
    used to live here, but that produced false negatives once we started
    dropping untaggable data streams from DJI footage (issue surfaced while
    testing v1.3.0 against real Air 3S clips): the legitimate output was a
    few percent smaller than the source even though no video frames were
    lost. Duration is what we actually care about — truncation manifests as
    a short duration, which this catches; cosmetic size drops do not.

    Parameters
    ----------
    original_path : Path
        Original source video path.
    temp_path : Path
        Path to the temporary embedded output file.

    Returns
    -------
    bool
        True if validation passes and the file is safe to move to destination.
    """
    if not temp_path.exists():
        logger.debug("Validation failed: temp file does not exist %s", temp_path)
        return False

    out_duration = _ffprobe_duration(temp_path)
    if out_duration is None:
        logger.warning(
            "Validation failed: ffprobe could not read output %s", temp_path.name
        )
        return False

    src_duration = _ffprobe_duration(original_path)
    if src_duration is None:
        # If the source is unreadable we can't compare; trust that the output
        # was at least readable above.
        return True

    # 1 second tolerance covers container rounding and the subtitle track's
    # final-frame extension; anything more is real truncation.
    if out_duration + 1.0 < src_duration:
        logger.warning(
            "Validation failed: output duration %.2fs < source %.2fs for %s",
            out_duration, src_duration, temp_path.name,
        )
        return False

    return True


# Video container extensions the embedder can mux a subtitle track into.
# ``.osv``/``.lrf`` are DJI's 360 video and low-res proxy formats (Avata 360);
# both are ISO BMFF (MP4-family) containers ffmpeg reads like a normal ``.mp4``.
# Matching is case-insensitive; cameras emit upper-case extensions while some
# tools rewrite them lower-case.
_VIDEO_EXTENSIONS = ("mp4", "osv", "lrf")


def discover_video_files(directory: Path) -> list[Path]:
    """Return the video files in *directory* the embedder can process.

    Globs each supported extension in both cases (``*.mp4`` and ``*.MP4``) so
    discovery works on case-sensitive file systems too, then returns a sorted,
    de-duplicated list. On case-insensitive file systems the two globs would
    otherwise yield the same path twice, hence the set.
    """
    matches: set[Path] = set()
    for ext in _VIDEO_EXTENSIONS:
        matches.update(directory.glob(f"*.{ext}"))
        matches.update(directory.glob(f"*.{ext.upper()}"))
    return sorted(matches)


class DJIMetadataEmbedder:
    """Embed DJI telemetry data into video files.

    The embedder scans a directory for MP4 videos and their matching SRT files
    and writes processed copies with subtitle tracks and metadata. A DAT flight
    log can be merged if provided or automatically discovered. Processed files
    are written to ``output_dir``.

    Parameters
    ----------
    directory: path to folder containing MP4/SRT pairs
    output_dir: destination directory for processed files (ignored if overwrite=True)
    overwrite: if True, write embedded video over the original file (in-place)
    dat_path: optional path to a DAT flight log
    dat_autoscan: search for DAT logs matching each video
    redact: GPS redaction mode ("none", "drop", "fuzz")
    time_offset: time offset in seconds to align SRT with MP4
    resample_strategy: resampling strategy for SRT↔MP4 alignment ("linear", "nearest", "cubic")

    Usage:
        embedder = DJIMetadataEmbedder("/videos", time_offset=0.5)
        embedder.process_directory()
    """

    def __init__(
        self,
        directory: str,
        output_dir: Optional[str] = None,
        overwrite: bool = False,
        dat_path: Optional[str] = None,
        dat_autoscan: bool = False,
        redact: str = "none",
        time_offset: float = 0.0,
        resample_strategy: str = "linear",
        container: str = "mp4",
    ):
        self.directory = Path(directory)
        self.output_dir = (
            Path(output_dir) if output_dir else self.directory / "processed"
        )
        self.overwrite = overwrite
        if not self.overwrite:
            self.output_dir.mkdir(exist_ok=True)
        self.dat_path = Path(dat_path) if dat_path else None
        self.dat_autoscan = dat_autoscan
        self.redact = redact
        self.time_offset = time_offset
        self.resample_strategy = resample_strategy
        # Output container. "mp4" (default) drops DJI's untaggable djmd/dbgi
        # data streams; "mkv" preserves them — Matroska's codec table accepts
        # the codec=none streams the MP4 muxer rejects (issue #197).
        self.container = container

    def parse_dji_srt(self, srt_path: Path) -> Dict[str, Any]:
        """Parse DJI SRT file and extract telemetry data."""
        telemetry_data: Dict[str, Any] = {
            "gps_coords": [],
            "altitudes": [],
            "rel_altitudes": [],
            "speeds": [],
            "timestamps": [],
            "camera_info": [],
            "first_gps": None,
            "avg_gps": None,
            "max_altitude": None,
            "flight_duration": None,
            "srt_counts": [],
            "diff_times": [],
            "barometers": [],
        }

        try:
            with open(srt_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Split into subtitle blocks
            blocks = content.strip().split("\n\n")

            for block in blocks:
                lines = block.strip().split("\n")
                if len(lines) >= 3:
                    # Parse timestamp
                    timestamp_line = lines[1]
                    timestamp_match = re.search(
                        r"(\d{2}:\d{2}:\d{2},\d{3})", timestamp_line
                    )
                    if timestamp_match:
                        telemetry_data["timestamps"].append(timestamp_match.group(1))

                    # Parse telemetry data (usually in the 3rd line onward)
                    telemetry_line = " ".join(lines[2:])

                    # Remove HTML tags if present (newer DJI format)
                    if "<font" in telemetry_line:
                        telemetry_line = re.sub(r"<[^>]+>", "", telemetry_line)

                    # Detect comprehensive format with frame counters. Older
                    # firmware labels this ``SrtCnt``; newer firmware (Neo,
                    # Mini 5 Pro, Avata 360) uses ``FrameCnt``. Accept either
                    # spelling and store under the existing ``srt_counts`` key
                    # for backwards compatibility.
                    counter_match = re.search(
                        r"(?:Srt|Frame)Cnt\s*:\s*(\d+)", telemetry_line
                    )
                    diff_time_match = re.search(
                        r"DiffTime\s*:\s*([^\s]+)", telemetry_line
                    )
                    if counter_match or diff_time_match:
                        telemetry_data.setdefault("srt_counts", []).append(
                            int(counter_match.group(1)) if counter_match else None
                        )
                        telemetry_data.setdefault("diff_times", []).append(
                            diff_time_match.group(1) if diff_time_match else None
                        )

                    # Extract GPS coordinates - Multiple format support
                    # Format 1: [latitude: xx.xxx] [longitude: xx.xxx]
                    lat_match = re.search(
                        r"\[latitude:\s*([+-]?\d+\.?\d*)\]", telemetry_line
                    )
                    lon_match = re.search(
                        r"\[longitude:\s*([+-]?\d+\.?\d*)\]", telemetry_line
                    )

                    # Format 2: GPS(lat,lon,alt) — also tolerates a unit
                    # suffix on altitude (e.g. M300 emits ``GPS(lat,lon,0.0M)``)
                    # and an optional space between ``GPS`` and ``(`` used by
                    # the P4 RTK compact single-line family.
                    if not lat_match or not lon_match:
                        gps_match = re.search(
                            r"GPS\s*\(([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)[A-Za-z]*\)",
                            telemetry_line,
                        )
                        if gps_match:
                            lat_match = gps_match
                            lon_match = gps_match
                            lat = float(gps_match.group(1))
                            lon = float(gps_match.group(2))
                        else:
                            lat = None
                            lon = None
                    else:
                        lat = float(lat_match.group(1))
                        lon = float(lon_match.group(1))

                    if lat is not None and lon is not None:
                        telemetry_data["gps_coords"].append((lat, lon))

                    # Extract altitudes - [rel_alt: x.xxx abs_alt: xxx.xxx]
                    alt_match = re.search(
                        r"\[rel_alt:\s*([+-]?\d+\.?\d*)\s*abs_alt:\s*([+-]?\d+\.?\d*)\]",
                        telemetry_line,
                    )
                    if alt_match:
                        rel_alt = float(alt_match.group(1))
                        abs_alt = float(alt_match.group(2))
                        telemetry_data["rel_altitudes"].append(rel_alt)
                        telemetry_data["altitudes"].append(abs_alt)

                    # Extract barometric altitude. Two delimiter variants exist:
                    # Avata 2 parenthesised ``BAROMETER(91.2)`` and Matrice 300
                    # colon form ``BAROMETER:0.3M`` (optional trailing unit).
                    # Barometric height is more reliable than GPS altitude in
                    # tight / FPV environments.
                    baro_match = re.search(
                        r"BAROMETER[(:]\s*([+-]?\d+\.?\d*)[A-Za-z]*\)?",
                        telemetry_line,
                    )
                    if baro_match:
                        telemetry_data["barometers"].append(
                            float(baro_match.group(1))
                        )

                    # Extract camera info including extended fields
                    iso_match = re.search(r"\[iso\s*:\s*(\d+)\]", telemetry_line)
                    shutter_match = re.search(
                        r"\[shutter\s*:\s*([^\]]+)\]", telemetry_line
                    )
                    # Aperture is reported two ways: legacy models use an
                    # f-number*100 integer (``[fnum : 170]`` → f/1.7) while
                    # current models (Avata 360, Mini 5 Pro, …) emit a literal
                    # decimal (``[fnum: 1.9]``). Capture both; the value is
                    # stored verbatim without interpretation.
                    fnum_match = re.search(
                        r"\[fnum\s*:\s*([+-]?\d+\.?\d*)\]", telemetry_line
                    )
                    ev_match = re.search(r"\[ev\s*:\s*([^\]]+)\]", telemetry_line)
                    # P4 RTK compact single-line family uses free-standing
                    # tokens (``F/5.6, SS 400, ISO 100, EV 0``) rather than
                    # the bracketed ``[fnum:…]`` syntax. Fall back to those
                    # when the bracket form did not match.
                    if not fnum_match:
                        fnum_match = re.search(
                            r"(?<![A-Za-z])F/(\d+\.?\d*)", telemetry_line
                        )
                    if not shutter_match:
                        shutter_match = re.search(
                            r"(?<![A-Za-z])SS\s+(\d+(?:\.\d+)?)", telemetry_line
                        )
                    if not iso_match:
                        iso_match = re.search(
                            r"(?<![A-Za-z])ISO\s+(\d+)", telemetry_line
                        )
                    if not ev_match:
                        ev_match = re.search(
                            r"(?<![A-Za-z])EV\s+([+-]?\d+\.?\d*)", telemetry_line
                        )
                    ct_match = re.search(r"\[ct\s*:\s*([^\]]+)\]", telemetry_line)
                    color_md_match = re.search(
                        r"\[color_md\s*:\s*([^\]]+)\]", telemetry_line
                    )
                    focal_len_match = re.search(
                        r"\[focal_len\s*:\s*([^\]]+)\]", telemetry_line
                    )

                    if (
                        iso_match
                        or shutter_match
                        or fnum_match
                        or ev_match
                        or ct_match
                        or color_md_match
                        or focal_len_match
                    ):
                        camera_data = {}
                        if iso_match:
                            camera_data["iso"] = iso_match.group(1)
                        if shutter_match:
                            camera_data["shutter"] = shutter_match.group(1)
                        if fnum_match:
                            camera_data["fnum"] = fnum_match.group(1)
                        if ev_match:
                            camera_data["ev"] = ev_match.group(1)
                        if ct_match:
                            camera_data["ct"] = ct_match.group(1)
                        if color_md_match:
                            camera_data["color_md"] = color_md_match.group(1)
                        if focal_len_match:
                            camera_data["focal_len"] = focal_len_match.group(1)

                        telemetry_data["camera_info"].append(camera_data)

            # Calculate summary statistics
            if telemetry_data["gps_coords"]:
                telemetry_data["first_gps"] = telemetry_data["gps_coords"][0]
                avg_lat = sum(coord[0] for coord in telemetry_data["gps_coords"]) / len(
                    telemetry_data["gps_coords"]
                )
                avg_lon = sum(coord[1] for coord in telemetry_data["gps_coords"]) / len(
                    telemetry_data["gps_coords"]
                )
                telemetry_data["avg_gps"] = (avg_lat, avg_lon)

            if telemetry_data["altitudes"]:
                telemetry_data["max_altitude"] = max(telemetry_data["altitudes"])

            if telemetry_data["rel_altitudes"]:
                telemetry_data["max_rel_altitude"] = max(
                    telemetry_data["rel_altitudes"]
                )

            if telemetry_data["timestamps"] and len(telemetry_data["timestamps"]) > 1:
                # Calculate flight duration
                first_time = telemetry_data["timestamps"][0].split(",")[0]
                last_time = telemetry_data["timestamps"][-1].split(",")[0]
                telemetry_data["flight_duration"] = f"{first_time} - {last_time}"

            # Get camera settings from first frame
            if telemetry_data["camera_info"]:
                telemetry_data["camera_settings"] = telemetry_data["camera_info"][0]

        except Exception as e:
            logger.error("Error parsing SRT file %s: %s", srt_path, e)

        return telemetry_data

    def embed_metadata_ffmpeg(
        self,
        video_path: Path,
        srt_path: Path,
        telemetry: Dict[str, Any],
        output_path: Path,
    ) -> bool:
        """Embed SRT as subtitle track and add metadata using ffmpeg."""
        import os
        import platform

        try:
            # Check for ffmpeg in environment variable first (Windows)
            ffmpeg_cmd = "ffmpeg"
            if platform.system() == "Windows":
                env_ffmpeg = os.environ.get("DJIEMBED_FFMPEG_PATH")
                if env_ffmpeg and Path(env_ffmpeg).exists():
                    ffmpeg_cmd = env_ffmpeg

            # Build ffmpeg command.
            #
            # MP4 (default): -map 0 -map -0:d -map 1 keeps every video/audio
            # stream from the source plus the SRT subtitle, but explicitly
            # drops DJI's proprietary data streams (`djmd` / `dbgi`, gyro and
            # debug metadata on Air 3S / Neo 2 / etc.). The MP4 muxer cannot
            # tag their codec, so without the drop the whole mux fails with
            # "Could not find tag for codec none". Background: GH discussion
            # #192, follow-up to #193.
            #
            # MKV (--container mkv): Matroska's codec table accepts those
            # streams, so we keep -map 0 (no -0:d) to round-trip djmd/dbgi
            # byte-for-byte, and use the Matroska-native `srt` subtitle codec
            # rather than the MP4-only `mov_text` (issue #197).
            if self.container == "mkv":
                stream_maps = ["-map", "0", "-map", "1"]
                subtitle_codec = "srt"
            else:
                stream_maps = ["-map", "0", "-map", "-0:d", "-map", "1"]
                subtitle_codec = "mov_text"
            cmd = [
                ffmpeg_cmd,
                "-i",
                str(video_path),
                "-i",
                str(srt_path),
                *stream_maps,
                "-c",
                "copy",
                "-c:s",
                subtitle_codec,
                "-metadata:s:s:0",
                "language=eng",
                "-metadata:s:s:0",
                "title=Telemetry Data",
            ]

            # Add GPS metadata if available
            if telemetry["first_gps"]:
                lat, lon = telemetry["first_gps"]
                cmd.extend(
                    [
                        "-metadata",
                        f"location={lat:+.6f}{lon:+.6f}/",
                        "-metadata",
                        f"location-eng={lat:+.6f}{lon:+.6f}/",
                    ]
                )

            # Add other metadata
            if telemetry["max_altitude"]:
                cmd.extend(["-metadata", f'altitude={telemetry["max_altitude"]:.1f}'])

            # Add creation date from filename if it matches DJI pattern
            filename_date_match = re.search(r"DJI_(\d{8})_(\d{6})", video_path.stem)
            if filename_date_match:
                date_str = filename_date_match.group(1)
                time_str = filename_date_match.group(2)
                creation_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
                cmd.extend(["-metadata", f"creation_time={creation_date}"])

            # Output file
            cmd.extend(["-y", str(output_path)])

            # Run ffmpeg
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info("Successfully processed: %s", video_path.name)
                return True
            else:
                logger.error("FFmpeg error for %s: %s", video_path.name, result.stderr)
                return False

        except Exception as e:
            logger.error("Error processing %s: %s", video_path.name, e)
            return False

    def embed_metadata_exiftool(
        self, video_path: Path, telemetry: Dict[str, Any]
    ) -> bool:
        """Use exiftool to embed GPS metadata (alternative/additional method)."""
        import os
        import platform

        try:
            if not telemetry["first_gps"]:
                return False

            lat, lon = telemetry["first_gps"]

            # Check for exiftool in environment variable first (Windows)
            exiftool_cmd = "exiftool"
            if platform.system() == "Windows":
                env_exiftool = os.environ.get("DJIEMBED_EXIFTOOL_PATH")
                if env_exiftool and Path(env_exiftool).exists():
                    exiftool_cmd = env_exiftool

            cmd = [
                exiftool_cmd,
                f"-GPSLatitude={abs(lat)}",
                f'-GPSLatitudeRef={"N" if lat >= 0 else "S"}',
                f"-GPSLongitude={abs(lon)}",
                f'-GPSLongitudeRef={"E" if lon >= 0 else "W"}',
                "-overwrite_original",
                str(video_path),
            ]

            if telemetry["max_altitude"]:
                cmd.insert(-2, f'-GPSAltitude={telemetry["max_altitude"]}')
                cmd.insert(-2, "-GPSAltitudeRef=0")  # Above sea level

            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0

        except Exception as e:
            logger.error("ExifTool error: %s", e)
            return False

    def process_directory(self, use_exiftool: bool = False) -> Dict[str, Any]:
        """Process all MP4/SRT pairs in the directory.
        
        Returns:
            Dict containing processing results and statistics
        """
        # Find all supported video files (.mp4 plus DJI 360 .osv/.lrf).
        video_files = discover_video_files(self.directory)

        # Initialize result structure
        result: Dict[str, Any] = {
            "processed": 0,
            "total_files": len(video_files),
            "warnings": [],
            "errors": [],
            "output_directory": str(self.directory if self.overwrite else self.output_dir),
        }

        if not video_files:
            warning_msg = f"No MP4 files found in {self.directory}"
            logger.warning(warning_msg)
            result["warnings"].append(warning_msg)
            return result

        logger.info("Found %d video files to process", len(video_files))
        if self.overwrite:
            logger.info("Overwrite mode: embedding in place (destination = input folder)\n")
        else:
            logger.info("Output directory: %s\n", self.output_dir)

        success_count = 0

        with Progress() as progress:
            task = progress.add_task("Processing videos", total=len(video_files))
            for video_path in video_files:
                # Look for corresponding SRT file
                srt_path = video_path.with_suffix(".srt")
                if not srt_path.exists():
                    srt_path = video_path.with_suffix(".SRT")

                if not srt_path.exists():
                    warning_msg = f"No SRT file found for: {video_path.name}"
                    logger.warning(warning_msg)
                    result["warnings"].append(warning_msg)
                    progress.advance(task)
                    continue

                progress.update(task, description=video_path.name)
                logger.debug("Processing %s", video_path.name)

                # Parse SRT telemetry
                telemetry = self.parse_dji_srt(srt_path)
                apply_redaction(telemetry, self.redact)

                # Optionally parse DAT telemetry
                dat_file = None
                if self.dat_path:
                    dat_file = self.dat_path
                elif self.dat_autoscan:
                    cand = video_path.with_suffix(".DAT")
                    if cand.exists():
                        dat_file = cand
                    else:
                        matches = list(
                            video_path.parent.glob(f"{video_path.stem}*.DAT")
                        )
                        if matches:
                            dat_file = matches[0]
                if dat_file and dat_file.exists():
                    try:
                        dat_data = parse_dat_v13(dat_file)
                        telemetry["dat_records"] = dat_data.get("records", [])
                    except Exception as e:
                        logger.warning(
                            "Failed to parse DAT file %s: %s", dat_file.name, e
                        )

                # Final output path; write to temp first, then atomic move (issue #162).
                # When overwrite (issue #163), destination = same as input file.
                if self.overwrite:
                    output_path = video_path
                else:
                    # MKV mode rewrites the extension so the preserved
                    # djmd/dbgi data streams land in a Matroska container.
                    out_suffix = (
                        ".mkv" if self.container == "mkv" else video_path.suffix
                    )
                    output_path = (
                        self.output_dir / f"{video_path.stem}_metadata{out_suffix}"
                    )
                temp_output_path = output_path.with_name(
                    output_path.stem + _TEMP_SUFFIX + output_path.suffix
                )

                # Embed metadata using ffmpeg into temp file
                if self.embed_metadata_ffmpeg(
                    video_path, srt_path, telemetry, temp_output_path
                ):
                    if _validate_embedded_output(video_path, temp_output_path):
                        try:
                            os.replace(temp_output_path, output_path)
                        except OSError as e:
                            logger.error(
                                "Failed to move temp output to %s: %s",
                                output_path,
                                e,
                            )
                            if temp_output_path.exists():
                                try:
                                    temp_output_path.unlink()
                                except OSError:
                                    pass
                            progress.advance(task)
                            continue
                        success_count += 1

                        # Optionally use exiftool for additional metadata
                        if use_exiftool:
                            self.embed_metadata_exiftool(output_path, telemetry)

                        # Save telemetry summary as JSON (atomic write)
                        json_path = output_path.parent / f"{video_path.stem}_telemetry.json"
                        json_tmp_path = Path(str(json_path) + _TEMP_SUFFIX)
                        json_data = {
                            "filename": video_path.name,
                            "first_gps": telemetry["first_gps"],
                            "average_gps": telemetry["avg_gps"],
                            "max_altitude": telemetry["max_altitude"],
                            "max_relative_altitude": telemetry.get("max_rel_altitude"),
                            "flight_duration": telemetry["flight_duration"],
                            "num_gps_points": len(telemetry["gps_coords"]),
                            "camera_settings": telemetry.get("camera_settings", {}),
                            "dat_records": len(telemetry.get("dat_records", [])),
                        }
                        # Barometric altitude is only present on some formats
                        # (Avata 2 / Matrice 300); include it when captured.
                        if telemetry.get("barometers"):
                            json_data["barometers"] = telemetry["barometers"]
                        try:
                            with open(json_tmp_path, "w") as f:
                                json.dump(json_data, f, indent=2)
                            os.replace(json_tmp_path, json_path)
                        except OSError as e:
                            logger.warning("Failed to write telemetry JSON: %s", e)
                            if json_tmp_path.exists():
                                try:
                                    json_tmp_path.unlink()
                                except OSError:
                                    pass
                    else:
                        logger.error(
                            "Validation failed for %s; output not saved.",
                            video_path.name,
                        )
                        if temp_output_path.exists():
                            try:
                                temp_output_path.unlink()
                            except OSError:
                                pass
                    progress.advance(task)
                else:
                    if temp_output_path.exists():
                        try:
                            temp_output_path.unlink()
                        except OSError:
                            pass
                    progress.advance(task)

        result["processed"] = success_count
        
        logger.info(
            "Processing complete! Successfully processed %d/%d videos",
            success_count,
            len(video_files),
        )
        logger.info("Processed files saved to: %s", self.output_dir)
        
        return result


def run_doctor() -> None:
    """Print system and dependency information."""
    from .utilities import check_dependencies

    # System information
    logger.info("System information:")
    sys_info = system_info.get_system_summary()
    for key, value in sys_info.items():
        logger.info("  %s: %s", key, value)

    # Check dependencies using the utilities function which checks environment vars
    logger.info("Dependency check:")
    deps_ok, missing = check_dependencies()

    logger.info("  ffmpeg: %s", "FOUND" if "ffmpeg" not in missing else "MISSING")
    logger.info("  exiftool: %s", "FOUND" if "exiftool" not in missing else "MISSING")

    if deps_ok:
        logger.info("All dependencies verified.")
    else:
        logger.warning("Some dependencies are missing or not functional.")


def main():
    parser = argparse.ArgumentParser(
        description="Embed DJI drone telemetry from SRT files into MP4 videos"
    )
    parser.add_argument(
        "directory",
        nargs="?",
        help="Directory containing MP4 and SRT files",
    )
    parser.add_argument(
        "-o", "--output", help="Output directory (default: ./processed); ignored if --overwrite"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite original video files in place (destination = input folder)",
    )
    parser.add_argument(
        "--exiftool", action="store_true", help="Also use exiftool for GPS metadata"
    )
    parser.add_argument("--check", action="store_true", help="Only check dependencies")
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Show system information and verify dependencies",
    )
    parser.add_argument("--dat", help="Path to a DAT flight log to merge")
    parser.add_argument(
        "--dat-auto",
        action="store_true",
        help="Automatically scan for matching DAT files",
    )
    parser.add_argument(
        "--redact",
        choices=["none", "drop", "fuzz"],
        default="none",
        help="Redact GPS coordinates (none, drop or fuzz)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress info output"
    )

    args = parser.parse_args()
    setup_logging(args.verbose, args.quiet)

    logger.info("DJI Drone Media Metadata Embedder")

    if args.doctor:
        run_doctor()
        return

    from .utilities import check_dependencies

    deps_ok, missing = check_dependencies()

    if args.check:
        if not deps_ok:
            logger.error("Missing dependencies: %s", ", ".join(missing))
        return

    if not deps_ok:
        logger.error("Missing dependencies: %s", ", ".join(missing))
        logger.error("Please install missing dependencies before continuing.")
        return

    if not args.directory:
        parser.error("the following arguments are required: directory")

    embedder = DJIMetadataEmbedder(
        args.directory,
        args.output,
        overwrite=args.overwrite,
        dat_path=args.dat,
        dat_autoscan=args.dat_auto,
        redact=args.redact,
    )
    embedder.process_directory(use_exiftool=args.exiftool)


if __name__ == "__main__":
    main()
