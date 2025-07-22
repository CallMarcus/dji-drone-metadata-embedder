# Windows Quick Setup

This guide explains two ways to run **DJI Drone Metadata Embedder** on Windows without
needing to manage a Python environment manually.

## Option 1: pipx

1. [Install Python](https://www.python.org/) 3.10 or newer.
2. Open **PowerShell** and install `pipx`:
   ```powershell
   python -m pip install --user pipx
   python -m pipx ensurepath
   ```
   Restart PowerShell so the `pipx` command becomes available.
3. Install the embedder:
   ```powershell
   pipx install dji-drone-metadata-embedder
   ```
   `pipx` creates an isolated environment and adds the `dji-embed` command to your
   user path.
4. Double‑click the provided `process_drone_footage.bat` script and select your
   footage folder when prompted. The script uses the `dji-embed` command installed
   by `pipx`.

## Option 2: PyInstaller executable

1. Install Python 3.10+ and download [PyInstaller](https://pyinstaller.org/) using
   PowerShell:
   ```powershell
   pip install pyinstaller
   ```
2. Build a standalone executable from the project root:
   ```powershell
   pyinstaller --onefile -n dji-embed dji_metadata_embedder/embedder.py
   ```
   The resulting `dist\dji-embed.exe` can be copied anywhere and run without
   Python. You may create a desktop shortcut or batch file that calls the
   executable with your footage directory.

Both methods avoid having to manage virtual environments or command‑line
arguments every time you process videos.
