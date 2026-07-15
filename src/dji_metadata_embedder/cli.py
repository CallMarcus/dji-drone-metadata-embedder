"""Command line interface for DJI Metadata Embedder."""

from __future__ import annotations

import json
import sys
import webbrowser
import click
from collections.abc import Sequence
from pathlib import Path
from typing import Any

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
    folder_has_photos,
    redact_photo_points,
    scan_flights,
    scan_photos,
    serve_directory,
    write_flights_geojson,
    write_flights_html,
    write_flights_kml,
    write_photos_geojson,
    write_photos_html,
    write_photos_kml,
)
from .mp4_telemetry import Mp4TelemetryError
from .progress import make_progress
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


def _launched_from_explorer() -> bool:
    """True when this process is the sole owner of its console window.

    That is the double-click / drag-and-drop launch shape on Windows:
    Explorer spawns a fresh console holding only this process, and it
    vanishes the instant the process exits. Started from cmd/PowerShell,
    the shell also owns the console, so the count is >= 2.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        process_ids = (ctypes.c_uint32 * 2)()
        count = ctypes.windll.kernel32.GetConsoleProcessList(process_ids, 2)
        return count <= 1
    except Exception:  # no console at all, or a non-standard runtime
        return False


def _dragdrop_pause() -> None:
    """Hold an Explorer-spawned console open so the message stays readable."""
    if getattr(sys, "frozen", False) and _launched_from_explorer():
        click.echo()
        click.pause("Press any key to close this window ...")


def _echo_dragdrop_hint() -> None:
    """Friendly double-click message instead of the full CLI help dump."""
    click.echo(f"dji-embed {__version__}")
    click.echo()
    click.echo(
        "To make a map of your drone footage: drag the folder that holds\n"
        "your videos or photos onto dji-embed.exe, and the map will open\n"
        "in your browser."
    )
    click.echo()
    click.echo("For everything else, open a terminal and run: dji-embed --help")


class DragDropGroup(click.Group):
    """Click group that also accepts a bare directory argument.

    Windows Explorer passes a dragged folder as ``argv[1]`` with no
    subcommand; routing that to the hidden ``dragdrop`` command is the whole
    no-command-line story of issue #264 stage 1.
    """

    def main(
        self, args: Sequence[str] | None = None, *pargs: Any, **extra: Any
    ) -> Any:
        # args must be passed through untouched: click only applies its
        # Windows glob/~/env expansion when it receives args=None.
        argv = sys.argv[1:] if args is None else args
        if not argv and getattr(sys, "frozen", False) and _launched_from_explorer():
            _echo_dragdrop_hint()
            _dragdrop_pause()
            return None
        try:
            return super().main(
                None if args is None else list(args), *pargs, **extra
            )
        except SystemExit as e:
            if e.code not in (0, None):
                # Errors on a double-click launch print into a console that
                # closes instantly; hold it open (no-op elsewhere).
                _dragdrop_pause()
            raise

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str, click.Command, list[str]]:
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            paths = [Path(a) for a in args]
            if all(p.exists() for p in paths):
                if any(p.is_dir() for p in paths):
                    cmd = self.get_command(ctx, "dragdrop")
                    assert cmd is not None  # registered below in this module
                    return "dragdrop", cmd, args
                raise click.UsageError(
                    f"'{args[0]}' is a file. To make a map, drag the folder "
                    "that contains your footage instead."
                )
            if paths and paths[0].is_dir():
                raise click.UsageError(
                    f"'{args[0]}' is a folder, and bare-folder mapping takes "
                    "no other arguments. For options, name the command: "
                    f"dji-embed flightmap {args[0]} ... or "
                    f"dji-embed photomap {args[0]} ..."
                )
            raise


@click.group(
    cls=DragDropGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
)
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


# Shared by photomap/flightmap/embed/check. Contract: docs/PROGRESS_JSONL.md.
_progress_option = click.option(
    "--progress",
    "progress_mode",
    type=click.Choice(["jsonl"]),
    default=None,
    help="Emit machine-readable progress events on stdout, one JSON object "
    "per line (see docs/PROGRESS_JSONL.md). Suppresses human output on "
    "stdout; warnings and logs still go to stderr.",
)


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
@_progress_option
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
    progress_mode: str | None,
    verbose: bool,
    quiet: bool,
) -> None:
    """Embed telemetry from SRT files into MP4 videos."""
    progress = make_progress(progress_mode)
    if progress.active:
        quiet = True  # stdout belongs to the JSONL events
    setup_logging(verbose, quiet)
    progress.start("embed")
    try:
        deps_ok, missing = check_dependencies()
        if not deps_ok:
            raise click.ClickException(
                f"Missing dependencies: {', '.join(missing)}"
            )

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
        result = embedder.process_directory(
            use_exiftool=exiftool,
            on_progress=progress.advance if progress.active else None,
        )
    except click.ClickException as e:
        progress.error(e.format_message())
        raise
    if progress.active:
        for message in result["warnings"] + result["errors"]:
            progress.warning(message)
        progress.result(
            # Per-file failures keep the existing exit-0 behaviour; ok=false
            # is the machine-readable signal (see docs/PROGRESS_JSONL.md).
            ok=not result["errors"],
            outputs=[result["output_directory"]],
            summary={
                "processed": result["processed"],
                "total": result["total_files"],
                "warnings": len(result["warnings"]),
                "errors": len(result["errors"]),
                "output_directory": result["output_directory"],
            },
        )


@main.command()
@click.argument("paths", nargs=-1, type=click.Path())
@_progress_option
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress info output")
def check(
    paths: tuple[str, ...],
    progress_mode: str | None,
    verbose: bool,
    quiet: bool,
) -> None:
    """Check media files for embedded metadata."""
    progress = make_progress(progress_mode)
    setup_logging(verbose, quiet)
    progress.start("check", total=len(paths))
    try:
        if not paths:
            raise click.ClickException("No file or directory specified")
        files: dict[str, dict] = {}
        for index, target in enumerate(paths, start=1):
            progress.advance(index, len(paths), item=target)
            result = check_metadata(target)
            files[target] = result
            if not progress.active:
                click.echo(f"{target}: {result}")
    except click.ClickException as e:
        progress.error(e.format_message())
        raise
    progress.result(
        ok=True,
        outputs=[],
        summary={"checked": len(paths), "files": files},
    )


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
@click.option(
    "--redact",
    type=click.Choice(["none", "fuzz"], case_sensitive=False),
    default="none",
    show_default=True,
    help="GPS redaction: fuzz coarsens every photo location to ~100 m "
    "before writing (all formats). Linked/attached original files still "
    "carry exact GPS in their EXIF.",
)
@click.option(
    "--serve", "serve_map", is_flag=True,
    help="After writing the map, serve its folder at a private local address "
         "(http://127.0.0.1, this computer only) and open the browser. "
         "Implies --link-originals. Needed for the 360° viewer, which "
         "browsers block when the map is opened straight from disk. "
         "With -v, each HTTP request is logged.",
)
@_progress_option
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
    redact: str,
    serve_map: bool,
    progress_mode: str | None,
    verbose: bool,
    quiet: bool,
) -> None:
    """Map GPS-tagged still photos (JPG/JPEG/DNG) as HTML, KML, or GeoJSON.

    Scans DIRECTORY with ExifTool, drops a pin per geotagged photo, and embeds
    each photo's EXIF thumbnail in the html/kml popups. The html map clusters
    nearby pins and loads Leaflet and OpenStreetMap tiles from the internet.
    Requires ExifTool (see 'dji-embed doctor'). GPano 360° panoramas open in
    an embedded viewer when --link-originals is set. Use --serve to view the
    map over local HTTP — required for the 360° viewer, which browsers block
    on maps opened straight from disk.
    """
    progress = make_progress(progress_mode)
    if progress.active:
        quiet = True  # stdout belongs to the JSONL events
        if serve_map:
            raise click.UsageError(
                "--serve cannot be combined with --progress jsonl (serving "
                "blocks; open the written HTML yourself instead)"
            )
    setup_logging(verbose, quiet)
    if serve_map:
        if fmt.lower() not in ("html", "all"):
            raise click.UsageError(
                "--serve requires the HTML map (use -f html or -f all)"
            )
        if link_base is not None:
            click.echo(
                "Note: --serve serves the map's own folder; --link-base "
                "links may not resolve through it",
                err=True,
            )
        link_originals = True
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
    progress.start("photomap")
    try:
        try:
            points, skipped = scan_photos(src, recursive=recursive)
        except PhotomapError as e:
            raise click.ClickException(str(e))
        if redact.lower() == "fuzz":
            points = redact_photo_points(points, "fuzz")
            if link_originals:
                click.echo(
                    "Note: --redact fuzz coarsens the map coordinates, but the "
                    "linked original photos still carry exact GPS in their EXIF",
                    err=True,
                )
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
        for name in skipped:
            progress.warning("No GPS data", item=name)
            if verbose:
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
            targets = [
                (f, base.with_suffix(f".{f}")) for f in ("html", "kml", "geojson")
            ]
        else:
            f = fmt.lower()
            out = Path(output) if output else src / f"photomap.{f}"
            targets = [(f, out)]
        for f, out in targets:
            try:
                if f == "html":
                    write_photos_html(
                        points, out, map_title, link_base=html_link_base
                    )
                elif f == "kml":
                    write_photos_kml(points, out, map_title)
                else:
                    write_photos_geojson(points, out)
            except OSError as e:
                raise click.ClickException(f"Could not write {out}: {e}")
    except click.ClickException as e:
        progress.error(e.format_message())
        raise
    progress.result(
        ok=True,
        outputs=[str(out.resolve()) for _f, out in targets],
        summary={"photos": len(points), "skipped": len(skipped)},
    )
    if serve_map:
        html_out = next(out for f, out in targets if f == "html")
        serve_directory(
            html_out.parent,
            html_out.name,
            quiet=quiet,
            log_requests=verbose,
        )


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
@_progress_option
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
    progress_mode: str | None,
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
    progress = make_progress(progress_mode)
    if progress.active:
        quiet = True  # stdout belongs to the JSONL events
    setup_logging(verbose, quiet)
    progress.start("flightmap")
    try:
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
            on_file=progress.advance if progress.active else None,
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
        for name in skipped:
            progress.warning("No GPS telemetry", item=name)
            if verbose:
                click.echo(f"Skipped (no GPS telemetry): {name}", err=True)
        joined = [t for t in tracks if t.segments]
        files_joined = sum(len(t.segments or []) for t in joined)
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
            if joined:
                click.echo(
                    f"Joined {files_joined} files into "
                    f"{len(joined)} flight{'s' if len(joined) != 1 else ''}"
                )
        map_title = title or src.resolve().name
        if fmt.lower() == "all":
            base = Path(output) if output else src / "flightmap.html"
            targets = [
                (f, base.with_suffix(f".{f}")) for f in ("html", "kml", "geojson")
            ]
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
    except click.ClickException as e:
        progress.error(e.format_message())
        raise
    progress.result(
        ok=True,
        outputs=[str(out.resolve()) for _f, out in targets],
        summary={
            "flights": len(tracks),
            "skipped": len(skipped),
            "joined_files": files_joined,
        },
    )


@main.command(hidden=True)
@click.argument(
    "paths",
    nargs=-1,
    required=True,
    type=click.Path(exists=True),
)
@click.pass_context
def dragdrop(ctx: click.Context, paths: tuple[str, ...]) -> None:
    """Map folders dropped onto the EXE and open the results in the browser.

    This runs when dji-embed is invoked with bare path arguments (the shape
    Windows Explorer produces for drag-and-drop): flightmap over each
    folder's .SRT logs and, when the folder holds stills, photomap too —
    both recursive — then every written HTML map opens in the default
    browser. Files in the selection are skipped with a note.
    """
    setup_logging(verbose=False, quiet=False)
    unmapped: list[str] = []
    for target in paths:
        src = Path(target)
        if not src.is_dir():
            click.echo(
                f"Skipping {src.name}: drag folders to map, not single files",
                err=True,
            )
            continue
        maps: list[Path] = []
        flight_out = src / "flightmap.html"
        try:
            ctx.invoke(
                flightmap,
                directory=target,
                recursive=True,
                output=str(flight_out),
            )
            maps.append(flight_out)
        except click.ClickException as e:
            click.echo(f"No flight map for {src}: {e.message}", err=True)
        if folder_has_photos(src):
            photo_out = src / "photomap.html"
            try:
                ctx.invoke(
                    photomap,
                    directory=target,
                    recursive=True,
                    output=str(photo_out),
                )
                maps.append(photo_out)
            except click.ClickException as e:
                click.echo(f"No photo map for {src}: {e.message}", err=True)
        for out in maps:
            webbrowser.open(out.resolve().as_uri())
        if not maps:
            unmapped.append(str(src))
    if unmapped:
        click.echo(
            "Nothing to map: no DJI .SRT flight logs or geotagged photos "
            f"found in {', '.join(unmapped)}",
            err=True,
        )
        sys.exit(ExitCode.GENERAL_ERROR)


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
@click.option(
    "--online/--offline",
    "online",
    default=None,
    help="Enable/disable the online update check (PyPI + ExifTool pin) for "
    "this run and remember the choice. Default: remembered choice, asked "
    "once on interactive terminals. DJIEMBED_NO_UPDATE_CHECK=1 hard-disables.",
)
@click.pass_context
def doctor(
    ctx: click.Context,
    verbose: bool,
    quiet: bool,
    install_tool: str | None,
    force: bool,
    online: bool | None,
) -> None:
    """Show system information and verify dependencies."""
    log_json = ctx.obj.get('log_json', False)
    setup_logging(verbose, quiet, log_json)

    try:
        if install_tool == "exiftool":
            exe = provision_exiftool(force=force)
            click.echo(f"ExifTool {EXIFTOOL_VERSION} installed: {exe}")
        run_doctor(online=online)
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
