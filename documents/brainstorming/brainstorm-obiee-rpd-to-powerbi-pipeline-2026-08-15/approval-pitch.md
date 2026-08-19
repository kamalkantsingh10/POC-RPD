# Accelerating OBIEE → Power BI Migration with an AI-Assisted Pipeline

**Proposal for internal approval** · Kamal · August 2026
**The ask:** two weeks to prove one phase. Nothing more.

---

## The problem

Migrating OBIEE reports to Power BI is bottlenecked long before anyone opens Power BI. The expensive part is **understanding the RPD** — tracing what a metric actually computes, which physical tables it resolves to, which of its logical sources fires under which conditions. Today that is manual, slow, and done by the few people who can do it.

We are not short of Power BI skill. We are short of hours spent decoding OBIEE.

## The proposal

A two-stage assistant:

**Stage 1 — Extraction (plain Python).** Reads the RPD export and produces an **Excel knowledge base**: every presentation column, its exact logic as written, and its full lineage down to physical tables. Deterministic. No AI involved. 100% reproducible.

**Stage 2 — Documentation and design (AI agents).** Consumes that knowledge base to produce a **specification / LLD per report**, then a Power BI model design, then the model, then validation.

**Crucially, Stage 2 does not just generate.** It reviews its own output, tests it, and — because it can query our data exactly as we can — **compares the migrated numbers against the legacy report itself.**

## Why this is low-risk

**Phase 1 pays for itself even if we stop there.**

The Excel knowledge base automates analysis the team already performs by hand. It produces *understanding*, not code. It cannot introduce a production bug. If the rest of the pipeline never ships, we have still replaced days of manual RPD spelunking with a file generated in seconds.

Each phase is cheap to abandon, and the riskiest work comes last:

| Phase | Delivers | If it fails |
|---|---|---|
| **0 — Extract & document** | Excel KB + LLD per report | Known within two weeks, at near-zero cost |
| **1 — Analysis & design** | Trustworthy specs and model designs | We keep Phase 0's value |
| **2 — Build & verify** | Generated models + automated parity checks | We keep Phases 0 and 1 |

## What we are asking to prove in two weeks

- The extractor produces a correct, complete knowledge base from a real RPD
- The AI produces an LLD accurate enough that an OBIEE veteran signs off on it
- We can measure that accuracy on **six real reports across three difficulty tiers** — two simple, two medium, two genuinely tangled

That tiered set is deliberate. It gives us an **accuracy-vs-complexity curve**, which is what actually tells us how long a full migration takes and where a human needs to review.

## Answering the obvious objections

**"How do we know the output can be trusted?"**
We measure it before we rely on it. The LLD is reviewed by an OBIEE expert against the original report — that gives us a real accuracy number in an afternoon, before a single Power BI model exists.

**"What about bugs reaching production?"**
Phase 0 generates documentation only. It structurally cannot. Later phases ship behind an automated parity gate that compares migrated output against the legacy report using our actual data.

**"How does this run in the VDI?"**
It is designed for it from the first line of code. Two constraints: every Python dependency installs without admin rights, and every agent definition is a plain markdown file. Porting is a copy operation, not a project.

**"Does the team need training?"**
Minimal. There is no framework to learn — the agent definitions are readable markdown files, and the knowledge base is an Excel workbook. Anyone who understands OBIEE can read, review, and edit both.

**"Can the AI access our data?"**
Yes. Humans in the VDI can already query it, so the tool can, using the same access. Nothing new is exposed.

**"What does it cost?"**
Token cost will be real and we will measure it explicitly as cost-per-report during the POC. The comparison is against senior analyst days per report. We expect the ROI to be substantial and we will publish the actual number rather than assert it.

## What this is not

**It is not an autopilot.** It is an assistant that multiplies an experienced person's throughput. Its output is only as good as the person operating it — which is exactly why the specification document exists: it is where expert judgement gets captured, reviewed, and reused.

**It is not a redesign.** This is a strictly as-is migration. No enhancements, no opportunistic improvements, no silent "fixes."

## The part that outlasts the migration

When the migration is done, we will own something we would never have funded on its own: **a complete, machine-readable and human-readable map of every metric in our estate** — exact logic, full lineage, per report.

That becomes the maintenance documentation for the Power BI estate going forward. The migration is what pays for it.

---

## The decision

**Approve two weeks** to build the extractor, generate LLDs for six benchmark reports, and demonstrate the results.

At the end you will see a real accuracy number on real reports, a cost-per-report figure, and a working artifact — and a clear go/no-go on everything that follows.
