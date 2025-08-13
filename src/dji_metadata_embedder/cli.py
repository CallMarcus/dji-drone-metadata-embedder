"""Command line interface for DJI Metadata Embedder."""

from __future__ import annotations

import json
import sys
import click
from pathlib import Path

from . import __version__
from .embedder import DJIMetadataEmbedder, run_doctor
from .metadata_check import check_metadata
from .telemetry_converter import (
    extract_telemetry_to_gpx,
    extract_telemetry_to_csv,
)
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
      export    Export telemetry to GPX or CSV formats
      probe     Analyze video files for embedded metadata
      doctor    Check system dependencies and configuration
    """
    ctx.ensure_object(dict)
    ctx.obj['log_json'] = log_json


@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option(
    "-o", "--output", type=click.Path(file_okay=False), help="Output directory"
)
@click.option("--exiftool", is_flag=True, help="Also use ExifTool for GPS metadata")
@click.option("--dat", type=click.Path(exists=True), help="DAT flight log to merge")
@click.option("--dat-auto", is_flag=True, help="Auto-detect DAT logs matching videos")
@click.option(
    "--redact",
    type=click.Choice(["none", "drop", "fuzz"], case_sensitive=False),
    default="none",
    show_default=True,
    help="Redact GPS coordinates",
)
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress progress output")
def embed(
    directory: str,
    output: str | None,
    exiftool: bool,
    dat: str | None,
    dat_auto: bool,
    redact: str,
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
        dat_path=dat,
        dat_autoscan=dat_auto,
        redact=redact,
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
@click.argument("command", type=click.Choice(["gpx", "csv"], case_sensitive=False))
@click.argument("input", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path())
@click.option("-b", "--batch", is_flag=True, help="Batch process directory")
@click.option("-v", "--verbose", is_flag=True)
@click.option("-q", "--quiet", is_flag=True)
def convert(
    command: str,
    input: str,
    output: str | None,
    batch: bool,
    verbose: bool,
    quiet: bool,
) -> None:
    """Convert SRT telemetry to GPX or CSV."""
    setup_logging(verbose, quiet)

    src = Path(input)
    if batch and not src.is_dir():
        raise click.ClickException("--batch requires a directory input")

    if batch:
        for srt in src.glob("*.SRT"):
            if command == "gpx":
                extract_telemetry_to_gpx(srt, None)
            else:
                extract_telemetry_to_csv(srt, None)
    else:
        if command == "gpx":
            extract_telemetry_to_gpx(src, output)
        else:
            extract_telemetry_to_csv(src, output)


@main.command()
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress info output")
@click.pass_context
def doctor(ctx: click.Context, verbose: bool, quiet: bool) -> None:
    """Show system information and verify dependencies."""
    log_json = ctx.obj.get('log_json', False)
    setup_logging(verbose, quiet, log_json)
    
    try:
        result = run_doctor()
        if log_json:
            click.echo(json.dumps({"status": "success", "doctor_result": result}))
        sys.exit(ExitCode.SUCCESS)
    except Exception as e:
        error_msg = f"Doctor check failed: {e}"
        if log_json:
            click.echo(json.dumps({"error": "doctor_failed", "message": error_msg}))
        else:
            click.echo(f"Error: {error_msg}", err=True)
        sys.exit(ExitCode.GENERAL_ERROR)


# Legacy command aliases for backward compatibility
@main.command(hidden=True)
@click.argument("paths", nargs=-1, type=click.Path())
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress info output")
@click.pass_context
def check_legacy(ctx: click.Context, paths: tuple[str, ...], verbose: bool, quiet: bool) -> None:
    """Legacy alias for 'probe' command."""
    ctx.invoke(probe, paths=paths, verbose=verbose, quiet=quiet)


@main.command(hidden=True)
@click.argument("command", type=click.Choice(["gpx", "csv"], case_sensitive=False))
@click.argument("input", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path())
@click.option("-b", "--batch", is_flag=True, help="Batch process directory")
@click.option("-v", "--verbose", is_flag=True)
@click.option("-q", "--quiet", is_flag=True)
@click.pass_context
def convert_legacy(ctx: click.Context, command: str, input: str, output: str | None, batch: bool, verbose: bool, quiet: bool) -> None:
    """Legacy alias for 'export' command."""
    ctx.invoke(export, format=command, input=input, output=output, batch=batch, verbose=verbose, quiet=quiet)


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


if __name__ == "__main__":  # pragma: no cover
    main()
