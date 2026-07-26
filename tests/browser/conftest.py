"""Harness for the durable browser tests (Track B spec, 2026-07-21).

Generated map HTML is served over a local http.server and loaded in headless
Chromium via pytest-playwright. The suite is hermetic: unpkg assets (Leaflet,
markercluster) are fulfilled from a once-per-run download cache verified
against the SRI hashes the templates themselves declare, image requests
(map tiles, Leaflet sprite icons) get a stub PNG, and any other external
request is aborted so a new outside dependency fails loudly.

The whole directory skips when playwright is not installed — the plain
``uv run pytest`` gate and the CI build legs run without the ``browser``
extra and are unaffected.
"""

import base64
import hashlib
import http.server
import json
import re
import struct
import threading
import zlib
from pathlib import Path
from urllib.parse import urlsplit

import pytest

pytest.importorskip("playwright")


# A valid 1x1 transparent PNG: the stand-in for every tile and sprite
# request, so the map lays out normally with zero external traffic.
_STUB_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBg"
    "AAAABQABh6FO1AAAAABJRU5ErkJggg=="
)

# src/href + integrity pairs as the map templates emit them.
_ASSET_RE = re.compile(
    r'(?:src|href)="(https://unpkg\.com/[^"]+)"\s+integrity="([^"]+)"'
)


def _asset_cache_dir() -> Path:
    import os

    default = Path.home() / ".cache" / "djiembed-test-assets"
    return Path(os.environ.get("DJIEMBED_TEST_ASSET_CACHE", default))


def _fetch_asset(url: str, integrity: str) -> Path:
    """Return a cached copy of *url*, downloading and SRI-verifying once."""
    cache = _asset_cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / hashlib.sha256(f"{url}#{integrity}".encode()).hexdigest()
    if not dest.exists():
        import urllib.request

        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read()
        algo, _, want = integrity.partition("-")
        got = base64.b64encode(hashlib.new(algo, data).digest()).decode()
        if got != want:
            raise RuntimeError(f"SRI mismatch for {url}: {got} != {want}")
        dest.write_bytes(data)
    return dest


def _dem_png(elev_m: float) -> bytes:
    """256x256 constant-elevation PNG in mapbox raster-dem encoding.

    The 3D template's terrain sources declare no ``encoding``, so MapLibre
    decodes tiles as mapbox: h = -10000 + (R*65536 + G*256 + B) * 0.1.
    """
    v = round((elev_m + 10000) / 0.1)
    r, g, b = (v >> 16) & 255, (v >> 8) & 255, v & 255
    row = b"\x00" + bytes((r, g, b)) * 256  # filter byte 0 + RGB pixels
    raw = row * 256

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 256, 256, 8, 2, 0, 0, 0)  # 8-bit RGB
    return (
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    )


_STRIP_HILLSHADE_JS = """
(() => {
  // SwiftShader (headless CI WebGL) hangs when the hillshade layer renders
  // real DEM data under pitch — MapLibre 'load' never fires. Terrain-stub
  // runs strip hillshade: it is presentation-only for these tests.
  const wrapMap = (M) => {
    const W = function (opts) {
      if (opts && opts.style && opts.style.layers) {
        opts.style.layers = opts.style.layers.filter(
          (l) => l.type !== 'hillshade');
        if (opts.style.sources) delete opts.style.sources.hillshade;
      }
      return new M(opts);
    };
    W.prototype = M.prototype;
    Object.assign(W, M);
    return W;
  };
  let lib;
  Object.defineProperty(window, 'maplibregl', {
    configurable: true,
    get() { return lib; },
    set(v) {
      lib = v;
      if (!v || typeof v !== 'object') return;
      if (v.Map) { v.Map = wrapMap(v.Map); return; }
      let realMap;
      Object.defineProperty(v, 'Map', {
        configurable: true,
        enumerable: true,
        get() { return realMap; },
        set(M) { realMap = wrapMap(M); },
      });
    },
  });
})();
"""


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: ARG002 - silence per-request stderr
        pass


@pytest.fixture(scope="session")
def map_server(tmp_path_factory):
    """(directory, base_url) of a localhost server the tests write maps into."""
    root = tmp_path_factory.mktemp("maps")

    def handler(*args, **kwargs):
        return _QuietHandler(*args, directory=str(root), **kwargs)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield root, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def serve_map(map_server, page):
    """Serve an HTML string and open it, with external traffic stubbed.

    ``on`` targets a different Page (e.g. one from a touch-emulating
    context) instead of the default ``page`` fixture. ``terrain_stub``
    opts into fulfilling the Mapterhorn TileJSON + DEM tile requests with
    a constant-elevation PNG (mapbox raster-dem encoding) instead of the
    default abort, so terrain-dependent behaviour becomes testable.
    Terrain-stub runs also strip the ``hillshade`` source/layer before the
    map constructs: headless SwiftShader hangs rendering it against real
    DEM data under pitch, and it is presentation-only, so these runs never
    see it (see ``_STRIP_HILLSHADE_JS``).
    """
    root, base_url = map_server

    def _serve(html: str, *, on=None, terrain_stub: float | None = None) -> str:
        import uuid

        target = on if on is not None else page
        name = f"map-{uuid.uuid4().hex[:12]}.html"
        (root / name).write_text(html, encoding="utf-8")
        assets = {
            url: _fetch_asset(url, integrity)
            for url, integrity in _ASSET_RE.findall(html)
        }

        def route(r):
            url = r.request.url
            if url.startswith(base_url):
                return r.continue_()
            if url in assets:
                ctype = (
                    "text/css" if url.endswith(".css")
                    else "application/javascript"
                )
                return r.fulfill(path=str(assets[url]), content_type=ctype)
            if r.request.resource_type == "image":
                return r.fulfill(body=_STUB_PNG, content_type="image/png")
            return r.abort()

        target.route("**/*", route)

        if terrain_stub is not None:
            target.add_init_script(_STRIP_HILLSHADE_JS)
            dem = _dem_png(terrain_stub)
            tilejson = json.dumps({
                "tilejson": "2.2.0",
                "tiles": ["https://tiles.mapterhorn.com/dem/{z}/{x}/{y}.png"],
                "minzoom": 0,
                "maxzoom": 12,
            }).encode()

            def terrain_route(r):
                if r.request.url.endswith("tilejson.json"):
                    return r.fulfill(body=tilejson,
                                     content_type="application/json")
                return r.fulfill(body=dem, content_type="image/png")

            target.route(
                lambda u: urlsplit(u).hostname == "tiles.mapterhorn.com",
                terrain_route,
            )

        url = f"{base_url}/{name}"
        target.goto(url)
        return url

    return _serve
