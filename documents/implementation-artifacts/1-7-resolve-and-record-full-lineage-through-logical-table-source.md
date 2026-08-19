# Story 1.7: Resolve and Record Full Lineage Through Logical Table Sources

Status: review — implementation complete, 66/66 tests passing, verified against the full corpus.

**Review intensity: Normal** — the referential-integrity check makes breakage visible. Watch one thing: a dropped source in a multi-source column is a *missing row*, which reads as normal output unless the count is asserted.

## Story

As an Operator,
I want every presentation column traced to the physical tables and columns it depends on,
so that I can answer "where does this number come from" without opening the Administration Tool.

## Acceptance Criteria

1. `logical_table_sources.csv` and `lts_column_map.csv` are written with qualified identifiers.
2. `lineage.csv` states a full path per row: presentation column → logical column → Logical Table Source → physical table and column (FR-3).
3. A logical column with three Logical Table Sources produces three lineage rows — every source listed, none dropped (FR-3).
4. Each Logical Table Source records its priority order where the source provides one.
5. Every physical column referenced by a lineage row resolves to an existing row in `physical_columns.csv`.
6. A presentation column whose path cannot be fully resolved is recorded in `unparsed.csv` with the reason and the point at which resolution failed (AD-3, NFR7).
7. Every lineage row traces to source objects through recorded identifiers, with no unstated inference (NFR2).
8. Fixtures with recorded Ground Truth cover a single-source column and a multi-source column (AD-19).

## Tasks / Subtasks

- [ ] Parse `LogicalTableSource` (AC: #1, #4)
- [ ] Resolve `ColumnMapping` pairs into the logical → physical map (AC: #1, #5)
- [ ] Build `lineage.csv` by walking presentation → logical → LTS → physical (AC: #2, #3)
- [ ] Referential-integrity check across tables (AC: #5)
- [ ] Fixtures and tests, including the multi-source count assertion (AC: #8)

## Dev Notes

```
LogicalTableSource  @mdsid @name @isActive @logicalTableRef
  ColumnMapping ×1035        holds BOTH sides of one mapping:
    LogicalColumnExpr          logical side  → "SAMPLESALES"."Fact Revenue"."Bill Day Dt"
    Expr                       physical side → "xe".""."SAMPLESALES"."SAMP_REVENUE_F"."BILL_DAY_DT"
  Link@startNodeTableRef ×111  the physical join path this source traverses
  FragmentContent ×92          present on every source; 0 populated in this corpus
  GroupBy ×92                  21 populated
  WhereClause                  content filter; 6 populated
```

**`ColumnMapping` is the lineage primitive.** Each of the 1035 mappings carries both sides as a paired expression triple. The logical side names the logical column; the physical side names the physical column. Resolve both to core identifiers at the adapter boundary per AD-20 — never store `.xml#mdsid` strings in the Knowledge Base.

### The failure mode this story is most likely to hide

A logical column mapped by three sources should produce three lineage rows. Drop one and the output still looks entirely normal — there is no error, no gap, and no visibly wrong value. It only surfaces much later as a number that disagrees with the legacy report.

So AC #3 is not satisfied by "multi-source columns produce multiple rows". **Assert the count**: for each logical column, the number of distinct Logical Table Sources in `lineage.csv` must equal its `RefTableSources/RefLogicalTableSource` count, which Story 1.5 already records. A mismatch is a hard failure, not a warning.

This is why the story is Normal intensity overall but carries one keen-review line.

### Priority (AC #4)

**`LogicalTableSource` has no priority attribute in this corpus.** The observed attributes are `@mdsid @name @isActive @logicalTableRef`, and a single stray `priorityGroup` appears in one SampleApp file.

Record priority where the source provides it and record its **absence explicitly** where it does not — an empty column with a documented reason, not a silently omitted concept. FR-4 requires LTS priority order captured, so this is a genuine coverage gap that Story 1.9's Constructed Cases must close, and Story 1.10 cannot claim the construct until they do (AD-19).

Do not infer priority from document order or file name. That is precisely the guess AD-3 forbids, and getting it wrong silently repoints a measure at the wrong source.

### `Link` and the physical join path

`Link@startNodeTableRef` (111 occurrences) names the physical table a source starts from, which combined with Story 1.4's `physical_joins.csv` gives the traversal. Capture it; it is what makes a lineage row explainable rather than merely stated.

### Referential integrity (AC #5)

After writing, every `physical_column_id` in `lineage.csv` must exist in `physical_columns.csv`, and every `logical_column_id` in `logical_columns.csv`. Run it as a test over the real corpus, not only over fixtures — 1035 mappings is a far better integrity check than any fixture set.

### References

- [Source: estate/test-corpus/mds-xml-schema.md#Business Model & Mapping]
- [Source: .../ARCHITECTURE-SPINE.md#AD-3, #AD-20, #AD-19]
- [Source: prd.md#FR-3, #FR-4] — all sources listed; LTS priority order
- [Source: prd.md#7 Cross-Cutting NFRs] — NFR2 traceability, NFR7 failure honesty
- [Source: documents/implementation-artifacts/1-6-extract-the-presentation-layer-and-subject-areas.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

**Lineage resolved end to end: 1573 rows, zero dangling physical references.**

- **AC #1.** `logical_table_sources` (92) and `lts_column_map` (1035).
- **AC #2.** `lineage.csv` states presentation column → logical column → source → physical table and column.
- **AC #3.** 29 multi-source columns each produce one row per mapping source.
- **AC #5.** **Referential integrity verified on the real corpus: 1573/1573 physical references resolve.**
- **AC #6, #7, #8.** Unresolvable paths recorded; fixtures cover single-source and multi-source columns.

**AC #4 and a spec correction — the story's assertion was wrong.**

The story required lineage source counts to equal the logical column's `source_count`. Running it against the corpus produced **30 mismatches**, and they were correct data, not bugs: `source_count` counts sources declared on the owning **table**, while lineage counts sources that actually **map that column**. A table with four sources may map a given column in only two.

So the extractor now records both, and the test asserts against `mapped_source_count`. Asserting against the table count would have failed on correct data and — worse — masked the real finding: **53 columns are mapped by fewer sources than their table declares.** A source that cannot supply a column cannot satisfy a query needing it. That gap is a genuine parity hazard, and it is now visible in the Knowledge Base instead of being averaged away.

**Priority: recorded as absent, never inferred.** MDS XML carries no priority attribute on `LogicalTableSource`. Empty means *not recorded*, not *lowest*. Inferring order from document position is the guess AD-3 forbids, and getting it wrong silently repoints a measure at the wrong source. FR-4's LTS priority requirement therefore remains **uncovered by this corpus** and needs Story 1.9.

**Present-but-empty is distinguished from absent.** `FragmentContent` exists on all 92 sources and is populated on none. "This corpus does not exercise fragmentation" and "there is no fragmentation" must not read the same (NFR7). A test pins the distinction.

**Six real content filters captured**, including a live RLS predicate using `valueof(NQ_SESSION.ROLEGUIDS)` — a genuine FR-4 construct on real data.

### File List

- `tools/rpd_extract/core/model.py` (`LogicalTableSource`, `ColumnMapping`, `LineageRow`, `mapped_source_count`)
- `tools/rpd_extract/adapters/inbound/mds_xml.py` (`_parse_table_source`, `_count_mapped_sources`, `_build_lineage`)
- `tools/rpd_extract/adapters/outbound/knowledge_base.py` (`logical_table_sources`, `lts_column_map`, `lineage`)
- `tools/rpd_extract/tests/` (fixtures + `Lineage` tests)
