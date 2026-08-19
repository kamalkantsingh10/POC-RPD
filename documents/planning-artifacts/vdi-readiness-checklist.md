---
title: VDI Readiness Checklist
date: 2026-08-17
status: open
---

# VDI Readiness Checklist

**What this covers:** everything that must be true in the VDI for this product to work there, ordered so the answers that invalidate the most come first.
**Who it is for:** whoever gets VDI access, and the approval audience — several of these are PRD open questions that have been unanswered since the PRD was written.

Record the answer beside each item. **A blocked item is a finding, not a failure** — it is far cheaper here than in Phase 2.

---

## Tier 1 — nothing works without these

Do these first. A bad answer here changes the product, not the plan.

### 1.1 Is Python ≥ 3.11 present?

```sh
python3 --version
```

**Why it blocks everything:** the extractor is Python. FR-23 forbids requiring admin rights, so if Python is absent and cannot be installed as an unprivileged user, **there is no product** — not a degraded one.
**If it fails:** stop and escalate. This is the single assumption with no fallback.

### 1.2 Does the extractor run from a plain copy, with no install?

Copy the repository to the VDI, then:

```sh
python3 -m tools.rpd_extract.cli \
  --corpus estate/test-corpus/constructed-cases/constructed \
  --rpd-id demo --out %TEMP%/demo
```

Expect `parsed: 21 objects`, `errors: 0`. Needs no network, no install, no corpus.
**Why:** proves AD-16 (deployment is a file copy) and FR-23/FR-24 in one command. **This is the single most informative test in the list.**

### 1.3 Can you write files where you need to?

The extractor writes CSVs; the analysis skill writes markdown. Confirm a writable working directory outside any locked-down profile path.

---

## Tier 2 — the AI client (PRD §15 Q4, FR-25)

The PRD calls this *"the single largest portability risk."* It is **two** capabilities, not one.

### 2.1 What exactly is the Copilot client?

Product and tier — completion-only, chat, or agent mode. Agent mode is what can execute commands.
**Resolves:** §15 Q4, and FR-25's `[ASSUMPTION]`.

### 2.2 Can it execute a local command?

Ask it to run the command from 1.2.

| Outcome | Consequence |
|---|---|
| It runs it | Full automation. Best case |
| It suggests but will not run | **Manual-invocation fallback** — you run commands, point the agent at the output. Viable; PRD §11 already plans for it |
| No command capability at all | Manual mode only. Still workable because the Python does not care who runs it |

**Note:** this is why AD-11 sets the floor at "run a local command". A command has a human fallback; **MCP has none** — if the client cannot do MCP, the capability simply does not exist.

### 2.3 Can it read markdown skill definitions?

Put `.claude/skills/obiee-as-is-analysis/SKILL.md` in place and see whether Copilot picks it up, or whether its own instruction-file convention must be used instead.
**If not:** skills become procedures a human follows, or need restating in Copilot's format. Content survives; invocation changes.

---

## Tier 3 — dependencies and network

### 3.1 Confirm the extractor needs nothing

Already true by design — standard library only, asserted by a test. Item 1.2 proves it in situ.

### 3.2 Can a pure-Python wheel be installed offline, without admin?

```sh
pip install --user --no-index --find-links=./wheels oracledb
```

**Why it matters later:** parity testing (Epic 6) needs a database driver. `python-oracledb` in **Thin mode** is pure Python and needs no Oracle Client libraries, which is exactly the exception NFR13 allows. **Not needed for extraction or analysis** — only for query execution.

### 3.3 Is there any internet access?

Assume none. Confirm it, because it determines whether wheels must be pre-staged.

### 3.4 Can MCP servers be installed without admin?

PRD §9 calls this *"an open item and a Phase 2 gate."* They usually ship as `npx`/`uvx` packages.
**If not:** nothing breaks. AD-11 already forbids any skill depending on MCP, so this is an optimisation, not a requirement.

---

## Tier 4 — source artifacts (what the whole product consumes)

**This is the tier most likely to change scope**, and the SampleApp experience is the warning.

### 4.1 Can you export the RPD as MDS XML?

Administration Tool offline → **File → Save As → MDS XML Documents**, or:

```sh
biserverxmlgen -R <repo>.rpd -D <out-dir> -M -8
```

**Both `-M` and `-D` are required.** **Never `-Q`** — it silently drops all security objects.
**Resolves:** whether the extractor works on your estate at all.

### 4.2 Can you export the Web Catalog?

`runcat.sh` (`$DOMAIN_HOME/bitools/bin`) archive, or a copy of the catalog directory.
**Why it matters:** **82% of Analyses in a real SampleApp catalog define logic that does not exist in the RPD** — moving averages, running totals, `AGO`, ranking. Without the catalog, an as-is document is missing most of the actual computation, silently.

### 4.3 Better than 4.1 + 4.2 — can you get a BAR file?

A BI Archive contains **both the RPD and the catalog from the same service instance**. One ask instead of two, and it guarantees the halves match — which is the pairing problem that makes FR-7 untestable on public data.
**Ask for this first.**

### 4.4 Which OBIEE or OAS version?

**Resolves:** §15 Q2. Our corpus is 2013–2014 vintage; a version gap shows up as `unread_attribute` entries in `unparsed.csv` rather than as failures, so it is detectable but must be looked for.

### 4.5 Is Usage Tracking enabled?

A separate database schema recording which reports are actually run. **The best migration-prioritisation input there is** — it distinguishes the dashboards that matter from the ones nobody has opened in two years. PRD §6.2 lists dead-report detection as out of scope, but for scoping the work it is worth knowing it exists.

---

## Tier 5 — data access (Epic 6 only)

Not needed for extraction or analysis. Needed for parity.

### 5.1 Do **you** have read access to the warehouse?

Under your own account. **NFR11: no service account, no new access path** — and specifically **not** the OBIEE connection-pool credentials, which are service accounts.

### 5.2 What programmatic path exists?

`nqcmd`, JDBC, ODBC, or direct database connection. **Resolves:** §15 Q5 and the §4.8 assumption that programmatic access exists at all, not just UI access.

### 5.3 Can the new tables be queried too?

Parity compares old against new; both sides must be reachable.

---

## Tier 6 — the review loop (PRD §4.10 assumptions)

### 6.1 Is Git reachable from the VDI, and which host?

GitHub.com, GitHub Enterprise, or an internal instance. **Resolves:** §15 Q13.
**If unreachable:** the markdown-and-diff review loop the PRD chose does not work, and the artifact-format decision needs revisiting.

### 6.2 Do reviewers and approvers have access to it?

**Resolves:** §15 Q12. A stakeholder without access reintroduces a document-conversion step that §9 explicitly excluded.

### 6.3 Is Estate metadata acceptable in version control?

**Resolves:** §15 Q15. The Knowledge Base contains verbatim metric logic and object names. In our development corpus it also contained a credential — now redacted, but the general risk is real.

---

## Quick summary to bring back

| Tier | Question | Blocks |
|---|---|---|
| 1 | Python ≥3.11, runs from a copy | **Everything** |
| 2 | Copilot: executes commands? reads skills? | Automation, not capability |
| 3 | Offline wheel install, no admin | Parity only |
| 4 | RPD export · **catalog export** · BAR | What can be analysed |
| 5 | Your own query access | Parity only |
| 6 | Git reachable, reviewers have access | The review loop |

**If you can only ask three things:** items **1.2** (does it run), **4.3** (can we get a BAR), and **2.2** (can Copilot execute). Those three determine whether this is a product, a manual tool, or neither.
