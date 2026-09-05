# Airspace fixtures (#413)

Trimmed copies of public regulatory feeds, shaped like the live responses
verified on issue #413 (2026-07-29). Public data, no privacy concern.

- `faa-uasfm.json` — FAA UAS Facility Map ArcGIS `f=geojson` response
  (LaGuardia-area grid cells; US-Government work, public-domain class).
- `ed269-lu.json` — Luxembourg ED-269 document (drones.geoportail.lu, CC0).
  Ships with the UTF-8 BOM the live feed has.
- `ed269-fi.json` — Finland ED-269 document (Traficom, CC BY 4.0). BOM too;
  includes a zone with no upper/lower limit ("not stated" path).
- `ed269-ch.json` — Switzerland ED-269 document (BAZL, O-BY; live shape
  verified on issue #456, 2026-08-02). No BOM, like the live feed. Includes
  the `99999 m` no-ceiling sentinel in both its AGL and AMSL forms, and a
  multi-volume zone whose volumes share identical vertical limits.
- `ed318-ie.json` — Ireland ED-318 document (iaa.ie, "reference only — not
  to be used for navigation"; live shape verified on issue #452,
  2026-08-14).
- `aixm51-gb.xml` — UK AIXM 5.1 UAS flight-restrictions document (NATS AIS;
  live shape verified on issue #499, 2026-08-15; usage unrestricted per the
  product's ISO 19115 metadata — not for resale, for aviation use only).
- `dronezoner-dk.json` — Denmark drone-zone document (Trafikstyrelsen,
  "Data kan frit anvendes med kildeangivelse" / free use with attribution;
  live shape verified on issue #508, 2026-08-15).
- `ed318-se.json` — **synthetic**, not a trimmed copy. Invented zones in the
  real LFV file's ED-318 shape (issue #510, 2026-08-19), deliberate under
  LFV's condition that the zone content not be modified — a trimmed extract
  of the live file would have breached that, so this fixture pastes no live
  LFV zone data at all. Don't "fix" it by swapping in real zones.
- `eans-ee.json` — **synthetic**, not a trimmed copy. Invented zones in the
  real EANS `uas.geojson` shape (issue #511, 2026-08-19), covering both
  viewer-furniture masks the parser must skip — a `hidden` feature and the
  world-spanning `EERZout` "Outside Estonia" prohibition — so the fixture
  pins the skip contract instead of just the happy path. Attribution:
  "Estonian Air Navigation Services", public data confirmed in writing by
  EANS UTM development.
- `caa-si.kml` — Slovenia: the `doc.kml` inside the CAA's "UAS Geo zones -
  May 2026" KMZ (caa.si, file dated 2026-05-25; issue #565, live shape
  verified 2026-09-05), trimmed to one placemark per representative folder
  (9 of 137) with each ring reduced to a few of its real vertices. Every
  placemark's popup HTML is kept whole: that table IS the attribute schema,
  and its field names differ per folder. Tests wrap the KML into the live
  zip→kmz nesting in memory. Reproduced under the CAA site's terms of use
  (source marked, data content unchanged).

The manual E2E step before merge re-fetches each live endpoint and confirms
these shapes still match; `ed318-se.json` and `eans-ee.json` are synthetic,
so there is nothing to byte-match for them — but their live endpoints are
still re-fetched and each fixture's shape confirmed against it (these are
the fixtures with no tie to a live file, which makes them the most prone to
drifting from reality unnoticed).
