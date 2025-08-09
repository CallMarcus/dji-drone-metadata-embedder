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
    (root / "winget/manifest.yaml").write_text(f'PackageVersion: {version}\n')


def test_sync_and_check(tmp_path: Path):
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
    ]:
        assert "1.2.3" in (tmp_path / rel).read_text()

    # Check mode should pass
    sync_version.main(["--check"], project_root=tmp_path)

    # Introduce drift and ensure check fails
    (tmp_path / "README.md").write_text(
        '[![Version](https://img.shields.io/badge/version-0.0.1-blue)][release]\n'
    )
    with pytest.raises(SystemExit) as exc:
        sync_version.main(["--check"], project_root=tmp_path)
    assert exc.value.code == 1

