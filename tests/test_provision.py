from pathlib import Path

from dji_metadata_embedder.utils import provision
from dji_metadata_embedder.utils.provision import (
    EXIFTOOL_VERSION,
    provisioned_exiftool,
    tools_dir,
)


def test_tools_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("DJIEMBED_TOOLS_DIR", str(tmp_path / "custom"))
    assert tools_dir() == tmp_path / "custom"


def test_tools_dir_platform_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("DJIEMBED_TOOLS_DIR", raising=False)
    monkeypatch.setattr(provision.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert tools_dir() == tmp_path / "xdg" / "dji-embed" / "tools"

    monkeypatch.setattr(provision.platform, "system", lambda: "Windows")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "lad"))
    assert tools_dir() == tmp_path / "lad" / "dji-embed" / "tools"

    monkeypatch.setattr(provision.platform, "system", lambda: "Darwin")
    assert tools_dir() == (
        Path.home() / "Library" / "Application Support" / "dji-embed" / "tools"
    )


def test_provisioned_exiftool_absent(tmp_path):
    assert provisioned_exiftool(tmp_path) is None


def test_provisioned_exiftool_present_unix(monkeypatch, tmp_path):
    monkeypatch.setattr(provision.platform, "system", lambda: "Linux")
    exe = tmp_path / f"exiftool-{EXIFTOOL_VERSION}" / "exiftool"
    exe.parent.mkdir(parents=True)
    exe.write_text("#!/usr/bin/perl\n")
    assert provisioned_exiftool(tmp_path) == exe


def test_provisioned_exiftool_present_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(provision.platform, "system", lambda: "Windows")
    exe = tmp_path / f"exiftool-{EXIFTOOL_VERSION}" / "exiftool.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("stub")
    assert provisioned_exiftool(tmp_path) == exe
