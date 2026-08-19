---
title: Agent responsibility map
date: 2026-08-18
status: draft
---

# Agent responsibility map

**What this covers:** which BMad agent gains which capability, and which stay untouched.
**Who it is for:** whoever builds the added skills, and anyone wondering why a capability sits where it does.

Every addition is a **new skill plus a `_bmad/custom/*.toml` menu entry** — never an edit to a shipped file (AD-14, FR-11). Menu arrays merge by `code`, so new codes append and survive a BMad upgrade.

---

## The map

| Agent | Shipped menu | Added | Epic |
|---|---|---|---|
| **Winston** — Architect | `CA` `IR` | **`AA`** as-is analysis ✅ *built* | 3 |
| | | `VC` verify a claim | 3 |
| | | `MS` Migration Spine | 5 |
| **Amelia** — Dev | `BD` `QA` `CR` `SP` `ER` | **nothing** | — |
| **Mary** — Analyst | `BP` `MR` `DR` `TR` `TS` `CR` `UV` `CB` `WB` `PC` | **nothing** | — |
| **John** — PM | `PRD` `CE` `IR` `CC` | **nothing** | — |
| **Sally** — UX | `CU` | **nothing** | — |
| **Parity Agent** | — | **new agent** | 6 |

Plus standalone skills invoked from a menu entry rather than being agents in their own right: the **Group Spec skill** (Epic 5) and the **change-map proposal** (Epic 4).

---

## Why each sits where it does

### Winston gets the analysis and design work

His role is *"convert requirements into technical architecture decisions."* Reverse-engineering an estate and mapping OBIEE constructs to Power BI are both that. FR-10 and FR-11 name him explicitly for the Migration Spine.

| Code | Capability | Reason |
|---|---|---|
| `AA` | As-is analysis of one Subject Area | Describes an existing system. Built; not yet run |
| `VC` | Re-derive one challenged claim | The reviewer's half of the loop. Distinct from authoring: it reads the slice and shows a derivation, rather than regenerating a document |
| `MS` | Migration Spine | FR-10, FR-11 |

### Amelia gets nothing — deliberately

FR-16: *"No change to Amelia is in scope."* She consumes what the analysis produces and generates Power BI files from stories, exactly as shipped.

The stronger reason is structural. The Group Spec exists so judgement is **captured and reviewed before anyone builds**. If the agent who builds also authors the specification, that review gate quietly disappears. Author and consumer must be different.

### Mary gets nothing — right name, wrong phase

Her role is *"ideate, research and analyse **before committing to a project**"*, and every menu item is forward-looking discovery: market research, brainstorming, product briefs. Nothing in her repertoire explains a system that already exists. "Analyst" reads like a fit and is not one.

### The Parity Agent is the only genuinely new agent

PRD §4.7 calls it *"the only genuinely new agent in the product."* Nothing shipped covers it: `bmad-qa-generate-e2e-tests` writes application E2E tests and `bmad-code-review` reviews code — **neither compares data**.

It authors Parity Checks, executes both sides, and reports divergence as a triage list (FR-17 to FR-20). It needs its own persona because its job is adversarial in a way none of the others are: its purpose is to find the migration wrong.

---

## A risk worth naming

**Winston accumulates three added capabilities.** That is a lot for one agent, and the failure mode is a menu nobody can navigate.

Two things make it tolerable. Each capability is a **separate skill file** — the menu entry is a pointer, so the agent definition stays thin. And all three are the same kind of work: understanding or designing structure.

**What would change this:** if a fourth or fifth lands on him, split by *artifact* rather than by agent — an estate-analysis persona distinct from a target-design one. Not warranted yet. Rule of Three.

**What must not happen:** moving capabilities to Amelia to balance the load. That trades a navigation problem for the loss of the review gate.

---

## Build order

| Epic | Agent work | Depends on |
|---|---|---|
| 2 | **None** — deterministic extractor only | — |
| 3 | Winston `AA` (validate), `VC` (build) | Knowledge Base |
| 4 | Change-map proposal skill | Schema file from DE |
| 5 | Winston `MS`; Group Spec skill | Epics 3, 4 |
| 6 | **Parity Agent** | Query access to both systems |

**Epic 2 needs no agent at all.** Catalog extraction is deterministic Python — the same principle that keeps agents off raw estate content, which is both the accuracy control and the token-cost control.

---

## Rules every added capability inherits

- **AD-4** — read the blackboard, state missing prerequisites, stop. Never assume a predecessor ran.
- **AD-11** — capability floor is *read a file, write a file, run a local command*. No MCP dependency, no client-specific tool names.
- **AD-12** — no subagent delegation. Partition the input instead; that is what the slice is for.
- **AD-14** — shipped BMad is read-only. New skill directory plus a `_bmad/custom/*.toml` entry.
- **AD-18** — one writer per `estate/` area. Declare it before writing anything.
- **NFR2** — every statement cites a Knowledge Base identifier, which is what makes `VC` possible at all.
