"""Simple progress bar component."""

from __future__ import annotations


class ProgressBar:
    """Placeholder progress bar for tracking task completion."""

    def __init__(self) -> None:
        self.value = 0

    def update(self, percent: int) -> None:
        """Update the progress percentage."""
        self.value = max(0, min(100, percent))
