# Geo Mapping Phase 1 — Track Export (GeoJSON + KML) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `dji-embed convert geojson` and `dji-embed convert kml` that export a DJI flight track to GeoJSON and KML, reusing the existing parser and redaction.

**Architecture:** A new `geo/` package builds one canonical `Track` from the existing `parse_telemetry_points`, applies redaction once at that layer, and renders it through two stateless serializers (GeoJSON, KML). The CLI `convert` command gains the two new formats plus a `--redact` option. GeoJSON is the canonical spine later viewers (#221/#222) will consume.

**Tech Stack:** Python 3.10+, Click (CLI), stdlib `json` + string templates (no new runtime deps), pytest + click `CliRunner`.

**Spec:** `docs/superpowers/specs/2026-06-04-flight-path-mapping-design.md` (Phase 1). Tracking issue: #215.

---

## File Structure

- Create: `src/dji_metadata_embedder/geo/__init__.py` — package exports.
- Create: `src/dji_metadata_embedder/geo/track.py` — `TrackPoint`, `Track`, `build_track()`.
- Create: `src/dji_metadata_embedder/geo/geojson.py` — `track_to_geojson()`, `write_geojson()`, `convert_to_geojson()`.
- Create: `src/dji_metadata_embedder/geo/kml.py` — `track_to_kml()`, `write_kml()`, `convert_to_kml()`.
- Modify: `src/dji_metadata_embedder/cli.py` — add `geojson`/`kml` to the `convert` choices + `--redact`.
- Create: `tests/test_geo_track.py`
- Create: `tests/test_geo_geojson.py`
- Create: `tests/test_geo_kml.py`
- Create: `tests/test_cli_convert_geo.py`
- Create: `docs/geospatial.md`
- Modify: `README.md` — list the new formats.

**Test fixture:** `samples/air3S/clip.SRT` — 5 frames, all at `lat 34.270373, lon -84.176160, abs_alt 302.208`. Deterministic, already committed. `parse_telemetry_points` returns 5 points for it.

**Coordinate order reminder:** GeoJSON and KML both use **`lon, lat, alt`** order (RFC 7946 / OGC KML), the opposite of how DJI prints `latitude` then `longitude`.

**Note on test commands:** the project standard is `uv run pytest -q`. If `uv` is unavailable in your environment, `PYTHONPATH=src python3 -m pytest -q` is the equivalent.

---

## Branch

- [ ] **Create the feature branch** off updated `master`:

```bash
git checkout master && git pull
git checkout -b feat/issue-215-track-export
```

---

### Task 1: Track model + `build_track`

**Files:**
- Create: `src/dji_metadata_embedder/geo/__init__.py`
- Create: `src/dji_metadata_embedder/geo/track.py`
- Test: `tests/test_geo_track.py`

- [ ] **Step 1: Create the empty package marker**

Create `src/dji_metadata_embedder/geo/__init__.py` with a single line (exports are filled in Task 4):

```python
"""Geospatial track model and exporters (GeoJSON, KML)."""
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_geo_track.py`:

```python
from pathlib import Path

from dji_metadata_embedder.geo.track import build_track

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
CLIP = SAMPLES / "air3S" / "clip.SRT"


def test_build_track_reads_all_points():
    track = build_track(CLIP)
    assert track.name == "clip"
    assert len(track.points) == 5
    p = track.points[0]
    assert (p.lat, p.lon, p.alt) == (34.270373, -84.176160, 302.208)
    assert p.timestamp != ""


def test_build_track_redact_drop_empties_track():
    track = build_track(CLIP, redact="drop")
    assert track.points == []


def test_build_track_redact_fuzz_rounds_coords():
    track = build_track(CLIP, redact="fuzz")
    assert len(track.points) == 5
    p = track.points[0]
    assert (p.lat, p.lon) == (34.27, -84.176)
    # Altitude and timestamp are preserved, only coordinates are coarsened.
    assert p.alt == 302.208
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_geo_track.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'dji_metadata_embedder.geo.track'`

- [ ] **Step 4: Write minimal implementation**

Create `src/dji_metadata_embedder/geo/track.py`:

```python
"""Canonical flight-track model built from parsed SRT telemetry.

A :class:`Track` is the single source of truth every exporter and viewer
consumes. Redaction is applied here, once, so no downstream renderer can leak
exact coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..utilities import parse_telemetry_points, redact_coords


@dataclass
class TrackPoint:
    """One GPS-fixed sample: WGS84 lat/lon, absolute altitude (m), raw cue time."""

    lat: float
    lon: float
    alt: float
    timestamp: str


@dataclass
class Track:
    """A named ordered sequence of :class:`TrackPoint`."""

    name: str
    points: list[TrackPoint]


def build_track(srt_file: Path | str, redact: str = "none") -> Track:
    """Build a :class:`Track` from a DJI SRT file.

    ``redact`` mirrors the embed pipeline: ``"drop"`` yields an empty track,
    ``"fuzz"`` coarsens coordinates to ~100 m (3 decimals), ``"none"`` keeps
    them. Pre-GPS-lock ``(0, 0)`` frames are already excluded by
    :func:`parse_telemetry_points`.
    """
    srt_path = Path(srt_file)
    raw = parse_telemetry_points(srt_path)

    coords = redact_coords([(lat, lon) for lat, lon, _, _ in raw], redact)
    if redact == "drop":
        points: list[TrackPoint] = []
    else:
        points = [
            TrackPoint(lat=c[0], lon=c[1], alt=alt, timestamp=ts)
            for c, (_, _, alt, ts) in zip(coords, raw)
        ]

    return Track(name=srt_path.stem, points=points)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_geo_track.py -q`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add src/dji_metadata_embedder/geo/__init__.py src/dji_metadata_embedder/geo/track.py tests/test_geo_track.py
git commit -m "feat(geo): canonical Track model with redaction"
```

---

### Task 2: GeoJSON serializer

**Files:**
- Create: `src/dji_metadata_embedder/geo/geojson.py`
- Test: `tests/test_geo_geojson.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_geo_geojson.py`:

```python
import json
from pathlib import Path

from dji_metadata_embedder.geo.geojson import convert_to_geojson, track_to_geojson
from dji_metadata_embedder.geo.track import build_track

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
CLIP = SAMPLES / "air3S" / "clip.SRT"


def test_track_to_geojson_structure():
    fc = track_to_geojson(build_track(CLIP))
    assert fc["type"] == "FeatureCollection"

    line = fc["features"][0]
    assert line["geometry"]["type"] == "LineString"
    # GeoJSON is [lon, lat, alt] order, the reverse of DJI's printed lat/lon.
    assert line["geometry"]["coordinates"][0] == [-84.176160, 34.270373, 302.208]

    points = [f for f in fc["features"] if f["geometry"]["type"] == "Point"]
    assert len(points) == 5
    assert points[0]["properties"]["abs_alt"] == 302.208
    assert "timestamp" in points[0]["properties"]


def test_convert_to_geojson_writes_valid_file(tmp_path):
    out = tmp_path / "clip.geojson"
    result = convert_to_geojson(CLIP, out)
    assert result == out
    data = json.loads(out.read_text())
    assert data["type"] == "FeatureCollection"


def test_convert_to_geojson_default_output_path(tmp_path):
    srt = tmp_path / "flight.SRT"
    srt.write_text(CLIP.read_text(encoding="utf-8"), encoding="utf-8")
    result = convert_to_geojson(srt)
    assert result == srt.with_suffix(".geojson")
    assert result.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_geo_geojson.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'dji_metadata_embedder.geo.geojson'`

- [ ] **Step 3: Write minimal implementation**

Create `src/dji_metadata_embedder/geo/geojson.py`:

```python
"""Render a :class:`Track` as GeoJSON (RFC 7946).

GeoJSON is the canonical interchange the map viewers (#221, #222) consume: a
``FeatureCollection`` holding one ``LineString`` for the path plus one ``Point``
per sample carrying altitude and timestamp.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .track import Track, build_track

logger = logging.getLogger(__name__)


def track_to_geojson(track: Track) -> dict:
    """Return a GeoJSON ``FeatureCollection`` dict for *track*."""
    line_coords = [[p.lon, p.lat, p.alt] for p in track.points]
    features: list[dict] = [
        {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": line_coords},
            "properties": {"name": track.name},
        }
    ]
    for index, p in enumerate(track.points):
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [p.lon, p.lat, p.alt]},
                "properties": {
                    "index": index,
                    "abs_alt": p.alt,
                    "timestamp": p.timestamp,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def write_geojson(track: Track, output_path: Path) -> Path:
    """Write *track* as GeoJSON to *output_path* and return it."""
    output_path.write_text(
        json.dumps(track_to_geojson(track), indent=2), encoding="utf-8"
    )
    logger.info("GeoJSON file created: %s", output_path)
    return output_path


def convert_to_geojson(
    srt_file: Path | str, output_file: Path | str | None = None, redact: str = "none"
) -> Path:
    """Convert a DJI SRT file to GeoJSON. Defaults output to ``<srt>.geojson``."""
    srt_path = Path(srt_file)
    output_path = Path(output_file) if output_file else srt_path.with_suffix(".geojson")
    return write_geojson(build_track(srt_path, redact=redact), output_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_geo_geojson.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/dji_metadata_embedder/geo/geojson.py tests/test_geo_geojson.py
git commit -m "feat(geo): GeoJSON track serializer"
```

---

### Task 3: KML serializer

**Files:**
- Create: `src/dji_metadata_embedder/geo/kml.py`
- Test: `tests/test_geo_kml.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_geo_kml.py`:

```python
from pathlib import Path
from xml.etree import ElementTree as ET

from dji_metadata_embedder.geo.kml import convert_to_kml, track_to_kml
from dji_metadata_embedder.geo.track import build_track

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
CLIP = SAMPLES / "air3S" / "clip.SRT"


def test_track_to_kml_is_well_formed_and_has_linestring():
    kml = track_to_kml(build_track(CLIP))
    # Parses as XML (well-formed).
    root = ET.fromstring(kml)
    ns = "{http://www.opengis.net/kml/2.2}"
    coords = root.find(f".//{ns}LineString/{ns}coordinates")
    assert coords is not None
    # KML coordinates are lon,lat,alt tuples.
    first = coords.text.split()[0]
    assert first == "-84.17616,34.270373,302.208"


def test_convert_to_kml_writes_file(tmp_path):
    out = tmp_path / "clip.kml"
    result = convert_to_kml(CLIP, out)
    assert result == out
    assert "<kml" in out.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_geo_kml.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'dji_metadata_embedder.geo.kml'`

- [ ] **Step 3: Write minimal implementation**

Create `src/dji_metadata_embedder/geo/kml.py`:

```python
"""Render a :class:`Track` as KML — a LineString placemark for Google Earth."""

from __future__ import annotations

import logging
from pathlib import Path
from xml.sax.saxutils import escape

from .track import Track, build_track

logger = logging.getLogger(__name__)

_KML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{name}</name>
    <Placemark>
      <name>DJI Flight Path</name>
      <LineString>
        <altitudeMode>absolute</altitudeMode>
        <coordinates>{coordinates}</coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""


def track_to_kml(track: Track) -> str:
    """Return a KML document string for *track* (coordinates as lon,lat,alt)."""
    coordinates = " ".join(f"{p.lon},{p.lat},{p.alt}" for p in track.points)
    return _KML_TEMPLATE.format(name=escape(track.name), coordinates=coordinates)


def write_kml(track: Track, output_path: Path) -> Path:
    """Write *track* as KML to *output_path* and return it."""
    output_path.write_text(track_to_kml(track), encoding="utf-8")
    logger.info("KML file created: %s", output_path)
    return output_path


def convert_to_kml(
    srt_file: Path | str, output_file: Path | str | None = None, redact: str = "none"
) -> Path:
    """Convert a DJI SRT file to KML. Defaults output to ``<srt>.kml``."""
    srt_path = Path(srt_file)
    output_path = Path(output_file) if output_file else srt_path.with_suffix(".kml")
    return write_kml(build_track(srt_path, redact=redact), output_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_geo_kml.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/dji_metadata_embedder/geo/kml.py tests/test_geo_kml.py
git commit -m "feat(geo): KML track serializer"
```

---

### Task 4: Package exports

**Files:**
- Modify: `src/dji_metadata_embedder/geo/__init__.py`

- [ ] **Step 1: Fill in the package exports**

Replace the contents of `src/dji_metadata_embedder/geo/__init__.py` with:

```python
"""Geospatial track model and exporters (GeoJSON, KML)."""

from .geojson import convert_to_geojson, track_to_geojson
from .kml import convert_to_kml, track_to_kml
from .track import Track, TrackPoint, build_track

__all__ = [
    "Track",
    "TrackPoint",
    "build_track",
    "track_to_geojson",
    "convert_to_geojson",
    "track_to_kml",
    "convert_to_kml",
]
```

- [ ] **Step 2: Verify imports resolve**

Run: `uv run python -c "from dji_metadata_embedder.geo import convert_to_geojson, convert_to_kml; print('ok')"`
Expected: prints `ok`

- [ ] **Step 3: Commit**

```bash
git add src/dji_metadata_embedder/geo/__init__.py
git commit -m "feat(geo): export public geo API"
```

---

### Task 5: CLI wiring — `convert geojson|kml` + `--redact`

**Files:**
- Modify: `src/dji_metadata_embedder/cli.py`
- Test: `tests/test_cli_convert_geo.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_convert_geo.py`:

```python
import json
from pathlib import Path

from click.testing import CliRunner

from dji_metadata_embedder.cli import main

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
CLIP = SAMPLES / "air3S" / "clip.SRT"


def test_convert_geojson_cli(tmp_path):
    out = tmp_path / "clip.geojson"
    runner = CliRunner()
    result = runner.invoke(main, ["convert", "geojson", str(CLIP), "-o", str(out)])
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert data["type"] == "FeatureCollection"


def test_convert_kml_cli(tmp_path):
    out = tmp_path / "clip.kml"
    runner = CliRunner()
    result = runner.invoke(main, ["convert", "kml", str(CLIP), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert "<kml" in out.read_text()


def test_convert_geojson_redact_drop_empties_track(tmp_path):
    out = tmp_path / "clip.geojson"
    runner = CliRunner()
    result = runner.invoke(
        main, ["convert", "geojson", str(CLIP), "-o", str(out), "--redact", "drop"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    # Drop leaves only the (empty) LineString feature, no Point features.
    assert data["features"][0]["geometry"]["coordinates"] == []
    assert all(f["geometry"]["type"] != "Point" for f in data["features"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_convert_geo.py -q`
Expected: FAIL — the `geojson` choice is invalid, exit code 2 (`Invalid value for '{gpx|csv}'`).

- [ ] **Step 3: Update the imports in `cli.py`**

In `src/dji_metadata_embedder/cli.py`, the existing import block (around line 13) reads:

```python
from .telemetry_converter import (
    extract_telemetry_to_gpx,
    extract_telemetry_to_csv,
```

Immediately after that import block's closing line, add:

```python
from .geo import convert_to_geojson, convert_to_kml
```

- [ ] **Step 4: Extend the `convert` command signature and dispatch**

Replace the whole `convert` command (currently `cli.py:155-201`, from the `@main.command()` above `convert` through the final `extract_telemetry_to_csv(src, output)` line) with:

```python
@main.command()
@click.argument(
    "command",
    type=click.Choice(["gpx", "csv", "geojson", "kml"], case_sensitive=False),
)
@click.argument("input", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path())
@click.option("-b", "--batch", is_flag=True, help="Batch process directory")
@click.option(
    "--tz-offset",
    default="auto",
    show_default=True,
    metavar="OFFSET",
    help="UTC offset for GPX timestamps, e.g. '+05:30' or '-8'. "
    "'auto' detects it from the SRT file mtime.",
)
@click.option(
    "--redact",
    type=click.Choice(["none", "drop", "fuzz"], case_sensitive=False),
    default="none",
    show_default=True,
    help="GPS redaction for geojson/kml: drop removes the track, "
    "fuzz coarsens to ~100 m.",
)
@click.option("-v", "--verbose", is_flag=True)
@click.option("-q", "--quiet", is_flag=True)
def convert(
    command: str,
    input: str,
    output: str | None,
    batch: bool,
    tz_offset: str,
    redact: str,
    verbose: bool,
    quiet: bool,
) -> None:
    """Convert SRT telemetry to GPX, CSV, GeoJSON, or KML."""
    setup_logging(verbose, quiet)

    try:
        offset = parse_utc_offset(tz_offset)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="--tz-offset")

    src = Path(input)
    if batch and not src.is_dir():
        raise click.ClickException("--batch requires a directory input")

    def run_one(srt: Path, out: str | None) -> None:
        if command == "gpx":
            extract_telemetry_to_gpx(srt, out, tz_offset=offset)
        elif command == "csv":
            extract_telemetry_to_csv(srt, out)
        elif command == "geojson":
            convert_to_geojson(srt, out, redact=redact)
        else:
            convert_to_kml(srt, out, redact=redact)

    if batch:
        for srt in src.glob("*.SRT"):
            run_one(srt, None)
    else:
        run_one(src, output)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_convert_geo.py -q`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add src/dji_metadata_embedder/cli.py tests/test_cli_convert_geo.py
git commit -m "feat(cli): convert geojson and kml with --redact"
```

---

### Task 6: Docs

**Files:**
- Create: `docs/geospatial.md`
- Modify: `README.md`

- [ ] **Step 1: Write `docs/geospatial.md`**

Create `docs/geospatial.md`:

```markdown
# Geospatial export

`dji-embed convert` turns a DJI SRT flight track into geospatial formats that
open in mapping tools and feed the project's own map viewers.

## GeoJSON

```bash
dji-embed convert geojson DJI_0001.SRT          # -> DJI_0001.geojson
dji-embed convert geojson DJI_0001.SRT -o track.geojson
```

A `FeatureCollection` with one `LineString` for the flight path and one `Point`
per sample carrying `abs_alt` and `timestamp`. Coordinates are
`[longitude, latitude, altitude]` (RFC 7946). Opens in QGIS, geojson.io, and
most web maps; it is also the canonical format the HTML/web-UI viewers render.

## KML

```bash
dji-embed convert kml DJI_0001.SRT              # -> DJI_0001.kml
```

A `LineString` placemark with absolute altitude — double-click to open the
flight path in Google Earth.

## Privacy

Both formats honour `--redact`:

```bash
dji-embed convert geojson DJI_0001.SRT --redact drop   # empty track, no coords
dji-embed convert kml DJI_0001.SRT --redact fuzz       # ~100 m coarsened coords
```

Pre-GPS-lock `(0, 0)` frames are always excluded.

## Batch

```bash
dji-embed convert geojson ./footage --batch     # all *.SRT in the folder
```
```

- [ ] **Step 2: Add the new formats to `README.md`**

In `README.md`, find the line listing GPX/CSV export under the features (search for `GPX` near "Export"). Add GeoJSON/KML alongside it. For example, if the line reads:

```markdown
- **Export formats**: JSON, GPX, CSV
```

change it to:

```markdown
- **Export formats**: JSON, GPX, CSV, GeoJSON, KML
```

If the exact wording differs, make the minimal edit that adds **GeoJSON** and **KML** to the existing export-formats list, and add a one-line pointer to `docs/geospatial.md`.

- [ ] **Step 3: Verify the docs build is not broken (links)**

Run: `uv run python -c "import pathlib; assert pathlib.Path('docs/geospatial.md').exists()"`
Expected: no error.

- [ ] **Step 4: Commit**

```bash
git add docs/geospatial.md README.md
git commit -m "docs(geo): document geojson and kml export"
```

---

### Task 7: Full suite + finish

- [ ] **Step 1: Run the entire test suite**

Run: `uv run pytest -q`
Expected: all pass (the pre-existing `flask`-missing skip in `tests/test_ui_server.py` is unrelated and fine).

- [ ] **Step 2: Smoke-test the CLI end to end**

```bash
uv run dji-embed convert geojson samples/air3S/clip.SRT -o /tmp/clip.geojson
uv run dji-embed convert kml samples/air3S/clip.SRT -o /tmp/clip.kml
head -c 120 /tmp/clip.geojson; echo; head -c 120 /tmp/clip.kml
```

Expected: a `FeatureCollection` JSON and a `<kml ...>` document.

- [ ] **Step 3: Push and open the PR**

```bash
git push -u origin feat/issue-215-track-export
gh pr create --base master \
  --title "feat(geo): GeoJSON + KML track export (Phase 1, #215)" \
  --body "Closes the track-only scope of #215. Adds convert geojson|kml over a shared Track model with --redact. Unblocks the viewer work (#221/#222)."
```

---

## Self-Review

**Spec coverage (Phase 1 acceptance criteria):**
- `convert geojson`/`convert kml` produce valid output → Tasks 2, 3, 5. ✓
- GeoJSON has track LineString + per-point properties; KML opens in Google Earth → Task 2 (LineString + Point props), Task 3 (absolute-altitude LineString). ✓
- `--redact` honored → Task 1 (Track layer), Task 5 (CLI option + drop test). ✓
- Unit tests: fixture → expected structure; CLI smoke tests → Tasks 1–3, 5. ✓
- Docs: README + `docs/geospatial.md` → Task 6. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code; README edit gives an exact before/after with a fallback rule. ✓

**Type consistency:** `build_track(srt_file, redact)` returns `Track(name, points: list[TrackPoint(lat, lon, alt, timestamp)])`; `track_to_geojson`/`track_to_kml` consume `Track`; `convert_to_geojson`/`convert_to_kml(srt_file, output_file, redact)` used identically in CLI Task 5. Names match across tasks. ✓

**Deviation noted:** The spec's GeoJSON Point properties mention `speed` and `rel_alt` "if available". `parse_telemetry_points` only yields `(lat, lon, abs_alt, timestamp)`, so Phase 1 emits `abs_alt` + `timestamp` only; `speed`/`rel_alt` are a clean follow-up if a richer point parser lands. This keeps Phase 1 honest to its data source.
