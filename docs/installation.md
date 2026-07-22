# Installation

[← Back to Home](index.md)

## Easy Windows install

### Windows – installer with desktop app (recommended)

Download `dji-metadata-embedder-setup-<version>.exe` from the
[latest release](https://github.com/CallMarcus/dji-drone-metadata-embedder/releases/latest)
and run it. One installer carries everything:

- the **DJI Metadata Embedder** desktop app (Start menu entry) for the
  common tasks — make a map, embed telemetry, check your setup — with no
  command line involved;
- the full `dji-embed` command line, ready in any new terminal window
  (the install folder is added to your user PATH);
- pinned FFmpeg and ExifTool builds, so nothing else needs installing.

No admin rights needed — it installs per-user. The uninstaller removes the
PATH entries again. From v1.23.0 the installer and every binary inside it
are Authenticode code-signed, so Windows shows a verified publisher instead
of an "unknown publisher" warning.

### Windows – bootstrap script

```powershell
iwr -useb https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/master/tools/bootstrap.ps1 | iex
```

The bootstrap script also installs FFmpeg and ExifTool (CLI only, no
desktop app).

### Windows – winget

```powershell
winget install CallMarcus.DJIMetadataEmbedder
```

Installs the portable `dji-embed.exe`. FFmpeg and ExifTool are not bundled — add
them with `winget install Gyan.FFmpeg OliverBetz.ExifTool`, or use the bootstrap
script above, which bundles everything. For MP4 timed-metadata support you can
also let the tool install its own pinned ExifTool: `dji-embed doctor --install
exiftool` (any OS, no admin rights).

The full desktop-app installer is also on winget as a separate package
(from v1.23.0, appearing shortly after each release once the winget
moderators approve it):

```powershell
winget install CallMarcus.DJIMetadataEmbedder.Desktop
```

Install one or the other — both put `dji-embed` on PATH.

### Windows – manual path

```powershell
pip install dji-drone-metadata-embedder
```

### macOS

```bash
brew install ffmpeg exiftool pipx
pipx install dji-drone-metadata-embedder
```

Homebrew's Python is [externally managed](https://peps.python.org/pep-0668/),
so a bare `pip install` is refused with an `externally-managed-environment`
error — `pipx` installs the tool into its own isolated environment and puts
`dji-embed` on your PATH (run `pipx ensurepath` once if the command isn't
found in a new terminal).

### Linux

```bash
sudo apt update && sudo apt install ffmpeg exiftool
pip install dji-drone-metadata-embedder
```

Distro ExifTool packages are often too old for DJI MP4 timed metadata —
run `dji-embed doctor --install exiftool` to get a current, checksum-verified
copy in your user directory.

### Docker

```bash
docker run --rm -v "$PWD":/data callmarcus/dji-embed embed /data
```

## Prefer clicking over typing?

On Windows, the installer bundles the [desktop app](desktop-app.md) —
folder in, map or telemetry out, no terminal. For viewing maps from any
OS there's `dji-embed photomap <folder> --serve`.
See the [User Guide](user_guide.md#web-ui-deprecated) for details.

<details>
<summary>Advanced</summary>

- Build from source with `uv sync --extra dev` (or `pip install -e .`)
- Use the provided `Dockerfile` to customize images
- CI scripts live under `.github/workflows`

</details>

## Validation tests

The scripts in [`validation_tests`](validation_tests.md) verify that
your installation is ready for real footage. Before running them, make sure that
`ffmpeg` and `exiftool` can be found on your `PATH`.

`validation_tests/test_installation_and_dependencies.py` specifically checks for
these binaries. If either command is missing the tests will fail early. Use the
installation steps above—your package manager on
macOS/Linux—to install FFmpeg and ExifTool before running the validation suite.

