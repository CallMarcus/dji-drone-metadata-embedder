"""Tests for tools/macos_bundle.py (#414 Stage D).

Loaded via importlib because tools/ is not a package (same pattern as
test_build_exe.py)."""

import importlib.util
import os
import plistlib
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "macos_bundle.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("macos_bundle", _MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mb = _load_module()


def test_info_plist_core_identity():
    plist = mb.info_plist("2.5.0")
    assert plist["CFBundleExecutable"] == "DjiEmbed.Gui"
    assert plist["CFBundleIdentifier"] == "com.callmarcus.djiembed"
    assert plist["CFBundleName"] == "DJI Embedder"
    assert plist["CFBundleDisplayName"] == "DJI Metadata Embedder"
    assert plist["CFBundlePackageType"] == "APPL"


def test_info_plist_versions_and_platform():
    plist = mb.info_plist("2.5.0")
    assert plist["CFBundleVersion"] == "2.5.0"
    assert plist["CFBundleShortVersionString"] == "2.5.0"
    assert plist["CFBundleIconFile"] == "app-icon.icns"
    assert plist["NSHighResolutionCapable"] is True
    # .NET 10 supports macOS 14 "Sonoma" and later.
    assert plist["LSMinimumSystemVersion"] == "14.0"


def test_info_plist_bundle_name_fits_finder_limit():
    assert len(mb.info_plist("2.5.0")["CFBundleName"]) <= 15


def test_iconset_entries_skip_sizes_that_would_upscale():
    # 256px source: every entry at most 256px, and the 512-point tier
    # (512px and 1024px renditions) is absent entirely.
    assert mb.iconset_entries(256) == [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
    ]


def test_iconset_entries_full_set_with_1024_source():
    entries = mb.iconset_entries(1024)
    assert ("icon_512x512.png", 512) in entries
    assert ("icon_512x512@2x.png", 1024) in entries
    assert len(entries) == 10


def _fake_inputs(tmp_path):
    publish = tmp_path / "publish"
    publish.mkdir()
    (publish / "DjiEmbed.Gui").write_bytes(b"gui")
    (publish / "libcoreclr.dylib").write_bytes(b"dylib")
    cli = tmp_path / "dji-embed"
    cli.write_bytes(b"cli")
    icns = tmp_path / "app-icon.icns"
    icns.write_bytes(b"icns")
    return publish, cli, icns


def test_assemble_builds_the_bundle_layout(tmp_path):
    publish, cli, icns = _fake_inputs(tmp_path)
    app = mb.assemble(publish, cli, icns, "2.5.0", tmp_path / "out")
    assert app == tmp_path / "out" / "DJI Metadata Embedder.app"
    macos = app / "Contents" / "MacOS"
    assert (macos / "DjiEmbed.Gui").read_bytes() == b"gui"
    assert (macos / "libcoreclr.dylib").exists()
    # The CLI sits beside the GUI executable — exactly where CliLocator
    # probes first (and the same layout the Windows installer uses).
    assert (macos / "dji-embed").read_bytes() == b"cli"
    assert os.access(macos / "dji-embed", os.X_OK)
    assert (app / "Contents" / "Resources" / "app-icon.icns").exists()


def test_assemble_writes_a_valid_info_plist(tmp_path):
    publish, cli, icns = _fake_inputs(tmp_path)
    app = mb.assemble(publish, cli, icns, "2.5.0", tmp_path / "out")
    with (app / "Contents" / "Info.plist").open("rb") as fh:
        plist = plistlib.load(fh)
    assert plist == mb.info_plist("2.5.0")


def test_assemble_replaces_a_stale_bundle(tmp_path):
    publish, cli, icns = _fake_inputs(tmp_path)
    out = tmp_path / "out"
    stale = out / "DJI Metadata Embedder.app" / "Contents" / "MacOS"
    stale.mkdir(parents=True)
    (stale / "leftover.dylib").write_bytes(b"old")
    app = mb.assemble(publish, cli, icns, "2.5.0", out)
    assert not (app / "Contents" / "MacOS" / "leftover.dylib").exists()


def test_cli_iconset_prints_name_px_lines(capsys):
    mb.main(["iconset", "--source-px", "256"])
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0] == "icon_16x16.png 16"
    assert lines[-1] == "icon_256x256.png 256"
    assert len(lines) == 7


def test_cli_assemble_end_to_end(tmp_path, capsys):
    publish, cli, icns = _fake_inputs(tmp_path)
    mb.main([
        "assemble",
        "--publish-dir", str(publish),
        "--cli", str(cli),
        "--icns", str(icns),
        "--version", "2.5.0",
        "--out", str(tmp_path / "out"),
    ])
    out = capsys.readouterr().out.strip()
    assert out.endswith("DJI Metadata Embedder.app")
    assert (tmp_path / "out" / "DJI Metadata Embedder.app").is_dir()
