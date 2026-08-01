"""Assemble the macOS .app bundle for the DjiEmbed GUI (#414 Stage D).

Pure helpers (unit-tested on any OS via tests/test_macos_bundle.py) plus a
thin CLI used by .github/workflows/release-macos.yml on the macos-14
runner. Layout contract: the GUI publish output and the CLI live together
in Contents/MacOS (CliLocator finds dji-embed beside the GUI executable,
same as the Windows installer layout).
"""

from __future__ import annotations

import argparse
import plistlib
import shutil
from pathlib import Path

APP_DIR_NAME = "DJI Metadata Embedder.app"
BUNDLE_ID = "com.callmarcus.djiembed"
MAIN_EXECUTABLE = "DjiEmbed.Gui"
ICNS_NAME = "app-icon.icns"


def info_plist(version: str) -> dict[str, object]:
    """The complete Info.plist contents for the given release version."""
    return {
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": MAIN_EXECUTABLE,
        # Finder short name; Apple caps CFBundleName at 15 characters.
        "CFBundleName": "DJI Embedder",
        "CFBundleDisplayName": "DJI Metadata Embedder",
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleVersion": version,
        "CFBundleShortVersionString": version,
        "CFBundleIconFile": ICNS_NAME,
        "NSHighResolutionCapable": True,
        # .NET 10 supports macOS 14 "Sonoma" and later.
        "LSMinimumSystemVersion": "14.0",
    }


def iconset_entries(source_px: int) -> list[tuple[str, int]]:
    """(filename, pixel size) pairs for an iconutil .iconset, skipping any
    rendition that would upscale a source_px-square master image."""
    entries: list[tuple[str, int]] = []
    for point in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            px = point * scale
            if px > source_px:
                continue
            suffix = "" if scale == 1 else "@2x"
            entries.append((f"icon_{point}x{point}{suffix}.png", px))
    return entries


def assemble(
    publish_dir: Path, cli: Path, icns: Path, version: str, out_dir: Path
) -> Path:
    """Build <out_dir>/<APP_DIR_NAME> from a dotnet publish directory, a
    signed dji-embed binary, and a compiled .icns. Replaces any previous
    bundle at that path."""
    app = out_dir / APP_DIR_NAME
    if app.exists():
        shutil.rmtree(app)
    contents = app / "Contents"
    macos = contents / "MacOS"
    shutil.copytree(publish_dir, macos)
    shutil.copy2(cli, macos / "dji-embed")
    (macos / "dji-embed").chmod(0o755)
    resources = contents / "Resources"
    resources.mkdir()
    shutil.copy2(icns, resources / ICNS_NAME)
    with (contents / "Info.plist").open("wb") as fh:
        plistlib.dump(info_plist(version), fh)
    return app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    icon = sub.add_parser("iconset", help="print iconutil renditions")
    icon.add_argument("--source-px", type=int, required=True)
    asm = sub.add_parser("assemble", help="build the .app bundle")
    asm.add_argument("--publish-dir", type=Path, required=True)
    asm.add_argument("--cli", type=Path, required=True)
    asm.add_argument("--icns", type=Path, required=True)
    asm.add_argument("--version", required=True)
    asm.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "iconset":
        for name, px in iconset_entries(args.source_px):
            print(f"{name} {px}")
    else:
        print(assemble(args.publish_dir, args.cli, args.icns,
                       args.version, args.out))


if __name__ == "__main__":
    main()
