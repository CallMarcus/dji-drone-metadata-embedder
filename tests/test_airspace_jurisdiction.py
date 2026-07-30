"""Jurisdiction-from-track tests (#413): flight-relevant, never guessed."""
from dji_metadata_embedder.geo.airspace.jurisdiction import resolve_jurisdiction
from dji_metadata_embedder.geo.track import Track, TrackPoint


def _track(*coords):
    return Track(
        name="t",
        points=[TrackPoint(lat=la, lon=lo, alt=100, timestamp="c") for la, lo in coords],
    )


def test_a_new_york_flight_resolves_to_the_us():
    r = resolve_jurisdiction(_track((40.77, -73.9), (40.78, -73.88)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "US"
    assert "107.51" in r.jurisdiction.measure_note


def test_a_luxembourg_flight_resolves_to_lu_with_the_eu_measure():
    r = resolve_jurisdiction(_track((49.62, 6.2)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "LU"
    assert "2019/947" in r.jurisdiction.measure_note


def test_a_helsinki_flight_resolves_to_fi():
    r = resolve_jurisdiction(_track((60.25, 24.95)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "FI"


def test_a_swedish_flight_is_an_honest_gap():
    r = resolve_jurisdiction(_track((59.33, 18.07)))  # Stockholm
    assert r.jurisdiction is None
    assert r.gap_reason is not None and "no supported airspace data" in r.gap_reason


def test_a_border_band_flight_gaps_instead_of_guessing():
    # Tornio, on the Finnish-Swedish border: inside the FI hull, outside core.
    r = resolve_jurisdiction(_track((65.85, 24.15)))
    assert r.jurisdiction is None
    assert r.gap_reason is not None and "boundary" in r.gap_reason


def test_an_empty_track_gaps():
    r = resolve_jurisdiction(Track(name="t", points=[]))
    assert r.jurisdiction is None and r.gap_reason is not None
