# fredq

[![CI](https://github.com/joce/fredq/actions/workflows/ci.yml/badge.svg)](https://github.com/joce/fredq/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/joce/fredq/graph/badge.svg)](https://codecov.io/gh/joce/fredq)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![GitHub License](https://img.shields.io/github/license/joce/fredq)](https://github.com/joce/fredq/blob/main/LICENSE)

fredq brings [FRED](https://fred.stlouisfed.org/docs/api/fred/) (Federal
Reserve Economic Data) to Python two ways: a typed library for programs
(`fredq.Series("DGS10").observations()` returns a polars frame; `.info()`
returns a validated, typed record) and an LLM-friendly command line
(`fredq series observations DGS10`) that prints the raw JSON FRED returns,
byte-for-byte, for scripts, agents, and quick terminal work.

## Install

fredq is a Python 3.10+ package:

```powershell
pip install fredq
# or, as a standalone CLI tool
uv tool install fredq
```

Add the `pandas` extra for `to_pandas()` / `to_arrow()` frame conversions:

```powershell
pip install "fredq[pandas]"
```

A free FRED API key is required — see [Auth](#auth).

## Library quickstart

```python
import fredq

# Observations come back as a typed, polars-backed frame.
obs = fredq.Series("DGS10").observations(observation_start="2024-01-01")
df = obs.to_polars()          # or .to_pandas() / .to_arrow() (needs [pandas]) / .to_dicts()
print(obs.meta.units, obs.meta.count)   # the response envelope, corpus-typed

# Metadata calls return validated pydantic models with real fields.
info = fredq.Series("DGS10").info()
print(info.title, info.frequency, info.observation_start)

# Free-text search, releases, sources — all typed.
hits = fredq.search_series("10-year treasury", limit=10)
for s in hits.seriess:
    print(s.id, s.title)

release = fredq.Release(53).info()  # 53 = GDP
print(release.name, release.link)
```

Errors are raised as typed exceptions instead of surfacing raw HTTP details:

```python
from fredq import FredApiError

try:
    fredq.Series("NOT-A-REAL-SERIES").info()
except FredApiError as exc:
    print(exc.error_code, exc.error_message)
```

Configure the shared client once, before the first call (API key, timeout):

```python
fredq.configure(api_key="...", timeout=None)
```

Anything without a first-class method is reachable through the escape
hatch, which validates parameters exactly like the typed calls and returns
the parsed payload as a plain dict:

```python
payload = fredq.raw("series", series_id="DGS10")
```

## Library surface

Every entity class binds one ID and exposes endpoint methods as
keyword-only calls (wire parameter names, unchanged from FRED's own
spelling). Every call is one HTTP request and returns a typed pydantic
model, except `Series.observations()`, which returns an `Observations`
frame.

| Entity | Methods |
| --- | --- |
| `Series(series_id)` | `info`, `observations`, `vintage_dates`, `categories`, `tags`, `release` |
| `Category(category_id)` | `info`, `children`, `related`, `series`, `tags`, `related_tags` |
| `Release(release_id)` | `info`, `dates`, `series`, `sources`, `tags`, `related_tags`, `tables` |
| `Source(source_id)` | `info`, `releases` |

Module-level functions cover the endpoints with no natural entity owner:

| Function | FRED data |
| --- | --- |
| `search_series(search_text, ...)` | Search FRED series by keyword. |
| `search_series_tags(series_search_text, ...)` | Tags for a series full-text search. |
| `search_series_related_tags(series_search_text, tag_names, ...)` | Tags related to a search and existing tag filter. |
| `series_updates(...)` | Recently updated FRED series. |
| `releases(...)` | All FRED economic data releases. |
| `release_calendar(...)` | Release dates across all FRED releases. |
| `sources(...)` | All FRED data sources. |
| `tags(...)` | All FRED tags. |
| `tag_series(tag_names, ...)` | Series matching a set of FRED tags. |
| `related_tags(tag_names, ...)` | Tags related to an existing tag filter. |
| `raw(command, **params)` | Escape hatch — any command by name. |
| `configure(*, api_key=None, timeout=None)` | Set shared-client options before the first call. |

Date-like parameters (`observation_start`, `realtime_start`, ...) accept a
`str`, `datetime.date`, or `datetime.datetime`. Errors are raised as
`fredq.FredApiError` (FRED's structured error response) or
`fredq.FredClientUsageError` (invalid arguments caught before any request is
sent); both subclass `fredq.FredqError`.

## Typed models

Every typed return value is a frozen pydantic model under `fredq.models`,
built directly from a corpus of real FRED responses: fields are marked
required only when they are present in 100% of the corpus's captures for
that endpoint, and optional otherwise — no guessing from documentation.
Unrecognized fields land on `model_extra` rather than raising, so a new FRED
field surfaces as data, not a crash. fredq ships [PEP 561](https://peps.python.org/pep-0561/)
type information (`py.typed`), so type checkers see the real return types
without stubs.

## Examples

[`examples/fred_explorer.py`](examples/fred_explorer.py) is an interactive
[marimo](https://marimo.io) notebook built entirely on the library: a series
explorer with units transforms and frequency aggregation, multi-series
comparison, catalog search, ALFRED vintage-revision analysis, and a
mortgage-vs-Treasury spread dashboard. Run it without adding dependencies:

```sh
uv run --with marimo --with altair marimo edit examples/fred_explorer.py
```

## Command line

The CLI is a separate, from-scratch layer: it prints the FRED response body
to stdout exactly as returned, with no reshaping or interpretation — the
library's typed models are not involved. It is built for scripts, agents,
and terminal use that want raw JSON.

```powershell
fredq --help
```

### Quick start

Show metadata for a series:

```powershell
fredq series show GNPCA
```

Fetch a series' observations:

```powershell
fredq series observations CPIAUCSL
```

Apply a unit transformation and frequency aggregation:

```powershell
fredq series observations CPIAUCSL --units pch --frequency m
```

Search for a series by keyword:

```powershell
fredq series search "10-year treasury" --limit 10
```

Browse the FRED category tree from the root:

```powershell
fredq category children 0
```

List recent economic releases:

```powershell
fredq release list --limit 10
```

List recent release publication dates across all releases:

```powershell
fredq release calendar --limit 20
```

Show metadata for a specific release (53 = GDP):

```powershell
fredq release show 53
```

Find all series tagged with a set of FRED tags:

```powershell
fredq tag series "usa;monthly;cpi" --limit 25
```

ALFRED point-in-time: see what GDP looked like on a past date:

```powershell
fredq series vintage-dates GNPCA
fredq series observations GNPCA --realtime-start 2024-09-25
```

### Parquet output

`series observations` can write a typed Parquet table instead of raw JSON.
Parquet output is included in a plain install — no extra required. Pass
`--format parquet --out PATH`:

```powershell
fredq series observations CPIAUCSL --units pch --frequency m \
  --format parquet --out cpi_yoy.parquet
```

On success a single JSON descriptor line goes to stdout (the file format, out
path, row count, byte size). The Parquet schema is `date` (date32), `value`
(float64), `realtime_start` (date32), `realtime_end` (date32). FRED's
missing-value sentinel `.` is written as `NaN`. The full response envelope
(count, offset, limit, observation range, units, sort order) and the request
context (units, frequency, realtime range) are stored as schema key-value
metadata so the table is self-describing.

Parquet writes are scoped to `series observations` only; every other command
stays JSON-only, and rejects `--format parquet` with a usage error. Parquet
output assumes FRED's default observation layout (one row per observation);
fredq does not expose FRED's alternative `output_type` modes.

### Discovering IDs

Most commands take an ID as a positional argument. If you don't know one yet,
start with the commands that need no ID, then chain:

```powershell
# Find a series ID by keyword
fredq series search "unemployment rate" --limit 10

# List the catalogs
fredq release list --limit 1000  # release IDs
fredq source list                # source IDs
fredq tag list --limit 50        # tag names

# Walk the category tree from the root (0 = root)
fredq category children 0
```

Then use the ID with the matching command:

```powershell
fredq series observations DGS10
fredq category series 106
fredq release series 10
```

### Commands

Use root help to see the command list:

```powershell
fredq --help
```

Current commands, grouped by how often they're reached for:

**Daily-driver fetches**

| Command | FRED data |
| --- | --- |
| `series show` | Show metadata for one FRED series (title, units, frequency, observation range). |
| `series observations` | Fetch the observation values for one FRED series. |

**Series discovery**

| Command | FRED data |
| --- | --- |
| `series search` | Search FRED series by keyword. |
| `series search-tags` | List tags for a series full-text search. |
| `series search-related-tags` | List tags related to a search and existing tag filter. |
| `tag series` | List series matching a set of FRED tags. |
| `tag list` | List all FRED tags. |
| `tag related` | List tags related to an existing tag filter. |

**Series-bound analysis**

| Command | FRED data |
| --- | --- |
| `series vintage-dates` | List vintage dates (revision dates) for one FRED series. |
| `series categories` | List categories that contain a given series. |
| `series tags` | List tags assigned to a FRED series. |
| `series release` | Show the release that a FRED series belongs to. |
| `series updates` | List recently updated FRED series. |

**Category browse**

| Command | FRED data |
| --- | --- |
| `category show` | Show metadata for one FRED category. |
| `category children` | List child categories of a FRED category. |
| `category related` | List categories related to a given FRED category. |
| `category series` | List series belonging to one FRED category. |
| `category tags` | List tags for series in one FRED category. |
| `category related-tags` | List tags related to a category and existing tag filter. |

**Releases and calendar**

| Command | FRED data |
| --- | --- |
| `release list` | List all FRED economic data releases. |
| `release calendar` | List release dates across all FRED releases. |
| `release show` | Show metadata for one FRED release. |
| `release dates` | List publication dates for one FRED release. |
| `release series` | List series belonging to one FRED release. |
| `release sources` | List sources for one FRED release. |
| `release tags` | List tags for one FRED release. |
| `release related-tags` | List tags related to a release and existing tag filter. |
| `release tables` | Fetch the hierarchical data table for one FRED release. |

**Sources**

| Command | FRED data |
| --- | --- |
| `source list` | List all FRED data sources. |
| `source show` | Show metadata for one FRED source. |
| `source releases` | List releases published by one FRED source. |

A bare group prints its list of subcommands; each leaf command has its own
adaptive help:

```powershell
fredq series --help              # group: lists the series subcommands
fredq series observations --help # leaf: full endpoint help
fredq series search --help
fredq release calendar --help
```

Leaf-command help is the primary documentation surface. It shows the FRED target
endpoint, accepted parameters, allowed value sets, defaults, and examples.

### Dates, booleans, and tag lists

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
fredq tag series "usa;annual"
```

### ALFRED point-in-time

Most endpoints accept `--realtime-start` and `--realtime-end` to view data
as of a historical date (the [ALFRED](https://alfred.stlouisfed.org/)
archival API). Combined with `series vintage-dates`, this lets you replay
what an analyst would have seen on a specific past date — useful for
backtests and for distinguishing data revisions from real-time signals.

```powershell
# When were GNP revisions published?
fredq series vintage-dates GNPCA

# What did GNP look like on 2024-09-25?
fredq series observations GNPCA \
  --realtime-start 2024-09-25 --realtime-end 2024-09-25
```

### Output contract

fredq writes the FRED response body to stdout exactly as returned. This makes
it easy to pipe into tools that expect JSON:

```powershell
fredq series show GNPCA | jq .
fredq release list --limit 25 | jq '.releases[].name'
```

Diagnostics, warnings, and errors are written to stderr. The exit code is
`0` on success, `1` on a FRED request failure, and `2` on a usage or
configuration error.

## Auth

The FRED API requires a free API key. Request one at
<https://fred.stlouisfed.org/docs/api/api_key.html>.

Both the library and the CLI read the key from, in order:

1. The `FRED_API_KEY` environment variable.
2. The first non-empty line of `~/.fredq/api_key`.
3. CLI only: the `--api-key` flag (visible in process listings; prefer the
   env var). Library callers pass `api_key=` to `fredq.configure()` instead.

On POSIX systems, restrict the key file so only your user can read it:

```bash
chmod 600 ~/.fredq/api_key
```

fredq emits a warning if the file is readable by group or world. To disable
the file fallback entirely (for hermetic runs), set `FREDQ_DISABLE_KEY_FILE=1`
or pass `--no-key-file` (CLI), or call `fredq.configure(api_key=...)` with an
explicit key (library).

fredq never prints, logs, or echoes the API key. The key is also redacted
from URLs in error messages and from any httpx2 debug logs emitted under
`--verbose`.

## Development

See [AGENTS.md](AGENTS.md) for architecture, conventions, and the
CLI-layer/library-layer split. In short:

```powershell
uv sync --all-groups
uv run pytest
uv run tox   # full gate: formatting, lint, type check, tests across supported Python versions, spelling
```

## License

fredq is released under the MIT License. See [LICENSE](LICENSE).
