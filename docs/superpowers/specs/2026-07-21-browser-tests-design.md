# Durable browser tests for generated maps (Track B)

**Status:** approved 2026-07-21 (maintainer chose a required CI job and the
playback + hover-toggle first slice).

## Problem

The richest behaviour in the generated maps lives in inlined JavaScript —
flight playback (#327), the hover-previews toggle (#345), the pano viewer —
and is pinned only by string-level tests that assert the *source* looks
right, never that the page *behaves* right. Regressions there have been
caught by hand (Playwright MCP sessions, human passes), which does not scale
and rots.

## Decision

A committed pytest-playwright suite that loads real generated maps in
headless Chromium and asserts behaviour, running as a required CI job on one
leg. First slice: playback + hover toggle; pano viewer and pin-link checks
are the named next slice.

## Design

### Layout & dependency

- Tests live in `tests/browser/`, marked `@pytest.mark.browser` (marker
  registered in pytest config).
- New pinned optional extra in `pyproject.toml`, alongside `dev`:
  `browser = ["pytest-playwright==0.8.0", "playwright==1.61.0"]`.
- Every module starts with `pytest.importorskip("playwright")`: the existing
  CI build legs (no `--extra browser`) and plain local `uv run pytest` skip
  the suite silently; nothing else about the default run changes.

### Map generation — no CLI, no ExifTool

Tests call `photos_to_html` / `write_flights_html` directly on synthetic
`PhotoPoint` / `Track` objects (fictitious GPS, built in-test). The
CLI-to-file pipeline is already covered by the GUI real-CLI E2E suite
(PR #344); this suite is about what the emitted page *does*. The synthetic
flight spans several hundred metres — a geographically tiny flight renders
~12 px wide and defeats position assertions.

### Hermetic networking

- A session-scoped `http.server` on an ephemeral localhost port serves a
  temp directory the tests write map HTML into.
- `page.route` intercepts everything non-localhost:
  - **unpkg assets** (Leaflet, markercluster): fulfilled from a
    once-per-run download cache. The (URL, SRI) pairs are scraped from the
    generated HTML itself, each download is verified against its SRI hash,
    and the cache directory (`~/.cache/djiembed-test-assets`, overridable
    via `DJIEMBED_TEST_ASSET_CACHE`) is kept warm by CI's cache action —
    steady-state runs are fully offline. A hash mismatch or failed download
    fails the run loudly.
  - **tile servers**: fulfilled with a stub 1×1 PNG. No OSM traffic, no
    flake, and the map still lays out normally.
  - anything else non-localhost: aborted (fail loudly on new external
    dependencies).

### First slice (~9 tests)

Playback, on a two-flight map (one large flight):

1. Play advances the position dot (marker coordinates change).
2. Scrubbing the slider positions the dot at the expected time.
3. The speed button cycles its labels and wraps.
4. Compare mode shows one dot per flight.
5. Unticking a flight in the layer control removes its paths (path-count
   delta).
6. Reaching the end flips the play button into its replay state.

Hover toggle, on a photomap:

7. Default off: hovering a pin shows no tooltip; toggling on shows the
   filename tooltip.
8. The choice survives `page.reload()` (localStorage).
9. A touch-emulated context (mobile device descriptor) gets no toggle
   control at all (#295 parity).

### Assertion conventions (codified gotchas)

- JS-evaluation probes only: path counts, slider max, marker/dot
  coordinates, element text. Never screen-pixel positions.
- Playwright's polling `expect` (or an explicit poll helper) instead of
  sleeps — Leaflet tooltip close has a fade animation that races immediate
  DOM checks, and synthetic mouse events don't perfectly mimic hover.
- No screenshot-comparison assertions.

### CI

One new `browser` job in `ci.yml` (ubuntu-22.04, Python 3.12), parallel to
`build` and `gui`, required like them:

- `uv sync --extra dev --extra browser`
- `uv run playwright install chromium` (with `--with-deps` for the runner
  libraries), `~/.cache/ms-playwright` cached keyed on the playwright pin
- asset cache dir cached keyed on the scraped (URL, SRI) set
- `uv run pytest tests/browser`

## Out of scope (this slice)

- Pano viewer open + `--link-originals` 404 checks (next slice; needs pano
  fixtures).
- Popup-field DOM assertions (HTML-level coverage exists via PR #344).
- Anything WebView2/GUI-side (Windows-only, separate concern).
- Real tile rendering.
