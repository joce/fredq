# AGENTS.md

## Project
fredq is a typed Python library and an LLM-friendly CLI over FRED (Federal
Reserve Economic Data) HTTP endpoints. The CLI prints the raw JSON FRED
returns, byte-for-byte. The library (`fredq.api` and below) returns parsed,
typed results. The two share client/commands/params foundations but the CLI
never routes through the library's typed surface.

## Stack
Python 3.10+, uv, httpx2, argparse, pytest, ruff, pyright, tox, hatchling.

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
Commands are organized into five noun groups, each with verb leaves:
- **series**: `show`, `observations`, `search`, `search-tags`, `search-related-tags`, `vintage-dates`, `categories`, `tags`, `release`, `updates`
- **category**: `show`, `children`, `related`, `series`, `tags`, `related-tags`
- **release**: `list`, `show`, `calendar` (all releases dates), `dates` (one release's dates), `series`, `sources`, `tags`, `related-tags`, `tables`
  - `release calendar` → `/fred/releases/dates`; `release dates ID` → `/fred/release/dates` (distinct endpoints)
- **source**: `list`, `show`, `releases`
- **tag**: `list`, `series`, `related`

Each `CommandSpec.name` is globally unique and unchanged (routing key). The `leaf` field is display-only.

## Architecture
- `src/fredq/client.py` -> FRED HTTP client (single async GET, api_key injection, retries, raw response retrieval).
- `src/fredq/auth.py` -> Read FRED_API_KEY from env or fallback file.
- `src/fredq/commands.py` -> command metadata used to build CLI commands, validation, and help.
- `src/fredq/params.py` -> CLI parameter coercion and validation helpers.
- `src/fredq/_bridge.py` -> background event loop; sync-over-async bridge (library only).
- `src/fredq/_core.py` -> async endpoint core: shared client, configure(), param building, error contract (library only).
- `src/fredq/api.py` -> public synchronous library surface (entity classes + module functions).
- `src/fredq/frames.py` -> polars-backed Frame containers for bulk tabular payloads (library only).
- `src/fredq/cli.py` -> argparse command tree and stdout/stderr behavior.
- `src/fredq/skills/content/` -> Agent Skills-standard skill (SKILL.md router + domain docs) teaching agents fredq's library and CLI, shipped as package data.
- `src/fredq/skills/_install.py` -> copy-only installer for the skill content (resolve_roots/install/uninstall/status) targeting every major agent's documented skill-discovery root.
- `tests/` -> pytest tests mirroring `src/fredq/`.

## Rules — CLI layer
- IMPORTANT: `--help` is the primary product surface; keep it complete, adaptive, and generated from command metadata where practical.
- Do not add `describe`, `endpoints`, `params`, or other discovery commands; discovery belongs under `fredq --help` and `fredq <endpoint> --help`.
- Print FRED response bodies to stdout exactly as returned; do not model, reshape, pretty-print, or interpret endpoint JSON. (CLI layer only; the library layer interprets.)
- In the CLI layer, keep FRED endpoint knowledge in metadata and validation only. Response classes live exclusively in the library layer (src/fredq/models/).
- Use `uv run python` for Python scripts; never use bare `python` or `python3`.
- Use `regex` instead of standard library `re` for regular expressions.
- Never log or print the FRED API key.
- Keep runtime dependencies narrow; do not add TUI, ORM, web framework, or rich formatting libraries.
- The skills command group is packaging/installer surface: human-readable output, outside both the raw-JSON contract and the no-discovery-commands rule.

## Rules — library layer
- The library layer (`api.py`, `_core.py`, `_bridge.py`, `frames.py`, `models/`) parses and types FRED responses; the raw-JSON law above does not apply to it.
- The CLI never imports `api.py`, `frames.py`, or `models/`. `fredq --help` and all CLI commands must never pay the polars import cost.
- Library kwargs mirror wire parameter names exactly as spelled in `CommandSpec`s; never an inverted flag.
- The committed corpus (`tests/fixtures/corpus/`, see its README) is the only authority for wire spellings, presence, and types. Errors are mapped by status + body shape, never message wording.

## Response model conventions (library layer)
- Every response model subclasses `FredModel` (`src/fredq/models/_base.py`): `frozen=True`, `extra="allow"` (drift lands on `model_extra` for the gates — never use `forbid`), `populate_by_name=True`, `str_strip_whitespace=True`. No alias generator; field names mirror wire keys exactly, warts included (`seriess`).
- Required vs optional comes from the corpus, never docs or guesses: present in 100% of corpus records → required (no default); sometimes absent → `T | None = None`; always present but sometimes null → `T | None` (no default). Live evidence may LOOSEN (required → optional) with a dated docstring note and a pinned test; never tighten.
- Every model is registered in `tests/test_models_gates.py` in the same commit that creates it: zero-nested-extras over all relevant captures, required-set == corpus universal keys, alphabetical field order.
- Temporal honesty: ISO date strings → `datetime.date`; FRED's offset datetimes (`2026-04-09 07:53:12-05`) → aware `datetime` via `FredDatetime`. No temporal value stays a bare string.
- Enums only where the vocabulary is closed by request-side validation or explicit FRED documentation; corpus-only closure is insufficient (the corpus's series are not the universe). Open vocabularies stay `str`. `Literal` for true constants (`file_type`).
- `functools.cached_property` for conveniences; NEVER `computed_field` (`model_dump()` stays wire-shaped).
- Nested structures are typed sub-models, never `dict[str, Any]` (documented exceptions: `raw()`, evidence-justified Frame columns); keyed collections are `dict[str, SubModel]`.
- Model reuse across endpoints only after script-validated evidence (zero extras + required set holds on the candidate's captures); the model docstring lists every endpoint it covers.
- Single-entity endpoints unwrap their one-element list; violations raise the malformed-response contract (`FredApiError`, `error_code=None`).
- Module docstring names the endpoint noun + corpus date; sometimes-absent fields carry an applicability note.

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
6. **Positional primary args**: each command's single primary required argument is a positional (its `metavar` is shown in usage); all other parameters are flags. `series search` / `series search-tags` / `series search-related-tags` take the search text positionally; `tag series` / `tag related` take the tag list positionally.

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
Exception: the library-api feature runs brainstorm → spec → multi-part plans on a single `library-api` branch with ONE PR at the very end, merged by the user. The per-PR merge loop below applies to normal maintenance work.

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
9. Merge only after actionable comments are handled/rebutted and CI passes. Squash and merge (`gh pr merge --squash --delete-branch`); clean up local + remote branches after.

## FRED API state probes
- When checking the current FRED API surface, use a varied set of series, releases, and categories so behavior is not inferred from one path only.
- Baseline probe targets:
  - Series: `GNPCA` (annual GDP), `DGS10` (10y yield), `CPIAUCSL` (CPI), `UNRATE` (unemployment), `FEDFUNDS` (fed funds), `DEXCAUS` (CAD/USD)
  - Categories: `32991` (Money, Banking), `0` (root)
  - Releases: `53` (GDP), `10` (CPI), `175` (Employment)
  - Sources: `1` (Board of Governors), `3` (Bureau of Labor Statistics)
- Add targeted probes when an endpoint is series-sensitive, but keep this baseline for broad API-surface discovery.

## Out of scope
- Separate documentation/discovery subcommands.
- Secrets or API keys in checked-in files.
- Typed models outside the library layer.
