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

<details>
<summary>Advanced</summary>

- Build from source with `pip install -r requirements.txt`
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

