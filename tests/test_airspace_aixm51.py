"""AIXM 5.1 provider tests (#499): UK NATS AIS UAS flight restrictions.

The authoritative product is an AIXM 5.1 BasicMessage inside a zip with
its own SHA-256 sidecar, published per AIRAC cycle with dated filenames;
the current AND next cycle are both listed, so discovery is date-aware.
"""
import hashlib
import io
import zipfile
from datetime import date
from pathlib import Path

import pytest

from dji_metadata_embedder.geo.airspace import AirspaceError, SourceInfo
from dji_metadata_embedder.geo.airspace.aixm51 import (
    AIXM_FEEDS,
    discover_feed_url,
    extract_xml,
)

FIXTURES = Path(__file__).parent.parent / "samples" / "airspace"
SRC = SourceInfo(
    feed="test", url="https://example.invalid/datasets",
    fetched="2026-08-15T12:00:00Z",
    license="test", caveat="informational only",
)

PAGE = (
    b'<a href="/x/UAS_AREA_1/EG_UAS_FR_DS_AREA1_FULL_20260806_KML.zip">k</a>'
    b'<a href="/x/UAS_AREA_1/EG_UAS_FR_DS_AREA1_FULL_20260806_XML.zip">x</a>'
    b'<a href="/x/UAS_AREA_1/EG_UAS_FR_DS_AREA1_FULL_20260903_KML.zip">k</a>'
    b'<a href="/x/UAS_AREA_1/EG_UAS_FR_DS_AREA1_FULL_20260903_XML.zip">x</a>'
)
BASE = "https://nats-uk.ead-it.com/cms-nats/opencms/en/Publications/digital-datasets/"


def test_discovery_picks_the_effective_cycle_not_the_next_one():
    # Both the current and the NEXT AIRAC cycle are on the page; a cycle
    # takes effect at 00:00 UTC on its filename date.
    url = discover_feed_url(PAGE, BASE, today=date(2026, 8, 15))
    assert url.endswith("EG_UAS_FR_DS_AREA1_FULL_20260806_XML.zip")
    assert url.startswith("https://nats-uk.ead-it.com/x/")


def test_discovery_rolls_over_on_the_cycle_date():
    url = discover_feed_url(PAGE, BASE, today=date(2026, 9, 3))
    assert "20260903_XML" in url


def test_discovery_falls_back_to_the_oldest_when_all_dates_are_future():
    url = discover_feed_url(PAGE, BASE, today=date(2026, 8, 1))
    assert "20260806_XML" in url


def test_discovery_never_picks_the_kml_product():
    kml_only = PAGE.replace(b"_XML.zip", b"_XKL.zip")
    with pytest.raises(AirspaceError, match="NATS"):
        discover_feed_url(kml_only, BASE, today=date(2026, 8, 15))


def _zip(xml: bytes, *, sha: str | None = None,
         xml_name: str = "EG_UAS_FR_DS_AREA1_FULL_20260806.xml") -> bytes:
    digest = sha if sha is not None else hashlib.sha256(xml).hexdigest()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(xml_name, xml)
        zf.writestr(
            "EG_UAS_FR_DS_AREA1_FULL_20260806.sha256",
            f"{digest} *{xml_name}",
        )
    return buf.getvalue()


def test_extract_verifies_the_archives_own_sha256():
    assert extract_xml(_zip(b"<xml/>")) == b"<xml/>"


def test_a_sha_mismatch_is_an_error_not_a_silent_accept():
    with pytest.raises(AirspaceError, match="SHA-256"):
        extract_xml(_zip(b"<xml/>", sha="0" * 64))


def test_an_archive_without_the_dataset_xml_is_an_error():
    with pytest.raises(AirspaceError, match="dataset XML"):
        extract_xml(_zip(b"<xml/>", xml_name="export-filter.xml"))


def test_a_non_zip_body_is_an_error():
    with pytest.raises(AirspaceError, match="zip"):
        extract_xml(b"<html>login wall</html>")


def test_gb_feed_registry_states_source_rights_and_honesty_note():
    feed = AIXM_FEEDS["GB"]
    assert feed.page_url.startswith("https://nats-uk.ead-it.com/")
    assert "NATS" in feed.license and "ISO 19115" in feed.license
    assert "not for resale" in feed.license
    note = feed.note or ""
    assert "Activation hours" in note and "Temporary restrictions" in note
