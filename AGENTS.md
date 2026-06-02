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

## Command grouping (noun-verb)
Commands are organized into six noun groups, each with verb leaves:
- **series**: `show`, `observations`, `search`, `search-tags`, `search-related-tags`, `vintage-dates`, `categories`, `tags`, `release`, `updates`
- **category**: `show`, `children`, `related`, `series`, `tags`, `related-tags`
- **release**: `list`, `show`, `calendar` (all releases dates), `dates` (one release's dates), `series`, `sources`, `tags`, `related-tags`, `tables`
  - `release calendar` → `/fred/releases/dates`; `release dates ID` → `/fred/release/dates` (distinct endpoints)
- **source**: `list`, `show`, `releases`
- **tag**: `list`, `series`, `related`
- **geofred**: `series-group`, `series-data`, `regional-data`, `shapes` (unchanged; leaf stays None → uses name)

Each `CommandSpec.name` is globally unique and unchanged (routing key). The `leaf` field is display-only.

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
6. **Positional primary args**: each command's single primary required argument is a positional (its `metavar` is shown in usage); all other parameters are flags. `series search` / `series search-tags` / `series search-related-tags` take the search text positionally; `tag series` / `tag related` take the tag list positionally; `geofred regional-data` / `geofred shapes` take their primary (`series_group` / `shape`) positionally.

## Output formats
- **Default**: raw FRED JSON to stdout, exactly as returned.
- **Parquet**: opt-in via `--format parquet --out PATH`, `series-observations` only. Parses the response into a typed table (`date`, `value`, realtime bounds) with the response envelope stored as schema metadata. Parquet output is written with **polars** (a core dependency); other endpoints reject `--format parquet` with a usage error.
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

## Development workflow
Use this process for all development work — bug fixes and features alike. For features, brainstorm and plan first, then follow the implement → review → dogfood loop below.

Model / effort split:
- **Implementation** — `claude-sonnet-4-6`, effort `high` (`medium` ok for tiny localized edits). TDD: write/adjust a focused failing test first, then the smallest fix. No unrelated refactors.
- **Review** — `claude-opus-4-8`, effort `xhigh`. Senior-reviewer pass: correctness bugs, regressions, missing tests, CLI-contract breaks, cache/identity issues, help-text drift. Fix real findings before dogfooding.
- **Dogfood / test runner** — `claude-haiku-4-5`, effort `medium`. Run targeted tests + CLI probes, report exact evidence; don't redesign unless a failure proves the design wrong.
- **Escalation** — `claude-opus-4-8`, effort `max`. Only for stuck cases, architectural ambiguity, repeated failed reviews, or broad cross-module changes. Not the default.

Steps:
1. Create a new branch before implementation.
2. Read `AGENTS.md`, `CLAUDE.md`, the issue/PR context, and the touched modules/tests.
3. Implement with TDD: focused tests first, minimal change, no unrelated refactors.
4. Run an `xhigh` review pass; fix real issues before moving on.
5. Dogfood with focused tests + CLI probes (`uv run python`, never bare `python`). For command/parameter changes verify `fredq <command> --help` and representative live forms.
6. Full verification before "ready": `uv run tox` and `npm run spell`.
7. Commit, push, open a PR.
8. Wait for CI + review comments (check ~every minute, up to 10 min). Prioritize actionable human comments; treat ordinary Codecov patch-coverage advisories as non-blocking unless they flag a concrete behavioral gap.
9. Merge only after actionable comments are handled/rebutted and CI passes. Prefer fast-forward merge; clean up local + remote branches after.

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
