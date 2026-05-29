# Changelog

All notable changes to fredq are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/joce/fredq/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/joce/fredq/releases/tag/v0.1.0
