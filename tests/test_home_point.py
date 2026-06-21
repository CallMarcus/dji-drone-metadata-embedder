from dji_metadata_embedder.utilities import Home, apply_redaction, parse_home, redact_home

# Variant 1: HOME(lat,lon) no space, no altitude
SRT_V1 = "HOME(39.906206,116.391400) D=5.2m H=1.5m"
# Variant 2: HOME (lat, lon, altm) leading space + altitude with trailing m
SRT_V2 = "HOME (-58.847509, -34.232707, -57.98m), D 698.70m, H 85.80m,"


def test_parse_home_variant1_no_alt():
    home = parse_home(SRT_V1)
    assert home == Home(lat=39.906206, lon=116.391400, alt=None)


def test_parse_home_variant2_with_alt():
    home = parse_home(SRT_V2)
    assert home == Home(lat=-58.847509, lon=-34.232707, alt=-57.98)


def test_parse_home_absent_returns_none():
    assert parse_home("[latitude: 1.0] [longitude: 2.0]") is None


def test_redact_home_drop():
    assert redact_home(Home(1.23456, 2.34567, 10.0), "drop") is None


def test_redact_home_fuzz_rounds_to_3dp():
    assert redact_home(Home(1.23456, 2.34567, 10.12345), "fuzz") == Home(1.235, 2.346, 10.123)


def test_redact_home_none_passthrough():
    h = Home(1.23456, 2.34567, None)
    assert redact_home(h, "none") == h


def test_redact_home_handles_none_input():
    assert redact_home(None, "fuzz") is None


def test_apply_redaction_drops_home():
    tel = {"gps_coords": [(1.0, 2.0)], "first_gps": (1.0, 2.0), "avg_gps": (1.0, 2.0),
           "home": Home(1.23456, 2.34567, 10.0)}
    apply_redaction(tel, "drop")
    assert tel["home"] is None


def test_apply_redaction_fuzzes_home():
    tel = {"gps_coords": [(1.0, 2.0)], "first_gps": (1.0, 2.0), "avg_gps": (1.0, 2.0),
           "home": Home(1.23456, 2.34567, 10.0)}
    apply_redaction(tel, "fuzz")
    assert tel["home"] == Home(1.235, 2.346, 10.0)


def test_apply_redaction_no_home_key_is_noop():
    tel = {"gps_coords": [(1.0, 2.0)], "first_gps": (1.0, 2.0), "avg_gps": (1.0, 2.0)}
    apply_redaction(tel, "drop")  # must not raise
    assert "home" not in tel
