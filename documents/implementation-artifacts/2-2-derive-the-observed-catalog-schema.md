# Story 2.2: Derive the Observed Catalog Schema

Status: review

**Review intensity: High** — every later story is written against this document, and a wrong entry propagates into acceptance criteria.

## Story

As a developer,
I want the catalog's element and attribute vocabulary derived by parsing every fixture file,
so that the adapter is written against observed structure rather than assumed structure.

## Acceptance Criteria

1. `estate/test-corpus/catalog-xml-schema.md` records element paths and attributes per object type, with occurrence counts, derived by parsing all 5371 fixture files.
2. The `xmlVersion` spread is recorded per object type, **including objects that declare no version**, and any element or attribute appearing under some versions but not others is identified.
3. Styling and formatting attributes are listed separately from structural ones, the document states that styling is out of scope per FR-34, and **the membership rule for "styling" is stated explicitly** rather than left to the reader.
4. The document states that it records what was **observed**, never what exists, and an unrecognised construct is handled per AD-3 rather than assumed absent.
5. Root element types that belong to other products — BI Publisher and raw data exports — are identified as such, so that a later reader does not mistake them for catalog constructs the adapter failed to model.
6. Every element that carries a `@path` reference is listed with its count, because path resolution is Story 2.4's central mechanic and the reference vocabulary is larger than `sawd:reportRef` alone.

## Tasks / Subtasks

- [x] Write the deriving script; parse every file, count elements, attributes and `xsi:type` values (AC: #1)
- [x] Record version spread per object type, absence included (AC: #2)
- [x] Define and apply the styling membership rule; report both populations (AC: #3)
- [x] Classify the 59 root types by product (AC: #5)
- [x] Enumerate `@path`-carrying elements (AC: #6)
- [x] Write `catalog-xml-schema.md` with the observed-not-exhaustive statement (AC: #4)

## Dev Notes

**Writer: Operator.** `estate/test-corpus/` has one writer (AD-18). This is the catalog counterpart of `mds-xml-schema.md`, which Story 1.6 proved is worth trusting over any grep.

### Measured 2026-08-20, whole fixture

- **618 distinct attribute names**, 572,357 occurrences.
- **59 distinct root element types**, of which 4341 files parse and 1030 do not.
- Three `xmlVersion` values on roots; 1643 roots carry none.

### The styling boundary needs defining, not inheriting (AC #3)

The epic stated styling as *"94,796 attribute occurrences across 35 distinct names, against 660 distinct non-styling attributes"* — flagged there as unreconciled on 2026-08-20. A broader sweep — anything whose name contains `wraptext`, `padding`, `border`, `fmt`, `font`, `color`, `width`, `height`, `align`, `style`, `bgcolor`, `indent`, `format` — gives **60 distinct names and 112,100 occurrences**, against 618 distinct attributes in total.

These do not reconcile, and 35 + 660 = 695 exceeds the 618 attributes that exist. The two counts are answering different questions, and neither wrote its question down.

**So this story's job is to fix the definition before counting.** The largest members are unambiguous:

| Attribute | Occurrences |
|---|---|
| `wrapText` | 14,060 |
| `fmt` | 12,124 |
| `fontSize` | 7,190 |
| `width` | 6,033 |
| `borderPosition` | 5,551 |
| `color` | 5,306 |
| `fontColor` | 4,848 |
| `lineStyle` | 4,536 |
| `paddingTop` | 4,262 |

The judgement calls sit at the edge — `width` on a table column is layout, `width` on a map viewport may not be. Decide each edge case explicitly and record the decision beside the name. An attribute excluded from the audit by a rule nobody wrote down is indistinguishable from one that was overlooked, which is the failure FR-34's exclusion is supposed to be safe from.

### Root types belong to three products, not one (AC #5)

| Root | Count | What it is |
|---|---|---|
| `xmlp:dataModel` | 162 | BI Publisher data model |
| `xmlp:report` | 156 | BI Publisher report |
| `oxp/config:config` | 85 | BI Publisher configuration |
| `DATA_DS` | 86 | Raw sample data |
| `data` | 22 | Raw sample data |
| `ROWSET` | 14 | Raw sample data |

**BI Publisher is a different product sharing the catalog tree.** Its objects are not OBIEE Analyses and the adapter does not model them. Story 2.7 reports them as unmodelled types; this document is where a reader learns they are a separate product rather than a gap in coverage.

### The `@path` reference vocabulary (AC #6)

| Element | With `@path` |
|---|---|
| `sawd:reportRef` | 1722 |
| `sawd:dashboardPageRef` | 1041 |
| `sawd:globalFilterView` | 887 |
| `sawx:expr` | 417 |
| `oxp/config:truetype` | 312 |
| `sawd:scorecardViewRef` | 41 |
| `sawbsc:perspectiveRef` | 32 |
| `sawd:folderView` | 27 |
| `saw:reportRef` | 21 |
| `saw:catalogColumnRef` | 15 |

**Note `saw:reportRef` and `sawd:reportRef` are different elements in different namespaces**, both carrying `@path`. Record the namespace, not just the local name. `oxp/config:truetype[@path]` is a font file path in a BI Publisher config — a reminder that `@path` alone does not mean *catalog reference*.

### The `xsi:type` axis matters as much as the element name

Type carries meaning the element name does not:

| `xsi:type` | Occurrences |
|---|---|
| `sawx:sqlExpression` | 14,771 |
| `saw:regularColumn` | 10,606 |
| `sawx:comparison` | 2,173 |
| `saw:simpleCriteria` | 1,680 |
| `sawx:special` | 1,608 |
| `sawx:columnRefExpr` | 1,280 |
| `sawx:savedFilter` | 417 |
| `sawx:eval` | 360 |

A schema recorded by element name alone would miss that a saved-filter reference and a SQL expression are **the same element**, distinguished only by type. Record type as a first-class axis.

### References

- [Source: estate/test-corpus/mds-xml-schema.md] — the shape to follow
- [Source: documents/planning-artifacts/epics.md#Epic 2 — Measured before planning]
- [Source: .../ARCHITECTURE-SPINE.md#AD-3, #AD-18, #AD-21]
- [Source: prd.md#FR-34]

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Amelia, bmad-agent-dev)

### Debug Log References

### Completion Notes List

All six ACs met. `estate/test-corpus/catalog-xml-schema.md` written, derived by parsing all 5371 files.

- **AC #1:** element paths and attributes per object type with occurrence counts, for the four modelled types in full and the
  whole vocabulary via `--section vocabulary`.
- **AC #2:** version spread per object type. **Only `saw:report` carries more than one version**, so drift is measurable for
  Analyses and nothing else — and most apparent drift is sampling (766 constructs "absent" from a 103-object population
  against a 1504-object one). The document reports the direction sampling *cannot* explain: **15 constructs present only in
  the versionless Analyses**, including `saw:paSimpleColumnFormula`.
- **AC #3 — the membership rule, defined before counting.** 13 name substrings, plus **ten exceptions each decided by reading
  the values the attribute carries**. The decisive one: **`fmt` (12,124 occurrences) takes only `text` and `html`** — whether
  cell content is interpreted as markup or shown literally. FR-34 puts *displayed data* on the defect side, so `fmt` is
  **structural**, not styling. Result: **50 styling names / 97,498 occurrences against 568 / 474,859** — and both partitions
  reconcile to 618 / 572,357, which the epic's two earlier counts could not.
  Two exclusions carry recorded caveats: 138 `style` values are `display:none` and 565 `height` values are `0`, and hidden
  content is a column-set difference rather than a visual one.
- **AC #4:** the observed-not-exhaustive statement leads the document, with AD-3 named.
- **AC #5:** roots classified by namespace into OBIEE (25 types, 3772 files), BI Publisher (4, 404), no-namespace raw data and
  business documents (28, 161), XSLT and Adobe form data (2, 4) — 59 types and 4341 files, summing exactly.
- **AC #6:** all 14 `@path`-carrying elements listed with counts and namespaces, with the three warnings a resolver needs.

Two findings the derivation produced that later stories depended on: **`sawd:folderView` targets folders, not objects**
(a file-only index reports all 27 as dangling), and **40 of 67 `subjectArea` values are `XSA(...)` uploaded datasets**, not
Subject Areas — which bears directly on FR-7.

### File List

- `estate/test-corpus/catalog-xml-schema.md` (new)
- `tools/catalog_survey.py` (styling rule, product classification, version drift, vocabulary sections)
