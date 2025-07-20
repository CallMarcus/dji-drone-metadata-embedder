"""Command line interface for DJI Metadata Embedder."""

from __future__ import annotations

import click
from pathlib import Path

from . import __version__
from .embedder import DJIMetadataEmbedder, run_doctor
from .metadata_check import check_metadata
from .telemetry_converter import (
    extract_telemetry_to_gpx,
    extract_telemetry_to_csv,
)
from .utilities import check_dependencies, setup_logging


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="dji-embed")
def main() -> None:
    """DJI Metadata Embedder command line interface."""
    pass


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
def wizard() -> None:
    """Launch interactive setup wizard."""
    run_doctor()
    click.echo("Wizard functionality not yet implemented.")


@main.command()
def doctor() -> None:
    """Show system information and verify dependencies."""
    run_doctor()


@main.command()
def gui() -> None:
    """Launch graphical interface (placeholder)."""
    click.echo("Not yet implemented")


@main.command()
def init() -> None:
    """Perform initial setup (placeholder)."""
    click.echo("Not yet implemented")


if __name__ == "__main__":  # pragma: no cover
    main()
