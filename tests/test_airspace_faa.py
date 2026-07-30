"""FAA UASFM provider tests (#413): bbox hygiene, paging, normalization."""
import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from dji_metadata_embedder.geo.airspace import AirspaceError, SourceInfo
from dji_metadata_embedder.geo.airspace.arcgis_faa import (
    FAA_QUERY_URL,
    fetch_faa_pages,
    parse_faa,
    snap_bbox,
)

FIXTURE = Path(__file__).parent.parent / "samples" / "airspace" / "faa-uasfm.json"
SRC = SourceInfo(
    feed="FAA UAS Facility Maps", url=FAA_QUERY_URL,
    fetched="2026-07-30T12:00:00Z", license="US Gov", caveat="informational",
)


class FakeTransport:
    """urlopen-shaped: records every Request, replays queued bodies."""

    def __init__(self, bodies):
        self.bodies = list(bodies)
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        body = self.bodies.pop(0)
        resp = io.BytesIO(body)
        resp.__enter__ = lambda *a: resp  # type: ignore[method-assign]
        resp.__exit__ = lambda *a: False  # type: ignore[method-assign]
        return resp


def test_snap_bbox_pads_and_snaps_outward_to_a_tenth_degree():
    assert snap_bbox((-73.91, 40.761, -73.87, 40.779)) == (-74.0, 40.7, -73.8, 40.9)


def test_snap_bbox_never_shrinks_a_grid_aligned_box():
    x1, y1, x2, y2 = snap_bbox((-73.9, 40.7, -73.8, 40.8))
    assert x1 <= -73.9 and y1 <= 40.7 and x2 >= -73.8 and y2 >= 40.8


def test_fetch_sends_the_snapped_bbox_and_geojson_params():
    fake = FakeTransport([FIXTURE.read_bytes()])
    fetch_faa_pages((-73.91, 40.761, -73.87, 40.779), fake)
    q = parse_qs(urlparse(fake.requests[0].full_url).query)
    assert q["geometry"] == ["-74.0,40.7,-73.8,40.9"]
    assert q["f"] == ["geojson"]
    assert q["inSR"] == ["4326"]
    assert q["outFields"] == ["*"]


def test_fetch_pages_until_the_transfer_limit_clears():
    fixture_doc = json.loads(FIXTURE.read_text())
    page1 = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [fixture_doc["features"][0]],
            "exceededTransferLimit": True,
        }
    ).encode()
    fake = FakeTransport([page1, FIXTURE.read_bytes()])
    pages = fetch_faa_pages((-73.9, 40.7, -73.8, 40.8), fake)
    assert len(pages) == 2
    q2 = parse_qs(urlparse(fake.requests[1].full_url).query)
    assert q2["resultOffset"] == ["1"]


def test_fetch_raises_when_transfer_limit_is_flagged_on_an_empty_page():
    page1 = json.dumps(
        {"type": "FeatureCollection", "features": [], "exceededTransferLimit": True}
    ).encode()
    fake = FakeTransport([page1])
    with pytest.raises(AirspaceError, match="completeness"):
        fetch_faa_pages((-73.9, 40.7, -73.8, 40.8), fake)


def test_parse_normalizes_cells_with_agl_foot_ceilings():
    zones = parse_faa([FIXTURE.read_bytes()], SRC)
    assert len(zones) == 2
    zero, two_hundred = zones
    assert zero.restriction == "CEILING"
    assert zero.upper is not None and zero.upper.label() == "0 ft AGL"
    assert zero.lower is not None and zero.lower.label() == "0 ft AGL"
    assert two_hundred.upper is not None and two_hundred.upper.value == 200
    assert "LaGuardia" in zero.name
    assert zero.applicability == []
    assert zero.native["MAP_EFF"] == "2026-06-12"


def test_parse_refuses_a_cell_without_a_ceiling():
    doc = json.loads(FIXTURE.read_text())
    del doc["features"][0]["properties"]["CEILING"]
    with pytest.raises(AirspaceError, match="CEILING"):
        parse_faa([json.dumps(doc).encode()], SRC)
