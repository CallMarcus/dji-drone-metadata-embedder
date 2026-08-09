"""The provenance stamp: every emitted page names its generator.

The comment is honest metadata (view-source only); the credit link joins
the attribution strip only on pages that already have one. Both are
single-sourced in geo/provenance.py so wording and version cannot drift
between writers.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from dji_metadata_embedder import __version__
from dji_metadata_embedder.geo.flightmap3d_html import flights_to_3d_html
from dji_metadata_embedder.geo.flightmap_html import flights_to_html
from dji_metadata_embedder.geo.html_viewer import track_to_html
from dji_metadata_embedder.geo.panoedit_html import build_editor_page
from dji_metadata_embedder.geo.photomap import PhotoPoint
from dji_metadata_embedder.geo.photomap_html import photos_to_html
from dji_metadata_embedder.geo.provenance import (
    REPO_URL,
    attribution_credit,
    generator_comment,
    stamp,
)
from dji_metadata_embedder.geo.track import Track, TrackPoint

_TRACK = Track(name="DJI_0001", points=[
    TrackPoint(lat=10.0, lon=20.0, alt=5.0, timestamp="00:00:00,000",
               utc=datetime(2026, 6, 15, 12, 0, 0)),
    TrackPoint(lat=10.001, lon=20.001, alt=6.5, timestamp="00:00:01,000",
               utc=datetime(2026, 6, 15, 12, 1, 0)),
])

_PHOTOS = [PhotoPoint(lat=60.1, lon=24.9, alt=12.0, name="photo1.jpg")]


def test_comment_names_tool_version_and_repo():
    comment = generator_comment()
    assert comment.startswith("<!--") and comment.endswith("-->")
    assert "DJI Metadata Embedder" in comment
    assert __version__ in comment
    assert REPO_URL in comment


def test_stamp_lands_directly_after_the_doctype():
    html = stamp("<!DOCTYPE html>\n<html></html>")
    assert html.startswith("<!DOCTYPE html>\n" + generator_comment() + "\n")


@pytest.mark.parametrize("build", [
    lambda: photos_to_html(_PHOTOS, title="t"),
    lambda: flights_to_html([_TRACK], title="t"),
    lambda: flights_to_3d_html([_TRACK], "t"),
    lambda: track_to_html(_TRACK),
    lambda: build_editor_page("tok"),
], ids=["photomap", "flightmap", "flightmap3d", "viewer", "panoedit"])
def test_every_page_carries_the_generator_comment(build):
    assert generator_comment() in build()


@pytest.mark.parametrize("build", [
    lambda: photos_to_html(_PHOTOS, title="t"),
    lambda: flights_to_html([_TRACK], title="t"),
    lambda: flights_to_3d_html([_TRACK], "t"),
    lambda: track_to_html(_TRACK),
], ids=["photomap", "flightmap", "flightmap3d", "viewer"])
def test_map_pages_credit_the_generator_in_the_attribution(build):
    html = build()
    # Leaflet pages embed the attribution through json.dumps, which
    # escapes the credit's quotes; both spellings decode to the same DOM.
    escaped = attribution_credit().replace('"', '\\"')
    assert attribution_credit() in html or escaped in html
    assert "__CREDIT__" not in html


def test_the_editor_page_stays_credit_free():
    # panoedit is a localhost-only tool with no attribution control —
    # the visible credit belongs only on pages users publish.
    assert attribution_credit() not in build_editor_page("tok")
