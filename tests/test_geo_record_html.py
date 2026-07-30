"""Record HTML structure tests (#413): labels, caveats, no verdicts."""
from datetime import datetime

from dji_metadata_embedder.geo.airspace import (
    AirspaceReport,
    SourceInfo,
    VerticalLimit,
    Zone,
)
from dji_metadata_embedder.geo.airspace.evaluate import ZoneFinding
from dji_metadata_embedder.geo.record import FlightRecordData
from dji_metadata_embedder.geo.record_html import record_to_html, write_flight_record

SRC = SourceInfo(
    feed="Luxembourg UAS geographical zones (ED-269)",
    url="https://drones.geoportail.lu/zones",
    fetched="2026-07-30T12:00:00Z", license="CC0 (data.public.lu)",
    caveat="informational only, not an authorization",
    note=None,
)
ZONE = Zone(
    identifier="LU-P-001", name="Findel <CTR>", restriction="PROHIBITED",
    lower=VerticalLimit(0, "m", "AGL"), upper=VerticalLimit(120, "m", "AGL"),
    applicability=[], polygons=[[(6.18, 49.61), (6.24, 49.61), (6.24, 49.65),
                                 (6.18, 49.65), (6.18, 49.61)]],
    source=SRC, native={},
)


def _record(**over):
    base = dict(
        name="LUX0001", start_utc=datetime(2026, 7, 30, 12, 0),
        end_utc=datetime(2026, 7, 30, 12, 3), duration_s=180.0,
        takeoff=(49.615, 6.19), distance_m=350.0, max_home_m=120.0,
        max_rel_alt_m=30.0, max_surface_m=33.5,
        surface_note=None, max_amsl_m=303.0, time_note=None,
        measure_note="Regulation (EU) 2019/947 ... makes no determination.",
        airspace=AirspaceReport(
            findings=[ZoneFinding(
                zone=ZONE, entered=True,
                entry_utc=datetime(2026, 7, 30, 12, 1),
                exit_utc=datetime(2026, 7, 30, 12, 2),
                max_rel_alt_m=30.0, max_surface_m=33.5, max_amsl_m=303.0,
            )],
            source=SRC,
        ),
        points=[(49.615, 6.19), (49.618, 6.19)],
    )
    base.update(over)
    return FlightRecordData(**base)


def test_the_three_label_height_block_is_present():
    html = record_to_html([_record()], "My flights", "2.4.0")
    assert "above takeoff point" in html and "aircraft-reported" in html
    assert "estimated" in html.lower() and "surface model" in html.lower()
    assert "not the measure the regulations use" in html.lower() or \
        "not the legal measure" in html.lower()


def test_sources_caveats_and_footer_identify_the_record():
    html = record_to_html([_record()], "My flights", "2.4.0")
    assert "drones.geoportail.lu" in html
    assert "2026-07-30T12:00:00Z" in html
    assert "CC0" in html and "informational" in html
    assert "dji-embed 2.4.0" in html
    assert "factual record, not a determination" in html


def test_no_verdict_vocabulary_ever():
    html = record_to_html([_record()], "t", "2.4.0").lower()
    for word in ("legal", "illegal", "compliant", "violation"):
        assert word not in html


def test_zone_names_are_escaped():
    html = record_to_html([_record()], "t", "2.4.0")
    assert "Findel <CTR>" not in html and "Findel &lt;CTR&gt;" in html


def test_unavailable_surface_height_is_a_stated_row_not_a_blank():
    rec = _record(max_surface_m=None,
                  surface_note="the [terrain] extra is not installed")
    html = record_to_html([rec], "t", "2.4.0")
    assert "unavailable" in html and "[terrain]" in html


def test_gap_reason_renders_when_no_provider_covers_the_flight():
    rec = _record(measure_note=None,
                  airspace=AirspaceReport(gap_reason="no supported airspace data source for this location"))
    html = record_to_html([rec], "t", "2.4.0")
    assert "no supported airspace data source" in html


def test_svg_outline_and_print_css_are_embedded():
    html = record_to_html([_record()], "t", "2.4.0")
    assert "<svg" in html and "polyline" in html
    assert "@media print" in html


def test_write_flight_record_writes_utf8(tmp_path):
    out = write_flight_record([_record()], tmp_path / "flight-record.html", "t")
    assert out.exists()
    assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")
