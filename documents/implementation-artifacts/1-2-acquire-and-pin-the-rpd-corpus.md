# Story 1.2: Acquire and Pin the RPD Corpus

Status: review — implementation complete. Corpus acquired, pinned, cleaned, and documented.

**Review intensity: Normal** — the corpus either parses or it does not, and errors surface immediately in Story 1.4. One exception deserves attention: the declared `rpd-id` values become permanent identifier prefixes under AD-7 and are expensive to change once anything cites them.

*Rewritten 2026-08-16. This story previously read "Produce a Reproducible RPD XML Export" and called for `biserverxmlgen`. Story 1.1 established that no OBIEE instance is obtainable, so no export can be produced. The corpus is acquired from pinned public sources instead. The story's purpose is unchanged: give the extractor a real, regenerable input that nobody made by hand.*

## Story

As an Operator,
I want the RPD corpus acquired at pinned commits, reduced to a clean loadable set, and documented well enough to rebuild from nothing,
so that the extractor has a real input, every run is reproducible, and a demo can point at one directory and load everything.

## Acceptance Criteria

1. Each source is pinned to an explicit commit SHA, with SHA, source URL, and acquisition date recorded.
2. The clean set contains only the `oracle/bi/server/base/**` XML trees; non-RPD content and `.git` directories are excluded.
3. Each source sits under its declared `rpd-id` as a lower-kebab directory name, declared by the Operator and not derived from filename, timestamp, or content hash (AD-7).
4. Every source has an identical internal layout, so one directory path reaches all of them.
5. The corpus manifest is CSV, produced by the Story 1.3 writer rather than by hand, listing `rpd-id`, origin, commit SHA, acquisition date, and object counts by type (FR-27).
6. The procedure lets a reader rebuild the corpus from nothing, and records why the corpus is kept outside the repository.
7. No credentials appear in the procedure (NFR11).
8. Personal names in Source B are stated explicitly so derived artifacts are reviewed before leaving the team.

## Tasks / Subtasks

- [x] Acquire and pin both sources (AC: #1)
- [x] Build the clean set (AC: #2, #4)
- [x] Declare `rpd-id` values (AC: #3)
- [x] Generate the manifest with the Story 1.3 writer (AC: #5)
- [x] Document the rebuild procedure (AC: #6, #7)
- [x] Record the personal-data caveat (AC: #8)

## Dev Notes

**Deliverables are Operator artifacts, not product code.** Nothing under `tools/` changed. The corpus itself lives outside the repository; only the manifest and the documentation are committed.

**Layout is the contract with Story 1.4.** A loader walks `clean/*/oracle/bi/server/base/*/*.xml` and derives each file's `rpd-id` from the path segment directly beneath `clean/`. That satisfies the demo requirement — one path loads everything — without the CLI needing per-source configuration. It does **not** weaken FR-9: the argument names a corpus root, never a Dashboard or Subject Area scope.

**`rpd-id` is the one expensive decision here.** Per AD-7 these values prefix every Knowledge Base identifier as `<rpd-id>::<layer>::<object-path>`, and every Group Spec and Parity Check citation uses the qualified form. Changing one later invalidates every citation. Declared: `bi-analytics-2013` and `sampleapp`.

### Project Structure Notes

Writes `estate/test-corpus/corpus.md` and `estate/test-corpus/corpus-manifest.csv`. Both are Operator-owned per the AD-18 declaration made in Story 1.1. No `estate/knowledge-base/` content is written — AD-2 reserves that for the extractor, and Story 1.4 creates it.

### References

- [Source: documents/planning-artifacts/architecture/architecture-POC-RPD-2026-08-15/ARCHITECTURE-SPINE.md#AD-7] — Operator-declared `rpd-id`, never derived
- [Source: .../ARCHITECTURE-SPINE.md#AD-16] — deployment is a file copy; the corpus is not part of the deliverable
- [Source: .../ARCHITECTURE-SPINE.md#AD-19] — adapters tested against captured samples, never a live instance
- [Source: documents/planning-artifacts/prds/prd-POC-RPD-2026-08-15/prd.md#FR-27] — Tabular Artifacts as CSV
- [Source: documents/planning-artifacts/prds/prd-POC-RPD-2026-08-15/prd.md#8.2 Data] — NFR11, no embedded credentials
- [Source: estate/test-corpus/environment.md] — Story 1.1's availability finding and FR-4 coverage measurement
- [Source: documents/planning-artifacts/epics.md#Story 1.2] — acceptance criteria

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context)

### Completion Notes List

**All eight acceptance criteria met.**

- **AC #1.** Pinned: `bi-analytics-2013` at `19bef42a9574a039a90a40d986c10194aa3376f5` (2013-10-08, 1252 XML), `sampleapp` at `9a1c0a28211d981f320e38247b416c754c334398` (2014-07-30, 131 XML).
- **AC #2.** Clean set verified: **1383 XML files, 0 non-XML.** The raw `obiee` clone carries a Java project, an `.ear`, and a `.jdb` database file; none reach the clean set.
- **AC #3.** `rpd-id` values declared by the Operator, lower-kebab, recorded in `corpus.md` with an explicit note that they are permanent identifier prefixes.
- **AC #4.** Both sources have identical internal layout, so `clean/` alone reaches everything and the path segment beneath it *is* the `rpd-id`.
- **AC #5.** `estate/test-corpus/corpus-manifest.csv` — 40 rows, 1383 objects — written by the Story 1.3 writer and read back byte-equal. `commit_sha` is declared a guarded column, since an all-digit SHA would otherwise be coerced by a spreadsheet.
- **AC #6, #7.** `estate/test-corpus/corpus.md` gives exact clone-and-checkout commands plus the clean-set build, with two verification counts. Both sources are public; no credentials involved.
- **AC #8.** Personal names recorded (`Iryna_Bradzetskaya_MT_Full`, `Anton_Tserakhau`), with the recommendation to prefer the `sampleapp` source for anything shown outside the team.

**The manifest is the first real use of the Story 1.3 writer.** It produced correct output on genuine data and round-tripped byte-equal, which is stronger evidence than the synthetic test corpus alone.

**Note for Story 1.4.** Expect a corpus-root argument pointing at `clean/`, with `rpd-id` read from the path rather than passed per source. That keeps the demo to one path while still honouring AD-7's "declared, not derived" rule — the declaration lives in the directory name, authored by the Operator in this story.

**Still open, carried from Story 1.1 and not addressed here:** the format decision (MDS XML versus the single-file `biserverxmlgen` export that FR-1 and PRD §4.1 assume) is for Winston before Story 1.4 starts. The corpus being MDS XML makes it urgent rather than theoretical.

### File List

- `estate/test-corpus/corpus.md` (created)
- `estate/test-corpus/corpus-manifest.csv` (created)
- `documents/planning-artifacts/epics.md` (Story 1.2 rewritten)
- `documents/implementation-artifacts/1-2-acquire-and-pin-the-rpd-corpus.md` (renamed from `1-2-produce-a-reproducible-rpd-xml-export.md`)
- `~/Documents/Garage/obiee-corpus/` (outside the repository — clones, pins, and the clean set)
