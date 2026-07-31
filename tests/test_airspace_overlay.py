"""Unit tests for the pure --airspace overlay builder (#413 PR 2)."""
from datetime import datetime
from pathlib import Path

from dji_metadata_embedder.geo.airspace.ed269 import ED269_FEEDS, parse_ed269
from dji_metadata_embedder.geo.airspace.fetch import AirspaceData
from dji_metadata_embedder.geo.airspace.model import SourceInfo
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
        "id", "name", "restriction", "lower", "upper", "applicability",
        "polygons", "holes", "source", "entered",
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
