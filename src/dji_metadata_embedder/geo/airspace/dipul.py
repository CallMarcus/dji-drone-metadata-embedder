"""dipul (Germany) UAS geographical-zone provider (#593).

dipul (Digitale Plattform Unbemannte Luftfahrt; publisher: Bundesministerium
für Verkehr, operated by DFS) publishes the § 21h LuftVO geographic zones,
the § 17 flight restriction areas and the control zones as 31 per-category
layers on an anonymous OGC WFS. One attribute schema across the layers:
``name`` (German), English/German generated names, ``legal_ref`` verbatim,
dipul's own ``type_code`` (+ ``type_code_detail`` for airfields, control
zones and restricted areas), ``external_reference``, and lower/upper limits
as value + unit (m/M/ft/FT/FL) + datum (AGL/MSL/PA). Temporary operating
restrictions carry ``start_time``/``end_time``.

Zones are fetched per flight by a padded, grid-snapped bbox (one request
per layer; the service refuses multi-layer requests), paged by
``startIndex``, and cached as one body. The WFS takes its bbox in
latitude-first axis order.

Restriction class (maintainer decision, 2026-10-02): dipul's ``U_NFZ``
temporary no-fly areas are PROHIBITED; § 17 flight restriction areas are
REQ_AUTHORISATION; every § 21h Abs. 3 category and the control zones are
CONDITIONAL (operation permitted only under the conditions the paragraph
sets out: consent, special category, distance and height rules, ATC
clearance); an unknown legal basis keeps dipul's published ``type_code`` as
the label rather than guessing or failing. The popup shows dipul's
category, legal reference and type code as published and does not restate
the conditions.

Licence (CC BY-ND 4.0, confirmed in writing by the dipul Service Team,
2026-09-28, issue #593): geometry passes through untouched, attributes
verbatim, attribution "dipul, CC-BY-ND 4.0". Format conversion for display
is permitted; nothing is clipped, merged or simplified here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from .arcgis_faa import snap_bbox
from .ed318 import _rings
from .model import (
    AirspaceError,
    Applicability,
    SourceInfo,
    VerticalLimit,
    Zone,
    iso_utc,
)

DIPUL_WFS = "https://uas-betrieb.de/geoservices/dipul/wfs"
_PAGE = 1000
# Hard stop per layer: 100 pages of up to 1000 rows is far beyond any real set.
_MAX_PAGES = 100
_TIMEOUT_S = 60

# Layer short name -> dipul's own title, from the live capabilities
# document (2026-10-02). The order is the fetch order.
DIPUL_LAYERS: dict[str, str] = {
    "sicherheitsbehoerden": "Andere Sicherheitsbehörden",
    "bahnanlagen": "Bahnanlagen",
    "binnenwasserstrassen": "Binnenwasserstraßen",
    "bundesautobahnen": "Bundesautobahnen",
    "bundesstrassen": "Bundesstraßen",
    "diplomatische_vertretungen": "Diplomatische und konsularische Vertretungen",
    "labore": "Einrichtungen BSL-4",
    "ffh-gebiete": "FFH-Gebiete",
    "flugbeschraenkungsgebiete": "Flugbeschränkungsgebiete",
    "flughaefen": "Flughäfen",
    "flugplaetze": "Flugplätze",
    "freibaeder": "Freibäder und Badestrände",
    "industrieanlagen": "Industrieanlagen",
    "internationale_organisationen": "Internationale Organisationen im Sinne des Völkerrechts",
    "justizvollzugsanstalten": "JVA und Einrichtungen des Maßregelvollzugs",
    "kontrollzonen": "Kontrollzonen",
    "kraftwerke": "Kraftwerke",
    "krankenhaeuser": "Krankenhäuser",
    "polizei": "Liegenschaften der Polizei",
    "militaerische_anlagen": "Militärische Anlagen und Organisationen",
    "nationalparks": "Nationalparks",
    "naturschutzgebiete": "Naturschutzgebiete",
    "behoerden": "Oberste Bundes- und Landesbehörden und Verfassungsorgane",
    "schifffahrtsanlagen": "Schifffahrtsanlagen",
    "seewasserstrassen": "Seewasserstraßen",
    "stromleitungen": "Stromleitungen",
    "temporaere_betriebseinschraenkungen": "Temporäre Betriebseinschränkungen",
    "umspannwerke": "Umspannwerke",
    "vogelschutzgebiete": "Vogelschutzgebiete",
    "windkraftanlagen": "Windkraftanlagen",
    "wohngrundstuecke": "Wohngrundstücke",
}


@dataclass(frozen=True)
class DipulFeed:
    code: str
    feed_name: str
    license: str
    caveat: str
    note: str | None = None


_CAVEAT = (
    "UAS geographical-zone data is informational and is not an authorization to fly."
)

DIPUL_FEED = DipulFeed(
    code="DE",
    feed_name="Germany UAS geographical zones (dipul)",
    license=(
        "© dipul (Bundesministerium für Verkehr, operated by DFS), CC BY-ND 4.0 "
        '— attribution "dipul, CC-BY-ND 4.0"; use confirmed in writing by the '
        "dipul Service Team, 2026-09-28"
    ),
    caveat=_CAVEAT,
    note=(
        "dipul's static layers are refreshed on the 28-day AIRAC cycle and "
        "carry no edition date, so only the fetch time is shown. Zones are "
        "fetched for the flight's area only. The § 21h LuftVO categories are "
        "permitted only under the conditions § 21h Abs. 3 sets out (consent "
        "of the operator or authority, the 'special' category, distance and "
        "height rules, ATC clearance in control zones); the popup shows "
        "dipul's category, legal reference and type code as published and "
        "does not restate those conditions."
    ),
)


def query_url(
    layer: str, bbox: tuple[float, float, float, float], start_index: int
) -> str:
    """One page of *layer* for the (already snapped) *bbox*."""
    x1, y1, x2, y2 = bbox
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": f"dipul:{layer}",
        # WFS 2.0 with EPSG:4326 takes the bbox latitude-first; a
        # longitude-first box silently matches nothing (probed 2026-10-02).
        "bbox": f"{y1},{x1},{y2},{x2}",
        "outputFormat": "application/json",
        "count": str(_PAGE),
    }
    if start_index:
        params["startIndex"] = str(start_index)
    return f"{DIPUL_WFS}?{urlencode(params)}"


def _fetch_page(url: str, transport, layer: str) -> dict:
    req = Request(url, headers={"User-Agent": "dji-embed"})
    try:
        with transport(req, timeout=_TIMEOUT_S) as resp:
            body = resp.read()
    except HTTPError as exc:
        raise AirspaceError(f"dipul layer {layer} answered HTTP {exc.code}") from exc
    except (URLError, OSError) as exc:
        raise AirspaceError(f"dipul layer {layer} query failed: {exc}") from exc
    try:
        doc = json.loads(body)
    except ValueError as exc:
        raise AirspaceError(f"dipul layer {layer} response is not JSON") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("features"), list):
        raise AirspaceError(f"dipul layer {layer} response has no 'features' list")
    return doc


def fetch_dipul_body(bbox: tuple[float, float, float, float], transport) -> bytes:
    """Every layer's pages for the snapped *bbox* as one cacheable JSON body."""
    snapped = snap_bbox(bbox)
    layers: dict[str, list[dict]] = {}
    for layer in DIPUL_LAYERS:
        pages: list[dict] = []
        fetched = 0
        total: int | None = None
        while total is None or fetched < total:
            if len(pages) >= _MAX_PAGES:
                raise AirspaceError(f"dipul layer {layer}: paging did not converge")
            doc = _fetch_page(query_url(layer, snapped, fetched), transport, layer)
            if total is None:
                stated = doc.get("totalFeatures")
                if not isinstance(stated, int) or isinstance(stated, bool):
                    raise AirspaceError(
                        f"dipul layer {layer}: response states no totalFeatures count"
                    )
                total = stated
            pages.append(doc)
            got = len(doc["features"])
            if got == 0 and fetched < total:
                raise AirspaceError(
                    f"dipul layer {layer}: page set incomplete "
                    f"({fetched} of {total} features)"
                )
            fetched += got
            if fetched > total:
                raise AirspaceError(f"dipul layer {layer}: paging did not converge")
        layers[f"dipul:{layer}"] = pages
    return json.dumps({"layers": layers}).encode("utf-8")


_UNIT = {"m": "m", "ft": "ft", "fl": "FL"}
_DATUM = {"AGL": "AGL", "MSL": "AMSL", "PA": "STD"}


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _limit(props: dict, side: str, where: str) -> VerticalLimit | None:
    published = props.get(f"{side}_limit_altitude")
    if isinstance(published, bool):
        raise AirspaceError(
            f"{where}: {side}_limit_altitude {published!r} is not a number"
        )
    if isinstance(published, (int, float)):
        # The live service publishes JSON numbers (the cache keeps them as-is).
        value = float(published)
    else:
        raw = _text(published)
        if raw is None:
            return None
        try:
            value = float(raw)
        except ValueError as exc:
            raise AirspaceError(
                f"{where}: {side}_limit_altitude {raw!r} is not a number"
            ) from exc
    unit_raw = _text(props.get(f"{side}_limit_unit")) or ""
    unit = _UNIT.get(unit_raw.lower())
    if unit is None:
        raise AirspaceError(f"{where}: {side}_limit_unit {unit_raw!r} is not supported")
    datum_raw = _text(props.get(f"{side}_limit_alt_ref")) or ""
    reference = _DATUM.get(datum_raw)
    if reference is None:
        raise AirspaceError(
            f"{where}: {side}_limit_alt_ref {datum_raw!r} is not supported"
        )
    return VerticalLimit(value=value, unit=unit, reference=reference)


def _restriction(props: dict, where: str) -> str:
    type_code = _text(props.get("type_code")) or ""
    legal = _text(props.get("legal_ref")) or ""
    if type_code == "U_NFZ":
        return "PROHIBITED"
    if legal.startswith("§ 17"):
        return "REQ_AUTHORISATION"
    if legal.startswith("§ 21h") or type_code == "KONTROLLZONE":
        return "CONDITIONAL"
    if not type_code and not legal:
        raise AirspaceError(f"{where}: no legal_ref or type_code")
    return type_code or legal


def _english_name(props: dict) -> str | None:
    # The temporary layer spells the key lower-case; everything else upper.
    return _text(props.get("generated_name_EN")) or _text(
        props.get("generated_name_en")
    )


def parse_dipul(raw: bytes, source: SourceInfo) -> list[Zone]:
    """Every feature in a cache body as one Zone each; all-or-nothing."""
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        raise AirspaceError(f"{source.feed}: body is not JSON ({exc})") from exc
    layers = doc.get("layers") if isinstance(doc, dict) else None
    if not isinstance(layers, dict):
        raise AirspaceError(f"{source.feed}: body has no 'layers' object")
    zones: list[Zone] = []
    seen: set[str] = set()
    for layer_name, pages in layers.items():
        short = layer_name.split(":", 1)[-1]
        title = DIPUL_LAYERS.get(short)
        if title is None:
            raise AirspaceError(f"{source.feed}: {layer_name!r} is not a dipul layer")
        if not isinstance(pages, list):
            raise AirspaceError(f"{source.feed}: {layer_name} pages are not a list")
        index = 0
        for page in pages:
            feats = page.get("features") if isinstance(page, dict) else None
            if not isinstance(feats, list):
                raise AirspaceError(
                    f"{source.feed}: {layer_name} page has no 'features' list"
                )
            for feat in feats:
                where = f"{source.feed}: {short} feature {index}"
                index += 1
                if not isinstance(feat, dict):
                    raise AirspaceError(f"{where}: not an object")
                props = feat.get("properties")
                if not isinstance(props, dict):
                    raise AirspaceError(f"{where}: missing properties")
                ref = _text(props.get("external_reference"))
                if ref is None:
                    raise AirspaceError(f"{where}: missing external_reference")
                ident = f"{short}:{ref}"
                if ident in seen:
                    raise AirspaceError(
                        f"{source.feed}: zone id {ident!r} is not unique"
                    )
                seen.add(ident)
                name = _text(props.get("name")) or ident
                start = _text(props.get("start_time"))
                end = _text(props.get("end_time"))
                applicability: list[Applicability] = []
                if start or end:
                    applicability.append(
                        Applicability(
                            start=iso_utc(start, f"{where}: start_time")
                            if start
                            else None,
                            end=iso_utc(end, f"{where}: end_time") if end else None,
                            permanent=False,
                        )
                    )
                type_code = _text(props.get("type_code")) or ""
                detail = _text(props.get("type_code_detail"))
                english = _english_name(props)
                notes = [title]
                if english and english != name:
                    notes.append(english)
                legal = _text(props.get("legal_ref"))
                if legal:
                    notes.append(legal)
                if type_code:
                    notes.append(f"{type_code} / {detail}" if detail else type_code)
                polygons, holes = _rings(feat.get("geometry") or {}, ident, where)
                if not polygons:
                    raise AirspaceError(f"{where} ({ident}): no polygon geometry")
                zones.append(
                    Zone(
                        identifier=ident,
                        name=name,
                        restriction=_restriction(props, f"{where} ({ident})"),
                        lower=_limit(props, "lower", f"{where} ({ident})"),
                        upper=_limit(props, "upper", f"{where} ({ident})"),
                        applicability=applicability,
                        polygons=polygons,
                        holes=holes,
                        source=source,
                        native=feat,
                        notes=notes,
                    )
                )
    return zones
