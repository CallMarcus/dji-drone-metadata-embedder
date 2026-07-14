# Photomap `--serve` + friendly `file://` pano error — design

**Date:** 2026-07-14
**Issue:** [#274](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues/274)
**Status:** Approved

## Problem

The #271 panorama viewer (PR #272, unreleased) fails when `photomap.html` is
opened directly from disk — the default double-click workflow. Browsers give
every `file://` document an opaque origin, so WebGL is refused pixel access
to the linked panorama and Pannellum shows a raw "The file ... could not be
accessed" error. The "open original" fallback works (plain navigation is
allowed; only WebGL texture reads are blocked).

Verified with a real 12000×6000 equirectangular JPEG: the identical map fails
from `file://` and works over `http://localhost`. The wiring is correct; the
protocol is the problem.

## Scope

Two parts, one PR:

1. A clear in-page message when a pano is clicked from `file://`.
2. A `--serve` flag on `photomap` that serves the map over local HTTP and
   opens the browser — making `dji-embed photomap <folder> --serve` the
   complete one-liner for the pano-viewer experience.

Out of scope: `flightmap` (no linked assets — unaffected by `file://`),
serving directories other than the output folder, daemon/background mode,
port selection flags (YAGNI until someone asks).

## Design

### 1. Friendly `file://` message — `geo/photomap_html.py`

In `_PANO_JS`'s `openPano(src)`, before creating the viewer:

- If `location.protocol === 'file:'`, do **not** call `pannellum.viewer`.
  Instead show the overlay with a styled message in the `#pano-viewer`
  container (static text, no user data — no escaping concerns):

  > 360° view is blocked by the browser for maps opened straight from disk.
  > Use the "open original" link in the popup, or rebuild the map with:
  > `dji-embed photomap <your folder> --serve`

- Close button and Escape already tear the overlay down; `closePano()` must
  clear the injected message so a later HTTP-served viewer isn't mixed with
  stale text (simplest: `openPano` sets the container's content each time —
  message text on the `file:` branch, empty before `pannellum.viewer()` on
  the normal branch; Pannellum owns the container from there).
- Emitted only inside `_PANO_JS`, which is already gated on
  `link_base is not None and any(p.is_pano)` — maps without panos are
  byte-for-byte unchanged.

### 2. `--serve` — `cli.py` + new `geo/serve.py`

New module `src/dji_metadata_embedder/geo/serve.py`:

```python
def serve_directory(directory: Path, filename: str, *, quiet: bool = False,
                    log_requests: bool = False, open_browser: bool = True) -> None
```

- `ThreadingHTTPServer` + `SimpleHTTPRequestHandler` via
  `functools.partial(SimpleHTTPRequestHandler, directory=str(directory))`.
- Binds `("127.0.0.1", 0)` — **loopback only**, OS-assigned free port.
  Never `0.0.0.0`.
- Prints `Serving map at http://127.0.0.1:<port>/<filename> — press Ctrl+C
  to stop`. The URL line is printed even under `--quiet` (it is the product
  of the command); only the closing "Stopped." note honours quiet.
- Opens `webbrowser.open(url)` unless `open_browser=False` (tests).
- `serve_forever()` until `KeyboardInterrupt`, then clean shutdown and a
  short "Stopped." note (suppressed by `--quiet`).
- Request logging: subclass the handler to silence `log_message` unless
  verbose logging is enabled (pass a `log_requests: bool`).

CLI wiring in the `photomap` command:

- New flag after `--redact`: `--serve` / `is_flag=True`, help: "After
  writing the map, serve its folder on localhost and open the browser
  (implies --link-originals; needed for the 360° viewer when opening the
  map from disk would be blocked)".
- `--serve` sets `link_originals = True` (silently — it's documented
  behaviour, not a surprise).
- Guard: `--serve` with `-f kml` or `-f geojson` → `click.UsageError`
  ("--serve requires the HTML map (use -f html or -f all)").
- Warn (stderr, non-fatal) when `--serve` is combined with `--link-base`:
  the links then point away from the served folder and may not resolve
  through the local server.
- Serve directory = the parent of the written HTML output (`out.parent` /
  `base.parent`), filename = the HTML file's name — correct for both the
  default (`<dir>/photomap.html`) and `-o elsewhere/map.html`. With `-o`
  outside the photo folder and no `--link-base`, relative links break
  exactly as they do without `--serve`; existing docs already cover it.
- Runs after all formats are written (`-f all` writes kml/geojson first,
  then serves).

### 3. Docs

- `docs/geospatial.md` (360° section): rewrite the caveat list around the
  local-file case — "opened straight from disk, the 360° viewer is blocked
  by the browser; run with `--serve`" — keep the texture-limit and CORS
  (`--link-base` URL) notes.
- README + `docs/user_guide.md`: add `--serve` to the photomap option
  table/examples; the EyesWideShut-shaped example is
  `dji-embed photomap C:\photos --serve`.

## Testing

- `tests/test_geo_serve.py` (real server, no mocks): start on port 0 against
  a tmp dir with an html + jpg; GET both → 200 and correct bytes; assert the
  bound address is `127.0.0.1`; `open_browser=False`; shutdown cleanly from
  the test thread.
- CLI tests (`tests/test_cli_photomap.py`, `serve_directory` +
  `webbrowser` mocked): `--serve` implies links (`"link"` present in the
  written HTML's GeoJSON); `--serve -f kml` fails with the usage error;
  `--serve --link-base x` warns; `serve_directory` called with the HTML's
  parent dir and filename.
- HTML tests (`tests/test_geo_photomap_html.py`): the emitted pano JS
  contains the `file:` protocol branch and the message text; still absent
  entirely when there are no panos or no links.

## E2E verification (manual, done during design)

Local reproduction is already the proof: `python3 -m http.server` over
`C:\TEMP\PanoTest` renders the 12000×6000 pano in the viewer; the same map
from `file://` shows Pannellum's raw error. After implementation, repeat
with `dji-embed photomap /mnt/c/TEMP/PanoTest --serve`.
