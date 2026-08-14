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


# Regression: the original US/LU core boxes wrongly resolved foreign
# territory (northern Mexico, western Bahamas, a German corner near
# 50.0N 6.3E). Each of these must gap instead of guessing a jurisdiction.
def test_hermosillo_mexico_gaps_instead_of_resolving_us():
    r = resolve_jurisdiction(_track((29.07, -110.95)))
    assert r.jurisdiction is None


def test_ciudad_juarez_mexico_gaps_instead_of_resolving_us():
    r = resolve_jurisdiction(_track((31.74, -106.49)))
    assert r.jurisdiction is None


def test_nassau_bahamas_gaps_instead_of_resolving_us():
    r = resolve_jurisdiction(_track((25.08, -77.35)))
    assert r.jurisdiction is None


def test_freeport_bahamas_gaps_instead_of_resolving_us():
    r = resolve_jurisdiction(_track((26.53, -78.70)))
    assert r.jurisdiction is None


def test_the_german_corner_near_50n_6point3e_gaps_instead_of_resolving_lu():
    r = resolve_jurisdiction(_track((50.00, 6.30)))
    assert r.jurisdiction is None


def test_phoenix_resolves_to_us():
    r = resolve_jurisdiction(_track((33.45, -112.07)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "US"


def test_tucson_resolves_to_us():
    r = resolve_jurisdiction(_track((32.22, -110.97)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "US"


def test_san_antonio_resolves_to_us():
    r = resolve_jurisdiction(_track((29.42, -98.49)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "US"


def test_houston_resolves_to_us():
    r = resolve_jurisdiction(_track((29.76, -95.37)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "US"


def test_miami_resolves_to_us():
    r = resolve_jurisdiction(_track((25.76, -80.19)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "US"


def test_luxembourg_city_still_resolves_to_lu():
    r = resolve_jurisdiction(_track((49.61, 6.13)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "LU"


# Regression: the LU centre box's original single span (49.8-49.9N) was
# split into a centre box and a Bettendorf-band box because the Our river
# cuts the actual border west near Gentingen, Germany.
def test_gentingen_germany_gaps_instead_of_resolving_lu():
    r = resolve_jurisdiction(_track((49.90, 6.245)))
    assert r.jurisdiction is None


def test_a_point_near_the_gentingen_border_band_gaps_by_design():
    # ~900 m from Germany here — inside the hull but outside the core, so
    # this gaps as a border-band flight, deliberately, not a resolution.
    r = resolve_jurisdiction(_track((49.90, 6.22)))
    assert r.jurisdiction is None


def test_a_point_inside_the_bettendorf_band_resolves_to_lu():
    r = resolve_jurisdiction(_track((49.89, 6.15)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "LU"


# Switzerland (#456): plateau core boxes, Nominatim-verified 2026-08-05 —
# every edge and margin probe resolved to CH with >=5 km of border buffer.
def test_a_zurich_flight_resolves_to_ch_with_the_eu_measure():
    r = resolve_jurisdiction(_track((47.37, 8.54)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "CH"
    assert "2019/947" in r.jurisdiction.measure_note


def test_bern_resolves_to_ch():
    r = resolve_jurisdiction(_track((46.95, 7.45)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "CH"


def test_lucerne_resolves_to_ch():
    r = resolve_jurisdiction(_track((47.05, 8.31)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "CH"


def test_geneva_gaps_as_a_border_band():
    # Geneva is enclosed by France on three sides; inside the CH hull but
    # deliberately outside every core box.
    r = resolve_jurisdiction(_track((46.20, 6.15)))
    assert r.jurisdiction is None
    assert r.gap_reason is not None and "boundary" in r.gap_reason


def test_basel_gaps_as_a_border_band():
    r = resolve_jurisdiction(_track((47.56, 7.59)))
    assert r.jurisdiction is None


def test_konstanz_germany_gaps_instead_of_resolving_ch():
    r = resolve_jurisdiction(_track((47.66, 9.17)))
    assert r.jurisdiction is None


def test_bregenz_austria_gaps_instead_of_resolving_ch():
    r = resolve_jurisdiction(_track((47.50, 9.75)))
    assert r.jurisdiction is None


def test_milan_gaps_outside_the_ch_hull():
    r = resolve_jurisdiction(_track((45.46, 9.19)))
    assert r.jurisdiction is None
    assert r.gap_reason is not None and "no supported airspace data" in r.gap_reason


# --- Ireland (#452) ---------------------------------------------------------
# Core/hull edges Nominatim-verified 2026-08-14: the NI border's
# southernmost reach is ~54.03 (Carlingford Lough) and its westernmost
# ~-8.18 (Belleek), so the cores stop at 53.85 and -8.4 respectively.


def test_a_dublin_flight_resolves_to_ie_with_the_eu_measure():
    r = resolve_jurisdiction(_track((53.35, -6.26), (53.36, -6.25)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "IE"
    assert "2019/947" in r.jurisdiction.measure_note


def test_a_sligo_flight_resolves_through_the_northwest_core():
    r = resolve_jurisdiction(_track((54.27, -8.48)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "IE"


def test_a_belfast_flight_gaps_instead_of_resolving_ie():
    r = resolve_jurisdiction(_track((54.60, -5.93)))
    assert r.jurisdiction is None
    assert "boundary" in (r.gap_reason or "")


def test_a_dundalk_flight_gaps_as_a_border_band():
    # 15 km from the border: too close to choose from coordinates alone.
    r = resolve_jurisdiction(_track((54.00, -6.40)))
    assert r.jurisdiction is None
    assert "boundary" in (r.gap_reason or "")


def test_the_no_provider_message_names_ireland():
    r = resolve_jurisdiction(_track((48.85, 2.35)))   # Paris
    assert r.jurisdiction is None
    assert "Ireland" in (r.gap_reason or "")
