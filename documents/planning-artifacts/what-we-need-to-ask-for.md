---
title: What we need — the full list of asks
date: 2026-08-18
status: open
---

# What we need — the full list of asks

**What this covers:** everything the product needs from outside the team, grouped by who you ask.
**Who it is for:** Kamal, taking these to the OBIEE, database, Power BI and platform owners.

Ordered within each group so the first item is the one that unblocks the most. **Nothing here needs a running OBIEE server** — every OBIEE ask is a one-time export.

---

## 1. From whoever owns OBIEE

### 1.1 RPD exported as MDS XML — **required**

The exploded, one-file-per-object format:

```sh
biserverxmlgen -R <repo>.rpd -D <out-dir> -M -8
```

or Administration Tool, offline → **File → Save As → MDS XML Documents**.

**Both `-M` and `-D` are needed.** `-M` alone writes one large file; `-D` alone writes plain XUDML. Only together do they give the per-object layout.

⚠️ **Never `-Q`** — it silently drops every security object, so application roles, privileges and row-level filters vanish with no error.
⚠️ **Omit `-P`** — a password on the command line lands in shell history and the process list. Let it prompt.

**Unlocks:** everything. Without this there is no product.

### 1.2 Web Catalog archive — **required for report-layer work**

`runcat.sh` archive (`$DOMAIN_HOME/bitools/bin`) or a plain copy of the catalog directory.

**Why it matters:** in a real sample catalog, **82% of Analyses define logic that exists nowhere in the RPD** — moving averages, running totals, `AGO`, ranking. Without the catalog, an as-is document silently omits most of the actual computation.

**Unlocks:** FR-6, FR-7, Dashboard-level analysis, and the report-level half of any migration spec.

### 1.3 Both in one folder — **how to hand them over**

```
my-estate/
  rpd/       oracle/bi/server/base/…
  catalog/   …
```

One folder, both halves. Putting them together under one name *is* the declaration that they belong to the same estate — the tool never infers that.

**A BAR export is not sufficient on its own.** Verified 2026-08-17: a BAR contains `content/catalog/` (usable) but `datamodel/rpd/default.rpd` — the **proprietary binary**, which this tool does not parse. If a BAR is all that is available, it still needs `biserverxmlgen` run against the extracted `.rpd`.

### 1.4 The OBIEE or OAS version — **required**

A version gap shows up as unread attributes in `unparsed.csv` rather than as failures, so it is detectable but must be looked for. One sample catalog alone contained **four** distinct schema versions, so an estate's spread is real data.

### 1.5 Is Usage Tracking enabled? — **high value, ask early**

See §2.2. If it is on, most of the parity problem is already solved and nobody has to run anything.

---

## 2. From whoever owns the database

### 2.1 Read-only access, under your own account — **required for parity**

**Not a service account, and specifically not the OBIEE connection-pool credentials** — those are service accounts, and using them introduces exactly the new access path NFR11 forbids. The tool operates under your existing rights and exposes nothing new.

Needed against: the warehouse OBIEE queries, and later the new tables DE builds.

### 2.2 Usage Tracking schema — **the single highest-value database ask**

| Table | Holds |
|---|---|
| `S_NQ_DB_ACCT` | **The physical SQL OBIEE actually issued**, per query |
| `S_NQ_ACCT` | Logical SQL, timings, which user ran what |

**Why this is the unlock:** it is OBIEE's own answer, captured at the database. Comparing that against a Power BI result is *real* parity — not our reconstruction of what OBIEE would do, but what it did, including aggregate navigation, content filters and session-variable substitution.

**Second benefit:** it tells you which reports are actually used. The difference between migrating 77 dashboards and migrating the 20 anyone opens.

**If Usage Tracking is off:** `V$SQL` and AWR still show SQL issued by the OBIEE connection-pool user, but only recently and without report attribution. Worth asking whether it can be switched on now — history accumulates from the moment it is.

### 2.3 Stored procedure and function bodies — **needed for migration, not extraction**

`ALL_SOURCE` / `DBA_SOURCE`.

The repository invokes database routines and the tool records **every call site** — that is the dependency, and it cannot be recovered any other way. What it cannot show is what those routines *do*. Confirmed in a real sample: `FND_PROFILE.VALUE_SPECIFIC` (an E-Business Suite package) across 6 init blocks, plus 43 `EVALUATE` calls across 18 Analyses invoking DB functions directly from reports.

One of those feeds row-level security. Reproduce it wrongly in Power BI and rows silently disappear for some users.

### 2.4 DDL for the source tables — **for the Data Engineering handoff**

Indexes, partitioning, constraints, datatypes. The RPD names tables and columns; it does not define them.

---

## 3. From whoever owns Power BI

### Minimum for the POC: **Power BI Desktop. Nothing else.**

Desktop is a free download. That is the entire ask to prove the concept, because:

- **PBIP/TMDL are text files generated locally.** Nothing is published to produce them.
- **Desktop opens them** — which is FR-16's actual test: *"generated files open in Power BI Desktop without repair."*
- **Desktop runs a local Analysis Services instance**, so a generated model can be queried on the machine that made it. FR-22 anticipated exactly this: *"queries execute against the model as generated, **without manual publication steps** during Phase 2 validation."*

So the whole loop — generate, open, query, compare against the legacy number from the database — runs locally with no tenant, no workspace and no licence beyond the free Desktop install.

**One constraint worth checking:** Power BI Desktop is **Windows-only**. If the VDI is Linux, that changes where the validation step happens.

### Not needed for the POC

| | Needed when |
|---|---|
| Workspace and deploy rights | Publishing a migrated report for real users |
| **XMLA endpoint (Premium/PPU)** | Querying a *published* model programmatically — i.e. automating comparison at estate scale |
| Data gateway | A published model reaching on-premises tables |
| RLS configuration in the service | Row-level security enforced for real users |

**On XMLA specifically:** I previously listed it as required. It is not, for a POC. It matters when comparison moves from a handful of measures on one machine to hundreds across a published estate. Establish it before Phase 2 plans automation around it — but do not let it block starting.

### Worth confirming early, cheaply

**Is PBIP with TMDL available and permitted?** The PRD assumes it, chosen because it is text — diffable, generatable, reviewable. It is an unverified assumption and a one-question answer. If the organisation's tooling or policy rules it out, that is a Phase 2 rethink, not a Phase 0 blocker.

**Does the estate use row-level security?** Our sample does, some of it computed by a database function at login. If yours does, reproducing it is real work and worth knowing about before design, not during.

## 4. From whoever owns the VDI

Full detail in `vdi-readiness-checklist.md`. The three that decide everything:

1. **Python ≥ 3.11, runnable from a plain copy** — the only item with no fallback. If Python is absent and cannot be installed without admin, there is no product.
2. **Can the AI client execute a local command?** If not, a manual-invocation mode still works — a command does not care who runs it.
3. **Is Git reachable, and do reviewers have access?** The markdown-and-diff review loop depends on it.

---

## 5. From the Data Engineering team — later, once they build

### 5.1 The new schema, as a file

DDL or an information-schema dump. **Not query access** — a skill must never require it (AD-11). Live profiling strengthens a proposal where access exists; it never gates one.

### 5.2 The change map — old table/column → new, reviewed and signed

The tool proposes; **DE declares**. Concluding that old `SAMP_REVENUE_F.REVENUE` *is* new `fct_sales.amount` because names and types line up is exactly the error AD-8 forbids.

This artifact does two jobs: it feeds report design, and it **generates the parity checks** — a declared sameness is a testable claim.

---

## Summary — what each ask unlocks

| Ask | Unlocks | Priority |
|---|---|---|
| RPD as MDS XML | Everything | **Blocking** |
| Web Catalog archive | 82% of report logic, Dashboard-level work | **Blocking for report layer** |
| Both in one folder | Estate pairing, FR-7 | **Blocking for lineage end-to-end** |
| Read-only DB access (your account) | Parity | **Blocking for verification** |
| **Usage Tracking** | **Real parity + usage-based scoping** | **Highest value per unit of effort** |
| Power BI **Desktop** (free) | Opening and querying generated models | **Minimum — that is the whole POC ask** |
| Power BI XMLA / workspace | Automated comparison at scale, real deployment | Later — not a POC blocker |
| Stored procedure bodies | Correct RLS and calculations | High |
| Source DDL | DE rebuild | Medium — DE has it already |
| Gateway, RLS config, PBIP support | Deployment | Confirm before Phase 2 |

**If you can only ask three things:** the **estate folder** (RPD as MDS XML + catalog together), **Usage Tracking**, and **read-only DB access under your own account**. Those three take the project from analysis to provable migration.
