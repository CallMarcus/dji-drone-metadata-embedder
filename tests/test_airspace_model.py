"""Normalized airspace model (#413): shared by both providers and the evaluator."""
from dji_metadata_embedder.geo.airspace.model import VerticalLimit


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
