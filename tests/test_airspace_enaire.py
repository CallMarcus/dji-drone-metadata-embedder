"""ENAIRE (Spain) provider tests (#451) against the cache-shaped fixture."""

import json
import os
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
from dji_metadata_embedder.geo.airspace.evaluate import evaluate
from dji_metadata_embedder.geo.track import Track, TrackPoint

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
    assert by["LEBZ45"].part_holes == [by["LEBZ45"].holes]
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


def _many(*props_list: dict) -> bytes:
    geom = {
        "type": "Polygon",
        "coordinates": [[[-3.7, 40.4], [-3.6, 40.4], [-3.6, 40.5], [-3.7, 40.4]]],
    }
    feats = [{"type": "Feature", "properties": p, "geometry": geom} for p in props_list]
    return json.dumps(
        {"layers": {"2": [{"type": "FeatureCollection", "features": feats}]}}
    ).encode()


def test_split_zones_without_a_guid_cannot_be_told_apart():
    base = {"identifier": "X1", "type": "CONDITIONAL"}
    with pytest.raises(AirspaceError, match="tell them apart"):
        parse_enaire(_many({**base, "name": "A"}, {**base, "name": "B"}), SRC)


def test_pieces_with_different_windows_stay_separate_zones():
    base = {
        "identifier": "X1",
        "type": "CONDITIONAL",
        "name": "A",
        "lower": 0,
        "lowerReference": "AGL",
    }
    zones = parse_enaire(
        _many(
            {**base, "GFID": "{AAAA0001-0}", "startDateTime": "2026-10-01T06:00:00"},
            {**base, "GFID": "{BBBB0002-0}", "startDateTime": "2026-10-02T06:00:00"},
        ),
        SRC,
    )
    assert len(zones) == 2
    assert all(z.identifier.startswith("X1 [") for z in zones)


def test_suffix_of_a_merged_zone_is_its_smallest_guid_in_any_order():
    base = {"identifier": "X1", "type": "CONDITIONAL"}
    a1 = {**base, "name": "A", "GFID": "{CCCC0003}"}
    a2 = {**base, "name": "A", "GFID": "{AAAA0001}"}
    b = {**base, "name": "B", "GFID": "{BBBB0002}"}
    seen = []
    for order in ((a1, a2, b), (b, a2, a1), (a2, b, a1)):
        zones = parse_enaire(_many(*order), SRC)
        assert len(zones) == 2
        seen.append({z.name: z.identifier for z in zones})
    assert seen[0] == {"A": "X1 [AAAA0001]", "B": "X1 [BBBB0002]"}
    assert seen[0] == seen[1] == seen[2]


def test_identifier_less_features_get_a_synthesised_id():
    z = parse_enaire(
        _one(
            {
                "identifier": "",
                "name": "",
                "type": "REQ_AUTHORIZATION",
                "extendedProperties": "ENR_5_5",
                "GFID": "{8FA678F7-1111-2222}",
            }
        ),
        SRC,
    )
    assert [x.identifier for x in z] == ["ENR_5_5 [8FA678F7]"]
    # Without a subtype the id still carries the GUID.
    z = parse_enaire(
        _one({"type": "REQ_AUTHORIZATION", "OBJECTID": 1445}),
        SRC,
    )
    assert z[0].identifier == "zone [1445]"


def _ring(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


def _entered(zone, lon, lat):
    pt = TrackPoint(lat=lat, lon=lon, alt=0.0, timestamp="00:00:00,000")
    return evaluate(Track(name="t", points=[pt]), [zone]).findings[0].entered


def test_a_holed_piece_merges_and_keeps_its_hole_on_its_own_part():
    # Holes ride per part (Zone.part_holes, #593), so a holed piece merges
    # with a same-attribute piece lying inside its hole: the hole cuts only
    # its own piece, and the island still counts.
    base = {"identifier": "X1", "type": "CONDITIONAL", "name": "A"}
    outer = {
        "type": "Polygon",
        "coordinates": [_ring(0, 0, 10, 10), _ring(4, 4, 6, 6)],
    }
    inner = {"type": "Polygon", "coordinates": [_ring(4.5, 4.5, 5.5, 5.5)]}
    feats = [
        {
            "type": "Feature",
            "properties": {**base, "GFID": "{AAAA0001}"},
            "geometry": outer,
        },
        {
            "type": "Feature",
            "properties": {**base, "GFID": "{BBBB0002}"},
            "geometry": inner,
        },
    ]
    for order in (feats, feats[::-1]):
        body = json.dumps(
            {"layers": {"2": [{"type": "FeatureCollection", "features": order}]}}
        ).encode()
        zones = parse_enaire(body, SRC)
        assert len(zones) == 1
        z = zones[0]
        assert z.identifier == "X1"
        assert z.part_holes is not None
        assert len(z.polygons) == len(z.part_holes) == 2
        assert len(z.holes) == 1
        # The hole is aligned with the outer piece, wherever it sits.
        holed = [i for i, part in enumerate(z.part_holes) if part]
        assert len(holed) == 1 and z.polygons[holed[0]][0] == (0.0, 0.0)
        assert _entered(z, 5, 5)  # on the island inside the hole
        assert not _entered(z, 4.2, 4.2)  # in the hole, off the island
        assert _entered(z, 1, 1)  # the outer ring clear of the hole


def test_a_truncated_trailing_tag_is_dropped_from_notes():
    z = parse_enaire(
        _one(
            {
                "identifier": "X1",
                "type": "CONDITIONAL",
                "message": "<p>Contacte <a href='x",
            }
        ),
        SRC,
    )[0]
    assert z.notes == ["Contacte"]


# A whole live Aero layer, when a maintainer points at a local download
# (DJIEMBED_ENAIRE_AERO_SAMPLE=/path/to/aero.json); never present in CI.
LIVE_AERO = Path(os.environ.get("DJIEMBED_ENAIRE_AERO_SAMPLE", ""))


@pytest.mark.skipif(
    not LIVE_AERO.is_file(),
    reason="set DJIEMBED_ENAIRE_AERO_SAMPLE to a live Aero download",
)
def test_the_whole_live_aero_layer_parses():
    doc = json.loads(LIVE_AERO.read_text(encoding="utf-8"))
    zones = parse_enaire(json.dumps({"layers": {"2": [doc]}}).encode(), SRC)
    assert len(zones) > 1400


def test_unknown_uom_is_an_error():
    with pytest.raises(AirspaceError, match="uom 'FL' is not supported"):
        parse_enaire(
            _one(
                {
                    "identifier": "X1",
                    "type": "CONDITIONAL",
                    "upper": 100,
                    "upperReference": "AMSL",
                    "uom": "FL",
                }
            ),
            SRC,
        )


def test_a_duplicate_zone_id_after_splitting_is_an_error():
    # Two different zones under one identifier whose GUIDs share the same
    # 8-character prefix would collide on the suffix; the overlay would
    # drop one, so the parser refuses instead.
    body = json.dumps(
        {
            "layers": {
                "2": [
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {
                                    "identifier": "X1",
                                    "name": "A",
                                    "type": "CONDITIONAL",
                                    "GFID": "{ABCDEF12-1111}",
                                },
                                "geometry": {
                                    "type": "Polygon",
                                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
                                },
                            },
                            {
                                "type": "Feature",
                                "properties": {
                                    "identifier": "X1",
                                    "name": "B",
                                    "type": "CONDITIONAL",
                                    "GFID": "{ABCDEF12-2222}",
                                },
                                "geometry": {
                                    "type": "Polygon",
                                    "coordinates": [[[2, 2], [3, 2], [3, 3], [2, 2]]],
                                },
                            },
                        ],
                    }
                ]
            }
        }
    ).encode()
    with pytest.raises(AirspaceError, match="not unique"):
        parse_enaire(body, SRC)


def test_prose_with_a_lone_less_than_sign_survives_tag_trimming():
    z = parse_enaire(
        _one(
            {
                "identifier": "X1",
                "type": "CONDITIONAL",
                "message": "vuele a altura < 120 m",
            }
        ),
        SRC,
    )[0]
    assert z.notes == ["vuele a altura < 120 m"]
