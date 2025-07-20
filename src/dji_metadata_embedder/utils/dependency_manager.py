from __future__ import annotations

import logging
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Dict, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


class DependencyManager:
    """Manage download and verification of external dependencies."""

    FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-essentials.zip"
    EXIFTOOL_URL = "https://exiftool.org/exiftool-13.32_64.zip"

    def __init__(self, tools_dir: Path) -> None:
        """Initialize manager with tools directory."""
        self.tools_dir = tools_dir
        self.ffmpeg_dir = self.tools_dir / "ffmpeg"
        self.exiftool_dir = self.tools_dir / "exiftool"
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(level=logging.INFO)

    # internal helper to download file with progress
    def _download(self, url: str, dest: Path) -> None:
        logging.info("Downloading %s", url)
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req) as response, open(dest, "wb") as out_file:
                total_length = response.length
                downloaded = 0
                block_size = 8192
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    out_file.write(buffer)
                    downloaded += len(buffer)
                    if total_length:
                        percent = downloaded * 100 / total_length
                        logging.info("%s %.2f%%", dest.name, percent)
        except (URLError, HTTPError) as exc:
            raise RuntimeError(f"Failed to download {url}: {exc}")

    def _extract_zip(self, zip_path: Path, target_dir: Path) -> None:
        logging.info("Extracting %s to %s", zip_path, target_dir)
        with zipfile.ZipFile(zip_path, "r") as zf:
            if target_dir.exists():
                shutil.rmtree(target_dir)
            zf.extractall(target_dir)
        zip_path.unlink(missing_ok=True)

    def download_ffmpeg(self) -> bool:
        """Download and extract FFmpeg. Returns True on success."""
        zip_path = self.tools_dir / "ffmpeg.zip"
        try:
            self._download(self.FFMPEG_URL, zip_path)
            self._extract_zip(zip_path, self.ffmpeg_dir)
            return True
        except Exception as exc:  # noqa: BLE001
            logging.error("FFmpeg download failed: %s", exc)
            return False

    def download_exiftool(self) -> bool:
        """Download and extract ExifTool. Returns True on success."""
        zip_path = self.tools_dir / "exiftool.zip"
        try:
            self._download(self.EXIFTOOL_URL, zip_path)
            self._extract_zip(zip_path, self.exiftool_dir)
            return True
        except Exception as exc:  # noqa: BLE001
            logging.error("ExifTool download failed: %s", exc)
            return False

    def _get_executable_version(self, exec_path: Path, args: list[str]) -> Optional[str]:
        try:
            result = subprocess.run([str(exec_path), *args], capture_output=True, text=True, check=True)
            return result.stdout.strip().splitlines()[0]
        except (subprocess.SubprocessError, FileNotFoundError):
            return None

    def verify_dependencies(self) -> Dict[str, bool]:
        """Verify downloaded dependencies by calling their version commands."""
        ffmpeg_exec = self._find_ffmpeg_executable()
        exif_exec = self._find_exiftool_executable()
        ffmpeg_ok = bool(self._get_executable_version(ffmpeg_exec, ["-version"])) if ffmpeg_exec else False
        exif_ok = bool(self._get_executable_version(exif_exec, ["-ver"])) if exif_exec else False
        return {"ffmpeg": ffmpeg_ok, "exiftool": exif_ok}

    def get_dependency_info(self) -> Dict[str, Dict[str, Optional[str]]]:
        """Return path and version information for dependencies."""
        ffmpeg_exec = self._find_ffmpeg_executable()
        exif_exec = self._find_exiftool_executable()
        info = {
            "ffmpeg": {
                "path": str(ffmpeg_exec) if ffmpeg_exec else None,
                "version": self._get_executable_version(ffmpeg_exec, ["-version"]) if ffmpeg_exec else None,
            },
            "exiftool": {
                "path": str(exif_exec) if exif_exec else None,
                "version": self._get_executable_version(exif_exec, ["-ver"]) if exif_exec else None,
            },
        }
        return info

    def _find_ffmpeg_executable(self) -> Optional[Path]:
        candidate = None
        if self.ffmpeg_dir.exists():
            for name in ("ffmpeg.exe", "ffmpeg"):
                path = next(self.ffmpeg_dir.rglob(name), None)
                if path:
                    candidate = path
                    break
        # Look in tools_dir itself when executables are placed directly under bin
        if not candidate and self.tools_dir.exists():
            for name in ("ffmpeg.exe", "ffmpeg"):
                path = self.tools_dir / name
                if path.exists():
                    candidate = path
                    break
        if not candidate:
            found = shutil.which("ffmpeg")
            if found:
                candidate = Path(found)
        return candidate

    def _find_exiftool_executable(self) -> Optional[Path]:
        candidate = None
        if self.exiftool_dir.exists():
            for name in ("exiftool.exe", "exiftool"):
                path = next(self.exiftool_dir.rglob(name), None)
                if path:
                    candidate = path
                    break
        if not candidate and self.tools_dir.exists():
            for name in ("exiftool.exe", "exiftool"):
                path = self.tools_dir / name
                if path.exists():
                    candidate = path
                    break
        if not candidate:
            found = shutil.which("exiftool")
            if found:
                candidate = Path(found)
        return candidate
