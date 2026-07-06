# FRED capture corpus

Committed captures of real FRED API responses. This corpus is the ONLY
authority for wire spellings, field presence, and types when writing
response models (see the library-api design spec, evidence discipline).

- Regenerate: `uv run python -m tools.probe` (needs a FRED API key via
  `FRED_API_KEY` or `~/.fredq/api_key`; ~5 min, politeness-limited to
  ~100 requests/min).
- `manifest.json` describes every case: argv (the exact `fredq ...`
  invocation), status (`ok` / `http_error` / `error`), http_status, file.
- A manifest `ok` guarantees the capture parses as JSON. An `error` entry
  carries `http_status: 200` when the payload was corrupt but the HTTP
  transaction succeeded, and `http_status: null` for non-HTTP failures —
  never assume `error` implies `null`.
- All content is scrubbed: the probe redacts `api_key=[REDACTED]` fragments
  and the literal key; `tests/test_corpus.py` sweeps the whole corpus and
  fails on any leak.
- `series-updates/RECENT_WINDOW` has time-relative argv by design; its
  start/end times drift on every regeneration.

## Curation rulings (2026-07-05 run: 94 cases — 85 ok, 9 http_error, 0 error)

- `tags-series/ERR_bogus-tag`: FRED rejects unknown tag names with HTTP 400
  rather than returning an empty list.
- `related-tags/monetary_group-geo`: HTTP 400 — FRED rejects
  `tag_names=monetary` combined with `tag_group_id=geo`. Kept as evidence
  of a valid-params-but-rejected-combination error shape.
- `series-search/EMPTY_RESULT`, `category-children/125_maybe-leaf`,
  `category-related/125_maybe-empty`: HTTP 200 with empty lists — empty
  results are values, not errors. Category 125 is confirmed a leaf.
- `release-tables/175_maybe-no-tables`: release 175 actually HAS table
  elements; the case name records the original uncertainty, the capture is
  the truth.
- `series-observations/DGS10_future-window` (2030 window): HTTP 200 with
  `observations: []` — FRED answers future windows with empty data, not an
  error.
- `series/ERR_bad-api-key`: FRED's 400 body is a static generic message; it
  never echoes submitted key material.
- `series-group/ERR_invalid-id` (removed 2026-07-06, Part 5): GeoFRED
  answered an invalid series id with HTTP 500, unlike the core API's 400 —
  the geofred error family differed. The `geofred` command group, its
  probe cases, and the `series-group`/`series-data`/`regional-data`/`shapes`
  captures were removed entirely in Part 5 of the library-api feature (site
  sunset 2022; API deprecated); the captures remain retrievable from git
  history prior to that removal.
- Missing-value evidence: `series-observations/DEXCAUS_holidays` contains
  `"value": "."` entries (FRED's missing-data sentinel).
- Vintage evidence: `series-observations/UNRATE_vintage-2001` carries three
  distinct realtime windows.

Never hand-edit captures. To change evidence, change the probe plan in
`tools/probe.py` and re-run it.
