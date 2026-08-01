"""Assemble the macOS .app bundle for the DjiEmbed GUI (#414 Stage D).

Pure helpers (unit-tested on any OS via tests/test_macos_bundle.py) plus a
thin CLI used by .github/workflows/release-macos.yml on the macos-14
runner. Layout contract: the GUI publish output and the CLI live together
in Contents/MacOS (CliLocator finds dji-embed beside the GUI executable,
same as the Windows installer layout).
"""

from __future__ import annotations


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
