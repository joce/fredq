---
name: fredq
description: Fetch and analyze FRED (Federal Reserve Economic Data) from the Federal Reserve Bank of St. Louis — time series observations, ALFRED point-in-time vintages and revisions, and the categories/releases/sources/tags catalog — through the fredq Python library (typed pydantic models, polars-backed frames) or its raw-JSON CLI. Use when a task needs U.S. or international economic and financial time series, historical data revisions or point-in-time (as-of) analysis, series/category/release/source/tag discovery, or any FRED API access.
---

# fredq

FRED economic data: observations, ALFRED vintages and revisions, and the
categories/releases/sources/tags catalog — as a typed Python library or a
raw-JSON CLI.

## Quickstart

```bash
pip install fredq
```

A free FRED API key is required — request one at
<https://fred.stlouisfed.org/docs/api/api_key.html> (no billing, no scopes,
just the key). Set it once and every call picks it up:

```bash
export FRED_API_KEY=your-key-here
```

```python
import fredq

obs = fredq.Series("DGS10").observations(observation_start="2024-01-01")
```

No install needed for one-off shell use:

```bash
uvx fredq series observations DGS10 --observation-start 2024-01-01
```

## Two surfaces, one vocabulary

**Library primary:** `import fredq` — typed pydantic models, typed errors,
a polars-backed `Observations` frame for series data.

**CLI secondary:** shell one-offs and no-dependency contexts
(`uvx fredq …`). Same command names as the library; flags mirror kwargs
mechanically: `--observation-start` ↔ `observation_start=`, `--units pch`
↔ `units="pch"`. The CLI prints FRED's raw wire JSON to stdout; the
library returns typed models (or a typed frame for observations) and
raises typed errors for the same call.

Tag-name lists use FRED's own `;`-separated wire format and need shell
quoting: `"usa;quarterly"`.

```bash
fredq series observations CPIAUCSL --units pch
```

```python
pch = fredq.Series("CPIAUCSL").observations(units="pch")
```

## Routing table

| Task | Use |
| --- | --- |
| Data bound to one series, category, release, or source | `Series`/`Category`/`Release`/`Source` methods |
| Catalog-wide search or listing (no single ID to bind) | module-level functions (`search_series`, `releases`, `sources`, `tags`, ...) |
| Point-in-time / ALFRED vintages | `realtime_start`/`realtime_end` kwargs plus `Series.vintage_dates()` |
| An endpoint with no typed wrapper | `raw(command, **params)` |

## Errors

One contract everywhere: every FRED request-level failure (unknown id, bad
parameter value, bad API key) raises `fredq.FredApiError` (`.status_code`,
`.error_code`, `.error_message`) — the same shape for every 400 cause, by
design; there is deliberately no not-found subclass (see
[catalog/SHARP-EDGES.md](catalog/SHARP-EDGES.md)). Transport failures
without FRED's error body raise `FredRequestError`/`FredUnavailableError`;
caller mistakes caught before any request is sent raise
`FredClientUsageError`. A query with zero matches returns an **empty
result** — an empty `seriess`/`categories` list (or `observations: []`) is
a value FRED sent, never an exception.

## Parameters

Do not guess parameter names or values. Run `fredq <noun> <verb> --help`
— it is generated, complete, and authoritative for both surfaces via the
flag↔kwarg mirror rule.

## Domain index

| Domain | Read when… |
| --- | --- |
| [observations](observations/README.md) | fetching series data: windows, units transforms, frequency aggregation, missing values |
| [revisions](revisions/README.md) | working with ALFRED realtime windows, vintage dates, or revision analysis |
| [catalog](catalog/README.md) | searching series, walking the category tree, or browsing releases/sources/tags |
| [dataframes](dataframes/README.md) | converting, joining, or exporting `Observations` frames |
