---
title: Sprint Change Proposal — SampleApp unobtainable
date: 2026-08-16
trigger_story: 1.1
status: approved
approved_by: Kamal
approved_on: 2026-08-16
scope: Moderate
---

# Sprint Change Proposal — SampleApp unobtainable

## 1. Issue Summary

**Story 1.1's first acceptance criterion fired, exactly as designed.** It was written to check SampleApp availability before any effort was sunk into work depending on it. The answer is negative.

**Problem statement.** The Oracle SampleApp v607 virtual appliance — the assumed foundation for the entire Test Corpus — is not obtainable. Three PRD commitments depend on it and cannot be met as written.

**Issue type:** technical limitation discovered during implementation. Specifically, an external dependency assumption falsified. This is not a misunderstanding of requirements: PRD §15 named SampleApp availability as *the highest-priority open item*, and §11 listed its disappearance as a risk that removes Phase 0's foundation. The plan anticipated this; the check confirmed it.

**Evidence** (2026-08-16, recorded in `estate/test-corpus/environment.md` §1):

| Check | Result |
|---|---|
| Historic SampleApp URL | Redirects to **Page not found** |
| `oracle.com` search, "SampleApp" | 22 results, none the OBIEE appliance |
| **`edelivery.oracle.com`, signed in** | Only Siebel and WebLogic samples — **no OBIEE SampleApp** |
| Oracle licence held | **None** — closes every edelivery route, including the OBIEE 12c Docker path |

**What was recovered.** Two genuine OBIEE repositories were found on GitHub and pinned as the corpus: `VasiliKorzun/BI-Analytics-2013` (a real working estate — 1252 XML files, 18 Subject Areas, 343 variables, 152 init blocks) and `rvijay17/obiee` (SampleApp-derived — `SAMP_REVENUE_F`, `SAMPLESALES`, Subject Areas "Sample Sales", "Densification - US Crime By State", "Population"). Both are RPD metadata only. **Neither contains a Web Catalog, and neither carries live data.**

## 2. Impact Analysis

### Epic impact

**Epic 1 is not invalidated and should not be rolled back.** Seven of ten stories are delivered and working: the extractor parses 1383 real XML files into 5290 Knowledge Base objects across a full three-layer model, with 1573 lineage rows, zero dangling references, byte-identical re-runs, and 66 passing tests. PRD §13's standalone-value argument holds in practice — the Knowledge Base exists, works on a real estate, and returns value whether or not anything downstream ships.

Three stories are blocked, all for the same root cause:

| Story | Blocked by | Resolution |
|---|---|---|
| 1.8 Benchmark set | No Dashboards — no Web Catalog in corpus | Rescope to Subject Areas |
| 1.9 Constructed Cases | No Administration Tool — no licence | Hand-author MDS XML, with disclosure |
| 1.10 Parity-critical metadata | Depends on 1.9 for 5 of 9 constructs | Unblocked once 1.9 lands |

**Epic 2** (deliberately unplanned) is affected in one way: its candidate scope included one hand-run Parity Check and a Comparison Report. Both require live data. Group Spec generation and the Migration Spine are unaffected — they consume the Knowledge Base, which exists.

**No epic is obsolete. No new epic is needed. Sequencing is unchanged.**

### Artifact conflicts

**PRD** — four requirements conflict with reality: FR-30, FR-31, §6.1's parity commitment, and consequentially §14 (SM-2), §11 and §16.

**Architecture Spine** — already reconciled on 2026-08-16. AD-20 (MDS XML is the target serialisation) and AD-21 (an expression is captured in all three forms) were added, the layout gained `estate/test-corpus/` and `tools/rpd_extract/tests/`, and the catalog deferral was sharpened. **No further architecture change is required by this proposal.**

**UX** — N/A. No user interface exists or is planned.

**Other artifacts** — testing strategy changes materially: fixtures are hand-authored rather than tool-generated (see Risk below). No CI in Phase 0, no deployment scripts, no IaC. New documentation created: `environment.md`, `corpus.md`, `mds-xml-schema.md`.

### A second finding, sharper than the first

FR-6 and FR-7 (Web Catalog extraction) are deferred to Phase 1 and now have **no fixture at all**. Under AD-19 they cannot be written or tested. This is not caused by the present change, but it is exposed by it, and Phase 1 must not be planned around a parser with nothing to parse.

## 3. Recommended Approach

**Hybrid: Direct Adjustment (Option 1) + targeted PRD MVP Review (Option 3).**

| Option | Verdict |
|---|---|
| **1. Direct Adjustment** — modify stories 1.8–1.10 | **Viable.** Effort: Medium. Risk: Low |
| **2. Rollback** — revert completed work | **Not viable.** Nothing would be simplified. Seven stories delivered working software whose value is independent of the blocked three; reverting destroys value for no gain |
| **3. PRD MVP Review** — amend requirements | **Required.** FR-30, FR-31 and §6.1 are PRD-level commitments, not story details. Effort: Medium. Risk: Medium — the approval pitch changes |

**Rationale.** Story-level edits alone would leave the PRD describing a plan nobody can execute, and a future reader would re-plan against impossible requirements. Amending the PRD keeps it the single source of truth. Rollback is rejected outright: the extractor works on a real estate today, and that is the epic's whole purpose.

**Timeline impact:** none to Epic 1's remaining work. The blocked stories become executable rather than deferred.

**Scope classification: Moderate** — backlog reorganisation plus PRD amendment, no fundamental replan.

## 4. Detailed Change Proposals

### 4.1 PRD — FR-30

**Section:** §4.11 Test Corpus

> **OLD:** *Simple / Medium / Tangled tiers … Each tier contains at least two Dashboards. At least two Dashboards in the corpus share a Subject Area, so Semantic Model reuse is exercised rather than assumed.*

> **NEW:** Tiers are assigned to **Subject Areas**, not Dashboards. Each tier contains at least two Subject Areas. At least two Subject Areas share logical tables, so Semantic Model reuse is exercised rather than assumed. Tier assignment cites the Knowledge Base row identifiers evidencing it.
>
> **Explicitly out of scope:** report-layer difficulty. The corpus contains no Web Catalog, so tiering measures the difficulty of the *semantic* migration only. Dashboard-level difficulty — visual count, prompt complexity, drill paths — is unassessed and must not be claimed.

**Rationale.** Dashboards live in the Web Catalog, which the corpus lacks. The Subject Area is the PRD's own stated *"natural unit of a Power BI Semantic Model"* (§3 Glossary), so it is the right substitute rather than a convenient one. Tier criteria also become **queryable from the Knowledge Base** — multi-source count, `AggrRule@isDefault`, time-series function presence — which makes assignment reproducible rather than a reviewer's judgement. That is a genuine improvement on the original.

### 4.2 PRD — FR-31

**Section:** §4.11 Test Corpus

> **OLD:** *Constructed Case — a deliberately authored OBIEE construct, built in the Admin Tool to exercise a known parity hazard.*

> **NEW:** Constructed Cases are authored **directly as MDS XML**, modelled on real corpus files. The Administration Tool is unavailable.
>
> Each case records that it is hand-authored, and that its Ground Truth is **authorial intent rather than observed OBIEE behaviour**. Accuracy derived from Constructed Cases is reported separately from accuracy measured against real corpus content, and never merged into a single figure.
>
> Cases are required only for constructs the corpus does not already exercise. A construct with real corpus evidence cites that evidence instead — a real example always beats a constructed one.

**Rationale.** Measuring the corpus shrank the problem: **four constructs need authoring, not six.** Content filters, join types, aggregation rules and multi-source are covered by real data. Fragmentation predicates, LTS priority, `PERIODROLLING` and implicit fact column are the genuine gaps.

### 4.3 PRD — §6.1 Phase 0 scope

> **OLD:** *At least one Parity Check, run by hand on the demo Dashboard: query SampleApp's Oracle Database for the legacy figure, query the hand-built Power BI model, show them matching.*

> **NEW:** **Removed.** No live data source is obtainable, so no Parity Check can be run in Phase 0.
>
> Phase 0 evidence is instead: (a) extraction accuracy against recorded Ground Truth, reported per construct type (SM-7); (b) the Knowledge Base demonstrated on a real 1252-object estate; (c) coverage reporting showing exactly which constructs are and are not exercised.
>
> **Phase 0 must state plainly that numeric parity is unproven and remains a Phase 2 question.** The product's thesis — that verification is the real risk — is argued in Phase 0 and demonstrated in Phase 2.

**Rationale.** This is the most consequential change in the proposal and the one to be most honest about. PRD §6.1 justified the hand-run check precisely because *"an MVP that demonstrates no verification leaves that thesis unproven at exactly the moment it is being judged."* That concern is valid and is not resolved — it is deferred. The alternative was pausing the approval gate on a dependency nobody controls, which forfeits the standalone value the Knowledge Base already delivers.

### 4.4 PRD — consequential updates

- **§14 SM-2 (Parity pass rate):** mark **not measurable in Phase 0**. No live data.
- **§14 SM-7:** remains the headline accuracy figure, now carrying the hand-authored-Ground-Truth caveat from §4.2.
- **§16 Assumptions Index:** the §4.11 assumption *"the SampleApp appliance is obtainable"* is **falsified**. Replace with the corpus sourced from pinned public repositories, and add the assumption that hand-authored MDS XML is representative of Administration-Tool output.
- **§11 Risk table:** *"SampleApp is no longer downloadable"* has **materialised** — record the outcome and the mitigation taken. **Add a new risk:** hand-authored Ground Truth is circular — a misunderstanding of the format produces a fixture and an expectation that agree with each other and disagree with reality. Mitigation: model every case on a real file, prefer strengthening thin constructs over inventing absent ones, and have Ground Truth reviewed by someone who did not author the case.
- **§10 Dependencies:** SampleApp appliance and Administration Tool are unavailable; corpus dependency is now two pinned GitHub repositories, **neither licensed** — recorded as an open legal question, not resolved.

### 4.5 Stories

**1.8** — retitle *Select and Tier the Benchmark Set*; acceptance criteria already drafted against Subject Areas in the story file. Unblock to `ready-for-dev`.

**1.9** — approach changed to hand-authored MDS XML; scope narrowed to four constructs; disclosure criteria added. Unblock to `ready-for-dev`.

**1.10** — no change to acceptance criteria. Its AC #7 already requires any construct without a fixture be *reported as unimplemented rather than claimed as working*, which is exactly the right behaviour under this proposal. Remains dependent on 1.9.

## 5. Implementation Handoff

**Scope: Moderate** — backlog reorganisation plus PRD amendment. No fundamental replan; the architecture is already reconciled.

| Recipient | Responsibility |
|---|---|
| **PM (John)** | Apply §4.1–§4.4 PRD amendments. Owns the §6.1 scope reduction and the honesty of the approval pitch |
| **Developer** | Apply §4.5 story edits; update `sprint-status.yaml`; execute 1.8 → 1.9 → 1.10 in order |
| **Architect (Winston)** | **No action.** Spine already reconciled 2026-08-16 (AD-20, AD-21, layout, catalog deferral) |
| **Operator (Kamal)** | Decide the licensing question on the two unlicensed corpus repositories before any derived artifact leaves the team |

**Success criteria**

1. PRD contains no requirement that cannot be executed against the available corpus.
2. Stories 1.8–1.10 are executable without further blockers.
3. Every accuracy figure states whether it rests on real corpus evidence or hand-authored Ground Truth.
4. Phase 0 materials state plainly that numeric parity is unproven until Phase 2.

**Sequencing:** PRD amendments first (they define what 1.8 and 1.9 must satisfy), then 1.8, then 1.9, then 1.10.

## Checklist Record

| § | Item | Status |
|---|---|---|
| 1.1 | Triggering story identified — 1.1 | Done |
| 1.2 | Core problem defined — external dependency assumption falsified | Done |
| 1.3 | Evidence gathered — browser + edelivery checks, measured coverage | Done |
| 2.1 | Epic 1 completable with modifications | Done |
| 2.2 | Epic changes — modify 3 story scopes; no add/remove/redefine | Done |
| 2.3 | Future epics reviewed — Epic 2 loses parity elements only | Done |
| 2.4 | No epic invalidated; no new epic needed | Done |
| 2.5 | Sequencing unchanged | Done |
| 3.1 | PRD conflicts — FR-30, FR-31, §6.1, §11, §14, §16 | Action-needed |
| 3.2 | Architecture — reconciled 2026-08-16 | Done |
| 3.3 | UI/UX — no interface exists | N/A |
| 3.4 | Other artifacts — testing strategy changed; docs created | Done |
| 4.1 | Option 1 Direct Adjustment | Viable |
| 4.2 | Option 2 Rollback | Not viable |
| 4.3 | Option 3 PRD MVP Review | Viable — required |
| 4.4 | Path selected — Hybrid 1 + 3 | Done |
| 5.1–5.5 | Proposal components | Done |
| 6.3 | Explicit user approval obtained | Done — Kamal, 2026-08-16 |
| 6.4 | `sprint-status.yaml` update | Done |
| 6.5 | Handoff confirmed | Done |
