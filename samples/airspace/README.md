# Airspace fixtures (#413)

Trimmed copies of public regulatory feeds, shaped like the live responses
verified on issue #413 (2026-07-29). Public data, no privacy concern.

- `faa-uasfm.json` — FAA UAS Facility Map ArcGIS `f=geojson` response
  (LaGuardia-area grid cells; US-Government work, public-domain class).
- `ed269-lu.json` — Luxembourg ED-269 document (drones.geoportail.lu, CC0).
  Ships with the UTF-8 BOM the live feed has.
- `ed269-fi.json` — Finland ED-269 document (Traficom, CC BY 4.0). BOM too;
  includes a zone with no upper/lower limit ("not stated" path).

The manual E2E step before merge re-fetches each live endpoint and confirms
these shapes still match.
