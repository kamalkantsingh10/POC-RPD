# Story 2.6: Extract Filters, Prompts and Saved Filters

Status: review

**Review intensity: Normal** — fixture-checked, and an unresolvable saved-filter reference surfaces as an error.

## Story

As an Operator,
I want the filters and prompts applied to reports captured,
so that a rebuilt report restricts data the same way the original did.

## Acceptance Criteria

1. `analysis_filters.csv` and `saved_filters.csv` are written with qualified identifiers.
2. A filter's expression text is stored verbatim with its `xsi:type`, and its operator (`@op`) is recorded.
3. A saved-filter reference is resolved to a catalog object identifier by the Story 2.4 resolver, and an unresolvable path is recorded in `errors.csv` (AD-3).
4. A prompt records the column it binds to.
5. Dashboard-level and Analysis-level filters are both recorded, and the scope of each is distinguishable.
6. The saved-filter reference is matched on **`xsi:type`, not on element name**, because no element named `sawx:savedFilter` exists.

## Tasks / Subtasks

- [x] Parse `saw:filter` and its `sawx:expr` children; capture text, type and `@op` (AC: #1, #2)
- [x] Parse `sawsf:savedFilterObject` roots into `saved_filters.csv` (AC: #1)
- [x] Resolve `sawx:expr[@xsi:type="sawx:savedFilter"][@path]` via the Story 2.4 resolver (AC: #3, #6)
- [x] Capture prompts and their column bindings (AC: #4)
- [x] Record filter scope — dashboard versus Analysis (AC: #5)
- [x] Tests: an unresolvable saved-filter path, a prompted filter, a dashboard-scope filter (AC: #3, #5)

## Dev Notes

### `sawx:savedFilter` is a type, not an element (AC #6)

**The epic's Story 2.6 said "when `sawx:savedFilter` is encountered"** — corrected 2026-08-20. Measured across the fixture, **no element by that name exists — zero occurrences.**

Saved filters are referenced as an attribute pair on an ordinary expression element:

```xml
<sawx:expr xsi:type="sawx:savedFilter"
           path="/shared/03. Mobile/_filters/PC1/Game Prompted Filters"/>
```

**417 occurrences**, all on `sawx:expr`, all carrying `@path`, all with empty text. Match on `xsi:type`. An implementer searching for the element name would find nothing and could reasonably conclude the construct is absent from the fixture — which is exactly the false-absence failure AD-3 exists to prevent, arriving through a story rather than through code.

This was the second name slip in the epic; Story 2.4 records the other (`sawd:report` for `sawd:reportRef`). Both counts were right and both element names were wrong, which suggests they were transcribed from a summary rather than from the parse. Both are now corrected at source, but the correction is recorded here too — a reader who met the old name in a draft, a commit message or a branch needs to be able to find out what happened to it.

### Saved-filter references resolve at the same rate as everything else

Of the 417, **222 resolve after case normalisation, 0 resolve exactly, 195 do not resolve at all.** They are covered by the Story 2.4 resolver and inherit its recording rules — including that a case-normalised resolution stays distinguishable from an exact one.

The unresolved 195 are the same story as everywhere else: most point into `/company_shared/`, a catalog root absent from this fixture. A handful point inside `/shared` at objects that are genuinely missing, such as a `_filters/PC1/` folder referenced from `_filters/y13 - nfl demo/`.

**96 `sawsf:savedFilterObject` roots exist**, so a majority of the 417 references point at fewer than 96 distinct objects — saved filters are reused heavily, which is the point of them.

### Filter operators, measured

| `@op` | Count | | `@op` | Count |
|---|---:|---|---|---:|
| `prompted` | 1615 | | `between` | 293 |
| `in` | 1599 | | `lessOrEqual` | 127 |
| `equal` | 910 | | `notNull` | 80 |
| `and` | 614 | | `greaterOrEqual` | 76 |
| `greater` | 403 | | `multiply` | 75 |
| `less` | 347 | | `top` | 48 |

**`prompted` is the most common operator of all.** A `prompted` filter has no value in the artifact — the value arrives at runtime from a dashboard prompt. Record it as prompted; do not record it as an empty comparison, which would read as *filters on blank* and would be wrong in a way that changes numbers.

`multiply`, `union` (35) and the arithmetic operators appearing in the same attribute confirm `@op` is a general expression operator, not a filter-specific enum. Capture the value; do not validate it against a closed list.

### Structure

`saw:filter` occurs 1086 times, and 1087 of its children are `sawx:expr` — filters are a thin wrapper around one expression tree. Nesting is via `sawx:expr[@xsi:type="sawx:logical"]` (639) with `sawx:comparison` (2173) at the leaves.

### Scope (AC #5)

Two populations, in different namespaces, and the distinction is structural rather than a judgement:

| Scope | Construct | Count |
|---|---|---:|
| Analysis | `saw:filter` inside a `saw:report` | 1086 |
| Dashboard | `sawd:globalFilterView[@path]` | 887 |
| Dashboard | `sawd:dashboardHiddenPromptRef` | 34 |
| Dashboard | `sawd:dashboardFiltersAndVariables` | 19 |

A dashboard-level filter applies to every Analysis on the page, so folding the two populations into one table would misstate what each report restricts. Record scope as a column, sourced from which construct the filter came from.

### Prompts (AC #4)

| Construct | Count |
|---|---:|
| `saw:prompt` | 1997 |
| `saw:promptSource` | 1322 |
| `saw:promptOperator` | 1321 |
| `saw:promptUIControl` | 1321 |
| `saw:promptDefaultValues` | 1321 |
| `saw:setPromptVariable` | 1311 |
| `saw:constrainPrompt` | 1309 |
| `xsi:type="saw:columnFilterPrompt"` | 995 |

`saw:setPromptVariable` (1311) is worth attention beyond AC #4: a prompt that **sets a presentation variable** is not merely filtering — the variable it sets may be read by a column formula elsewhere in the report. That is a dependency between a prompt and a calculation, and it is invisible if only the column binding is captured. Capture the variable name.

### References

- [Source: .../ARCHITECTURE-SPINE.md#AD-3, #AD-21]
- [Source: documents/implementation-artifacts/2-4-extract-dashboards-and-pages.md] — the resolver
- [Source: documents/planning-artifacts/epics.md#Epic 2, Story 2.6]

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Amelia, bmad-agent-dev)

### Debug Log References

### Completion Notes List

Five of six ACs met in full. **AC #4 is met in mechanism but nearly empty in content**, for a reason worth reading.

- **AC #1, #2:** 7135 filter expressions and 96 saved filters. Every expression in a filter tree is recorded, not only the
  outermost, because nesting is where the predicates are. `@op` is captured and **never validated against a closed list** —
  `multiply` and `union` share the attribute, so it is a general expression operator.
- **AC #3, #6:** saved-filter references matched on **`xsi:type`, not element name** — no element named `sawx:savedFilter`
  exists anywhere in the fixture. 341 references found inside Analysis filters; unresolvable ones land in `errors.csv`.
- **AC #5:** scope sourced from **which construct the filter came from**, not a judgement: `saw:filter` inside a `saw:report`
  is Analysis scope (6248), `sawd:globalFilterView` is dashboard scope (887).
- **AC #2, prompted:** recorded as `prompted`, never as an empty comparison — which would read as *filters on blank* and be
  wrong in a way that changes numbers.

**AC #4 — prompts, and the wall it hits.** A prompt records its column binding, its operator, its UI control and **the
presentation variable it sets** (the dependency a column binding alone would hide). But `analysis_prompts.csv` holds **4
rows**, because **991 of the fixture's 995 `saw:columnFilterPrompt` elements live in `saw:view` roots** — 530 objects this
epic lists as unmodelled — and only 4 sit inside an Analysis.

This matters more than the row count suggests: **`prompted` is the most common filter operator in the entire catalog** (1615
occurrences), so the values those filters receive at runtime are defined almost entirely in objects nobody has parsed.

I did not expand scope to model `saw:view` — that is a new object type, not a tweak, and the epic lists it as unmodelled.
Instead the gap is made loud: a test asserts the 4/530 split so it fails if anyone changes it silently, the README says an
almost-empty prompts table means *not extracted* rather than *not present*, and `deferred-work.md` names modelling `saw:view`
as **the single highest-value addition to catalog extraction**.

### File List

- `tools/rpd_extract/adapters/inbound/catalog_xml.py`
- `tools/rpd_extract/core/model.py` (`AnalysisFilter`, `AnalysisPrompt`, `SavedFilter`, scope constants)
- `tools/rpd_extract/adapters/outbound/knowledge_base.py` (three tables)
- `tools/rpd_extract/tests/test_catalog.py`, `test_catalog_fixture.py`
- `documents/implementation-artifacts/deferred-work.md`
