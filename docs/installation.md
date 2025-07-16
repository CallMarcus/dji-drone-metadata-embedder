# Installation

Follow these steps to install **DJI Drone Metadata Embedder** and its dependencies.

## Via `pip`

```bash
pip install dji-drone-metadata-embedder
```

This installs the `dji-embed` command into your current Python environment. Ensure the Python `Scripts` directory is in your `PATH` so the command is available.

## Via `pipx`

[`pipx`](https://pypa.github.io/pipx/) creates an isolated environment and places the command on your user path. It is a convenient option on Windows.

```bash
python -m pip install --user pipx
python -m pipx ensurepath
pipx install dji-drone-metadata-embedder
```

Restart your terminal so `dji-embed` is found.

## FFmpeg

The embedder relies on [FFmpeg](https://ffmpeg.org/) for video processing. Install it according to your platform:

- **Windows:** download a build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), extract it and add the `bin` folder to your `PATH`.
- **macOS:** `brew install ffmpeg`
- **Linux:** use your package manager, e.g. `sudo apt install ffmpeg`

Verify the installation with `ffmpeg -version`.

## ExifTool (optional)

ExifTool is only required when embedding additional metadata. Install it if you plan to use the `--exiftool` option.

- **Windows:** grab the Windows package from [exiftool.org](https://exiftool.org/), rename the executable to `exiftool.exe` and add its folder to `PATH`.
- **macOS:** `brew install exiftool`
- **Linux:** `sudo apt install libimage-exiftool-perl`

With these tools installed you are ready to embed metadata into your DJI footage.
