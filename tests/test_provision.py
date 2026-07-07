import hashlib
from pathlib import Path
from urllib.error import URLError

import pytest

from dji_metadata_embedder.utils import provision
from dji_metadata_embedder.utils.provision import (
    EXIFTOOL_VERSION,
    ProvisionError,
    _fetch_artifact,
    _verify_sha256,
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


def test_verify_sha256_accepts_matching_file(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"payload")
    _verify_sha256(f, hashlib.sha256(b"payload").hexdigest())  # no raise


def test_verify_sha256_rejects_mismatch(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"tampered")
    with pytest.raises(ProvisionError, match="Checksum mismatch"):
        _verify_sha256(f, hashlib.sha256(b"payload").hexdigest())


def test_fetch_artifact_falls_back_to_second_mirror(monkeypatch, tmp_path):
    calls = []

    def fake_download(url, dest):
        calls.append(url)
        if "exiftool.org" in url:
            raise URLError("404 gone after release rollover")
        dest.write_bytes(b"from-mirror")

    monkeypatch.setattr(provision, "_download", fake_download)
    dest = tmp_path / "artifact.zip"
    _fetch_artifact("exiftool-13.59_64.zip", dest)
    assert dest.read_bytes() == b"from-mirror"
    assert len(calls) == 2
    assert "sourceforge" in calls[1]


def test_fetch_artifact_reports_all_mirrors_on_total_failure(monkeypatch, tmp_path):
    def fake_download(url, dest):
        raise URLError("no route")

    monkeypatch.setattr(provision, "_download", fake_download)
    with pytest.raises(ProvisionError, match="exiftool.org"):
        _fetch_artifact("exiftool-13.59_64.zip", tmp_path / "artifact.zip")
