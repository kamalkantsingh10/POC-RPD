# Story 2.7: Report Catalog Coverage Honestly

Status: review

**Review intensity: Keen** — this story decides whether the epic's output can be trusted on an estate nobody has seen. An over-generous coverage report is worse than none.

## Story

As an Operator,
I want to know exactly what the catalog extraction did and did not understand,
so that I can trust the output against an estate this tool has never encountered.

## Acceptance Criteria

1. Catalog object types appear in `coverage.csv` alongside RPD types, distinguishable by layer.
2. Every root element type present but not modelled is recorded as `unmodelled_type` with a count, never skipped in silence — **all of them, not a named subset**.
3. A file that is not XML at all is classified as **not a catalog object**, distinguishably from a catalog object that failed to parse.
4. `xmlVersion` is recorded per object, **its absence recorded as a value in its own right**, and the version spread appears in the coverage report.
5. Styling exclusion is stated as a scope decision, distinguishable from content that was not understood.
6. A test proves an unknown attribute on a parsed catalog object is reported, and a test proves an unknown object type is reported.
7. The coverage report states what proportion of the input the extraction models, in whole numbers a reader can check.

## Tasks / Subtasks

- [x] Extend `coverage.csv` with a layer column and catalog rows (AC: #1)
- [x] Enumerate root types by parse and emit `unmodelled_type` rows for every unmodelled one (AC: #2)
- [x] Classify non-XML files as a distinct outcome (AC: #3)
- [x] Record `xmlVersion` per object, absence included, and aggregate the spread (AC: #4)
- [x] Emit the styling exclusion as a declared scope decision (AC: #5)
- [x] Emit the modelled-proportion figures (AC: #7)
- [x] Tests for unknown attribute and unknown object type (AC: #6)

## Dev Notes

### What the fixture actually contains, measured 2026-08-20

Of **5371 files**, 4341 parse as XML and **1030 do not**. Of the 4341:

| Population | Count | Share of files |
|---|---:|---:|
| **Modelled by Epic 2** — `saw:report`, `sawd:dashboardPage`, `sawd:dashboard`, `sawsf:savedFilterObject` | **2850** | **53%** |
| OBIEE catalog, not modelled — `saw:view` 530, `sawbsc:*` 216, `sawkpi:kpi` 47, `saw:action` 115, `saw:ibot` 10, others 4 | 922 | 17% |
| BI Publisher — `xmlp:dataModel` 162, `xmlp:report` 156, `oxp/config:config` 85, others 8 | 411 | 8% |
| Raw data and business documents — `DATA_DS` 86, `data` 22, `ROWSET` 14, ~30 one-off roots | 158 | 3% |
| Not XML — `.rtf`, `.png` inside `.xdo` folders, `.gitignore` | 1030 | 19% |

**Epic 2 models a little over half the files in this fixture.** That is the number AC #7 exists to make visible. It is not a failing — the rest is a different product, raw data, or object types the epic deliberately excludes — but a coverage report that does not say it invites a reader to assume the other 47% was understood.

### The named subset is not the whole set (AC #2)

The epic's Story 2.7 named five unmodelled types — `saw:view`, `saw:action`, `sawbsc:*`, `sawkpi:kpi`, `saw:ibot` — and was corrected 2026-08-20 to require enumeration instead. Measured, there are **59 distinct root element types**, of which **55 are unmodelled**.

The five named account for 918 of the 1491 unmodelled parsed objects. The remaining 573 include an entire second product and around thirty one-off roots — `SalesData`, `INVOICELIST`, `EMPLOYEES`, `MasterReport`, `xliff`, `xfdf`, `PROFILE`.

**Enumerate by parsing, not from a list in a story.** A hard-coded list of expected unmodelled types silently drops the fifty-fourth, and the whole point of this story is that nothing is dropped silently. The rule is: every root type encountered that the adapter does not model produces a row. This file's own table is evidence, not a specification.

### Non-XML is not a parse failure (AC #3)

Catalog objects are **extensionless**, so there is no suffix to filter on before parsing. Every file must be attempted, and 1030 will fail — all of them BI Publisher `.rtf` templates and `.png` previews inside `*.xdo` folders, plus `.gitignore`.

Two wrong answers are available, and both are the failure this project exists to prevent:

- **Report them as errors** — 1030 entries in `errors.csv` bury the 33 genuinely dangling references that matter. Signal lost in noise reads as *broken*, and a reader stops looking.
- **Skip them silently** — 19% of the input vanishes with nothing recorded. That reads as *complete*, and it is worse.

Classify them: *present, not a catalog object*. A count and a reason. That is the same distinction `unparsed.csv` and `errors.csv` already draw for the RPD side, extended to a population the RPD never had.

### Absence is a version value (AC #4)

| `xmlVersion` on root | Objects |
|---|---:|
| `201201160` | 1504 |
| `200810300` | 1147 |
| **none** | **1643** |
| `201106170` | 47 |

**No version at all is the most common state of all** — 1643 roots, ahead of `201201160`'s 1504 — covering 38% of parseable roots — including 103 `saw:report` roots, 530 `saw:view`, 115 `saw:action` and all 96 `savedFilterObject`.

A version spread that reports only the three declared values describes 62% of the estate and reads as though it describes all of it. Record absence as its own row.

One further value, `200811100`, appears exactly once and only on a nested element, never on a root. Whether nested versions are in scope is a decision to record, not to leave implied.

### Styling exclusion is a decision with a name (AC #5)

Story 2.2 settles which attributes count as styling and why. This story's job is narrower: make the exclusion **visible in the coverage report itself**, so a reader meeting `wrapText` nowhere in the output learns it was excluded by FR-34 rather than missed.

An exclusion recorded only in a schema document nobody opens is indistinguishable, from the coverage report, from an oversight.

### Why this story carries Keen intensity

Every other story in this epic is checkable against the fixture: an element either parses or it does not. **This one is a claim about estates nobody has seen**, and the only defence against it being over-generous is that its numbers are derived by enumeration rather than asserted from a list.

The failure mode is specific and quiet: a coverage report that counts what the adapter modelled, divides by what the adapter attempted, and reports 100%. Both numbers would be true. The reader would conclude the catalog was fully understood, and 2521 files would have gone unmentioned.

### References

- [Source: .../ARCHITECTURE-SPINE.md#AD-3, #AD-5, #AD-18]
- [Source: estate/knowledge-base/coverage.csv] — the existing RPD shape
- [Source: documents/implementation-artifacts/1-6-extract-the-presentation-layer-and-subject-areas.md] — where per-type coverage was completed for the RPD
- [Source: documents/implementation-artifacts/2-2-derive-the-observed-catalog-schema.md]
- [Source: prd.md#FR-34]

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Amelia, bmad-agent-dev)

### Debug Log References

### Completion Notes List

All seven ACs met.

- **AC #1:** `coverage.csv` gains a `layer` column; catalog types sit beside RPD types, distinguishable.
- **AC #2 — enumerated by parsing, never from a list.** All **55** unmodelled root types are reported with counts. The rule is
  mechanical: every root type encountered that no parser handles produces a row, so the fifty-fourth cannot be dropped. A
  fixture test asserts the count is exactly 55.
- **AC #3:** a non-XML file is `not_a_catalog_object`, classified by **leading bytes** into ten content types — not an error
  and not silence. 1030 files, aggregated by what they are rather than one row each, because 1030 rows in `errors.csv` would
  bury the 33 genuinely dangling references that matter.
- **AC #4:** `xml_version` recorded on every catalog object row, and aggregated per object type in `catalog_versions.csv`
  with **absence written as `(none)`**. **Absence is the most common state of all — 1643 against 1504** for the largest
  declared value. The story, Story 2.1 and the epic all called it *second* most common; corrected at all four sources.
- **AC #5:** styling exclusion emitted as `excluded_by_scope` rows in `unparsed.csv`, so the exclusion is visible **in the
  output** rather than only in a schema document nobody opens. A fixture test asserts no attribute is ever both excluded and
  a gap.
- **AC #6:** tests prove an unknown attribute and an unknown object type are both reported.
- **AC #7 — `coverage_summary.csv`, in whole numbers that add up:**

  | Population | Files | Share |
  |---|---:|---:|
  | Modelled | 2850 | **53%** |
  | Parsed, type not modelled | 1491 | 28% |
  | Not a catalog object | 1030 | 19% |

  53 + 28 + 19 = 100, and `parsed_as_xml + not_a_catalog_object = files_seen` is asserted by test rather than by arithmetic in
  a document. **The failure this exists to prevent — counting what was modelled, dividing by what was attempted, reporting
  100% — is impossible here, because the denominator is files seen.**

### File List

- `tools/rpd_extract/adapters/inbound/catalog_xml.py` (census, unmodelled enumeration, non-XML classification)
- `tools/rpd_extract/adapters/inbound/observing.py` (`out_of_scope` scope-decision reporting)
- `tools/rpd_extract/core/model.py` (layer-qualified coverage, `catalog_versions`, `input_census`)
- `tools/rpd_extract/adapters/outbound/knowledge_base.py` (`coverage`, `catalog_versions`, `coverage_summary`)
- `tools/rpd_extract/tests/test_catalog.py`, `test_catalog_fixture.py`
