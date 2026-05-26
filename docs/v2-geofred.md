# fredq v2 — GeoFRED (Maps) API

Deferred from v1.

## Why deferred

- v1 scope: ~31 core FRED endpoints, single base URL (`https://api.stlouisfed.org/fred/...`).
- GeoFRED adds:
  - Different base URL (`https://api.stlouisfed.org/geofred/...`) → metadata table needs `base_url` per command.
  - GeoJSON shape-file output (megabytes) → needs `--output file` flag, not stdout-friendly.
  - Region-type param surface (state / county / MSA / Federal Reserve District / BEA region / NECTA).
- Core FRED covers national macro (rates, CPI, unemployment, GDP) — 95% of financial-agent need.
- Cleaner to ship v1 + prove metadata-driven CLI pattern, then layer GeoFRED.

## Scope for v2

### Endpoints (~5)

| Endpoint | Returns | Notes |
|---|---|---|
| `geofred/series/group` | JSON | Group metadata: frequency, region type, units. |
| `geofred/series/data` | JSON | Regional time series for one series ID. |
| `geofred/regional/data` | JSON | Snapshot — all regions, one date. |
| `geofred/series/meta` | JSON | Series metadata at geo level. |
| `geofred/shapes/file` | **GeoJSON** | Region polygons. Map rendering only. Bytes-heavy. |

### Param surface additions

- `region_type`: `state`, `county`, `msa`, `country`, `frb`, `bea`, `censusregion`, `censusdivision`, `necta`, `state-msa`.
- `date` / `start_date` / `end_date`: regional snapshots and time series.
- `transformation`: same as core FRED units transforms (`lin`, `chg`, `pch`, etc.) — verify per endpoint.

### Output handling

- `shapes/file` cannot reasonably print to stdout → support `--output PATH` for GeoJSON dump.
- Other endpoints stay JSON-to-stdout (matches Yogurt rule).
- Parquet `--format parquet` likely irrelevant for geo (regional snapshots are small; shapes aren't tabular).

## When to revisit

Trigger conditions for picking up v2:

- Real thesis needs regional data:
  - Regional bank picks → state unemployment / housing.
  - REIT picks → metro vacancy / rent indices.
  - Homebuilder picks → state housing permits.
  - Commodity / energy plays → regional industrial production.
- v1 has shipped, metadata-table pattern proven.
- No earlier than: 1 month post-v1 release.

## Implementation hints (for future-me)

- Metadata table needs second `base_url` column or per-command `base_url` field; default = core FRED base.
- Reuse v1 auth handling (env `FRED_API_KEY` / file) — same key works for GeoFRED.
- New CLI subcommand group `geofred` to keep namespace separate from `fred`.
- Consider `--shape-format geojson|topojson` if FRED ever adds TopoJSON; today GeoJSON only.

## References

- FRED Maps docs: `https://fred.stlouisfed.org/docs/api/geofred/`
- Example wrapper for reference: `pyfredapi.maps` module, `pystlouisfed.FREDMaps`.
