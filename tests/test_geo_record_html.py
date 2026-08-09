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


def test_record_carries_the_generator_comment():
    from dji_metadata_embedder.geo.provenance import generator_comment

    html = record_to_html([_record()], "My flights", "2.4.0")
    assert html.startswith("<!DOCTYPE html>\n" + generator_comment())


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


def test_terrain_source_renders_even_with_no_airspace_source():
    rec = _record(
        measure_note=None,
        airspace=AirspaceReport(gap_reason="no supported airspace data source"),
        terrain_source=(
            "Mapterhorn terrain tiles (tiles.mapterhorn.com) — Copernicus "
            "GLO-30-based surface model, includes vegetation and buildings"
        ),
    )
    html = record_to_html([rec], "t", "2.4.0")
    assert "Data &amp; caveats" in html
    assert "tiles.mapterhorn.com" in html
    assert "Mapterhorn terrain tiles" in html


def test_only_entered_zones_get_a_table_row_with_a_not_entered_summary():
    other = Zone(
        identifier="LU-P-999", name="Not entered zone", restriction="PROHIBITED",
        lower=VerticalLimit(0, "m", "AGL"), upper=VerticalLimit(50, "m", "AGL"),
        applicability=[], polygons=[[(9.0, 49.0), (9.1, 49.0), (9.1, 49.1),
                                     (9.0, 49.1), (9.0, 49.0)]],
        source=SRC, native={},
    )
    other2 = Zone(
        identifier="LU-P-998", name="Also not entered", restriction="PROHIBITED",
        lower=VerticalLimit(0, "m", "AGL"), upper=VerticalLimit(50, "m", "AGL"),
        applicability=[], polygons=[[(9.0, 49.0), (9.1, 49.0), (9.1, 49.1),
                                     (9.0, 49.1), (9.0, 49.0)]],
        source=SRC, native={},
    )
    rec = _record(
        airspace=AirspaceReport(
            findings=[
                ZoneFinding(
                    zone=ZONE, entered=True,
                    entry_utc=datetime(2026, 7, 30, 12, 1),
                    exit_utc=datetime(2026, 7, 30, 12, 2),
                    max_rel_alt_m=30.0, max_surface_m=33.5, max_amsl_m=303.0,
                ),
                ZoneFinding(zone=other, entered=False),
                ZoneFinding(zone=other2, entered=False),
            ],
            source=SRC,
        ),
    )
    html = record_to_html([rec], "t", "2.4.0")
    assert html.count("LU-P-001") == 1  # exactly one data row for the entered zone
    assert "Findel &lt;CTR&gt;" in html
    assert "Not entered zone" not in html
    assert "Also not entered" not in html
    assert "2 further zones in the evaluated area were not entered." in html


def test_a_single_not_entered_zone_uses_singular_agreement():
    other = Zone(
        identifier="LU-P-997", name="Not entered zone", restriction="PROHIBITED",
        lower=VerticalLimit(0, "m", "AGL"), upper=VerticalLimit(50, "m", "AGL"),
        applicability=[], polygons=[[(9.0, 49.0), (9.1, 49.0), (9.1, 49.1),
                                     (9.0, 49.1), (9.0, 49.0)]],
        source=SRC, native={},
    )
    rec = _record(
        airspace=AirspaceReport(
            findings=[
                ZoneFinding(
                    zone=ZONE, entered=True,
                    entry_utc=datetime(2026, 7, 30, 12, 1),
                    exit_utc=datetime(2026, 7, 30, 12, 2),
                    max_rel_alt_m=30.0, max_surface_m=33.5, max_amsl_m=303.0,
                ),
                ZoneFinding(zone=other, entered=False),
            ],
            source=SRC,
        ),
    )
    html = record_to_html([rec], "t", "2.4.0")
    assert "1 further zone in the evaluated area was not entered." in html
    assert "1 further zones" not in html and "was were" not in html


def test_write_flight_record_writes_utf8(tmp_path):
    out = write_flight_record([_record()], tmp_path / "flight-record.html", "t")
    assert out.exists()
    assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")


# #422 item 2: a zone with only a stated lowerLimit (ED-269 permits it)
# must state its floor, not claim "not stated" / "no stated limit".
def test_a_lower_limit_only_zone_states_its_floor():
    floor_zone = Zone(
        identifier="FI-R-77", name="Begins above floor",
        restriction="REQ_AUTHORISATION",
        lower=VerticalLimit(500, "ft", "AMSL"), upper=None,
        applicability=[], polygons=ZONE.polygons, source=SRC, native={},
    )
    rec = _record(airspace=AirspaceReport(
        findings=[ZoneFinding(
            zone=floor_zone, entered=True,
            entry_utc=datetime(2026, 7, 30, 12, 1),
            exit_utc=datetime(2026, 7, 30, 12, 2),
            max_amsl_m=303.0,
        )],
        source=SRC,
    ))
    html = record_to_html([rec], "t", "2.4.0")
    assert "from 500 ft AMSL" in html
    assert "no stated limit" not in html
    # The comparison follows the floor's datum (AMSL here).
    assert "max altitude (amsl) during dwell" in html.lower()


def test_a_zone_with_no_limits_at_all_still_says_not_stated():
    bare = Zone(
        identifier="FI-R-78", name="No limits", restriction="REQ_AUTHORISATION",
        lower=None, upper=None,
        applicability=[], polygons=ZONE.polygons, source=SRC, native={},
    )
    rec = _record(airspace=AirspaceReport(
        findings=[ZoneFinding(zone=bare, entered=True,
                              entry_utc=datetime(2026, 7, 30, 12, 1),
                              exit_utc=datetime(2026, 7, 30, 12, 2))],
        source=SRC,
    ))
    html = record_to_html([rec], "t", "2.4.0")
    assert "not stated" in html
    assert "no stated limit to compare against" in html


# #422 item 1: the cover table shows local + UTC times and the estimated
# max height above surface (the spec's logbook columns).
def _cover(html: str) -> str:
    return html.split("<table class='cover'>")[1].split("</table>")[0]


def test_cover_shows_local_and_utc_times_when_offset_known():
    from datetime import timedelta

    rec = _record(local_offset=timedelta(hours=2))
    cover = _cover(record_to_html([rec], "t", "2.4.0"))
    assert "14:00:00 +02:00" in cover      # 12:00 UTC start, +02:00
    assert "12:00:00 UTC" in cover
    assert "14:03:00 +02:00" in cover      # end


def test_cover_dates_follow_local_time_across_midnight():
    from datetime import timedelta

    rec = _record(
        start_utc=datetime(2026, 7, 30, 23, 30),
        end_utc=datetime(2026, 7, 30, 23, 40),
        local_offset=timedelta(hours=2),
    )
    cover = _cover(record_to_html([rec], "t", "2.4.0"))
    assert "2026-07-31" in cover           # the pilot's logbook date


def test_cover_without_offset_states_utc_only():
    cover = _cover(record_to_html([_record()], "t", "2.4.0"))
    assert "12:00:00 UTC" in cover
    assert "+02:00" not in cover


def test_cover_shows_both_height_columns_with_labelled_datums():
    # The spec's logbook row carries BOTH heights: max above takeoff and
    # est. max above surface (review finding: replacing one with the other
    # left a terrain-less install with only "unavailable" rows).
    html = record_to_html([_record()], "t", "2.4.0")
    header = html.split("<table class='cover'>")[1].split("</tr>")[0]
    assert "above takeoff" in header
    assert "est. above surface" in header
    cover = _cover(html)
    assert "30 m" in cover             # max_rel_alt_m
    assert "34 m" in cover             # max_surface_m 33.5 -> "34 m"


def test_cover_surface_unavailable_is_stated():
    rec = _record(max_surface_m=None, surface_note="no terrain data")
    cover = _cover(record_to_html([rec], "t", "2.4.0"))
    assert "unavailable" in cover


def test_cover_surface_column_alone_can_be_unavailable():
    from datetime import timedelta as _td  # noqa: F401  (kept for symmetry)

    rec = _record(max_surface_m=None, surface_note="no terrain data")
    cover = _cover(record_to_html([rec], "t", "2.4.0"))
    assert "unavailable" in cover
    assert "30 m" in cover             # the takeoff figure is still there


# Review findings on #432: banded limits, the horizontal-entry footnote,
# per-cell date datums, and offset-label edge cases.
def test_a_banded_zone_states_floor_and_ceiling():
    banded = Zone(
        identifier="EFHKUASC", name="Helsinki C", restriction="REQ_AUTHORISATION",
        lower=VerticalLimit(50, "m", "AGL"), upper=VerticalLimit(120, "m", "AGL"),
        applicability=[], polygons=ZONE.polygons, source=SRC, native={},
    )
    rec = _record(airspace=AirspaceReport(
        findings=[ZoneFinding(
            zone=banded, entered=True,
            entry_utc=datetime(2026, 7, 30, 12, 1),
            exit_utc=datetime(2026, 7, 30, 12, 2), max_surface_m=33.5,
        )], source=SRC))
    html = record_to_html([rec], "t", "2.4.0")
    assert "50&#x2013;120 m AGL" in html or "50–120 m AGL" in html
    assert ">120 m AGL<" not in html   # never the ceiling alone


def test_a_zero_floor_renders_the_ceiling_alone():
    # The FAA shape: lower is always 0 ft AGL — "0–400" would be noise.
    faa_like = Zone(
        identifier="UASFM-1", name="Cell", restriction="CEILING",
        lower=VerticalLimit(0, "ft", "AGL"), upper=VerticalLimit(400, "ft", "AGL"),
        applicability=[], polygons=ZONE.polygons, source=SRC, native={},
    )
    rec = _record(airspace=AirspaceReport(
        findings=[ZoneFinding(
            zone=faa_like, entered=True,
            entry_utc=datetime(2026, 7, 30, 12, 1),
            exit_utc=datetime(2026, 7, 30, 12, 2),
            max_surface_m=33.5, max_amsl_m=303.0,
        )], source=SRC))
    html = record_to_html([rec], "t", "2.4.0")
    assert "400 ft AGL" in html
    assert "0" + "\u2013" not in html and "0-400" not in html


def test_a_mixed_datum_band_prints_each_sides_datum():
    mixed = Zone(
        identifier="X", name="Mixed", restriction="REQ_AUTHORISATION",
        lower=VerticalLimit(500, "ft", "AMSL"), upper=VerticalLimit(120, "m", "AGL"),
        applicability=[], polygons=ZONE.polygons, source=SRC, native={},
    )
    rec = _record(airspace=AirspaceReport(
        findings=[ZoneFinding(
            zone=mixed, entered=True,
            entry_utc=datetime(2026, 7, 30, 12, 1),
            exit_utc=datetime(2026, 7, 30, 12, 2),
            max_surface_m=33.5, max_amsl_m=303.0,
        )], source=SRC))
    html = record_to_html([rec], "t", "2.4.0")
    assert "500 ft AMSL" in html and "120 m AGL" in html


def test_entered_is_defined_as_horizontal_below_the_airspace_table():
    html = record_to_html([_record()], "t", "2.4.0")
    assert "Entry is horizontal" in html
    assert "makes no determination" in html


def test_cover_date_cells_carry_their_datum():
    from datetime import timedelta

    with_offset = _record(local_offset=timedelta(hours=2))
    cover = _cover(record_to_html([with_offset], "t", "2.4.0"))
    assert "<small>local</small>" in cover
    cover_utc = _cover(record_to_html([_record()], "t", "2.4.0"))
    assert "<small>UTC</small>" in cover_utc


def test_cover_utc_line_keeps_the_date_for_midnight_crossings():
    from datetime import timedelta

    rec = _record(
        start_utc=datetime(2026, 7, 30, 23, 30),
        end_utc=datetime(2026, 7, 30, 23, 40),
        local_offset=timedelta(hours=2),
    )
    cover = _cover(record_to_html([rec], "t", "2.4.0"))
    assert "2026-07-30 23:30:00 UTC" in cover   # the UTC line self-dates


def test_negative_and_odd_offsets_label_correctly():
    from datetime import timedelta

    rec = _record(local_offset=timedelta(hours=-5, minutes=-30))
    cover = _cover(record_to_html([rec], "t", "2.4.0"))
    assert "06:30:00 -05:30" in cover           # 12:00 UTC at -05:30


def test_a_zero_offset_renders_utc_only():
    from datetime import timedelta

    rec = _record(local_offset=timedelta(0))
    cover = _cover(record_to_html([rec], "t", "2.4.0"))
    assert "+00:00" not in cover
    assert "12:00:00 UTC" in cover


def test_an_offset_with_unknown_times_stays_unknown():
    from datetime import timedelta

    rec = _record(start_utc=None, end_utc=None,
                  local_offset=timedelta(hours=2))
    cover = _cover(record_to_html([rec], "t", "2.4.0"))
    assert "unknown" in cover
