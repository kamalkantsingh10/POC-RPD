# Story 1.6: Extract the Presentation Layer and Subject Areas

Status: review — implementation complete, 66/66 tests passing, verified against the full corpus.

**Review intensity: Normal** — fixture-checked, and a broken rename chain surfaces as an unresolvable reference.

## Story

As an Operator,
I want every Subject Area and presentation column captured with its rename chain back to the logical layer,
so that I can start from the names business users see and reach the logic underneath.

## Acceptance Criteria

1. `presentation_subject_areas.csv` and `presentation_columns.csv` are written, each row carrying `<rpd-id>::pres::<object-path>`.
2. Each presentation column records the logical column it exposes, by resolved core identifier.
3. The physical → logical → presentation name chain is recoverable (FR-4).
4. A Subject Area with an implicit fact column records it (FR-4).
5. With all three layers captured, `coverage.csv` reports parsed and skipped counts for physical, BMM, and presentation objects — completing FR-1.
6. A presentation column pointing at a logical column that does not exist is recorded in `unparsed.csv` with the reason rather than silently dropped (AD-3).
7. Fixtures with recorded Ground Truth cover a renamed column and a Subject Area carrying an implicit fact column (AD-19).

## Tasks / Subtasks

- [ ] Extend the core model with subject area, presentation table, presentation column (AC: #1)
- [ ] Parse `PresentationCatalog`, `PresentationTable`, `PresentationHierarchy` (AC: #1, #2, #4)
- [ ] Record the rename chain (AC: #3)
- [ ] Write the tables; complete coverage reporting across all three layers (AC: #5)
- [ ] Fixtures and tests (AC: #6, #7)

## Dev Notes

```
PresentationCatalog  @mdsid @name @subjectAreaRef @isAutoAggr @isDefaultReadable
                     @defaultFactColumnRef          ← the implicit fact column
  RefTables/RefPresentationTable@presentationTableRef ×128
  Alias@name                                          former names

PresentationTable    @mdsid @name @containerRef @hasDispName @dispName
  PresentationColumn ×1543  @mdsid @name @logicalColumnRef @overrideLogicalName
                            @hasDispName @dispName
```

**Terminology trap:** `PresentationCatalog` is a **Subject Area**, not the Web Catalog. The Web Catalog is the report store, is absent from this corpus entirely, and belongs to the deferred FR-6/FR-7 work. Do not conflate them — the names are close and the concepts are unrelated.

### The rename chain (AC #3)

Three attributes carry it:

- `@logicalColumnRef` — the logical column exposed. Resolve to a core identifier at the adapter boundary (AD-20).
- `@overrideLogicalName` — present on all 1543 presentation columns. Records whether the presentation name is an override rather than inherited.
- `@dispName` / `@hasDispName` — a display name distinct from the object name (6 columns, 1 table).

Combined with Story 1.5's logical columns and Story 1.4's physical columns, this makes the full physical → logical → presentation chain recoverable. Record the components rather than a pre-joined string: FR-4 asks for the chain to be *recoverable*, and NFR2 wants every step traceable to a recorded identifier.

`Alias` elements (15 across catalogs, 13 on tables) hold former names. Capture them — they are how a Group Spec stays valid across a rename, and dropping them loses information that cannot be recovered later.

### Implicit fact column (AC #4)

`@defaultFactColumnRef` on `PresentationCatalog`. **Present on 1 of 21 catalogs in this corpus.**

This is thin coverage, and it is deliberate that AC #7 requires a fixture. Under AD-19 a construct without a fixture is treated as unimplemented, and one live example is a weak basis for a claim — Story 1.9's Constructed Cases should strengthen it.

An earlier survey recorded this construct as absent because it searched for `implicitFact`. The attribute is `defaultFactColumnRef`. Trust `mds-xml-schema.md`, which was derived by parsing every file, over any grep.

### Completing FR-1 (AC #5)

FR-1 requires all three layers captured, so this story is where it closes. `coverage.csv` must report per object type across physical, BMM, and presentation — not a single total. Object types present but not modelled still appear, with a skip reason.

### References

- [Source: estate/test-corpus/mds-xml-schema.md#Presentation layer]
- [Source: .../ARCHITECTURE-SPINE.md#AD-20, #AD-3, #AD-19]
- [Source: prd.md#FR-1, #FR-4]
- [Source: documents/implementation-artifacts/1-5-extract-the-bmm-layer-with-verbatim-formulas.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

**Presentation layer extracted; FR-1 now closed** — all three RPD layers captured.

- **AC #1.** `presentation_subject_areas` (21), `presentation_tables` (128), `presentation_columns` (1543), identified as `<rpd-id>::pres::<subject-area>.<table>[.<column>]`.
- **AC #2.** **All 1543 presentation columns resolve to a logical column.** Zero dangling references across the corpus.
- **AC #3.** The rename chain is stored as components — `logical_column_id`, `override_logical_name`, `display_name` — not as a pre-joined string, so every step stays traceable (NFR2).
- **AC #4.** `@defaultFactColumnRef` captured. Present on **1 of 21** Subject Areas, so the fixture carries most of the evidence this construct works at all.
- **AC #5.** `coverage.csv` reports parsed and skipped per object type across physical, BMM and presentation.
- **AC #6, #7.** Unresolvable logical-column references recorded; fixtures cover a renamed column and an implicit fact column.

**`Alias` elements are captured** (former names, on Subject Areas and tables). They are how a Group Spec stays valid across a rename; dropping them loses information that cannot be recovered later.

**Terminology guarded in code and docstring:** `PresentationCatalog` is a **Subject Area**, not the Web Catalog. The names are close, the concepts unrelated, and the Web Catalog is absent from this corpus entirely.

### File List

- `tools/rpd_extract/core/model.py` (`SubjectArea`, `PresentationTable`, `PresentationColumn`)
- `tools/rpd_extract/adapters/inbound/mds_xml.py` (`_parse_subject_area`, `_parse_presentation_table`)
- `tools/rpd_extract/adapters/outbound/knowledge_base.py` (three presentation tables)
- `tools/rpd_extract/tests/` (fixtures + `PresentationLayer` tests)
