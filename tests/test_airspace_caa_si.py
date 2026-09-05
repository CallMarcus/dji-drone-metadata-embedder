"""Slovenia CAA KMZ provider tests (#565) against the trimmed real fixture.

The CAA publishes a Google Earth export: one zip → one kmz → ``doc.kml``.
Every zone attribute lives in the placemark's popup HTML table and the
field names differ per folder, so the parser is a tolerant mapper and the
tests pin each mapping case the live file exhibits.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from dji_metadata_embedder.geo.airspace.caa_si import (
    CAA_SI_FEEDS,
    caa_si_effective,
    discover_feed_url,
    parse_caa_si,
)
from dji_metadata_embedder.geo.airspace.model import AirspaceError, SourceInfo

FIXTURE = Path(__file__).parent.parent / "samples" / "airspace" / "caa-si.kml"
PAGE_URL = "https://www.caa.si/geografske-omejitve-za-uas.html"
SOURCE = SourceInfo(
    feed="Slovenia UAS geographical zones (CAA)",
    url=PAGE_URL,
    fetched="2026-09-05T12:00:00Z",
    license="test",
    caveat="test",
)


def wrap(kml: bytes, kmz_name: str = "UAS Geo zones - May_2026.kmz",
         stamp: tuple = (2026, 5, 25, 13, 39, 0),
         inner_name: str = "doc.kml") -> bytes:
    """The live nesting: zip → kmz (itself a zip) → doc.kml, with the kmz
    member carrying the publication timestamp."""
    kmz = io.BytesIO()
    with zipfile.ZipFile(kmz, "w") as z:
        z.writestr(inner_name, kml)
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as z:
        info = zipfile.ZipInfo(kmz_name, date_time=stamp)
        z.writestr(info, kmz.getvalue())
    return outer.getvalue()


def fixture_zones():
    return parse_caa_si(wrap(FIXTURE.read_bytes()), SOURCE)


def zone(zones, ident):
    return next(z for z in zones if z.identifier == ident)


KML_HEAD = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>t</name>'
)
KML_TAIL = b"</Document></kml>"


def placemark(name: str, rows: str, coords: str,
              inner: str | None = None, folder: str = "Test") -> bytes:
    hole = (
        f"<innerBoundaryIs><LinearRing><coordinates>{inner}</coordinates>"
        f"</LinearRing></innerBoundaryIs>" if inner else ""
    )
    desc = (
        "&lt;html&gt;&lt;body&gt;&lt;table&gt;"
        + rows.replace("<", "&lt;").replace(">", "&gt;")
        + "&lt;/table&gt;&lt;/body&gt;&lt;/html&gt;"
    )
    return (
        f"<Folder><name>{folder}</name><Placemark><name>{name}</name>"
        f"<description>{desc}</description><MultiGeometry><Polygon>"
        f"<outerBoundaryIs><LinearRing><coordinates>{coords}</coordinates>"
        f"</LinearRing></outerBoundaryIs>{hole}</Polygon></MultiGeometry>"
        f"</Placemark></Folder>"
    ).encode("utf-8")


SQUARE = "14.5,46.0,0 14.6,46.0,0 14.6,46.1,0 14.5,46.1,0 14.5,46.0,0"
SQUARE_HOLE = "14.52,46.02,0 14.58,46.02,0 14.58,46.08,0 14.52,46.08,0 14.52,46.02,0"


# --- registry, discovery, unpacking, edition ---------------------------------

def test_registry_states_the_caa_terms_and_the_populated_area_gap():
    feed = CAA_SI_FEEDS["SI"]
    assert feed.page_url == PAGE_URL
    assert "caa.si" in feed.license and "unchanged" in feed.license
    assert feed.note is not None and "populated-area" in feed.note
    assert "NOTAM" in feed.note


def test_discovery_finds_the_single_zip_href_and_resolves_it():
    page = (
        b'<p>Omejitve ...: <a href="https://caa-slovenia.maps.arcgis.com/x">'
        b'3D aplikacija</a>, <a href="/upload/editor/file/filef72ffaa1afe7b46.zip">'
        b'ezyZip_maj 2026.zip</a></p>'
    )
    assert discover_feed_url(page, PAGE_URL) == (
        "https://www.caa.si/upload/editor/file/filef72ffaa1afe7b46.zip"
    )


def test_discovery_fails_loudly_on_zero_or_several_zip_hrefs():
    with pytest.raises(AirspaceError, match="caa.si"):
        discover_feed_url(b"<a href='/upload/editor/file/x.pdf'>x</a>", PAGE_URL)
    two = (b'<a href="/upload/editor/file/a.zip">a</a>'
           b'<a href="/upload/editor/file/b.zip">b</a>')
    with pytest.raises(AirspaceError, match="2"):
        discover_feed_url(two, PAGE_URL)


def test_edition_date_is_the_kmz_members_timestamp():
    assert caa_si_effective(wrap(FIXTURE.read_bytes())) == "2026-05-25"


def test_edition_date_is_absent_when_the_body_is_not_a_zip():
    assert caa_si_effective(b"not a zip") is None


def test_unpacking_errors_name_the_missing_layer():
    with pytest.raises(AirspaceError, match="zip"):
        parse_caa_si(b"not a zip", SOURCE)
    no_kmz = io.BytesIO()
    with zipfile.ZipFile(no_kmz, "w") as z:
        z.writestr("readme.txt", b"x")
    with pytest.raises(AirspaceError, match="kmz"):
        parse_caa_si(no_kmz.getvalue(), SOURCE)
    with pytest.raises(AirspaceError, match="kml"):
        parse_caa_si(wrap(b"<kml/>", inner_name="styles.xsl"), SOURCE)


# --- the fixture: one placemark per representative folder --------------------

def test_parses_the_nine_fixture_placemarks_with_folder_based_identifiers():
    zones = fixture_zones()
    assert [z.identifier for z in zones] == [
        "SI-polygons-1", "SI-uas-ursiks-1", "SI-ctr-wgs-1", "SI-modelarskecone-1",
        "SI-restricted-area-1", "SI-jek-prohibited-1", "SI-tnp-wgs-1",
        "SI-danger-1", "SI-luka-koper-25-1",
    ]
    for z in zones:
        assert z.lower is None and z.applicability == []
        assert z.native["folder"]
        for ring in z.polygons:
            assert ring[0] == ring[-1] and len(ring) >= 4
            assert all(len(pt) == 2 for pt in ring)
            assert all(13.0 < lon < 17.0 and 45.0 < lat < 47.0 for lon, lat in ring)


def test_prohibited_heliport_keeps_its_exceptions_and_contact_as_notes():
    z = zone(fixture_zones(), "SI-polygons-1")
    assert z.name == "Heliport UKC Ljubljana"
    assert z.restriction == "PROHIBITED"
    assert z.upper is None
    assert ("Exceptions: Approval from heliport + valid certificate for "
            "subcategory A2") in z.notes
    assert "Kontakt: heliport@kclj.si" in z.notes
    # ArcGIS export furniture never reaches the reader
    assert not any(n.startswith(("FolderPath", "SymbolID", "PopupInfo", "FID"))
                   for n in z.notes)
    assert z.polygons[0][0] == pytest.approx((14.52056, 46.07173), abs=1e-5)


def test_prison_zone_states_its_published_height_as_the_upper_limit():
    z = zone(fixture_zones(), "SI-uas-ursiks-1")
    assert z.restriction == "PROHIBITED"
    assert z.upper is not None and z.upper.label() == "150 m AGL"
    assert any(n.startswith("Regulation: Act on the Execution") for n in z.notes)


def test_ctr_allowed_up_to_50_m_is_conditional_with_that_ceiling():
    z = zone(fixture_zones(), "SI-ctr-wgs-1")
    assert z.name == "Kontrolirana cona (CTR Ljubljana)"
    assert z.restriction == "CONDITIONAL"
    assert z.upper is not None and z.upper.label() == "50 m AGL"


def test_model_flying_permit_zone_is_conditional():
    z = zone(fixture_zones(), "SI-modelarskecone-1")
    assert z.restriction == "CONDITIONAL"
    assert z.upper is None


def test_restricted_area_without_a_statement_says_so_and_points_at_notam():
    z = zone(fixture_zones(), "SI-restricted-area-1")
    assert z.name == "LJ R6A restricted"
    assert z.restriction == "Restriction not stated (check NOTAM)"
    assert any("sloveniacontrol.si" in n for n in z.notes)


def test_nuclear_plant_and_national_park_are_prohibited_in_either_case():
    zones = fixture_zones()
    assert zone(zones, "SI-jek-prohibited-1").restriction == "PROHIBITED"
    assert zone(zones, "SI-tnp-wgs-1").restriction == "PROHIBITED"   # "prepovedano"


def test_junk_placemark_names_fall_back_to_the_popup_name_row():
    zones = fixture_zones()
    assert zone(zones, "SI-danger-1").name == "LJD1 - Danger area"      # was "33297.328…"
    assert zone(zones, "SI-luka-koper-25-1").name == "Luka Koper"      # was "22"
    assert zone(zones, "SI-luka-koper-25-1").restriction == "PROHIBITED"


# --- synthetic edge cases ----------------------------------------------------

def test_inner_rings_become_holes():
    kml = KML_HEAD + placemark(
        "Hole zone", "<tr><td>Omejitev</td><td>Prepovedano</td></tr>",
        SQUARE, inner=SQUARE_HOLE,
    ) + KML_TAIL
    z = parse_caa_si(wrap(kml), SOURCE)[0]
    assert len(z.polygons) == 1 and len(z.holes) == 1
    assert z.holes[0][0] == (14.52, 46.02)


def test_an_unseen_restriction_wording_fails_loudly_naming_the_zone():
    kml = KML_HEAD + placemark(
        "Odd zone", "<tr><td>Omejitev</td><td>Dovoljeno s pogoji</td></tr>", SQUARE,
    ) + KML_TAIL
    with pytest.raises(AirspaceError, match="Odd zone"):
        parse_caa_si(wrap(kml), SOURCE)


def test_a_placemark_without_polygon_geometry_fails_loudly():
    kml = KML_HEAD + (
        b"<Folder><name>F</name><Placemark><name>Pt</name>"
        b"<description>x</description><Point><coordinates>14.5,46.0,0"
        b"</coordinates></Point></Placemark></Folder>"
    ) + KML_TAIL
    with pytest.raises(AirspaceError, match="Pt"):
        parse_caa_si(wrap(kml), SOURCE)


def test_nested_folders_are_walked_and_indexed_per_folder():
    inner_a = placemark("A1", "<tr><td>Omejitev</td><td>Prepovedano</td></tr>", SQUARE, folder="Inner")
    kml = KML_HEAD + b"<Folder><name>Outer</name>" + inner_a + placemark(
        "O1", "<tr><td>Omejitev</td><td>Prepovedano</td></tr>", SQUARE, folder="Outer"
    ) + b"</Folder>" + KML_TAIL
    ids = [z.identifier for z in parse_caa_si(wrap(kml), SOURCE)]
    assert sorted(ids) == ["SI-inner-1", "SI-outer-1"]
