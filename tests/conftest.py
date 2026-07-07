import logging
import sys
import types

# Provide stub implementations of the "rich" package so the library modules
# can be imported in the test environment without installing the dependency.
if "rich" not in sys.modules:
    rich = types.ModuleType("rich")
    progress = types.ModuleType("rich.progress")
    logging_mod = types.ModuleType("rich.logging")

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

        def __init__(self, *args, **kwargs):
            super().__init__()

    setattr(progress, "Progress", _StubProgress)
    setattr(logging_mod, "RichHandler", _StubRichHandler)
    setattr(rich, "progress", progress)
    setattr(rich, "logging", logging_mod)
    sys.modules["rich"] = rich
    sys.modules["rich.progress"] = progress
    sys.modules["rich.logging"] = logging_mod

import pytest


@pytest.fixture(autouse=True)
def _isolate_tools_dir(monkeypatch, tmp_path_factory):
    """Keep a developer's provisioned ExifTool from leaking into tests."""
    monkeypatch.setenv("DJIEMBED_TOOLS_DIR", str(tmp_path_factory.mktemp("tools")))
