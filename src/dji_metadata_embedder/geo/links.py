"""Hrefs from a generated map to the original media beside it."""

from __future__ import annotations

from urllib.parse import quote


def link_href(name: str, base: str) -> str:
    """Href to an original file: percent-encoded *name* under *base*.

    Each ``/``-separated segment of *name* is fully percent-encoded (spaces,
    ``#``, quotes) while the separators survive, so relative subdirectory
    links from recursive scans still resolve. *base* is taken as-is apart
    from separator normalisation — it may be a relative folder or an absolute
    URL, and encoding it would corrupt ``https://``.
    """
    encoded = "/".join(quote(seg, safe="") for seg in name.split("/"))
    base = base.replace("\\", "/").rstrip("/")
    return f"{base}/{encoded}" if base else encoded
