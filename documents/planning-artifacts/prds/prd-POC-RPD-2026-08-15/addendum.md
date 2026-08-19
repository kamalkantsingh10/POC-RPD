# Addendum — OBIEE → Power BI Migration Assistant

Depth that belongs downstream (architecture, solution design) or earned a place but does not fit the PRD's main narrative. Companion to `prd.md`.

---

## A1. Rejected alternatives and the reasoning behind them

### A1.1 Naming the per-group artifact "LLD" rather than "Spec"

**Rejected.** The original framing called it an LLD. BMad ships `bmad-spec`, and the chain downstream of it — `bmad-create-epics-and-stories` → `bmad-build` — consumes specs natively. Naming the artifact a Spec means the existing pipeline picks it up with no custom adapter; naming it an LLD would require building glue between a bespoke document format and the shipped pipeline. Same document, but one name is free and the other costs a workstream.

### A1.2 Folding specification authoring into Winston (the Architect)

**Partially rejected.** The original instinct was that specifications could be part of the Architect's remit. The distinction that decided it is *frequency*:

- The **Migration Spine** is written **once for the Estate** — it defines the invariants that keep independently-migrated Report Groups consistent. That is precisely what an architecture spine is for, so it belongs to Winston.
- The **Group Spec** is written **once per Report Group** — an instance of applying that spine.

Folding both into Winston would mean re-deriving the mapping rules on every Report Group. That is token cost paid repeatedly, and worse, it is a source of inconsistency: the same OBIEE construct mapped two different ways in two different Specs. Consistency is what the spine exists to guarantee.

### A1.3 Per-Dashboard extraction

**Rejected.** Extraction scoped to the Dashboard being migrated would be cheaper per run and superficially matches the iterative operating model. It was rejected because Dashboards are the unit of *work* but Semantic Models are the unit of *reuse*. Without an Estate-wide picture, the tool cannot know that a Subject Area's model already exists, and each Dashboard rebuilds it — producing the same measure defined slightly differently in two places. That is metric drift, and it is the accuracy failure mode the product exists to prevent.

Extraction and migration therefore run at different frequencies: extract once for the Estate, migrate one Dashboard at a time against that picture.

### A1.4 Forking BMad skills to add capability

**Rejected.** Additions are made via `_bmad/custom/<skill>.toml` overrides. The merge rules key menu arrays by `code`, so a new entry appends and shipped entries are untouched. Forking would break on BMad upgrade and would undermine the "adaptation, not construction" premise the whole product rests on.

### A1.5 Building an agent framework

**Never seriously considered, but worth recording.** BMad is already installed and operating in both target clients. The great majority of the pipeline — PM, Dev, sprint planning, code review, retrospectives, epics and stories — is used exactly as shipped. Only four things are genuinely new: the Python extractor, the Migration Spine menu option, the Group Spec skill, and the Parity Agent.

---

## A2. Component inventory — reuse versus addition

| Component | Status | Detail |
|---|---|---|
| John (PM) | **as shipped** | `bmad-prd`, `bmad-create-epics-and-stories`, `bmad-sprint-planning`, `bmad-correct-course` |
| Amelia (Dev) | **as shipped** | `bmad-build`, `bmad-code-review`, `bmad-retrospective` |
| Mary (Analyst) | **as shipped** | brainstorming, research, briefs |
| Winston (Architect) | **extended** | +1 menu entry for the Migration Spine, added via `_bmad/custom/bmad-agent-architect.toml` |
| Group Spec skill | **new** | Applies the Spine to the Knowledge Base per Report Group |
| Parity Agent | **new** | The only genuinely new agent. No shipped skill covers data parity — `bmad-qa-generate-e2e-tests` writes application E2E tests, `bmad-code-review` reviews code |
| `rpd-extract` package | **new** | Deterministic Python. Not an agent. |
| MCP configuration | **new** | Data connectivity for parity |

Packaging this as a formal BMad module is worth evaluating — `bmad-module-builder` exists for exactly this. Deferred until the skills stabilise; premature modularisation would slow Phase 0.

---

## A3. Parity-critical extraction detail

The constructs below are boring, mechanical, and deterministic — which is exactly why they belong in Python and never in an LLM. Each of them silently changes a number when missed, and none of them changes the formula, so they are invisible to a reviewer comparing formulas alone.

- **Aggregation rule per logical column**, including dimension-specific aggregation overrides (SUM by product, AVG by time). Determines measure semantics in the target.
- **Logical Table Source priority and fragmentation predicates.** The same measure resolving to different physical tables depending on date range or dimension value. The single most dangerous construct to miss, because the formula looks identical.
- **Content-level filters on each LTS.** Effectively invisible WHERE clauses applied before anything the report author wrote.
- **Inner versus left-outer joins in the BMM layer.** Changes row counts, never changes the formula.
- **Time-series functions** — `AGO`, `TODATE`, `PERIODROLLING`. No clean DAX equivalent; these require genuine translation patterns defined once in the Migration Spine.
- **Session and repository variables** referenced in filters and formulas.
- **The physical → logical → presentation rename chain.** Three names for one column, and only the third appears in the report.
- **Implicit fact column** per Subject Area. Determines which fact table a query lands on when the query is otherwise ambiguous.
- **Row-level security filters per application role.**

---

## A3b. Output formats — the decision and what it discarded

The output formats were settled in two moves. The first specified Word for narrative documents and Excel for analysis, on the reasonable grounds that the artifacts are read by business-facing people who work in Office. The second reversed it once GitHub entered the picture: markdown for documents, CSV for tables.

**Why the reversal is right.** With a repository in play, markdown stops being a developer-only format. GitHub renders headings, tables, and navigation, and its review tooling gives inline comments that flow back to the source — a better review loop for a Group Spec than circulating a `.docx` and reconciling three people's tracked changes. CSV likewise loses little: it opens in any spreadsheet, and unlike a binary workbook it produces a readable diff, so a reviewer can see exactly what an extraction changed.

**What was genuinely given up.** Multiple sheets in one file — the Knowledge Base becomes a directory rather than a workbook. Frozen header rows, column sizing, and typed numeric columns. For a very wide table opened raw, a workbook is a nicer reading experience. These are real losses, judged worth it for diffability and zero dependencies.

**The trap that was avoided.** `pandoc` and `LibreOffice` are the conventional route from markdown to Word, and both were found already installed on the development machine. Both are system binaries requiring administrator installation, so a rendering path built on either would have worked perfectly in development and failed in the VDI. Because they are already present locally, that dependency could have been acquired without anyone deciding to acquire it. The exclusion is recorded in §9 rather than left to judgement for exactly that reason. `python-docx` and `openpyxl` would have satisfied the no-admin rule, but with the format decision reversed they are no longer needed at all.

**The consequence that matters most.** With markdown and CSV as the only output formats, the extractor needs **no third-party Python dependency**. The no-admin, offline, vendored-wheel constraint stops being something to engineer around and becomes a property of the design.

**The one thing that must be designed, not assumed.** CSV opened in a spreadsheet application is not lossless. Excel interprets any cell beginning with `=`, `+`, `-`, or `@` as a formula, strips leading zeros, and converts long numeric strings to scientific notation. The Knowledge Base carries OBIEE formula text captured character-for-character (FR-2), so this directly attacks the product's central accuracy claim. FR-28 exists to make it a tested requirement — including a write / open / save / re-read round-trip against real OBIEE formula text — rather than a convention someone remembers.

---

## A4. Technical direction (for the architecture phase, not the PRD)

- **Knowledge Base as Excel.** Chosen because it serves an Operator reading it and an agent consuming it, and because the team already works in Excel. A machine-only format would be cheaper to produce but would forfeit the standalone Phase 0 value that de-risks the whole project. Internally the extractor may use a normalised intermediate representation; Excel is a rendering of it.
- **PBIP/TMDL as target.** Text-based, therefore generatable by an agent, diffable in review, and version-controllable. Also readable *back*, which is the enabler for regenerating documentation from a live model later.
- **Two parsers, not one.** RPD (semantic layer) and Web Catalog (report layer) are separate formats with separate export mechanisms and separate risk profiles. Phasing them separately is deliberate.
- **Stable identifiers.** Every Knowledge Base row needs an identifier stable across regenerations, so Specs can reference extracted source and traceability survives a re-extract.
- **Tolerance handling in Parity Checks.** Floating-point and rounding differences between OBIEE and Power BI are expected. Tolerance must be configurable, recorded with each result, and never defaulted silently.

---

## A5. Ideas recorded but deliberately not built

These belong in the pitch, not the backlog. Each follows cheaply from the Knowledge Base once it exists.

- **Living documentation** — regenerate Group Specs from PBIP/TMDL so documentation cannot go stale. Documentation that cannot regenerate becomes worse than none, because people trust it. This is the fix, and it is a Phase 3 conversation.
- **Spec-driven BI** — invert the flow: the Spec becomes source, the model becomes generated output. This is the line between an internal migration tool and a product.
- **Estate analytics** — impact analysis ("what breaks if we change this table"), dead-report detection, duplicate-metric detection across business units, a searchable metric dictionary for onboarding.
- **Retargeting** — the same extraction and spine pattern applied to a different source or target platform.

---

## A6. The strategic framing

Recorded because it shapes prioritisation, not because it is a requirement.

**The migration is the funding event. The documented semantic estate is the asset that outlives it.**

Nobody funds a project to document an OBIEE landscape. Everybody funds a Power BI migration. Complete the migration and the organisation owns a complete map of every metric it has defined — which then serves ongoing maintenance of the Power BI estate.

The design implication is concrete and non-obvious: **the Group Spec is not a byproduct of the pipeline; it is the point of it.** Power BI generation is what gets the Spec funded. Where the two compete for effort, the Spec wins.
