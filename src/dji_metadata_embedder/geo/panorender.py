"""Square perspective crops of equirectangular panoramas at their GPano
opening view (#441). Pure Pillow, per-pixel inverse mapping.

Per-pixel (not Pillow's MESH transform) is a measured decision: mesh quads
interpolate source coordinates linearly, which breaks across the equirect
longitude seam and near the poles — and nadir opening views are common for
drone panos. A 320x320 crop costs ~0.07 s in pure Python; JPEG decode of
the source dominates the runtime either way."""

from __future__ import annotations

import base64
import io
import logging
from math import asin, atan2, cos, pi, radians, sin, sqrt, tan
from pathlib import Path

from PIL import Image

from .photomap import PhotoPoint

logger = logging.getLogger(__name__)

# The source is downscaled to this width before sampling: a 320 px crop of
# a <=170 degree view never needs more than ~2x that angular resolution,
# and Image.draft lets JPEG decode skip DCT blocks entirely.
_MAX_SRC_WIDTH = 2048


def render_view(
    path: Path,
    yaw_deg: float,
    pitch_deg: float = 0.0,
    hfov_deg: float = 90.0,
    size: int = 320,
) -> bytes | None:
    """JPEG bytes of a size x size perspective crop, or None on failure.

    ``yaw_deg`` is viewer yaw relative to the image center (photomap's
    ``pano_yaw``), so no pose handling is needed here — the equirect's own
    frame is the reference. Pitch/hfov are clamped to the same physical
    ranges the viewer enforces.
    """
    try:
        with Image.open(path) as im:
            im.draft("RGB", (_MAX_SRC_WIDTH, _MAX_SRC_WIDTH // 2))
            src = im.convert("RGB")
        if src.width > _MAX_SRC_WIDTH:
            src.thumbnail((_MAX_SRC_WIDTH, _MAX_SRC_WIDTH))
        W, H = src.size
        if W < 2 or H < 2 or size < 1:
            return None
        px = src.load()
        if px is None:
            return None
        yaw = radians(yaw_deg)
        p = radians(max(-90.0, min(90.0, pitch_deg)))
        hfov = radians(max(10.0, min(170.0, hfov_deg)))
        f = (size / 2.0) / tan(hfov / 2.0)
        cp, sp = cos(p), sin(p)
        out = Image.new("RGB", (size, size))
        opx = out.load()
        if opx is None:
            return None
        half = size / 2.0
        two_pi = 2.0 * pi
        for j in range(size):
            v = half - (j + 0.5)
            # Pitch rotates the ray about the x-axis; +pitch looks up.
            # y/z depend only on the row, so they hoist out of the column
            # loop — that hoist is what makes pure Python fast enough.
            y = v * cp + f * sp
            z = f * cp - v * sp
            for i in range(size):
                u = (i + 0.5) - half
                lon = atan2(u, z) + yaw
                lat = asin(y / sqrt(u * u + y * y + z * z))
                sx = int(((lon / two_pi + 0.5) % 1.0) * W)
                sy = int((0.5 - lat / pi) * H)
                opx[i, j] = px[min(sx, W - 1), min(max(sy, 0), H - 1)]
        buf = io.BytesIO()
        out.save(buf, "JPEG", quality=85)
        return buf.getvalue()
    except Exception:
        # Degrade presentation, never lose the popup: the caller keeps
        # the 2:1 strip thumbnail for this pano.
        logger.debug("opening-view render failed for %s", path, exc_info=True)
        return None


def apply_view_thumbnails(points: list[PhotoPoint], root: Path) -> int:
    """Swap tagged panos' popup thumbnails for opening-view crops, in place.

    Only panoramas with a saved heading qualify (missing pitch/hfov fall
    back to level/90 degrees, same as the viewer). Returns how many were
    replaced; failures silently keep the 2:1 strip."""
    count = 0
    for point in points:
        if not (point.is_pano and point.pano_yaw is not None):
            continue
        data = render_view(
            root / point.name,
            point.pano_yaw,
            point.pano_pitch if point.pano_pitch is not None else 0.0,
            point.pano_hfov if point.pano_hfov is not None else 90.0,
        )
        if data is not None:
            point.thumbnail_b64 = base64.b64encode(data).decode("ascii")
            point.thumb_is_view = True
            count += 1
    return count
