"""Golden math tests for the equirect -> perspective opening-view render.

The fixture equirect encodes position as color: four vertical longitude
stripes (A red, B green, C blue, D yellow reading left to right), a white
zenith band and a black nadir band. yaw/pitch then predict the center
pixel's color exactly. Image center (yaw 0) falls at x = W/2 — the
boundary between stripes B and C — so stripe tests target stripe centers
(yaw -135, -45, +45, +135), never boundaries."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from dji_metadata_embedder.geo.panorender import render_view

RED, GREEN, BLUE, YELLOW = ((255, 0, 0), (0, 200, 0),
                            (0, 0, 255), (240, 220, 0))
WHITE, BLACK = (255, 255, 255), (0, 0, 0)


@pytest.fixture
def equirect(tmp_path) -> Path:
    W, H = 256, 128
    im = Image.new("RGB", (W, H))
    for x in range(W):
        color = [RED, GREEN, BLUE, YELLOW][min(x * 4 // W, 3)]
        for y in range(H):
            im.putpixel((x, y), color)
    for y in range(8):                       # zenith band
        for x in range(W):
            im.putpixel((x, y), WHITE)
    for y in range(H - 8, H):                # nadir band
        for x in range(W):
            im.putpixel((x, y), BLACK)
    p = tmp_path / "eq.jpg"
    im.save(p, "JPEG", quality=95)
    return p


def _center_pixel(data: bytes) -> tuple:
    im = Image.open(io.BytesIO(data))
    assert im.size == (64, 64)
    return im.getpixel((32, 32))


def _close(a, b, tol=40):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def test_yaw_selects_longitude_stripe(equirect):
    # yaw 0 = image center = x W/2; stripe centers are at yaw -135/-45/45/135.
    for yaw, color in ((-135.0, RED), (-45.0, GREEN),
                       (45.0, BLUE), (135.0, YELLOW)):
        data = render_view(equirect, yaw, 0.0, 90.0, size=64)
        assert data is not None
        assert _close(_center_pixel(data), color), f"yaw {yaw}"


def test_pitch_reaches_zenith_and_nadir(equirect):
    up = render_view(equirect, 0.0, 89.0, 90.0, size=64)
    down = render_view(equirect, 0.0, -89.0, 90.0, size=64)
    assert _close(_center_pixel(up), WHITE)
    assert _close(_center_pixel(down), BLACK)


def test_yaw_wraps_across_seam(equirect):
    # yaw 179 looks at the seam (x ~ 0/W): stripe A/D territory, and must
    # not produce a smear of all stripes (the mesh-transform failure mode).
    data = render_view(equirect, 179.0, 0.0, 20.0, size=64)
    im = Image.open(io.BytesIO(data))
    colors = {im.getpixel((x, 32)) for x in (8, 32, 56)}
    assert all(_close(c, RED) or _close(c, YELLOW) for c in colors)


def test_output_is_jpeg_and_size(equirect):
    data = render_view(equirect, 0.0, 0.0, 90.0, size=48)
    assert data[:2] == b"\xff\xd8"
    assert Image.open(io.BytesIO(data)).size == (48, 48)


def test_bad_input_returns_none(tmp_path):
    bad = tmp_path / "corrupt.jpg"
    bad.write_bytes(b"not a jpeg")
    assert render_view(bad, 0.0) is None
    assert render_view(tmp_path / "missing.jpg", 0.0) is None
