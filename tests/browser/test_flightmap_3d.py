"""3D flightmap (issue #268) behaviour in a real headless Chromium.

The map boots over MapLibre, lists flights in the ``#flights-panel``
checkbox panel, and degrades to the flat-view ``.map-note`` banner when its
terrain source errors. The harness (see ``conftest.py``) aborts every
non-unpkg, non-image external request, so the Mapterhorn TileJSON fetch is
always blocked here — that deterministically exercises the terrain-failure
path on every run, it is not a workaround.
"""

from datetime import datetime, timedelta

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect  # noqa: E402

from dji_metadata_embedder.geo.flightmap3d_html import flights_to_3d_html  # noqa: E402
from dji_metadata_embedder.geo.track import Track, TrackPoint  # noqa: E402

pytestmark = pytest.mark.browser


def _flight(name: str, lat: float, lon: float, points: int) -> Track:
    t0 = datetime(2026, 6, 15, 12, 0, 0)
    return Track(name=name, points=[
        TrackPoint(lat=lat, lon=lon + i * 0.0006, alt=100.0 + i,
                   timestamp=f"00:00:{i:02d},000",
                   utc=t0 + timedelta(seconds=i * 10.0))
        for i in range(points)
    ])


def test_3d_map_boots_and_lists_flights(serve_map, page):
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, 5), _flight("DJI_0002", 11.0, 21.0, 5)],
        "trip",
    )
    serve_map(html)
    expect(page.locator("#flights-panel")).to_be_visible(timeout=15000)
    assert page.locator("#flights-panel input[type=checkbox]").count() == 2
    assert page.locator("#map canvas").count() >= 1


def test_3d_terrain_failure_shows_flat_view_banner(serve_map, page):
    html = flights_to_3d_html([_flight("DJI_0001", 10.0, 20.0, 5)], "trip")
    serve_map(html)
    expect(page.locator(".map-note")).to_contain_text(
        "Terrain tiles unavailable", timeout=15000
    )


def test_3d_toggle_hides_a_flight(serve_map, page):
    html = flights_to_3d_html(
        [_flight("DJI_0001", 10.0, 20.0, 5), _flight("DJI_0002", 11.0, 21.0, 5)],
        "trip",
    )
    serve_map(html)
    expect(page.locator("#flights-panel")).to_be_visible(timeout=15000)
    page.locator("#flights-panel input[type=checkbox]").first.uncheck()
    assert page.evaluate(
        "() => map.getLayoutProperty('flight-0', 'visibility')"
    ) == "none"
