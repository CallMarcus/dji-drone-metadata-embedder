# A printable flight record with airspace facts

A flight record is a factual account of a flight, built entirely from the
aircraft's own telemetry — no manual entry. It opens as one page per flight
plus a logbook table on top, ready to print or save as a PDF for a logbook,
a client, or your own records.

```bash
dji-embed flightmap ./flights -f record
```

This writes `flight-record.html` next to your footage. Every figure on it
carries its source and what it approximates — a missing datum is stated as
a note, never filled in with a guessed number.

A flight record needs exact coordinates to place a track against airspace
zones honestly, so `-f record` refuses to run with `--redact fuzz` — drop
`--redact` for a record, or use `--redact fuzz` for the map formats instead.

## What gets fetched, and what it reveals

Building the record's airspace section, and the surface-referenced height
estimate, are **the only network access in this command**. The logbook and
the track come from the SRT telemetry already on disk; so does the
takeoff-referenced height, which is aircraft-reported. The
surface-referenced height is the exception — it needs a fetch from
Mapterhorn's terrain tiles (see "The `[terrain]` extra" below).

Three feeds are used:

- **US flights** query the FAA's UAS Facility Map (keyless ArcGIS). The
  bounding box sent to the endpoint is padded and snapped outward to a
  0.1° grid before it goes on the wire, so the endpoint learns no more
  about where you flew than a map-tile fetch already would.
- **Luxembourg and Finland** flights fetch the country's whole ED-269
  geographical-zone document — the feed has no query parameter for a
  location at all, so nothing about the flight is sent; the entire country's
  zones come back regardless of where the flight was.
- **Every flight**, regardless of jurisdiction, fetches surface-height
  tiles from Mapterhorn (`tiles.mapterhorn.com`) for the surface-referenced
  height estimate, when the `[terrain]` extra is installed.

Every fetch is announced before it happens, and the response is cached
beside the output — airspace data at `airspace-cache/`, terrain tiles
alongside it — so a re-run reuses both and stays offline. Pass
`--airspace-refresh` to bypass the airspace cache and fetch again (does
nothing without `-f record`; terrain tiles are unaffected by this flag).

```bash
dji-embed flightmap ./flights -f record --airspace-refresh
```

## Coverage: US, Luxembourg, Finland — and an honest gap everywhere else

Airspace lookup only resolves for flights that sit clearly inside the
United States, Luxembourg, or Finland. Everywhere else — including
Sweden — the record states the gap instead of guessing: *"no supported
airspace data source for this location."* A flight near a jurisdiction
boundary gaps the same way, deliberately, rather than borrowing a
neighbouring country's rules from coordinates alone. The logbook half of
the record (times, distances, heights) is unaffected — a gapped airspace
section never blocks the rest.

Widening coverage means adding and verifying another feed; it will grow,
but a wrong jurisdiction guessed from coordinates would be worse than no
jurisdiction at all.

## Three heights, each labelled with what it means

The record prints up to three height figures per flight, and never
substitutes one for another:

- **Height above takeoff point** — aircraft-reported, exact, straight from
  telemetry.
- **Estimated height above surface** — the aircraft's height above takeoff
  combined with a digital surface model (includes vegetation and buildings)
  under the flight path; requires the `[terrain]` extra and a network
  connection.
- **Altitude (AMSL)** — the aircraft-reported altitude above mean sea level,
  where the telemetry carries one.

Height above takeoff is **not** the regulatory measure, in either
jurisdiction covered here: both the FAA's 400 ft AGL limit and the EU's
120 m surface limit are measured above the ground directly under the
aircraft, not above the point it launched from. On sloped or varied
terrain the two diverge — a hover over a valley reads higher above takeoff
than it is above the ground beneath it. The surface-referenced estimate is
the one that approximates the regulatory measure; see the 3D map's
[terrain view](../geospatial.md#3d-terrain-view) for the same digital
surface model used to drape flights over real ground.

## The `[terrain]` extra

The surface-referenced height needs the `terrain` extra:

```bash
pip install 'dji-drone-metadata-embedder[terrain]'
```

Without it, the record still writes — the surface height row states why
it's missing rather than silently disappearing. The Windows EXE and
installer builds ship with `[terrain]` already included, so this only
matters for a `pip install`.

## Printing to PDF

The record is a single self-contained HTML file with print styles built
in — open it in a browser and use **Print → Save as PDF**. No extra tool
or export step is needed.

## What this record is not

The record states facts and their sources; it does not determine whether a
flight complied with any regulation. Both the FAA's Part 107 rules and the
EU's Open Category rules carry exceptions — structures, obstacles, and
others — that telemetry alone cannot evaluate. Read every airspace
zone and height figure as a measurement, not a verdict.

The same zones can be drawn on the interactive map: `dji-embed flightmap
FLIGHTS --airspace` overlays them on the 2D HTML map, sharing this
command's cache and consent model.
