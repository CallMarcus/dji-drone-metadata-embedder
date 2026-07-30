"""Surface elevations from Mapterhorn terrarium tiles (#413, feeds #266).

Python-side sibling of the 3D map's browser terrain: fetches the tilejson
once, then the covering z12 tiles, decodes terrarium RGB to metres via
Pillow (the optional ``[terrain]`` extra). Every figure derived from this
module is an ESTIMATE against a surface model (Copernicus GLO-30 base —
includes vegetation/buildings); callers must label it as such.
Degradation is explicit: :class:`TerrainUnavailable` carries the reason,
and callers report it — never a silent fallback to another datum.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

TILEJSON_URL = "https://tiles.mapterhorn.com/tilejson.json"
ZOOM = 12
_TIMEOUT_S = 60


class TerrainUnavailable(Exception):
    """Surface elevations cannot be produced; the message says why."""


def _fetch(url: str, transport) -> bytes:
    req = Request(url, headers={"User-Agent": "dji-embed"})
    try:
        with transport(req, timeout=_TIMEOUT_S) as resp:
            return resp.read()
    except (URLError, OSError) as exc:
        raise TerrainUnavailable(f"terrain tile fetch failed: {exc}") from exc


def _tile_of(lat: float, lon: float) -> tuple[int, int]:
    n = 2**ZOOM
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def _pixel_of(lat: float, lon: float, x: int, y: int) -> tuple[int, int]:
    n = 2**ZOOM
    fx = (lon + 180.0) / 360.0 * n - x
    lat_r = math.radians(lat)
    fy = (1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n - y
    return min(int(fx * 256), 255), min(int(fy * 256), 255)


def surface_elevations(
    coords: list[tuple[float, float]],
    cache_dir: Path,
    *,
    transport=urlopen,
    announce=None,
) -> list[float]:
    """Surface elevation (m) under each (lat, lon), via cached z12 tiles."""
    try:
        from PIL import Image  # type: ignore[import-untyped]
    except ImportError as exc:
        raise TerrainUnavailable(
            "the [terrain] extra is not installed — "
            "pip install 'dji-drone-metadata-embedder[terrain]'"
        ) from exc

    cache_dir.mkdir(parents=True, exist_ok=True)
    template: str | None = None
    tiles: dict[tuple[int, int], object] = {}
    elevations: list[float] = []
    announced = False
    for lat, lon in coords:
        x, y = _tile_of(lat, lon)
        if (x, y) not in tiles:
            tile_path = cache_dir / f"terrain-{ZOOM}-{x}-{y}.png"
            if not tile_path.exists():
                if not announced and announce is not None:
                    announce(
                        "Fetching terrain tiles from tiles.mapterhorn.com "
                        "for the surface-height estimate..."
                    )
                    announced = True
                if template is None:
                    doc = json.loads(_fetch(TILEJSON_URL, transport))
                    urls = doc.get("tiles") or []
                    if not urls:
                        raise TerrainUnavailable(
                            "terrain tilejson lists no tile endpoints"
                        )
                    template = urls[0]
                url = (
                    template.replace("{z}", str(ZOOM))
                    .replace("{x}", str(x))
                    .replace("{y}", str(y))
                )
                tile_path.write_bytes(_fetch(url, transport))
            try:
                img = Image.open(tile_path).convert("RGB")
            except OSError as exc:
                tile_path.unlink(missing_ok=True)
                raise TerrainUnavailable(
                    f"terrain tile did not decode: {exc}"
                ) from exc
            tiles[(x, y)] = img
        px, py = _pixel_of(lat, lon, x, y)
        r, g, b = tiles[(x, y)].getpixel((px, py))  # type: ignore[attr-defined]
        elev = r * 256 + g + b / 256 - 32768
        if not -500 <= elev <= 9000:
            raise TerrainUnavailable(
                f"terrain tile decoded to an implausible {elev:.0f} m — "
                "refusing to build height estimates from it"
            )
        elevations.append(elev)
    return elevations
