"""Terrain lookup tests (#413): tile math, terrarium decode, degradation."""
import io
import json
import struct
import zlib

import pytest

from dji_metadata_embedder.geo.terrain import (
    TerrainUnavailable,
    ZOOM,
    surface_elevations,
)


def _png_rgb(width, height, rgb):
    """Minimal uncompressed-idea PNG: one solid RGB color (stdlib-only)."""
    raw = b"".join(
        b"\x00" + bytes(rgb) * width for _ in range(height)
    )
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(
            ">I", zlib.crc32(c) & 0xFFFFFFFF
        )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


# Terrarium: elev = R*256 + G + B/256 - 32768. (32768+100)//256=128, rem 100.
HUNDRED_M = _png_rgb(256, 256, (128, 100, 0))
TILEJSON = json.dumps(
    {"tiles": ["https://tiles.example.invalid/{z}/{x}/{y}.png"]}
).encode()


class FakeTransport:
    def __init__(self, bodies):
        self.bodies = list(bodies)
        self.urls = []

    def __call__(self, req, timeout=None):
        self.urls.append(req.full_url)
        resp = io.BytesIO(self.bodies.pop(0))
        resp.__enter__ = lambda *a: resp  # type: ignore[method-assign]
        resp.__exit__ = lambda *a: False  # type: ignore[method-assign]
        return resp


def test_decodes_a_terrarium_tile_to_metres(tmp_path):
    fake = FakeTransport([TILEJSON, HUNDRED_M])
    elevs = surface_elevations([(49.61, 6.13)], tmp_path, transport=fake)
    assert elevs == [pytest.approx(100.0)]
    assert f"/{ZOOM}/" in fake.urls[1]


def test_reuses_the_cached_tile_without_network(tmp_path):
    fake = FakeTransport([TILEJSON, HUNDRED_M])
    surface_elevations([(49.61, 6.13)], tmp_path, transport=fake)
    fake2 = FakeTransport([TILEJSON])  # only tilejson; a tile fetch would IndexError
    assert surface_elevations([(49.61, 6.13)], tmp_path, transport=fake2) == [
        pytest.approx(100.0)
    ]


def test_a_failed_tile_fetch_degrades_to_unavailable(tmp_path):
    class Boom:
        def __call__(self, req, timeout=None):
            raise OSError("no route")
    with pytest.raises(TerrainUnavailable, match="no route"):
        surface_elevations([(49.61, 6.13)], tmp_path, transport=Boom())


def test_an_absurd_elevation_is_a_decode_bug_not_a_mountain(tmp_path):
    weird = _png_rgb(256, 256, (255, 255, 255))  # ~32767 m
    fake = FakeTransport([TILEJSON, weird])
    with pytest.raises(TerrainUnavailable, match="implausible"):
        surface_elevations([(49.61, 6.13)], tmp_path, transport=fake)
