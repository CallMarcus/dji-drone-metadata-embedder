"""Opt-in online update check for ``dji-embed doctor``.

Principle: normal commands never touch the network. ``doctor`` is the only
command that may go online for version info, and it asks first. The user's
answer is remembered in the per-user config dir (the parent of the provisioned
ExifTool tools dir — see :func:`provision.tools_dir`), so the prompt appears
only once. ``DJIEMBED_NO_UPDATE_CHECK=1`` hard-disables regardless of stored
consent, and any network failure degrades silently to the offline report.

The ExifTool-vs-pin comparison in :func:`exiftool_pin_lines` needs no network
at all: the pin ships with the package.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from .provision import EXIFTOOL_VERSION, tools_dir

logger = logging.getLogger(__name__)

PYPI_PROJECT = "dji-drone-metadata-embedder"
PYPI_URL = f"https://pypi.org/pypi/{PYPI_PROJECT}/json"
RELEASES_URL = "https://github.com/CallMarcus/dji-drone-metadata-embedder/releases/latest"
WINGET_ID = "CallMarcus.DJIMetadataEmbedder"
NO_UPDATE_CHECK_ENV = "DJIEMBED_NO_UPDATE_CHECK"

# Hard latency bound for the one optional network call (issue #277: ~3 s).
HTTP_TIMEOUT = 3.0

_PROMPT = "Check online for newer versions (PyPI + ExifTool)? [y/N] "


# ---------------------------------------------------------------------------
# Consent persistence
# ---------------------------------------------------------------------------


def consent_path() -> Path:
    """Consent file in the per-user config dir (parent of the tools dir)."""
    return tools_dir().parent / "update_check.json"


def load_consent() -> bool | None:
    """The remembered opt-in choice, or ``None`` when never answered."""
    try:
        data = json.loads(consent_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get("online_check") if isinstance(data, dict) else None
    return value if isinstance(value, bool) else None


def save_consent(enabled: bool) -> None:
    """Persist the opt-in choice; failures are non-fatal (read-only homes)."""
    path = consent_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"online_check": enabled}) + "\n", encoding="utf-8"
        )
    except OSError:
        logger.debug("Could not persist update-check consent to %s", path)


# ---------------------------------------------------------------------------
# Consent resolution
# ---------------------------------------------------------------------------


def hard_disabled() -> bool:
    """True when ``DJIEMBED_NO_UPDATE_CHECK`` is set to a truthy value."""
    value = os.environ.get(NO_UPDATE_CHECK_ENV, "").strip().lower()
    return value not in ("", "0", "false", "no")


def is_interactive() -> bool:
    """A real terminal on both ends and not a CI environment."""
    if os.environ.get("CI"):
        return False
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def _prompt_consent() -> bool:
    """One-time interactive prompt; plain Enter (or EOF) means No."""
    try:
        answer = input(_PROMPT)
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


def _status(enabled: bool) -> str:
    if enabled:
        return "online check: enabled (change with doctor --offline)"
    return "online check: disabled (enable with doctor --online)"


def resolve_online(cli_choice: bool | None = None) -> tuple[bool, str]:
    """Decide whether this doctor run may go online.

    Precedence: kill-switch env var > ``--online``/``--offline`` flag (which
    also persists) > remembered choice > one-time interactive prompt (which
    also persists) > off. Non-interactive runs never prompt and never check.
    """
    if hard_disabled():
        return False, f"online check: disabled ({NO_UPDATE_CHECK_ENV}=1)"
    if cli_choice is not None:
        save_consent(cli_choice)
        return cli_choice, _status(cli_choice)
    stored = load_consent()
    if stored is not None:
        return stored, _status(stored)
    if not is_interactive():
        return False, _status(False)
    choice = _prompt_consent()
    save_consent(choice)
    return choice, _status(choice)


# ---------------------------------------------------------------------------
# Check 1: dji-embed version via the PyPI JSON API
# ---------------------------------------------------------------------------


def latest_pypi_version(timeout: float = HTTP_TIMEOUT) -> str | None:
    """Latest released version on PyPI, or ``None`` on any failure (silent)."""
    req = Request(PYPI_URL, headers={"User-Agent": "dji-embed"})
    try:
        with urlopen(req, timeout=timeout) as response:
            data = json.load(response)
        version = data["info"]["version"]
    except Exception:  # offline, timeout, PyPI down, bad JSON — never an error
        return None
    return str(version) if version else None


def parse_version(version: str) -> tuple[int, ...]:
    """Leading numeric components of a dotted version ("1.18.0" -> (1, 18, 0))."""
    parts: list[int] = []
    for chunk in version.strip().split("."):
        digits = re.match(r"\d+", chunk)  # stop at the first non-numeric chunk
        if digits is None:
            break
        parts.append(int(digits.group()))
    return tuple(parts) or (0,)


def is_newer(candidate: str, current: str) -> bool:
    """True when ``candidate`` is a strictly newer version than ``current``."""
    return parse_version(candidate) > parse_version(current)


def _norm_parts(path: str) -> list[str]:
    """Case-folded path components, tolerating both / and \\ separators."""
    return [part.lower() for part in re.split(r"[\\/]+", path) if part]


def detect_install_environment(executable: str | None = None) -> str:
    """How dji-embed was installed: ``frozen``, ``pipx``, or ``pip``."""
    if getattr(sys, "frozen", False):  # PyInstaller EXE
        return "frozen"
    exe = executable or sys.executable
    exe_parts = _norm_parts(exe)
    pipx_home = os.environ.get("PIPX_HOME")
    if pipx_home:
        home_parts = _norm_parts(pipx_home)
        if exe_parts[: len(home_parts)] == home_parts:
            return "pipx"
    # Default pipx layouts keep a literal "pipx" path component:
    # ~/.local/pipx/venvs/... and %LOCALAPPDATA%\pipx\venvs\...
    if "pipx" in exe_parts:
        return "pipx"
    return "pip"


def upgrade_hint(env: str | None = None) -> str:
    """Environment-aware upgrade command for an outdated dji-embed."""
    env = env or detect_install_environment()
    if env == "frozen":
        return (
            f"download the new EXE from {RELEASES_URL} "
            f"or run: winget upgrade {WINGET_ID}"
        )
    if env == "pipx":
        return f"pipx upgrade {PYPI_PROJECT}"
    # Literal interpreter path defeats the multi-Python trap: bare `pip`
    # often belongs to a different Python than the dji-embed on PATH.
    return f'"{sys.executable}" -m pip install --upgrade {PYPI_PROJECT}'


def _pypi_lines() -> list[str]:
    from .. import __version__

    latest = latest_pypi_version()
    if latest is None:  # network failure: degrade silently to offline report
        return []
    if not is_newer(latest, __version__):
        return [f"dji-embed {__version__} is up to date"]
    return [
        f"dji-embed {__version__} -> {latest} available",
        f"  update: {upgrade_hint()}",
    ]


# ---------------------------------------------------------------------------
# Check 2: resolved ExifTool vs the shipped pin (fully offline)
# ---------------------------------------------------------------------------


def exiftool_pin_lines() -> list[str]:
    """Hint when the resolved ExifTool is older than the pinned release."""
    from . import exiftool as exiftool_utils

    ver = exiftool_utils.exiftool_version()
    if ver is None:  # missing entirely — doctor already reports that
        return []
    if exiftool_utils.version_key(ver) >= exiftool_utils.version_key(
        EXIFTOOL_VERSION
    ):
        return []
    lagging = [
        model
        for model, floor in exiftool_utils.EXIFTOOL_FLOORS.values()
        if exiftool_utils.version_key(ver) < exiftool_utils.version_key(floor)
    ]
    detail = f"decodes {' / '.join(lagging)}" if lagging else "available"
    return [
        f"exiftool {ver} ({exiftool_utils.exiftool_source()}) "
        f"-> pinned {EXIFTOOL_VERSION} {detail}",
        "  update: dji-embed doctor --install exiftool",
    ]


# ---------------------------------------------------------------------------
# Doctor report
# ---------------------------------------------------------------------------


def update_report(cli_choice: bool | None = None) -> list[str]:
    """All update-check lines for doctor output (may prompt interactively)."""
    online, status = resolve_online(cli_choice)
    lines: list[str] = []
    if online:
        lines.extend(_pypi_lines())
    lines.extend(exiftool_pin_lines())
    lines.append(status)
    return lines
