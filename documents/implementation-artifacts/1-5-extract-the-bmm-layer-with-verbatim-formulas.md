# Story 1.5: Extract the BMM Layer with Verbatim Formulas

Status: review — implementation complete, 50/50 tests passing, verified against the full corpus.

**Review intensity: Normal** — Ground Truth fixtures catch errors mechanically, provided Story 1.3's guard decision and AD-21's three-form rule are both honoured.

## Story

As an Operator,
I want every logical table and logical column captured with its formula exactly as written, in all three of the forms MDS XML stores,
so that I can read a metric's true logic in a spreadsheet instead of decoding the RPD by hand, and a later Parity Check can reason over it with certainty.

## Acceptance Criteria

1. `logical_tables.csv` and `logical_columns.csv` are written, each row carrying `<rpd-id>::bmm::<object-path>`.
2. **Every expression is captured in all three forms** — `ExprText`, `ExprTextDesc`, and the `ObjectRefList` references — each in its own column, each verbatim (AD-21).
3. Stored expression text is character-for-character identical to the source, with no normalisation, reformatting, or whitespace collapsing (FR-2).
4. Expression text containing commas, double quotes, or newlines round-trips intact through the Story 1.3 writer.
5. A logical column that is a measure records its aggregation rule from `MeasureDefn/AggrRule`.
6. Each logical column records how many Logical Table Sources map it, so multi-source columns are identifiable without joining another table (FR-3 support).
7. A logical column whose expression cannot be parsed with certainty is recorded in `unparsed.csv` with its identifier and reason; nothing is approximated (AD-3).
8. No content in `estate/knowledge-base/` originates from an LLM (AD-2).
9. Fixtures with recorded Ground Truth cover expression text containing each of: an embedded comma, a double quote, a newline, and a leading `-` (AD-19).

## Tasks / Subtasks

- [ ] Extend the core model with logical table, logical column, expression triple, aggregation rule (AC: #1, #2, #5)
- [ ] Extend `mds_xml` to parse `LogicalTable` (AC: #1, #2, #5, #6, #7)
- [ ] Write `logical_tables.csv` and `logical_columns.csv` (AC: #1, #2, #4)
  - [ ] Declare `expr_text`, `expr_text_desc`, and `expr_refs` as guard columns
- [ ] Fixtures and tests (AC: #3, #9)

## Dev Notes

**Read `estate/test-corpus/mds-xml-schema.md` first.** Structure:

```
LogicalTable  @mdsid @name @subjectAreaRef
  LogicalColumn ×1010   @mdsid @name @isWriteable
    AttrDefn/Expr ×933      the column's physical mapping
    Expr          ×15       the column's OWN formula  ← FR-2's primary target
    MeasureDefn   ×35       present when the column is a measure; AggrRule lives here
  RefTableSources/RefLogicalTableSource@logicalTableSourceRef ×92
  LogicalKey/RefColumns/RefLogicalColumn
```

**Only 15 logical columns across the whole corpus carry a derived expression.** The other ~995 are direct mappings expressed through `AttrDefn`. Those 15 plus the 35 `AggrRule` expressions are the interesting cases and where review effort belongs. A real example:

```
Cast("VASILI_KORZUN_DW"."DIM_TIMES"."CALENDAR_YEAR" AS CHAR ) || ' - ' ||
Cast("VASILI_KORZUN_DW"."DIM_TIMES"."CALENDAR_MONTH" AS CHAR )
```

Note the embedded newline and the trailing space before `AS CHAR` — exactly what FR-2 forbids normalising and what the Story 1.3 writer exists to protect.

### AD-21 — three columns, not one

MDS XML stores every expression three ways at once:

| Column | Source | Nature |
|---|---|---|
| `expr_text` | `ExprText` | template with `%1` placeholders — e.g. `SUM("%1")` |
| `expr_text_desc` | `ExprTextDesc` | rendered with names resolved — **derived, never authoritative** |
| `expr_refs` | `ObjectRefList/RefObject@objectRef` | what the placeholders bind to |

Capturing one and discarding the others *is* a rewrite of the formula and breaches FR-2; choosing between them is the guess AD-3 forbids. Store all three verbatim.

`expr_refs` holds MDS object references. Per AD-20 these must be translated to core identifiers at the adapter boundary — store the resolved `<rpd-id>::…` identifiers, not raw `.xml#mdsid` strings. Where a reference cannot be resolved, record an unparsed entry rather than storing a dangling GUID.

### Guard columns are not optional here

`ExprText` values like `SUM("%1")` are safe, but rendered expressions beginning `-` (negation) and any expression beginning `=` are not, and a spreadsheet will eat them. Declare all three expression columns guardable. An undeclared guardable value raises — the intended loud failure.

### Aggregation rule

`MeasureDefn` appears on 35 logical columns and contains `AggrRule`, itself carrying the full expression triple (`SUM("%1")` / `SUM("...")`). Record both the rule name and its expression forms. `AggrRule@isDefault` distinguishes the default rule from dimension-specific overrides — FR-4 requires overrides captured, so **do not collapse multiple `AggrRule` elements into one**.

### Multi-source count

`RefTableSources/RefLogicalTableSource` gives the count directly (92 references across 82 logical tables). Story 1.7 resolves the full lineage; this story records the count so a reader can spot multi-source columns without a join.

### References

- [Source: estate/test-corpus/mds-xml-schema.md#Business Model & Mapping]
- [Source: .../ARCHITECTURE-SPINE.md#AD-21] — all three forms, verbatim
- [Source: .../ARCHITECTURE-SPINE.md#AD-20] — references resolved at the adapter boundary
- [Source: .../ARCHITECTURE-SPINE.md#AD-2, #AD-3, #AD-19]
- [Source: prd.md#FR-2] — verbatim, character for character
- [Source: documents/implementation-artifacts/1-4-extract-the-physical-layer-into-the-knowledge-base.md] — patterns this story extends

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

**AD-21 implemented as specified: all three expression forms, verbatim.** `logical_columns.csv` carries six expression columns — `derived_expr_{text,text_desc,refs}` and `mapping_expr_{text,text_desc,refs}` — and `aggregation_rules.csv` three more. Every one is a declared guard column.

- **AC #1.** `logical_tables` (82) and `logical_columns` (1016), identified as `<rpd-id>::bmm::<business-model>.<table>[.<column>]`.
- **AC #2, #3.** All three forms captured. **`ExprText` and `ExprTextDesc` are read without stripping** — real `AggrRule` expressions begin with a space, and FR-2 forbids reformatting anywhere in the chain. A fixture pins the leading space.
- **AC #4.** Verified on the hardest real value: `-1 * "%1", "x"\nnext` — leading `-`, embedded comma, embedded quotes, embedded newline — round-trips byte-identical and is guarded on disk.
- **AC #5.** `AggrRule` extracted from `MeasureDefn`. **One row per rule**, never collapsed: `@isDefault` distinguishes the default from dimension-specific overrides, and FR-4 requires the overrides. A fixture asserts two rules survive, and that a sibling rule without `ObjectRefList` does not inherit refs from the other.
- **AC #6.** `source_count` from `RefTableSources/RefLogicalTableSource`, so multi-source columns are identifiable without a join.
- **AC #7, #8.** Unparsed entries for unresolvable references; no LLM produces any Knowledge Base content.
- **AC #9.** Fixtures cover embedded comma, double quote, newline, and leading `-` with recorded Ground Truth.

**15 derived logical columns exist across the whole corpus**, exactly matching the schema census. They are FR-2's real target, and they are genuinely interesting — one is a live `AGO` time-series expression:

```
text : Ago("%1" ,  "%2" , 1)
desc : Ago("Anton_Tserakhau"."Operations"."Total Sales ($)" ,  "…"."Month" , 1)
```

Note the double space and trailing space, both preserved. The other ~1000 logical columns are direct mappings expressed through `AttrDefn`, captured separately in `mapping_expr_*`.

**Why `derived` and `mapping` are separate columns rather than one.** They answer different questions: `derived` is the column's own formula, `mapping` is how it reaches physical storage. Merging them would force a choice at extraction time — the lossy decision AD-21 exists to prevent.

**A logical table whose business model cannot be resolved is recorded unparsed rather than given a placeholder container.** The business model qualifies the identifier; inventing one would produce a plausible identifier pointing at nothing, which AD-3 forbids.

### File List

- `tools/rpd_extract/core/model.py` (logical table, logical column, aggregation rule, expression triple)
- `tools/rpd_extract/adapters/inbound/mds_xml.py` (`_parse_logical`, `_read_expression`)
- `tools/rpd_extract/adapters/outbound/knowledge_base.py` (`logical_tables`, `logical_columns`, `aggregation_rules`)
- `tools/rpd_extract/tests/test_extraction.py`, `tests/fixtures/GROUND-TRUTH.md`
