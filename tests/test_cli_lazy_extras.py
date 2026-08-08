"""Base installs must work without the optional extras.

Pillow ships only in the ``[terrain]`` extra. v2.7.0 imported
geo/panorender (and therefore PIL) at CLI module load, which broke every
bare ``pip install`` — dev environments and CI always sync all extras, so
no other gate can catch this class. These tests are that gate.
"""
from __future__ import annotations

import subprocess
import sys

import pytest
from click.testing import CliRunner


def test_cli_imports_without_pillow():
    # A fresh interpreter with PIL unimportable must still import the CLI,
    # and the CLI import must not drag panorender in.
    code = (
        "import sys\n"
        "sys.modules['PIL'] = None\n"      # any 'import PIL' now fails
        "import dji_metadata_embedder.cli\n"
        "assert 'dji_metadata_embedder.geo.panorender' not in sys.modules\n"
        "print('ok')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout


def test_pano_view_thumbs_without_pillow_is_clean_error(monkeypatch, tmp_path):
    from dji_metadata_embedder import cli as cli_mod
    from dji_metadata_embedder.geo.photomap import PhotoPoint

    pano = PhotoPoint(lat=1.0, lon=2.0, alt=None, name="p.jpg",
                      is_pano=True, pano_yaw=0.0)
    monkeypatch.setattr(cli_mod, "scan_photos",
                        lambda d, recursive=False: ([pano], []))
    # Block Pillow: a None sys.modules entry makes `from PIL import Image`
    # raise ImportError even though the test env has Pillow installed.
    monkeypatch.setitem(sys.modules, "PIL", None)
    result = CliRunner().invoke(cli_mod.main, [
        "photomap", str(tmp_path), "--pano-view-thumbs",
        "-o", str(tmp_path / "m.html")])
    assert result.exit_code != 0
    assert "terrain" in result.output          # names the extra to install
    assert "Traceback" not in result.output


def test_pano_view_thumbs_unavailable_error_names_the_extra():
    from dji_metadata_embedder.geo.panorender import (
        PanorenderUnavailable,
        _pil_image,
    )

    saved = sys.modules.get("PIL")
    sys.modules["PIL"] = None  # type: ignore[assignment]
    try:
        with pytest.raises(PanorenderUnavailable, match=r"\[terrain\]"):
            _pil_image()
    finally:
        if saved is None:
            sys.modules.pop("PIL", None)
        else:
            sys.modules["PIL"] = saved
