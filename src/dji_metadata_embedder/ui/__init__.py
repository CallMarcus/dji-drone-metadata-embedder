"""Local web UI for dji-embed.

Runs a Flask app bound to 127.0.0.1 and served in the user's default browser.
No new binaries are shipped; trust is delegated to the installed browser.

Requires the optional ``[ui]`` extra.
"""

from __future__ import annotations

__all__ = ["create_app", "run_server"]


def __getattr__(name: str):
    if name in __all__:
        from . import server

        return getattr(server, name)
    raise AttributeError(name)
