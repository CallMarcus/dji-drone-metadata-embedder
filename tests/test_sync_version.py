import importlib.util
from pathlib import Path

import pytest


def _load_module():
    path = Path(__file__).resolve().parent.parent / "tools" / "sync_version.py"
    spec = importlib.util.spec_from_file_location("sync_version", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


def _write_project(root: Path, version: str) -> None:
    (root / "src/pkg").mkdir(parents=True)
    (root / "tools").mkdir()
    (root / "winget").mkdir()
    (root / "docs").mkdir()

    (root / "pyproject.toml").write_text(
        """
[tool.hatch.version]
path = "src/pkg/__init__.py"
""".strip()
    )

    (root / "src/pkg/__init__.py").write_text(f'__version__ = "{version}"\n')
    (root / "README.md").write_text(
        f'[![Version](https://img.shields.io/badge/version-{version}-blue)][release]\n'
    )
    (root / "tools/bootstrap.ps1").write_text(
        f'$fallbackVersion = "{version}"\n'
    )
    (root / "dji-embed.spec").write_text(f'__version__ = "{version}"\n')
    (root / "winget/manifest.yaml").write_text(
        f"PackageVersion: {version}\n"
        f"ReleaseNotesUrl: https://example.com/owner/repo/releases/tag/v{version}\n"
    )

    # Doc "current version" stamps that sync_version.py keeps fresh.
    (root / "CLAUDE.md").write_text(f"**Project Version:** v{version}\n")
    (root / "HOUSEKEEPING.md").write_text(
        f"**Current state:** v{version}, production-ready\n"
    )
    # This one carries non-ASCII (·), so it must be written UTF-8 explicitly:
    # sync_version.py reads it as UTF-8, and a locale-default (cp1252) write on
    # Windows would produce bytes it can't decode.
    (root / "docs/development_roadmap.md").write_text(
        f"_Last updated: 2026-06-21 · Current version: **v{version}** · Status: x_\n",
        encoding="utf-8",
    )
    # Two matrix rows (first column) + the `dji-embed X.Y.Z` example line; the
    # FFmpeg column must stay untouched.
    (root / "docs/external-tool-versions.md").write_text(
        "| dji-embed | FFmpeg |\n"
        "|-----------|--------|\n"
        f"| {version}    | 6.1.1   |\n"
        f"| {version}    | 6.0.x   |\n"
        "\n"
        f"dji-embed {version}\n"
        "  ffmpeg: 6.1.1\n"
    )


def test_sync_and_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    sync_version = _load_module()
    _write_project(tmp_path, "0.1.0")

    sync_version.main(["1.2.3"], project_root=tmp_path)

    # All files should now contain the new version
    for rel in [
        "src/pkg/__init__.py",
        "README.md",
        "tools/bootstrap.ps1",
        "dji-embed.spec",
        "winget/manifest.yaml",
        "CLAUDE.md",
        "HOUSEKEEPING.md",
        "docs/development_roadmap.md",
        "docs/external-tool-versions.md",
    ]:
        assert "1.2.3" in (tmp_path / rel).read_text(encoding="utf-8")

    # external-tool-versions.md has the version in multiple spots (both matrix
    # rows + the example line); re.subn must bump them all while leaving the
    # FFmpeg tool version alone.
    ext = (tmp_path / "docs/external-tool-versions.md").read_text(encoding="utf-8")
    assert ext.count("1.2.3") == 3
    assert "0.1.0" not in ext
    assert "6.1.1" in ext

    # Release-tag links (ReleaseNotesUrl) should be bumped too, so the winget
    # manifest never ships stale release notes.
    assert "releases/tag/v1.2.3" in (tmp_path / "winget/manifest.yaml").read_text(encoding="utf-8")

    # Explicit check with matching version should pass
    sync_version.main(["1.2.3", "--check"], project_root=tmp_path)

    # A stale ReleaseNotesUrl tag (right PackageVersion, wrong tag) is caught
    (tmp_path / "winget/manifest.yaml").write_text(
        "PackageVersion: 1.2.3\n"
        "ReleaseNotesUrl: https://example.com/owner/repo/releases/tag/v0.0.1\n"
    )
    with pytest.raises(SystemExit):
        sync_version.main(["1.2.3", "--check"], project_root=tmp_path)
    err = capsys.readouterr().err
    assert "winget/manifest.yaml" in err
    # restore so later assertions in this test see an otherwise-synced tree
    (tmp_path / "winget/manifest.yaml").write_text(
        "PackageVersion: 1.2.3\n"
        "ReleaseNotesUrl: https://example.com/owner/repo/releases/tag/v1.2.3\n"
    )

    # Providing a mismatched version should fail with a helpful message
    with pytest.raises(SystemExit):
        sync_version.main(["9.9.9", "--check"], project_root=tmp_path)
    err = capsys.readouterr().err
    assert "expected 9.9.9" in err
    assert "src/pkg/__init__.py" in err

    # Introduce drift and ensure check reports the offending file
    (tmp_path / "README.md").write_text(
        '[![Version](https://img.shields.io/badge/version-0.0.1-blue)][release]\n'
    )
    with pytest.raises(SystemExit):
        sync_version.main(["1.2.3", "--check"], project_root=tmp_path)
    err = capsys.readouterr().err
    assert "expected 1.2.3" in err
    assert "README.md" in err


def test_doc_version_stamp_drift_is_caught(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """A stale 'current version' stamp in a doc must fail --check."""
    sync_version = _load_module()
    _write_project(tmp_path, "1.2.3")

    # Everything is in sync to start with.
    sync_version.main(["1.2.3", "--check"], project_root=tmp_path)

    # Let a doc stamp rot, exactly the failure mode this wiring guards against.
    (tmp_path / "CLAUDE.md").write_text("**Project Version:** v0.0.1\n")
    with pytest.raises(SystemExit):
        sync_version.main(["1.2.3", "--check"], project_root=tmp_path)
    err = capsys.readouterr().err
    assert "CLAUDE.md" in err

