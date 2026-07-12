"""Command line interface for DJI Metadata Embedder."""

from __future__ import annotations

import json
import sys
import click
from pathlib import Path

from . import __version__
from .embedder import DJIMetadataEmbedder, run_doctor
from .utils.provision import EXIFTOOL_VERSION, provision_exiftool
from .metadata_check import check_metadata
from .telemetry_converter import (
    extract_telemetry_to_gpx,
    extract_telemetry_to_csv,
    parse_utc_offset,
    summarize_sun,
)
from .geo import (
    convert_to_geojson,
    convert_to_kml,
    convert_to_html,
    convert_to_cot,
    PhotomapError,
    scan_flights,
    scan_photos,
    write_flights_geojson,
    write_flights_html,
    write_flights_kml,
    write_photos_geojson,
    write_photos_html,
    write_photos_kml,
)
from .mp4_telemetry import Mp4TelemetryError
from .utilities import check_dependencies, setup_logging, get_tool_versions


# Exit codes for consistent CLI behavior
class ExitCode:
    SUCCESS = 0
    GENERAL_ERROR = 1
    DEPENDENCY_ERROR = 2
    VALIDATION_ERROR = 3
    FILE_ERROR = 4
    PARSER_ERROR = 5


def _print_version(ctx: click.Context, param: click.Parameter, value: bool) -> None:
    """Print application and toolchain versions."""
    if not value or ctx.resilient_parsing:
        return
    click.echo(f"dji-embed {__version__}")
    versions = get_tool_versions()
    for name in ("ffmpeg", "exiftool"):
        ver = versions.get(name)
        if ver:
            line = ver if ver.lower().startswith(name) else f"{name} {ver}"
        else:
            line = f"{name} not found"
        click.echo(line)
    ctx.exit(ExitCode.SUCCESS)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--version",
    is_flag=True,
    expose_value=False,
    is_eager=True,
    callback=_print_version,
    help="Show version and exit",
)
@click.option(
    "--log-json",
    is_flag=True,
    help="Output structured JSON logs for machine processing",
    envvar="DJIEMBED_LOG_JSON",
)
@click.pass_context
def main(ctx: click.Context, log_json: bool) -> None:
    """DJI Metadata Embedder - Embed drone telemetry into videos.

    Available commands:
      embed     Embed telemetry from SRT files into MP4 videos
      validate  Validate SRT/MP4 pairs and report drift
      convert   Convert SRT telemetry to GPX or CSV formats
      flightmap Map every flight in a folder of SRT logs on one combined map (experimental)
      photomap  Map GPS-tagged still photos to an HTML/KML/GeoJSON map
      check     Analyze video files for embedded metadata
      doctor    Check system dependencies and configuration
      ui        Launch the local web UI in your browser
    """
    ctx.ensure_object(dict)
    ctx.obj['log_json'] = log_json


@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option(
    "-o", "--output", type=click.Path(file_okay=False), help="Output directory (ignored if --overwrite)"
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Overwrite original video files in place (destination = input folder)",
)
@click.option("--exiftool", is_flag=True, help="Also use ExifTool for GPS metadata")
@click.option("--dat", type=click.Path(exists=True), help="DAT flight log to merge")
@click.option("--dat-auto", is_flag=True, help="Auto-detect DAT logs matching videos")
@click.option(
    "--audio-sidecar",
    is_flag=True,
    help="Auto-detect a same-basename .m4a audio sidecar (e.g. DJI Neo 2) and "
    "mux it into the output (no re-encode).",
)
@click.option(
    "--redact",
    type=click.Choice(["none", "drop", "fuzz"], case_sensitive=False),
    default="none",
    show_default=True,
    help="Redact GPS coordinates",
)
@click.option(
    "--container",
    type=click.Choice(["mp4", "mkv"], case_sensitive=False),
    default="mp4",
    show_default=True,
    help="Output container. Use 'mkv' to preserve DJI djmd/dbgi data streams "
    "(dropped by the mp4 muxer).",
)
@click.option(
    "--extract-home",
    is_flag=True,
    help="Opt-in: extract the HOME/launch point (operator location) into the "
    "JSON sidecar. Never written to the MP4. Subject to --redact.",
)
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress progress output")
def embed(
    directory: str,
    output: str | None,
    overwrite: bool,
    exiftool: bool,
    dat: str | None,
    dat_auto: bool,
    audio_sidecar: bool,
    redact: str,
    container: str,
    extract_home: bool,
    verbose: bool,
    quiet: bool,
) -> None:
    """Embed telemetry from SRT files into MP4 videos."""
    setup_logging(verbose, quiet)

    deps_ok, missing = check_dependencies()
    if not deps_ok:
        raise click.ClickException(f"Missing dependencies: {', '.join(missing)}")

    embedder = DJIMetadataEmbedder(
        directory,
        output,
        overwrite=overwrite,
        dat_path=dat,
        dat_autoscan=dat_auto,
        redact=redact,
        container=container.lower(),
        extract_home=extract_home,
        audio_sidecar=audio_sidecar,
    )
    embedder.process_directory(use_exiftool=exiftool)


@main.command()
@click.argument("paths", nargs=-1, type=click.Path())
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress info output")
def check(paths: tuple[str, ...], verbose: bool, quiet: bool) -> None:
    """Check media files for embedded metadata."""
    setup_logging(verbose, quiet)

    if not paths:
        raise click.ClickException("No file or directory specified")

    for target in paths:
        result = check_metadata(target)
        click.echo(f"{target}: {result}")


@main.command()
@click.argument(
    "command",
    type=click.Choice(
        ["gpx", "csv", "geojson", "kml", "html", "cot"], case_sensitive=False
    ),
)
@click.argument("input", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path())
@click.option("-b", "--batch", is_flag=True, help="Batch process directory")
@click.option(
    "--tz-offset",
    default="auto",
    show_default=True,
    metavar="OFFSET",
    help="UTC offset for GPX/CoT timestamps, e.g. '+05:30' or '-8'. "
    "'auto' detects it from the SRT file mtime. Ignored for MP4 input "
    "(its GPSDateTime is already UTC).",
)
@click.option(
    "--redact",
    type=click.Choice(["none", "drop", "fuzz"], case_sensitive=False),
    default="none",
    show_default=True,
    help="GPS redaction, applied to the track in every format: drop removes "
    "the track (gpx/geojson/kml/html/cot) or blanks the GPS+sun columns "
    "(csv, rows kept); fuzz coarsens to ~100 m. The opt-in HOME marker is "
    "redacted the same way.",
)
@click.option(
    "--interval",
    type=float,
    default=1.0,
    show_default=True,
    help="cot only: seconds between sampled track points.",
)
@click.option(
    "--cot-type",
    default="a-n-A",
    show_default=True,
    metavar="CODE",
    help="cot only: CoT event type/affiliation code (default neutral air).",
)
@click.option("--footprint", is_flag=True, help="Add camera footprint polygons (geojson/kml, redact=none only)")
@click.option(
    "--footprint-interval",
    type=float,
    default=2.0,
    show_default=True,
    help="Seconds between footprint samples",
)
@click.option("--model", default=None, help="Drone model for the footprint FOV table (e.g. air3, mini4pro)")
@click.option(
    "--extract-home",
    is_flag=True,
    help="Opt-in: extract the HOME/launch point (operator location) into "
    "gpx/csv/geojson output. Subject to --redact.",
)
@click.option("-v", "--verbose", is_flag=True)
@click.option("-q", "--quiet", is_flag=True)
def convert(
    command: str,
    input: str,
    output: str | None,
    batch: bool,
    tz_offset: str,
    redact: str,
    interval: float,
    cot_type: str,
    footprint: bool,
    footprint_interval: float,
    model: str | None,
    extract_home: bool,
    verbose: bool,
    quiet: bool,
) -> None:
    """Convert SRT telemetry to GPX, CSV, GeoJSON, KML, CoT, or a standalone HTML map.

    The html format embeds the flight data but loads Leaflet and the map tiles
    from the internet, so the produced file needs a connection to render.
    """
    setup_logging(verbose, quiet)

    try:
        offset = parse_utc_offset(tz_offset)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="--tz-offset")

    src = Path(input)
    if batch and not src.is_dir():
        raise click.ClickException("--batch requires a directory input")

    # -o pointing at an existing directory means "write <stem>.<ext> in there",
    # matching embed -o semantics (#257).
    if output is not None and Path(output).is_dir():
        suffix = ".cot.xml" if command == "cot" else f".{command}"
        output = str(Path(output) / (src.stem + suffix))

    def run_one(srt: Path, out: str | None) -> None:
        if command == "gpx":
            extract_telemetry_to_gpx(srt, out, tz_offset=offset,
                                     extract_home=extract_home, redact=redact)
        elif command == "csv":
            extract_telemetry_to_csv(srt, out, tz_offset=offset,
                                     extract_home=extract_home, redact=redact)
        elif command == "geojson":
            convert_to_geojson(
                srt, out, redact=redact,
                footprint=footprint, footprint_interval=footprint_interval, model=model,
                extract_home=extract_home,
            )
        elif command == "kml":
            convert_to_kml(
                srt, out, redact=redact,
                footprint=footprint, footprint_interval=footprint_interval, model=model,
            )
        elif command == "cot":
            convert_to_cot(
                srt, out, redact=redact, tz_offset=offset,
                interval=interval, cot_type=cot_type,
            )
        else:  # html
            convert_to_html(srt, out, redact=redact)

    if batch:
        patterns = ("*.SRT", "*.srt", "*.MP4", "*.mp4", "*.MOV", "*.mov")
        seen: set[Path] = set()
        for pattern in patterns:
            for path in src.glob(pattern):
                if path in seen:
                    continue
                seen.add(path)
                try:
                    run_one(path, None)
                except Mp4TelemetryError as e:
                    click.echo(f"Skipping {path.name}: {e}", err=True)
    else:
        try:
            run_one(src, output)
        except Mp4TelemetryError as e:
            raise click.ClickException(str(e))


@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option(
    "-o", "--output", type=click.Path(dir_okay=False),
    help="Output file; used as the base name when --format all",
)
@click.option(
    "-f", "--format", "fmt",
    type=click.Choice(["html", "kml", "geojson", "all"], case_sensitive=False),
    default="html", show_default=True, help="Map output format",
)
@click.option("-r", "--recursive", is_flag=True, help="Scan subdirectories too")
@click.option("--title", default=None, help="Map title (default: directory name)")
@click.option(
    "--link-originals", is_flag=True,
    help="HTML popups link the thumbnail/filename to the original photo file "
         "(resolves while the map stays next to the photos)",
)
@click.option(
    "--link-base", default=None, metavar="PREFIX",
    help="Folder or URL prefix for --link-originals hrefs, for when the "
         "originals do not sit beside the HTML (e.g. photos/ or "
         "https://example.com/photos/)",
)
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress info output")
def photomap(
    directory: str,
    output: str | None,
    fmt: str,
    recursive: bool,
    title: str | None,
    link_originals: bool,
    link_base: str | None,
    verbose: bool,
    quiet: bool,
) -> None:
    """Map GPS-tagged still photos (JPG/JPEG/DNG) as HTML, KML, or GeoJSON.

    Scans DIRECTORY with ExifTool, drops a pin per geotagged photo, and embeds
    each photo's EXIF thumbnail in the html/kml popups. The html map clusters
    nearby pins and loads Leaflet and OpenStreetMap tiles from the internet.
    Requires ExifTool (see 'dji-embed doctor').
    """
    setup_logging(verbose, quiet)
    if link_base is not None and not link_originals:
        raise click.UsageError("--link-base requires --link-originals")
    if link_originals and fmt.lower() not in ("html", "all"):
        click.echo(
            "Note: --link-originals only affects HTML output; "
            f"{fmt.lower()} is unchanged",
            err=True,
        )
    # None = no links (default, self-contained map); "" = originals beside the
    # HTML; otherwise the user-supplied prefix.
    html_link_base = (link_base or "") if link_originals else None
    src = Path(directory)
    try:
        points, skipped = scan_photos(src, recursive=recursive)
    except PhotomapError as e:
        raise click.ClickException(str(e))
    total = len(points) + len(skipped)
    if total == 0:
        raise click.ClickException(
            f"No photos (JPG/JPEG/DNG) found in {src}"
            + ("" if recursive else " (use -r to scan subdirectories)")
        )
    if not points:
        raise click.ClickException(
            f"None of the {total} photos in {src} carry GPS coordinates"
        )
    if verbose:
        for name in skipped:
            click.echo(f"Skipped (no GPS): {name}", err=True)
    if not quiet:
        if skipped:
            click.echo(
                f"Mapped {len(points)} of {total} photos; "
                f"{len(skipped)} had no GPS data (use -v to list them)"
            )
        else:
            click.echo(
                f"Mapped {len(points)} photo{'s' if len(points) != 1 else ''}"
            )
    map_title = title or src.resolve().name
    if fmt.lower() == "all":
        base = Path(output) if output else src / "photomap.html"
        targets = [(f, base.with_suffix(f".{f}")) for f in ("html", "kml", "geojson")]
    else:
        f = fmt.lower()
        out = Path(output) if output else src / f"photomap.{f}"
        targets = [(f, out)]
    for f, out in targets:
        try:
            if f == "html":
                write_photos_html(points, out, map_title, link_base=html_link_base)
            elif f == "kml":
                write_photos_kml(points, out, map_title)
            else:
                write_photos_geojson(points, out)
        except OSError as e:
            raise click.ClickException(f"Could not write {out}: {e}")


@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option(
    "-o", "--output", type=click.Path(dir_okay=False),
    help="Output file; used as the base name when --format all",
)
@click.option(
    "-f", "--format", "fmt",
    type=click.Choice(["html", "kml", "geojson", "all"], case_sensitive=False),
    default="html", show_default=True, help="Map output format",
)
@click.option("-r", "--recursive", is_flag=True, help="Scan subdirectories too")
@click.option("--title", default=None, help="Map title (default: directory name)")
@click.option(
    "--redact",
    type=click.Choice(["none", "fuzz"], case_sensitive=False),
    default="none",
    show_default=True,
    help="GPS redaction: fuzz coarsens every flight to ~100 m before writing",
)
@click.option(
    "--join-gap",
    type=float,
    default=15.0,
    show_default=True,
    metavar="SECONDS",
    help="Chain size-split recordings (DJI starts a new file at the 4 GB "
    "limit) into one flight when the next file's telemetry starts within "
    "SECONDS and resumes where the previous file ended. 0 disables joining.",
)
@click.option(
    "--tz-offset",
    default="auto",
    show_default=True,
    metavar="OFFSET",
    help="UTC offset of the SRT timestamps, e.g. '+05:30' or '-8'. 'auto' "
    "detects it from each file's mtime; pass it explicitly when the files "
    "were copied through zip/cloud transfers that rewrote the mtimes.",
)
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress info output")
def flightmap(
    directory: str,
    output: str | None,
    fmt: str,
    recursive: bool,
    title: str | None,
    redact: str,
    join_gap: float,
    tz_offset: str,
    verbose: bool,
    quiet: bool,
) -> None:
    """Map every flight in a folder of DJI .SRT logs on one combined map (experimental).

    Reads only the .SRT telemetry sidecars (fast — the videos are never
    opened) and draws each flight as its own coloured track with a summary
    popup, as HTML, KML, or GeoJSON. Recordings split at the 4 GB file
    limit are chained back into one flight (see --join-gap). Sidecar-less
    models whose telemetry lives inside the MP4 (Air 3S, Mini 5 Pro, ...)
    need 'dji-embed convert html VIDEO.MP4' per clip instead.
    """
    setup_logging(verbose, quiet)
    try:
        offset = parse_utc_offset(tz_offset)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="--tz-offset")
    src = Path(directory)
    tracks, skipped = scan_flights(
        src,
        recursive=recursive,
        redact=redact.lower(),
        join_gap=join_gap,
        tz_offset=offset,
    )
    total = len(tracks) + len(skipped)
    if total == 0:
        raise click.ClickException(
            f"No .SRT telemetry files found in {src}"
            + ("" if recursive else " (use -r to scan subdirectories)")
        )
    if not tracks:
        raise click.ClickException(
            f"None of the {total} SRT files in {src} contain GPS telemetry"
        )
    if verbose:
        for name in skipped:
            click.echo(f"Skipped (no GPS telemetry): {name}", err=True)
    if not quiet:
        if skipped:
            click.echo(
                f"Mapped {len(tracks)} of {total} flights; "
                f"{len(skipped)} had no GPS telemetry (use -v to list them)"
            )
        else:
            click.echo(
                f"Mapped {len(tracks)} flight{'s' if len(tracks) != 1 else ''}"
            )
        joined = [t for t in tracks if t.segments]
        if joined:
            files_joined = sum(len(t.segments or []) for t in joined)
            click.echo(
                f"Joined {files_joined} files into "
                f"{len(joined)} flight{'s' if len(joined) != 1 else ''}"
            )
    map_title = title or src.resolve().name
    if fmt.lower() == "all":
        base = Path(output) if output else src / "flightmap.html"
        targets = [(f, base.with_suffix(f".{f}")) for f in ("html", "kml", "geojson")]
    else:
        f = fmt.lower()
        out = Path(output) if output else src / f"flightmap.{f}"
        targets = [(f, out)]
    for f, out in targets:
        try:
            if f == "html":
                write_flights_html(tracks, out, map_title)
            elif f == "kml":
                write_flights_kml(tracks, out, map_title)
            else:
                write_flights_geojson(tracks, out)
        except OSError as e:
            raise click.ClickException(f"Could not write {out}: {e}")


@main.command()
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress info output")
@click.option(
    "--install",
    "install_tool",
    type=click.Choice(["exiftool"]),
    help="Download a pinned, checksum-verified copy of the tool into the "
    "per-user tools directory (no admin rights needed), then run the checks.",
)
@click.option(
    "--force",
    is_flag=True,
    help="With --install: reinstall even when already provisioned.",
)
@click.pass_context
def doctor(
    ctx: click.Context, verbose: bool, quiet: bool, install_tool: str | None, force: bool
) -> None:
    """Show system information and verify dependencies."""
    log_json = ctx.obj.get('log_json', False)
    setup_logging(verbose, quiet, log_json)

    try:
        if install_tool == "exiftool":
            exe = provision_exiftool(force=force)
            click.echo(f"ExifTool {EXIFTOOL_VERSION} installed: {exe}")
        run_doctor()
        if log_json:
            click.echo(json.dumps({"status": "success"}))
        sys.exit(ExitCode.SUCCESS)
    except Exception as e:
        error_msg = f"Doctor check failed: {e}"
        if log_json:
            click.echo(json.dumps({"error": "doctor_failed", "message": error_msg}))
        else:
            click.echo(f"Error: {error_msg}", err=True)
        sys.exit(ExitCode.GENERAL_ERROR)


# New validate command for M3 milestone
@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--drift-threshold",
    type=float,
    default=1.0,
    help="Drift threshold in seconds for warnings",
)
@click.option(
    "--format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format for drift report",
)
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress info output")
@click.pass_context
def validate(
    ctx: click.Context,
    directory: str,
    drift_threshold: float,
    format: str,
    verbose: bool,
    quiet: bool,
) -> None:
    """Validate SRT/MP4 pairs and generate drift analysis report."""
    log_json = ctx.obj.get('log_json', False)
    setup_logging(verbose, quiet, log_json)
    
    try:
        from .core.validator import validate_directory
        
        validation_result = validate_directory(
            Path(directory),
            drift_threshold=drift_threshold
        )
        
        if format == "json" or log_json:
            click.echo(json.dumps(validation_result))
        else:
            # Text format output
            click.echo(f"Validation Report for: {directory}")
            click.echo(f"Files processed: {validation_result.get('total_files', 0)}")
            click.echo(f"Valid pairs: {validation_result.get('valid_pairs', 0)}")
            click.echo(f"Issues found: {len(validation_result.get('issues', []))}")
            
            for issue in validation_result.get('issues', []):
                click.echo(f"  ⚠️ {issue}")
        
        # Exit with appropriate code
        if validation_result.get('issues'):
            sys.exit(ExitCode.VALIDATION_ERROR)
        else:
            sys.exit(ExitCode.SUCCESS)
            
    except Exception as e:
        error_msg = f"Validation failed: {e}"
        if log_json:
            click.echo(json.dumps({"error": "validation_failed", "message": error_msg}))
        else:
            click.echo(f"Error: {error_msg}", err=True)
        sys.exit(ExitCode.GENERAL_ERROR)


@main.command(name="verify-sun")
@click.argument("srt", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--tz-offset",
    default="auto",
    show_default=True,
    metavar="OFFSET",
    help="UTC offset for the SRT timestamps, e.g. '+05:30' or '-8'. "
    "'auto' detects it from the SRT file mtime.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format",
)
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress info output")
@click.pass_context
def verify_sun(
    ctx: click.Context,
    srt: str,
    tz_offset: str,
    fmt: str,
    verbose: bool,
    quiet: bool,
) -> None:
    """Summarise the sun's position over a clip for shadow cross-checking.

    Computes solar azimuth/elevation for each GPS point so analysts can compare
    shadow direction/length in the footage against the astronomical sun.
    """
    log_json = ctx.obj.get("log_json", False)
    setup_logging(verbose, quiet, log_json)

    try:
        offset = parse_utc_offset(tz_offset)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="--tz-offset")

    try:
        summary = summarize_sun(Path(srt), tz_offset=offset)
    except Exception as e:
        msg = f"verify-sun failed: {e}"
        if log_json:
            click.echo(json.dumps({"error": "verify_sun_failed", "message": msg}))
        else:
            click.echo(f"Error: {msg}", err=True)
        sys.exit(ExitCode.GENERAL_ERROR)

    if fmt == "json" or log_json:
        click.echo(json.dumps(summary))
    else:
        click.echo(f"Sun verification for: {summary['file']}")
        click.echo(
            f"GPS points: {summary['points']}  "
            f"(sun computed: {summary['sun_computed']})"
        )
        if summary["sun_computed"]:
            click.echo(f"UTC span: {summary['utc_start']} -> {summary['utc_end']}")
            click.echo(
                f"Sun elevation: {summary['elevation_min']} -> "
                f"{summary['elevation_max']} deg (min/max)"
            )
            click.echo(
                f"Sun azimuth: {summary['azimuth_start']} -> "
                f"{summary['azimuth_end']} deg (start/end)"
            )
        for flag in summary["flags"]:
            click.echo(f"  WARNING: {flag}")

    sys.exit(ExitCode.SUCCESS)


@main.command()
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Host to bind. Only 127.0.0.1/localhost are intended for use.",
)
@click.option(
    "--port",
    type=int,
    default=None,
    help="Port to bind (default: a random free port).",
)
@click.option(
    "--no-browser",
    is_flag=True,
    help="Do not open the browser automatically.",
)
def ui(host: str, port: int | None, no_browser: bool) -> None:
    """Launch the local web UI in your default browser.

    Requires the ``[ui]`` extra:

        pip install 'dji-drone-metadata-embedder[ui]'
    """
    try:
        from .ui.server import run_server
    except ImportError as exc:  # pragma: no cover - defensive
        raise click.ClickException(f"UI module could not be loaded: {exc}")
    try:
        run_server(host=host, port=port, open_browser=not no_browser)
    except RuntimeError as exc:
        raise click.ClickException(str(exc))


if __name__ == "__main__":  # pragma: no cover
    main()
