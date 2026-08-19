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
  live shape verified on issue #499, 2026-08-15). No location sent to fetch
  it; the whole dataset comes back regardless of where the flight was.
- `dronezoner-dk.json` — Denmark drone-zone document (Trafikstyrelsen,
  "Data kan frit anvendes med kildeangivelse" / free use with attribution;
  live shape verified on issue #508, 2026-08-15).
- `ed318-se.json` — **synthetic**, not a trimmed copy. Invented zones in the
  real LFV file's ED-318 shape (issue #510, 2026-08-19), deliberate under
  LFV's condition that the zone content not be modified — a trimmed extract
  of the live file would have breached that, so this fixture pastes no live
  LFV zone data at all. Don't "fix" it by swapping in real zones.

The manual E2E step before merge re-fetches each live endpoint and confirms
these shapes still match; `ed318-se.json` is exempt from that step since
it is not derived from the live feed.
