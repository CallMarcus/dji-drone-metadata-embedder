"""Record content-model tests (#413): three-label heights, honest notes."""
import io
from datetime import datetime
from pathlib import Path
from urllib.error import URLError

from dji_metadata_embedder.geo.record import build_records
from dji_metadata_embedder.geo.track import (
    Track,
    TrackPoint,
    build_track_from_samples,
)
from dji_metadata_embedder.utilities import TelemetrySample

FIXTURES = Path(__file__).parent.parent / "samples" / "airspace"


class FakeTransport:
    """Queued fake HTTP responses. Once exhausted, raises URLError — the
    same failure mode a real dead server produces — so callers that
    degrade network failures into a stated note (terrain.py's TerrainUnavailable)
    exercise that path instead of crashing on a test-only IndexError."""

    def __init__(self, bodies):
        self.bodies = list(bodies)

    def __call__(self, req, timeout=None):
        if not self.bodies:
            raise URLError("no more fake responses queued")
        resp = io.BytesIO(self.bodies.pop(0))
        resp.__enter__ = lambda *a: resp  # type: ignore[method-assign]
        resp.__exit__ = lambda *a: False  # type: ignore[method-assign]
        return resp


def _lux_track():
    pts = [
        TrackPoint(lat=49.615 + i * 0.001, lon=6.19, alt=300 + i, timestamp="c",
                   utc=datetime(2026, 7, 30, 12, i), rel_alt=10.0 * i)
        for i in range(4)
    ]
    return Track(name="LUX0001", points=pts)


def test_records_carry_flight_facts_and_the_eu_measure(tmp_path):
    fake = FakeTransport([(FIXTURES / "ed269-lu.json").read_bytes()])
    rec = build_records([_lux_track()], cache_dir=tmp_path, transport=fake)[0]
    assert rec.name == "LUX0001"
    assert rec.duration_s == 180
    assert rec.takeoff == (49.615, 6.19)
    assert rec.distance_m > 0 and rec.max_home_m > 0
    assert rec.max_rel_alt_m == 30.0
    assert rec.measure_note is not None and "2019/947" in rec.measure_note
    assert rec.airspace.findings  # the CTR fixture zone was entered


def test_terrain_absence_is_a_stated_note_never_a_zero(tmp_path, monkeypatch):
    from dji_metadata_embedder.geo import record as record_mod
    from dji_metadata_embedder.geo.terrain import TerrainUnavailable

    def unavailable(coords, cache_dir, *, transport=None, announce=None):
        raise TerrainUnavailable("the [terrain] extra is not installed")

    monkeypatch.setattr(record_mod, "surface_elevations", unavailable)
    fake = FakeTransport([(FIXTURES / "ed269-lu.json").read_bytes()])
    rec = build_records([_lux_track()], cache_dir=tmp_path, transport=fake)[0]
    assert rec.max_surface_m is None
    assert rec.surface_note is not None and "[terrain]" in rec.surface_note


def test_a_gap_jurisdiction_still_yields_the_logbook_half(tmp_path, monkeypatch):
    from dji_metadata_embedder.geo import record as record_mod
    from dji_metadata_embedder.geo.terrain import TerrainUnavailable

    def unavailable(coords, cache_dir, *, transport=None, announce=None):
        raise TerrainUnavailable("stubbed out")

    monkeypatch.setattr(record_mod, "surface_elevations", unavailable)

    def no_network(req, timeout=None):
        raise AssertionError("a gap flight must not touch the network")

    pts = [TrackPoint(lat=59.33, lon=18.07, alt=50, timestamp="c",
                      utc=datetime(2026, 7, 30, 12, 0), rel_alt=20)]
    rec = build_records([Track(name="SWE", points=pts)], cache_dir=tmp_path,
                        transport=no_network)[0]
    assert rec.airspace.gap_reason is not None
    assert rec.measure_note is None  # no borrowed framing
    assert rec.max_rel_alt_m == 20


def test_a_zero_point_track_yields_no_record_and_an_announce(tmp_path):
    announced = []
    empty = Track(name="EMPTY0001", points=[])
    recs = build_records(
        [empty, _lux_track()],
        cache_dir=tmp_path,
        transport=FakeTransport([(FIXTURES / "ed269-lu.json").read_bytes()]),
        announce=announced.append,
    )
    assert [r.name for r in recs] == ["LUX0001"]
    assert any(
        "EMPTY0001" in msg and "no GPS points" in msg for msg in announced
    )


def test_partial_utc_leaves_time_fields_unstated(tmp_path):
    pts = [
        TrackPoint(lat=49.615 + i * 0.001, lon=6.19, alt=300 + i, timestamp="c",
                   utc=None if i == 1 else datetime(2026, 7, 30, 12, i),
                   rel_alt=10.0 * i)
        for i in range(3)
    ]
    fake = FakeTransport([(FIXTURES / "ed269-lu.json").read_bytes()])
    rec = build_records(
        [Track(name="PARTIAL", points=pts)], cache_dir=tmp_path, transport=fake
    )[0]
    assert rec.start_utc is None
    assert rec.end_utc is None
    assert rec.duration_s == 0.0
    assert rec.time_note is not None and "not stated" in rec.time_note


def test_mtime_synthesized_utc_is_labelled():
    samples = [TelemetrySample(cue="00:00:01,000 --> 00:00:02,000", dt=None,
                               lat=49.6, lon=6.2, alt=100, rel_alt=10)]
    t = build_track_from_samples("x", samples,
                                 mtime_utc=datetime(2026, 7, 30, 12, 0))
    assert t.utc_source == "mtime"


def test_telemetry_utc_is_labelled_as_such():
    samples = [TelemetrySample(cue="00:00:01,000 --> 00:00:02,000",
                               dt=datetime(2026, 7, 30, 14, 0),
                               lat=49.6, lon=6.2, alt=100, rel_alt=10)]
    t = build_track_from_samples("x", samples,
                                 mtime_utc=datetime(2026, 7, 30, 12, 0))
    assert t.utc_source == "telemetry"


def test_the_tracks_local_offset_reaches_the_record(tmp_path):
    from datetime import timedelta

    fake = FakeTransport([(FIXTURES / "ed269-lu.json").read_bytes()])
    track = _lux_track()
    track.local_offset = timedelta(hours=2)
    rec = build_records([track], cache_dir=tmp_path, transport=fake)[0]
    assert rec.local_offset == timedelta(hours=2)
