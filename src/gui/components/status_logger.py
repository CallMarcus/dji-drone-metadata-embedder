"""Component for logging status messages to the user."""

from __future__ import annotations


class StatusLogger:
    """Collect status messages for display in the GUI."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def log(self, message: str) -> None:
        """Add a message to the log."""
        self.messages.append(message)

    def clear(self) -> None:
        """Clear all logged messages."""
        self.messages.clear()
