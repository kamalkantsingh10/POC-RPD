# Story 2.9: Complete the Presentation Layer, and Resolve Report Lineage

Status: review

**Review intensity: Keen** — half of this story is FR-7, which the architecture placed in Epic 4 because it cannot be verified against the available fixtures. It is being built here anyway, by decision, and the story's job is to make that decision legible rather than invisible.

## Story

As a Migration Analyst,
I want a report column traced back through the semantic layer to a database column,
so that "if this table changes, which reports break" is one lookup instead of an unanswerable question.

## Two halves, and they are not equally provable

**Part 1 — presentation hierarchies — is ordinary Epic 2 work.** `PresentationHierarchy` (58) and `Dimension` (25) are unmodelled today, so the presentation layer is incomplete: an Analysis that references a hierarchy rather than a flat column has nothing in the Knowledge Base to resolve to. This is verifiable against the real RPD fixtures exactly like every other Epic 2 story.

**Part 2 — report lineage — is FR-7, and it is not verifiable here.** `ARCHITECTURE-SPINE.md` records FR-7 as Epic 4, gated on a matched RPD-plus-catalog pair, on the grounds that *"putting an unverifiable requirement beside verifiable ones makes that claim unreadable."* That reasoning has not changed. What has changed is that a **constructed pair now exists** (Story 2.8's `constructed-catalog/`), so the mechanism can be exercised end to end.

**A constructed pair proves the mechanism, not the estate.** Both halves were authored by the same hand, so their agreement is a property of the author. Under FR-31 that accuracy is reported **separately and never merged** with accuracy measured against real content — the same rule already applied to the five constructed cases. This story therefore does **not** claim FR-7 is verified. It claims FR-7 is built and demonstrated, and states plainly what remains unproven.

## Acceptance Criteria

**Part 1 — the presentation layer**

1. `presentation_hierarchies` carries one row per `PresentationHierarchy` — **58** for the two repositories — with its presentation table, its logical dimension, and its level count.
2. `presentation_levels` carries one row per `PresentationLevel` — **246** — with its hierarchy, its position in the drill order, and its logical level.
3. `presentation_level_columns` carries one row per `RefPresentationColumn` **held by a level** — **199** — mapping a level to the presentation column displayed at it. This is the drill path, and it is what a Power BI hierarchy needs.
4. `logical_dimensions` (**25**) and `logical_levels` (**106**) are modelled, so `presentation_levels.logical_level_id` resolves to a row rather than dangling. `isRagged`, `isSkipped` and `isValueBased` are carried, because each changes what a hierarchy means and none is styling.
5. The `unmodelled_type` entries for `PresentationHierarchy` and `Dimension` no longer appear in `unparsed.csv`.

**Part 2 — report lineage**

6. A new table `report_lineage.csv` (AD-23 — **never** an extension of `lineage.csv`) carries one row per `analysis_columns` row, resolving it toward the semantic layer.
7. `analysis_criteria.subject_area` resolves to `presentation_subject_areas` by name with quotes stripped. The verbatim value stays in `analysis_criteria`, unchanged — resolution is recorded beside it, never over it.
8. A bare `"Table"."Column"` formula resolves to a `presentation_column_id`. Where it resolves, `logical_column_id` and `physical_column_id` are chained from the existing `lineage` table so the row completes the four-layer path.
9. **Every row records how it resolved**, using the same vocabulary as the catalog's reference resolution: exact, case-normalised, or unresolved — plus a distinct outcome for a formula that **is not a column reference at all**, which is not a failure and must not read as one.
10. A formula naming a source outside the semantic model — the `XSA('user'.'dataset')` Visual Analyzer form, 40 of the fixture's 67 distinct `subjectArea` values — is recorded as **sourced outside the semantic model**, distinguishable from both a resolution failure and a computation.
11. A presentation column that resolves but has no `lineage` row — a BMM-derived column such as `PERIODROLLING` — records that it is **computed, not sourced**, rather than leaving an empty cell that reads as a lookup failure.
12. The post-pass runs over the merged Estate and reads only what extraction already produced. **No adapter changes, no re-parsing of source files.**

**Both halves**

13. Accuracy for Part 2 is recorded against the **constructed pair only**, in a section that states it is constructed and therefore circular, kept separate from any figure measured against real corpus content (FR-31).
14. `README.md` gains the five new tables in **What you get**, the new edges in the `erDiagram`, and a statement in **What this does not do yet** that FR-7 is built but unverified against a real estate. Counts re-derived from a run, not copied from this story.

## Tasks / Subtasks

- [x] Measure the hierarchy and dimension populations independently before parsing (AC: #1-#4)
- [x] Model `presentation_hierarchies`, `presentation_levels`, `presentation_level_columns` (AC: #1-#3)
- [x] Model `logical_dimensions` and `logical_levels`, carrying ragged/skipped/value-based (AC: #4)
- [x] Confirm the two `unmodelled_type` entries disappear (AC: #5)
- [x] Add `report_lineage` as a post-pass over the merged Estate (AC: #6, #12)
- [x] Resolve the subject area by name, leaving the verbatim value untouched (AC: #7)
- [x] Resolve bare column references and chain through `lineage` (AC: #8)
- [x] Record every resolution outcome, including the three non-failures (AC: #9-#11)
- [x] Report constructed-pair accuracy separately (AC: #13)
- [x] Update the README from a fresh run (AC: #14)

## Dev Notes

### The shapes, measured 2026-08-21

`PresentationHierarchy` hangs off a presentation table and points at a logical `Dimension`:

```xml
<PresentationHierarchy name="Delivery systems"
    containerRef=".../PresentationTable/...xml#m9054e769..."
    logicalDimensionRef=".../Dimension/...xml#m921af6d0...">
  <PresentationLevel name="Delivery system" logicalLevelRef=".../Dimension/...#m921c7d70...">
    <RefDisplayColumns><RefPresentationColumn presentationColumnRef="..."/></RefDisplayColumns>
```

`Dimension` carries the drill semantics — `isValueBased`, `isRagged`, `isSkipped` — and its `LogicalLevel` children carry `memberCount` and a `LogicalKey` marked `isForDrillDown`.

| Object | bi-analytics-2013 | sampleapp | Total |
|---|---:|---:|---:|
| `PresentationHierarchy` | 53 | 5 | **58** |
| `PresentationLevel` | 226 | 20 | **246** |
| `RefPresentationColumn` | 183 | 17 | **200** |
| `Dimension` | 20 | 5 | **25** |
| `LogicalLevel` | 84 | 22 | **106** |

### Why hierarchies are not optional for the target

Power BI treats hierarchies as first-class, and drill behaviour depends on them. A migration that flattens a ragged or skip-level hierarchy silently changes what a user can do without changing any number — which is the worst kind of regression, because parity checking on values will not catch it.

### Why `report_lineage` is a post-pass and not an adapter change

Everything it reads is already extracted and fully populated: `analysis_criteria.subject_area` (1680 of 1789), `analysis_columns.criteria_id` (11143 of 11143), `analysis_columns.formula` (10328), `presentation_tables.subject_area_id` (128 of 128), `presentation_columns.table_id` (1543 of 1543) and `lineage` (1573). The join is arithmetic over rows, not a second reading of the source. Keeping it a post-pass also keeps it honest: it cannot invent a fact the adapters did not record.

### What will not resolve, and why that is the finding

Of 10,328 formulas carrying text, **5806 (56%) are bare `"Table"."Column"`**. The rest are computations whose column references are embedded in an expression. Resolving those means parsing the expression, which is out of scope here — AC #9's *not a column reference* outcome exists so the 44% is stated rather than reported as 4522 failures.

A further population will never resolve at any effort: `XSA('prodney'.'US 5Y Florida lotto')` names a Visual Analyzer uploaded dataset that was never in the RPD. **40 of 67 distinct `subjectArea` values are XSA forms.** AC #10 makes that a category, because "the data is not in the semantic model" is a migration finding, not a defect.

### The honest limit

Both fixtures remain unpaired — 0 of 1680 subject areas match — so on the real corpus this table will resolve almost nothing, and that is the correct output. The constructed pair is the only place the chain completes. **Do not read a low resolution rate on the real corpus as a defect in this story**; read it as the missing matched pair it has always been.


## Completion Notes

Implemented 2026-08-21. Suite **207 passing** (190 before). Both parts landed; the second is built, not verified.

### Part 1 — every count exact

| Table | Rows | Expected |
|---|---:|---:|
| `presentation_hierarchies` | 58 | 58 |
| `presentation_levels` | 246 | 246 |
| `presentation_level_columns` | 199 | **199, not 200** |
| `logical_dimensions` | 25 | 25 |
| `logical_levels` | 106 | 106 |

`PresentationHierarchy` and `Dimension` no longer appear as `unmodelled_type`.

**AC #3 said 200 and was wrong.** The 200th `RefPresentationColumn` does not belong to a level — it hangs directly off `Sales Rep Hierarchy`, which has **zero** `PresentationLevel` children because its dimension is `isValueBased="true"`. A parent-child hierarchy has no levels; it names one column on the hierarchy itself. Reading display columns only from levels drops it silently, so `presentation_hierarchies.display_column_id` was added and the AC corrected to 199 + 1. **1 of 25 dimensions is value-based**, and in Power BI those become `PATH()` rather than a level hierarchy — a different rebuild, not a detail.

### Two defects the fixtures caught

**Dimension identifiers collided — 18 `duplicate_identifier` errors.** The first implementation fell back to the dimension's own name as its identifier container when the business model did not resolve, producing `bmm::Times.Times` for **four** different dimensions named `Times`. `index.identifier()` was the wrong lookup: `BusinessModel` is index-only and carries a name, not an identifier. Corrected to `index.get(mdsid).name` and to **refusing** rather than inventing a container, matching `_parse_logical` exactly. FR-8 is why this is an error and not a naming preference. Now **0 duplicates**.

**Nested reference lists were invisible.** `_children` reads direct children only, and both `RefLogicalColumn` and `RefPresentationColumn` sit one wrapper deep. Added `_descendants`.

**A bonus, measured not intended:** errors fell 1583 → 1556. Binding `LogicalLevel` identifiers made 27 previously-dangling `ExpressionRef` errors resolve (31 → 4). Those were expressions citing dimension levels the Knowledge Base did not model.

### Part 2 — built, demonstrated, unverified

`report_lineage.csv`, 11143 rows, one per `analysis_columns` row. `tools/rpd_extract/core/report_lineage.py` is a post-pass over the merged Estate called from `cli.extract` — **no adapter changed and no source file is re-read** (AC #12).

**On the real corpus, and the partition is exact:**

| Outcome | Rows |
|---|---:|
| `unresolved` | 5806 |
| `not_a_column_reference` | 4586 |
| `outside_semantic_model` | 751 |
| **Total** | **11143** |

`subject_area` resolved: **0**. That is the correct output — the two halves are different SampleApp releases. The 5806 is exactly the bare-reference population measured before the work started, so every reference that *could* resolve given a matched pair is accounted for and none is hidden among the computations.

### Constructed-pair accuracy — reported separately (AC #13, FR-31)

**These figures are circular and must never be merged with any figure measured against real corpus content.** Both halves of the constructed pair were authored here, so their agreement is a property of the author, not of OBIEE.

| Reference | Resolution | Chain |
|---|---|---|
| `"Sales Facts"."Amount"` | `exact` | presentation → logical → `CC_SCHEMA.FCT_SALES_DETAIL.AMOUNT`, `sourced` |
| `"Sales Facts"."Rolling Amount 3M"` | `exact` | presentation → **no physical**, `computed_not_sourced` |

2 of 2 resolved. The second is the case AC #11 exists for: a `PERIODROLLING` column resolves correctly and legitimately reaches no physical column, and an empty cell there would read as a lookup failure.

**What this does and does not establish.** It establishes that the mechanism completes a four-layer path when names match. It establishes nothing about whether a real OBIEE catalog and a real repository name things consistently. `ARCHITECTURE-SPINE.md` still records FR-7 as unverifiable, and that remains true.

### README

Six tables in **What you get**, eight new `erDiagram` edges (rendered through `mmdc` to confirm they parse), reading notes on why hierarchies are three tables and why most `report_lineage` non-resolutions are not failures, and **What this does not do yet** rewritten to say FR-7 is built but resolves 0 of 11143 on the corpus and has only ever completed against a constructed pair. Counts re-derived from a fresh run (AC #8/#14), including `unparsed` 1478 → 1443 and the audit total 1100/418,322 → 1148/421,755.
