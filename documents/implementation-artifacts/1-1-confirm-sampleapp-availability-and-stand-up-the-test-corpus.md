# Story 1.1: Confirm SampleApp Availability and Stand Up the Test Corpus Environment

Status: done — AC #1 resolved NEGATIVE; corpus sourced differently. See Completion Notes.

**Review intensity: Keen** — rests on an unconfirmed external dependency (PRD Open Question 1). A wrong call here is not wrong code; it reshapes the epic. Errors of judgement in this story will not surface in any later test.

## Story

As an Operator,
I want a running SampleApp instance with its RPD, Web Catalog, and populated database,
so that the Test Corpus has a foundation and every later story works against real OBIEE content rather than invented fixtures.

## Acceptance Criteria

1. SampleApp availability is checked **as the first action of the epic**. Either a working download is obtained and its version recorded, or unavailability is reported immediately as a blocker with alternatives assessed. The epic does not proceed around an unconfirmed dependency.
2. The appliance imports and boots on available hardware; the OBIEE server starts and the Analytics UI is reachable.
3. The Web Catalog opens, SampleApp's shipped Dashboards are present, and at least one renders with data.
4. A sample query against the warehouse schema returns rows, confirming live data exists for later parity work.
5. `estate/test-corpus/environment.md` records the SampleApp version, OBIEE version, host hardware, import steps, and how to start and stop the appliance — sufficient to rebuild from scratch (FR-30).
6. The SampleApp OBIEE version is stated explicitly so parser-transfer risk against the organisation's unknown version can be assessed before the parser is built on it (PRD Open Question 2).
7. All access is read-only. Nothing in this story or any later one writes to the OBIEE source or the warehouse (NFR12).

## Tasks / Subtasks

- [ ] Confirm SampleApp obtainability (AC: #1)
  - [ ] Locate the SampleApp VirtualBox appliance (OBIEE 12c, v607 per PRD §10). Distribution is via Oracle OTN, unsupported, large, and dated.
  - [ ] Record the exact download source, file size, checksum if published, and date obtained.
  - [ ] **If it cannot be obtained: stop and report.** Do not substitute a hand-built RPD or a synthetic fixture — the whole corpus argument (PRD §4.11) rests on real Oracle-authored content plus deliberately authored irregularity. Escalate to the Operator with alternatives assessed.
- [ ] Import and boot the appliance (AC: #2)
  - [ ] Import into VirtualBox on available hardware; record RAM/CPU/disk actually allocated.
  - [ ] Start the OBIEE stack and confirm the Analytics UI loads.
  - [ ] Record startup and shutdown procedure verbatim, including any service start order and wait times.
- [ ] Verify catalog and data (AC: #3, #4)
  - [ ] Open the Web Catalog; confirm shipped Dashboards are present; note roughly how many and their Subject Areas.
  - [ ] Render at least one Dashboard and confirm it returns data.
  - [ ] Run one read-only query against the warehouse schema; record the query and that rows returned.
  - [ ] Note the programmatic query path available (nqcmd / JDBC / ODBC). This pre-answers PRD Open Question 5 material and matters for later parity work — record it even though nothing consumes it in this epic.
- [ ] Write the environment record (AC: #5, #6)
  - [ ] Create `estate/test-corpus/environment.md` per the structure in Dev Notes.
  - [ ] State the SampleApp version and the OBIEE version separately and explicitly.
  - [ ] Confirm a second person could rebuild from the document alone.
- [ ] Confirm read-only posture (AC: #7)
  - [ ] Record in `environment.md` that all access is read-only and that no story writes to OBIEE or the warehouse.

## Dev Notes

**This story is Operator work, not code.** Nothing under `tools/` is created here. The deliverable is a running environment plus one markdown document. Do not scaffold the extractor, create `estate/knowledge-base/`, or write Python — Story 1.4 owns the first code that produces Knowledge Base output, and Story 1.3 owns the first code overall.

**Why this story is first.** SampleApp availability is PRD §15 Open Question 1, named there as the highest-priority open item, and PRD §11 lists "SampleApp is no longer downloadable" as a risk that removes Phase 0's foundation entirely. A negative answer reshapes the epic rather than delaying it, so the check happens before any effort is sunk into stories that depend on it.

**What the environment must supply downstream:**

| Consumer | Needs from this story |
|---|---|
| Story 1.2 | `biserverxmlgen` inside the VM, and the RPD to export |
| Story 1.3 | Real OBIEE formula text for the round-trip corpus (arrives via 1.2's export) |
| Stories 1.4–1.7 | The RPD XML export |
| Story 1.8 | Shipped Dashboards to tier, at least two sharing a Subject Area |
| Story 1.9 | Oracle BI Administration Tool to author Constructed Cases |
| Phase 2 | Live warehouse data for Parity Checks |

Verify the Administration Tool is present while the VM is up — Story 1.9 is blocked without it, and discovering that eight stories later is expensive. PRD §10 notes it is Windows-only in most versions.

**Structure for `estate/test-corpus/environment.md`** (FR-29 applies — open with what it covers and who it is for; reference material in tables, not prose):

- What this document covers and who it is for
- Provenance: download source, date obtained, file size, checksum
- Versions: SampleApp version, OBIEE version, database version — as a table
- Host: hardware, VirtualBox version, RAM/CPU/disk allocated
- Import procedure: numbered steps
- Start and stop procedure: numbered steps, including service order and waits
- What is present: Dashboard count, Subject Areas observed, Administration Tool availability
- Programmatic query path available
- Read-only statement
- Known deviations from the shipped appliance, if any

### Project Structure Notes

**New blackboard area — declare it.** The Architecture Spine's layout (§Structural Seed) does not include a Test Corpus area, but the Capability Map assigns Test Corpus (FR-30, FR-31) to "`estate/` fixtures + SampleApp". This story creates:

```
estate/test-corpus/          # writer: Operator
  environment.md             # this story
  benchmark-set.md           # Story 1.8
  constructed-cases/         # Story 1.9
```

AD-18 requires every `estate/` area to have exactly one declared writer. **Writer: Operator.** No agent and no extractor writes here. Record this declaration in `environment.md` so the rule is stated where the area lives, and raise the layout addition with Winston so the Architecture Spine stays the single source of truth.

**Do not** place corpus content under `documents/` — that directory holds planning artifacts and is explicitly "not blackboard state" per the Spine's layout comment.

### References

- [Source: documents/planning-artifacts/prds/prd-POC-RPD-2026-08-15/prd.md#4.11 Test Corpus] — FR-30, FR-31, why SampleApp and why Constructed Cases
- [Source: documents/planning-artifacts/prds/prd-POC-RPD-2026-08-15/prd.md#10 Integration and Dependencies] — SampleApp v607, `biserverxmlgen`, Administration Tool, distribution risk
- [Source: documents/planning-artifacts/prds/prd-POC-RPD-2026-08-15/prd.md#11 Risk and Mitigations] — "SampleApp is no longer downloadable", "SampleApp version differs from the organisation's OBIEE version"
- [Source: documents/planning-artifacts/prds/prd-POC-RPD-2026-08-15/prd.md#15 Open Questions] — Q1 (availability), Q2 (organisation's OBIEE version)
- [Source: documents/planning-artifacts/prds/prd-POC-RPD-2026-08-15/prd.md#8.3 Safety] — read-only, NFR12
- [Source: documents/planning-artifacts/architecture/architecture-POC-RPD-2026-08-15/ARCHITECTURE-SPINE.md#AD-18] — one writer per blackboard area
- [Source: documents/planning-artifacts/architecture/architecture-POC-RPD-2026-08-15/ARCHITECTURE-SPINE.md#Structural Seed] — `estate/` layout, `documents/` is not blackboard state
- [Source: documents/planning-artifacts/epics.md#Story 1.1] — acceptance criteria

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

**Outcome: the story's first acceptance criterion fired.** SampleApp is not obtainable, and the epic's shape changed rather than the work being delayed. No code was written.

- **AC #1 — RESOLVED NEGATIVE.** SampleApp v607 is not published by Oracle. Historic URL → "Page not found"; `oracle.com` search for "SampleApp" returns 22 unrelated results; **edelivery, checked while signed in, returns only Siebel/WebLogic samples — no OBIEE SampleApp.** Both public and authenticated paths are closed.
- **Blocked further by licensing.** The Operator has no Oracle licence, so every edelivery route (OBIEE 12.2.1.x binaries, Oracle Analytics Server, the Docker build path) is unavailable regardless of what is listed there.
- **AC #4 — host capability PASS.** 16 cores, 94 GB RAM, 383 GB free, VT-x/AMD-V present, Docker installed, VirtualBox not.
- **AC #2, #3 — not achievable and superseded.** No appliance to import or boot.
- **AC #5, #6, #7 — partially satisfied.** `estate/test-corpus/environment.md` exists and records the investigation, host capability, and the read-only posture. Version fields stay pending because no instance was stood up.
- **Corpus sourced from GitHub instead.** Two genuine MDS XML repositories found, free and licence-free to read: `rvijay17/obiee` (**SampleApp content** — `SAMP_REVENUE_F`, `SAMPLESALES`, Subject Areas "Sample Sales", "Densification - US Crime By State", "Population") and `VasiliKorzun/BI-Analytics-2013` (a real working estate — 1253 files, 18 Subject Areas, 343 variables, 152 init blocks, 72 query privileges). Verified authentic via the `http://www.oracle.com/obis/repository` namespace and opaque MDS GUIDs.
- **A third candidate was examined and rejected:** `cyphou/OACToFabric`'s six "RPD XML" samples are synthetic (human-readable `mdsid` slugs, namespace-less root, attribute-only `LogicalTableSource`).

**Consequences carried forward — none of these are closed by this story:**

1. **Format.** The corpus is **MDS XML** (exploded, one file per object, GUID cross-references), not the single-file `biserverxmlgen` export FR-1 and PRD §4.1 assume. The Spine's inbound adapter list names neither. **Decision for Winston before Story 1.4.**
2. **FR-2 verbatim.** MDS XML stores each expression three ways — `ExprText` (parameterised, `"%1"`), `ExprTextDesc` (fully-qualified readable), `ObjectRefList` (object references). No single "as written" field exists. **Decision for the Operator on Story 1.5.**
3. **FR-30 is not satisfiable.** No Web Catalog means no Dashboards, so "six Dashboards across three tiers" cannot be met.
4. **No live data.** PRD §6.1's one hand-run Parity Check — the thesis-proving element of the demo — cannot be performed.
5. **Story 1.9 has no Administration Tool.** Constructed Cases could be hand-authored as MDS XML text, but hand-written XML may not match what the Admin Tool emits, which weakens the Ground Truth claim.
6. **Licensing and privacy unresolved.** Neither repository carries a licence (all rights reserved by default); Source A is Oracle IP wherever hosted; Source B contains personal names in Subject Area names. Reading is fine; **vendoring into this repository is an open decision.**

Items 3 and 4 change agreed MVP scope and need `bmad-correct-course`, not a silent adjustment.

### File List

- `estate/test-corpus/environment.md` (created)
