# Roadmap: flight-log decoder API fetcher (#390)

_Date: 2026-07-29_

## Context

#374 shipped the bring-your-own-CSV mapping layer (`geo/flightlog.py`):
`parse_flight_log` reads a decrypted flight-log CSV, `merge_gimbal` joins
true gimbal attitude onto a track. #390 is the opt-in convenience layer on
top — fetch that CSV directly from a decoder API instead of asking the user
to export it by hand.

As of 2026-07-28 every prerequisite in #390 is cleared:

- The provider (Flight Reader) confirmed the user-supplied-key model is
  acceptable, and their ToS explicitly contemplates third-party API use.
- The ToS makes the API the **only** compliant automation route ("automate
  flight log processing, except when using the Flight Reader API").
- The API returns CSV with customizable fields, so the fetcher drops
  directly in front of `parse_flight_log` with zero adaptation.
- Marcus's direction: API consumption, plainly described, is the intended
  integration; the issue graduated from research to planned implementation.

This document stages that implementation. Each stage gets its own design
doc when it is picked up; this roadmap fixes the ordering, the boundaries
between stages, and the constraints that bind all of them.

## API facts the roadmap relies on

From <https://www.flightreader.com/api/documentation/> (read 2026-07-29):

- Base URL `https://api.flightreader.com/v1`, HTTPS only, Bearer auth.
- `POST /v1/logs` — upload a TXT flight log (multipart `file`), **billable
  per request**. Returns CSV; a `fields` parameter selects columns.
- `GET /v1/fields` — list available fields, **not billable**.
- Two key types: secret (`sk_…`, plain Bearer) and public (`pk_…`, requires
  HMAC-SHA256 request signing with 5-minute expiry). The user's key lives
  on the user's own machine, which is the secret-key threat model — we use
  `sk_` keys and skip the signing dance entirely.
- DJI Cloud retrieval exists (`GET /v1/logs/{id}`, `POST /v1/accounts/dji`)
  but requires DJI account linkage — explicitly out of scope (stage 4).

## Constraints binding every stage (from #390, settled)

- **User-supplied key, never ours.** No key custody, no brokering.
- **Name the fact.** Consent line, with the deletion claim attributed:
  *"This uploads your entire flight log to Flight Reader to decrypt it.
  Your exact coordinates — and everything else the log records — leave
  your computer (they state uploads are deleted immediately after
  processing)."*
- **Refused under `--redact`** — feature off, reason stated, same gate
  shape as the gaze and the crossfade.
- **A fetcher, not a second pipeline.** Output feeds `parse_flight_log`
  unchanged; detect-and-advise behavior carries over as-is.
- **Polite by construction** (ToS abuse clause): one request per record,
  no automatic retries, no batching, and never re-uploading a log the
  API already decoded for us (see caching, stage 1).

## Stage 1 — CLI fetcher (the v2.3.0 candidate)

`POST /v1/logs` with the TXT file and a `fields` parameter preselecting
exactly the columns `parse_flight_log` consumes. The returned CSV is
written **beside the TXT** (cache file, e.g. `<log>.flightreader.csv`) and
then handed to the existing mapping layer as if the user had exported it.

- **Cache is the politeness mechanism**: if the cache file exists, no
  request is made, ever. Re-runs are free and offline. `--flight-log`
  pointing at the cache file must behave identically.
- **Key handling**: environment variable or interactive prompt — never a
  CLI argument (argv leaks into shell history and the process list).
- Failures are terminal and stated plainly (HTTP status + provider
  message); no retry loops.
- Consent is an explicit flag/action in the same invocation, not sticky
  state.

## Stage 2 — free-tier plumbing

`GET /v1/fields` is not billable. Use it for:

- a test-connection check (validates the key at zero cost), and
- field-availability validation feeding detect-and-advise.

Small, ships with or immediately after stage 1 — listed separately so it
is not skipped: it is the only way to verify a key without spending the
user's money.

## Stage 3 — GUI integration

Already decided in #390 (2026-07-28 comment); pure execution once stage 1
exists:

- Setup › Integrations group: service picker, key field, test-connection
  button (backed by stage 2).
- Key protected via DPAPI (`ProtectedData`) in the persisted GUI state,
  never plain text.
- Per-run opt-in checkbox in the mode that uses it, greyed until a key
  exists, consent line beside it. Setup stores capability; the run grants
  permission per use.

## Stage 4 — RC record retrieval, documented

A docs task: the supported method for copying TXT flight logs off the
remote controller (MTP/USB paths per RC model). This unblocks users who
have footage but no logs on their computer.

The API's DJI Cloud endpoints are a separate, optional retrieval path
with a bigger privacy surface (DJI account linkage) and are **explicitly
deferred** — not silently bundled into this stage or any other.

## Stage 5 — evidence attribution

If gimbal attitude can arrive from three places — the SRT, a
user-exported CSV, or an API fetch — the map should say which. The two
routes also have measurably different privacy footprints (desktop app
sends keys-only; API receives the whole log), and a verification tool
should show that chain rather than flatten it. Real design work,
independent of the fetcher; stays unscheduled until the stages above are
done.

## Non-goals (unchanged from #390)

- Bundling or brokering any API key.
- Online mode as a default, a prompt, or a suggestion to users who did
  not ask.
- Any upload without a specific, informed user action in the same
  session.
- DJI Cloud account linkage (see stage 4).
