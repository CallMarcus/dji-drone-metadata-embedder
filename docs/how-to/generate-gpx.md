# Generate GPX

The package can convert DJI SRT telemetry files into GPX tracks using the
`telemetry_converter` module.

Convert a single file:

```bash
python -m dji_metadata_embedder.telemetry_converter gpx DJI_0001.SRT
```

Process an entire directory:

```bash
python -m dji_metadata_embedder.telemetry_converter gpx /path/to/srt --batch
```

GPX files are saved to a `gpx_tracks` directory in the input folder.
