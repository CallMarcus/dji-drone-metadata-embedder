"""Doctor output and --install smoke tests (all external calls mocked)."""

import logging

from click.testing import CliRunner

from dji_metadata_embedder import embedder
from dji_metadata_embedder import cli as cli_mod
from dji_metadata_embedder.utils.provision import ProvisionError


def test_run_doctor_reports_exiftool_version_and_capability(monkeypatch, caplog):
    monkeypatch.setattr(
        "dji_metadata_embedder.utilities.check_dependencies",
        lambda: (True, []),
    )
    monkeypatch.setattr(
        "dji_metadata_embedder.utils.exiftool.exiftool_version", lambda: "12.76"
    )
    monkeypatch.setattr(
        "dji_metadata_embedder.utils.exiftool.exiftool_source", lambda: "PATH"
    )
    with caplog.at_level(logging.INFO):
        embedder.run_doctor()
    text = caplog.text
    assert "12.76" in text
    assert "timed-metadata decode" in text
    assert "UNAVAILABLE" in text
    assert "dji-embed doctor --install exiftool" in text


def test_run_doctor_missing_exiftool_still_reports(monkeypatch, caplog):
    monkeypatch.setattr(
        "dji_metadata_embedder.utilities.check_dependencies",
        lambda: (False, ["exiftool"]),
    )
    with caplog.at_level(logging.INFO):
        embedder.run_doctor()
    assert "exiftool: MISSING" in caplog.text


def test_doctor_install_invokes_provisioning(monkeypatch, tmp_path):
    installed = []

    def fake_provision(force=False):
        installed.append(force)
        return tmp_path / "exiftool"

    monkeypatch.setattr(cli_mod, "provision_exiftool", fake_provision)
    runner = CliRunner()
    result = runner.invoke(cli_mod.main, ["doctor", "--install", "exiftool", "-q"])
    assert installed == [False]
    assert result.exit_code == 0
    assert "installed" in result.output.lower()


def test_doctor_install_force(monkeypatch, tmp_path):
    seen = []

    def fake_provision(force=False):
        seen.append(force)
        return tmp_path / "exiftool"

    monkeypatch.setattr(cli_mod, "provision_exiftool", fake_provision)
    runner = CliRunner()
    result = runner.invoke(
        cli_mod.main, ["doctor", "--install", "exiftool", "--force", "-q"]
    )
    assert seen == [True]
    assert result.exit_code == 0


def test_doctor_install_failure_exits_nonzero(monkeypatch):
    def fake_provision(force=False):
        raise ProvisionError("Checksum mismatch for X")

    monkeypatch.setattr(cli_mod, "provision_exiftool", fake_provision)
    runner = CliRunner()
    result = runner.invoke(cli_mod.main, ["doctor", "--install", "exiftool", "-q"])
    assert result.exit_code != 0
    assert "Checksum mismatch" in result.output


def test_doctor_install_rejects_unknown_tool():
    runner = CliRunner()
    result = runner.invoke(cli_mod.main, ["doctor", "--install", "ffmpeg"])
    assert result.exit_code != 0  # click.Choice rejects it
