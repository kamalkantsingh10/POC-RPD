# Story 2.8: Extract Analysis Views — What Each Report Renders As

Status: review

**Review intensity: Normal** — the population is large and countable, so an error announces itself against `unparsed.csv`. The judgement call in this story is scope, not correctness.

## Story

As a Migration Analyst,
I want to know what each Analysis renders as — chart, pivot, table, gauge, map — and in what order,
so that a Power BI target visual can be chosen from the Knowledge Base instead of by opening 1607 reports by hand.

## Acceptance Criteria

1. A new `analysis_views` table carries one row per `<saw:view>` element found inside an Analysis, with `analysis_id`, sibling position, view type and view name. The fixture yields **10,879 rows**.
2. `xsi:type` is stored **verbatim** — `saw:pivotTableView`, never `Pivot Table`. A view carrying no `xsi:type` records that absence as a value in its own right.
3. Container and caption views (`compoundView`, `titleView`) are distinguishable from data-bearing views (`dvtchart`, `pivotTableView`, `tableView`, …) without the reader supplying a lookup table, and the distinction is derived from what was parsed rather than from a hardcoded list of the 26 types this fixture happens to hold.
4. The 530 standalone `saw:view` root objects — **all of them `saw:globalFilterPrompt`** — are not merged into `analysis_views`, and the coverage report states where they went, so "not a report visual" stays distinguishable from "not understood".
5. An unknown `xsi:type` yields a row rather than an error, because the type is recorded and not interpreted. An unknown *attribute* on a parsed view is still reported to `unparsed.csv`.
6. After this story the `unread_element` entry for `report/v1.1}view` and its 10,879 occurrences no longer appears, and `coverage_summary` shows the increase in modelled objects as a number.
7. `README.md` is updated: `analysis_views` in the **What you get** table with its row count; an `analyses ||--o{ analysis_views` edge in the `erDiagram` under **How the tables connect**, in the same `resolved/present` form as every other edge; and **How much of a Web Catalog this understands** revised, since the modelled share changes.
8. Every count written into the README is **re-derived from a run**, not copied from this story — the rule Story 2.1 AC #7 applies, because a corrected number that nobody re-measured is still a number nobody measured.

## Tasks / Subtasks

- [x] Measure the view population independently before writing any parser (AC: #1, #3)
- [x] Add the `analysis_views` model and writer table (AC: #1, #2)
- [x] Parse views within `saw:report`, preserving sibling order (AC: #1)
- [x] Decide and implement the container/data distinction from parsed evidence (AC: #3)
- [x] Settle the standalone `globalFilterPrompt` population and record it (AC: #4)
- [x] Tests: unknown type recorded, unknown attribute still audited (AC: #5)
- [x] Confirm the audit entry disappears and coverage moves (AC: #6)
- [x] Update the README from a fresh run's numbers (AC: #7, #8)

## Dev Notes

**Writer: this story owns `analysis_views`.** No other table changes shape.

### Why this was not already covered

Story 2.5 extracts what an Analysis **computes** — criteria, columns, formulas verbatim. Nothing extracts what it **displays**.

`dashboard_contents` is often mistaken for the visuals table. It is not: its 3718 rows are `reportRef` (1722), `dashboardPageRef` (1041), `globalFilterView` (887), `scorecardViewRef` (41) and `folderView` (27) — pointers to objects, never visuals. The visuals sit one level further in, under `saw:views` inside each Analysis.

### Measured 2026-08-21 — count elements, not root elements

The Epic 2 planning table counts **root elements**, so it records `saw:view` at 530. That is the standalone population only, and it understates the real one by a factor of 21.

| Population | Count | Where it is recorded today |
|---|---|---|
| `<saw:view>` elements, whole fixture | **11,409** | — |
| ...nested inside `saw:report` | **10,879** | `unparsed.csv`, `unread_element` |
| ...standalone root objects | **530** | `unparsed.csv`, `unmodelled_type` |

**The two recorded figures reconcile exactly**: 10,879 + 530 = 11,409, and both match `unparsed.csv` line for line. Nothing is silently dropped — AD-3 is holding. **This story moves a recorded gap into a table; it does not repair a leak.** That distinction matters for how the work is reviewed: the risk here is mis-modelling, not loss.

### Three findings that shape the work

**Every view belongs to an Analysis or to nothing.** Zero `<saw:view>` elements appear inside `sawd:dashboard` or `sawd:dashboardPage`. The visual layer is entirely an Analysis-level concern, so the table hangs off `analyses` and never off `dashboard_pages`.

**All 530 standalone roots are `saw:globalFilterPrompt`** — dashboard prompts saved as catalog objects in their own right, not report visuals. They share an element name with something they are not, and merging them would be a category error that inflates the visual count by 5%.

**1598 of 1607 Analyses carry at least one view. 26 distinct `xsi:type` values appear**, led by:

| `xsi:type` | Count | | `xsi:type` | Count |
|---|---|---|---|---|
| `saw:dvtchart` | 1739 | | `saw:htmlview` | 796 |
| `saw:compoundView` | 1581 | | `saw:headlineView` | 367 |
| `saw:titleView` | 1482 | | `saw:narrativeView` | 232 |
| `saw:pluginView` | 1288 | | `saw:trellisView` | 182 |
| `saw:tableView` | 1207 | | `saw:dvtgauge` | 172 |
| `saw:pivotTableView` | 1156 | | `saw:mapview` | 148 |

`compoundView` is a layout container and `titleView` a caption. **Not every view is a data visual**, and a table that implies 11,409 charts would be worse than the gap it replaces. AC #3 exists for that reason.

### Why `xsi:type` stays verbatim

Mapping `saw:pivotTableView` to "Pivot Table", or worse to a Power BI visual name, is a migration judgement. AD-21 keeps every representation the source provides; the choice of target visual belongs to the Migration Analyst reading the Knowledge Base, not to the extractor writing it. A friendly-name column would also drift silently the first time an estate carries a type this fixture never had.

### The check that matters most

AC #6 is the regression guard, not a nicety. If views are modelled but the `unread_element` line for `report/v1.1}view` stays put, something is being counted twice or parsed in a path the audit does not observe. The audit **observes what the parsers actually read** rather than consulting a declaration — that mechanism already caught six drifted entries once, including `PrivilegePackage@userRef` silencing three privilege grants. Watching the 10,879 go to zero is how this story proves it landed.

### README scope

Three places, all of which currently describe a Knowledge Base without visuals:

- **What you get** — the table list, plus its row count
- **How the tables connect** — the `erDiagram`, and the catalog reading notes beneath it
- **How much of a Web Catalog this understands** — the modelled share changes

AC #8 forbids copying the counts above into the README. Re-run and re-derive; these figures were measured on 2026-08-21 against the pinned fixture and are an input to the work, not its output.


## Completion Notes

Implemented 2026-08-21. Full suite **184 passing** (176 before). Eight new tests in `test_catalog.py` under a Story 2.8 section, driven by six views added to the shared `ANALYSIS` fixture — a container, a caption, a pivot, a chart, one with an unknown `xsi:type` and one with none at all.

**Measured against the pinned fixture after the change:**

| Claim | AC | Result |
|---|---|---|
| `analysis_views` rows | #1 | **10,879** — exact |
| `analysis_id` resolves | #1 | 10,879 / 10,879 |
| distinct `view_type` | #2 | 25 |
| container / data / chrome | #3 | 1580 / 6239 / 3060 |
| `globalFilterPrompt` in the table | #4 | **0** |
| standalone views still `unmodelled_type` | #4 | 530 |
| `unread_element` for `report/v1.1}view` | #6 | **gone** |
| `unread_element` for `report/v1.1}views` | #6 | **gone** |
| `unparsed` rows | #6 | 1686 → **1478** |
| audited-but-unread | #6 | 1308 items / 725,198 occurrences → **1100 / 418,322** |

25 distinct types rather than the 26 measured across the whole fixture, because `saw:globalFilterPrompt` is entirely the standalone population — which is AC #4 confirming itself from the other direction.

### AC #6 was partly imprecise, and this is what happened instead

The AC asked for `coverage_summary` to show the increase in modelled objects. **It does not, and cannot.** `coverage_summary` counts *files* — `files_seen`, `modelled_object`, `not_a_catalog_object` — and a view is an element inside a file, not a file. Modelled share is unchanged at 53%, correctly.

The gain is visible in two other places, both real numbers rather than assertions:

- `coverage.csv` gains a row, `saw:view (element, inside an Analysis)`, parsed 10,879. The label is spelled out because the standalone roots are counted under the bare element name in a separate row (skipped 530), and one row carrying both populations would restate the 21× frame confusion this story exists to end.
- The audited-but-unread total falls by 42%.

The story's AC text was written before the code and assumed the wrong table. Recorded here rather than quietly satisfied by inventing a file-level metric that would not mean anything.

### The container/data distinction, as built

Derived from structure, per AC #3, with no list of type names anywhere in the code:

- `references_views` counts `saw:cvCell[@viewName]` — a view arranging other views by name
- `bound_column_count` counts descendants carrying `@columnID`, asked at every depth because a binding sits differently in a pivot, a chart and a trellis
- `display_type` / `display_subtype` carry `saw:display`'s own words for the `dvt*` family

On the fixture this separates cleanly: 1580 of 1581 `compoundView` reference views and bind nothing; `titleView`, `htmlview` and `narrativeView` do neither.

### README

Updated per AC #7 from a fresh run, not from the figures in this story (AC #8): the `analysis_views` row in **What you get**, the `analyses ||--o{ analysis_views : "analysis_id (10879/10879)"` edge, a reading note on the type being verbatim and the two counted columns, the corrected `unparsed` and audit totals, and a clarification in **How much of a Web Catalog this understands** distinguishing the 10,879 nested views from the 530 standalone objects. The `erDiagram` was rendered through `mmdc` to confirm it parses and `analysis_views` appears.

The note that 991 of 995 column prompts sit outside Analyses was re-checked and still holds — they live in the standalone `saw:view` objects, which remain unmodelled.
