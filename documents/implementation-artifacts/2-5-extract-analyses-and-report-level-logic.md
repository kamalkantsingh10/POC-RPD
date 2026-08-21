# Story 2.5: Extract Analyses and Report-Level Logic

Status: review

**Review intensity: Keen** — this is the epic's reason for existing. A dropped `columnFormula` is a missing calculation that no test on the RPD side can detect, and the as-is document would silently understate what a report computes.

## Story

As an Operator,
I want every Analysis captured with the calculations defined inside it,
so that logic that exists nowhere in the RPD is visible to whoever rebuilds the report.

## Acceptance Criteria

1. `analyses.csv` and `analysis_columns.csv` are written with qualified identifiers.
2. `saw:criteria[@subjectArea]` is captured verbatim as a string and is **not** resolved to a Knowledge Base Subject Area — that is FR-7, and it needs a matched pair (AD-22).
3. Each `saw:columnFormula`'s `sawx:expr` text is stored verbatim, character-for-character (AD-21, FR-2), and no template, rendered form or reference list is fabricated to imitate the RPD's three-form shape.
4. Expression text round-trips byte-identical through the Story 1.3 writer, including text beginning `-` or `=` and text containing commas, quotes and newlines.
5. Each column records its `xsi:type`, so a reader can distinguish a plain column reference from a computation.
6. An expression of type `sawx:eval` is flagged, because it invokes a database function directly and is an external dependency a rebuild must resolve against the database.
7. A column whose formula is more than a bare column reference is identifiable without parsing the expression.
8. An Analysis carrying more than one `saw:criteria` records each, because the count of criteria exceeds the count of Analyses and a one-per-report assumption would drop logic.

## Tasks / Subtasks

- [x] Parse `saw:report` roots into `analyses.csv` with qualified identifiers (AC: #1)
- [x] Capture `@subjectArea` verbatim, unresolved, with a comment naming FR-7 (AC: #2)
- [x] Capture `columnFormula/sawx:expr` verbatim with its `xsi:type` (AC: #3, #5)
- [x] Derive and record the is-a-computation flag and the `sawx:eval` flag (AC: #6, #7)
- [x] Handle multi-criteria Analyses (AC: #8)
- [x] Round-trip tests against the Story 1.3 writer, with adversarial expression text (AC: #4)

## Dev Notes

### Measured 2026-08-20

| Construct | Count |
|---|---:|
| `saw:report` roots (Analyses) | 1607 |
| `saw:criteria[@subjectArea]` | 1680 |
| `saw:columnFormula` | 10,866 |
| `saw:column` | 14,749 |

**AD-21 recorded `saw:columnFormula` as "verified across 409 expressions."** The measured count is **10,866** — an understatement by a factor of 26. **AD-21 was corrected 2026-08-20**; its rule was never in question, since a single-representation source offers nothing to choose between. Story 2.1 carries the same note about `web-catalog-findings.md`; both stem from the same partial survey.

### One representation, and that is the whole of it (AC #3)

MDS XML stores three forms — `ExprText`, `ExprTextDesc`, `ObjectRefList` — and Story 1.5 captures all three because AD-21 forbids choosing. **Catalog XML stores one:** the text inside `sawx:expr`. There is no template, no resolved rendering, no reference list.

Do not synthesise the missing two. A fabricated `ExprTextDesc` would be indistinguishable from one the source provided, and the verbatim guarantee is the product's central claim. Where the RPD's shape has no counterpart, the field is absent, not empty-because-we-made-one.

This is also why the semantic model document renders `%1` placeholders for RPD formulas and will not for catalog formulas: catalog expressions arrive already readable.

### `xsi:type` is where the meaning lives (AC #5, #6, #7)

| `xsi:type` | Occurrences | What it means for a rebuild |
|---|---:|---|
| `sawx:sqlExpression` | 14,771 | A computation — the migration target |
| `saw:regularColumn` | 10,606 | A plain reference to a semantic-layer column |
| `sawx:comparison` | 2,173 | A filter predicate |
| `sawx:special` | 1,608 | A built-in |
| `sawx:columnRefExpr` | 1,280 | A reference to another column in the same Analysis |
| `sawx:eval` | **360** | **A direct database function call** |

AC #7 asks for the computation flag to be derivable **without parsing the expression**, and `xsi:type` supplies it: `saw:regularColumn` is a bare reference, everything else is not. That keeps the flag deterministic — no expression parsing, therefore no guessing, therefore no AD-3 exposure.

### `sawx:eval` is an external dependency (AC #6)

360 occurrences, concentrated in the database-monitor content (`10. lifecycle and admin/database monitor/…`), with expressions like `Owner`. `EVALUATE` passes a function straight through to the database, so the calculation is **not defined in OBIEE at all** — it lives in the target schema.

Flag it because a migration cannot read the logic from any artifact this tool produces. Whoever rebuilds must resolve it against the database, and a flag turns that from a discovery into a listed task.

### `@subjectArea` stays a string (AC #2)

`saw:criteria[@subjectArea]` is the join key FR-7 needs, and it is the join key that has no fixture: the catalog references 86 Subject Areas, our RPD holds 21, and the overlap is **zero**. They are different estates.

Capture the string verbatim. **Do not resolve it, do not normalise it, do not strip its quotes** — values arrive quoted, e.g. `"A - Sample Sales"`. Under AD-23, resolution lands in `report_lineage.csv` when a matched pair exists; it never extends an existing table.

### More criteria than Analyses (AC #8)

1680 `saw:criteria[@subjectArea]` against 1607 Analyses. An Analysis can carry more than one criteria block — combined requests, set operations — and 35 `sawx:union`-family operators appear in the filter operator counts.

A one-criteria-per-Analysis model drops the extra blocks, and each dropped block is an entire query definition. Model criteria as a child collection, not a field.

### References

- [Source: .../ARCHITECTURE-SPINE.md#AD-21, #AD-22, #AD-23, #AD-3]
- [Source: documents/implementation-artifacts/1-3-spreadsheet-safe-csv-writer-with-a-verbatim-text-guarantee.md]
- [Source: documents/implementation-artifacts/1-5-extract-the-bmm-layer-with-verbatim-formulas.md]
- [Source: estate/test-corpus/web-catalog-findings.md#2, #3]
- [Source: prd.md#FR-2, #FR-6]

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Amelia, bmad-agent-dev)

### Debug Log References

### Completion Notes List

All eight ACs met. 1607 Analyses, 1789 criteria blocks, 11,143 columns, **10,340 formulas captured verbatim**.

- **AC #3, #4 — the verbatim guarantee, proven on real content.** All 11,143 column formulas round-trip **byte-identical**
  through the Story 1.3 writer, including **299 beginning with `-`, `=`, `+` or `@`**, 104 containing newlines and 917
  containing both commas and quotes. Nothing is synthesised: where the RPD's three-form shape has no counterpart the field is
  absent, not invented.
- **AC #2:** `@subjectArea` captured verbatim, unresolved, quotes intact. **40 of the 67 distinct values are
  `XSA('prodney'.'Sample Pharma')` uploaded datasets, not Subject Areas** — recorded in `catalog-xml-schema.md` because an
  FR-7 resolver that joins them against `presentation_subject_areas` would report 40 of 67 as dangling.
- **AC #5, #7:** `xsi:type` recorded per column; `is_computation` derived from it alone, never by parsing the expression — so
  the flag is deterministic and carries no AD-3 exposure. 803 of 11,143 columns are computations.
- **AC #6 — corrected by measurement.** `sawx:eval` is **never inside a column formula**: all 356 occurrences are nested
  inside another expression, 297 in Analysis filters and 4 in saved filters. The flag therefore lives on
  `analysis_filters` and `saved_filters`, and is found by scanning the expression tree rather than reading the outermost
  `xsi:type` — which would have found none of them.
- **AC #8 — and a bug it exposed.** Criteria **nest**: 182 of 1789 blocks sit inside another, because a set operation wraps
  its operands. A descendant search from every block counted shared columns once per enclosing block — **13,091 columns where
  11,143 exist, and 12,424 `columnFormula` where the file holds 10,474.** Ownership is now nearest-ancestor.

**Full accounting of the 10,474 `columnFormula` elements inside criteria:** 10,340 belong to a column and are captured here,
132 sit inside `saw:filter` and are captured as filter expressions, and 2 are a second formula on a column that already has
one — reported as `unread_element`. **None is lost.**

`saw:paSimpleColumnFormula` (42) is **not** captured: measured, all 42 hang off `saw:propertyAddition` in Visual Analyzer
projects, never off a column and never inside a criteria. They surface as `unread_element` × 42 rather than vanishing;
capturing them means modelling VA project structure, recorded in `deferred-work.md`.

### File List

- `tools/rpd_extract/adapters/inbound/catalog_xml.py`
- `tools/rpd_extract/core/model.py` (`Analysis`, `AnalysisCriteria`, `AnalysisColumn`)
- `tools/rpd_extract/adapters/outbound/knowledge_base.py` (three tables)
- `tools/rpd_extract/tests/test_catalog.py`, `test_catalog_fixture.py`
