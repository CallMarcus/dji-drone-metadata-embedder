# Embed GPS

This guide shows how to embed GPS data from an SRT file into your DJI video files.

1. Ensure `ffmpeg` is installed and accessible in your `PATH`.
2. Run the `dji-embed` command pointing at the directory that contains your MP4
   and SRT files:

```bash
dji-embed /path/to/videos
```

3. The processed videos are written to a `processed` directory alongside the
   originals. Pass `-o` to select a different output folder.

For additional metadata such as EXIF GPS tags, add the `--exiftool` option if
`exiftool` is installed:

```bash
dji-embed /path/to/videos --exiftool
```
