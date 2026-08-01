# Installation

[← Back to Home](index.md)

## Windows

### Installer with desktop app (recommended)

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

### Bootstrap script

```powershell
iwr -useb https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/master/tools/bootstrap.ps1 | iex
```

The bootstrap script also installs FFmpeg and ExifTool (CLI only, no
desktop app).

### winget

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

### Manual path

```powershell
pip install dji-drone-metadata-embedder
```

## macOS

### DMG with desktop app (recommended)

Download `dji-metadata-embedder-<version>-macos-arm64.dmg` from the
[latest release](https://github.com/CallMarcus/dji-drone-metadata-embedder/releases/latest),
open it, and drag **DJI Metadata Embedder** to Applications. The app is
Developer ID-signed, notarized and stapled — first launch works offline
and shows only the standard "downloaded from the internet" dialog. It's
the same workspace as on Windows, and carries the full `dji-embed` CLI
inside the bundle (at
`/Applications/DJI Metadata Embedder.app/Contents/MacOS/dji-embed`).

The app supports Apple Silicon Macs (M1 or later) on macOS 14 Sonoma or
newer — that floor is deliberate. On Intel Macs or older macOS, use the
pipx route below.

FFmpeg and ExifTool come from Homebrew: `brew install ffmpeg exiftool`.
The app's Setup screen confirms it found them.

To use the bundled CLI from a terminal, symlink it rather than extending
`PATH` — the directory also holds the app's two hundred runtime libraries:

```bash
sudo mkdir -p /usr/local/bin
sudo ln -sf "/Applications/DJI Metadata Embedder.app/Contents/MacOS/dji-embed" /usr/local/bin/dji-embed
```

The `mkdir` is not ceremony: on an Apple Silicon Mac, Homebrew installs to
`/opt/homebrew` and nothing else creates `/usr/local/bin`, so it is often
missing and `ln` fails with *No such file or directory*. macOS lists it in
`/etc/paths` regardless, so once it exists it is on your `PATH`.

### pipx (CLI only — works on any Mac, Intel included)

```bash
brew install ffmpeg exiftool pipx
pipx install dji-drone-metadata-embedder
```

Homebrew's Python is [externally managed](https://peps.python.org/pep-0668/),
so a bare `pip install` is refused with an `externally-managed-environment`
error — `pipx` installs the tool into its own isolated environment and puts
`dji-embed` on your PATH (run `pipx ensurepath` once if the command isn't
found in a new terminal).

### Standalone CLI binary

On Apple Silicon, grab the standalone `dji-embed-macos-arm64.zip` from the
[GitHub Releases page](https://github.com/CallMarcus/dji-drone-metadata-embedder/releases),
unzip it, and run `./dji-embed`. The binary is Developer ID-signed and
notarized, but a bare binary can't carry a stapled notarization ticket, so
the **first run needs a network connection** for Gatekeeper's online ticket
check (the DMG app above is stapled and has no such requirement). Verify
either download against `SHA256SUMS-macos.txt` from the same release.

Run it from a terminal, not by double-clicking it in Finder. It is a
command-line tool, so a double-click only opens a window, runs it with no
arguments and closes; and because Finder applies the strictest Gatekeeper
path to a downloaded executable, that is also where you may meet
**"Apple could not verify 'dji-embed' is free of malware"**. That wording
means the online ticket check could not be completed — it is not the
"developer cannot be verified" message an unsigned binary gets. Check
your network, then clear the download quarantine flag and run it
normally:

```bash
xattr -d com.apple.quarantine ./dji-embed
./dji-embed --version
```

If you would rather not think about any of this, use the DMG: its ticket
is stapled, so it never needs the online check.

## Linux

```bash
sudo apt update && sudo apt install ffmpeg exiftool
pip install dji-drone-metadata-embedder
```

Distro ExifTool packages are often too old for DJI MP4 timed metadata —
run `dji-embed doctor --install exiftool` to get a current, checksum-verified
copy in your user directory.

## Docker

```bash
docker run --rm -v "$PWD":/data callmarcus/dji-embed embed /data
```

## Upgrading

`dji-embed doctor` tells you when a newer version exists, and names the
command for the way *you* installed it. The paths, for reference:

| How you installed | How you upgrade |
| --- | --- |
| Windows installer | Run the new installer over the old one, or `winget upgrade CallMarcus.DJIMetadataEmbedder.Desktop` |
| Windows, winget CLI | `winget upgrade CallMarcus.DJIMetadataEmbedder` |
| macOS DMG | Open the new DMG and drag the app to Applications, replacing the old one — the bundled `dji-embed` comes with it |
| macOS standalone binary | Download the new `dji-embed-macos-arm64.zip` and replace the binary you unzipped |
| pipx (any OS) | `pipx upgrade dji-drone-metadata-embedder` |
| pip (any OS) | `pip install --upgrade dji-drone-metadata-embedder` |

**If `dji-embed --version` still shows the old version afterwards**, you
have two copies and the older one comes first on `PATH`. `which -a
dji-embed` (`where dji-embed` on Windows) lists them in the order the
shell searches. This bites most often on macOS, where a `pipx` install
in `~/.local/bin` predates a later DMG install.

On macOS the tidiest fix is to keep one copy — the app's — and point a
symlink at it, so it follows the app from then on:

```bash
pipx uninstall dji-drone-metadata-embedder   # if pipx put an older one on PATH
sudo mkdir -p /usr/local/bin                 # often absent on Apple Silicon
sudo ln -sf "/Applications/DJI Metadata Embedder.app/Contents/MacOS/dji-embed" /usr/local/bin/dji-embed
hash -r && dji-embed --version
```

Loose copies you unzipped earlier are worth deleting rather than leaving
around: they never update, and running one by its full path reports its
own old version, which reads like a failed upgrade.

## Prefer clicking over typing?

The [desktop app](desktop-app.md) — folder in, map or telemetry out, no
terminal — comes with the Windows installer and the macOS DMG. For
viewing maps from any OS there's `dji-embed photomap <folder> --serve`.
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

