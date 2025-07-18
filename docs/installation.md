# Installation

[← Back to README](../README.md)

## Easy Windows install

```powershell
iwr -useb https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/master/tools/bootstrap.ps1 | iex
```

The script fetches the latest version automatically and falls back to `1.0.2` if GitHub or PyPI are unreachable. Use `-Version` to specify a different release.

```powershell
winget install -e --id CallMarcus.DJI-Embed
```

If winget cannot locate the package, it may still be awaiting approval. Run the PowerShell one-liner above instead.

### Windows – manual path

```powershell
winget install -e --id Python.Python.3
winget install -e --id Gyan.FFmpeg
winget install -e --id PhilHarvey.ExifTool
pip install dji-metadata-embedder
```

## macOS / Linux quick-start

```bash
brew install ffmpeg exiftool
sudo apt update && sudo apt install ffmpeg exiftool
pip install dji-drone-metadata-embedder
```

```bash
docker run --rm -v "$PWD":/data callmarcus/dji-embed -i *.MP4
```

<details>
<summary>Advanced</summary>

- Build from source with `pip install -r requirements.txt`
- Use the provided `Dockerfile` to customize images
- CI scripts live under `.github/workflows`

</details>
