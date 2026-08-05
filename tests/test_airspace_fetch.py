"""Fetch orchestration tests (#413): consent lines, cache, honest gaps."""
import io
from datetime import datetime
from pathlib import Path

from dji_metadata_embedder.geo.airspace.fetch import fetch_zones
from dji_metadata_embedder.geo.track import Track, TrackPoint

FIXTURES = Path(__file__).parent.parent / "samples" / "airspace"


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


def _track(lat, lon):
    return Track(name="t", points=[
        TrackPoint(lat=lat, lon=lon, alt=300, timestamp="c",
                   utc=datetime(2026, 7, 30, 12, 0), rel_alt=50),
    ])


def test_luxembourg_fetch_parses_caches_and_announces(tmp_path):
    fake = FakeTransport([(FIXTURES / "ed269-lu.json").read_bytes()])
    lines = []
    data = fetch_zones(_track(49.62, 6.2), tmp_path, transport=fake,
                       announce=lines.append)
    assert data.gap_reason is None and len(data.zones) == 2
    assert data.source is not None and "drones.geoportail.lu" in data.source.url
    assert not data.from_cache
    assert any("Fetching" in ln and "geoportail.lu" in ln for ln in lines)
    assert (tmp_path / "ed269-LU.json").exists()
    assert (tmp_path / "ed269-LU.json.meta.json").exists()


def test_second_run_uses_the_cache_offline(tmp_path):
    fake = FakeTransport([(FIXTURES / "ed269-lu.json").read_bytes()])
    fetch_zones(_track(49.62, 6.2), tmp_path, transport=fake)
    lines = []

    def no_network(req, timeout=None):
        raise AssertionError("cache hit must not touch the network")

    data = fetch_zones(_track(49.62, 6.2), tmp_path, transport=no_network,
                       announce=lines.append)
    assert data.from_cache and len(data.zones) == 2
    assert any("cached" in ln for ln in lines)


def test_refresh_forces_a_refetch(tmp_path):
    fake = FakeTransport([(FIXTURES / "ed269-lu.json").read_bytes()])
    fetch_zones(_track(49.62, 6.2), tmp_path, transport=fake)
    fake2 = FakeTransport([(FIXTURES / "ed269-lu.json").read_bytes()])
    data = fetch_zones(_track(49.62, 6.2), tmp_path, refresh=True,
                       transport=fake2)
    assert not data.from_cache and fake2.urls


def test_a_us_flight_routes_to_the_faa_provider(tmp_path):
    fake = FakeTransport([(FIXTURES / "faa-uasfm.json").read_bytes()])
    data = fetch_zones(_track(40.77, -73.89), tmp_path, transport=fake)
    assert data.gap_reason is None and data.zones
    assert data.zones[0].restriction == "CEILING"
    assert "arcgis" in fake.urls[0]


def test_a_swedish_flight_is_a_stated_gap_without_network(tmp_path):
    def no_network(req, timeout=None):
        raise AssertionError("gap must not touch the network")

    data = fetch_zones(_track(59.33, 18.07), tmp_path, transport=no_network)
    assert data.gap_reason is not None and not data.zones


def test_a_dead_feed_becomes_a_stated_gap_not_a_crash(tmp_path):
    def dead(req, timeout=None):
        raise OSError("connection refused")

    data = fetch_zones(_track(49.62, 6.2), tmp_path, transport=dead)
    assert data.gap_reason is not None
    assert "connection refused" in data.gap_reason


def test_a_malformed_feed_is_all_or_nothing(tmp_path):
    fake = FakeTransport([b'{"features": [{"identifier": "X"}]}'])
    data = fetch_zones(_track(49.62, 6.2), tmp_path, transport=fake)
    assert data.gap_reason is not None and "restriction" in data.gap_reason


def test_a_corrupted_meta_json_triggers_a_refetch_not_a_crash(tmp_path):
    fake = FakeTransport([(FIXTURES / "ed269-lu.json").read_bytes()])
    fetch_zones(_track(49.62, 6.2), tmp_path, transport=fake)
    (tmp_path / "ed269-LU.json.meta.json").write_bytes(b"not json{{{")

    fake2 = FakeTransport([(FIXTURES / "ed269-lu.json").read_bytes()])
    data = fetch_zones(_track(49.62, 6.2), tmp_path, transport=fake2)
    assert data.gap_reason is None and len(data.zones) == 2
    assert not data.from_cache
    assert fake2.urls


def test_a_corrupted_cached_faa_body_becomes_a_gap_not_a_crash(tmp_path):
    fake = FakeTransport([(FIXTURES / "faa-uasfm.json").read_bytes()])
    fetch_zones(_track(40.77, -73.89), tmp_path, transport=fake)
    body_path = next(
        p for p in tmp_path.glob("faa-*.json") if not p.name.endswith(".meta.json")
    )
    body_path.write_bytes(b"not json{{{")

    def no_network(req, timeout=None):
        raise AssertionError("a corrupted cache hit must not force a live fetch")

    data = fetch_zones(_track(40.77, -73.89), tmp_path, transport=no_network)
    assert data.gap_reason is not None and "JSON" in data.gap_reason
    assert not data.zones


def test_refresh_failure_with_corrupted_stale_cache_is_a_gap_not_a_false_announce(
    tmp_path,
):
    fake = FakeTransport([(FIXTURES / "ed269-lu.json").read_bytes()])
    fetch_zones(_track(49.62, 6.2), tmp_path, transport=fake)
    (tmp_path / "ed269-LU.json").write_bytes(b"not xml or json at all")

    def dead(req, timeout=None):
        raise OSError("connection refused")

    lines = []
    data = fetch_zones(_track(49.62, 6.2), tmp_path, refresh=True,
                       transport=dead, announce=lines.append)
    assert data.gap_reason is not None and not data.zones
    assert not any("using cached" in ln.lower() for ln in lines)


def test_a_cached_faa_body_with_no_pages_list_is_a_gap_not_zero_zones(tmp_path):
    fake = FakeTransport([(FIXTURES / "faa-uasfm.json").read_bytes()])
    fetch_zones(_track(40.77, -73.89), tmp_path, transport=fake)
    body_path = next(
        p for p in tmp_path.glob("faa-*.json") if not p.name.endswith(".meta.json")
    )
    body_path.write_bytes(b"{}")  # valid JSON, but no 'pages' list

    def no_network(req, timeout=None):
        raise AssertionError("a genuine cache hit must not touch the network")

    data = fetch_zones(_track(40.77, -73.89), tmp_path, transport=no_network)
    assert data.gap_reason is not None and "pages" in data.gap_reason
    assert not data.zones


def test_corrupted_primary_cache_hit_is_a_gap_not_a_false_announce(tmp_path):
    fake = FakeTransport([(FIXTURES / "ed269-lu.json").read_bytes()])
    fetch_zones(_track(49.62, 6.2), tmp_path, transport=fake)
    (tmp_path / "ed269-LU.json").write_bytes(b"not xml or json at all")

    def no_network(req, timeout=None):
        raise AssertionError("a genuine cache hit must not touch the network")

    lines = []
    data = fetch_zones(_track(49.62, 6.2), tmp_path, transport=no_network,
                       announce=lines.append)
    assert data.gap_reason is not None and not data.zones
    assert not any("using cached" in ln.lower() for ln in lines)


def test_switzerland_fetch_applies_the_no_ceiling_sentinel(tmp_path):
    fake = FakeTransport([(FIXTURES / "ed269-ch.json").read_bytes()])
    data = fetch_zones(_track(47.37, 8.54), tmp_path, transport=fake)
    assert data.gap_reason is None and len(data.zones) == 4
    assert data.source is not None and "data.geo.admin.ch" in data.source.url
    assert "O-BY" in data.source.license
    assert (tmp_path / "ed269-CH.json").exists()
    sentinel_zone = next(z for z in data.zones if z.identifier == "CH-GT9990")
    assert sentinel_zone.upper is None  # 99999 m AMSL sentinel, not a ceiling
