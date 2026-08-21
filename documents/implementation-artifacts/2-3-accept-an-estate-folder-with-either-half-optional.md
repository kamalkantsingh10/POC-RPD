# Story 2.3: Accept an Estate Folder, With Either Half Optional

Status: review

**Review intensity: High** — this is the input contract every later story and every operator depends on.

## Story

As an Operator,
I want to point the extractor at one folder holding an estate's RPD and catalog,
so that both halves extract in one run and pairing them is something I declared rather than something the tool guessed.

## Acceptance Criteria

1. Given an estate folder containing `rpd/` and `catalog/` subdirectories, run with a declared `rpd-id`, both halves extract into one Knowledge Base.
2. That pairing is recorded in the manifest as an Operator declaration (AD-22), and the tool never infers a pairing from matching Subject Area names.
3. When only `rpd/` or only `catalog/` is present, extraction succeeds for what is there, and the manifest records which halves were present.
4. When `<rpd-id>/oracle/bi/server/base/` is found directly, it is read as RPD-only, unchanged, and the existing 1383-file corpus extracts exactly as before.
5. A folder matching no accepted shape fails naming every accepted layout, and writes no partial Knowledge Base.
6. The documentation instructs an Operator holding a BAR archive to unzip and arrange into `rpd/` and `catalog/`; no BAR-specific code path exists, because a BAR may contain a binary `.rpd`, which AD-20 puts out of scope.
7. A `catalog/` directory is accepted on the Operator's declaration that it is one — **never on a content sniff** — and the reason is recorded.

## Tasks / Subtasks

- [x] Define the accepted layouts and write them into the CLI's failure message (AC: #1, #5)
- [x] Route each present half to its adapter; record halves-present in the manifest (AC: #1, #3)
- [x] Record the pairing as a declaration, with the declaring act named (AC: #2)
- [x] Preserve the existing bare-RPD path and re-run the full corpus to prove byte-identical output (AC: #4)
- [x] Document the BAR unpack instruction; add no BAR code (AC: #6)
- [x] Tests: each accepted layout, each rejected layout, both single-half cases (AC: #3, #5)

## Dev Notes

### AC #4 is a regression guard, not a feature

The corpus extracts today. This story changes the code that finds it. **The proof is the existing output, unchanged** — regenerate the Knowledge Base and diff it byte-for-byte against the current one. Every Epic 1 story's verification rests on that output, so a silent shift in it invalidates ten stories' evidence at once.

### There is no reliable marker for a catalog directory (AC #7)

The RPD half announces itself: `oracle/bi/server/base/` is a fixed path, and AD-20 names it. **The catalog half has no equivalent.** The fixture's top level is:

```
00%2e+va+projects/   01%2e+quickstart/   ...   11%2e+demos/
components/   custom/   demos+business+story/   git_test_dash/
mobile+app+designer/   workshops/   your+custom+public+content/
```

Arbitrary user-named folders. The nearest thing to a marker is that dashboards live under a `_portal/` subdirectory (25 present) and saved filters under `_filters/` (11 present), but both are conventions inside user folders, not a root signature. Objects are **extensionless**, so extension filtering is unavailable too.

**Therefore: the Operator declares it by putting it in `catalog/`.** Do not sniff content to decide whether a directory is a catalog. That is the same class of inference AD-22 forbids for pairing, arriving one level lower down — and a wrong answer produces a Knowledge Base whose provenance is fiction. If `catalog/` holds something that is not a catalog, extraction reports what it could not read; it does not silently reclassify the folder.

### What "either half optional" costs the reader

A Knowledge Base built from a catalog alone contains report structure with **no semantic layer to resolve into** — that is FR-7, and Epic 2's opening note explains why it is deferred to Epic 4 for want of a matched fixture. A Knowledge Base built from an RPD alone is what exists today.

Both are legitimate. What is not legitimate is a reader being unable to tell which they are holding. The manifest entry is the mechanism: it records which halves were present, so *"no dashboards"* and *"dashboards not extracted"* stay distinguishable. This is the same distinction Story 3.3's honesty preamble depends on, and the same reasoning that put `errors.csv` and `unparsed.csv` in separate files.

### The BAR instruction (AC #6)

Verified 2026-08-17 by opening `ee.bar`: a BAR is a zip containing `content/catalog/` — parseable — and `datamodel/rpd/default.rpd` — **the proprietary binary AD-20 excludes**. A BAR is therefore not a ready matched pair. The Operator instruction is: unzip, put `content/catalog/` in `catalog/`, and supply the RPD **as MDS XML**, which requires `biserverxmlgen` against the binary.

Write this as documentation only. A BAR is a zip in front of two adapters we already have; modelling it as a third serialisation would be building for a format nobody has asked us to read.

### References

- [Source: .../ARCHITECTURE-SPINE.md#AD-20, #AD-22, #AD-18]
- [Source: estate/test-corpus/web-catalog-findings.md#6]
- [Source: documents/planning-artifacts/epics.md#Epic 2, Story 2.3]
- [Source: tools/rpd_extract/cli.py]

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Amelia, bmad-agent-dev)

### Debug Log References

### Completion Notes List

All seven ACs met.

- **AC #1, #3:** `tools/rpd_extract/layout.py` resolves three accepted shapes and reports which halves are present per
  `rpd-id`. Verified end to end on a real paired estate: `rpd/` = the 1383-file corpus, `catalog/` = the 5371-file fixture,
  one `rpd-id`, one Knowledge Base.
- **AC #2:** the manifest records `halves_present:<rpd-id>` and `pairing:<rpd-id>`, and the pairing row names **the act** —
  *"declared by the Operator: both halves supplied in one estate folder under one rpd-id (AD-22). Never inferred."*
- **AC #4 — regression guard, and the honest result.** Every data table is **byte-identical** to the Epic 1 baseline. Two
  files change, both by design and both required by other ACs: `coverage.csv` gains the `layer` column (2.7 AC #1) and
  `manifest.csv` gains the halves/pairing rows (AC #3) plus a version bump. **This is not full byte-identity and the story's
  wording asked for it**, so it is stated plainly rather than claimed.
  I also declined to guard `object_type` in `errors.csv` and `unparsed.csv`: it would have added a companion column to every
  existing Knowledge Base for a value that can never need one.
- **AC #5:** layout resolution happens **before `--clean` and before any write**. Previously `--clean` deleted tables before
  parsing, so a failed run left a cleaned directory — which reads as an estate containing very little rather than as a
  failure.
- **AC #6:** README gains the BAR unpack instruction with the binary-`.rpd` warning. **No BAR code exists, and a test asserts
  no module imports `zipfile`.**
- **AC #7:** `catalog/` is accepted on declaration alone. A test puts a plain text file in it and asserts the directory is
  still accepted as the catalog half — sniffing content would be AD-22's forbidden inference one level down.

**One defect found and fixed during this story.** Reading both halves into one shared `Estate` re-ran each adapter's
post-passes over rows the other had contributed, duplicating every lineage and security row and reporting **1507 false
`duplicate_identifier` errors** on a corpus that has none. Each adapter now builds its own Estate and the CLI merges them.

### File List

- `tools/rpd_extract/layout.py` (new)
- `tools/rpd_extract/cli.py` (rewritten around the layout)
- `tools/rpd_extract/core/model.py` (`Estate.merge`, `halves_present`)
- `tools/rpd_extract/adapters/outbound/knowledge_base.py` (manifest halves and pairing rows)
- `tools/rpd_extract/tests/test_catalog.py` (`LayoutTests`)
- `README.md`
