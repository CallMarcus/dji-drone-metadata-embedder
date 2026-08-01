"""Tests for tools/make_app_icon.py (#438).

The GUI icon was originally generated with an uncommitted Pillow script,
which is how the 256px ceiling of #438 happened; these tests pin the
committed generator to the design so the assets can't drift from their
source again. Loaded via importlib because tools/ is not a package (same
pattern as test_macos_bundle.py)."""

import importlib.util
from pathlib import Path

from PIL import Image

_MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "make_app_icon.py"

BLUE = (42, 129, 203, 255)
ORANGE = (246, 151, 48, 255)
WHITE = (255, 255, 255, 255)


def _load_module():
    spec = importlib.util.spec_from_file_location("make_app_icon", _MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mai = _load_module()


def _near(a, b, tol=8):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def test_draw_icon_produces_an_rgba_square_of_the_asked_size():
    im = mai.draw_icon(1024)
    assert im.mode == "RGBA"
    assert im.size == (1024, 1024)


def test_draw_icon_design_probes_at_1024():
    im = mai.draw_icon(1024)
    # Rounded square: corners transparent, edge midpoints blue.
    assert im.getpixel((4, 4))[3] == 0
    assert im.getpixel((1019, 4))[3] == 0
    assert _near(im.getpixel((80, 512)), BLUE)
    # Pin head ring is white, its centre dot orange (centre at 0.4 h).
    assert _near(im.getpixel((512, 408)), ORANGE)
    assert _near(im.getpixel((360, 408)), WHITE)
    # Tail: white on the centreline below the head, blue beside it.
    assert _near(im.getpixel((512, 740)), WHITE)
    assert _near(im.getpixel((300, 740)), BLUE)


def test_draw_icon_matches_the_shipped_256px_design():
    # The same probes the original asset answers — the regeneration must
    # keep the identity, not just "a" pin.
    im = mai.draw_icon(256)
    assert _near(im.getpixel((30, 128)), BLUE)
    assert _near(im.getpixel((128, 100)), ORANGE)
    assert im.getpixel((2, 2))[3] == 0


def test_main_writes_the_png_master_and_multires_ico(tmp_path):
    mai.main(["--out-dir", str(tmp_path)])
    png = Image.open(tmp_path / "app-icon.png")
    assert png.size == (1024, 1024)
    ico = Image.open(tmp_path / "app-icon.ico")
    assert ico.info["sizes"] == {
        (16, 16), (24, 24), (32, 32), (48, 48),
        (64, 64), (128, 128), (256, 256),
    }
