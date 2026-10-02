"""dipul (Germany) provider tests (#593) against the cache-shaped fixture."""

import io
import json
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError

import pytest

from dji_metadata_embedder.geo.airspace import AirspaceError, SourceInfo
from dji_metadata_embedder.geo.airspace.dipul import (
    DIPUL_FEED,
    DIPUL_LAYERS,
    DIPUL_WFS,
    fetch_dipul_body,
    parse_dipul,
    query_url,
)

FIXTURES = Path(__file__).parent.parent / "samples" / "airspace"
SRC = SourceInfo(
    feed="test",
    url="https://example.invalid/dipul",
    fetched="2026-10-02T12:00:00Z",
    license="test",
    caveat="informational only",
)


class FakeTransport:
    def __init__(self, bodies):
        self.bodies = list(bodies)
        self.urls = []

    def __call__(self, req, timeout=None):
        self.urls.append(req.full_url)
        resp = io.BytesIO(self.bodies.pop(0))
        resp.__enter__ = lambda *a: resp  # type: ignore[method-assign]
        resp.__exit__ = lambda *a: False  # type: ignore[method-assign]
        return resp


def _body() -> bytes:
    return (FIXTURES / "dipul-de.json").read_bytes()


def _zones():
    return parse_dipul(_body(), SRC)


def test_the_registry_lists_all_31_layers_with_dipul_titles():
    assert len(DIPUL_LAYERS) == 31
    assert DIPUL_LAYERS["polizei"] == "Liegenschaften der Polizei"
    assert (
        DIPUL_LAYERS["temporaere_betriebseinschraenkungen"]
        == "Temporäre Betriebseinschränkungen"
    )
    assert "dipul, CC-BY-ND 4.0" in DIPUL_FEED.license
    assert "28-day" in (DIPUL_FEED.note or "")


def test_parses_the_fixture_into_one_zone_per_feature():
    zones = _zones()
    assert len(zones) == 12
    assert len({z.identifier for z in zones}) == 12
    assert all(":" in z.identifier for z in zones)
    assert all(z.polygons for z in zones)


def test_restriction_classes_follow_the_legal_basis_and_type_code():
    by_layer = {}
    for z in _zones():
        by_layer.setdefault(z.identifier.split(":")[0], []).append(z)
    assert {z.restriction for z in by_layer["bahnanlagen"]} == {"CONDITIONAL"}
    assert {z.restriction for z in by_layer["kontrollzonen"]} == {"CONDITIONAL"}
    assert {z.restriction for z in by_layer["flugbeschraenkungsgebiete"]} == {
        "REQ_AUTHORISATION"
    }
    assert {z.restriction for z in by_layer["temporaere_betriebseinschraenkungen"]} == {
        "PROHIBITED"
    }


def test_limits_keep_units_and_map_datums():
    zones = _zones()
    ctr = next(z for z in zones if z.identifier.startswith("kontrollzonen:"))
    assert (
        ctr.upper is not None
        and ctr.upper.unit == "ft"
        and ctr.upper.reference == "AMSL"
    )
    assert ctr.lower is not None and ctr.lower.reference == "AMSL"
    fl = next(
        z
        for z in zones
        if z.identifier.startswith("flugbeschraenkungsgebiete:")
        and z.upper is not None
        and z.upper.unit == "FL"
    )
    assert fl.upper.reference == "STD" and fl.upper.label().startswith("FL ")
    rail = next(z for z in zones if z.identifier.startswith("bahnanlagen:"))
    assert (
        rail.upper is None
        and rail.lower is not None
        and rail.lower.label() == "0 m AGL"
    )
    tmp = next(
        z
        for z in zones
        if z.identifier.startswith("temporaere_betriebseinschraenkungen:")
    )
    assert tmp.lower is not None and tmp.lower.unit == "m"  # published as "M"


def test_temporary_restrictions_carry_their_window():
    tmp = next(
        z
        for z in _zones()
        if z.identifier.startswith("temporaere_betriebseinschraenkungen:")
    )
    assert len(tmp.applicability) == 1
    win = tmp.applicability[0]
    assert (
        win.permanent is False
        and isinstance(win.start, datetime)
        and isinstance(win.end, datetime)
    )
    rail = next(z for z in _zones() if z.identifier.startswith("bahnanlagen:"))
    assert rail.applicability == []


def test_notes_carry_dipul_category_legal_ref_and_type_code_verbatim():
    heli = next(z for z in _zones() if z.identifier.startswith("flugplaetze:"))
    assert heli.notes[0] == "Flugplätze"
    assert any(n.startswith("§ 21h, Abs. 3 (1.) LuftVO") for n in heli.notes)
    assert any(n.startswith("FLUGPLATZ") and " / " in n for n in heli.notes)
    embassy = next(
        z for z in _zones() if z.identifier.startswith("diplomatische_vertretungen:")
    )
    assert embassy.notes[0] == "Diplomatische und konsularische Vertretungen"
    assert embassy.name and embassy.name == embassy.native["properties"]["name"]


def _one(layer: str, props: dict, geometry: dict | None = None) -> bytes:
    geometry = geometry or {
        "type": "Polygon",
        "coordinates": [[[13.4, 52.5], [13.41, 52.5], [13.41, 52.51], [13.4, 52.5]]],
    }
    feat = {
        "type": "Feature",
        "id": f"{layer}.1",
        "properties": props,
        "geometry": geometry,
    }
    return json.dumps(
        {
            "layers": {
                f"dipul:{layer}": [{"type": "FeatureCollection", "features": [feat]}]
            }
        }
    ).encode()


BASE = {
    "external_reference": "abc",
    "name": "X",
    "legal_ref": "§ 21h, Abs. 3 (5.) LuftVO",
    "type_code": "BAHNANLAGE",
    "lower_limit_altitude": "0",
    "lower_limit_unit": "m",
    "lower_limit_alt_ref": "AGL",
}


def test_unknown_legal_basis_keeps_the_published_type_code_as_the_label():
    z = parse_dipul(
        _one(
            "bahnanlagen",
            {**BASE, "legal_ref": "§ 99 Phantasie", "type_code": "NEUARTIG"},
        ),
        SRC,
    )[0]
    assert z.restriction == "NEUARTIG"


def test_missing_external_reference_or_unknown_unit_is_an_error():
    with pytest.raises(AirspaceError, match="external_reference"):
        parse_dipul(_one("bahnanlagen", {**BASE, "external_reference": ""}), SRC)
    with pytest.raises(AirspaceError, match="unit"):
        parse_dipul(_one("bahnanlagen", {**BASE, "lower_limit_unit": "yards"}), SRC)
    with pytest.raises(AirspaceError, match="alt_ref"):
        parse_dipul(_one("bahnanlagen", {**BASE, "lower_limit_alt_ref": "WGS"}), SRC)
    with pytest.raises(AirspaceError, match="not supported"):
        parse_dipul(
            _one("bahnanlagen", BASE, {"type": "Point", "coordinates": [13.4, 52.5]}),
            SRC,
        )
    with pytest.raises(AirspaceError, match="no 'layers' object"):
        parse_dipul(b'{"features": []}', SRC)


def test_an_unknown_layer_in_the_body_is_an_error():
    with pytest.raises(AirspaceError, match="not a dipul layer"):
        parse_dipul(_one("ufo_landeplaetze", BASE), SRC)


def test_query_url_uses_wfs_axis_order_and_paging():
    url = query_url("bahnanlagen", (13.3, 52.4, 13.5, 52.6), 0)
    assert url.startswith(DIPUL_WFS + "?")
    assert "typeNames=dipul%3Abahnanlagen" in url
    assert "bbox=52.4%2C13.3%2C52.6%2C13.5" in url  # lat,lon order
    assert "count=1000" in url and "startIndex" not in url
    assert "startIndex=1000" in query_url("bahnanlagen", (13.3, 52.4, 13.5, 52.6), 1000)


def _page(n, total):
    return json.dumps(
        {
            "type": "FeatureCollection",
            "totalFeatures": total,
            "numberReturned": n,
            "features": [{"type": "Feature", "properties": {"i": k}} for k in range(n)],
        }
    ).encode()


BB = (13.3, 52.4, 13.5, 52.6)


def test_fetch_body_queries_every_layer_once_and_pages_by_start_index():
    bodies = [_page(1000, 1005), _page(5, 1005)] + [_page(0, 0)] * 30
    fake = FakeTransport(bodies)
    body = fetch_dipul_body(BB, fake)
    assert len(fake.urls) == 32
    assert "startIndex=1000" in fake.urls[1]
    doc = json.loads(body)
    assert len(doc["layers"]) == 31
    first = next(iter(doc["layers"].values()))
    assert sum(len(p["features"]) for p in first) == 1005


def test_fetch_body_stops_after_exactly_one_full_page_when_total_matches():
    fake = FakeTransport([_page(1000, 1000)] + [_page(0, 0)] * 30)
    fetch_dipul_body(BB, fake)
    assert len(fake.urls) == 31


def test_fetch_body_continues_when_the_server_caps_pages_below_1000():
    fake = FakeTransport(
        [_page(500, 1200), _page(500, 1200), _page(200, 1200)] + [_page(0, 0)] * 30
    )
    body = fetch_dipul_body(BB, fake)
    assert len(fake.urls) == 33
    assert "startIndex" not in fake.urls[0]
    assert "startIndex=500" in fake.urls[1]
    assert "startIndex=1000" in fake.urls[2]
    first = next(iter(json.loads(body)["layers"].values()))
    assert sum(len(p["features"]) for p in first) == 1200


def test_fetch_body_refuses_a_response_without_a_total():
    page = json.dumps({"features": []}).encode()
    with pytest.raises(AirspaceError, match="no totalFeatures"):
        fetch_dipul_body(BB, FakeTransport([page]))


def test_fetch_body_refuses_a_short_page_set():
    bodies = [_page(1000, 1005), _page(0, 1005)] + [_page(0, 0)] * 30
    with pytest.raises(AirspaceError, match="incomplete"):
        fetch_dipul_body(BB, FakeTransport(bodies))


def test_fetch_body_cannot_spin_on_a_server_that_ignores_start_index():
    bodies = [_page(1000, 1005)] * 200
    with pytest.raises(AirspaceError, match="did not converge"):
        fetch_dipul_body(BB, FakeTransport(bodies))


def test_fetch_body_raises_on_http_error():
    def transport(req, timeout=None):
        raise HTTPError(req.full_url, 503, "unavailable", {}, None)  # type: ignore[arg-type]

    with pytest.raises(AirspaceError, match="answered HTTP 503"):
        fetch_dipul_body(BB, transport)


def test_a_duplicate_identifier_in_one_body_is_an_error():
    doc = json.loads(_one("bahnanlagen", BASE))
    page = doc["layers"]["dipul:bahnanlagen"][0]
    page["features"].append(page["features"][0])
    with pytest.raises(AirspaceError, match="not unique"):
        parse_dipul(json.dumps(doc).encode(), SRC)


def test_a_multipolygon_hole_stays_with_its_own_part():
    outer1 = [[13.0, 52.0], [13.1, 52.0], [13.1, 52.1], [13.0, 52.0]]
    hole = [[13.02, 52.02], [13.05, 52.02], [13.05, 52.05], [13.02, 52.02]]
    outer2 = [[13.2, 52.0], [13.3, 52.0], [13.3, 52.1], [13.2, 52.0]]
    z = parse_dipul(
        _one(
            "bahnanlagen",
            BASE,
            {"type": "MultiPolygon", "coordinates": [[outer1, hole], [outer2]]},
        ),
        SRC,
    )[0]
    assert len(z.polygons) == 2
    assert len(z.holes) == 1  # the flat union, for older consumers
    # #593: the hole belongs to the first part only, never to the second.
    assert z.part_holes == [
        [[(13.02, 52.02), (13.05, 52.02), (13.05, 52.05), (13.02, 52.02)]],
        [],
    ]


def test_an_altitude_with_no_unit_is_an_error():
    props = {**BASE}
    del props["lower_limit_unit"]
    with pytest.raises(AirspaceError, match="unit"):
        parse_dipul(_one("bahnanlagen", props), SRC)


def test_a_json_number_limit_parses_to_a_float_label():
    z = parse_dipul(_one("bahnanlagen", {**BASE, "lower_limit_altitude": 100.5}), SRC)[
        0
    ]
    assert z.lower is not None
    assert z.lower.value == 100.5
    assert "100.5" in z.lower.label()


def test_neither_legal_ref_nor_type_code_is_an_error_not_a_guess():
    props = {**BASE, "legal_ref": "", "type_code": ""}
    with pytest.raises(AirspaceError, match="no legal_ref or type_code"):
        parse_dipul(_one("bahnanlagen", props), SRC)


def test_fetch_body_raises_on_a_maintenance_page():
    bodies = [_page(0, 0)] * 3 + [b"<html>maintenance</html>"]
    with pytest.raises(AirspaceError, match="not JSON"):
        fetch_dipul_body((13.3, 52.4, 13.5, 52.6), FakeTransport(bodies))


def test_legal_bases_match_as_whole_references_not_prefixes():
    def restriction(legal):
        props = {**BASE, "legal_ref": legal, "type_code": "NEUARTIG"}
        return parse_dipul(_one("bahnanlagen", props), SRC)[0].restriction

    assert restriction("§ 17, Abs. 1 LuftVO") == "REQ_AUTHORISATION"
    assert restriction("§ 21h, Abs. 3 LuftVO") == "CONDITIONAL"
    assert restriction("§ 170 LuftVO") == "NEUARTIG"
    assert restriction("§ 17a LuftVO") == "NEUARTIG"
    assert restriction("§ 21hx LuftVO") == "NEUARTIG"


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", float("inf")])
def test_a_non_finite_limit_is_an_error(bad):
    with pytest.raises(AirspaceError, match="is not finite"):
        parse_dipul(_one("bahnanlagen", {**BASE, "lower_limit_altitude": bad}), SRC)
