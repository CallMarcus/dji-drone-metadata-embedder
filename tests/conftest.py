import sys
import types

# Provide stub implementations of the "rich" package so the library modules
# can be imported in the test environment without installing the dependency.
if "rich" not in sys.modules:
    rich = types.ModuleType("rich")
    progress = types.ModuleType("rich.progress")
    logging_mod = types.ModuleType("rich.logging")
    setattr(progress, "Progress", object)
    setattr(logging_mod, "RichHandler", object)
    setattr(rich, "progress", progress)
    setattr(rich, "logging", logging_mod)
    sys.modules["rich"] = rich
    sys.modules["rich.progress"] = progress
    sys.modules["rich.logging"] = logging_mod
