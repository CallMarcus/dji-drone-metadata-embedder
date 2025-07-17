"""GUI component for selecting files."""

from __future__ import annotations

from pathlib import Path
from typing import Optional


class FileSelector:
    """Placeholder widget allowing the user to choose a file."""

    def __init__(self, initial_path: Path | None = None) -> None:
        self.path: Optional[Path] = Path(initial_path) if initial_path else None

    def select(self, path: Path) -> None:
        """Select a new file path."""
        self.path = Path(path)

    def get_path(self) -> Optional[Path]:
        """Return the currently selected path, if any."""
        return self.path
