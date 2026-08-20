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


def test_a_stockholm_flight_resolves_to_se_with_the_eu_measure():
    r = resolve_jurisdiction(_track((59.33, 18.07)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "SE"
    assert "2019/947" in r.jurisdiction.measure_note


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


def test_a_dundalk_flight_gaps_as_a_border_band():
    # 15 km from the border: too close to choose from coordinates alone.
    r = resolve_jurisdiction(_track((54.00, -6.40)))
    assert r.jurisdiction is None
    assert "boundary" in (r.gap_reason or "")


def test_the_no_provider_message_names_ireland():
    r = resolve_jurisdiction(_track((48.85, 2.35)))   # Paris
    assert r.jurisdiction is None
    assert "Ireland" in (r.gap_reason or "")


# --- United Kingdom (#499) --------------------------------------------------
# Cores break hull ties: NI sits in both the GB and IE hulls, and
# resolves through the GB NI core. Edges Nominatim/arithmetic-verified
# at implementation time.


def test_a_london_flight_resolves_to_gb_with_the_uk_measure():
    r = resolve_jurisdiction(_track((51.50, -0.12), (51.51, -0.11)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "GB"
    assert "assimilated" in r.jurisdiction.measure_note
    assert "2019/947" in r.jurisdiction.measure_note


def test_cardiff_resolves_to_gb():
    r = resolve_jurisdiction(_track((51.48, -3.18)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "GB"


def test_manchester_resolves_to_gb():
    r = resolve_jurisdiction(_track((53.48, -2.24)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "GB"


def test_edinburgh_resolves_to_gb():
    r = resolve_jurisdiction(_track((55.95, -3.19)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "GB"


def test_dover_and_margate_resolve_through_the_kent_core():
    for lat, lon in ((51.13, 1.31), (51.39, 1.38)):
        r = resolve_jurisdiction(_track((lat, lon)))
        assert r.jurisdiction is not None and r.jurisdiction.code == "GB"


def test_the_scottish_islands_resolve_to_gb():
    # Kirkwall and Wick RPZs are in the dataset; Orkney, Shetland and
    # the Hebrides get cores, not border-band gaps.
    for lat, lon in ((58.98, -2.96), (60.15, -1.15), (58.21, -6.39)):
        r = resolve_jurisdiction(_track((lat, lon)))
        assert r.jurisdiction is not None and r.jurisdiction.code == "GB"


def test_a_belfast_flight_now_resolves_to_gb():
    # The whole point of #499's NI coverage: Belfast sits in both the
    # GB and IE hulls and only the GB cores contain it.
    r = resolve_jurisdiction(_track((54.60, -5.93)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "GB"


def test_dublin_still_resolves_to_ie():
    r = resolve_jurisdiction(_track((53.35, -6.26)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "IE"


def test_derry_gaps_as_a_border_band():
    # ~3 km from the IE border: outside the NI core by design.
    r = resolve_jurisdiction(_track((54.997, -7.32)))
    assert r.jurisdiction is None
    assert "boundary" in (r.gap_reason or "")


def test_the_isle_of_man_gaps_instead_of_claiming_coverage():
    # Its own AIP; the dataset has no Ronaldsway FRZ. Hull yes, core no.
    r = resolve_jurisdiction(_track((54.15, -4.48)))
    assert r.jurisdiction is None
    assert "boundary" in (r.gap_reason or "")


def test_jersey_is_an_honest_no_provider_gap():
    r = resolve_jurisdiction(_track((49.21, -2.13)))
    assert r.jurisdiction is None
    assert "no supported airspace data" in (r.gap_reason or "")


def test_calais_gaps_instead_of_resolving_gb():
    r = resolve_jurisdiction(_track((50.96, 1.85)))
    assert r.jurisdiction is None


def test_the_no_provider_message_names_the_uk():
    r = resolve_jurisdiction(_track((48.85, 2.35)))   # Paris
    assert "the UK" in (r.gap_reason or "")


# --- Denmark (Trafikstyrelsen Dronezoner) ---


def test_a_copenhagen_flight_resolves_to_dk_with_the_eu_measure():
    r = resolve_jurisdiction(_track((55.68, 12.57), (55.66, 12.6)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "DK"
    assert "2019/947" in r.jurisdiction.measure_note


def test_kastrup_airport_resolves_to_dk():
    # Amager sits 2 km from the core's Øresund edge; the Swedish coast
    # is >=13 km further east (Nominatim-verified 2026-08-15).
    r = resolve_jurisdiction(_track((55.62, 12.65)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "DK"


def test_aarhus_and_odense_resolve_to_dk():
    for lat, lon in ((56.16, 10.21), (55.40, 10.39)):
        r = resolve_jurisdiction(_track((lat, lon)))
        assert r.jurisdiction is not None and r.jurisdiction.code == "DK"


def test_the_danish_islands_resolve_to_dk():
    # Bornholm (Rønne), Læsø, Skagen at Jutland's tip.
    for lat, lon in ((55.10, 14.70), (57.26, 11.00), (57.72, 10.58)):
        r = resolve_jurisdiction(_track((lat, lon)))
        assert r.jurisdiction is not None and r.jurisdiction.code == "DK"


def test_sonderborg_gaps_as_a_border_band():
    # Danish, but <10 km from the German border: inside the hull,
    # outside every core.
    r = resolve_jurisdiction(_track((54.91, 9.79)))
    assert r.jurisdiction is None
    assert r.gap_reason is not None and "boundary" in r.gap_reason


def test_helsingor_gaps_as_a_border_band():
    # The strait to Helsingborg is ~4.5 km wide; coordinates alone
    # cannot pick a side confidently.
    r = resolve_jurisdiction(_track((56.03, 12.61)))
    assert r.jurisdiction is None
    assert r.gap_reason is not None and "boundary" in r.gap_reason


def test_helsingborg_sweden_gaps_instead_of_resolving_dk():
    # Inside the DK hull on purpose (CH-Konstanz semantics) but never
    # inside a core.
    r = resolve_jurisdiction(_track((56.05, 12.69)))
    assert r.jurisdiction is None
    assert r.gap_reason is not None and "boundary" in r.gap_reason


def test_flensburg_germany_gaps_instead_of_resolving_dk():
    r = resolve_jurisdiction(_track((54.79, 9.43)))
    assert r.jurisdiction is None
    assert r.gap_reason is not None and "boundary" in r.gap_reason


def test_the_no_provider_message_names_denmark():
    r = resolve_jurisdiction(_track((48.85, 2.35)))  # Paris
    assert r.gap_reason is not None and "Denmark" in r.gap_reason


# --- Sweden (LFV Dronezoner via ED-318) ---


def test_gothenburg_resolves_to_se():
    r = resolve_jurisdiction(_track((57.71, 11.97)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "SE"


def test_malmo_resolves_to_se_despite_the_oresund():
    # Malmö sits ~13 km from Danish Saltholm; the core's 12.95 west edge
    # keeps it in while the Öresund shore north of it gaps.
    r = resolve_jurisdiction(_track((55.61, 13.00)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "SE"


def test_visby_gotland_resolves_to_se():
    r = resolve_jurisdiction(_track((57.64, 18.30)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "SE"


def test_kiruna_resolves_to_se():
    r = resolve_jurisdiction(_track((67.86, 20.22)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "SE"


def test_umea_and_lulea_resolve_through_the_norrland_coast_core():
    r = resolve_jurisdiction(_track((63.83, 20.26), (65.58, 22.15)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "SE"


def test_helsingborg_gaps_as_an_oresund_border_band():
    # 4.5 km strait to Helsingør: inside the hull, outside every core —
    # the mirror of Helsingør's cut on the Danish side.
    r = resolve_jurisdiction(_track((56.05, 12.70)))
    assert r.jurisdiction is None
    assert r.gap_reason is not None and "boundary" in r.gap_reason


def test_halden_norway_gaps_instead_of_resolving_se():
    r = resolve_jurisdiction(_track((59.12, 11.39)))
    assert r.jurisdiction is None


def test_eckero_aland_still_gaps():
    # Åland: inside the FI and SE hulls, inside neither's cores.
    r = resolve_jurisdiction(_track((60.22, 19.55)))
    assert r.jurisdiction is None


def test_copenhagen_still_resolves_dk_with_the_se_hull_overlapping():
    # Kastrup sits inside the new SE south hull; the DK core breaks the
    # tie (#499 semantics).
    r = resolve_jurisdiction(_track((55.63, 12.65)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "DK"


def test_oslo_stays_outside_the_se_hull_entirely():
    r = resolve_jurisdiction(_track((59.91, 10.75)))
    assert r.jurisdiction is None
    assert r.gap_reason is not None and "Sweden" in r.gap_reason


def test_svappavaara_resolves_se_closing_the_67_2_to_67_5_hole():
    # #510 M2: core 11 used to stop at 67.2N, leaving a band up to core
    # 12's 67.5N start unreachable even though it's Swedish interior.
    # Nominatim-verified 2026-08-19 at (67.35, 20.50).
    r = resolve_jurisdiction(_track((67.35, 20.50)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "SE"


def test_transtrand_resolves_se_now_the_hull_reaches_the_whole_core():
    # #510 M3: core 8 topped out at 61.5N but the Norrland hull box
    # stopped at 14.0E, leaving 13.4-14.0E x 61.0-61.5N inside the core
    # but outside every hull. Transtrand area, west Dalarna.
    r = resolve_jurisdiction(_track((61.2, 13.7)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "SE"



def test_a_tallinn_flight_resolves_to_ee_with_the_eu_measure():
    r = resolve_jurisdiction(_track((59.44, 24.75)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "EE"
    assert "2019/947" in r.jurisdiction.measure_note


def test_tartu_resolves_to_ee():
    r = resolve_jurisdiction(_track((58.38, 26.72)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "EE"


def test_parnu_resolves_to_ee():
    r = resolve_jurisdiction(_track((58.39, 24.50)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "EE"


def test_kuressaare_and_sorve_resolve_through_the_saaremaa_core():
    r = resolve_jurisdiction(_track((58.25, 22.48), (57.92, 22.04)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "EE"


def test_kardla_hiiumaa_resolves_to_ee():
    r = resolve_jurisdiction(_track((59.00, 22.75)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "EE"


def test_kopu_and_ristna_resolve_through_the_hiiumaa_core():
    # #521: the Kõpu peninsula sits ~90 km from the nearest foreign
    # territory — a gap there was an inset-rectangle artefact, not a
    # border band.
    r = resolve_jurisdiction(_track((58.916, 22.200), (58.939, 22.057)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "EE"


def test_kasmu_lahemaa_resolves_to_ee():
    # #521: Käsmu missed the N-core top by ~390 m.
    r = resolve_jurisdiction(_track((59.6035, 25.928)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "EE"


def test_hanko_still_resolves_fi_above_the_raised_ee_core():
    # The FI core floor is 59.8; the raised EE core top (59.65) must
    # not capture Finland's south coast.
    r = resolve_jurisdiction(_track((59.823, 22.97)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "FI"


def test_valga_gaps_as_a_border_band():
    # Its Latvian twin Valka is 1.2 km away — no coordinate box can
    # honestly split the twin towns.
    r = resolve_jurisdiction(_track((57.78, 26.03)))
    assert r.jurisdiction is None
    assert r.gap_reason is not None and "boundary" in r.gap_reason


def test_narva_gaps_as_a_border_band():
    r = resolve_jurisdiction(_track((59.38, 28.20)))
    assert r.jurisdiction is None
    assert r.gap_reason is not None and "boundary" in r.gap_reason


def test_valka_latvia_gaps_inside_the_hull_only():
    r = resolve_jurisdiction(_track((57.77, 26.02)))
    assert r.jurisdiction is None


def test_riga_stays_outside_the_ee_hull_entirely():
    r = resolve_jurisdiction(_track((56.95, 24.10)))
    assert r.jurisdiction is None
    assert r.gap_reason is not None and "Estonia" in r.gap_reason


def test_helsinki_still_resolves_fi_with_the_ee_hull_nearby():
    r = resolve_jurisdiction(_track((60.25, 24.95)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "FI"


def test_the_gulf_coast_overlap_band_resolves_ee_via_its_core():
    # Kunda (59.50, 26.50) sits inside BOTH the FI hull (lat >= 59.5) and
    # the EE hull; only the EE core contains it (#499 tie-break).
    r = resolve_jurisdiction(_track((59.50, 26.50)))
    assert r.jurisdiction is not None and r.jurisdiction.code == "EE"
