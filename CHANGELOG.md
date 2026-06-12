# Changelog

All notable changes to fredq are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/joce/fredq/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/joce/fredq/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/joce/fredq/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/joce/fredq/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/joce/fredq/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/joce/fredq/releases/tag/v0.1.0
