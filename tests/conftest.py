import logging
import sys
import types

# Provide stub implementations of the "rich" package so the library modules
# can be imported in the test environment without installing the dependency.
if "rich" not in sys.modules:
    rich = types.ModuleType("rich")
    progress = types.ModuleType("rich.progress")
    logging_mod = types.ModuleType("rich.logging")
    console_mod = types.ModuleType("rich.console")

    class _StubConsole:
        """Minimal Console stub: remembers which stream it stands for."""

        def __init__(self, *args, stderr=False, **kwargs):
            self.file = sys.stderr if stderr else sys.stdout

    class _StubProgress:
        """Minimal Progress stub: acts as a no-op context manager."""

        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def add_task(self, *args, **kwargs):
            return 0

        def update(self, *args, **kwargs):
            pass

    class _StubRichHandler(logging.StreamHandler):
        """Minimal RichHandler stub: plain StreamHandler so setup_logging works."""

        def __init__(self, *args, console=None, **kwargs):
            # Honours an explicit console's stream; without one it defaults
            # to stderr (StreamHandler's default). NOTE: the real RichHandler
            # defaults to STDOUT, so in-process tests cannot catch logging
            # polluting jsonl stdout — that guarantee is covered by the
            # subprocess test in test_progress_jsonl.py.
            super().__init__(console.file if console is not None else None)

    setattr(progress, "Progress", _StubProgress)
    setattr(logging_mod, "RichHandler", _StubRichHandler)
    setattr(console_mod, "Console", _StubConsole)
    setattr(rich, "progress", progress)
    setattr(rich, "logging", logging_mod)
    setattr(rich, "console", console_mod)
    sys.modules["rich"] = rich
    sys.modules["rich.progress"] = progress
    sys.modules["rich.logging"] = logging_mod
    sys.modules["rich.console"] = console_mod

import pytest


@pytest.fixture(autouse=True)
def _isolate_tools_dir(monkeypatch, tmp_path_factory):
    """Keep a developer's provisioned ExifTool from leaking into tests."""
    monkeypatch.setenv("DJIEMBED_TOOLS_DIR", str(tmp_path_factory.mktemp("tools")))
