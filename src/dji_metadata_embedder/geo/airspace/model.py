"""Normalized airspace-zone model (#413).

Both providers (FAA UASFM ArcGIS, ED-269 documents) map into one ``Zone``
shape so the evaluator, the record and the map overlay never care where a
zone came from. Source-native attributes ride along in ``native`` —
normalization must lose nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

M_PER_FT = 0.3048


class AirspaceError(ValueError):
    """A feed failed to fetch or parse; the message names the concrete
    field/position. All-or-nothing: one bad zone invalidates the feed."""


@dataclass(frozen=True)
class VerticalLimit:
    """A published vertical limit: value + unit as published + datum.

    A missing limit is ``None`` at the :class:`Zone` level and renders
    "not stated" — never 0 (live ED-269 zones omit limits)."""

    value: float
    unit: str        # "m" | "ft", as published
    reference: str   # "AGL" | "AMSL"

    def label(self) -> str:
        return f"{self.value:g} {self.unit} {self.reference}"


@dataclass(frozen=True)
class Applicability:
    """One time window a zone applies in; ``None`` bounds are open-ended."""

    start: datetime | None
    end: datetime | None
    permanent: bool = True


@dataclass
class SourceInfo:
    """Provenance of a fetched feed — the record prints all of it."""

    feed: str      # human name, e.g. "FAA UAS Facility Maps"
    url: str       # endpoint actually contacted
    fetched: str   # ISO timestamp of the fetch (or the cached copy's)
    license: str   # license line, printed verbatim
    caveat: str    # the feed's own informational-only wording
    note: str | None = None  # e.g. Finland's established-zones-only limit


@dataclass
class Zone:
    """One normalized airspace zone.

    ``restriction``: "CEILING" (FAA grid cells, value in ``upper``) or the
    ED-269 class ("PROHIBITED"/"REQ_AUTHORISATION"/"NO_RESTRICTION"/other
    passthrough). ``polygons`` are closed rings of (lon, lat)."""

    identifier: str
    name: str
    restriction: str
    lower: VerticalLimit | None
    upper: VerticalLimit | None
    applicability: list[Applicability]
    polygons: list[list[tuple[float, float]]]
    source: SourceInfo
    native: dict = field(default_factory=dict)
