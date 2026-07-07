import hashlib
import io
import os
import tarfile
import zipfile
from pathlib import Path
from urllib.error import URLError

import pytest

from dji_metadata_embedder.utils import provision
from dji_metadata_embedder.utils.provision import (
    EXIFTOOL_VERSION,
    ProvisionError,
    _fetch_artifact,
    _verify_sha256,
    provision_exiftool,
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


def _make_windows_zip(path, version=EXIFTOOL_VERSION):
    """Mimic exiftool-<ver>_64.zip: top dir with exiftool(-k).exe + exiftool_files/."""
    top = f"exiftool-{version}_64"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"{top}/exiftool(-k).exe", "fake-exe")
        zf.writestr(f"{top}/exiftool_files/perl.dll", "fake-dll")


def _make_unix_tarball(path, version=EXIFTOOL_VERSION):
    """Mimic Image-ExifTool-<ver>.tar.gz: top dir with exiftool script + lib/."""
    top = f"Image-ExifTool-{version}"
    script = f"#!/bin/sh\necho {version}\n".encode()
    with tarfile.open(path, "w:gz") as tf:
        info = tarfile.TarInfo(f"{top}/exiftool")
        info.size = len(script)
        tf.addfile(info, io.BytesIO(script))
        lib = f"# perl module for {version}\n".encode()
        info = tarfile.TarInfo(f"{top}/lib/Image/ExifTool.pm")
        info.size = len(lib)
        tf.addfile(info, io.BytesIO(lib))


def _pin_checksum(monkeypatch, artifact_path, artifact_name):
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    monkeypatch.setitem(provision.EXIFTOOL_SHA256, artifact_name, digest)


def _serve_fixture(monkeypatch, artifact_path):
    def fake_fetch(artifact, dest):
        dest.write_bytes(artifact_path.read_bytes())

    monkeypatch.setattr(provision, "_fetch_artifact", fake_fetch)


def test_provision_windows_layout(monkeypatch, tmp_path):
    monkeypatch.setattr(provision.platform, "system", lambda: "Windows")
    monkeypatch.setattr(provision, "_smoke_version", lambda exe: EXIFTOOL_VERSION)
    name = f"exiftool-{EXIFTOOL_VERSION}_64.zip"
    fixture = tmp_path / name
    _make_windows_zip(fixture)
    _pin_checksum(monkeypatch, fixture, name)
    _serve_fixture(monkeypatch, fixture)

    root = tmp_path / "tools"
    exe = provision_exiftool(root=root)

    assert exe == root / f"exiftool-{EXIFTOOL_VERSION}" / "exiftool.exe"
    assert exe.exists()
    assert (exe.parent / "exiftool_files" / "perl.dll").exists()
    assert not (exe.parent / "exiftool(-k).exe").exists()


def test_provision_unix_layout(monkeypatch, tmp_path):
    monkeypatch.setattr(provision.platform, "system", lambda: "Linux")
    monkeypatch.setattr(provision, "_smoke_version", lambda exe: EXIFTOOL_VERSION)
    monkeypatch.setattr(provision.shutil, "which", lambda name: "/usr/bin/perl")
    name = f"Image-ExifTool-{EXIFTOOL_VERSION}.tar.gz"
    fixture = tmp_path / name
    _make_unix_tarball(fixture)
    _pin_checksum(monkeypatch, fixture, name)
    _serve_fixture(monkeypatch, fixture)

    root = tmp_path / "tools"
    exe = provision_exiftool(root=root)

    assert exe == root / f"exiftool-{EXIFTOOL_VERSION}" / "exiftool"
    assert exe.exists()
    assert (exe.parent / "lib" / "Image" / "ExifTool.pm").exists()
    if os.name != "nt":
        assert os.access(exe, os.X_OK)


@pytest.mark.skipif(os.name == "nt", reason="runs the stub shell script")
def test_provision_unix_smoke_check_runs_real_script(monkeypatch, tmp_path):
    # End-to-end minus network: the real _smoke_version executes the stub.
    monkeypatch.setattr(provision.platform, "system", lambda: "Linux")
    monkeypatch.setattr(provision.shutil, "which", lambda name: "/usr/bin/perl")
    name = f"Image-ExifTool-{EXIFTOOL_VERSION}.tar.gz"
    fixture = tmp_path / name
    _make_unix_tarball(fixture)
    _pin_checksum(monkeypatch, fixture, name)
    _serve_fixture(monkeypatch, fixture)

    exe = provision_exiftool(root=tmp_path / "tools")
    assert exe.exists()


def test_provision_checksum_mismatch_installs_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(provision.platform, "system", lambda: "Linux")
    monkeypatch.setattr(provision.shutil, "which", lambda name: "/usr/bin/perl")
    name = f"Image-ExifTool-{EXIFTOOL_VERSION}.tar.gz"
    fixture = tmp_path / name
    _make_unix_tarball(fixture)
    # Deliberately do NOT pin the fixture's checksum: real pin != fixture hash.
    _serve_fixture(monkeypatch, fixture)

    root = tmp_path / "tools"
    with pytest.raises(ProvisionError, match="Checksum mismatch"):
        provision_exiftool(root=root)
    assert not (root / f"exiftool-{EXIFTOOL_VERSION}").exists()
    assert not list(root.glob("*.part"))  # temp download cleaned up


def test_provision_noop_when_already_installed(monkeypatch, tmp_path):
    monkeypatch.setattr(provision.platform, "system", lambda: "Linux")
    monkeypatch.setattr(provision, "_smoke_version", lambda exe: EXIFTOOL_VERSION)
    root = tmp_path / "tools"
    existing = root / f"exiftool-{EXIFTOOL_VERSION}" / "exiftool"
    existing.parent.mkdir(parents=True)
    existing.write_text("#!/bin/sh\n")

    def explode(artifact, dest):
        raise AssertionError("must not download when already provisioned")

    monkeypatch.setattr(provision, "_fetch_artifact", explode)
    assert provision_exiftool(root=root) == existing


def test_provision_force_reinstalls(monkeypatch, tmp_path):
    monkeypatch.setattr(provision.platform, "system", lambda: "Linux")
    monkeypatch.setattr(provision, "_smoke_version", lambda exe: EXIFTOOL_VERSION)
    monkeypatch.setattr(provision.shutil, "which", lambda name: "/usr/bin/perl")
    name = f"Image-ExifTool-{EXIFTOOL_VERSION}.tar.gz"
    fixture = tmp_path / name
    _make_unix_tarball(fixture)
    _pin_checksum(monkeypatch, fixture, name)
    fetched = []

    def fake_fetch(artifact, dest):
        fetched.append(artifact)
        dest.write_bytes(fixture.read_bytes())

    monkeypatch.setattr(provision, "_fetch_artifact", fake_fetch)
    root = tmp_path / "tools"
    existing = root / f"exiftool-{EXIFTOOL_VERSION}" / "exiftool"
    existing.parent.mkdir(parents=True)
    existing.write_text("stale")

    provision_exiftool(root=root, force=True)
    assert fetched  # re-downloaded despite existing install


def test_provision_missing_perl_fails_clearly(monkeypatch, tmp_path):
    monkeypatch.setattr(provision.platform, "system", lambda: "Linux")
    monkeypatch.setattr(provision.shutil, "which", lambda name: None)
    with pytest.raises(ProvisionError, match="Perl"):
        provision_exiftool(root=tmp_path / "tools")


def test_reject_unsafe_archive_members(monkeypatch, tmp_path):
    monkeypatch.setattr(provision.platform, "system", lambda: "Windows")
    name = f"exiftool-{EXIFTOOL_VERSION}_64.zip"
    fixture = tmp_path / name
    with zipfile.ZipFile(fixture, "w") as zf:
        zf.writestr("../evil.exe", "boom")
    _pin_checksum(monkeypatch, fixture, name)
    _serve_fixture(monkeypatch, fixture)

    with pytest.raises(ProvisionError, match="Unsafe path"):
        provision_exiftool(root=tmp_path / "tools")


@pytest.mark.skipif(
    not os.environ.get("DJIEMBED_NETWORK_TESTS"),
    reason="real-network test; set DJIEMBED_NETWORK_TESTS=1 to run",
)
def test_provision_real_download(tmp_path):
    exe = provision_exiftool(root=tmp_path / "tools")
    assert exe.exists()


def test_check_dependencies_finds_provisioned_exiftool(monkeypatch, tmp_path):
    """A provisioned copy satisfies the exiftool dependency check."""
    import subprocess

    from dji_metadata_embedder import utilities

    def fake_run(cmd, **kwargs):
        exe = cmd[0] if isinstance(cmd, list) else cmd
        if "exiftool" in str(exe) and str(tmp_path) in str(exe):
            return subprocess.CompletedProcess(cmd, 0, stdout="13.59", stderr="")
        raise FileNotFoundError(exe)

    monkeypatch.setenv("DJIEMBED_TOOLS_DIR", str(tmp_path))
    monkeypatch.delenv("DJIEMBED_EXIFTOOL_PATH", raising=False)
    exe = tmp_path / f"exiftool-{EXIFTOOL_VERSION}" / (
        "exiftool.exe" if provision.platform.system() == "Windows" else "exiftool"
    )
    exe.parent.mkdir(parents=True)
    exe.write_text("stub")
    monkeypatch.setattr(utilities.subprocess, "run", fake_run)

    ok, missing = utilities.check_dependencies()
    assert "exiftool" not in missing


def test_get_tool_versions_sees_provisioned_exiftool(monkeypatch, tmp_path):
    """--version resolves exiftool through the shared resolver (provisioned copy)."""
    import subprocess

    from dji_metadata_embedder import utilities

    monkeypatch.setenv("DJIEMBED_TOOLS_DIR", str(tmp_path))
    monkeypatch.delenv("DJIEMBED_EXIFTOOL_PATH", raising=False)
    exe = tmp_path / f"exiftool-{EXIFTOOL_VERSION}" / (
        "exiftool.exe" if provision.platform.system() == "Windows" else "exiftool"
    )
    exe.parent.mkdir(parents=True)
    exe.write_text("stub")

    def fake_run(cmd, **kwargs):
        first = str(cmd[0] if isinstance(cmd, list) else cmd)
        if str(tmp_path) in first:
            return subprocess.CompletedProcess(cmd, 0, stdout="13.59", stderr="")
        raise FileNotFoundError(first)

    monkeypatch.setattr(utilities.subprocess, "run", fake_run)
    versions = utilities.get_tool_versions()
    assert versions["exiftool"] == "13.59"
