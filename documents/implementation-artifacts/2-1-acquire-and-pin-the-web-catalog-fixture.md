# Story 2.1: Acquire and Pin the Web Catalog Fixture

Status: review

**Review intensity: Normal** — errors surface immediately in 2.4.

## Story

As an Operator,
I want the Web Catalog test fixture acquired at a pinned commit and documented,
so that catalog extraction is developed against real content and every run is reproducible.

## Acceptance Criteria

1. The fixture is pinned to commit `5266344cbf9f319c86cad5718eb456c0a9b290a6`, and its source URL, acquisition date and object counts are recorded in `corpus-manifest.csv` alongside the two RPD sources.
2. The record states plainly that the tool targets any OBIEE estate and this corpus is one sample — the same position the RPD corpus takes.
3. The `xmlVersion` values present are recorded **with their measured spread**, including how many objects carry no `xmlVersion` at all, as evidence that no single catalog schema exists.
4. The fixture lives outside the repository, like the RPD corpus, and the licensing position is recorded rather than assumed.
5. The absence of `.atr` files — and therefore of permissions, ACLs and ownership — is stated explicitly.
6. The count that **1030 of 5371 files are not XML at all** is recorded, because every later story must distinguish "not a catalog object" from "failed to parse".
7. The corrected counts already recorded in `web-catalog-findings.md` §2 and §4 are **re-derived independently** and confirmed, rather than copied forward, because they were wrong once already.

## Tasks / Subtasks

- [x] Verify the clone is at the pinned commit and record the manifest rows (AC: #1)
- [x] Record object counts by root element, from a parse, not a grep (AC: #1, #3)
- [x] Record the non-XML file population and what those files are (AC: #6)
- [x] Record licensing position, `.atr` absence, and the fixture-not-target statement (AC: #2, #4, #5)
- [x] Re-derive and confirm the corrected counts in `web-catalog-findings.md` (AC: #7)

## Dev Notes

**Writer: Operator.** `estate/test-corpus/` has one writer (AD-18).

The clone is already present at `~/Documents/Garage/obiee-corpus/obiee_sample_git`, at the pinned commit, dated 2019-08-06. 5371 files, 420 MB expanded. Nothing needs acquiring; this story records what is there, correctly.

### Measured 2026-08-20 — parse every file, count root elements

| Root element | Count |
|---|---|
| `saw:report` (Analyses) | 1607 |
| `sawd:dashboardPage` | 1036 |
| `saw:view` | 530 |
| `saw:action` | 115 |
| `sawd:dashboard` | 111 |
| `sawsf:savedFilterObject` | 96 |
| `sawkpi:kpi` | 47 |
| `sawbsc:objective` | 73 |
| `sawbsc:perspective` | 32 |
| `sawbsc:initiative` | 20 |

**59 distinct root element types in total.** 4341 files parse as XML; **1030 do not.**

### The stale counts, corrected 2026-08-20 (AC #7)

`web-catalog-findings.md` §2 recorded these same object types at **1108 / 854 / 355 / 101 / 77 / 58** — understated by roughly a third across every type. **The document has been corrected**, with the correction dated and the original figures kept visible so a reader meeting the old numbers elsewhere can tell what happened.

The same undercount had reached the architecture: **AD-21 recorded `saw:columnFormula` as "verified across 409 expressions"** against a measured 10,866. AD-21's *rule* was unaffected — the catalog still stores exactly one representation, so there is nothing to choose between — but the evidence line was off by a factor of 26. **Also corrected 2026-08-20.**

Both figures look like a survey over a subdirectory rather than the tree. This is the third time a grep or partial scan has misreported shape on this project, which is why AC #7 asks for an independent re-derivation rather than a copy: a corrected number that nobody re-measured is still a number nobody measured.

### The 1030 non-XML files (AC #6)

Catalog objects are **extensionless** — there is no suffix to filter on. The non-XML population is BI Publisher material living inside `*.xdo` folders: `.rtf` templates, `.png` previews, plus `.gitignore` at the root. They are not catalog objects and are not damaged objects.

This matters now rather than in Story 2.7 because it changes what "failed to parse" means. An extractor that reports 1030 parse errors has buried the real signal; one that skips them silently has done the thing this project exists to prevent. Story 2.7 owns the reporting; this story owns recording that the population exists and is 19% of the tree.

### `xmlVersion` is not always present (AC #3)

| Value | Roots carrying it |
|---|---|
| `201201160` | 1504 |
| `200810300` | 1147 |
| `201106170` | 47 |
| **none** | **1643** |

A fourth value, `200811100`, occurs exactly **once**, on a nested element, never on a root.

**The epic said "four distinct `xmlVersion` values"** — corrected 2026-08-20. On roots there are three. The fourth exists only if nested elements are counted. Either statement can be defended; neither should be made without saying which was counted. The important finding is the one nobody recorded: **38% of parseable roots declare no version at all**, including 103 `saw:report` roots. Any design that keys behaviour off `xmlVersion` must handle its absence as the **most common case of all** — 1643 roots against 1504 for the largest declared value. *(This line read "second most common" until 2026-08-20; the 38% was right, the ranking was not.)*

### Licensing and `.atr` (AC #4, #5)

Same position as the RPD corpus: unlicensed Oracle SampleApp content, stored outside the repository, acquired from a pinned commit rather than copied in. `.gitignore` already covers `/corpus/` and `/obiee-corpus/`.

No `.atr` files are present. Content is intact; **access control is absent entirely**. Whoever reads the catalog half of a Knowledge Base built from this fixture cannot learn who could see what, and the record must say so rather than leave the reader to infer it from silence.

### References

- [Source: estate/test-corpus/web-catalog-findings.md#2, #4]
- [Source: documents/planning-artifacts/epics.md#Epic 2 — Measured before planning]
- [Source: .../ARCHITECTURE-SPINE.md#AD-18, #AD-21, #AD-22]
- [Source: documents/implementation-artifacts/1-2-acquire-and-pin-the-rpd-corpus.md]

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Amelia, bmad-agent-dev)

### Debug Log References

### Completion Notes List

All seven ACs met. The re-derivation asked for by AC #7 **found three errors in the figures it was checking**, which is the
point of asking for it.

- **`tools/catalog_survey.py`** added: a committed, re-runnable measurement tool. Every catalog figure in every document is
  now reproducible by one command. The three wrong numbers this project has carried all came from surveys nobody could re-run.
- **AC #1, #2:** 60 rows added to `corpus-manifest.csv` under `rpd_id` `sampleapp-v607` — 59 root-element types plus one
  `(not XML)` row, **summing to exactly 5371**. The fixture-not-target statement and the licensing position are in
  `web-catalog-findings.md` §7.
- **AC #3, #5, #6:** version spread confirmed (1504 / 1147 / 47 / **1643 none**), `.atr` absence stated explicitly, 1030
  non-XML files recorded.
- **AC #7 — corrected counts confirmed, three new errors found:**
  1. **The 1030 non-XML files are ten formats, not two.** The record said "`.rtf` templates and `.png` previews inside
     `.xdo` folders". Measured by leading bytes: 561 PNG, 182 ZIP, 112 RTF, 58 OLE, 53 JPEG, 12 PDF, 6 GIF, 6 Flash, 17
     `data:` URIs, 23 unrecognised — and only 439 sit in a BI Publisher folder. The original claim was measured against raw
     on-disk names, where the folder is `sales+history+report%2exdo`; a `.xdo` suffix test finds nothing and returns zero.
     **Membership must be tested on the decoded path.**
  2. **`xmlp:dataModel` names nothing.** Both BI Publisher roots use their namespace as a *default* namespace and declare no
     prefix. Keying on rendered names also splits `sawbsc:kpiWatchlistView` into two types and reports 60 where 59 exist.
     Identity is namespace URI plus local name.
  3. **Absence of `xmlVersion` is the *most* common state (1643), not the second** — corrected in this file, Story 2.7, the
     epic and `catalog-xml-schema.md`.

Every corrected count from 2026-08-20 survived: 5371 / 4341 / 1030 / 59 roots / 1607 / 1036 / 530 / 115 / 111 / 96 / 10,866
`columnFormula` / 618 attributes / 572,357 occurrences.

### File List

- `tools/catalog_survey.py` (new)
- `estate/test-corpus/corpus-manifest.csv` (60 rows added)
- `estate/test-corpus/web-catalog-findings.md` (§2 corrected, §7 added)
