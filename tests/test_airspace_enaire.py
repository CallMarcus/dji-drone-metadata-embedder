"""ENAIRE (Spain) provider tests (#451) against the cache-shaped fixture."""

import json
from pathlib import Path

import pytest

from dji_metadata_embedder.geo.airspace import AirspaceError, SourceInfo
from dji_metadata_embedder.geo.airspace.enaire import (
    ENAIRE_BASE,
    ENAIRE_FEED,
    ENAIRE_LAYERS,
    parse_enaire,
    query_url,
)

FIXTURES = Path(__file__).parent.parent / "samples" / "airspace"
SRC = SourceInfo(
    feed="test",
    url="https://example.invalid/enaire",
    fetched="2026-10-02T12:00:00Z",
    license="test",
    caveat="informational only",
)


def _body() -> bytes:
    return (FIXTURES / "enaire-es.json").read_bytes()


def _by_id():
    return {z.identifier: z for z in parse_enaire(_body(), SRC)}


def test_parses_the_fixture_into_normalised_zones():
    zones = parse_enaire(_body(), SRC)
    ids = sorted(z.identifier for z in zones)
    # 6 aero features -> 6 zones (T0010 stays two zones); 6 infra features ->
    # 4 zones (INF0224 merged, INF0824 split, INF0524).
    assert len(zones) == 10
    assert "LEBZ45" in ids and "1080-4" in ids and "LEBB2_TMA" in ids
    assert "MUAV151" in ids and "INF0224" in ids and "INF0524" in ids
    assert all(z.restriction in ("REQ_AUTHORISATION", "CONDITIONAL") for z in zones)
    assert not any(z.restriction == "REQ_AUTHORIZATION" for z in zones)


def test_feet_and_amsl_limits_are_kept_as_published():
    by = _by_id()
    rvf = by["1080-4"]
    assert rvf.upper is not None and rvf.upper.label() == "3000 ft AGL"
    assert rvf.lower is not None and rvf.lower.label() == "0 ft AGL"
    tma = by["LEBB2_TMA"]
    assert tma.lower is not None and tma.lower.label() == "2896 m AMSL"
    assert tma.upper is not None and tma.upper.label() == "4420 m AMSL"


def test_holes_and_multipolygons_keep_their_geometry():
    by = _by_id()
    assert len(by["LEBZ45"].polygons) == 1 and len(by["LEBZ45"].holes) == 1
    assert len(by["MUAV151"].polygons) == 2


def test_pieces_sharing_identifier_and_attributes_merge_into_one_zone():
    by = _by_id()
    adif = by["INF0224"]
    assert len(adif.polygons) == 3
    assert adif.restriction == "CONDITIONAL"
    assert adif.name == "INF0224"  # the layer publishes no name for these pieces
    assert adif.upper is not None and adif.upper.label() == "120 m AGL"
    assert isinstance(adif.native, dict) and len(adif.native["pieces"]) == 3


def test_different_zones_under_one_identifier_get_a_stable_suffix():
    zones = parse_enaire(_body(), SRC)
    t0010 = [z for z in zones if z.identifier.startswith("T0010")]
    assert len(t0010) == 2
    assert {z.name for z in t0010} == {"Santa Comba", "Alcocer de Planes"}
    assert all(
        z.identifier != "T0010" and z.identifier.startswith("T0010 [") for z in t0010
    )
    inf = [z for z in zones if z.identifier.startswith("INF0824")]
    assert len(inf) == 2 and len({z.identifier for z in inf}) == 2
    # Deterministic across parses (cache stability).
    again = {z.identifier for z in parse_enaire(_body(), SRC)}
    assert {z.identifier for z in zones} == again


def test_notes_carry_the_subtype_and_the_message_without_markup():
    by = _by_id()
    z = by["LEBZ45"]
    assert z.notes[0] == "Aeródromo"
    assert any("Zona geográfica de UAS" in n for n in z.notes)
    assert not any("<" in n for n in z.notes)
    assert z.applicability == []  # the service publishes no windows today


def _one(props: dict, geometry: dict | None = None) -> bytes:
    geometry = geometry or {
        "type": "Polygon",
        "coordinates": [[[-3.7, 40.4], [-3.6, 40.4], [-3.6, 40.5], [-3.7, 40.4]]],
    }
    feat = {"type": "Feature", "properties": props, "geometry": geometry}
    return json.dumps(
        {"layers": {"2": [{"type": "FeatureCollection", "features": [feat]}]}}
    ).encode()


def test_the_services_three_spellings_of_empty_mean_not_stated():
    base = {"identifier": "X1", "type": "REQ_AUTHORIZATION", "GFID": "{ABCDEF12-0}"}
    for empty in ("", "None", None):
        z = parse_enaire(
            _one({**base, "lower": empty, "upper": empty, "name": empty}), SRC
        )[0]
        assert z.lower is None and z.upper is None and z.name == "X1" and z.notes == []


def test_malformed_zones_invalidate_the_document():
    with pytest.raises(AirspaceError, match="missing identifier"):
        parse_enaire(_one({"type": "REQ_AUTHORIZATION"}), SRC)
    with pytest.raises(AirspaceError, match="missing restriction type"):
        parse_enaire(_one({"identifier": "X1", "type": ""}), SRC)
    with pytest.raises(AirspaceError, match="not a number"):
        parse_enaire(
            _one(
                {
                    "identifier": "X1",
                    "type": "CONDITIONAL",
                    "lower": "ten",
                    "lowerReference": "AGL",
                }
            ),
            SRC,
        )
    with pytest.raises(AirspaceError, match="not supported"):
        parse_enaire(
            _one(
                {"identifier": "X1", "type": "CONDITIONAL"},
                {"type": "Point", "coordinates": [-3.7, 40.4]},
            ),
            SRC,
        )
    with pytest.raises(AirspaceError, match="no 'layers' object"):
        parse_enaire(b'{"features": []}', SRC)
    with pytest.raises(AirspaceError, match="not JSON"):
        parse_enaire(b"<html>", SRC)


def test_a_window_when_the_service_publishes_one():
    z = parse_enaire(
        _one(
            {
                "identifier": "X1",
                "type": "CONDITIONAL",
                "startDateTime": "2026-10-01T06:00:00",
                "endDateTime": "2026-10-01T18:00:00",
            }
        ),
        SRC,
    )[0]
    assert len(z.applicability) == 1 and z.applicability[0].permanent is False


def test_query_url_targets_the_v2_service_with_the_bbox_and_geojson():
    url = query_url(2, (-3.8, 40.3, -3.6, 40.5), 0)
    assert url.startswith(ENAIRE_BASE + "/2/query?")
    assert "geometry=-3.8%2C40.3%2C-3.6%2C40.5" in url
    assert "f=geojson" in url and "resultOffset" not in url
    assert "resultOffset=1000" in query_url(0, (-3.8, 40.3, -3.6, 40.5), 1000)
    assert ENAIRE_LAYERS == (2, 0)
    assert "ENAIRE" in ENAIRE_FEED.license and "caso 44348" in ENAIRE_FEED.license
    assert "Urbano" in (ENAIRE_FEED.note or "")
