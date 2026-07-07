# Sharp edges: catalog

## Category ID `0` is the tree root, not "no category"

**Severity:** low

Wrong way: treating `Category(0)` as an empty or sentinel value, or
guessing that category `1` is the root because it's the smallest "real"
looking ID.

Right way: `Category(0).children()` returns FRED's eight top-level
subject categories; walk the tree down from there. `Category(0).info()`
even names itself back as `"Categories"`, `parent_id=0` — the root is its
own parent.

Evidence: 2026-07-05, corpus-confirmed (`category/root`,
`category-children/root`).

## Zero search hits is a value, not an error

**Severity:** medium

Wrong way: wrapping `search_series()` (or `Category.children()`,
`Category.related()`, and friends) in a `try`/`except`, expecting an
exception when a query has no matches.

Right way: check `result.seriess`/`result.categories` (or `.count`) — an
empty list at HTTP 200 is FRED's real answer for "nothing matched."
Nothing is raised.

Evidence: 2026-07-05, corpus-confirmed (`series-search/EMPTY_RESULT`;
also `category-children/125_maybe-leaf`, `category-related/125_maybe-empty`).

## Unknown tag names raise, they don't come back empty

**Severity:** medium

Wrong way: passing a typo'd or made-up tag name to `tag_series()`,
`tags()`, or `related_tags()` and expecting an empty result list back,
the way an unmatched search behaves.

Right way: catch `FredApiError` — FRED rejects an unrecognized tag name
with HTTP 400 before it ever gets to filtering series.

Evidence: 2026-07-05, corpus-confirmed (`tags-series/ERR_bogus-tag`).

## A `tag_group_id` filter can reject an otherwise-fine tag name

**Severity:** medium

Wrong way: assuming a `tag_names` value that works alone will also work
once you add `tag_group_id`, or concluding a tag doesn't exist anywhere
just because one `tag_names`/`tag_group_id` combination was rejected.

Right way: treat `tag_names` and `tag_group_id` as a joint query — an
unrecognized combination 400s with the identical error shape as a
genuinely nonexistent tag, so don't infer global nonexistence from one
rejected combination; retry without the group filter to check.

Evidence: 2026-07-05, corpus-confirmed (`related-tags/monetary_group-geo`:
`tag_names=monetary` combined with `tag_group_id=geo` → HTTP 400).

## Tag statistics drift between identical calls, seconds apart

**Severity:** low

Wrong way: asserting two back-to-back calls to `tags()`/`Series.tags()`
return byte-identical `popularity`/`series_count` for the same tag, or
caching those numbers indefinitely as if they were static metadata.

Right way: treat `popularity` and `series_count` as eventually-consistent
counters FRED updates server-side in bursts, not stable identifiers —
diff-check with a tolerance, or refetch instead of trusting a cached
value.

Evidence: 2026-07-07, dogfooding (two consecutive `tag list` calls in the
same session returned different counts for the same tag).

## One `FredApiError` shape for every 400 cause — there is no not-found subclass

**Severity:** high

Wrong way: catching a hypothetical `SeriesNotFoundError`/
`CategoryNotFoundError`, or branching on the exception's message text to
tell "does not exist" apart from "bad parameter value" or "bad API key."

Right way: catch `fredq.FredApiError` and, if you need to branch, use
`.status_code`/`.error_code` — never message wording. FRED reports every
4xx cause with the identical `{"error_code": ..., "error_message": ...}`
shape, indistinguishably, and fredq deliberately does not add a
not-found subclass on top of it.

```python
from fredq import FredApiError

try:
    fredq.Category(999999999).info()
except FredApiError as exc:
    print(exc.status_code, exc.error_code, exc.error_message)
```

Evidence: 2026-07-05, corpus-confirmed (`category/ERR_invalid-id`,
`series/ERR_invalid-id`, `series/ERR_bad-api-key` all share one shape).

## GeoFRED is gone — there is no regional/shapefile data

**Severity:** medium

Wrong way: calling (or asking an agent trained on older FRED
documentation to call) `fredq.raw("series-group", ...)` or any
`geofred`-family command for map or regional data.

Right way: those commands do not exist in fredq. FRED itself sunset the
GeoFRED site in 2022, and fredq removed the entire `geofred` command
group in 0.4.0 — regional and shapefile data is not reachable through
this library at all, typed or `raw()`.

Evidence: 2026-07-06, library design constraint (removed in Part 5 of the
library-api feature; see `tests/fixtures/corpus/README.md` in the fredq
repository).
