# Story 1.3: Spreadsheet-Safe CSV Writer with a Verbatim-Text Guarantee

Status: review — implementation complete, 23/23 tests passing. **AC #4's manual spreadsheet round trip is outstanding.**

**Review intensity: Keen** — this story settles the FR-2 / FR-28 conflict and fixes the format every later CSV inherits. A wrong guard voids the verbatim claim silently: the tests still pass, the files still open, and the damage only appears when a reviewer checks a formula against the RPD. It is also expensive to reverse once tables exist. AC #8 requires the Operator's explicit decision for exactly this reason.

## Story

As an Operator,
I want every CSV the tool writes to survive being opened in a spreadsheet without altering a single character of OBIEE formula text,
so that the Knowledge Base's central claim — logic captured exactly as written — holds in the tool people will actually open it with.

## Acceptance Criteria

1. Every table written is UTF-8, comma-delimited, LF line endings, one header row, every field quoted.
2. A field value beginning `=`, `+`, `-`, or `@` is not interpreted as a formula when opened in a spreadsheet application, and the guard applied is documented and machine-reversible.
3. A value guarded on write is recovered byte-for-byte when read back by the tool.
4. A corpus of real OBIEE formula text containing embedded commas, double quotes, and newlines survives write → open in a spreadsheet → save → re-read with every value equal to the original (FR-28).
5. Identifier-like values such as `00123` and `1E5` keep their leading zeros and do not convert to scientific notation when opened in a spreadsheet.
6. The writer uses only the Python standard library and imports no third-party package (NFR13, FR-23).
7. The writer lives under `tools/rpd_extract/adapters/outbound/` and nothing in `tools/rpd_extract/core/` imports it (AD-15).
8. The FR-2 / FR-28 guard decision and its rationale are recorded in the repository, and the approach is confirmed with the Operator rather than decided unattended.

## Tasks / Subtasks

- [ ] **Settle the guard decision with the Operator before writing the writer** (AC: #2, #8)
  - [ ] Read "The central conflict" in Dev Notes.
  - [ ] Present the options and the recommendation to the Operator; get an explicit decision.
  - [ ] Record the decision, the rejected options, and the reasoning in `documents/planning-artifacts/decisions/csv-formula-guard.md`.
  - [ ] **Do not proceed past this task unattended.** AC #8 exists because a wrong default here silently voids FR-2, which is the claim the entire Phase 0 demo rests on.
- [ ] Implement the writer (AC: #1, #6, #7)
  - [ ] Create `tools/rpd_extract/adapters/outbound/csv_writer.py`.
  - [ ] Write a header row plus rows in caller-supplied order. **Never reorder rows or columns** — ordering is the caller's contract (Story 1.4 owns determinism of content; this writer must not perturb it).
  - [ ] Apply the agreed guard to affected fields only.
  - [ ] Provide the matching reader used by AC #3 verification and by later stories that read Knowledge Base tables back.
- [ ] Build the round-trip test corpus (AC: #4, #5)
  - [ ] Use the real OBIEE formula samples captured in Story 1.2 (`estate/test-corpus/formula-samples.txt`).
  - [ ] Ensure coverage of: embedded comma, embedded double quote, embedded newline, leading `-`, leading `=`, leading `+`, leading `@`, `00123`, `1E5`, non-ASCII text, empty string.
  - [ ] If Story 1.2 found no real sample of a given shape, construct one and mark it as constructed rather than observed.
- [ ] Test (AC: #3, #4, #5)
  - [ ] Automated: `unittest` covering write → read for every corpus value, asserting byte equality.
  - [ ] Automated: assert output bytes are UTF-8, LF-terminated, and that every field is quoted.
  - [ ] Manual, once: open the produced CSV in a spreadsheet application, save, re-read, confirm equality. Record the application and version used in the decision document. This step is manual by design — see the LibreOffice warning in Dev Notes.
- [ ] Record the decision (AC: #8)
  - [ ] Finalise `documents/planning-artifacts/decisions/csv-formula-guard.md` with the manual verification result.

## Dev Notes

**First code in the project.** Nothing exists under `tools/` yet. Create only what this story needs: the outbound adapter package and its tests. Do **not** create `core/`, `adapters/inbound/`, or `cli.py` — Story 1.4 owns those, and creating empty scaffolding now violates the incremental principle and AD-16's no-build-step stance.

### The central conflict

**FR-2 requires formula text stored character-for-character. FR-28 requires the file to survive a spreadsheet.** These genuinely collide, and the collision is not theoretical: OBIEE formulas can begin with `-` (negation) or `+`, and Excel evaluates leading-`=`/`-`/`+`/`@` fields as formulas *even when quoted*.

Worse, and easy to miss: **the same problem extends past the four punctuation characters.** Excel coerces `00123` to `123` and `1E5` to `100000` regardless of quoting. AC #5 is therefore part of the same decision, not a separate concern. Any guard chosen must cover numeric-looking identifiers too.

Options:

| Option | Spreadsheet-safe | Bytes on disk | Verdict |
|---|---|---|---|
| Quoting alone (`QUOTE_ALL`) | No — Excel still evaluates | Verbatim | Fails FR-28 |
| Leading apostrophe on affected fields | Yes | Altered | Viable if reversal is deterministic |
| Leading tab on affected fields | Partially; brittle across applications | Altered | Weaker than apostrophe |
| Guard + explicit `*_guarded` flag column | Yes | Altered, but self-describing | **Recommended** |

**Recommendation:** guard only affected fields with a single leading `'`, and emit a companion boolean column (e.g. `formula_guarded`) alongside any column that can carry guarded content. The reader strips exactly one leading apostrophe when the flag is true. This makes reversal deterministic rather than heuristic, and satisfies AD-5 (every artifact self-describing) because a reader can tell guarded from unguarded content without out-of-band knowledge. Record the guard policy in the Knowledge Base manifest as well, once Story 1.4 creates it.

Frame the FR-2 claim honestly in the decision document: **the stored logical value is verbatim and recoverable byte-for-byte; the on-disk representation carries a reversible, declared guard.** Do not claim the file bytes are unaltered when they are — the product's own NFR7 makes honesty about limitations non-negotiable, and this artifact is the one a sceptical reviewer will poke at.

### Standard library specifics

Python `>=3.11`, floor only, no upper pin. `csv` is stdlib — no dependency is added by this story, which is what makes FR-23's offline no-admin install structurally satisfied rather than engineered around.

Three defaults in the `csv` module will silently violate the Spine's conventions if left alone:

- **`lineterminator` defaults to `\r\n`.** The convention requires LF. Set `lineterminator="\n"` explicitly.
- **The file must be opened with `newline=""`.** Otherwise the platform's newline translation corrupts embedded newlines inside quoted fields — which is exactly AC #4's case.
- **`quoting` defaults to `QUOTE_MINIMAL`.** The convention requires every field quoted. Set `quoting=csv.QUOTE_ALL`.

So: `open(path, "w", encoding="utf-8", newline="")` and `csv.writer(fh, quoting=csv.QUOTE_ALL, lineterminator="\n")`.

**Do not add a UTF-8 BOM** (`utf-8-sig`) without raising it as part of the AC #8 decision. A BOM helps Excel detect encoding but changes the file's first bytes and contaminates the first header field name when read by anything that does not strip it. If non-ASCII content in SampleApp makes a BOM necessary, that is a decision to record, not a default to apply.

### Testing standards

**`unittest` from the standard library. Not pytest.** The Architecture Spine's stack table reads "Python third-party packages | none, at any version" — that includes test dependencies. A dev agent's instinct here is pytest; resisting it is a requirement, not a preference.

AD-19 requires the core to be testable directly because it performs no I/O. This story's writer *is* I/O, so test it against a temp directory (`tempfile`, stdlib) rather than a live anything. No test in this project ever requires a running OBIEE instance.

### ⚠️ LibreOffice and pandoc are installed on this machine — do not touch them

NFR15 excludes `pandoc`, `LibreOffice`, `python-docx`, and `openpyxl` explicitly, and the PRD states the reason plainly: they are already present on the development machine and **can therefore be adopted by accident — working locally and failing in the VDI.**

This story is the single most likely place in the epic for that accident, because "open in a spreadsheet and compare" is trivially automatable with LibreOffice's CLI or `openpyxl`. Do not. The spreadsheet round-trip in AC #4 is performed **manually, once, by a human**, and its result recorded. A human using a spreadsheet to check a file is not a dependency; a script importing one is.

### Project Structure Notes

Creates:

```
tools/rpd_extract/
  adapters/outbound/
    csv_writer.py            # this story
  tests/                     # this story — stdlib unittest
```

`tests/` placement is not specified in the Architecture Spine. Placing it inside `tools/rpd_extract/` keeps the extractor a single self-contained copyable unit, which is what AD-16 (deployment is a file copy) asks for. Flag the choice to Winston so the Spine's layout absorbs it.

AD-15 is directional and enforced here: `core/` depends on nothing and performs no I/O; adapters may depend on `core`, never the reverse. This writer may be written without any `core` dependency at all — prefer that, and let Story 1.4 decide whether typed row objects are worth introducing.

Writes no `estate/` content. AD-2 makes the extractor the sole writer of `estate/knowledge-base/`, but that area is created by Story 1.4, not this one.

### References

- [Source: documents/planning-artifacts/prds/prd-POC-RPD-2026-08-15/prd.md#FR-28] — spreadsheet-safe CSV integrity, round-trip requirement
- [Source: documents/planning-artifacts/prds/prd-POC-RPD-2026-08-15/prd.md#FR-27] — Tabular Artifacts as CSV
- [Source: documents/planning-artifacts/prds/prd-POC-RPD-2026-08-15/prd.md#FR-2] — verbatim metric logic, the claim in tension
- [Source: documents/planning-artifacts/prds/prd-POC-RPD-2026-08-15/prd.md#9 Runtime and Dependency Policy] — NFR13, NFR15 and why the exclusions are recorded explicitly
- [Source: documents/planning-artifacts/prds/prd-POC-RPD-2026-08-15/prd.md#7 Cross-Cutting NFRs] — NFR7 failure honesty
- [Source: documents/planning-artifacts/architecture/architecture-POC-RPD-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — CSV: UTF-8, comma, LF, one header row, every field quoted, formula-start guard
- [Source: documents/planning-artifacts/architecture/architecture-POC-RPD-2026-08-15/ARCHITECTURE-SPINE.md#Stack] — Python >=3.11, third-party packages: none at any version
- [Source: documents/planning-artifacts/architecture/architecture-POC-RPD-2026-08-15/ARCHITECTURE-SPINE.md#AD-15] — dependency direction
- [Source: documents/planning-artifacts/architecture/architecture-POC-RPD-2026-08-15/ARCHITECTURE-SPINE.md#AD-5] — artifacts are self-describing
- [Source: documents/planning-artifacts/architecture/architecture-POC-RPD-2026-08-15/ARCHITECTURE-SPINE.md#AD-19] — core tested directly, adapters against captured samples, never a live instance
- [Source: documents/implementation-artifacts/1-2-produce-a-reproducible-rpd-xml-export.md] — source of the real formula samples
- [Source: documents/planning-artifacts/epics.md#Story 1.3] — acceptance criteria

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

**AC #8 settled first, with the Operator, before any code was written.** Chosen: guard affected fields with a single leading apostrophe plus a companion `<column>_guarded` boolean column. Recorded with rejected alternatives in `documents/planning-artifacts/decisions/csv-formula-guard.md`.

The companion flag is what makes reversal deterministic rather than heuristic. A formula that legitimately begins with `'` is otherwise indistinguishable from a guarded one; the corpus includes exactly that case and a test pins it.

**The guard covers more than the four characters the Architecture Spine names.** Excel coerces `00123` → `123` and `1E5` → `100000` regardless of quoting, and loses precision past 15 digits. These are the same defect by another route, and FR-28's consequence list requires them handled, so `needs_guard` covers formula leaders, leading-zero integers, scientific notation, 16-digit-plus integers, and leading tab/CR/LF. A plain leading space is deliberately excluded — it round-trips reliably and guarding it would fire on ordinary formula text.

**Undeclared columns fail loudly** rather than silently mangling. A guardable value in a column not passed in `guard_columns` raises, naming the column and row (NFR7).

**Three `csv` module defaults were overridden**, each of which would otherwise have violated the Spine's conventions: `lineterminator` (defaults `\r\n`, set to `\n`), `quoting` (defaults `QUOTE_MINIMAL`, set to `QUOTE_ALL`), and the file opened with `newline=""` so embedded newlines inside quoted fields are not corrupted. No BOM — recorded as a decision, not a default.

**Tests: 23, all passing**, under stdlib `unittest`. Coverage: per-value byte-equality across a 21-value corpus, guarded/unguarded distinguishability, encoding and quoting assertions, byte-identical repeat writes (AD-6), order preservation, seven loud-failure paths, and an AST check asserting the module imports nothing outside the standard library (NFR13, FR-23).

Verified against real content shapes, including MDS XML expression text (`"SAMPLESALES"."Fact Revenue"."Bill Day Dt"` and the parameterised `"%1"` form).

**Outstanding — AC #4, the manual half.** The write → open in a spreadsheet → save → re-read verification has not been performed. It is deliberately manual: automating it would pull a spreadsheet library into the product and breach NFR15, which exists because LibreOffice and `openpyxl` are already installed on this machine. Record the result in the decision document's verification table. **The story is not complete until this is done.**

**Note for Story 1.4:** the demo requirement — point the tool at a directory and load every XML under it — lands on the CLI, not here. The writer is format-agnostic and needs no change for it.

### File List

- `tools/rpd_extract/__init__.py` (created)
- `tools/rpd_extract/adapters/__init__.py` (created)
- `tools/rpd_extract/adapters/outbound/__init__.py` (created)
- `tools/rpd_extract/adapters/outbound/csv_writer.py` (created)
- `tools/rpd_extract/tests/__init__.py` (created)
- `tools/rpd_extract/tests/test_csv_writer.py` (created)
- `documents/planning-artifacts/decisions/csv-formula-guard.md` (created)
