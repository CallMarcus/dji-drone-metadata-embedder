# Design: `fetch-log` — Flight Reader API fetcher (#390 stage 1)

_Date: 2026-07-29_

## Context

#374 shipped the vendor-neutral flight-log CSV mapping layer
(`geo/flightlog.py`): `parse_flight_log` reads a decrypted flight-log CSV
by semantic column matching, `merge_into_flights` joins gimbal attitude
onto the matching flight. The user currently produces that CSV by hand in
Flight Reader's desktop app.

#390 stage 1 (per the [roadmap](2026-07-29-flight-log-api-fetcher-roadmap.md))
is the opt-in convenience layer: fetch the CSV from the Flight Reader API
directly. Every prerequisite is cleared — the provider approves the
user-supplied-key model, the ToS makes the API the only compliant
automation route, and the API returns CSV.

Decision made with Marcus 2026-07-29: the fetch is a **separate
subcommand**, not a flag on `flightmap`. `flightmap` itself never goes
online; the cache file is a visible artifact the user can inspect; the
`--redact`-vs-upload contradiction #390 guards against cannot arise
inside a single run; and the GUI composes the two commands.

## The command

```
dji-embed fetch-log RECORD.txt [MORE.txt ...]
```

For each TXT flight record, decrypt it through the Flight Reader API and
write the returned CSV **beside the TXT** as `<stem>.flightreader.csv`.
The user (or the GUI) then passes that file to `flightmap --flight-log`
exactly as a hand-exported CSV — the fetcher feeds the same mapping
layer, never a second pipeline.

Per file, in order:

1. **Cache check.** If `<stem>.flightreader.csv` exists, report it and
   make **no network call**. Deleting the cache file is the refetch
   mechanism; there is no `--force`. The cache is the politeness
   mechanism the ToS abuse clause asks for: the same log is never
   uploaded twice, and re-runs are free and offline.
2. **Field discovery.** `GET /v1/fields` (not billable) lists the
   provider's field names. Token-match them with the same semantics
   `flightlog.py` already uses (gimbal+pitch, gimbal+yaw, utc,
   latitude, longitude, date/time) to build the `fields` parameter. If
   matching fails, request the full CSV instead of failing — the mapping
   layer's own detect-and-advise judges the result.
3. **Upload.** `POST /v1/logs` (billable), multipart `file` upload,
   `Authorization: Bearer` with the user's secret key. One attempt, no
   automatic retries, 120 s timeout, `User-Agent: dji-embed` (matching
   `utils/provision.py`).
4. **Write + verify.** Write the CSV beside the TXT, then run
   `parse_flight_log` over it immediately. If it lacks the columns the
   merge needs, say exactly what is missing and which export settings to
   fix — at fetch time, not later at map time. A failed verification
   **keeps** the file (it cost money) and exits nonzero.

Multiple TXTs are processed independently; one file's failure does not
stop the rest (matching `--flight-log`'s per-file error handling).

## Consent

Before any upload, print the consent line — the fact, with the deletion
claim attributed, per #390's name-the-fact rule:

> This uploads your entire flight log to Flight Reader to decrypt it.
> Your exact coordinates — and everything else the log records — leave
> your computer (they state uploads are deleted immediately after
> processing).

Then `Proceed? [y/N]`, once per invocation. Declining exits cleanly with
nothing sent.

- `--yes` skips the prompt for non-interactive use.
- Under `--progress jsonl` (the GUI contract) the prompt cannot be
  answered, so `--yes` is **required**; its absence is a usage error.
  The GUI shows its own per-run consent checkbox (#390's decided
  layout) and passes `--yes` only when the user ticks it.
- Consent is per-invocation, never sticky: no config flag, no
  environment variable, no "don't ask again".

A cache-hit-only invocation prints no consent line — nothing is
uploaded.

## Key handling

- `FLIGHTREADER_API_KEY` environment variable, or an interactive hidden
  prompt (`click.prompt(hide_input=True)`) when unset in a terminal.
- Deliberately **no `--api-key` option**: argv leaks into shell history
  and the process list.
- Under `--progress jsonl` with no environment key, fail with a message
  naming the variable — the GUI stores the key (DPAPI, stage 3) and
  injects it into the child's environment.
- Secret (`sk_`) keys only. The public-key HMAC signing path exists for
  browser embedding and is not needed when the key stays on the user's
  machine.
- The key is never logged, echoed, or written to any file by the CLI.

## Errors

Terminal and stated plainly, no retry loops:

- HTTP errors: status code plus the provider's message verbatim. 401
  additionally says "check FLIGHTREADER_API_KEY". Suspension responses
  (the ToS abuse clause) surface verbatim — the fetcher never papers
  over them.
- Network errors (`URLError`, timeout): the underlying reason, plus a
  note that the TXT was not consumed and the command can simply be
  re-run.
- A response that is not CSV (HTML error page, JSON error body): say so
  and show the first line; write nothing.

## Module shape

New `geo/logfetch.py` — sibling of `flightlog.py`, mirroring its
pure-stdlib rule (urllib only, no new dependencies):

- `fetch_log(txt: Path, key: str, *, transport=urlopen) -> Path` —
  fetch one record, return the cache path. Raises `LogFetchError`
  (message ready for `click.ClickException`, same pattern as
  `FlightLogError`).
- `select_fields(available: list[str]) -> list[str] | None` — the
  token-match from step 2; `None` means "request everything". Reuses
  `flightlog._tokens`/`_find` semantics rather than duplicating them —
  promote those helpers to module-public if needed.
- The `transport` seam exists for tests; production code never passes
  it.

The CLI subcommand lives in `cli.py` with the standard
`--progress`/`-v`/`-q` options and drives the per-file loop, consent,
and key resolution. API constants (base URL `https://api.flightreader.com/v1`,
endpoints, timeout) live in `logfetch.py`.

## Testing

No network in CI, ever:

- Unit tests monkeypatch `transport` with recorded fixtures: a
  `/v1/fields` JSON listing and a CSV body shaped like the real
  Mini 3 Pro export #374 was validated against (decimal commas, local
  timestamps — the returned CSV must survive `parse_flight_log`
  unchanged).
- `select_fields`: match, partial-match, and no-match (→ `None`) cases.
- CLI tests: cache hit makes **zero** transport calls; declining the
  consent prompt sends nothing and exits 0; `--progress jsonl` without
  `--yes` is a usage error; missing key under jsonl names the
  environment variable; HTTP 401/402/5xx and non-CSV bodies produce the
  documented messages; a verification failure keeps the file and exits
  nonzero.
- Real E2E against the live API waits on a key (test key requested from
  the provider 2026-07-29; pay-as-you-go is the fallback) and is a
  release-gate check, not a CI job.

## Documentation

- `docs/how-to/flight-log-gimbal.md` gains a "fetching via the API"
  section: the two-command flow, the consent fact, the cache file, and
  a pointer to Flight Reader's API signup. The existing
  recommended-export-settings note carries over — the API's field
  customization behaves the same.
- CHANGELOG under Unreleased; #390 stays open (stages 2–5 remain).

## Non-goals (v1)

- No `--service` abstraction: Flight Reader is the only provider and an
  enum of one is noise. The command name is generic so a second
  provider is additive.
- No ZIP or URL inputs — local TXT files only.
- No `--force` refetch, no `-o/--output` override, no batch parallelism.
- No fetch from inside `flightmap` (revisit only if users ask; the
  consent and `--redact` reasoning above would need rework first).
- Nothing from roadmap stages 2–5 beyond the `/v1/fields` call stage 1
  itself needs.
