"""Slovenia UAS geographical-zone parser (CAA Slovenia KMZ, #565).

The Javna agencija za civilno letalstvo RS publishes its UAS geographical
zones as a Google Earth export linked from its geographic-limits page: a
zip holding one ``.kmz``, itself a zip holding ``doc.kml``. Every zone is
a Placemark whose attributes live only in the popup HTML table of its
``description`` — and the table's field names differ per folder because
each folder is a different ArcGIS layer export ("UAS_omejit", "Omejitev",
"UAS omejitve" … all mean restriction). The parser is therefore a
tolerant mapper: keys are matched after diacritics and punctuation are
stripped, restriction wording is classified at the provider boundary, and
any wording this parser has never seen live fails loudly rather than being
guessed. The prose the CAA publishes alongside (exceptions, contacts,
reasons, regulations) rides verbatim in ``Zone.notes``.

Permission record: the CAA site's terms of use ("Avtorske pravice",
caa.si/pogoji-uporabe) permit storing, reproducing and distributing files
obtained from the site provided the source is visibly marked and the data
remain unchanged, with every reproduction accurate and the CAA named as
source. The zone content is carried unchanged; only the presentation is
ours.

Two limits the page itself states, both carried in the feed note: the
file does not contain the populated-area restrictions for the Open
category, and the CAA's 3D application is for flight notification only.
"""

from __future__ import annotations

import html
import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin
from xml.etree import ElementTree

from .model import AirspaceError, SourceInfo, VerticalLimit, Zone


@dataclass(frozen=True)
class CaaSiFeed:
    code: str
    page_url: str
    feed_name: str
    license: str
    caveat: str
    note: str | None = None


_CAVEAT = (
    "UAS geographical-zone data is informational and is not an "
    "authorization to fly."
)

CAA_SI_FEEDS: dict[str, CaaSiFeed] = {
    "SI": CaaSiFeed(
        code="SI",
        page_url="https://www.caa.si/geografske-omejitve-za-uas.html",
        feed_name="Slovenia UAS geographical zones (CAA)",
        license=(
            "© Javna agencija za civilno letalstvo RS (caa.si) — "
            "reproduction and distribution permitted with the source marked "
            "and the data unchanged (site terms of use)"
        ),
        caveat=_CAVEAT,
        note=(
            "The published file does not contain the populated-area (Open "
            "category) restrictions; the CAA's 3D application is for flight "
            "notification only. Restricted and danger areas refer to NOTAM "
            "(sloveniacontrol.si)."
        ),
    ),
}

# The page links exactly one zip (an opaque upload filename that churns
# between editions), so the page is what the registry pins and the zip
# href is discovered per fetch.
_ZIP_HREF_RE = re.compile(
    r"""href=["']([^"']*/upload/editor/file/[^"']+\.zip)["']""", re.IGNORECASE
)

_ROW_RE = re.compile(r"<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
# ArcGIS/Google Earth export furniture, never a published fact.
_FURNITURE = {
    "folderpath", "symbolid", "altmode", "base", "clamped", "extruded",
    "snippet", "popupinfo", "fid", "objectid", "id", "field",
    "shape length", "shape area", "lat", "lon",
}
# Name rows, in preference order, for placemarks whose own <name> is junk.
_NAME_KEYS = ("naziv", "name", "ime", "obmocje", "letalisce", "zone", "subject")
_JUNK_NAME_RE = re.compile(r"^(?:placemark|[0-9.\s]*)$", re.IGNORECASE)
_CEILING_RE = re.compile(
    r"(?:dovoljeno do|allowed up to)\D{0,40}?(\d+(?:[.,]\d+)?)\s*m\s*agl"
)


def discover_feed_url(page: bytes, page_url: str) -> str:
    """The current zones-zip URL from the CAA page's HTML."""
    hrefs = _ZIP_HREF_RE.findall(page.decode("utf-8", errors="replace"))
    if len(hrefs) != 1:
        raise AirspaceError(
            "expected exactly one UAS geo-zones zip on the caa.si page "
            f"({page_url}), found {len(hrefs)} — the page layout may have "
            "changed"
        )
    return urljoin(page_url, hrefs[0].replace("&amp;", "&"))


def _kmz_member(raw_zip: bytes, feed: str) -> tuple[zipfile.ZipInfo, bytes]:
    try:
        outer = zipfile.ZipFile(io.BytesIO(raw_zip))
    except zipfile.BadZipFile as exc:
        raise AirspaceError(f"{feed}: download is not a zip archive ({exc})") from exc
    members = [i for i in outer.infolist() if i.filename.lower().endswith(".kmz")]
    if len(members) != 1:
        raise AirspaceError(
            f"{feed}: expected one .kmz inside the zip, found {len(members)}"
        )
    return members[0], outer.read(members[0])


def _kml_bytes(raw_zip: bytes, feed: str) -> bytes:
    _, kmz = _kmz_member(raw_zip, feed)
    try:
        inner = zipfile.ZipFile(io.BytesIO(kmz))
    except zipfile.BadZipFile as exc:
        raise AirspaceError(f"{feed}: the .kmz is not a zip archive ({exc})") from exc
    names = [n for n in inner.namelist() if n.lower().endswith(".kml")]
    if len(names) != 1:
        raise AirspaceError(
            f"{feed}: expected one .kml inside the kmz, found {len(names)}"
        )
    return inner.read(names[0])


def caa_si_effective(raw_zip: bytes) -> str | None:
    """The edition the download says it is: the kmz member's own timestamp.

    The page names the edition only as a month ("maj 2026"); the kmz entry
    carries the day. A zip without a real timestamp (the 1980 epoch
    default) claims nothing."""
    try:
        info, _ = _kmz_member(raw_zip, "caa.si")
    except AirspaceError:
        return None
    year, month, day = info.date_time[:3]
    if year < 1990:
        return None
    return date(year, month, day).isoformat()


def _norm(key: str) -> str:
    folded = unicodedata.normalize("NFKD", key)
    ascii_only = "".join(c for c in folded if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", ascii_only.lower()).strip()


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _norm(name)).strip("-") or "folder"


def _rows(description: str | None) -> list[tuple[str, str]]:
    """The popup's attribute table as (key, value) pairs, tags stripped.

    The export wraps a title table around the attribute table; only the
    innermost table carries attributes, so parsing starts at the last
    ``<table``."""
    text = description or ""
    start = text.lower().rfind("<table")
    if start >= 0:
        text = text[start:]
    rows: list[tuple[str, str]] = []
    for raw_key, raw_value in _ROW_RE.findall(text):
        key = re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub("", raw_key))).strip()
        value = re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub("", raw_value))).strip()
        if not key or not value:
            continue
        if _norm(key) == "popupinfo" and "<table" in value.lower():
            # The Polygons-folder export (heliports, airfields) nests the
            # real attribute table one level down, as escaped HTML inside a
            # PopupInfo cell; unescaped above, it parses like any other.
            rows.extend(_rows(value))
            continue
        rows.append((key, value))
    return rows


def _restriction(values: list[str], where: str) -> tuple[str, VerticalLimit | None]:
    """The zone's restriction class from its published wording (any language).

    "dovoljeno do 50 m AGL" / "allowed up to 50 m AGL" is a conditional
    zone with that ceiling; "prepovedano / prohibited / forbidden" is
    PROHIBITED; a permit/approval regime (model-flying clubs) is
    CONDITIONAL. Anything else has never been seen live and fails loudly."""
    text = " | ".join(values)
    low = text.lower()
    ceiling = _CEILING_RE.search(low)
    if ceiling:
        metres = float(ceiling.group(1).replace(",", "."))
        return "CONDITIONAL", VerticalLimit(metres, "m", "AGL")
    if re.search(r"prepovedan|prohibit|forbidden", low):
        return "PROHIBITED", None
    if re.search(r"dovoljenje|permit|approval", low):
        return "CONDITIONAL", None
    raise AirspaceError(
        f"{where}: restriction wording {text!r} has not been seen live — "
        "refusing to guess a class"
    )


def _height_agl_m(rows: list[tuple[str, str]], where: str) -> VerticalLimit | None:
    for key, value in rows:
        norm = _norm(key)
        if "visina nad tlemi" in norm or "height agl" in norm:
            match = re.search(r"\d+(?:[.,]\d+)?", value)
            if not match:
                raise AirspaceError(f"{where}: height {value!r} is not a number")
            return VerticalLimit(float(match.group(0).replace(",", ".")), "m", "AGL")
    return None


def _is_restriction_key(norm: str) -> bool:
    return "omejit" in norm or "restrict" in norm


def _is_height_key(norm: str) -> bool:
    return "visina nad tlemi" in norm or "height agl" in norm


def _name(placemark_name: str | None, rows: list[tuple[str, str]],
          folder: str, index: int) -> str:
    own = (placemark_name or "").strip()
    if own and not _JUNK_NAME_RE.match(own):
        return own
    by_key = {_norm(k): v for k, v in rows}
    for key in _NAME_KEYS:
        if by_key.get(key):
            return by_key[key]
    return f"{folder} {index}"


def _coords(element: ElementTree.Element | None, ns: str, where: str
            ) -> list[tuple[float, float]]:
    text = element.findtext(f"{ns}LinearRing/{ns}coordinates") if element is not None else None
    if not text or not text.strip():
        raise AirspaceError(f"{where}: ring without coordinates")
    ring: list[tuple[float, float]] = []
    for token in text.split():
        parts = token.split(",")
        try:
            ring.append((float(parts[0]), float(parts[1])))
        except (IndexError, ValueError) as exc:
            raise AirspaceError(f"{where}: malformed coordinate {token!r}") from exc
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def _polygons(placemark: ElementTree.Element, ns: str, where: str
              ) -> tuple[list[list[tuple[float, float]]], list[list[tuple[float, float]]]]:
    polygons: list[list[tuple[float, float]]] = []
    holes: list[list[tuple[float, float]]] = []
    for polygon in placemark.iter(f"{ns}Polygon"):
        polygons.append(_coords(polygon.find(f"{ns}outerBoundaryIs"), ns, where))
        for inner in polygon.findall(f"{ns}innerBoundaryIs"):
            holes.append(_coords(inner, ns, where))
    if not polygons:
        raise AirspaceError(f"{where}: no polygon geometry")
    return polygons, holes


def parse_caa_si(raw_zip: bytes, source: SourceInfo) -> list[Zone]:
    """Every zone of the CAA's zones download as normalized :class:`Zone`s."""
    kml = _kml_bytes(raw_zip, source.feed)
    try:
        root = ElementTree.fromstring(kml)
    except ElementTree.ParseError as exc:
        raise AirspaceError(f"{source.feed}: doc.kml is not well-formed XML ({exc})") from exc
    ns = root.tag[: root.tag.index("}") + 1] if root.tag.startswith("{") else ""
    zones: list[Zone] = []
    containers = list(root.iter(f"{ns}Folder"))
    document = root.find(f"{ns}Document")
    if document is not None:
        containers.insert(0, document)
    for container in containers:
        folder = (container.findtext(f"{ns}name") or "").strip() or "document"
        slug = _slug(folder)
        for index, placemark in enumerate(container.findall(f"{ns}Placemark"), 1):
            raw_name = placemark.findtext(f"{ns}name")
            rows = _rows(placemark.findtext(f"{ns}description"))
            name = _name(raw_name, rows, folder, index)
            where = f"{source.feed}: {folder} / {name}"
            restriction_values = [v for k, v in rows if _is_restriction_key(_norm(k))]
            if restriction_values:
                restriction, upper = _restriction(restriction_values, where)
            else:
                # The restricted/danger areas publish only a name and a
                # "check NOTAM" pointer: no class is stated, so none is invented.
                restriction, upper = "Restriction not stated (check NOTAM)", None
            height = _height_agl_m(rows, where)
            if height is not None:
                upper = height
            notes = [
                f"{k}: {v}" for k, v in rows
                if _norm(k) not in _FURNITURE
                and not _is_restriction_key(_norm(k))
                and not _is_height_key(_norm(k))
                and not (_norm(k) in _NAME_KEYS and v == name)
            ]
            polygons, holes = _polygons(placemark, ns, where)
            zones.append(
                Zone(
                    identifier=f"SI-{slug}-{index}",
                    name=name,
                    restriction=restriction,
                    lower=None,
                    upper=upper,
                    applicability=[],
                    polygons=polygons,
                    holes=holes,
                    source=source,
                    native={
                        "folder": folder,
                        "placemark_name": raw_name,
                        "rows": [list(r) for r in rows],
                    },
                    notes=notes,
                )
            )
    return zones
