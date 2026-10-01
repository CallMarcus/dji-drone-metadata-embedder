"""Normalized airspace model (#413): shared by both providers and the evaluator."""

from datetime import datetime

import pytest

from dji_metadata_embedder.geo.airspace import AirspaceError
from dji_metadata_embedder.geo.airspace.model import VerticalLimit, iso_utc


def test_vertical_limit_labels_value_unit_and_reference():
    assert VerticalLimit(120, "m", "AGL").label() == "120 m AGL"
    assert VerticalLimit(400, "ft", "AGL").label() == "400 ft AGL"
    assert VerticalLimit(0, "ft", "AGL").label() == "0 ft AGL"


def test_vertical_limit_drops_trailing_zeros():
    assert VerticalLimit(45.72, "m", "AMSL").label() == "45.72 m AMSL"
    assert VerticalLimit(100.0, "ft", "AGL").label() == "100 ft AGL"


def test_flight_level_limits_render_as_fl_numbers():
    # UK danger areas publish flight levels (pressure datum STD); the
    # label is the aviation form, not "100 FL STD".
    fl = VerticalLimit(100.0, "FL", "STD")
    assert fl.label() == "FL 100"


@pytest.mark.parametrize(
    "raw",
    [
        "2026-06-30T21:00:00.0Z",
        "2026-06-30T21:00:00.00Z",  # Latvia's drz.lv file writes two digits (#594)
        "2026-06-30T21:00:00.000Z",
        "2026-06-30T21:00:00.000000Z",
        "2026-06-30T23:00:00.00+02:00",
    ],
)
def test_iso_utc_accepts_any_fractional_second_width(raw):
    # Python 3.10's fromisoformat takes only 3- or 6-digit fractions; the
    # feeds do not care, so the parser must not either.
    assert iso_utc(raw, "t") == datetime(2026, 6, 30, 21, 0)


def test_iso_utc_without_a_fraction_is_unchanged():
    assert iso_utc("2026-06-30T21:00:00Z", "t") == datetime(2026, 6, 30, 21, 0)
    assert iso_utc("2026-06-30T21:00:00+00:00", "t") == datetime(2026, 6, 30, 21, 0)


def test_iso_utc_still_rejects_garbage():
    with pytest.raises(AirspaceError, match="not an ISO datetime"):
        iso_utc("yesterday", "t")
