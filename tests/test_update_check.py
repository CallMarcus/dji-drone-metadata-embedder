"""Opt-in doctor update check: consent persistence, env detection, silent failure.

All HTTP is mocked — these tests never touch the network. The autouse
``_isolate_tools_dir`` fixture in conftest.py redirects the per-user config
dir (and thus the consent file) into a temp directory.
"""

import io
import json
from urllib.error import URLError

import pytest

from dji_metadata_embedder import __version__
from dji_metadata_embedder.utils import update_check as uc
from dji_metadata_embedder.utils.provision import EXIFTOOL_VERSION


@pytest.fixture(autouse=True)
def _no_hard_disable(monkeypatch, tmp_path):
    """Tests control the kill switch explicitly; consent file is per-test."""
    monkeypatch.delenv("DJIEMBED_NO_UPDATE_CHECK", raising=False)
    monkeypatch.delenv("CI", raising=False)
    # A nested tools dir gives each test its own config dir (its parent),
    # unlike conftest's flat tools0/tools1/... which share a parent.
    monkeypatch.setenv("DJIEMBED_TOOLS_DIR", str(tmp_path / "dji-embed" / "tools"))


# ---------------------------------------------------------------------------
# Consent persistence
# ---------------------------------------------------------------------------


def test_consent_round_trip():
    assert uc.load_consent() is None
    uc.save_consent(True)
    assert uc.load_consent() is True
    uc.save_consent(False)
    assert uc.load_consent() is False


def test_consent_file_lives_next_to_tools_dir():
    from dji_metadata_embedder.utils.provision import tools_dir

    uc.save_consent(True)
    assert uc.consent_path().parent == tools_dir().parent
    data = json.loads(uc.consent_path().read_text(encoding="utf-8"))
    assert data == {"online_check": True}


def test_corrupt_consent_file_reads_as_unset():
    uc.consent_path().parent.mkdir(parents=True, exist_ok=True)
    uc.consent_path().write_text("not json{", encoding="utf-8")
    assert uc.load_consent() is None


# ---------------------------------------------------------------------------
# Consent resolution (prompt / flags / kill switch)
# ---------------------------------------------------------------------------


def test_hard_disable_beats_flag_and_stored_consent(monkeypatch):
    uc.save_consent(True)
    monkeypatch.setenv("DJIEMBED_NO_UPDATE_CHECK", "1")
    online, status = uc.resolve_online(True)
    assert online is False
    assert "DJIEMBED_NO_UPDATE_CHECK" in status
    # the stored choice is left untouched
    assert uc.load_consent() is True


def test_cli_flag_overrides_and_persists(monkeypatch):
    uc.save_consent(False)
    online, status = uc.resolve_online(True)
    assert online is True
    assert uc.load_consent() is True
    online, status = uc.resolve_online(False)
    assert online is False
    assert uc.load_consent() is False
    assert "doctor --online" in status


def test_stored_consent_used_without_prompt(monkeypatch):
    uc.save_consent(True)
    monkeypatch.setattr(uc, "is_interactive", lambda: True)
    monkeypatch.setattr(
        "builtins.input", lambda *a: pytest.fail("must not prompt when stored")
    )
    online, status = uc.resolve_online(None)
    assert online is True
    assert "enabled" in status


def test_non_interactive_never_prompts_never_persists(monkeypatch):
    monkeypatch.setattr(uc, "is_interactive", lambda: False)
    monkeypatch.setattr(
        "builtins.input", lambda *a: pytest.fail("must not prompt non-interactively")
    )
    online, status = uc.resolve_online(None)
    assert online is False
    assert uc.load_consent() is None
    assert "doctor --online" in status


def test_ci_env_var_means_non_interactive(monkeypatch):
    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr(uc.sys, "stdin", io.StringIO())
    assert uc.is_interactive() is False


def test_interactive_prompt_default_is_no(monkeypatch):
    monkeypatch.setattr(uc, "is_interactive", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *a: "")  # plain Enter
    online, _ = uc.resolve_online(None)
    assert online is False
    assert uc.load_consent() is False  # remembered


def test_interactive_prompt_yes_enables_and_persists(monkeypatch):
    monkeypatch.setattr(uc, "is_interactive", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *a: "y")
    online, _ = uc.resolve_online(None)
    assert online is True
    assert uc.load_consent() is True


def test_prompt_eof_degrades_to_no(monkeypatch):
    def _eof(*a):
        raise EOFError

    monkeypatch.setattr(uc, "is_interactive", lambda: True)
    monkeypatch.setattr("builtins.input", _eof)
    online, _ = uc.resolve_online(None)
    assert online is False


# ---------------------------------------------------------------------------
# PyPI version check (mocked HTTP)
# ---------------------------------------------------------------------------


def _fake_urlopen(payload: bytes):
    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.close()

    def opener(req, timeout=None):
        assert timeout is not None and timeout <= 5, "timeout must be bounded"
        return _Resp(payload)

    return opener


def test_latest_pypi_version_parses_json(monkeypatch):
    body = json.dumps({"info": {"version": "9.9.9"}}).encode()
    monkeypatch.setattr(uc, "urlopen", _fake_urlopen(body))
    assert uc.latest_pypi_version() == "9.9.9"


def test_latest_pypi_version_network_error_is_silent(monkeypatch):
    def boom(req, timeout=None):
        raise URLError("offline")

    monkeypatch.setattr(uc, "urlopen", boom)
    assert uc.latest_pypi_version() is None


def test_latest_pypi_version_garbage_json_is_silent(monkeypatch):
    monkeypatch.setattr(uc, "urlopen", _fake_urlopen(b"<html>PyPI down</html>"))
    assert uc.latest_pypi_version() is None


def test_version_comparison():
    assert uc.is_newer("1.19.0", "1.18.0")
    assert not uc.is_newer("1.18.0", "1.18.0")
    assert not uc.is_newer("1.17.9", "1.18.0")
    assert uc.is_newer("2.0", "1.99.99")
    # non-numeric junk never raises
    assert not uc.is_newer("banana", "1.18.0")


# ---------------------------------------------------------------------------
# Install-environment detection matrix
# ---------------------------------------------------------------------------


def test_detect_frozen(monkeypatch):
    monkeypatch.setattr(uc.sys, "frozen", True, raising=False)
    assert uc.detect_install_environment() == "frozen"


def test_detect_pipx_posix_path(monkeypatch):
    monkeypatch.delenv("PIPX_HOME", raising=False)
    exe = "/home/u/.local/pipx/venvs/dji-drone-metadata-embedder/bin/python"
    assert uc.detect_install_environment(exe) == "pipx"


def test_detect_pipx_windows_path(monkeypatch):
    monkeypatch.delenv("PIPX_HOME", raising=False)
    exe = r"C:\Users\u\AppData\Local\pipx\venvs\dji\Scripts\python.exe"
    assert uc.detect_install_environment(exe) == "pipx"


def test_detect_pipx_home_env(monkeypatch):
    monkeypatch.setenv("PIPX_HOME", "/opt/isolated-apps")
    exe = "/opt/isolated-apps/venvs/dji/bin/python"
    assert uc.detect_install_environment(exe) == "pipx"


def test_detect_plain_pip(monkeypatch):
    monkeypatch.delenv("PIPX_HOME", raising=False)
    exe = "/usr/local/bin/python3"
    assert uc.detect_install_environment(exe) == "pip"


def test_upgrade_hint_pip_uses_literal_sys_executable():
    hint = uc.upgrade_hint("pip")
    assert uc.sys.executable in hint
    assert "-m pip install --upgrade dji-drone-metadata-embedder" in hint
    assert hint.startswith('"')  # quoted for paths with spaces


def test_upgrade_hint_pipx():
    assert uc.upgrade_hint("pipx") == "pipx upgrade dji-drone-metadata-embedder"


def test_upgrade_hint_frozen_mentions_winget_and_releases():
    hint = uc.upgrade_hint("frozen")
    assert "winget upgrade CallMarcus.DJIMetadataEmbedder" in hint
    assert "releases" in hint


# ---------------------------------------------------------------------------
# ExifTool-vs-pin (offline)
# ---------------------------------------------------------------------------


def test_exiftool_older_than_pin_hints_doctor_install(monkeypatch):
    monkeypatch.setattr(
        "dji_metadata_embedder.utils.exiftool.exiftool_version", lambda: "12.76"
    )
    monkeypatch.setattr(
        "dji_metadata_embedder.utils.exiftool.exiftool_source", lambda: "PATH"
    )
    lines = uc.exiftool_pin_lines()
    text = "\n".join(lines)
    assert "12.76" in text
    assert "PATH" in text
    assert EXIFTOOL_VERSION in text
    assert "dji-embed doctor --install exiftool" in text


def test_exiftool_at_pin_is_quiet(monkeypatch):
    monkeypatch.setattr(
        "dji_metadata_embedder.utils.exiftool.exiftool_version",
        lambda: EXIFTOOL_VERSION,
    )
    assert uc.exiftool_pin_lines() == []


def test_exiftool_missing_is_quiet(monkeypatch):
    monkeypatch.setattr(
        "dji_metadata_embedder.utils.exiftool.exiftool_version", lambda: None
    )
    assert uc.exiftool_pin_lines() == []


# ---------------------------------------------------------------------------
# Full report
# ---------------------------------------------------------------------------


def test_report_offline_no_network(monkeypatch):
    monkeypatch.setattr(uc, "is_interactive", lambda: False)
    monkeypatch.setattr(
        uc, "latest_pypi_version", lambda **k: pytest.fail("no network when offline")
    )
    monkeypatch.setattr(
        "dji_metadata_embedder.utils.exiftool.exiftool_version",
        lambda: EXIFTOOL_VERSION,
    )
    lines = uc.update_report(None)
    assert lines == ["online check: disabled (enable with doctor --online)"]


def test_report_online_outdated(monkeypatch):
    uc.save_consent(True)
    monkeypatch.setattr(uc, "latest_pypi_version", lambda **k: "99.0.0")
    monkeypatch.setattr(
        "dji_metadata_embedder.utils.exiftool.exiftool_version",
        lambda: EXIFTOOL_VERSION,
    )
    text = "\n".join(uc.update_report(None))
    assert f"dji-embed {__version__} -> 99.0.0 available" in text
    assert "update:" in text
    assert "online check: enabled (change with doctor --offline)" in text


def test_report_online_up_to_date(monkeypatch):
    uc.save_consent(True)
    monkeypatch.setattr(uc, "latest_pypi_version", lambda **k: __version__)
    monkeypatch.setattr(
        "dji_metadata_embedder.utils.exiftool.exiftool_version",
        lambda: EXIFTOOL_VERSION,
    )
    text = "\n".join(uc.update_report(None))
    assert "up to date" in text


def test_report_online_network_failure_degrades_silently(monkeypatch):
    uc.save_consent(True)
    monkeypatch.setattr(uc, "latest_pypi_version", lambda **k: None)
    monkeypatch.setattr(
        "dji_metadata_embedder.utils.exiftool.exiftool_version",
        lambda: EXIFTOOL_VERSION,
    )
    lines = uc.update_report(None)
    assert lines == ["online check: enabled (change with doctor --offline)"]
