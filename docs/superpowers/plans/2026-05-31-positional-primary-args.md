# Positional Primary Arguments — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each fredq command take its single primary required argument as a positional, removing the corresponding flag.

**Architecture:** The CLI plumbing already supports positionals — `ParamSpec.positional` exists, `ParamSpec.option` returns the bare name when positional, `cli._add_command_param` registers a positional via `parser.add_argument(param.name, metavar=..., help=...)`, and `_collect_params` reads by `param.name` so coercion/validation are unchanged. This change is therefore **metadata only** (`commands.py`), plus examples, tests, and docs. No changes to `params.py` or `cli.py` argument wiring.

**Tech Stack:** Python 3.10+, argparse, pytest, ruff, pyright, cspell. Run via `uv`.

---

## Key facts (verified against current code)

- `ParamSpec(positional: bool = False, ...)` — `src/fredq/params.py:32`.
- Positional registration — `src/fredq/cli.py:121-127` (no `--`, no `required=`, uses `metavar`).
- Shared ID constants in `commands.py`: `_SERIES_ID_PARAM`, `_CATEGORY_ID_PARAM`,
  `_RELEASE_ID_PARAM`, `_SOURCE_ID_PARAM`. Each is **always the primary arg** wherever used, so flipping the constant flips every command that uses it.
- `tag-names` already split: `_TAG_NAMES_PARAM` (optional filter), `_TAG_NAMES_REQUIRED_PARAM` (required flag, used by the `*-related-tags` commands). A **new** positional variant is needed for `tags-series` / `related-tags`.
- Primary search text is per-command inline (`series-search`, `series-search-tags`, `series-search-related-tags`), not a shared constant. `_SEARCH_TEXT_PARAM` is the *optional filter* `--search-text` on other commands — **do not** make it positional.
- geofred `regional-data` primary = its `series_group` param; geofred `shapes` primary = its `shape` param (both inline in the geofred command defs).

**Convention for every task:** TDD — update the affected tests to expect the positional form first, watch them fail, then flip the metadata, watch them pass, rewrite that command's `examples`, commit. Find old-flag usages with:

```
uv run python -c "import re,sys"   # (placeholder; use the grep below)
```
Use grep across tests: `rg -- "--series-id|--category-id|--release-id|--source-id|--search-text|--series-search-text|--tag-names" tests/`.

Test files in scope: `tests/test_cli_endpoints.py`, `tests/test_cli_endpoints_groups245.py`, `tests/test_cli_geofred.py`, `tests/test_cli.py`, `tests/test_cli_architecture.py`.

---

## Task 1: Add positional tag-names variant

**Files:**
- Modify: `src/fredq/commands.py` (near `_TAG_NAMES_REQUIRED_PARAM`, ~line 327)

- [ ] **Step 1: Add the constant**

```python
_TAG_NAMES_POSITIONAL_PARAM: Final[ParamSpec] = ParamSpec(
    name="tag_names",
    cli_name="tag-names",
    kind=ParamKind.CSV,
    help="Semicolon-separated list of tag names (e.g. 'usa;monthly').",
    positional=True,
    required=True,
    csv_separator=";",
    metavar="TAGS",
)
```

- [ ] **Step 2: Verify it imports**

Run: `uv run python -c "from fredq.commands import _TAG_NAMES_POSITIONAL_PARAM as p; print(p.option)"`
Expected: prints `tag_names`

- [ ] **Step 3: Commit**

```bash
git add src/fredq/commands.py
git commit -m "internal: add positional tag-names param variant"
```

---

## Task 2: Series-ID family → positional

Affects: `series`, `series-observations`, `series-vintagedates`, `series-categories`, `series-tags`, `series-release`, `geofred series-group`, `geofred series-data` (all use `_SERIES_ID_PARAM`).

**Files:**
- Modify: `src/fredq/commands.py` (`_SERIES_ID_PARAM`, ~line 64; examples in each command above)
- Test: `tests/test_cli_endpoints.py`, `tests/test_cli_geofred.py`

- [ ] **Step 1: Update tests to expect positional**

Replace every `["series", "--series-id", "GNPCA"]`-style arg list with the positional form `["series", "GNPCA"]` (and likewise for the other series-id commands). Example edit:

```python
# before
args = parser.parse_args(["series-observations", "--series-id", "DGS10"])
# after
args = parser.parse_args(["series-observations", "DGS10"])
assert args.series_id == "DGS10"
```

Add a missing-positional case:

```python
def test_series_requires_positional_id():
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["series"])
    assert exc.value.code == 2
```

- [ ] **Step 2: Run, verify failures**

Run: `uv run pytest tests/test_cli_endpoints.py tests/test_cli_geofred.py -q`
Expected: FAIL (metadata still registers `--series-id`).

- [ ] **Step 3: Flip the constant**

In `_SERIES_ID_PARAM`, add `positional=True` (keep `required=True`, `metavar="ID"`):

```python
_SERIES_ID_PARAM: Final[ParamSpec] = ParamSpec(
    name="series_id",
    cli_name="series-id",
    kind=ParamKind.STRING,
    help="FRED series identifier (e.g. GNPCA, DGS10, CPIAUCSL).",
    positional=True,
    required=True,
    metavar="ID",
)
```

- [ ] **Step 4: Rewrite examples**

In every command using `_SERIES_ID_PARAM`, change `--series-id X` to `X` in the `examples` tuples. e.g. `"fredq series-observations --series-id GNPCA"` → `"fredq series-observations GNPCA"`; `"fredq geofred series-group --series-id WIPCPI"` → `"fredq geofred series-group WIPCPI"`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_cli_endpoints.py tests/test_cli_geofred.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/fredq/commands.py tests/
git commit -m "change: series-id is now a positional argument"
```

---

## Task 3: Category-ID family → positional

Affects: `category`, `category-children`, `category-related`, `category-series`, `category-tags`, `category-related-tags` (use `_CATEGORY_ID_PARAM`).

**Files:**
- Modify: `src/fredq/commands.py` (`_CATEGORY_ID_PARAM`, ~line 269; examples)
- Test: `tests/test_cli_endpoints.py`, `tests/test_cli_endpoints_groups245.py`

- [ ] **Step 1: Update tests** — replace `["category-children", "--category-id", "0"]` → `["category-children", "0"]`; for `category-related-tags`, keep the secondary flag: `["category-related-tags", "32991", "--tag-names", "usa"]`. Add a missing-positional `SystemExit code == 2` case for `category`.

- [ ] **Step 2: Run, verify failures**

Run: `uv run pytest tests/test_cli_endpoints.py tests/test_cli_endpoints_groups245.py -q`
Expected: FAIL.

- [ ] **Step 3: Flip the constant** — add `positional=True` to `_CATEGORY_ID_PARAM` (keep `required=True`, `metavar="ID"`, `min_value=0`).

- [ ] **Step 4: Rewrite examples** — `--category-id N` → `N` in all category command examples; `category-related-tags` examples become `fredq category-related-tags 32991 --tag-names usa`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_cli_endpoints.py tests/test_cli_endpoints_groups245.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/fredq/commands.py tests/
git commit -m "change: category-id is now a positional argument"
```

---

## Task 4: Release-ID family → positional

Affects: `release`, `release-dates`, `release-series`, `release-sources`, `release-tags`, `release-related-tags`, `release-tables` (use `_RELEASE_ID_PARAM`).

**Files:**
- Modify: `src/fredq/commands.py` (`_RELEASE_ID_PARAM`, ~line 302; examples)
- Test: `tests/test_cli_endpoints.py`, `tests/test_cli_endpoints_groups245.py`

- [ ] **Step 1: Update tests** — `["release", "--release-id", "10"]` → `["release", "10"]`; `release-related-tags` keeps `--tag-names`: `["release-related-tags", "10", "--tag-names", "usa"]`. Add missing-positional `code == 2` case.

- [ ] **Step 2: Run, verify failures** — `uv run pytest tests/test_cli_endpoints.py tests/test_cli_endpoints_groups245.py -q` → FAIL.

- [ ] **Step 3: Flip the constant** — add `positional=True` to `_RELEASE_ID_PARAM` (keep `required=True`, `metavar="ID"`, `min_value=1`).

- [ ] **Step 4: Rewrite examples** — `--release-id N` → `N`; `release-related-tags` example → `fredq release-related-tags 10 --tag-names usa`.

- [ ] **Step 5: Run tests** → PASS.

- [ ] **Step 6: Commit**

```bash
git add src/fredq/commands.py tests/
git commit -m "change: release-id is now a positional argument"
```

---

## Task 5: Source-ID family → positional

Affects: `source`, `source-releases` (use `_SOURCE_ID_PARAM`).

**Files:**
- Modify: `src/fredq/commands.py` (`_SOURCE_ID_PARAM`, ~line 292; examples)
- Test: `tests/test_cli_endpoints.py`

- [ ] **Step 1: Update tests** — `["source", "--source-id", "1"]` → `["source", "1"]`; add missing-positional `code == 2`.

- [ ] **Step 2: Run, verify failures** → FAIL.

- [ ] **Step 3: Flip the constant** — add `positional=True` to `_SOURCE_ID_PARAM` (keep `required=True`, `metavar="ID"`, `min_value=1`).

- [ ] **Step 4: Rewrite examples** — `--source-id N` → `N`.

- [ ] **Step 5: Run tests** → PASS.

- [ ] **Step 6: Commit**

```bash
git add src/fredq/commands.py tests/
git commit -m "change: source-id is now a positional argument"
```

---

## Task 6: Search-text primaries → positional

Affects: `series-search` (inline `search_text`), `series-search-tags` (inline `series_search_text`), `series-search-related-tags` (inline `series_search_text`). Do **not** touch `_SEARCH_TEXT_PARAM` (the optional `--search-text` filter on other commands).

**Files:**
- Modify: `src/fredq/commands.py` (inline params in the three command defs; examples)
- Test: `tests/test_cli_endpoints.py`

- [ ] **Step 1: Update tests** — `["series-search", "--search-text", "cpi"]` → `["series-search", "cpi"]`; `series-search-related-tags` keeps `--tag-names`: `["series-search-related-tags", "inflation", "--tag-names", "usa"]`.

- [ ] **Step 2: Run, verify failures** → FAIL.

- [ ] **Step 3: Add `positional=True`** to the inline primary search param in each of the three command defs. Example (`series-search`):

```python
ParamSpec(
    name="search_text",
    cli_name="search-text",
    kind=ParamKind.STRING,
    help="Search string to match against series titles and notes.",
    positional=True,
    required=True,
    metavar="TEXT",
),
```

Apply the same (`positional=True, required=True`) to the `series_search_text` param in `series-search-tags` and `series-search-related-tags`.

- [ ] **Step 4: Rewrite examples** — `--search-text X`/`--series-search-text X` → `X` (quote multi-word text), keeping `--tag-names` where present.

- [ ] **Step 5: Run tests** → PASS.

- [ ] **Step 6: Commit**

```bash
git add src/fredq/commands.py tests/
git commit -m "change: search text is now a positional argument"
```

---

## Task 7: Tag-list primaries → positional

Affects: `tags-series`, `related-tags`. Swap their required `--tag-names` param for `_TAG_NAMES_POSITIONAL_PARAM` (Task 1).

**Files:**
- Modify: `src/fredq/commands.py` (the `tags-series` and `related-tags` command defs; examples)
- Test: `tests/test_cli_endpoints.py`

- [ ] **Step 1: Update tests** — `["tags-series", "--tag-names", "usa;monthly"]` → `["tags-series", "usa;monthly"]`; same for `related-tags`. Add missing-positional `code == 2`.

- [ ] **Step 2: Run, verify failures** → FAIL.

- [ ] **Step 3: Swap the param** — in the `tags-series` and `related-tags` `params` tuples, replace the current required tag-names entry with `_TAG_NAMES_POSITIONAL_PARAM`. (Leave `_EXCLUDE_TAG_NAMES_PARAM` and other flags as-is.)

- [ ] **Step 4: Rewrite examples** — `--tag-names 'usa;annual'` → `'usa;annual'`.

- [ ] **Step 5: Run tests** → PASS.

- [ ] **Step 6: Commit**

```bash
git add src/fredq/commands.py tests/
git commit -m "change: tag-names is positional for tags-series and related-tags"
```

---

## Task 8: GeoFRED regional-data and shapes → positional

Affects: `geofred regional-data` (primary `series_group`), `geofred shapes` (primary `shape`). Other required args stay flags (`--region-type`, `--date`, `--season`, `--frequency`, `--units`, `--out`).

**Files:**
- Modify: `src/fredq/commands.py` (the `regional-data` and `shapes` geofred defs; examples)
- Test: `tests/test_cli_geofred.py`

- [ ] **Step 1: Update tests** — `["geofred", "regional-data", "--series-group", "882", ...]` → `["geofred", "regional-data", "882", "--region-type", "state", "--date", "2023-01-01", "--season", "NSA", "--frequency", "a", "--units", "Dollars"]`; `["geofred", "shapes", "--shape", "state", "--out", p]` → `["geofred", "shapes", "state", "--out", p]`.

- [ ] **Step 2: Run, verify failures** → FAIL.

- [ ] **Step 3: Add `positional=True`** to the `series_group` param of `regional-data` and the `shape` param of `shapes` (keep their `required=True`, metavars `ID` and `SHAPE`).

- [ ] **Step 4: Rewrite examples** — `--series-group 882` → `882`; `--shape state` → `state` (keep `--out`).

- [ ] **Step 5: Run tests** → PASS.

- [ ] **Step 6: Commit**

```bash
git add src/fredq/commands.py tests/
git commit -m "change: geofred regional-data/shapes take a positional primary arg"
```

---

## Task 9: Docs + root-help epilog

**Files:**
- Modify: `src/fredq/cli.py` (root `epilog`, ~line 250)
- Modify: `README.md` (Discovering IDs, Quick Start, command examples)
- Modify: `AGENTS.md` (help-text rules)

- [ ] **Step 1: Update the root epilog** — change the discovery examples to positional:

```
  fredq series-search "unemployment"                  find series IDs by keyword
  ...
  fredq category-children 0                            root categories (0 = root; drill down)

Then use an ID with the matching command, e.g.:
  fredq series-observations DGS10
  fredq category-series 106
  fredq release-series 10
```

- [ ] **Step 2: Update README** — rewrite every `--series-id`/`--category-id`/`--release-id`/`--source-id`/`--search-text`/`--tag-names`(primary) example to positional across "Discovering IDs", "Quick Start", "Parquet Output", and the ALFRED/geofred examples. Keep secondary flags (`--tag-names` on `*-related-tags`, `--out`, `--units`, etc.).

- [ ] **Step 3: Update AGENTS.md** — add to the help-text rules: "Each command's single primary required arg is a positional (`metavar` shown); all other params are flags. `series-search`/`tags-series`/`related-tags` take their text/tag-list positionally."

- [ ] **Step 4: Verify help renders + spell**

Run: `uv run fredq --help` (eyeball epilog); `npm run spell`
Expected: epilog shows positional examples; spell `Issues found: 0`.

- [ ] **Step 5: Commit**

```bash
git add src/fredq/cli.py README.md AGENTS.md
git commit -m "internal: document positional primary args in help and README"
```

---

## Task 10: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the bundled check**

Run: `uv run tox`
Expected: format, lint (ruff), type (pyright), tests (3.10–3.14), spelling all pass.

- [ ] **Step 2: Live smoke a sample of commands** (needs FRED_API_KEY)

```bash
uv run fredq series GNPCA
uv run fredq series-search "unemployment" --limit 3
uv run fredq tags-series "usa;monthly" --limit 3
uv run fredq category-related-tags 32991 --tag-names usa --limit 3
uv run fredq geofred series-group WIPCPI
```
Expected: each returns JSON (or a clean upstream error), no argparse usage error.

- [ ] **Step 3: Confirm removed flags are gone**

```bash
uv run fredq series --series-id GNPCA   # expect: error, unrecognized arguments
```
Expected: exit `2`, usage error (flag removed).

- [ ] **Step 4: Final state** — all tasks committed; version is tag-derived, so no bump needed until release (next release tag will be `v0.2.0`).

---

## Self-review

- **Spec coverage:** every per-command-map group in the spec maps to a task (series→T2, category→T3, release→T4, source→T5, search→T6, tag-list→T7, geofred→T8, no-positional commands untouched, docs→T9). ✓
- **Placeholders:** none — each metadata edit shows the exact `positional=True` change and example transform; test changes show concrete arg-list rewrites. ✓
- **Consistency:** `_TAG_NAMES_POSITIONAL_PARAM` defined in T1, consumed in T7. Shared ID constants flipped once each. `_SEARCH_TEXT_PARAM` explicitly excluded. ✓
- **No infra changes:** `params.py`/`cli.py` wiring already supports positionals (verified), so no task touches them except the T9 epilog text. ✓
