# Troubleshooting

This page lists solutions to common issues encountered when running `dji-embed`.

## "ffmpeg is not recognized"

The program requires FFmpeg to be installed and available on your `PATH`.

- Verify with `ffmpeg -version` (single dash).
- Running `ffmpeg --version` will produce an `Unrecognized option '--version'` error.
- On Windows, download a build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add its `bin` folder to your `PATH`.

## "exiftool is not recognized"

ExifTool is optional but needed for the `--exiftool` flag.

- Download the package from [exiftool.org](https://exiftool.org/), rename the executable to `exiftool.exe` and add it to your `PATH`.

### "Could not find ...exiftool_files/perl5*.dll"

If ExifTool is installed but fails with a missing `perl5*.dll` message, the
`exiftool_files` directory was not copied alongside `exiftool.exe`.

- Delete the incomplete installation folder (usually `C:\Users\<user>\AppData\Local\dji-embed\bin`).
- Re-run the [PowerShell bootstrap](installation.md#easy-windows-install) to extract
  ExifTool correctly.

## "python was not found"

On Windows, the `python` command may not be available. Use `py` instead:

```cmd
dji-embed /path/to/footage
```

## Permission errors

If the tool fails to write output files, ensure you have permission to create files in the chosen directory. Try running the command prompt or terminal with elevated rights or choose a different output location.
