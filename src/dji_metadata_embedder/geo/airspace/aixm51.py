"""AIXM 5.1 UAS-restriction parser (#499): the UK NATS AIS dataset.

The authoritative product is an AIXM 5.1 BasicMessage: one
``aixm:Airspace`` per zone (single time slice, single volume), geometry
as GML curve segments — geodesic/line point runs, arcs and circles by
centre point, plus xlink references to in-document ``aixm:GeoBorder``
curves for coast/river-following boundaries. Arcs and circles are
densified here, deliberately: the sibling KML product ships pre-densified
with visual gaps between abutting volumes, the exact flaw a consistent
in-house densification avoids.

Arc sweep direction is untrustworthy in the wild (the 20260806 cycle
mixes clockwise and anticlockwise arcs), so each arc defaults to its
shorter sweep and the assembled ring is checked for self-intersection;
on failure every direction combination is tried until a simple ring
emerges (probe 2026-08-15: 543 of 548 arc-bearing zones take the shorter
sweep, 5 need the search, none unsolved).

Vertical limits arrive in feet and flight levels against SFC/MSL/STD
datums. An upper limit of FL 999 is the UK "unlimited" convention — a
sentinel mapped to "not stated", never rendered as a number (the Swiss
99999 lesson). Activation blocks (NOTAM-activated danger areas, prose
schedules) ride in ``native`` but never become applicability windows:
the evaluator treats a window's presence as machine-evaluable
time-bounding, and these are not.

Rights (issue #499): the dataset's own ISO 19115 metadata states
"Unrestricted" access and usage (not for resale; for aviation use only),
which governs over the site's copyright boilerplate.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urljoin

from .model import AirspaceError

_AIXM = "{http://www.aixm.aero/schema/5.1}"
_GML = "{http://www.opengis.net/gml/3.2}"
_XLINK = "{http://www.w3.org/1999/xlink}"
_XSI = "{http://www.w3.org/2001/XMLSchema-instance}"


@dataclass(frozen=True)
class Aixm51Feed:
    code: str
    page_url: str
    feed_name: str
    license: str
    caveat: str
    note: str | None = None


_CAVEAT = (
    "UAS flight-restriction data is informational and is not an "
    "authorization to fly."
)

AIXM_FEEDS: dict[str, Aixm51Feed] = {
    "GB": Aixm51Feed(
        code="GB",
        page_url=(
            "https://nats-uk.ead-it.com/cms-nats/opencms/en/Publications/"
            "digital-datasets/"
        ),
        feed_name="UK UAS flight restrictions (AIXM 5.1, NATS AIS)",
        license=(
            "© NATS Limited — UK UAS Flight Restrictions dataset; usage "
            "unrestricted per the product's ISO 19115 metadata (not for "
            "resale; for aviation use only)"
        ),
        caveat=_CAVEAT,
        note=(
            "Activation hours are not in the dataset and are not "
            "evaluated here (many danger areas are part-time; the AIP "
            "and NOTAM service hold the hours). Temporary restrictions "
            "live in NOTAMs and AIP Supplements, not in this record."
        ),
    ),
}

# The page lists the current AND next AIRAC cycle as dated zips; only
# the XML product is authoritative (the KML sibling is visualisation).
_ZIP_HREF_RE = re.compile(
    r'href="([^"]*UAS_AREA_1/EG_UAS_FR_DS_AREA1_FULL_(\d{8})_XML\.zip)"',
    re.IGNORECASE,
)


def discover_feed_url(page: bytes, page_url: str, *, today: date) -> str:
    """The currently-effective dataset zip URL from the datasets page.

    A cycle takes effect at 00:00 UTC on its filename date, so the
    newest listed date that is not in the future wins; a page listing
    only future cycles falls back to the oldest one."""
    dated: list[tuple[date, str]] = []
    for href, ymd in _ZIP_HREF_RE.findall(
        page.decode("utf-8", errors="replace")
    ):
        try:
            effective = datetime.strptime(ymd, "%Y%m%d").date()
        except ValueError:
            continue
        dated.append((effective, href.replace("&amp;", "&")))
    if not dated:
        raise AirspaceError(
            "could not find the UAS flight-restrictions dataset on the "
            f"NATS page ({page_url}) — the page layout may have changed"
        )
    current = [(d, h) for d, h in dated if d <= today]
    _, href = max(current) if current else min(dated)
    return urljoin(page_url, href)


_XML_MEMBER_RE = re.compile(r"EG_UAS_FR_DS_AREA1_FULL_\d{8}\.xml$")


def extract_xml(zip_bytes: bytes) -> bytes:
    """The dataset XML out of the downloaded archive, verified against
    the archive's own SHA-256 sidecar."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise AirspaceError(f"dataset archive is not a zip ({exc})") from exc
    with archive:
        names = archive.namelist()
        xml_names = [n for n in names if _XML_MEMBER_RE.search(n)]
        if len(xml_names) != 1:
            raise AirspaceError(
                f"expected one dataset XML in the archive, found "
                f"{len(xml_names)}"
            )
        body = archive.read(xml_names[0])
        sha_names = [n for n in names if n.endswith(".sha256")]
        if len(sha_names) != 1:
            raise AirspaceError(
                "no SHA-256 sidecar in the dataset archive"
            )
        sidecar = archive.read(sha_names[0]).decode("ascii", "replace")
        expected = sidecar.split()[0].lower() if sidecar.split() else ""
    if hashlib.sha256(body).hexdigest() != expected:
        raise AirspaceError(
            "dataset XML failed the archive's own SHA-256 integrity check"
        )
    return body
