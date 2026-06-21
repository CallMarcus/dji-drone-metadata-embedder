# Generate GPX

The `dji-embed convert` command turns DJI SRT telemetry files into GPX tracks
(it can also emit CSV, GeoJSON, KML, HTML, or CoT).

Convert a single file:

```bash
dji-embed convert gpx DJI_0001.SRT
```

Process an entire directory:

```bash
dji-embed convert gpx /path/to/srt --batch
```

By default the `.gpx` file is written next to the input SRT (e.g.
`DJI_0001.gpx`). Pass `-o/--output` to choose a different location.
