from dji_metadata_embedder.utilities import apply_redaction


def test_redact_drop():
    telemetry = {
        "gps_coords": [(59.123456, 18.654321)],
        "first_gps": (59.123456, 18.654321),
        "avg_gps": (59.123456, 18.654321),
    }
    apply_redaction(telemetry, "drop")
    assert telemetry["gps_coords"] == []
    assert telemetry["first_gps"] is None
    assert telemetry["avg_gps"] is None


def test_redact_fuzz():
    telemetry = {
        "gps_coords": [(59.123456, 18.654321)],
        "first_gps": (59.123456, 18.654321),
        "avg_gps": (59.123456, 18.654321),
    }
    apply_redaction(telemetry, "fuzz")
    assert telemetry["gps_coords"] == [(59.123, 18.654)]
    assert telemetry["first_gps"] == (59.123, 18.654)
    assert telemetry["avg_gps"] == (59.123, 18.654)
