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


def test_doctor_ci_env_no_prompt_no_network(monkeypatch, tmp_path):
    """Non-interactive doctor must neither prompt nor touch the network."""
    from dji_metadata_embedder.utils import update_check as uc

    monkeypatch.setenv("DJIEMBED_TOOLS_DIR", str(tmp_path / "dji-embed" / "tools"))

    monkeypatch.delenv("DJIEMBED_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(
        "builtins.input", lambda *a: (_ for _ in ()).throw(AssertionError("prompted"))
    )

    def no_net(*a, **k):
        raise AssertionError("network touched")

    monkeypatch.setattr(uc, "urlopen", no_net)
    runner = CliRunner()
    result = runner.invoke(cli_mod.main, ["doctor", "-q"], env={"CI": "1"})
    assert result.exit_code == 0


def test_doctor_online_flag_respects_kill_switch(monkeypatch, tmp_path):
    """DJIEMBED_NO_UPDATE_CHECK=1 hard-disables even doctor --online."""
    from dji_metadata_embedder.utils import update_check as uc

    monkeypatch.setenv("DJIEMBED_TOOLS_DIR", str(tmp_path / "dji-embed" / "tools"))

    def no_net(*a, **k):
        raise AssertionError("network touched despite kill switch")

    monkeypatch.setattr(uc, "urlopen", no_net)
    runner = CliRunner()
    result = runner.invoke(
        cli_mod.main,
        ["doctor", "--online"],
        env={"DJIEMBED_NO_UPDATE_CHECK": "1"},
    )
    assert result.exit_code == 0
    assert uc.load_consent() is None  # kill switch also blocks persisting


def test_doctor_offline_flag_persists_choice(monkeypatch, tmp_path):
    from dji_metadata_embedder.utils import update_check as uc

    monkeypatch.setenv("DJIEMBED_TOOLS_DIR", str(tmp_path / "dji-embed" / "tools"))

    monkeypatch.delenv("DJIEMBED_NO_UPDATE_CHECK", raising=False)
    runner = CliRunner()
    result = runner.invoke(cli_mod.main, ["doctor", "--offline", "-q"])
    assert result.exit_code == 0
    assert uc.load_consent() is False


def test_doctor_online_flag_checks_and_persists(monkeypatch, caplog, tmp_path):
    from dji_metadata_embedder.utils import update_check as uc

    monkeypatch.setenv("DJIEMBED_TOOLS_DIR", str(tmp_path / "dji-embed" / "tools"))

    monkeypatch.delenv("DJIEMBED_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(uc, "latest_pypi_version", lambda **k: "99.0.0")
    runner = CliRunner()
    with caplog.at_level(logging.INFO):
        result = runner.invoke(cli_mod.main, ["doctor", "--online"])
    assert result.exit_code == 0
    assert uc.load_consent() is True
    assert "99.0.0 available" in caplog.text
    assert "online check: enabled" in caplog.text
