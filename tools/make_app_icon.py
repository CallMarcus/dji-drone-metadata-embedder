"""Generate the GUI app icon (#438).

Redraws the original 2026-07-16 design — a map pin in the photomap blue
with the pano-orange dot on a rounded square — from committed code, so
the assets can never again outlive their generator (the original Pillow
script was never committed, which is how the 256px ceiling happened).
Emits the 1024px PNG master (the macOS .icns source; release-macos.yml
reads the size off the asset) and the 16-256px multi-resolution .ico
Windows embeds, both from the same drawing.

Geometry is expressed in 1/256ths of the canvas, matching the original
asset's measurements pixel for pixel at 256px.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

BLUE = (42, 129, 203, 255)
ORANGE = (246, 151, 48, 255)
WHITE = (255, 255, 255, 255)

ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48),
             (64, 64), (128, 128), (256, 256)]

_SS = 4  # supersampling factor for clean anti-aliased edges


def draw_icon(size: int) -> Image.Image:
    """The icon as an RGBA image of the given square size."""
    s = size * _SS
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)

    def u(n: float) -> float:
        return s * n / 256

    draw.rounded_rectangle(
        [u(16), u(16), u(240), u(240)], radius=u(51), fill=BLUE
    )
    # Pin head circle and the tangent-triangle tail.
    cx, cy, r, tip_y = u(128), u(102), u(53), u(204)
    cos_t = r / (tip_y - cy)
    sin_t = (1 - cos_t * cos_t) ** 0.5
    draw.polygon(
        [
            (cx, tip_y),
            (cx - r * sin_t, cy + r * cos_t),
            (cx + r * sin_t, cy + r * cos_t),
        ],
        fill=WHITE,
    )
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)
    dot = u(24)
    draw.ellipse([cx - dot, cy - dot, cx + dot, cy + dot], fill=ORANGE)

    return im.resize((size, size), Image.LANCZOS)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "gui" / "DjiEmbed.Gui" / "Assets",
    )
    args = parser.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    draw_icon(1024).save(args.out_dir / "app-icon.png")
    # The .ico keeps its 16-256 tiers (ICO tops out at 256 in practice);
    # Pillow derives each frame from this base image.
    draw_icon(256).save(
        args.out_dir / "app-icon.ico", format="ICO", sizes=ICO_SIZES
    )
    print(f"wrote app-icon.png + app-icon.ico to {args.out_dir}")


if __name__ == "__main__":
    main()
