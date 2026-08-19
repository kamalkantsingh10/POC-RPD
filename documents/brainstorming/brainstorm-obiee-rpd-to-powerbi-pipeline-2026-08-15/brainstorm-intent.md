# Brainstorm Intent — OBIEE RPD → Power BI Migration Assistant

**Source:** brainstorming session, 2026-08-15 · **Owner:** Kamal · **Status:** direction settled, ready for downstream planning

---

## What we are building

A two-stage assistant that reverse-engineers OBIEE RPD metadata into documentation and Power BI semantic models.

**Stage 1 — Deterministic extraction (Python).** Parse the RPD (via XML export) and emit an Excel knowledge base capturing exact metric logic and full physical lineage.

**Stage 2 — Judgement layer (markdown-defined agents).** PM → Analyst → Architect → Dev → Test, consuming the knowledge base to produce specs, an LLD per report, a Power BI model design, the model itself, and parity validation.

## Core thesis

**The risk is verification economics, not translation capability.**

Every question raised and every project-killer named concerns what happens *after* generation, never whether generation is possible. The POC must therefore prove the output can be *verified cheaply*, not that it can be *produced*.

## Non-negotiable decisions

| Decision | Detail |
|---|---|
| **Scope** | Strictly **as-is** migration. No enhancements. |
| **Source of truth** | The **RPD**. It is what the team already relies on for manual analysis today. |
| **AI's role** | An **assistant**, not an autopilot. Output quality is capped by the operating human's experience. |
| **AI's remit** | It does not just produce — it **reviews its own code, tests it, and compares results against legacy data**. |
| **Cost** | Token cost will be significant and must be modelled explicitly. ROI remains strongly positive. |
| **Portability** | Achieved via two standing design constraints, not a workstream (below). |
| **Data access** | **Confirmed available.** Humans in the VDI can query the data, therefore the tool can. |

## Standing design constraints — from the first commit

1. **Every Python dependency installs without admin rights.** Stdlib-first; `pip --user`, venv, or vendored wheels. No compiled extensions, no system packages.
2. **All agent definitions are plain markdown.** No framework, no runtime, nothing to install. Porting to the VDI is a copy operation.

*These are not compromises. Plain Python + Excel + markdown is more portable, more inspectable, and more teachable than any framework — and it largely answers the "will this need training?" question by itself.*

## Knowledge base fidelity requirements

The KB must capture **exact logic as written** and **full lineage to physical tables/columns** — plus the boring, deterministic details that destroy parity if skipped:

- Aggregation rule per logical column, including dimension-specific aggregation overrides
- Logical Table Source priority and fragmentation predicates
- Content-level filters on each LTS
- Inner vs. left-outer joins in the BMM layer
- Time-series functions (`AGO`, `TODATE`, `PERIODROLLING`) — no clean DAX equivalent, needs real translation
- Session and repository variables used in filters
- The physical → logical → presentation rename chain
- Implicit fact column
- RLS / data filters per application role

**Principle: anything deterministic happens in Python; the LLM only does what genuinely requires judgement.** This is simultaneously the accuracy control and the token-cost control.

## Success criteria (what failure looks like)

The project is abandoned if any of these occur:

1. Accuracy is too low
2. Debugging the output consumes too many man-hours
3. Bugs reach production

All three are addressed by the same mechanism: **AI-run parity comparison against legacy data**, now unblocked.

## Phased plan

**Phase 0 — Prove and win internal approval (2 weeks)**
- Python extractor → Excel knowledge base
- AI-generated LLD document per report
- Benchmark set: **6 reports across 3 difficulty tiers** (2 simple, 2 medium, 2 tangled)
- Demo → internal team approval

*Phase 0 wins standalone: it automates RPD analysis the team performs manually today, and produces documentation only — it cannot introduce a production bug.*

**Phase 1 — After approval**
- Deep parity-killer extraction
- Analyst + Architect workflows (the critical path — if the design is right, Dev is mechanical)

**Phase 2 — Verification and generation**
- Parity harness against legacy data
- Dev + Test workflows
- Accuracy-vs-complexity curve from the tiered benchmark — this is what forecasts full-migration effort and locates the human review gate

**Parked — pitch material, not POC work**
Living docs regenerated from PBIP/TMDL · spec-driven BI (LLD as source, model as output) · impact analysis · dead-report detection · duplicate-metric detection · guided vs. expert operator modes · training material

## Strategic framing

**The migration is the funding event. The documented semantic estate is the asset that outlives it.**

Nobody approves a project to document the OBIEE landscape; everybody approves a Power BI migration. Complete it and you own a machine-readable, human-readable map of every metric the organisation has defined — which then serves ongoing maintenance of the Power BI estate.

**Implication for design:** the LLD is not a byproduct of the pipeline. It is the point of it. Design it first and best; model generation hangs off it.

## Risk to manage deliberately

Quality is capped by operator experience, yet the goal is to resolve an effort crunch across the team. Scaled carelessly, this produces **junior-quality work at senior speed** — project-killer #3 with better throughput.

**Mitigation:** the LLD is the artifact where senior judgement is captured and made reviewable. Build explicit expertise-injection points where the tool stops and demands a judgement only an OBIEE veteran can make.

## Open item

Confirm that **programmatic** data access (nqcmd / JDBC / ODBC for issuing logical SQL) is available, not only human UI access. Five-minute check; gates the Phase 2 parity harness.

---

*Full session record: `.memlog.md` in this directory.*
