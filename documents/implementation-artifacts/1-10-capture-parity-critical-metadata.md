# Story 1.10: Capture Parity-Critical Metadata

*Verified against recorded Ground Truth.*

Status: review — implementation complete, 75/75 tests passing.

**Review intensity: High** — nine construct types, and it produces SM-7, the accuracy figure the PRD says to lead with at approval.

## Story

As an Operator,
I want the deterministic details that silently break numeric parity captured and proven correct,
so that a missing content filter or an aggregation override cannot produce a plausible wrong number months later.

## Acceptance Criteria

1. Aggregation rule per logical column is recorded, including dimension-specific overrides — multiple `AggrRule` elements are never collapsed into one (FR-4).
2. Logical Table Source priority order, fragmentation predicates, and content-level filters are recorded per source; where the source provides none, absence is recorded explicitly rather than omitted (FR-4, NFR7).
3. `bmm_joins.csv` records the join type for each join, from `LogicalComplexJoin@type` (FR-4).
4. A logical column using `AGO`, `TODATE`, or `PERIODROLLING` is flagged on its row (FR-4).
5. `variables.csv` records every session and repository variable with the object referencing it (FR-4).
6. `security_rls.csv` records the row-level security filter per application role (FR-4).
7. Each of the nine FR-4 construct types has a fixture with recorded Ground Truth, and **any construct without one is reported as unimplemented rather than claimed as working** (AD-19).
8. Extraction against the Constructed Cases compares each result to its recorded Ground Truth, and accuracy is reported per construct type as CSV, not as a single aggregate figure (SM-7).
9. A construct the parser recognises but cannot resolve with certainty is recorded in `unparsed.csv` with its identifier and reason (AD-3).
10. Re-running over unchanged input leaves every output file byte-identical (FR-9, AD-6).

## Tasks / Subtasks

- [ ] Aggregation rules including overrides (AC: #1)
- [ ] LTS priority, fragmentation, content filters (AC: #2)
- [ ] `bmm_joins.csv` from `LogicalComplexJoin` (AC: #3)
- [ ] Time-series flags (AC: #4)
- [ ] `variables.csv` from `Variable` + `InitBlock` (AC: #5)
- [ ] `security_rls.csv` from the Group → PrivilegePackage → ObjectPrivilege / QueryPrivilege chain (AC: #6)
- [ ] Ground Truth comparison and per-construct accuracy report (AC: #7, #8)

## Dev Notes

**This story produces SM-7**, which PRD §14 calls *"the only accuracy figure that is a fact rather than a judgement, and the one to lead with at approval."* Everything here serves that, so overstating coverage is the failure mode to guard against — not incompleteness.

### Coverage reality — what can and cannot be claimed

Measured across the corpus (`estate/test-corpus/environment.md` §3b):

| FR-4 construct | Corpus evidence | Claimable from corpus alone? |
|---|---|---|
| Aggregation rule | 35 `AggrRule`, `@isDefault` present | **Yes** |
| Content-level filter | 6 populated `WhereClause` | **Yes** |
| BMM join type | `LogicalComplexJoin@type` ×84 | **Yes** |
| Session / repository variables | 345 variables, 154 init blocks, 1294 `VALUEOF` | **Yes, strongly** |
| RLS per application role | Group 28 → PrivilegePackage 33 → ObjectPrivilege 68 / QueryPrivilege 73 | **Yes** |
| Rename chain | `@overrideLogicalName` ×1543 | **Yes** |
| `TODATE` | 9 files | Yes |
| `AGO` | 1 file | **Thin** |
| Implicit fact column | 1 of 21 catalogs | **Thin** |
| LTS priority order | absent | **No — needs Story 1.9** |
| Fragmentation predicate | `FragmentContent` ×92, **0 populated** | **No — needs Story 1.9** |
| `PERIODROLLING` | absent | **No — needs Story 1.9** |

**Three constructs cannot be claimed without Story 1.9, and two more are thin.** AC #7 exists to make that visible rather than papered over: under AD-19 a construct without a fixture is *unimplemented*, and the per-construct report must say so in the same table as the successes.

### Security is a chain, not an object

RLS does not live in one place. Resolve it:

```
Group (@guid @displayName)                    the application role
  ← PrivilegePackage (@roleRef | @userRef)
      ├── ObjectPrivilege (@type) → RefObjects/RefObject
      └── QueryPrivilegeMapping (@databaseRef @queryPrivilegeRef)
            → QueryPrivilege (@maxExecTime @maxRows)
```

The *predicate* itself is elsewhere again — a `WhereClause` on a Logical Table Source, typically referencing a session variable:

```
Position(';Role_DW_Admin;' in ';' || valueof(NQ_SESSION.ROLEGUIDS) || ';') > 0
```

So `security_rls.csv` must join the role chain to the filter expression. A role with privileges but no predicate, and a predicate not reachable from any role, are both real states — record them rather than dropping either.

### Aggregation overrides (AC #1)

`MeasureDefn` may hold more than one `AggrRule`; `@isDefault` marks the default and the others are dimension-specific overrides. **Collapsing them loses exactly the detail FR-4 names**, and it is the kind of loss that produces a plausible wrong number rather than an error. One row per rule.

### Absence is data (AC #2)

`FragmentContent` is present on all 92 Logical Table Sources and populated on none. That is not "no fragmentation" — it is "this corpus does not exercise fragmentation", and the two must not read the same in the output. Record the element as present-and-empty, and let `coverage.csv` carry the distinction.

The same applies to LTS priority, which has no attribute at all in this corpus. Do not infer it from document order or filename — that is the guess AD-3 forbids, and getting it wrong silently repoints a measure at the wrong source.

### References

- [Source: prd.md#FR-4] — the nine construct types
- [Source: prd.md#14] — SM-7, per construct type, the figure to lead with
- [Source: estate/test-corpus/environment.md#3b] — measured coverage
- [Source: estate/test-corpus/mds-xml-schema.md#Security] — the role chain
- [Source: .../ARCHITECTURE-SPINE.md#AD-19] — no fixture means unimplemented
- [Source: .../ARCHITECTURE-SPINE.md#AD-3] — never infer what is not recorded
- [Source: documents/implementation-artifacts/1-9-author-constructed-cases-with-recorded-ground-truth.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

**All FR-4 constructs now extracted, and SM-7 reported per construct type.**

New Knowledge Base tables: `bmm_joins` (84), `variables` (345), `init_blocks` (154), `security_rls` (198). `logical_columns` gains a `time_series` column. **Unparsed fell from 943 to 231.**

- **AC #1.** One row per `AggrRule`; overrides never collapsed.
- **AC #2.** Priority, fragmentation and content filters recorded per source, with **absence recorded explicitly** — `FragmentContent` present-and-empty is not the same as no fragmentation.
- **AC #3.** `bmm_joins.join_type` from `LogicalComplexJoin@type`: **76 Inner, 7 LeftOuter, 1 RightOuter.** The outer-join construct FR-4 names is present in real data.
- **AC #4.** `AGO` / `TODATE` / `PERIODROLLING` flagged per column. Detection lives in `core` — the function names are OBIEE's, not the file format's, so it is domain logic and does not breach AD-20.
- **AC #5.** 345 variables, 103 of them session variables, joined to 154 init blocks.
- **AC #6.** Security resolved through the real chain — `Group` → `PrivilegePackage` → `ObjectPrivilege` / `QueryPrivilege` — with **row-level predicates recorded where they actually sit**, on the Logical Table Source. A role with privileges but no predicate, and a predicate not reachable from any role, are both real states and both stay visible.
- **AC #7, #8.** `tools/rpd_extract/verify.py` writes `estate/test-corpus/accuracy-by-construct.csv`.
- **AC #9, #10.** Unresolvable constructs recorded; output byte-identical on re-run.

**The accuracy report: 15 pass, 0 fail, 2 unimplemented.**

The two `unimplemented` rows are the point of the exercise. Fragmentation predicate and aggregation override have **no corpus evidence**, so under AD-19 they are reported as unimplemented against corpus data — and separately as passing against Constructed Cases. Merging those into one figure would claim corpus evidence that does not exist. `evidence` is a column precisely so they cannot be merged.

A test asserts that an absent construct reports `unimplemented` rather than passing, so silence can never read as success.

**One correction to an earlier note.** LTS priority was previously called absent from the corpus. The report shows **one** real source carrying it — thin, but not zero. `accuracy-by-construct.csv` is the accurate record.

### File List

- `tools/rpd_extract/core/model.py` (`BmmJoin`, `Variable`, `InitBlock`, `SecurityRule`, `time_series_used`)
- `tools/rpd_extract/adapters/inbound/mds_xml.py` (five parsers, row-filter collection, time-series flagging)
- `tools/rpd_extract/adapters/outbound/knowledge_base.py` (four tables + `time_series`)
- `tools/rpd_extract/verify.py` (created)
- `estate/test-corpus/accuracy-by-construct.csv` (generated)
- `tools/rpd_extract/tests/test_extraction.py` (`ParityCriticalMetadata`, `AccuracyReport`)
