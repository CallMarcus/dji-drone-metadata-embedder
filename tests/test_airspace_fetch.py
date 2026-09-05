"""Fetch orchestration tests (#413): consent lines, cache, honest gaps."""
import hashlib
import io
import json
import zipfile
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
    # No dated product here: nothing is claimed and the sidecar stays as
    # it was (#502 only adds the key when a feed states a date).
    assert data.source.effective is None
    meta = json.loads(
        (tmp_path / "ed269-LU.json.meta.json").read_text(encoding="utf-8")
    )
    assert "effective" not in meta


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


def test_an_oslo_flight_is_a_stated_gap_without_network(tmp_path):
    # #510: Sweden now has a provider, so this no-provider-gap example
    # moves to Oslo (outside every hull, including the new SE one).
    def no_network(req, timeout=None):
        raise AssertionError("gap must not touch the network")

    data = fetch_zones(_track(59.91, 10.75), tmp_path, transport=no_network)
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


def test_an_irish_flight_discovers_the_dated_file_then_fetches_it(tmp_path):
    # #452: the IAA filename is dated and versioned, so the fetch is
    # two-step — zones page first, then the discovered file.
    page = (
        b'<a href="/docs/default-source/default-document-library/uas/'
        b'20260804_uas_zones_ireland_v1.geojson?sfvrsn=1_2&amp;download=true">'
        b'</a>'
    )
    fake = FakeTransport([page, (FIXTURES / "ed318-ie.json").read_bytes()])
    lines = []
    data = fetch_zones(_track(53.35, -6.26), tmp_path, transport=fake,
                       announce=lines.append)
    assert data.gap_reason is None and len(data.zones) == 4
    assert fake.urls[0].startswith(
        "https://www.iaa.ie/general-aviation/drones/uas-geographic-zones")
    assert "uas_zones_ireland" in fake.urls[1]
    assert data.source is not None and "Irish Aviation Authority" in data.source.license
    assert (tmp_path / "ed318-IE.json").exists()
    assert any("Fetching" in ln and "iaa.ie" in ln for ln in lines)
    # #563: the file's own edition (datasetMetadata.validFrom) is what the
    # IAA asked the reader to see; it reaches the record and the sidecar.
    assert data.source.effective == "2026-08-04"
    meta = json.loads(
        (tmp_path / "ed318-IE.json.meta.json").read_text(encoding="utf-8")
    )
    assert meta["effective"] == "2026-08-04"


def test_a_cached_irish_body_skips_discovery_entirely(tmp_path):
    page = (
        b'<a href="/docs/x/20260804_uas_zones_ireland_v1.geojson'
        b'?sfvrsn=1_2&amp;download=true"></a>'
    )
    fake = FakeTransport([page, (FIXTURES / "ed318-ie.json").read_bytes()])
    fetch_zones(_track(53.35, -6.26), tmp_path, transport=fake)

    def no_network(req, timeout=None):
        raise AssertionError("cached run must not touch the network")
    data = fetch_zones(_track(53.35, -6.26), tmp_path, transport=no_network)
    assert data.from_cache and len(data.zones) == 4
    # The cached copy still states which edition it is (#563).
    assert data.source is not None and data.source.effective == "2026-08-04"


def _gb_zip() -> bytes:
    xml = (FIXTURES / "aixm51-gb.xml").read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("EG_UAS_FR_DS_AREA1_FULL_20260806.xml", xml)
        zf.writestr(
            "EG_UAS_FR_DS_AREA1_FULL_20260806.sha256",
            hashlib.sha256(xml).hexdigest()
            + " *EG_UAS_FR_DS_AREA1_FULL_20260806.xml",
        )
    return buf.getvalue()


GB_PAGE = (
    b'<a href="/x/UAS_AREA_1/EG_UAS_FR_DS_AREA1_FULL_20200101_XML.zip">'
    b"</a>"
)


def test_a_uk_flight_discovers_the_cycle_zip_and_caches_the_xml(tmp_path):
    # #499: three-step — datasets page, then the dated zip, then the
    # XML is extracted (sha-verified) and cached as plain XML.
    fake = FakeTransport([GB_PAGE, _gb_zip()])
    lines = []
    data = fetch_zones(_track(51.50, -0.12), tmp_path, transport=fake,
                       announce=lines.append)
    assert data.gap_reason is None and len(data.zones) == 6
    assert fake.urls[0].startswith("https://nats-uk.ead-it.com/")
    assert fake.urls[1].endswith("_XML.zip")
    assert data.source is not None and "NATS" in data.source.license
    assert (tmp_path / "aixm-GB.xml").exists()
    assert (tmp_path / "aixm-GB.xml").read_bytes().startswith(b"<?xml")
    assert any("Fetching" in ln and "nats-uk.ead-it.com" in ln
               for ln in lines)
    # #502: the AIRAC cycle date from the zip filename reaches the
    # source line and the cache sidecar, so a cached run can state it.
    assert data.source.effective == "2020-01-01"
    meta = json.loads(
        (tmp_path / "aixm-GB.xml.meta.json").read_text(encoding="utf-8")
    )
    assert meta["effective"] == "2020-01-01"


def test_a_cached_uk_body_skips_discovery_and_the_network(tmp_path):
    fetch_zones(_track(51.50, -0.12), tmp_path,
                transport=FakeTransport([GB_PAGE, _gb_zip()]))

    def no_network(req, timeout=None):
        raise AssertionError("cached run must not touch the network")
    data = fetch_zones(_track(51.50, -0.12), tmp_path, transport=no_network)
    assert data.from_cache and len(data.zones) == 6
    assert data.source is not None and data.source.effective == "2020-01-01"


def test_a_cache_sidecar_without_a_cycle_date_states_none(tmp_path):
    # Sidecars written before #502 (or by feeds with no dated product)
    # carry no "effective" key: the record simply omits the line rather
    # than inventing a date or refusing the cache.
    fetch_zones(_track(51.50, -0.12), tmp_path,
                transport=FakeTransport([GB_PAGE, _gb_zip()]))
    meta_path = tmp_path / "aixm-GB.xml.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    del meta["effective"]
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    def no_network(req, timeout=None):
        raise AssertionError("cached run must not touch the network")
    data = fetch_zones(_track(51.50, -0.12), tmp_path, transport=no_network)
    assert data.from_cache and data.source is not None
    assert data.source.effective is None


def _gb_zip_bad_sha() -> bytes:
    # The naive byte-replace-in-the-finished-zip trick corrupts the
    # member's CRC-32 (BadZipFile, not a clean SHA mismatch) because
    # zipfile validates CRC on read. Build the bad zip explicitly
    # instead, mirroring `_zip(..., sha=...)` from
    # tests/test_airspace_aixm51.py.
    xml = (FIXTURES / "aixm51-gb.xml").read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("EG_UAS_FR_DS_AREA1_FULL_20260806.xml", xml)
        zf.writestr(
            "EG_UAS_FR_DS_AREA1_FULL_20260806.sha256",
            "0" * 64 + " *EG_UAS_FR_DS_AREA1_FULL_20260806.xml",
        )
    return buf.getvalue()


def test_a_uk_sha_mismatch_is_a_stated_gap(tmp_path):
    data = fetch_zones(_track(51.50, -0.12), tmp_path,
                       transport=FakeTransport([GB_PAGE, _gb_zip_bad_sha()]))
    assert data.gap_reason is not None and "SHA-256" in data.gap_reason


DK_PAGE = (
    b'<a href="https://trafikstyrelsen.maps.arcgis.com/sharing/rest/'
    b'content/items/f049a65ae2f34bd1b747895d555dac71/data">GeoJson</a>'
)


def test_a_danish_flight_discovers_the_geojson_and_caches_it(tmp_path):
    fake = FakeTransport(
        [DK_PAGE, (FIXTURES / "dronezoner-dk.json").read_bytes()]
    )
    lines = []
    data = fetch_zones(_track(55.68, 12.57), tmp_path, transport=fake,
                       announce=lines.append)
    assert data.gap_reason is None and len(data.zones) == 7
    assert fake.urls[0].startswith("https://www.en.droneregler.dk/")
    assert fake.urls[1].endswith(
        "items/f049a65ae2f34bd1b747895d555dac71/data"
    )
    assert data.source is not None
    assert "kildeangivelse" in data.source.license
    assert (tmp_path / "dronezoner-DK.json").exists()
    assert any("Fetching" in ln and "www.en.droneregler.dk" in ln
               for ln in lines)


def test_a_cached_danish_body_skips_discovery_and_the_network(tmp_path):
    fetch_zones(
        _track(55.68, 12.57), tmp_path,
        transport=FakeTransport(
            [DK_PAGE, (FIXTURES / "dronezoner-dk.json").read_bytes()]
        ),
    )

    def no_network(req, timeout=None):
        raise AssertionError("cached run must not touch the network")
    data = fetch_zones(_track(55.68, 12.57), tmp_path, transport=no_network)
    assert data.from_cache and len(data.zones) == 7


def test_a_redesigned_danish_page_is_a_stated_gap(tmp_path):
    data = fetch_zones(_track(55.68, 12.57), tmp_path,
                       transport=FakeTransport([b"<html>redesigned</html>"]))
    assert not data.zones
    assert data.gap_reason is not None
    assert "droneregler.dk" in data.gap_reason


def test_a_swedish_flight_fetches_the_lfv_file_directly(tmp_path):
    # #510: LFV's URL is the stable published address — one fetch, no
    # page discovery, and the record cites the file URL itself.
    fake = FakeTransport([(FIXTURES / "ed318-se.json").read_bytes()])
    lines = []
    data = fetch_zones(_track(59.33, 18.07), tmp_path, transport=fake,
                       announce=lines.append)
    assert data.gap_reason is None and len(data.zones) == 3
    assert fake.urls == [
        "https://dronechart.lfv.se/data/uas_zones_ED318.json"
    ]
    assert data.source is not None and "cite LFV as source" in data.source.license
    assert data.source.url.endswith("uas_zones_ED318.json")
    assert (tmp_path / "ed318-SE.json").exists()
    assert any("Fetching" in ln and "dronechart.lfv.se" in ln for ln in lines)
    assert data.source.effective == "2026-08-13"  # metadata.validFrom (#563)
    circle = next(z for z in data.zones if z.identifier == "ESU902")
    assert len(circle.polygons[0]) >= 32


def test_a_cached_swedish_body_never_touches_the_network(tmp_path):
    fake = FakeTransport([(FIXTURES / "ed318-se.json").read_bytes()])
    fetch_zones(_track(59.33, 18.07), tmp_path, transport=fake)

    def no_network(req, timeout=None):
        raise AssertionError("cached run must not touch the network")
    data = fetch_zones(_track(59.33, 18.07), tmp_path, transport=no_network)
    assert data.from_cache and len(data.zones) == 3


def test_an_estonian_flight_fetches_the_eans_file_directly(tmp_path):
    # #511: EANS's URL is stable — one fetch, no discovery, the record
    # cites the file URL itself.
    fake = FakeTransport([(FIXTURES / "eans-ee.json").read_bytes()])
    lines = []
    data = fetch_zones(_track(59.44, 24.75), tmp_path, transport=fake,
                       announce=lines.append)
    assert data.gap_reason is None and len(data.zones) == 3
    assert fake.urls == ["https://utm.eans.ee/avm/utm/uas.geojson"]
    assert data.source is not None
    assert "Estonian Air Navigation Services" in data.source.license
    assert "time of download" in (data.source.note or "")
    assert (tmp_path / "eans-EE.json").exists()
    assert any("Fetching" in ln and "utm.eans.ee" in ln for ln in lines)


def test_a_cached_estonian_body_never_touches_the_network(tmp_path):
    fake = FakeTransport([(FIXTURES / "eans-ee.json").read_bytes()])
    fetch_zones(_track(59.44, 24.75), tmp_path, transport=fake)

    def no_network(req, timeout=None):
        raise AssertionError("cached run must not touch the network")
    data = fetch_zones(_track(59.44, 24.75), tmp_path, transport=no_network)
    assert data.from_cache and len(data.zones) == 3



def test_a_200_error_page_never_reaches_the_cache(tmp_path):
    # #518: a provider maintenance page served with HTTP 200 must not be
    # written as the feed body — the next run should refetch, not be
    # stuck parsing poison until --airspace-refresh.
    fake = FakeTransport([b"<html>Down for maintenance</html>"])
    data = fetch_zones(_track(49.62, 6.2), tmp_path, transport=fake)
    assert data.gap_reason is not None
    assert not (tmp_path / "ed269-LU.json").exists()
    assert not (tmp_path / "ed269-LU.json.meta.json").exists()

    fake2 = FakeTransport([(FIXTURES / "ed269-lu.json").read_bytes()])
    healed = fetch_zones(_track(49.62, 6.2), tmp_path, transport=fake2)
    assert healed.gap_reason is None and len(healed.zones) == 2
    assert fake2.urls


def test_an_unparseable_cached_body_names_the_refresh_flag(tmp_path):
    # #518: caches poisoned before the write-after-parse fix (or corrupted
    # on disk) still fail — but the gap must tell the user the way out.
    fake = FakeTransport([(FIXTURES / "ed269-lu.json").read_bytes()])
    fetch_zones(_track(49.62, 6.2), tmp_path, transport=fake)
    (tmp_path / "ed269-LU.json").write_bytes(b"<html>Down</html>")

    def no_network(req, timeout=None):
        raise AssertionError("a corrupted cache hit must not force a live fetch")

    data = fetch_zones(_track(49.62, 6.2), tmp_path, transport=no_network)
    assert data.gap_reason is not None
    assert "--airspace-refresh" in data.gap_reason


def test_a_fresh_fetch_failure_does_not_name_the_refresh_flag(tmp_path):
    # Refreshing cannot help when the live feed itself is bad — the hint
    # belongs to cached-body failures only.
    fake = FakeTransport([b"<html>Down for maintenance</html>"])
    data = fetch_zones(_track(49.62, 6.2), tmp_path, transport=fake)
    assert data.gap_reason is not None
    assert "--airspace-refresh" not in data.gap_reason
