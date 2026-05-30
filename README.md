# fredq

[![CI](https://github.com/joce/fredq/actions/workflows/ci.yml/badge.svg)](https://github.com/joce/fredq/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/joce/fredq/graph/badge.svg)](https://codecov.io/gh/joce/fredq)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![GitHub License](https://img.shields.io/github/license/joce/fredq)](https://github.com/joce/fredq/blob/main/LICENSE)

FRED Query — Federal Reserve Economic Data on the command line.

fredq brings the [FRED](https://fred.stlouisfed.org/docs/api/fred/) (Federal
Reserve Economic Data) HTTP endpoints to the command line. It is built for
scripts, agents, and quick terminal work that needs the JSON returned by the
FRED API.

The project stays deliberately close to the source. It does not reshape FRED
responses, define economic domain models, or add a discovery API beyond CLI
help.

## Features

- Raw FRED JSON on stdout, with no pretty-printing or interpretation.
- Endpoint-specific commands for every public FRED API endpoint.
- Generated help that includes examples, parameters, and known value sets.
- Typed Parquet output for `series-observations` when a long time series is
  more useful as a columnar table than as JSON.
- ALFRED point-in-time support (`--realtime-start`, `--realtime-end`,
  `series-vintagedates`).
- GeoFRED / Maps regional data (`geofred` subcommands): regional time series,
  all-region snapshots, series-group metadata, and GeoJSON shape files.

## Install

fredq is a Python 3.10+ project. Install it as a tool with
[uv](https://docs.astral.sh/uv/) or with pip:

```powershell
uv tool install fredq
# or
pip install fredq
```

For Parquet output, include the `parquet` extra:

```powershell
uv tool install "fredq[parquet]"
# or
pip install "fredq[parquet]"
```

Then run:

```powershell
fredq --help
```

### From Source

To run from a local checkout (development):

```powershell
uv sync --all-groups
uv run fredq --help
```

Or install the checkout as a tool:

```powershell
uv tool install .
fredq --help
```

## API Key

The FRED API requires a free API key. Request one at
<https://fred.stlouisfed.org/docs/api/api_key.html>.

fredq reads the key from, in order:

1. The `FRED_API_KEY` environment variable.
2. The first non-empty line of `~/.fredq/api_key`.
3. The `--api-key` flag (visible in process listings; prefer the env var).

On POSIX systems, restrict the key file so only your user can read it:

```bash
chmod 600 ~/.fredq/api_key
```

fredq emits a warning if the file is readable by group or world. To disable
the file fallback entirely (for hermetic runs), set `FREDQ_DISABLE_KEY_FILE=1`
or pass `--no-key-file`.

fredq never prints, logs, or echoes the API key. The key is also redacted
from URLs in error messages and from any httpx debug logs emitted under
`--verbose`.

## Quick Start

Show metadata for a series:

```powershell
uv run fredq series --series-id GNPCA
```

Fetch a series' observations:

```powershell
uv run fredq series-observations --series-id CPIAUCSL
```

Apply a unit transformation and frequency aggregation:

```powershell
uv run fredq series-observations --series-id CPIAUCSL --units pch --frequency m
```

Search for a series by keyword:

```powershell
uv run fredq series-search --search-text "10-year treasury" --limit 10
```

Browse the FRED category tree from the root:

```powershell
uv run fredq category-children --category-id 0
```

List recent economic releases:

```powershell
uv run fredq releases --limit 10
```

List recent release publication dates across all releases:

```powershell
uv run fredq releases-dates --limit 20
```

Show metadata for a specific release (53 = GDP):

```powershell
uv run fredq release --release-id 53
```

Find all series tagged with a set of FRED tags:

```powershell
uv run fredq tags-series --tag-names "usa;monthly;cpi" --limit 25
```

ALFRED point-in-time: see what GDP looked like on a past date:

```powershell
uv run fredq series-vintagedates --series-id GNPCA
uv run fredq series-observations --series-id GNPCA --realtime-start 2024-09-25
```

Fetch GeoFRED regional data — per-capita income by state for one year:

```powershell
uv run fredq geofred series-group --series-id WIPCPI
uv run fredq geofred series-data --series-id WIPCPI --start-date 2022-01-01
```

## Parquet Output

`series-observations` can write a typed Parquet table instead of raw JSON.
Install with the `parquet` extra to pull in `pyarrow`:

```powershell
uv sync --extra parquet
```

Then pass `--format parquet --out PATH`:

```powershell
uv run fredq series-observations --series-id CPIAUCSL --units pch --frequency m \
  --format parquet --out cpi_yoy.parquet
```

On success a single JSON descriptor line goes to stdout (the file format, out
path, row count, byte size). The Parquet schema is `date` (date32), `value`
(float64), `realtime_start` (date32), `realtime_end` (date32). FRED's
missing-value sentinel `.` is written as `NaN`. The full response envelope
(count, offset, limit, observation range, units, sort order) and the request
context (units, frequency, realtime range) are stored as schema key-value
metadata so the table is self-describing.

Parquet writes are scoped to `series-observations` only; every other command
stays JSON-only, and rejects `--format parquet` with a usage error. Parquet
output assumes FRED's default observation layout (one row per observation);
fredq does not expose FRED's alternative `output_type` modes.

## Discovering IDs

Most commands take an ID (`--series-id`, `--category-id`, `--release-id`,
`--source-id`). If you don't know one yet, start with the commands that need no
ID, then chain:

```powershell
# Find a series ID by keyword
uv run fredq series-search --search-text "unemployment rate" --limit 10

# List the catalogs
uv run fredq releases --limit 1000   # release IDs
uv run fredq sources                 # source IDs
uv run fredq tags --limit 50         # tag names

# Walk the category tree from the root (0 = root)
uv run fredq category-children --category-id 0
```

Then use the ID with the matching command:

```powershell
uv run fredq series-observations --series-id DGS10
uv run fredq category-series --category-id 106
uv run fredq release-series --release-id 10
```

## Commands

Use root help to see the command list:

```powershell
uv run fredq --help
```

Current commands, grouped by how often they're reached for:

**Daily-driver fetches**

| Command | FRED data |
| --- | --- |
| `series` | Show metadata for one FRED series (title, units, frequency, observation range). |
| `series-observations` | Fetch the observation values for one FRED series. |

**Series discovery**

| Command | FRED data |
| --- | --- |
| `series-search` | Search FRED series by keyword. |
| `series-search-tags` | List tags for a series full-text search. |
| `series-search-related-tags` | List tags related to a search and existing tag filter. |
| `tags-series` | List series matching a set of FRED tags. |
| `tags` | List all FRED tags. |
| `related-tags` | List tags related to an existing tag filter. |

**Series-bound analysis**

| Command | FRED data |
| --- | --- |
| `series-vintagedates` | List vintage dates (revision dates) for one FRED series. |
| `series-categories` | List categories that contain a given series. |
| `series-tags` | List tags assigned to a FRED series. |
| `series-release` | Show the release that a FRED series belongs to. |
| `series-updates` | List recently updated FRED series. |

**Category browse**

| Command | FRED data |
| --- | --- |
| `category` | Show metadata for one FRED category. |
| `category-children` | List child categories of a FRED category. |
| `category-related` | List categories related to a given FRED category. |
| `category-series` | List series belonging to one FRED category. |
| `category-tags` | List tags for series in one FRED category. |
| `category-related-tags` | List tags related to a category and existing tag filter. |

**Releases and calendar**

| Command | FRED data |
| --- | --- |
| `releases` | List all FRED economic data releases. |
| `releases-dates` | List release dates across all FRED releases. |
| `release` | Show metadata for one FRED release. |
| `release-dates` | List publication dates for one FRED release. |
| `release-series` | List series belonging to one FRED release. |
| `release-sources` | List sources for one FRED release. |
| `release-tags` | List tags for one FRED release. |
| `release-related-tags` | List tags related to a release and existing tag filter. |
| `release-tables` | Fetch the hierarchical data table for one FRED release. |

**Sources**

| Command | FRED data |
| --- | --- |
| `sources` | List all FRED data sources. |
| `source` | Show metadata for one FRED source. |
| `source-releases` | List releases published by one FRED source. |

**GeoFRED / Maps (`geofred` subcommands)**

| Command | FRED data |
| --- | --- |
| `geofred series-group` | Show GeoFRED series-group metadata (region type, season, frequency, units). |
| `geofred series-data` | Fetch the regional time series for one FRED series. |
| `geofred regional-data` | Fetch a regional snapshot — all regions for a single date. |
| `geofred shapes` | Download a GeoJSON shape file for a region type, to `--out`. |

The GeoFRED endpoints use a different base URL and return regional data keyed by
FIPS code. `geofred shapes` returns Highcharts-format GeoJSON whose coordinates
are in a Lambert Conformal Conic projection (not WGS84); reproject before mixing
with lat/lon basemaps. See `fredq geofred --help` for the full subcommand list.

Each endpoint has its own adaptive help:

```powershell
uv run fredq series --help
uv run fredq series-observations --help
uv run fredq series-search --help
uv run fredq releases-dates --help
```

Endpoint help is the primary documentation surface. It shows the FRED target
endpoint, accepted parameters, allowed value sets, defaults, and examples.

## Dates, Booleans, and Tag Lists

Date parameters accept:

- `YYYY-MM-DD` calendar dates.
- ISO 8601 datetimes (the time component is dropped; UTC assumed for naive
  values).
- Unix timestamps in seconds (≥10 digits).

Boolean parameters accept common true and false forms such as `true`, `false`,
`1`, `0`, `yes`, and `no`.

Tag lists (`--tag-names`, `--exclude-tag-names`) use semicolons as
separators, matching FRED's wire format:

```powershell
uv run fredq tags-series --tag-names "usa;annual"
```

## ALFRED Point-in-Time

Most endpoints accept `--realtime-start` and `--realtime-end` to view data
as of a historical date (the [ALFRED](https://alfred.stlouisfed.org/)
archival API). Combined with `series-vintagedates`, this lets you replay
what an analyst would have seen on a specific past date — useful for
backtests and for distinguishing data revisions from real-time signals.

```powershell
# When were GNP revisions published?
uv run fredq series-vintagedates --series-id GNPCA

# What did GNP look like on 2024-09-25?
uv run fredq series-observations --series-id GNPCA \
  --realtime-start 2024-09-25 --realtime-end 2024-09-25
```

## Output Contract

fredq writes the FRED response body to stdout exactly as returned. This makes
it easy to pipe into tools that expect JSON:

```powershell
uv run fredq series --series-id GNPCA | jq .
uv run fredq releases --limit 25 | jq '.releases[].name'
```

Diagnostics, warnings, and errors are written to stderr. The exit code is
`0` on success, `1` on a FRED request failure, and `2` on a usage or
configuration error.

## Development

Install development dependencies:

```powershell
uv sync --all-groups
```

Run the test suite:

```powershell
uv run pytest
```

Run checks locally:

```powershell
uv run black --check .
uv run ruff format --check --diff .
uv run ruff check .
uv run pyright
uv run pytest -n auto
```

Run the full project check, including Python checks across supported
versions and spelling:

```powershell
uv run tox
```

When adding or changing command metadata, update validation, adaptive help,
and tests together. Then verify the relevant command against FRED with its
help, minimal required parameters, and representative optional parameters.

## License

fredq is released under the MIT License. See [LICENSE](LICENSE).
