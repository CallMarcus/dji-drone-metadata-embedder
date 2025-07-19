"""Validation utilities for input files."""

from __future__ import annotations

from pathlib import Path


class Validator:
    """Validate files before processing."""

    def is_valid(self, file_path: Path) -> bool:
        """Return True if the given path exists."""
        return Path(file_path).exists()
