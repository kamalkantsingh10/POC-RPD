# Story 2.4: Extract Dashboards and Pages

Status: review

**Review intensity: High** — establishes path resolution, which Stories 2.5 and 2.6 copy.

## Story

As an Operator,
I want every Dashboard and page captured with the Analyses placed on it,
so that I can see what reports exist and what each one is built from.

## Acceptance Criteria

1. `dashboards.csv` and `dashboard_pages.csv` are written, each row carrying `<rpd-id>::cat::<catalog-path>` (AD-22).
2. Identifiers are built from the **decoded** catalog path, the decoding rule is recorded, and the same object always yields the same identifier.
3. Each `sawd:reportRef[@path]` is resolved to a catalog object identifier; a path resolving to no object is recorded in `errors.csv` as an unresolved reference (AD-3).
4. A reference resolved only after case normalisation is **recorded as such**, distinguishably from an exact match, because normalising case is a judgement and AD-3 forbids making one silently.
5. Page ordering within a Dashboard is preserved.
6. Styling attributes are declared ignored rather than reported as gaps, and the reason is recorded so a later reader does not mistake exclusion for oversight.
7. An unrecognised element or attribute on a parsed object is reported in `unparsed.csv` as `unread_attribute` or `unread_element` with a count, and a test proves an unknown construct is reported rather than silently dropped.

## Tasks / Subtasks

- [x] Add the `cat` layer to `core/identifiers.py` and settle the path-joining collision (AC: #1, #2)
- [x] Decode catalog paths; build the on-disk object index (AC: #2)
- [x] Parse `sawd:dashboard` and `sawd:dashboardPage`; preserve page order (AC: #1, #5)
- [x] Resolve `sawd:reportRef[@path]` and `sawd:dashboardPageRef[@path]`; classify each outcome (AC: #3, #4)
- [x] Declare the styling exclusion in the adapter's consumed-attribute list (AC: #6)
- [x] Unread element and attribute reporting, with a test (AC: #7)

## Dev Notes

### The element is `sawd:reportRef`, not `sawd:report` (AC #3)

**The epic's Story 2.4 and its *Measured before planning* section both named `sawd:report[@path]`** — corrected 2026-08-20. Measured across the fixture, `sawd:report` occurs **zero** times. The element carrying 1722 `@path` references is **`sawd:reportRef`**. The counts were right; the element name was wrong.

Beware also that **`saw:reportRef` and `sawd:reportRef` are different elements** — report namespace and dashboard namespace — with 21 and 1722 occurrences. Match on namespace plus local name.

This is the second time on this project a construct has been searched for under a name it does not have. Story 1.6 records the first: `implicitFact` versus `defaultFactColumnRef`. Trust `catalog-xml-schema.md` from Story 2.2 over any name quoted in prose, this file included.

### Path resolution, measured (AC #3, #4)

4171 `@path` references were resolved against an index of every decoded on-disk path. Decoding is percent-decode plus `+`→space:

| Element | Total | Exact | Case-insensitive only | Unresolved |
|---|---:|---:|---:|---:|
| `sawd:reportRef` | 1722 | 0 | 1123 | 599 |
| `sawd:dashboardPageRef` | 1041 | 10 | 1028 | 3 |
| `sawd:globalFilterView` | 887 | 0 | 501 | 386 |
| `sawx:expr` | 417 | 0 | 222 | 195 |
| `sawd:scorecardViewRef` | 41 | 0 | 39 | 2 |
| `sawd:folderView` | 27 | 1 | 26 | 0 |
| `saw:reportRef` | 21 | 0 | 21 | 0 |
| `saw:catalogColumnRef` | 15 | 0 | 6 | 9 |
| **Total** | **4171** | **11** | **2966** | **1194** |

**Exact matching resolves 11 references out of 4171 — 0.3%.** Case-insensitive matching resolves 2966, or 71%.

Three separate rules are needed, and each was measured rather than assumed:

- **Strip the catalog root.** References are absolute from the catalog root — `/shared/05. Published Reporting/…` — while the fixture's tree begins one level below, at `05%2e+published+reporting/`. Strip the leading `/shared`.
- **Resolve relative references against the owning folder.** 1386 references are relative (`Exec - Income Stt`), overwhelmingly `sawd:dashboardPageRef` naming a sibling page of its own dashboard.
- **Percent-decoding is general, not a lookup table.** The epic gives `%2e` for `.` and `+` for space. The fixture also contains `co%6dponents` — `%6d` is `m`. Decode any `%XX`; do not table-match the two seen examples.

### Case normalisation is a decision, not a detail (AC #4)

The gap between 0.3% and 71% is entirely case. The on-disk tree is lowercased; the references keep display case. That is almost certainly an artifact of how this fixture was exported, not a property of OBIEE.

**AD-3 says Python never guesses, and AD-8 says name equality is not semantic equality.** Silently folding case to make 2955 references resolve is exactly the approximation those rules exist to stop — and on an estate that *does* distinguish case, it would join two different objects and nothing downstream would detect it.

Equally, refusing to fold case reports 99.7% of a real fixture as broken, which is not honest either.

**So resolve exactly first, fall back to case-insensitive, and record which happened per reference.** An `exact` and a `case_normalised` resolution are both usable; the difference stays visible, and an Operator on a case-sensitive estate can see at a glance whether the fallback is carrying their extraction. If a case-insensitive match is **ambiguous** — two on-disk objects differing only in case — that is not a resolution at all; record it as an error naming both candidates.

### The 1194 unresolved are mostly one absent root

| First path segment | Unresolved |
|---|---:|
| `company_shared` | 1161 |
| `shared` | 30 |
| relative | 3 |

**`/company_shared/` is a second catalog root that this fixture does not contain.** Those 1161 references are genuinely unresolvable here and must be recorded as such under AD-3 — not repaired, not suppressed. They are also the best available evidence that a partial catalog export is a normal state the tool will meet in the field, which is what Story 2.7's coverage report exists to make visible.

Only **33 references** are dangling within the content that is present. One is `/shared/03. Mobile/Mobility/Examples/m\/d linking_mob` — an escaped separator inside a name. Expect a small tail of genuinely malformed references, and record them with the offending string intact.

### The identifier collision (AC #1, #2)

`core/identifiers.py` today defines five layers — `phys`, `bmm`, `pres`, `sec`, `var` — and **`cat` is not among them**. AD-22 requires it. Add it.

Then `make_id` joins parts with `.`:

```python
return f"{rpd_id}{SEPARATOR}{layer}{SEPARATOR}{'.'.join(parts)}"
```

**Catalog path segments contain literal `.` characters** — `05. Published Reporting`, `1.00 general index` — and are `/`-separated. Joining them with `.` makes `parse_id` unable to recover the segments, and two different objects can produce one identifier.

Settle this in this story, because Stories 2.5, 2.6 and 2.7 all build on it. The options are to keep the decoded path whole as a single part with `/` separators intact, or to choose a segment separator that catalog names cannot contain. Whichever is chosen, `parse_id` must round-trip it, and a test must prove two objects whose names differ only by a `.` do not collide.

### References

- [Source: .../ARCHITECTURE-SPINE.md#AD-22, #AD-3, #AD-8, #AD-7]
- [Source: tools/rpd_extract/core/identifiers.py]
- [Source: documents/planning-artifacts/epics.md#Epic 2, Story 2.4]
- [Source: documents/implementation-artifacts/2-2-derive-the-observed-catalog-schema.md]

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Amelia, bmad-agent-dev)

### Debug Log References

### Completion Notes List

All seven ACs met. 111 Dashboards, 1036 pages, 3718 placements extracted from the fixture.

- **AC #1, #2 — the identifier collision, settled.** `cat` added to `core/identifiers.py`, and a catalog object passes its
  **whole decoded path as one part**, so the `/` separators survive and `parse_id` round-trips exactly. A test proves two
  objects differing only by a `.` do not collide. `make_id` now also refuses any part containing `::`, in every layer.
  Decoding is general: `+` to space first, then any `%XX` — `co%6dponents` decodes, and `a%2bb` stays `a+b`.
- **AC #3, #4 — resolution, exact first then case-folded, recorded per reference.** Measured: **11 of 4171 references resolve
  exactly and 2999 resolve only after folding case.** An ambiguous case-insensitive match is recorded as an error naming both
  candidates, never resolved. 1194 unresolved are kept as errors, not repaired — 1161 of them point into `/company_shared/`,
  a catalog root this fixture does not contain.
- **A finding that changed the resolver: `sawd:folderView[@path]` targets a folder, not an object.** Indexing files alone
  reported all 27 as dangling. Folders are now indexed too, and every resolution records `target_kind`, so a `reportRef`
  landing on a folder is a type mismatch rather than a silent hit.
- **AC #5:** page order preserved; `dashboard_pages.position` comes from the referencing Dashboard, filled in a later pass
  because a page is parsed before its Dashboard as often as after. A page no Dashboard references keeps an empty
  `dashboard_id` — a real state, distinct from one whose Dashboard was not understood.
- **AC #6:** styling excluded by the Story 2.2 rule and recorded as `excluded_by_scope` in `unparsed.csv`, not as gaps.
- **AC #7:** unknown elements and attributes reported, with tests for both.

The observing/audit machinery from `mds_xml.py` was extracted to `adapters/inbound/observing.py` so both adapters are audited
by **one** mechanism rather than two that can disagree. The RPD output was re-verified byte-identical after the move.

### File List

- `tools/rpd_extract/adapters/inbound/catalog_xml.py` (new)
- `tools/rpd_extract/adapters/inbound/observing.py` (new, extracted from `mds_xml.py`)
- `tools/rpd_extract/core/identifiers.py` (`cat` layer, `::` guard)
- `tools/rpd_extract/core/model.py` (`Dashboard`, `DashboardPage`, `DashboardContent`, resolution constants)
- `tools/rpd_extract/adapters/outbound/knowledge_base.py` (three tables)
- `tools/rpd_extract/tests/test_catalog.py`, `test_catalog_fixture.py`
