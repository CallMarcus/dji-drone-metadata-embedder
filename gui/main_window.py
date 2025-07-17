"""Main application window for the GUI interface."""

from __future__ import annotations

from pathlib import Path


class MainWindow:
    """Skeleton main window for the future GUI."""

    def __init__(self, project_dir: Path) -> None:
        """Initialize the main window with the project directory."""
        self.project_dir = Path(project_dir)

    def run(self) -> None:
        """Run the GUI event loop."""
        # TODO: connect to actual GUI framework
        pass
