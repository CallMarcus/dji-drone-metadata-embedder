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

from dji_metadata_embedder.geo.serve import _QuietHandler  # noqa: E402


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
        import os
        import urllib.request

        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read()
        algo, _, want = integrity.partition("-")
        got = base64.b64encode(hashlib.new(algo, data).digest()).decode()
        if got != want:
            raise RuntimeError(f"SRI mismatch for {url}: {got} != {want}")
        # Write-then-rename so a parallel xdist worker that sees the file
        # exists can never read a half-written copy on a cold cache.
        tmp = dest.with_suffix(f".tmp-{os.getpid()}")
        tmp.write_bytes(data)
        os.replace(tmp, dest)
    return dest


def _dem_rgb(elev_m: float) -> tuple[int, int, int]:
    """Mapbox raster-dem encoding: h = -10000 + (R*65536 + G*256 + B) * 0.1."""
    v = round((elev_m + 10000) / 0.1)
    return (v >> 16) & 255, (v >> 8) & 255, v & 255


def _dem_png(elev_m: float, high_m: float | None = None) -> bytes:
    """256x256 raster-dem tile.

    Constant *elev_m* by default. With *high_m*, the left half of the tile is
    ``elev_m`` and the right half ``high_m`` — a vertical cliff down the
    middle of every tile, which is what makes terrain occlusion testable.
    """
    lo = _dem_rgb(elev_m)
    hi = _dem_rgb(high_m if high_m is not None else elev_m)
    row = b"\x00" + bytes(lo) * 128 + bytes(hi) * 128
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


_RECORD_JS = """
async () => {
  const c = document.createElement('canvas');
  c.width = 320; c.height = 180;
  const ctx = c.getContext('2d');
  const stream = c.captureStream(30);
  const types = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8',
                 'video/webm'];
  const type = types.find(t => MediaRecorder.isTypeSupported(t));
  if (!type) throw new Error('no recordable mime type');
  const rec = new MediaRecorder(stream, {mimeType: type});
  const chunks = [];
  rec.ondataavailable = e => chunks.push(e.data);
  rec.start();
  for (let i = 0; i < 60; i++) {            // ~2 s of visibly changing frames
    ctx.fillStyle = `rgb(${i * 4}, 0, 0)`;
    ctx.fillRect(0, 0, 320, 180);
    await new Promise(r => setTimeout(r, 33));
  }
  await new Promise(r => { rec.onstop = r; rec.stop(); });
  const buf = await new Blob(chunks, {type}).arrayBuffer();
  let s = '';
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s);
}
"""


@pytest.fixture(scope="session")
def recorded_webm(browser) -> bytes:
    """A small, real, seekable video, recorded by Chromium itself.

    There is no ffmpeg in this environment and hand-built container bytes are
    a trap, so the browser makes its own: ~38 KB of VP9 WebM with a finite
    duration that seeks exactly. It is WebM rather than MP4, so these tests
    prove our seek logic and segment mapping -- MP4 decoding is the browser's
    job, not ours.
    """
    import base64

    page = browser.new_page()
    try:
        page.goto("about:blank")
        return base64.b64decode(page.evaluate(_RECORD_JS))
    finally:
        page.close()


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
    ``terrain_steps=(low_m, high_m)`` is the mutually-exclusive alternative:
    it fulfils a DEM whose left half is ``low_m`` and right half ``high_m``
    (a cliff down the middle of every tile) at ``maxzoom`` 15 so each tile
    spans ~1.2 km and the cliff falls inside the viewport — this is what
    makes terrain occlusion testable. Passing both ``terrain_stub`` and
    ``terrain_steps`` is a ``ValueError``. Terrain-stub/-steps runs also
    strip the ``hillshade`` source/layer before the map constructs: headless
    SwiftShader hangs rendering it against real DEM data under pitch, and it
    is presentation-only, so these runs never see it (see
    ``_STRIP_HILLSHADE_JS``). ``extra_files`` writes additional files
    (e.g. a recorded video clip) beside the served HTML, keyed by the
    relative href the map references them with.
    """
    root, base_url = map_server

    def _serve(html: str, *, on=None, terrain_stub: float | None = None,
               terrain_steps: tuple[float, float] | None = None,
               extra_files: dict[str, bytes] | None = None) -> str:
        import uuid

        target = on if on is not None else page
        name = f"map-{uuid.uuid4().hex[:12]}.html"
        (root / name).write_text(html, encoding="utf-8")
        for rel, data in (extra_files or {}).items():
            target_path = root / rel
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(data)
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

        if terrain_stub is not None and terrain_steps is not None:
            raise ValueError("pass terrain_stub or terrain_steps, not both")
        if terrain_stub is not None or terrain_steps is not None:
            target.add_init_script(_STRIP_HILLSHADE_JS)
            if terrain_steps is not None:
                dem = _dem_png(terrain_steps[0], terrain_steps[1])
                maxzoom = 15   # ~1.2 km tiles: a cliff fits in the viewport
            else:
                dem = _dem_png(terrain_stub)
                maxzoom = 12
            tilejson = json.dumps({
                "tilejson": "2.2.0",
                "tiles": ["https://tiles.mapterhorn.com/dem/{z}/{x}/{y}.png"],
                "minzoom": 0,
                "maxzoom": maxzoom,
            }).encode()

            def terrain_route(r):
                if r.request.url.endswith("tilejson.json"):
                    return r.fulfill(body=tilejson,
                                     content_type="application/json")
                return r.fulfill(body=dem, content_type="image/png")

            # Registered AFTER the catch-all route above: Playwright matches
            # routes in REVERSE registration order, so this must come last
            # to take priority over the catch-all's abort.
            target.route(
                lambda u: urlsplit(u).hostname == "tiles.mapterhorn.com",
                terrain_route,
            )

        url = f"{base_url}/{name}"
        target.goto(url)
        return url

    return _serve
