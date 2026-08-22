"""Unit tests for the pure --airspace overlay builder (#413 PR 2)."""
from datetime import datetime
from pathlib import Path

import pytest

from dji_metadata_embedder.geo.airspace.ed269 import ED269_FEEDS, parse_ed269
from dji_metadata_embedder.geo.airspace.ed318 import ED318_FEEDS, parse_ed318
from dji_metadata_embedder.geo.airspace.fetch import AirspaceData
from dji_metadata_embedder.geo.airspace.model import SourceInfo, VerticalLimit, Zone
from dji_metadata_embedder.geo.airspace.overlay import zones_to_overlay_json
from dji_metadata_embedder.geo.track import Track, TrackPoint

SAMPLES = Path(__file__).parent.parent / "samples" / "airspace"


def _lu_zones():
    feed = ED269_FEEDS["LU"]
    source = SourceInfo(
        feed=feed.feed_name, url=feed.url, fetched="2026-07-30T10:00:00Z",
        license=feed.license, caveat=feed.caveat, note=feed.note,
    )
    return parse_ed269((SAMPLES / "ed269-lu.json").read_bytes(), source), source


def _point(lat, lon, second, rel_alt=50.0):
    return TrackPoint(
        lat=lat, lon=lon, alt=300.0, timestamp=f"00:00:{second:02d}",
        utc=datetime(2026, 7, 30, 12, 0, second),
        rel_alt=rel_alt,
    )


def _track_inside(zone, name="LUX0001"):
    """A 3-point track sitting on the vertex-mean of the zone's first ring.
    Self-validating: asserts the point really is inside (guards against a
    concave fixture ring making the whole test vacuous)."""
    from dji_metadata_embedder.geo.airspace.evaluate import point_in_ring

    ring = zone.polygons[0]
    lon = sum(c[0] for c in ring[:-1]) / (len(ring) - 1)
    lat = sum(c[1] for c in ring[:-1]) / (len(ring) - 1)
    assert point_in_ring(lon, lat, ring), "fixture ring is concave; pick a point inside"
    return Track(name=name, points=[
        _point(lat, lon, 0), _point(lat, lon, 1, rel_alt=80.0), _point(lat, lon, 2),
    ])


def _track_far(name="FAR0001"):
    return Track(name=name, points=[_point(49.99, 6.05, s) for s in range(3)])


def test_entered_zone_carries_facts_and_dedupe_merges_tracks():
    zones, source = _lu_zones()
    target = zones[0]
    t1 = _track_inside(target, "LUX0001")
    t2 = _track_inside(target, "LUX0002")
    data = [
        AirspaceData(zones=zones, source=source),
        AirspaceData(zones=list(zones), source=source),  # second fetch, same zones
    ]
    out = zones_to_overlay_json([t1, t2], data)
    assert out["covered"] is True
    # dedupe: each zone appears once even though both tracks fetched it
    ids = [z["id"] for z in out["zones"]]
    assert len(ids) == len(set(ids)) == len(zones)
    entered = [z for z in out["zones"] if z["entered"]]
    hit = next(z for z in entered if z["id"] == target.identifier)
    flights = [e["flight"] for e in hit["entered"]]
    assert flights == ["LUX0001", "LUX0002"]
    e = hit["entered"][0]
    assert e["entry_utc"] == "2026-07-30 12:00:00 UTC"
    assert e["exit_utc"] == "2026-07-30 12:00:02 UTC"
    assert e["max_rel_alt_m"] == 80.0
    assert e["max_amsl_m"] == 300.0
    assert e["time_note"] is None


def test_zone_dict_shape_and_source_footer():
    zones, source = _lu_zones()
    out = zones_to_overlay_json(
        [_track_far()], [AirspaceData(zones=zones, source=source)]
    )
    z = out["zones"][0]
    assert set(z) == {
        "id", "name", "restriction", "lower", "upper", "upper_m", "upper_ref",
        "applicability", "polygons", "holes", "source", "entered",
    }
    assert z["source"] == {
        "feed": source.feed, "license": source.license, "fetched": source.fetched,
    }


def test_missing_limits_stay_none():
    # the FI fixture (verified) carries a zone without a published limit:
    # it must surface as None — the JS renders "not stated", never 0
    feed = ED269_FEEDS["FI"]
    source = SourceInfo(
        feed=feed.feed_name, url=feed.url, fetched="2026-07-30T10:00:00Z",
        license=feed.license, caveat=feed.caveat, note=feed.note,
    )
    zones = parse_ed269((SAMPLES / "ed269-fi.json").read_bytes(), source)
    out = zones_to_overlay_json(
        [_track_far()], [AirspaceData(zones=zones, source=source)]
    )
    assert any(z["upper"] is None or z["lower"] is None for z in out["zones"])


def test_notes_provenance_line_once_and_gap_lines():
    zones, source = _lu_zones()
    data = [
        AirspaceData(zones=zones, source=source),
        AirspaceData(gap_reason="no airspace data available for this location"),
    ]
    out = zones_to_overlay_json([_track_far("A"), _track_far("B")], data)
    assert out["covered"] is True
    provenance = [n for n in out["notes"] if source.feed in n]
    assert provenance == [f"Airspace: {source.feed}, fetched {source.fetched}"]
    assert any(n.startswith("Airspace, B:") for n in out["notes"])


def test_a_dated_product_states_its_effective_date_everywhere():
    # #502: a feed published per cycle (the UK AIRAC dataset) states the
    # cycle's effective date beside the fetch time — in the corner note
    # and in every zone's popup source block — so a reader can tell which
    # cycle the zones reflect, not just when this copy was downloaded.
    zones, source = _lu_zones()
    dated = SourceInfo(
        feed=source.feed, url=source.url, fetched=source.fetched,
        license=source.license, caveat=source.caveat, note=source.note,
        effective="2026-08-06",
    )
    for z in zones:
        z.source = dated
    out = zones_to_overlay_json(
        [_track_far()], [AirspaceData(zones=zones, source=dated)]
    )
    assert (f"Airspace: {dated.feed}, effective 2026-08-06, "
            f"fetched {dated.fetched}") in out["notes"]
    assert all(z["source"]["effective"] == "2026-08-06" for z in out["zones"])
    # Undated feeds keep the old shape: no key invented.
    out = zones_to_overlay_json(
        [_track_far()], [AirspaceData(zones=_lu_zones()[0], source=source)]
    )
    assert all("effective" not in z["source"] for z in out["zones"])


def test_source_note_reaches_the_map_notes_once():
    # #510 I3: the schedule/reference-only disclosures that ride in
    # SourceInfo.note must reach the overlay, not just the record.
    feed = ED318_FEEDS["SE"]
    source = SourceInfo(
        feed=feed.feed_name, url=feed.file_url, fetched="2026-08-19T10:00:00Z",
        license=feed.license, caveat=feed.caveat, note=feed.note,
    )
    zones = parse_ed318((SAMPLES / "ed318-se.json").read_bytes(), source)
    data = [
        AirspaceData(zones=zones, source=source),
        AirspaceData(zones=list(zones), source=source),  # second track, same feed
    ]
    out = zones_to_overlay_json([_track_far("A"), _track_far("B")], data)
    note_lines = [n for n in out["notes"] if n == f"Airspace note: {source.note}"]
    assert note_lines == [f"Airspace note: {source.note}"]


def test_source_without_note_adds_no_note_line():
    zones, source = _lu_zones()
    assert source.note is None
    out = zones_to_overlay_json(
        [_track_far()], [AirspaceData(zones=zones, source=source)]
    )
    assert not any(n.startswith("Airspace note:") for n in out["notes"])


def test_all_gapped_is_not_covered_but_notes_survive():
    out = zones_to_overlay_json(
        [_track_far()], [AirspaceData(gap_reason="reason text")]
    )
    assert out["covered"] is False
    assert out["zones"] == []
    assert out["notes"] == ["Airspace, FAR0001: reason text"]


def test_mtime_time_note_reaches_entered_entries():
    zones, source = _lu_zones()
    target = zones[0]
    t = _track_inside(target)
    t.utc_source = "mtime"
    out = zones_to_overlay_json([t], [AirspaceData(zones=zones, source=source)])
    hit = next(z for z in out["zones"] if z["id"] == target.identifier)
    assert "modification times" in hit["entered"][0]["time_note"]


def test_no_verdict_vocabulary_in_output():
    import json as _json
    zones, source = _lu_zones()
    out = zones_to_overlay_json(
        [_track_inside(zones[0])], [AirspaceData(zones=zones, source=source)]
    )
    blob = _json.dumps(out).lower()
    for banned in ("legal", "compliant", "violation"):  # "legal" subsumes "illegal"
        assert banned not in blob


def test_zone_dicts_carry_numeric_ceilings_for_the_3d_map():
    # #424: ft converts through M_PER_FT, metres pass through,
    # "not stated" stays None (this is what keeps no-ceiling zones flat).
    src = SourceInfo(feed="F", url="u", fetched="t", license="l", caveat="c")

    def zone(upper, ident):
        return Zone(
            identifier=ident, name=ident, restriction="CEILING",
            lower=None, upper=upper, applicability=[],
            polygons=[[(6.0, 49.0), (6.1, 49.0), (6.1, 49.1), (6.0, 49.0)]],
            source=src,
        )

    zones = [
        zone(VerticalLimit(400, "ft", "AGL"), "FT"),
        zone(VerticalLimit(2500, "m", "AMSL"), "M"),
        zone(None, "NONE"),
    ]
    out = zones_to_overlay_json(
        [_track_far()], [AirspaceData(zones=zones, source=src)]
    )
    by_id = {z["id"]: z for z in out["zones"]}
    assert by_id["FT"]["upper_m"] == pytest.approx(400 * 0.3048)
    assert by_id["FT"]["upper_ref"] == "AGL"
    assert by_id["M"]["upper_m"] == 2500.0
    assert by_id["M"]["upper_ref"] == "AMSL"
    assert by_id["NONE"]["upper_m"] is None
    assert by_id["NONE"]["upper_ref"] is None


def test_a_flight_level_ceiling_renders_flat_in_3d_not_100_metres():
    # FL is a pressure datum: converting it to a map height would be
    # false precision, and the ft-else-metres branch would draw a
    # 100 m-tall volume for FL 100.
    from dji_metadata_embedder.geo.airspace.overlay import _upper_numeric
    from dji_metadata_embedder.geo.airspace.model import VerticalLimit
    assert _upper_numeric(VerticalLimit(100.0, "FL", "STD")) == (None, None)
