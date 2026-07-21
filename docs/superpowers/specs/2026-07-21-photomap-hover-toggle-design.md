# Photomap: hover previews become a viewer-side toggle (issue #345)

**Status:** approved 2026-07-21 (maintainer chose "viewer: in-map toggle" over
an author-side CLI flag or both).

## Problem

Since #273, photomap pins show a sticky hover tooltip (thumbnail + filename)
on mouse devices, and the full popup — details and the link to the original /
360° viewer — still needs a click. On a mouse device the user therefore
interacts with a pin **twice** to get anywhere. The preview is great for
skimming a large map, but as the default it adds a step to the most common
action: opening a photo.

## Decision

The map itself grows a small **"Hover previews"** toggle, default **OFF**.
The map author's surface does not change: no CLI flag, no GUI panel row —
every regenerated map simply behaves this way, and anyone the map is shared
with gets the same choice.

## Design

1. **Control.** A custom Leaflet-style control (top-right, stacking with the
   existing photos/panos legend when present): a label + checkbox reading
   "Hover previews", styled like a `leaflet-control` card. Rendered **only
   when the device really hovers** (`!TOUCH`, the #295 capability check) —
   touch never had tooltips and must not gain a dead toggle.
2. **Default OFF.** Markers bind only the click popup at creation. A
   `setHoverPreviews(on)` function binds the existing #273 sticky tooltip
   (`buildTooltip`, `{ sticky: true, direction: 'top' }`) to every marker,
   or unbinds it; the marker loop keeps `(marker, feature)` pairs so the
   toggle can rebind lazily.
3. **Persistence.** `localStorage` key `djiembed-photomap-hover` (`'1'` =
   on), read at load to set the initial checkbox state and binding. All
   localStorage access is wrapped in try/catch — Safari private mode and
   file:// contexts can throw — and failure silently means "not remembered".
4. **Unchanged:** the tooltip content and CSS (#273), the touch tap-target
   handling (#295), the click popup, the pano viewer, flightmap (it has no
   hover previews), and the CLI/GUI surfaces.

## Docs & changelog

- `docs/user_guide.md` hover paragraph: previews are off by default; the
  toggle sits in the map's top-right corner and is remembered by the
  browser; phones/tablets still skip previews entirely.
- CHANGELOG entry under Changed (default behaviour change for mouse users).

## Testing

String-level tests in `tests/test_geo_photomap_html.py`, same style as the
existing #273/#295 pins (which move to the new shape rather than being
deleted):

- the control markup exists and is created only under `!TOUCH`;
- markers do NOT bind tooltips unconditionally at creation (default off);
- `setHoverPreviews` both binds and unbinds;
- the `djiembed-photomap-hover` localStorage key is present and guarded;
- `buildTooltip` content pins (#273) unchanged.

Manual E2E with the Playwright browser on a real generated map: default no
tooltip on hover; toggle on → tooltip appears; reload → remembered.
