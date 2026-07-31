"""Evaluator tests (#413): pure geometry + windows + dwell maxima."""
from datetime import datetime

from dji_metadata_embedder.geo.airspace import (
    Applicability,
    SourceInfo,
    VerticalLimit,
    Zone,
)
from dji_metadata_embedder.geo.airspace.evaluate import evaluate, point_in_ring
from dji_metadata_embedder.geo.track import Track, TrackPoint

SRC = SourceInfo(
    feed="test", url="u", fetched="2026-07-30T12:00:00Z",
    license="CC0", caveat="informational",
)
SQUARE = [(6.0, 49.0), (6.2, 49.0), (6.2, 49.2), (6.0, 49.2), (6.0, 49.0)]


def _zone(**over):
    base = dict(
        identifier="Z1", name="Zone 1", restriction="REQ_AUTHORISATION",
        lower=VerticalLimit(0, "m", "AGL"), upper=VerticalLimit(120, "m", "AGL"),
        applicability=[], polygons=[SQUARE], source=SRC, native={},
    )
    base.update(over)
    return Zone(**base)


def _pt(lat, lon, minute, rel=50.0, alt=300.0):
    return TrackPoint(
        lat=lat, lon=lon, alt=alt, timestamp="c",
        utc=datetime(2026, 7, 30, 12, minute), rel_alt=rel,
    )


def test_point_in_ring_basics():
    assert point_in_ring(6.1, 49.1, SQUARE)
    assert not point_in_ring(6.3, 49.1, SQUARE)


def test_an_entered_zone_carries_entry_exit_and_dwell_maxima():
    track = Track(name="t", points=[
        _pt(48.9, 6.1, 0, rel=10, alt=250),   # outside
        _pt(49.1, 6.1, 1, rel=80, alt=330),   # inside
        _pt(49.15, 6.1, 2, rel=95, alt=345),  # inside, the maxima
        _pt(49.3, 6.1, 3, rel=120, alt=370),  # outside again (higher, ignored)
    ])
    report = evaluate(track, [_zone()], surface_heights_m=[12.0, 81.0, 96.5, 130.0])
    f = report.findings[0]
    assert f.entered
    assert f.entry_utc == datetime(2026, 7, 30, 12, 1)
    assert f.exit_utc == datetime(2026, 7, 30, 12, 2)
    assert f.max_rel_alt_m == 95
    assert f.max_surface_m == 96.5
    assert f.max_amsl_m == 345


def test_a_missed_zone_reports_not_entered():
    track = Track(name="t", points=[_pt(48.5, 5.0, 0)])
    f = evaluate(track, [_zone()], surface_heights_m=None).findings[0]
    assert not f.entered and f.entry_utc is None and f.max_surface_m is None


def test_zones_outside_the_flight_window_land_in_not_applicable():
    later = _zone(identifier="Z2", applicability=[
        Applicability(datetime(2026, 8, 1, 6), datetime(2026, 8, 1, 18), False)
    ])
    track = Track(name="t", points=[_pt(49.1, 6.1, 0)])
    report = evaluate(track, [_zone(), later], surface_heights_m=None)
    assert [f.zone.identifier for f in report.findings] == ["Z1"]
    assert [z.identifier for z in report.not_applicable] == ["Z2"]


def test_a_window_overlapping_the_flight_stays_applicable():
    overlapping = _zone(applicability=[
        Applicability(datetime(2026, 7, 30, 11), datetime(2026, 7, 30, 13), False)
    ])
    track = Track(name="t", points=[_pt(49.1, 6.1, 0)])
    assert evaluate(track, [overlapping], surface_heights_m=None).findings


def test_missing_point_utc_keeps_timed_zones_visible():
    timed = _zone(applicability=[
        Applicability(datetime(2030, 1, 1), datetime(2030, 1, 2), False)
    ])
    p = TrackPoint(lat=49.1, lon=6.1, alt=300, timestamp="c", utc=None)
    report = evaluate(Track(name="t", points=[p]), [timed], surface_heights_m=None)
    assert report.findings  # shown, never hidden, when time is uncertain


def test_a_zero_dwell_maximum_is_not_overwritten_by_a_lower_negative_value():
    # regression: `max(x or float("-inf"), ...)` treats a true 0.0 max as
    # falsy and lets a later, lower value overwrite it.
    track = Track(name="t", points=[
        _pt(49.1, 6.1, 0, rel=0.0, alt=0.0),
        _pt(49.1, 6.1, 1, rel=-5.0, alt=-5.0),
    ])
    report = evaluate(track, [_zone()], surface_heights_m=[0.0, -5.0])
    f = report.findings[0]
    assert f.max_rel_alt_m == 0.0
    assert f.max_surface_m == 0.0
    assert f.max_amsl_m == 0.0


def test_reentering_a_zone_reports_one_spanning_entry_exit_window():
    track = Track(name="t", points=[
        _pt(49.1, 6.1, 0, rel=10, alt=300),   # enters
        _pt(49.1, 6.1, 1, rel=20, alt=310),   # still inside
        _pt(48.5, 5.0, 2, rel=999, alt=999),  # outside (higher, excluded)
        _pt(49.1, 6.1, 4, rel=30, alt=320),   # re-enters
    ])
    report = evaluate(track, [_zone()], surface_heights_m=None)
    f = report.findings[0]
    assert f.entry_utc == datetime(2026, 7, 30, 12, 0)
    assert f.exit_utc == datetime(2026, 7, 30, 12, 4)
    assert f.max_rel_alt_m == 30
    assert f.max_amsl_m == 320


def test_mismatched_surface_heights_length_raises():
    track = Track(name="t", points=[_pt(49.1, 6.1, 0), _pt(49.1, 6.1, 1)])
    try:
        evaluate(track, [_zone()], surface_heights_m=[1.0])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "1" in str(e) and "2" in str(e)


# #422: the parsers keep interior rings (holes) in Zone.holes; a point in
# any exterior ring counts unless a hole subtracts it. Plain even-odd
# parity across a flat ring list was rejected in review: it under-reports
# for overlapping same-limit volumes, the direction a record must never
# fail in.
HOLE = [(6.05, 49.05), (6.15, 49.05), (6.15, 49.15), (6.05, 49.15),
        (6.05, 49.05)]


def test_a_point_inside_an_interior_ring_is_not_entered():
    donut = _zone(polygons=[SQUARE], holes=[HOLE])
    track = Track(name="t", points=[_pt(49.1, 6.1, 0)])  # inside the hole
    report = evaluate(track, [donut], surface_heights_m=None)
    assert not report.findings[0].entered


def test_a_point_between_outer_ring_and_hole_is_entered():
    donut = _zone(polygons=[SQUARE], holes=[HOLE])
    track = Track(name="t", points=[_pt(49.175, 6.1, 0)])  # the donut band
    report = evaluate(track, [donut], surface_heights_m=None)
    assert report.findings[0].entered


def test_two_disjoint_polygons_both_count_as_the_zone():
    second = [(7.0, 50.0), (7.2, 50.0), (7.2, 50.2), (7.0, 50.2), (7.0, 50.0)]
    z = _zone(polygons=[SQUARE, second])
    track = Track(name="t", points=[_pt(50.1, 7.1, 0)])  # in the second only
    assert evaluate(track, [z], surface_heights_m=None).findings[0].entered


def test_a_point_inside_two_overlapping_volumes_is_entered():
    # Review regression pin: a zone published as overlapping same-limit
    # volumes must not cancel itself out for a point in the overlap.
    overlapping = [(6.1, 49.1), (6.3, 49.1), (6.3, 49.3), (6.1, 49.3),
                   (6.1, 49.1)]
    z = _zone(polygons=[SQUARE, overlapping])
    track = Track(name="t", points=[_pt(49.15, 6.15, 0)])  # in both
    assert evaluate(track, [z], surface_heights_m=None).findings[0].entered


def test_a_duplicated_exterior_ring_still_counts():
    z = _zone(polygons=[SQUARE, SQUARE])  # a feed repeating geometry
    track = Track(name="t", points=[_pt(49.1, 6.1, 0)])
    assert evaluate(track, [z], surface_heights_m=None).findings[0].entered
