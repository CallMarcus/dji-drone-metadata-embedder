"""Shared ArcGIS FeatureServer paging (#451).

Follows ``exceededTransferLimit`` until the server stops flagging it, so a
truncated page set never presents itself as complete. Used by the FAA (US)
and ENAIRE (ES) providers; *label* names the service in every error.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request

from .model import AirspaceError

_TIMEOUT_S = 60


def fetch_arcgis_pages(
    url_for_offset: Callable[[int], str], label: str, transport
) -> list[bytes]:
    """All response pages, in order; raises on any failure."""
    pages: list[bytes] = []
    offset = 0
    while True:
        req = Request(url_for_offset(offset), headers={"User-Agent": "dji-embed"})
        try:
            with transport(req, timeout=_TIMEOUT_S) as resp:
                body = resp.read()
        except HTTPError as exc:
            raise AirspaceError(f"{label} query answered HTTP {exc.code}") from exc
        except (URLError, OSError) as exc:
            raise AirspaceError(f"{label} query failed: {exc}") from exc
        pages.append(body)
        try:
            doc = json.loads(body)
        except ValueError as exc:
            raise AirspaceError(f"{label} response is not JSON") from exc
        if isinstance(doc, dict) and "error" in doc:
            err = doc["error"]
            message = err.get("message") if isinstance(err, dict) else err
            raise AirspaceError(f"{label} query returned an error: {message}")
        if not isinstance(doc, dict) or "features" not in doc:
            raise AirspaceError(f"{label} response has no 'features' list")
        exceeded = doc.get("exceededTransferLimit") or (
            isinstance(doc.get("properties"), dict)
            and doc["properties"].get("exceededTransferLimit")
        )
        if not exceeded:
            return pages
        features = doc.get("features") or []
        if not features:
            raise AirspaceError(
                f"{label} paging cannot establish completeness "
                "(transfer limit flagged on an empty page)"
            )
        # Advance by the real feature count returned by this page — the
        # server's page size may be under the ArcGIS default of 1000, and
        # guessing a fixed stride would silently skip records.
        offset += len(features)
