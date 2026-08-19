# Story 1.4: Extract the Physical Layer into the Knowledge Base

Status: review — implementation complete, 50/50 tests passing, verified against the full corpus.

**Review intensity: High** — the walking skeleton. AD-3, AD-5, AD-6, AD-7 and AD-20 all land here, and Stories 1.5–1.7 copy whatever pattern it sets.

## Story

As an Operator,
I want to run one command against the corpus and get the Physical Layer as Knowledge Base tables with a manifest and an honest coverage report,
so that the extraction pipeline works end to end and reports what it could not do from its very first run.

## Acceptance Criteria

1. One CLI invocation, given a corpus root, writes `estate/knowledge-base/` containing `physical_tables.csv`, `physical_columns.csv`, and `physical_joins.csv`, all through the Story 1.3 writer.
2. Every row carries a `row_id` of the form `<rpd-id>::phys::<object-path>` (AD-7).
3. The `rpd-id` comes from the corpus directory layout declared in Story 1.2 — never from a filename, timestamp, or content hash.
4. `manifest.csv` records the tables present, the corpus root, every `rpd-id` extracted, the extraction timestamp in ISO 8601 UTC, and the extractor version (AD-5).
5. An unrecognised construct produces a row in `unparsed.csv` carrying the source identifier and the reason; extraction continues and nothing is approximated (AD-3, NFR7).
6. `coverage.csv` states objects parsed and objects skipped per object type (FR-5).
7. A corpus root containing no recognisable MDS XML fails with an error naming the expected layout, and writes no partial Knowledge Base (FR-1).
8. Re-running over an unchanged corpus produces byte-identical output (AD-6, FR-8).
9. No CLI argument scopes extraction to a single Dashboard or Subject Area (FR-9).
10. The Estate model and parsing rules live in `tools/rpd_extract/core/` and perform no I/O; the reader lives in `tools/rpd_extract/adapters/inbound/mds_xml.py` (AD-1, AD-15).
11. **No MDS-specific concept appears in `core/`** — no GUIDs, file paths, or `#mdsid` fragments (AD-20).
12. Running from a clean checkout with no internet access and no installation step succeeds (AD-16, FR-23).
13. Core parsing is tested directly through fixtures; no test requires a live OBIEE instance (AD-19).

## Tasks / Subtasks

- [ ] Core Estate model (AC: #10, #11)
  - [ ] `core/model.py` — dataclasses for physical table, column, key, foreign key. Plain identifiers and values only.
  - [ ] `core/identifiers.py` — build and validate `<rpd-id>::<layer>::<object-path>`; lower-kebab `rpd-id`.
  - [ ] No imports from `adapters`. Add a test asserting it (mirror the AST check in `test_csv_writer.py`).
- [ ] Inbound adapter (AC: #1, #5, #7)
  - [ ] `adapters/inbound/mds_xml.py` — walk `<corpus>/<rpd-id>/oracle/bi/server/base/<ObjectType>/*.xml`.
  - [ ] Parse `PhysicalTable`, `Database`, `Schema`, `ConnectionPool`, `ComplexJoin`. Resolve `@containerRef` to name the owning schema/database.
  - [ ] Translate MDS references into core identifiers **at this boundary**. GUIDs stop here.
  - [ ] Record every unrecognised element and every unresolvable reference as an unparsed entry.
- [ ] Outbound tables (AC: #1, #2, #4, #6)
  - [ ] `physical_tables.csv`, `physical_columns.csv`, `physical_joins.csv`, `manifest.csv`, `coverage.csv`, `unparsed.csv` via `csv_writer.write_table`.
- [ ] CLI (AC: #1, #3, #9, #12)
  - [ ] `cli.py` — `--corpus <path>` and `--out <path>`. Nothing that narrows scope.
  - [ ] `rpd-id` read from the path segment directly beneath the corpus root.
- [ ] Determinism (AC: #8)
  - [ ] Sort rows by `row_id` before writing. Directory iteration order is not stable across filesystems and would otherwise break AD-6.
- [ ] Tests (AC: #13)

## Dev Notes

**Corpus:** `~/Documents/Garage/obiee-corpus/clean/` — two `rpd-id` directories, `bi-analytics-2013` and `sampleapp`, 1383 XML files, identical internal layout. Outside the repository by design; see `estate/test-corpus/corpus.md`.

**Read `estate/test-corpus/mds-xml-schema.md` before writing the adapter.** It is the observed schema for every object type, derived by parsing all 1383 files. Oracle publishes no schema for this format, so it is the only specification that exists.

### What the Physical Layer looks like

```
PhysicalTable  @mdsid @name @type @maxConn @containerRef
  PhysicalColumn ×1096   @mdsid @name @dataType @specialType @precision @nullable
                         @extName @sourceColumnRef
  PhysicalKey/RefColumns/RefColumn@columnRef
  PhysicalForeignKey/RefColumns/RefColumn@columnRef
Database       @mdsid @name @type    +  Feature@name/@value ×2739
ComplexJoin    @mdsid @name @cardinality @table1Ref @table2Ref  + Expr
```

`@containerRef` points at a `Schema` or `Database` file; resolving it gives the qualified physical name. `PhysicalForeignKey` and `ComplexJoin` are both physical joins and both belong in `physical_joins.csv` — distinguish them with a `join_kind` column rather than dropping either.

### AD-20 is the rule most likely to be broken here

The core must hold no MDS concept. Concretely: `core/` never sees a `.xml` path, an `mdsid`, or a `#fragment`. The adapter resolves `objectRef="/oracle/bi/server/base/PhysicalTable/abc.xml#mabc"` into the core identifier `sampleapp::phys::<schema>.<table>` and hands over the identifier alone.

This is what keeps a future `biserverxmlgen` adapter an addition rather than a rewrite. Treat a GUID reaching `core/` as a defect against AD-20, and add a test that asserts it.

### Determinism needs an explicit sort

`Path.iterdir()` order is filesystem-dependent. AC #8 requires byte-identical re-runs, so sort rows by `row_id` before writing. The CSV writer deliberately never reorders — ordering is the caller's contract, and this story is the caller.

### Identifiers

Format per AD-7: `<rpd-id>::<layer>::<object-path>`, `phys` for this layer.

```
sampleapp::phys::SAMPLESALES.SAMP_REVENUE_F
sampleapp::phys::SAMPLESALES.SAMP_REVENUE_F.REVENUE
```

`rpd-id` is declared, not derived — the declaration is the directory name the Operator chose in Story 1.2. Reading it from the path honours the rule; deriving it from a filename or hash would not.

### Guard columns

Pass `guard_columns` for any column that can carry expression text or identifier-like values. In this story `ComplexJoin` join conditions qualify (`Expr` content such as `1=1`), as do physical column names that could be numeric-looking. When in doubt declare the column: an undeclared guardable value raises, which is the intended loud failure and cheap to fix.

### Coverage and unparsed are not a later story

AD-3 requires the extractor never to guess, and NFR7 names silent omission as the primary failure mode. Both `coverage.csv` and `unparsed.csv` ship in this story so Stories 1.5–1.7 extend an existing mechanism rather than retrofitting honesty.

Expect real unparsed entries — that is success, not failure. `Database/Feature` alone has 2739 rows of capability flags this story does not model.

### Testing

`unittest`, stdlib only — the stack table says no third-party packages at any version, which includes pytest. Fixtures are small MDS XML files committed under `tools/rpd_extract/tests/fixtures/`, authored by us and derived from corpus shapes. **Do not commit corpus files**: unlicensed, and AD-16 ships every committed byte to the VDI.

### Project Structure Notes

Creates `core/`, `adapters/inbound/`, `cli.py`. `adapters/outbound/csv_writer.py` already exists from Story 1.3 and needs no change.

### References

- [Source: estate/test-corpus/mds-xml-schema.md] — observed schema, all object types
- [Source: estate/test-corpus/corpus.md] — corpus layout and `rpd-id` declarations
- [Source: .../ARCHITECTURE-SPINE.md#AD-20] — MDS XML is the target; no MDS concepts in core
- [Source: .../ARCHITECTURE-SPINE.md#AD-3] — never guess; unparsed entries carry identifier and reason
- [Source: .../ARCHITECTURE-SPINE.md#AD-5, #AD-6, #AD-7, #AD-15, #AD-19]
- [Source: documents/planning-artifacts/decisions/csv-formula-guard.md] — guard semantics
- [Source: documents/planning-artifacts/epics.md#Story 1.4]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

**Runs end to end against the real corpus.** 1383 XML files across two `rpd-id`s → 2471 objects parsed, 1157 recorded as unparsed, byte-identical on re-run.

- **AC #1–#4, #6.** `physical_tables` (100), `physical_columns` (1096), `physical_joins` (104), plus `manifest`, `coverage`, `unparsed`. All written through the Story 1.3 writer.
- **AC #3.** `rpd-id` comes from the corpus directory name — the Operator's declaration from Story 1.2 — and is validated as lower-kebab.
- **AC #5, #7.** Unparsed entries carry source identifier and reason. A corpus root with no MDS XML fails naming the expected layout.
- **AC #8.** Verified idempotent by diffing two full runs. Rows are sorted by `row_id` before writing — `Path.iterdir()` order is filesystem-dependent and would otherwise break AD-6 invisibly.
- **AC #9.** The CLI takes `--corpus` and `--out` only. Nothing narrows scope.
- **AC #10, #11.** `core/` holds the Estate model and identifier rules and performs no I/O. **A test asserts AD-20 mechanically**: `core/` must contain no `mdsid`, `.xml`, `objectRef`, `ExprTextDesc`, or `oracle/bi/server` in executable code.
- **AC #12.** Runs from a clean checkout via `python -m tools.rpd_extract.cli`. No install step, no third-party imports — asserted by test.
- **AC #13.** Fixtures under `tests/fixtures/` with Ground Truth in `fixtures/GROUND-TRUTH.md`. No test touches a live instance.

**Two-pass design was necessary, not incidental.** MDS XML is a graph, not a tree: a physical table names its container by reference and a column mapping names columns in other files. Pass one indexes every `mdsid`; pass two resolves references into Knowledge Base identifiers. Without it, identifiers could not be built at all.

**A real defect found and fixed during the run.** Unresolved expression references were being silently dropped, leaving an expression that still looked complete — precisely the plausible-wrong-answer failure NFR7 names as primary. They are now recorded as `ExpressionRef` unparsed entries. Four exist in the corpus out of 985 placeholder bindings.

**Physical joins carry a `kind` column** (`foreign_key` / `complex_join`). Both are physical joins in MDS XML and both are real relationships; dropping either would lose information silently.

**The 1157 unparsed entries are expected, not a failure.** They are object types this story does not model yet — `Variable` (345), `InitBlock` (154), `PresentationTable` (128), `LogicalTableSource` (92), `LogicalComplexJoin` (84) — each owned by Stories 1.6, 1.7 and 1.10. `coverage.csv` reports them per type so the gap is visible rather than implied.

### File List

- `tools/rpd_extract/core/__init__.py`, `core/identifiers.py`, `core/model.py` (created)
- `tools/rpd_extract/adapters/inbound/__init__.py`, `adapters/inbound/mds_xml.py` (created)
- `tools/rpd_extract/adapters/outbound/knowledge_base.py` (created)
- `tools/rpd_extract/cli.py` (created)
- `tools/rpd_extract/tests/test_extraction.py`, `tests/fixtures/**` (created)
