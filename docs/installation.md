# Installation

[← Back to Home](index.md)

## Easy Windows install

```powershell
iwr -useb https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/master/tools/bootstrap.ps1 | iex
```


### Windows – manual path

```powershell
pip install dji-drone-metadata-embedder
```
```bash
brew install ffmpeg exiftool
sudo apt update && sudo apt install ffmpeg exiftool
pip install dji-drone-metadata-embedder
```

```bash
docker run --rm -v "$PWD":/data callmarcus/dji-embed -i *.MP4
```

## Optional: browser-based UI

If you'd rather drive the tool from a browser than the terminal, install
the `[ui]` extra and launch it:

```bash
pip install 'dji-drone-metadata-embedder[ui]'
dji-embed ui
```

The UI binds to `127.0.0.1` only and opens in your default browser.
See the [User Guide](user_guide.md#web-ui) for details.

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

