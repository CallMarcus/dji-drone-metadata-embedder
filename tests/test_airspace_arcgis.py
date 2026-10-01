"""Shared ArcGIS paging (#451): used by the FAA and ENAIRE providers."""

import json

import pytest

from dji_metadata_embedder.geo.airspace import AirspaceError
from dji_metadata_embedder.geo.airspace.arcgis import fetch_arcgis_pages


class FakeTransport:
    def __init__(self, bodies):
        self.bodies = list(bodies)
        self.urls = []

    def __call__(self, req, timeout=None):
        self.urls.append(req.full_url)
        import io

        resp = io.BytesIO(self.bodies.pop(0))
        resp.__enter__ = lambda *a: resp  # type: ignore[method-assign]
        resp.__exit__ = lambda *a: False  # type: ignore[method-assign]
        return resp


def _page(n, exceeded):
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {"i": k}} for k in range(n)],
            "exceededTransferLimit": exceeded,
        }
    ).encode()


def test_pages_follow_the_transfer_limit_with_the_real_feature_count():
    fake = FakeTransport([_page(3, True), _page(2, False)])
    pages = fetch_arcgis_pages(
        lambda off: f"https://example.invalid/q?offset={off}", "Test service", fake
    )
    assert len(pages) == 2
    assert fake.urls == [
        "https://example.invalid/q?offset=0",
        "https://example.invalid/q?offset=3",
    ]


def test_errors_carry_the_callers_label():
    fake = FakeTransport([b"<html>maintenance</html>"])
    with pytest.raises(AirspaceError, match="Test service response is not JSON"):
        fetch_arcgis_pages(
            lambda off: "https://example.invalid/q", "Test service", fake
        )
    fake = FakeTransport([json.dumps({"error": {"message": "bad"}}).encode()])
    with pytest.raises(
        AirspaceError, match="Test service query returned an error: bad"
    ):
        fetch_arcgis_pages(
            lambda off: "https://example.invalid/q", "Test service", fake
        )
