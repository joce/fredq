# AGENTS.md

## Project
fredq exposes FRED (Federal Reserve Economic Data) HTTP endpoints as an LLM-friendly CLI that prints the raw JSON FRED returns.

## Stack
Python 3.10+, uv, httpx, argparse, pytest, pytest-httpx, ruff, pyright, tox, hatchling.

## Commands
- Install/sync: `uv sync --all-groups`
- Run CLI: `uv run fredq --help`
- Test single: `uv run pytest path/to/test_file.py`
- Test all: `uv run pytest`
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .`
- Type check: `uv run pyright`
- Spell check: `npm run spell` or `make spell`
- Spell changed files: `npm run spell:changed` or `make spell-changed`
- Full check: `uv run tox`

## Architecture
- `src/fredq/client.py` -> FRED HTTP client (single async GET, api_key injection, retries, raw response retrieval).
- `src/fredq/auth.py` -> Read FRED_API_KEY from env or fallback file.
- `src/fredq/commands.py` -> command metadata used to build CLI commands, validation, and help.
- `src/fredq/params.py` -> CLI parameter coercion and validation helpers.
- `src/fredq/cli.py` -> argparse command tree and stdout/stderr behavior.
- `tests/` -> pytest tests mirroring `src/fredq/`.

## Rules
- IMPORTANT: `--help` is the primary product surface; keep it complete, adaptive, and generated from command metadata where practical.
- Do not add `describe`, `endpoints`, `params`, or other discovery commands; discovery belongs under `fredq --help` and `fredq <endpoint> --help`.
- Print FRED response bodies to stdout exactly as returned; do not model, reshape, pretty-print, or interpret endpoint JSON.
- Keep FRED endpoint knowledge in metadata and validation only; do not create response classes.
- Use `uv run python` for Python scripts; never use bare `python` or `python3`.
- Never log or print the FRED API key.
- Keep runtime dependencies narrow; do not add TUI, ORM, web framework, or rich formatting libraries.

## API key
- Primary: `FRED_API_KEY` environment variable.
- Fallback: file at `~/.fredq/api_key` (single line, key only).
- The CLI must redact the key from any error messages and never log it.

## Help text
When adding or editing a CLI command:
1. **Summary**: active verb, ≤68 chars (over wraps two-line in top-level help). `Fetch` (data), `List` (catalog), `Search` (text), `Show` (single entity), `Discover` (curated). Pair sibling commands with the same verb.
2. **Description**: describe response content, not fredq mechanics. Forbidden phrasings: `Calls FRED`, `writes to stdout`, `response-model mapping`. The root parser already covers output behavior. Do not paraphrase the summary.
3. **Notes**: real clarifications only — FRED quirks, switch-behavior surprises, dependencies. Drop diary entries and redundant restatements.
4. **Order in `COMMANDS` tuple by importance**: daily-driver → discovery → entity lookups → schema introspection. Never append to the end.
5. **Param boilerplate is shared** (`--api-key`, `--realtime-start`, `--realtime-end` use exact strings — copy them). Run `pytest -k help` before and after.
6. **Positional primary args**: each command's single primary required argument is a positional (its `metavar` is shown in usage); all other parameters are flags. `series-search` / `series-search-tags` / `series-search-related-tags` take the search text positionally; `tags-series` / `related-tags` take the tag list positionally; `geofred regional-data` / `geofred shapes` take their primary (`series_group` / `shape`) positionally.

## Output formats
- **Default**: raw FRED JSON to stdout, exactly as returned.
- **Parquet**: opt-in via `--format parquet --out PATH`, `series-observations` only. Parses the response into a typed table (`date`, `value`, realtime bounds) with the response envelope stored as schema metadata. Other endpoints reject `--format parquet` with a usage error.
- Other endpoints stay JSON-only.

## Workflow
- Make minimal changes and avoid unrelated refactors.
- When adding a command or parameter, update validation, adaptive help, and tests in the same change.
- Prefer focused unit tests with mocked HTTP; mark live FRED tests as integration.
- Before considering code changes done, run `uv run tox`. It is the expected bundled verification for formatting, lint, type check, tests, and spelling.
- For command or parameter changes, also run the app against FRED after `tox`:
  - `uv run fredq <command> --help`
  - `uv run fredq <command> <minimal required parameters>`
  - `uv run fredq <command> <parameters with each supported date format when dates are involved>`
  - `uv run fredq <command> <parameters with meaningful values that could affect FRED's raw output>`
- When a parameter has a default, test both omission and explicit override if the default affects the request sent to FRED.
- Ask before making architectural changes that affect the CLI grammar or auth behavior.

## FRED API state probes
- When checking the current FRED API surface, use a varied set of series, releases, and categories so behavior is not inferred from one path only.
- Baseline probe targets:
  - Series: `GNPCA` (annual GDP), `DGS10` (10y yield), `CPIAUCSL` (CPI), `UNRATE` (unemployment), `FEDFUNDS` (fed funds), `DEXCAUS` (CAD/USD)
  - Categories: `32991` (Money, Banking), `0` (root)
  - Releases: `53` (GDP), `10` (CPI), `175` (Employment)
  - Sources: `1` (Board of Governors), `3` (Bureau of Labor Statistics)
- Add targeted probes when an endpoint is series-sensitive, but keep this baseline for broad API-surface discovery.

## GeoFRED / Maps
- Implemented under the `geofred` subcommand group (`series-group`, `series-data`, `regional-data`, `shapes`). Different base URL; regional data keyed by FIPS; `shapes` returns Highcharts-format GeoJSON in a Lambert Conformal Conic projection (not WGS84).

## Out of scope
- Mapping FRED JSON into Python domain models.
- Separate documentation/discovery subcommands.
- Secrets or API keys in checked-in files.
