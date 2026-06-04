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
