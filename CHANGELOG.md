# Changelog

All notable changes to fredq are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.2]

Maintenance release — no user-facing changes. Runtime dependency ranges in
`pyproject.toml` are unchanged.

### Internal

- Bumped development dependencies: ruff 0.16.0, tox 4.58.0, tox-uv 1.36.0,
  coverage 7.15.2, and the locked httpx2 2.9.1, polars 1.43.0, and
  regex 2026.7.19.
- Adopted ruff 0.16's `# ruff: ignore[...]` suppression comments in place of
  `# noqa:`, and rule names in place of rule codes in the lint configuration.
- Bumped GitHub Actions: `astral-sh/setup-uv` 8.3.2 to 9.0.0,
  `actions/setup-node` 6 to 7.

## [0.4.1]

Maintenance release — no user-facing changes.

### Internal

- Bumped `pyarrow` to 25.0.0 and widened its pin in the `pandas` extra
  from `<23` to `<26`.
- Bumped development dependencies: tox 4.56.4, ruff 0.15.21,
  tzdata 2026.3.

## [0.4.0]

fredq is now a typed Python library as well as a CLI. CLI behavior and
output are unchanged, except for the removal of the `geofred` command
group (see Removed).

### Added

- Typed library surface: `fredq.Series`, `fredq.Category`, `fredq.Release`,
  and `fredq.Source` entity classes, plus module-level functions
  (`search_series`, `releases`, `sources`, `tags`, and related lookups) —
  see the README for the full surface table.
- Corpus-gated pydantic response models under `fredq.models` (`SeriesInfo`,
  `ReleaseInfo`, `SourceInfo`, `TagsResult`, and others): frozen, with
  required/optional derived from real FRED response captures rather than
  documentation, and unrecognized fields captured on `model_extra` instead
  of raising.
- `fredq.Series.observations()` returns a polars-backed `Observations`
  frame (`fredq.frames`) with `.to_polars()`, `.to_pandas()`, `.to_arrow()`,
  `.to_dicts()`, and `.save_parquet()`, plus a typed `.meta` envelope.
- `fredq.raw(command, **params)`: an escape hatch that reaches every
  command the CLI knows, validated exactly like every other library call.
- `fredq.configure(*, api_key=None, timeout=None)` to set the shared
  library client's options before the first call.
- `fredq.FredApiError`, `fredq.FredClientUsageError`, and related
  exceptions for typed error handling in library code.
- `py.typed` marker ([PEP 561](https://peps.python.org/pep-0561/)) so type
  checkers see the library's real return types without stubs.
- New optional extra: `pip install "fredq[pandas]"` (pandas + pyarrow) for
  `Observations.to_pandas()` / `.to_arrow()`.
- An installable agent skill (Agent Skills standard: `SKILL.md` plus four
  markdown domains — observations, revisions, catalog, dataframes — with
  corpus-dated sharp edges), shipped inside the wheel under `fredq.skills`.
- A `fredq skills` CLI group: `install`/`uninstall`/`list` with explicit
  `--agent` targeting (`claude`/`codex`/`copilot`/`cursor`/`gemini`/`pi`,
  comma-separable), `--project` for repository-level directories, and a
  `--to PATH` escape hatch. Installs are copy-only, stamped with the
  installing version (surfaced by `list` as current/stale), and ownership-
  checked: a directory not created by fredq is never replaced or removed.

### Changed

- Added `pydantic` as a core runtime dependency (typed response models).

### Removed

- **Breaking:** the `geofred` CLI command group (`series-group`,
  `series-data`, `regional-data`, `shapes`) and its four FRED Maps API
  endpoints. The GeoFRED site was sunset in 2022 and the underlying API is
  deprecated. These commands are no longer reachable from the CLI, and
  `fredq.raw()` no longer recognizes these command names (GeoFRED was
  never part of the typed library surface — `raw()` was its only access
  point, and that access point is now gone too). Call the FRED Maps API
  directly (e.g. with `httpx`) if you still need this data; see the
  [FRED API docs](https://fred.stlouisfed.org/docs/api/geofred/) for the
  endpoint paths and parameters.

### Internal

- Packaging membership is test-pinned (`tests/test_packaging.py`): the
  wheel carries `py.typed` and the library modules and excludes
  `tests/`/`node_modules/`/`docs/`/`output/`; the sdist carries the test
  corpus and excludes dev-only trees. Added an explicit
  `[tool.hatch.build.targets.sdist] exclude` list — hatchling's
  VCS-ignore-based exclusion silently no-ops when the build root is passed
  as an absolute path inside a git worktree (`.git` is a file there),
  which had let dev trees like `node_modules/` leak into a worktree-built
  sdist.

## [0.3.3]

Maintenance release — no user-facing changes.

### Internal

- Bumped `polars` to 1.42.0 (within the existing `>=1.41,<2.0` pin).
- Bumped development dependencies: tox 4.56.1, pyright 1.1.411, ruff 0.15.20.

## [0.3.2]

### Changed

- Switched the runtime HTTP client from `httpx` to `httpx2`.
- Switched API-key redaction regular expressions from the standard library
  `re` module to `regex`.

### Internal

- Replaced the `pytest-httpx` test dependency with a small local `httpx2`
  transport fixture.

## [0.3.1]

### Changed

- Root `--help` is easier to scan: wider spacing between command names and
  summaries, and each command group (`series`, `category`, `release`, `source`,
  `tag`, `geofred`) now shows a description in its own `--help`.

### Internal

- Bumped development dependencies (tox 4.55.1, pyright 1.1.410, ruff 0.15.16)
  and GitHub Actions (astral-sh/setup-uv 8.2.0).

## [0.3.0]

### Changed

- Parquet output is now written with **polars** instead of pyarrow, and polars
  is a core dependency. The `parquet` optional extra is removed — parquet works
  with a plain install. **Breaking:** `pip install "fredq[parquet]"` no longer
  resolves (use `pip install fredq`).

## [0.2.1]

Maintenance release. No user-facing changes.

### Internal

- Removed the stale `docs/v2-geofred.md` planning note (GeoFRED has shipped).

## [0.2.0]

Command-line grammar overhaul. **Breaking** — the flat `noun-verb` command names
and the `--*-id` flags are replaced by noun groups with positional primary args.

### Changed

- **Commands are now noun groups with verb leaves.** e.g. `fredq series-observations`
  → `fredq series observations`, `fredq releases` → `fredq release list`,
  `fredq tags-series` → `fredq tag series`. Groups: `series`, `category`,
  `release`, `source`, `tag`, plus `geofred` (unchanged). A bare group prints its
  subcommands.
- **Primary arguments are positional, not flags.** The single primary required
  argument of each command is now positional and its flag is removed. e.g.
  `fredq series --series-id GNPCA` → `fredq series show GNPCA`;
  `fredq series-search --search-text "cpi"` → `fredq series search "cpi"`;
  `fredq tags-series --tag-names "usa;monthly"` → `fredq tag series "usa;monthly"`.
  Secondary required args stay flags (e.g. `--tag-names` on `* related-tags`).
- `releases-dates` and `release-dates` split into two clear commands:
  `release calendar` (all releases, `/fred/releases/dates`) and
  `release dates ID` (one release, `/fred/release/dates`).
- Version is now derived from the git tag via `hatch-vcs` (no hardcoded
  `__version__`).

### Fixed

- Root global options (`--api-key`, `--no-key-file`, `--verbose`) supplied before
  a command are no longer silently dropped by the group parsers.

### Internal

- Tag-driven release flow with a `twine check` gate; CHANGELOG + RELEASING docs;
  Dependabot (uv + GitHub Actions) with grouped minor/patch updates.

## [0.1.0]

Initial release.

### Added

- CLI for every public FRED API endpoint, printing raw FRED JSON to stdout.
- Endpoint-specific commands across series, search, tags, categories,
  releases, release tables, and sources.
- `series-observations` unit transforms (`--units`) and frequency aggregation
  (`--frequency`).
- ALFRED point-in-time support: `--realtime-start` / `--realtime-end` and
  `series-vintagedates`.
- GeoFRED / Maps regional data via the `geofred` subcommand group
  (`series-group`, `series-data`, `regional-data`, `shapes`).
- Typed Parquet output for `series-observations` (`--format parquet --out`),
  via the optional `parquet` extra.
- Adaptive `--help` generated from command metadata, with parameters, allowed
  value sets, and examples.
- API key resolution from `FRED_API_KEY`, `~/.fredq/api_key`, or `--api-key`,
  with the key redacted from all errors and logs.
- Exit-code contract: `0` success, `1` FRED request failure, `2` usage error.

[Unreleased]: https://github.com/joce/fredq/compare/v0.4.2...HEAD
[0.4.2]: https://github.com/joce/fredq/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/joce/fredq/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/joce/fredq/compare/v0.3.3...v0.4.0
[0.3.3]: https://github.com/joce/fredq/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/joce/fredq/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/joce/fredq/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/joce/fredq/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/joce/fredq/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/joce/fredq/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/joce/fredq/releases/tag/v0.1.0
