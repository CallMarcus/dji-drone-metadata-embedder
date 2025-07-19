"""Core processing pipeline for embedding metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


class Processor:
    """Process media files to embed DJI metadata."""

    def __init__(self, input_files: Iterable[Path]) -> None:
        self.input_files = [Path(p) for p in input_files]

    def process(self) -> None:
        """Process each input file."""
        for _file in self.input_files:
            # Placeholder for actual processing logic
            _ = _file  # avoid unused variable warning
            pass
