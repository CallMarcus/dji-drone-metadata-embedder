"""Synchronize project version across multiple files.

This helper keeps the version defined in ``pyproject.toml`` (via
``[tool.hatch.version]``) in sync with other project files such as the
README badge, bootstrap script, PyInstaller spec and optional winget
manifests.

Usage::

    python tools/sync_version.py 1.2.3       # update files to 1.2.3
    python tools/sync_version.py --check     # verify files are in sync

``--check`` exits with code 1 if any target file contains a different
version.  The script is intentionally dependency light and uses only the
standard library.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:  # Python >=3.11
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore


# ---------------------------------------------------------------------------
# Configuration

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# mapping of target files to (regex, replacement template)
TARGET_PATTERNS: dict[Path, tuple[str, str]] = {
    Path("README.md"): (
        r"https://img.shields.io/badge/version-(?P<ver>\d+\.\d+\.\d+)-blue",
        "https://img.shields.io/badge/version-{version}-blue",
    ),
    Path("tools/bootstrap.ps1"): (
        r"\$fallbackVersion\s*=\s*\"(?P<ver>\d+\.\d+\.\d+)\"",
        "$fallbackVersion = \"{version}\"",
    ),
    Path("dji-embed.spec"): (
        r"__version__\s*=\s*\"(?P<ver>\d+\.\d+\.\d+)\"",
        "__version__ = \"{version}\"",
    ),
}


VERSION_RE = re.compile(r"__version__\s*=\s*\"(?P<ver>\d+\.\d+\.\d+)\"")


# ---------------------------------------------------------------------------
# Helper functions


def _read_toml(path: Path) -> dict:
    with path.open("rb") as fh:  # tomllib requires binary mode
        return tomllib.load(fh)


def _version_file(root: Path) -> Path:
    """Return the path to the version file defined in pyproject.toml."""

    data = _read_toml(root / "pyproject.toml")
    try:
        rel_path = data["tool"]["hatch"]["version"]["path"]
    except KeyError as exc:  # pragma: no cover - malformed config
        raise KeyError("Version path not found in pyproject.toml") from exc
    return (root / rel_path).resolve()


def _replace_in_file(path: Path, pattern: str, replacement: str) -> bool:
    """Replace ``pattern`` with ``replacement`` in ``path``.

    Returns ``True`` if a substitution was made.
    """

    text = path.read_text(encoding="utf-8")
    new_text, count = re.subn(pattern, replacement, text)
    if count:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def _update_targets(version: str, root: Path) -> None:
    """Update all known target files to ``version``."""

    # update version file
    _replace_in_file(_version_file(root), VERSION_RE.pattern, f'__version__ = "{version}"')

    for rel_path, (pattern, template) in TARGET_PATTERNS.items():
        path = root / rel_path
        if path.exists():
            _replace_in_file(path, pattern, template.format(version=version))

    # winget manifests (optional)
    winget_dir = root / "winget"
    if winget_dir.exists():
        # Update PackageVersion in all manifest files (.yml and .yaml)
        yml_files = list(winget_dir.rglob("*.yml"))
        yaml_files = list(winget_dir.rglob("*.yaml"))
        for manifest in yml_files + yaml_files:
            _replace_in_file(manifest, r"(?m)^PackageVersion:\s*(?P<ver>\d+\.\d+\.\d+)", f"PackageVersion: {version}")
            
        # Update installer URL version references in installer manifest
        installer_files = list(winget_dir.glob("*.installer.yaml")) + list(winget_dir.glob("*.installer.yml"))
        for installer_file in installer_files:
            # Update download URLs that contain version numbers
            _replace_in_file(
                installer_file, 
                r"(https://github\.com/[^/]+/[^/]+/releases/download/v)(?P<ver>\d+\.\d+\.\d+)/", 
                rf"\g<1>{version}/"
            )


def _check_targets(version: str, root: Path) -> bool:
    """Return ``True`` if all target files contain ``version``."""

    mismatches: list[Path] = []

    # version file
    vf = _version_file(root)
    vf_text = vf.read_text(encoding="utf-8")
    match = VERSION_RE.search(vf_text)
    if not match or match.group("ver") != version:
        mismatches.append(vf)

    # other targets
    for rel_path, (pattern, _) in TARGET_PATTERNS.items():
        path = root / rel_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        match = re.search(pattern, text)
        if not match or match.group("ver") != version:
            mismatches.append(path)

    winget_dir = root / "winget"
    if winget_dir.exists():
        manifest_files = list(winget_dir.rglob("*.yml")) + list(winget_dir.rglob("*.yaml"))
        for manifest in manifest_files:
            text = manifest.read_text(encoding="utf-8")
            
            # Check PackageVersion field
            match = re.search(r"(?m)^PackageVersion:\s*(?P<ver>\d+\.\d+\.\d+)", text)
            if not match or match.group("ver") != version:
                mismatches.append(manifest)
            
            # For installer manifests, also check download URL versions
            if ".installer." in manifest.name:
                url_match = re.search(r"https://github\.com/[^/]+/[^/]+/releases/download/v(?P<ver>\d+\.\d+\.\d+)/", text)
                if url_match and url_match.group("ver") != version:
                    mismatches.append(manifest)

    if mismatches:
        print(
            f"Version mismatch: expected {version} in the following files:",
            file=sys.stderr,
        )
        for path in mismatches:
            print(f" - {path}", file=sys.stderr)
        print(
            f"Hint: run 'python tools/sync_version.py {version}' to update",
            file=sys.stderr,
        )
        return False
    return True


def _current_version(root: Path) -> str:
    """Extract current version from the version file."""

    vf = _version_file(root)
    text = vf.read_text(encoding="utf-8")
    match = VERSION_RE.search(text)
    if not match:
        raise RuntimeError("Version string not found in version file")
    return match.group("ver")


# ---------------------------------------------------------------------------
# CLI


def main(argv: list[str] | None = None, project_root: Path | None = None) -> None:
    parser = argparse.ArgumentParser(description="Synchronize project version")
    parser.add_argument("version", nargs="?", help="Version to apply")
    parser.add_argument(
        "--check", action="store_true", help="Only verify that versions match"
    )
    args = parser.parse_args(argv)

    root = project_root or PROJECT_ROOT

    if args.check:
        version = args.version or _current_version(root)
        ok = _check_targets(version, root)
        if not ok:
            raise SystemExit(1)
        return

    if not args.version:
        parser.error("version argument required when not using --check")

    _update_targets(args.version, root)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()

