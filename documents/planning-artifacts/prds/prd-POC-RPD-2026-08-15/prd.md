---
title: OBIEE → Power BI Migration Assistant
status: final
created: 2026-08-15
updated: 2026-08-16
amendments:
  - '2026-08-16 — SampleApp unobtainable. FR-30, FR-31, §6.1, §10, §11, §14, §16 amended per documents/planning-artifacts/sprint-change-proposal-2026-08-16.md'
---

# PRD: OBIEE → Power BI Migration Assistant

*Working title — confirm.*

> **Amendment, 2026-08-16 — SampleApp is unobtainable.**
> Story 1.1 confirmed the SampleApp appliance is no longer published by Oracle, on the public site or on edelivery, and no Oracle licence is held. The Test Corpus is instead sourced from two pinned public GitHub repositories containing genuine OBIEE **MDS XML** — a real working estate and a SampleApp-derived repository — carrying **RPD metadata only: no Web Catalog and no live data.**
> Amended: **FR-30** (tiers apply to Subject Areas, not Dashboards), **FR-31** (Constructed Cases hand-authored as MDS XML), **§6.1** (the hand-run Parity Check is removed), plus §10, §11, §14 and §16.
> Rationale and full impact analysis: `documents/planning-artifacts/sprint-change-proposal-2026-08-16.md`.

## 0. Document Purpose

This PRD is for the product owner (Kamal), the team who will operate the tool, and the downstream BMad workflows that consume this document — `bmad-architecture`, `bmad-create-epics-and-stories`, and `bmad-build`. It is structured Glossary-first: every domain noun is defined once in §3 and used verbatim throughout. Features are grouped in §4 with globally-numbered Functional Requirements nested beneath them; assumptions are tagged inline as `[ASSUMPTION]` and indexed in §16.

It builds on `documents/brainstorming/brainstorm-obiee-rpd-to-powerbi-pipeline-2026-08-15/brainstorm-intent.md`, which contains the settled direction and the reasoning behind the core decisions. That document is not duplicated here. Technical alternatives considered and rejected are recorded in `addendum.md` alongside this file.

A defining constraint on this product: **it is an adaptation, not a new system.** BMad is already installed and operating. The great majority of the agent pipeline — PM, Dev, sprint planning, code review, retrospectives — is used exactly as shipped. This PRD scopes only what must be *added*.

## 1. Vision

Migrating an OBIEE estate to Power BI is bottlenecked long before anyone opens Power BI. The expensive work is *understanding the RPD* — tracing what a metric actually computes, which physical tables it resolves to, which of its logical sources fires under which conditions, and which of those details will silently change a number if missed. Today that work is manual, slow, and concentrated in the few people who can do it. The team is not short of Power BI skill; it is short of hours spent decoding OBIEE.

The Migration Assistant addresses this in two stages. A deterministic Python extractor reads the RPD and the Web Catalog and produces an **Estate Knowledge Base** — a set of CSV tables, readable in any spreadsheet and diffable in git, capturing every metric's exact logic and its full lineage to physical tables. On top of that, a small set of added BMad skills drive the existing agent pipeline: Winston authors a **Migration Spine** once for the whole estate, a new skill writes a **Group Spec** per report group, Amelia generates Power BI project files, and a new **Parity Agent** compares the migrated numbers against the legacy report using live data.

**The thesis this product bets on is that the hard problem is verification, not translation.** An LLM can plausibly convert an OBIEE metric into DAX; what it cannot do unaided is prove the conversion is right. Every objection this product has drawn — how do we know the report can be trusted, what happens when bugs are reported, how do we produce quality consistently — is about what happens *after* generation. The three conditions under which this project should be abandoned are the same shape: **accuracy too low, too many hours spent debugging output, defects reaching production.** None of them is a failure to build; all of them are failures to verify cheaply. The architecture follows from that. Deterministic extraction removes an entire class of error before an agent sees anything; the Group Spec makes judgement reviewable; the Parity Agent makes correctness measurable. Features that make generation more capable rank below features that make it checkable.

The tool is explicitly an assistant, not an autopilot. Its output quality is capped by the experience of the person operating it, and it is designed around that fact: the Group Spec is where senior judgement is captured, reviewed, and reused. The strategic prize sits beyond the migration itself — when the last dashboard is ported, the organisation owns a complete, maintained, machine-readable map of every metric it has ever defined. The migration is what pays for that map.

## 2. Target User

### 2.1 Jobs To Be Done

- **Functional** — port an OBIEE dashboard to Power BI without spending days manually decoding the RPD first.
- **Functional** — know, with evidence rather than hope, that a migrated report returns the same numbers as the original.
- **Functional** — hand a migrated report to someone else six months later with documentation that explains what it does and where its data comes from.
- **Social** — stand in front of the team, or a stakeholder, and defend a migrated number without hedging.
- **Emotional** — stop dreading the tangled dashboards and stop deferring them to the end of the project.
- **Contextual** — do all of the above inside a locked-down VDI, without admin rights, without internet access, and without a framework nobody is allowed to install.

### 2.2 Non-Users (v1)

- **Business users and report consumers.** They never touch the tool; they receive migrated reports.
- **People with no OBIEE knowledge.** The tool multiplies expertise; it does not substitute for it. An operator who cannot judge whether a Group Spec is correct cannot safely use it.
- **Other teams and other organisations.** v1 targets this team, this estate, this VDI. Generalisation is out of scope.

### 2.3 Key User Journeys

- **UJ-1. Kamal proves the concept to a sceptical room.**
  Kamal, who needs approval before he can spend real time on this, has one meeting. He runs the extractor against the estate's RPD export and gets the Knowledge Base in under a minute. He opens the logical-columns table in a spreadsheet and finds one notoriously tangled metric — its exact formula, its aggregation rule, its three logical sources and the conditions under which each fires. He then shows the Group Spec the tool generated for that report group. The senior OBIEE analyst in the room reads it and agrees it is correct. **Climax:** the room sees, on real reports, that days of manual decoding were done in seconds and the result stands up to expert review. **Resolution:** approval to proceed to Phase 1. **Edge case:** if the expert disagrees with the Spec, that disagreement is itself the deliverable — it produces a measured accuracy number rather than a failed demo.

- **UJ-2. Priya migrates her third dashboard of the week.**
  Priya is a BI developer, comfortable in Power BI, moderate in OBIEE. She picks the next dashboard off the estate backlog. The tool reads the Estate Knowledge Base, sees that this dashboard's subject area already has a Semantic Model built by an earlier migration, and produces a Group Spec that says *"reuse the existing model; add two measures; no new tables."* She reviews the two measures, approves them, and runs the build. Amelia writes the PBIP files. The Parity Agent runs both the legacy and migrated queries and reports 14 of 14 checks matching. **Climax:** she opens the report and the numbers are right on the first pass. **Resolution:** dashboard marked done, story closed, next one picked. **Edge case:** three checks fail; she gets a triage list naming which measures diverged and by how much — she is debugging three named items, not hunting through a whole model.

- **UJ-3. Ravi is handed a migrated report he has never seen.**
  Ravi, six months after the migration, is asked why a figure on a Power BI report looks wrong. He opens the Group Spec for that report group and reads the exact logic of the measure, its lineage to the source tables, and the RLS rules applied. **Climax:** he answers the question in minutes without opening OBIEE or asking the person who built it. **Resolution:** the documentation earns its keep after the migration is over — the outcome this product is ultimately for.

## 3. Glossary

- **RPD** — the OBIEE repository file containing the semantic layer: Physical, Business Model & Mapping, and Presentation layers. The source of truth for all metric logic.
- **Physical Layer** — RPD layer describing source database tables, columns, and physical joins.
- **BMM Layer** *(Business Model & Mapping)* — RPD layer holding logical tables, logical columns, aggregation rules, and Logical Table Sources.
- **Presentation Layer** — RPD layer exposing Subject Areas to report authors; the names business users see.
- **Subject Area** — a Presentation Layer grouping of columns. The natural unit of a Power BI Semantic Model.
- **Logical Table Source (LTS)** — a mapping from a logical table to physical tables, with priority, fragmentation predicates, and content-level filters.
- **Web Catalog** — the OBIEE store of Analyses and Dashboards, separate from the RPD.
- **Analysis** — a single OBIEE query definition with its columns, filters, and views.
- **Dashboard** — an OBIEE page container holding tabs, Analyses, and prompts. The unit of migration work.
- **Estate** — the complete set of RPD content and Web Catalog content in scope for migration.
- **Estate Knowledge Base** *(or Knowledge Base)* — the set of CSV tables produced by deterministic extraction from the whole Estate. One CSV per concern, held together in a single directory. Estate-wide, parsed once, never per-Dashboard.
- **Report Group** — a set of Dashboards sharing a Subject Area, and therefore sharing one target Semantic Model.
- **Migration Spine** — the architecture document, written once for the Estate, defining how OBIEE constructs map to Power BI constructs.
- **Group Spec** *(or Spec)* — the per-Report-Group specification: the Semantic Model delta this group requires plus its report definitions. Consumed by `bmad-create-epics-and-stories` and `bmad-build`.
- **Semantic Model** — the Power BI tabular model: tables, relationships, measures, hierarchies, RLS roles.
- **PBIP / TMDL** — Power BI's text-based project and model definition formats. Diffable, generatable, version-controllable.
- **Parity Check** — an executable comparison of a legacy OBIEE result against the corresponding migrated Power BI result.
- **Parity Agent** — the added BMad agent that authors and runs Parity Checks and reports divergence.
- **Operator** — the team member running the tool. Assumed OBIEE-literate.
- **Migration Module** — the packaged deliverable: added BMad skills, agent definitions, customization TOML, the extractor package, and MCP configuration.
- **Narrative Artifact** — a document written to be read: Group Spec, Migration Spine, reports. Markdown, rendered by GitHub.
- **Tabular Artifact** — an artifact whose content is rows and columns: Knowledge Base tables, Parity Check results, coverage and accuracy reports. CSV, opened in any spreadsheet.
- **Working File** — an artifact consumed by the pipeline rather than read by a human: stories, epics, agent definitions, configuration. Markdown or TOML.
- **Test Corpus** — the Estate used to develop and prove the product. *Amended 2026-08-16: two pinned public MDS XML repositories — a real working estate and a SampleApp-derived repository — plus Constructed Cases. RPD metadata only; no Web Catalog, no live data.*
- **Constructed Case** — a deliberately authored OBIEE construct that exercises a known parity hazard, carrying a recorded Ground Truth. *Amended 2026-08-16: authored directly as MDS XML; the Administration Tool is unavailable.*
- **Ground Truth** — the known-correct expected result for a Constructed Case, recorded when the case is authored. Turns accuracy measurement from expert judgement into fact.
- **Comparison Report** — the per-Dashboard artifact placing the legacy report and the migrated report side by side, covering structure, content, and numbers.

## 4. Features

### 4.1 Estate Extraction — RPD

**Description:** A deterministic Python package reads the RPD and writes its full semantic content to the Knowledge Base. No LLM is involved at any point. The governing principle for the whole product applies here most sharply: **anything deterministic happens in Python; the LLM only does what genuinely requires judgement.** This is simultaneously the accuracy control and the token-cost control — the agents never read raw RPD content, which is large, repetitive, and expensive to reason over. `[ASSUMPTION: the RPD is supplied as an XML export produced by biserverxmlgen. Parsing the proprietary binary directly is out of scope and would be a material technical risk.]`

**Functional Requirements:**

#### FR-1: Parse RPD source

The Operator can point the extractor at an RPD XML export and receive a parsed representation of all three layers. Realizes UJ-1.

**Consequences (testable):**
- All Physical Layer tables, columns, data types, and physical joins are captured.
- All BMM logical tables, logical columns, and their Logical Table Sources are captured.
- All Presentation Layer Subject Areas and presentation columns are captured.
- Parsing an RPD export with no recognised root element fails with a clear error naming the expected format, rather than producing a partial Knowledge Base.

#### FR-2: Capture exact metric logic

The extractor records the logic of each logical column exactly as written, not summarised or normalised.

**Consequences (testable):**
- Each logical column's formula is stored verbatim, character-for-character.
- No formula is rewritten, simplified, or reformatted during extraction.

#### FR-3: Capture full lineage

The extractor resolves each presentation column through the BMM layer to the physical tables and columns it depends on.

**Consequences (testable):**
- Every presentation column has a traceable path: presentation name → logical column → LTS → physical table.column.
- Columns with multiple Logical Table Sources list all of them, not just the first.

#### FR-4: Capture parity-critical metadata

The extractor captures the deterministic details that silently break numeric parity when omitted.

**Consequences (testable):**
- Aggregation rule per logical column, including dimension-specific aggregation overrides.
- LTS priority order and fragmentation predicates.
- Content-level filters defined on each LTS.
- Join type (inner vs. left outer) for each BMM join.
- Time-series function usage (`AGO`, `TODATE`, `PERIODROLLING`) flagged per column.
- Session and repository variables referenced in any filter or formula.
- The full physical → logical → presentation rename chain for every column.
- Implicit fact column per Subject Area.
- Row-level security filters per application role.

#### FR-5: Report extraction coverage

The extractor reports what it could not parse rather than silently omitting it.

**Consequences (testable):**
- Output includes a coverage summary: objects parsed, objects skipped, and the reason for each skip.
- Any construct the parser does not recognise appears in the skipped list with its source identifier.

### 4.2 Estate Extraction — Web Catalog

**Description:** A second deterministic parser reads the Web Catalog and captures the report layer: Dashboards, their tabs, the Analyses they contain, and the prompts and filters applied. This is what allows the tool to generate Power BI report content rather than stopping at the Semantic Model. `[ASSUMPTION: the Web Catalog can be exported to a parseable XML form. The export mechanism has not been confirmed.]`

**Functional Requirements:**

#### FR-6: Parse Web Catalog structure

The Operator can point the extractor at a Web Catalog export and receive the Dashboard and Analysis inventory. Realizes UJ-2.

**Consequences (testable):**
- Each Dashboard is captured with its tabs and the Analyses placed on each tab.
- Each Analysis is captured with its selected columns, filters, and view types.
- Dashboard prompts and their bound columns are captured.

#### FR-7: Resolve catalog to semantic layer

Each Analysis column is resolved to its Presentation Layer column, and each Dashboard is assigned to a Report Group.

**Consequences (testable):**
- Every Analysis column maps to a named presentation column, or is listed as unresolved with a reason.
- Every Dashboard is assigned to exactly one Report Group based on the Subject Areas its Analyses use.
- A Dashboard drawing on more than one Subject Area is flagged for Operator decision rather than assigned arbitrarily.

### 4.3 Estate Knowledge Base

**Description:** The extraction output lands as a set of CSV tables in one directory, structured for two audiences at once: an Operator reading it to understand a metric, and an agent reading it as machine input. CSV is chosen over a spreadsheet workbook for three reasons — it opens in any spreadsheet application, it requires no third-party Python dependency, and it diffs line by line in git, so a reviewer can see exactly what changed between two extractions. A binary workbook would forfeit the third entirely.

The Knowledge Base is produced **once for the whole Estate** and refreshed only when the source changes. This is deliberate and load-bearing — per-Dashboard extraction would make cross-Dashboard reuse undetectable and cause metric drift.

The Knowledge Base has standalone value independent of everything downstream: it automates analysis the team performs manually today, and it produces understanding rather than code, so it cannot introduce a production defect.

**Functional Requirements:**

#### FR-8: Produce the Knowledge Base

The extractor writes a directory of CSV tables containing the parsed Estate. Realizes UJ-1, UJ-3.

**Consequences (testable):**
- Tables are separated by concern: physical objects, logical objects and their formulas, lineage, presentation columns, security, dashboards, analyses, and a coverage summary.
- Each table opens in a spreadsheet application with its columns correctly separated.
- Every row carries a stable identifier usable as a reference from a Group Spec.
- Regenerating from unchanged source produces byte-identical files, so an unchanged extraction shows no diff.
- A manifest file lists the tables present, the extraction source, and the extraction timestamp.

#### FR-9: Estate-wide scope enforcement

The Knowledge Base covers the entire Estate regardless of which Dashboard is being migrated.

**Consequences (testable):**
- The extractor accepts no per-Dashboard scoping argument that would produce a partial Knowledge Base.
- Migration of any Dashboard reads from the same single Knowledge Base.

**Notes:** `[NOTE FOR PM]` The Knowledge Base is the artifact most likely to be wanted by people outside this workflow. Consider whether it should be published somewhere the wider team can read it, independent of the migration.

### 4.4 Migration Spine

**Description:** Winston (`bmad-agent-architect`) gains one added menu option that produces the Migration Spine: a single architecture document, written once for the Estate, defining how OBIEE constructs map to Power BI constructs. It exists so that mapping decisions are made once and applied consistently, rather than re-derived by an LLM on every Report Group — which would be both expensive and inconsistent.

This is delivered as a customization override, not a fork. A new menu entry is added via `_bmad/custom/bmad-agent-architect.toml`; the shipped skill is not modified.

**Functional Requirements:**

#### FR-10: Author the Migration Spine

The Operator can invoke Winston to produce a Migration Spine from the Knowledge Base.

**Consequences (testable):**
- The Spine defines the mapping for every OBIEE construct type present in the Knowledge Base.
- The Spine covers, at minimum: aggregation rule semantics, time-series functions (`AGO`, `TODATE`, `PERIODROLLING`) to DAX time-intelligence patterns, LTS fragmentation handling, BMM join type handling, RLS role mapping, and naming conventions.
- Any construct present in the Knowledge Base with no defined mapping is listed explicitly as an open decision rather than left unmentioned.

#### FR-11: Extend the Architect without forking

The Migration Spine capability is added to the Architect agent by configuration override.

**Consequences (testable):**
- No file under `.claude/skills/bmad-agent-architect/` is modified.
- The new menu entry appears in Winston's menu alongside the shipped entries.
- A BMad upgrade that replaces shipped skill files does not remove the added entry.

### 4.5 Group Spec Generation

**Description:** A new skill produces a Group Spec per Report Group by applying the Migration Spine to the Knowledge Base. The Spec is the artifact where senior judgement is captured and made reviewable — the mechanism by which an experienced Operator's expertise is encoded once and reused, rather than re-supplied on every Dashboard.

The Spec is **additive**. Because Dashboards are the unit of work but Semantic Models are the unit of reuse, each Spec must state what already exists and is being reused, and what must be added. Without this, migrating the second Dashboard in a Report Group rebuilds the model and produces metric drift.

The artifact is deliberately named a *Spec* rather than an LLD so that the existing `bmad-spec` → `bmad-create-epics-and-stories` → `bmad-build` chain consumes it with no custom integration.

**Functional Requirements:**

#### FR-12: Generate a Group Spec

The Operator can generate a Group Spec for a Report Group from the Knowledge Base and the Migration Spine. Realizes UJ-2, UJ-3.

**Consequences (testable):**
- The Spec states the target Semantic Model's tables, relationships, measures, hierarchies, and RLS roles.
- Every measure in the Spec carries its source OBIEE logic verbatim alongside its proposed DAX.
- Every table in the Spec carries its lineage to physical source tables.
- The Spec states the report definitions for the Dashboards in the group: tabs, visuals, filters, prompts.
- The Spec references Knowledge Base row identifiers so any statement can be traced to extracted source.

#### FR-13: Additive specification against existing models

A Group Spec distinguishes what already exists from what must be created.

**Consequences (testable):**
- When a Semantic Model already exists for the Report Group, the Spec lists reused objects separately from new objects.
- A Spec requiring no new Semantic Model objects states this explicitly rather than restating the whole model.
- The Spec never proposes creating an object whose equivalent already exists in the target model.

#### FR-14: Flag judgement points

The Spec surfaces decisions the tool is not qualified to make.

**Consequences (testable):**
- Any OBIEE construct with no mapping in the Migration Spine is raised in the Spec as a decision for the Operator, not silently resolved.
- Any logical column with multiple Logical Table Sources and ambiguous precedence is raised for Operator confirmation.
- The Spec records a confidence indication per measure, and low-confidence measures are listed together for review.

#### FR-15: Consumable by the existing BMad chain

The Group Spec is structured so that shipped BMad skills consume it. `[ASSUMPTION: bmad-create-epics-and-stories can produce stories from a Group Spec without a custom adapter. This is unverified — it is a claim about a shipped skill's behaviour against a document format that does not yet exist, and the decision to name the artifact a Spec rather than an LLD rests on it. A Phase 1 spike validates it before the Spec format is fixed.]`

**Consequences (testable):**
- One Dashboard corresponds to one story.
- The Spec's structure is verified against `bmad-create-epics-and-stories` by a Phase 1 spike. If a custom adapter proves necessary, that adapter is scoped as work rather than assumed away.

### 4.6 Power BI Generation

**Description:** Amelia (`bmad-agent-dev`, via `bmad-build`) is used exactly as shipped. She consumes stories derived from the Group Spec and writes Power BI project files. The target is PBIP with TMDL model definitions — chosen because they are text: generatable by an agent, diffable in review, version-controllable, and readable back later to regenerate documentation. `[ASSUMPTION: PBIP with TMDL is the correct Power BI target format for this organisation's tooling and licensing.]`

No change to Amelia is in scope. If generation proves to need migration-specific guidance, that guidance belongs in the Migration Spine, not in a modified Dev agent.

**Functional Requirements:**

#### FR-16: Generate Power BI project files

Amelia can generate PBIP/TMDL files implementing a Group Spec. Realizes UJ-2.

**Consequences (testable):**
- Generated files open in Power BI Desktop without repair.
- Generated measures correspond one-to-one with the measures specified in the Group Spec.
- Generated output is text and diffable against the previous version.
- Generation adds to an existing Semantic Model where the Spec says reuse, rather than replacing it.

**Out of Scope:**
- Publishing to a workspace, deployment pipelines, and workspace permissions.

### 4.7 Parity Validation

**Description:** A new **Parity Agent** — the only genuinely new agent in the product — authors and runs Parity Checks: executing the legacy OBIEE query and the migrated Power BI query against live data and comparing results. This is the feature that addresses all three of the named project-killers, and it is the reason the product is viable at all. Nothing shipped with BMad covers it: `bmad-qa-generate-e2e-tests` writes application E2E tests and `bmad-code-review` reviews code; neither compares data.

Validation is expected to run per story, so a Dashboard is not considered migrated until its Parity Checks pass.

**Functional Requirements:**

#### FR-17: Author Parity Checks from a Group Spec

The Parity Agent can derive a set of Parity Checks for a migrated Dashboard.

**Consequences (testable):**
- Each measure in the Group Spec has at least one Parity Check.
- Checks cover unfiltered totals and at least one filtered slice per measure.
- Checks include the dimension combinations the source Dashboard actually displays.

#### FR-18: Execute Parity Checks against live data

The Parity Agent can execute both sides of a Parity Check and compare results. Realizes UJ-2.

**Consequences (testable):**
- The legacy result is obtained by querying OBIEE or its underlying warehouse.
- The migrated result is obtained by querying the generated Power BI model.
- Numeric comparison applies a configurable tolerance; the tolerance in force is recorded with the result.
- A check that cannot execute is reported as *errored*, never as *passed*.

#### FR-19: Report divergence as a triage list

Parity results are presented as named, actionable items.

**Consequences (testable):**
- Output states checks passed, failed, and errored.
- Each failure names the measure, the filter context, the expected value, the actual value, and the difference.
- Failures are grouped by probable cause where the Knowledge Base supports the inference (for example, aggregation rule mismatch or missing content filter).

#### FR-20: Parity gate before completion

A story is not completable while its Parity Checks fail.

**Consequences (testable):**
- Story completion requires a recorded Parity Check run with zero failures, or an explicit recorded Operator override with a reason.
- Overrides are logged and visible in the migration record.

### 4.8 Data Connectivity

**Description:** Agents reach OBIEE and the warehouse through MCP servers. The policy position is settled: the Operator can already query this data, so the tool queries it with the same access and exposes nothing new. What is not yet settled is the mechanism — the MCP servers must be installable and operable inside the VDI. `[ASSUMPTION: programmatic query access — nqcmd, JDBC, or ODBC — is available, not only human UI access.]`

**Functional Requirements:**

#### FR-21: Query legacy data via MCP

The Parity Agent can execute a query against the legacy source through a configured MCP server.

**Consequences (testable):**
- Connection configuration is external to agent definitions and holds no embedded credentials.
- The tool operates under the Operator's own access rights; no elevated or service account is introduced.
- A query the Operator is not permitted to run fails with a permission error and is reported as errored.

#### FR-22: Query the migrated model

The Parity Agent can execute a query against the generated Power BI Semantic Model.

**Consequences (testable):**
- Queries execute against the model as generated, without manual publication steps during Phase 2 validation. `[ASSUMPTION: a local or workspace query path is available; the mechanism is unconfirmed.]`

### 4.9 Packaging and Portability

**Description:** The deliverable is a **Migration Module**: added skill markdown, agent customization TOML, the Python extractor package, and MCP configuration. Porting to the VDI is a file copy, not an installation project. This is not a compromise forced by the environment — plain Python, markdown, and CSV are more portable, more inspectable, and more teachable than any framework, and they largely answer the training question by themselves.

**Functional Requirements:**

#### FR-23: No-admin installation

Every dependency installs without administrator rights.

**Consequences (testable):**
- Installation succeeds as an unprivileged user via `pip --user`, a virtual environment, or vendored wheels.
- No dependency requires a compiled extension built at install time, a system package, or a service.
- Installation succeeds with no internet access, from a pre-staged dependency bundle.

#### FR-24: Markdown and configuration only

All agent and skill definitions are plain text.

**Consequences (testable):**
- Every added agent and skill definition is a markdown or TOML file.
- No added component requires a runtime beyond Python and the AI client already present.
- Copying the Migration Module directory into a comparable environment yields a working installation.

#### FR-25: Runtime portability

The Migration Module operates under both AI clients in use.

**Consequences (testable):**
- Added skills function under Claude Code and under the VDI's Copilot client. `[ASSUMPTION: the VDI Copilot client can read markdown skill definitions and invoke local Python. Its exact capabilities are unconfirmed and this is the single largest portability risk.]`
- No added component depends on a capability present in only one client.

### 4.10 Artifact Formats

**Description:** Every artifact is plain text. **Narrative Artifacts are markdown; Tabular Artifacts are CSV.** Both are readable as-is, both are diffable in git, and neither requires a third-party library to produce.

The decision rests on the repository. `[ASSUMPTION: the Migration Module and its outputs live in a GitHub repository, and the people who review Group Specs have access to it.]` Because the Migration Module and its outputs live in GitHub, markdown is not a developer-only format — GitHub renders headings, tables, and navigation, and its review tooling lets a reviewer comment inline and have those comments flow back to the source. That is a better review loop than circulating a binary document, not a worse one. `[ASSUMPTION: GitHub's markdown rendering and inline review comments are an acceptable review loop for Group Specs; no circulated document format is required.]` CSV is likewise not a downgrade from a spreadsheet workbook: it opens in any spreadsheet application, and unlike a binary workbook it produces a readable diff, so a reviewer can see precisely what changed between two extractions. `[ASSUMPTION: reviewers are willing to open CSV in a spreadsheet application rather than receiving a formatted workbook.]`

| Artifact | Audience | Format |
|---|---|---|
| Group Spec | OBIEE reviewer, future maintainer | **Markdown** |
| Migration Spine | Architect, reviewer | **Markdown** |
| Estate Knowledge Base | Operator, analyst | **CSV** |
| Parity Check results | Operator, approver | **CSV** |
| Coverage and accuracy reports | Approver, stakeholders | **CSV** |
| Stories, epics, sprint tracking | The pipeline | **Markdown** |
| Agent and skill definitions, configuration | The pipeline | **Markdown / TOML** |

The consequence for §9 is significant: **the extractor requires no third-party Python dependency at all.** Markdown is text and CSV is in the standard library, so the no-admin, offline installation constraint is satisfied structurally rather than engineered around.

Narrative Artifacts carry a writing standard. They are read by busy people who did not write them, often months later. Prose is direct and concrete; sentences are short; structure is visible at a glance through headings and tables. Padding, hedging, and restating the obvious are defects in this context, not stylistic preferences.

**Functional Requirements:**

#### FR-26: Deliver Narrative Artifacts as markdown

Group Specs, the Migration Spine, and written reports are markdown files in the repository. Realizes UJ-1, UJ-3.

**Consequences (testable):**
- Every Narrative Artifact renders correctly on GitHub, including tables and nested lists.
- OBIEE formulas and DAX expressions appear in fenced code blocks so they are never reflowed or auto-formatted.
- Each artifact is a single file with a stable path, so it can be linked and reviewed.
- No conversion or rendering step is required before a human can read it.

#### FR-27: Deliver Tabular Artifacts as CSV

The Knowledge Base, Parity Check results, and coverage and accuracy reports are CSV files. Realizes UJ-1, UJ-2.

**Consequences (testable):**
- Each file has a single header row and one record per line.
- Files are UTF-8 encoded with a documented delimiter and consistent line endings.
- Files open in a spreadsheet application with columns correctly separated and no manual import configuration.
- Related tables share stable identifiers so they can be joined by a reader or an agent.

#### FR-28: Spreadsheet-safe CSV integrity

CSV content survives being opened in a spreadsheet application without alteration. This protects FR-2, which requires formula logic captured character-for-character.

**Consequences (testable):**
- All fields are quoted, so embedded commas, quotes, and newlines round-trip intact.
- Any field whose value begins with `=`, `+`, `-`, or `@` is written so a spreadsheet application does not interpret it as a formula.
- Identifier-like values do not lose leading zeros or convert to scientific notation on open.
- A round-trip test — write, open in a spreadsheet, save, re-read — produces the original values for a corpus including real OBIEE formula text.

#### FR-29: Narrative Artifacts meet the readability standard

Documents are written for a human reader, not a machine.

**Consequences (testable):**
- Each document opens with a short statement of what it covers and who it is for.
- Content is navigable by headings; a reader can locate a specific measure without reading linearly.
- Reference material — full logic listings, lineage tables, extraction detail — is presented in tables rather than prose.
- No document restates the same information in two places.

**Notes:** `[NOTE FOR PM]` If any stakeholder outside the repository needs a circulated document rather than a link, that requirement should be raised before Phase 1 rather than solved ad hoc. It would reintroduce a conversion step, and the conversion tools that are conventional for it are excluded by §9.

### 4.11 Test Corpus

**Description:** The product is developed and proved against Oracle's **SampleApp** rather than the organisation's own Estate. This is a deliberate decision taken because the real Estate is not obtainable, and it turns out to be an advantage rather than a concession.

SampleApp ships as a VirtualBox appliance containing a configured OBIEE 12c instance, the SampleApp RPD, a populated Web Catalog, and an Oracle Database with real data. `[ASSUMPTION: the SampleApp appliance is obtainable, runnable on available hardware, and its OBIEE version is close enough to the organisation's that the parser transfers.]` That combination gives the project everything it needs without any organisational access: the RPD can be exported to XML on demand, the catalog provides genuine dashboards, and the loaded database makes live Parity Checks possible.

SampleApp's weakness is that it is *clean*. It was authored by Oracle to demonstrate good practice, so it lacks the accumulated irregularity that makes a real repository difficult — and that irregularity is the actual difficulty of the problem. The corpus therefore extends SampleApp with **Constructed Cases**: parity hazards deliberately authored in the Admin Tool.

This produces a measurement property a real Estate could never offer. Against a real RPD, accuracy can only be judged against an expert's opinion. Against a Constructed Case, the correct answer is **known**, because it was authored deliberately and its Ground Truth recorded at the same time. Accuracy stops being a judgement call and becomes a fact. `[ASSUMPTION: Constructed Cases authored in the Admin Tool are representative enough of real-world irregularity for the accuracy claim to hold when the tool meets a real Estate.]`

**Functional Requirements:**

#### FR-30: Establish the Test Corpus

The project maintains a Test Corpus spanning three difficulty tiers. Realizes UJ-1.

*Amended 2026-08-16. Tiers apply to **Subject Areas**, not Dashboards: the corpus contains no Web Catalog. The Subject Area is this document's own "natural unit of a Power BI Semantic Model" (§3), so it is the correct unit rather than a convenient one.*

**Consequences (testable):**
- **Simple tier** — Subject Areas whose measures use a single Logical Table Source, a default aggregation rule, and no time-series function.
- **Medium tier** — Subject Areas containing at least one measure with either multiple Logical Table Sources, a non-default aggregation rule, or a time-series function.
- **Tangled tier** — Constructed Cases authored specifically to exercise parity hazards, per FR-31.
- Each tier contains at least two Subject Areas.
- At least two Subject Areas share logical tables, so Semantic Model reuse is exercised rather than assumed.
- The corpus is reproducible: every source is pinned to a commit SHA and every Constructed Case is documented sufficiently to rebuild from scratch.
- Tier assignment is recorded with the criterion that placed it there **and cites the Knowledge Base row identifiers evidencing that criterion**, so accuracy reported per tier is interpretable and the assignment is reproducible rather than a matter of judgement.
- **Report-layer difficulty is explicitly out of scope.** Tiering measures the difficulty of the semantic migration only. Dashboard-level difficulty — visual count, prompt complexity, drill paths — is unassessed and is not claimed.

#### FR-31: Record Ground Truth per Constructed Case

Every Constructed Case carries its known-correct expected result.

*Amended 2026-08-16. The Oracle BI Administration Tool is unavailable — no licence. Cases are authored directly as **MDS XML**, modelled on real corpus files.*

**Consequences (testable):**
- Each Constructed Case records the construct it exercises, why it is a parity hazard, and the correct extracted result.
- Ground Truth is recorded **at authoring time, before the extractor is run against the case**, so it cannot be back-fitted to whatever the extractor produced.
- **Cases are required only for constructs the corpus does not already exercise.** A construct with real corpus evidence cites that evidence instead; a real example always beats a constructed one. Measured against the corpus, four constructs need authoring — **LTS fragmentation, LTS priority order, `PERIODROLLING`, and implicit fact column** — while content-level filters, BMM join types, aggregation rules and multi-source mapping already have real evidence.
- **Each case records that it is hand-authored, and that its Ground Truth is authorial intent rather than observed OBIEE behaviour.**
- Accuracy derived from Constructed Cases is reported **separately** from accuracy measured against real corpus content, and the two are never merged into a single figure.

### 4.12 Migration Comparison Report

**Description:** For each migrated Dashboard the product produces a Comparison Report placing the legacy report and the migrated report side by side. Numeric parity (§4.7) proves the migration is *correct*; the Comparison Report is what makes that correctness *visible* to someone who will not read a parity table.

The report claims **structural and data equivalence, not visual identity.** Power BI and OBIEE use different rendering engines and chart libraries, so pixel-level similarity is neither achievable nor pursued. Overstating this is a demo risk in its own right: a claim of "it looks the same" invites a reviewer to reject the migration over a font. `[ASSUMPTION: the approval audience accepts structural and data equivalence, demonstrated side by side, as sufficient evidence; visual identity is not expected of a platform migration.]` The report therefore states what is equivalent — tabs, visuals, their order, columns, filters, and numbers — and states plainly what differs and why.

This is also the artifact the approval audience actually reads, and the natural home for the client-facing presentation output the product is expected to produce.

**Functional Requirements:**

#### FR-32: Produce a side-by-side Comparison Report

The product generates a Comparison Report per migrated Dashboard. Realizes UJ-1, UJ-2.

**Consequences (testable):**
- The report shows the legacy and migrated versions of each dashboard tab together, as captured images.
- Numeric Parity Check results for the Dashboard appear in the same report, so structure and numbers are assessed in one place.
- The report is a Narrative Artifact and renders on GitHub without a conversion step.

#### FR-33: Map every legacy view to its migrated counterpart

The Comparison Report inventories the report layer rather than only depicting it.

**Consequences (testable):**
- Every OBIEE view in the source Dashboard is listed with the Power BI visual that replaces it.
- Tab order, visual order within a tab, displayed columns, and applied filters and prompts are compared item by item.
- Any legacy view with no migrated counterpart is listed as a gap, never omitted.

#### FR-34: State divergence honestly

The report distinguishes equivalence from similarity.

**Consequences (testable):**
- The report explicitly claims structural and data equivalence, not visual identity.
- Known and accepted presentation differences — chart styling, fonts, colour, formatting — are listed as expected rather than presented as defects.
- Any difference in displayed data, column set, filter behaviour, or ordering is reported as a defect, not as a styling difference.

**Feature-specific NFRs:**
- Captured screenshots are the one exception to the plain-text principle in §7. They are captured evidence rather than a generated document format, they are referenced from markdown, and they introduce no conversion dependency.

**Notes:** `[NOTE FOR PM]` Screenshot capture may be manual in Phase 0. Automating it is worthwhile only if the corpus grows beyond what a person will patiently capture by hand.

## 5. Non-Goals (Explicit)

- **Not an autopilot.** The product does not run unattended end to end. It multiplies an experienced Operator's throughput and its quality is bounded by that Operator's judgement.
- **Not a redesign.** Migration is strictly as-is. No enhancements, no opportunistic improvements, no silent corrections of legacy behaviour. Where the legacy report is wrong, the migrated report reproduces it and the Spec notes it.
- **Not a general-purpose migration product.** v1 targets this team and this Estate. Generalisation, packaging for other organisations, and support for other source or target platforms are out of scope.
- **Not a replacement for BMad.** No shipped BMad skill is forked or modified. Every addition is a new skill or a configuration override.
- **Not a deployment tool.** Publishing, workspace management, gateway configuration, and refresh scheduling are outside the boundary.
- **Not a data quality tool.** The product validates that migrated numbers match legacy numbers. It does not assess whether the legacy numbers were right.
- **Not a pixel-perfect replicator.** The product targets structural and data equivalence. It does not reproduce OBIEE styling, fonts, colours, or chart rendering in Power BI, and effort spent pursuing visual identity is effort taken from parity.

## 6. MVP Scope

### 6.1 In Scope — Phase 0 (two weeks, ends at internal approval)

`[ASSUMPTION: two weeks is sufficient for Phase 0 given the Operator's availability.]`

- RPD extraction (FR-1 through FR-5) sufficient to populate the Knowledge Base for the benchmark set.
- The Knowledge Base workbook (FR-8).
- Migration Spine, first version, covering the constructs the benchmark set exercises (FR-10, FR-11).
- Group Spec generation for the benchmark set (FR-12, FR-14).
- Readable delivery of everything a human sees in the demo (FR-26, FR-27, FR-28, FR-29). This is not cosmetic: the Phase 0 deliverable is judged by people reading documents, so the reading experience is part of what is being proved. FR-28 in particular is not deferrable — a mangled formula in the Knowledge Base attacks the exact claim the demo is making.
- The **Test Corpus** (FR-30, FR-31): two pinned MDS XML repositories, a benchmark set of **six Subject Areas across three difficulty tiers**, **at least two sharing logical tables**, and Constructed Cases with recorded Ground Truth for the tangled tier. Building this corpus is real work and is scoped as such, not assumed away. *(Amended 2026-08-16 — was "a running SampleApp environment … six Dashboards".)*
- At least one **Comparison Report** (FR-32, FR-34) for the demo. In Phase 0 the migrated side is **built by hand from the generated Group Spec** — generation is not in scope yet. This is deliberate and it proves something specific and valuable: that the Spec alone was sufficient to build a correct report. If a person can build from the Spec, so can Amelia.
- ~~**At least one Parity Check, run by hand** on the demo Dashboard.~~ **Removed 2026-08-16.** No obtainable data source exists — the corpus is RPD metadata only. Phase 0 evidence is instead: **(a)** extraction accuracy against recorded Ground Truth, reported per construct type (SM-7); **(b)** the Knowledge Base demonstrated on a real 1252-object estate; **(c)** coverage reporting showing exactly which constructs are and are not exercised.
  **Phase 0 must state plainly that numeric parity is unproven and remains a Phase 2 question.** This removal is a genuine loss, not a reframing: the original commitment existed because *an MVP that demonstrates no verification leaves the thesis unproven at exactly the moment it is being judged*, and that concern is deferred rather than answered. The thesis is **argued** in Phase 0 and **demonstrated** in Phase 2.
- **Reuse detection** — the half of FR-13 that identifies what already exists in a Semantic Model. Phase 0's corpus contains two Dashboards sharing a Subject Area, so reuse will be encountered whether or not it is specified; the full additive machinery remains Phase 1.
- Measured accuracy: expert review of each generated Group Spec against its source for the simple and medium tiers, and comparison against recorded Ground Truth for the tangled tier.
- Measured cost: token cost per Dashboard.
- No-admin dependency policy and markdown-only definitions applied from the first commit (FR-23, FR-24).

**Phase 0 succeeds or fails on documentation alone.** It generates no code and touches no production system, so it carries no production risk.

### 6.2 Out of Scope for MVP

- **Web Catalog extraction (FR-6, FR-7)** — deferred to Phase 1. Phase 0 proves the semantic layer; the report layer is a second parser and a second risk.
- **Additive spec logic (FR-13), generation half** — reuse *detection* is in Phase 0 scope; the machinery that specifies deltas against an existing model is Phase 1.
- **Power BI generation (FR-16)** — Phase 2. Nothing is generated until parity can be checked.
- **Automated parity validation (FR-17 through FR-20)** — Phase 2. Phase 0 runs one Parity Check by hand; check authoring, execution, divergence triage, and the completion gate are Phase 2. The manual check proves the thesis is demonstrable; the automated agent is what makes it affordable at estate scale.
- **MCP data connectivity (FR-21, FR-22)** — Phase 2.
- **VDI deployment (FR-25)** — after approval. Deliberately sequenced: the environment is not audited for a project nobody has approved.
- **Living documentation** — regenerating Specs from PBIP/TMDL to keep documentation current after migration. Named as future direction; not built.
- **Spec-driven authoring** — treating the Spec as source and the model as generated output. This is the line between an internal tool and a product; recorded, not built.
- **Estate analytics** — impact analysis, dead-report detection, duplicate-metric detection across the Estate. These are pitch material and follow from the Knowledge Base for free later.
- **Guided vs. expert Operator modes** and formal training material.

## 7. Cross-Cutting NFRs

- **Determinism.** Extraction is fully deterministic. Identical input produces identical output. No LLM participates in extraction.
- **Traceability.** Every statement in a Group Spec traces to a Knowledge Base identifier, and every Knowledge Base row traces to a source object. A wrong number six months later must be explainable.
- **Reproducibility.** Any generated artifact can be regenerated from the Knowledge Base and the Migration Spine.
- **Inspectability.** Every artifact — Knowledge Base, Spine, Spec, generated model — is human-readable by an OBIEE-literate Operator without special tooling.
- **Plain text throughout.** Every artifact the product produces is text — markdown or CSV. Nothing requires conversion before a human can read it, and everything produces a meaningful diff in version control. The single exception is screenshots referenced by a Comparison Report (§4.12), which are captured evidence rather than a generated document format.
- **Diffability.** Because outputs live in GitHub, a reviewer must be able to see what changed between two runs. This rules out binary formats for any artifact the product generates.
- **Failure honesty.** The tool reports what it could not do. Silent omission is the primary failure mode to design against, in extraction, specification, and parity alike.
- **Offline operation.** All components function with no internet access.
- **Idempotence.** Re-running extraction or generation over unchanged input does not corrupt existing artifacts.

## 8. Constraints and Guardrails

### 8.1 Cost

Token cost is expected to be significant and must be measured, not estimated. Cost per Dashboard is a first-class metric reported from Phase 0 onward, benchmarked against the analyst-days per Dashboard it replaces. The primary cost control is architectural: deterministic work runs in Python where compute is free, and agents never read raw Estate content.

### 8.2 Data

- The tool operates strictly under the Operator's existing access rights. It introduces no new access path, service account, or credential.
- Estate data and query results remain inside the VDI boundary.
- Credentials are never embedded in skills, specs, or the Knowledge Base.

### 8.3 Safety

- No component writes to the OBIEE source or the warehouse. All access is read-only.
- Generated Power BI artifacts are written to a working directory and are never published automatically.

## 9. Runtime and Dependency Policy

This section is load-bearing rather than administrative: it is what makes VDI portability a copy operation instead of a project.

- **Python:** standard library first. Third-party dependencies are admitted only where the alternative is materially worse, and each must be pure-Python and installable from a vendored wheel.
- **No compiled extensions**, no system packages, no services, no daemons.
- **Output formats require no dependency at all.** Markdown is text; CSV is in the standard library. The extractor's target is zero third-party dependencies, and the output format decisions in §4.10 are what make that reachable.
- **Document conversion tooling is excluded.** `pandoc`, `LibreOffice`, `python-docx`, and `openpyxl` are all out of scope. The first two are system binaries requiring administrator installation; all four exist only to serve binary output formats the product has chosen not to produce. This is recorded as an explicit exclusion because `pandoc` and `LibreOffice` are already installed on the development machine and can therefore be adopted by accident — working locally and failing in the VDI.
- **No agent framework.** Skills and agents are markdown and TOML.
- **MCP servers** are the one component that may not satisfy this policy, since they are commonly distributed as `npx` or `uvx` packages. Confirming a no-admin installation path for the required MCP servers is an open item and a Phase 2 gate.
- **BMad is not forked.** Additions are new skills or `_bmad/custom/*.toml` overrides. A BMad upgrade must not remove any added capability.

## 10. Integration and Dependencies

| Dependency | Used for | Risk |
|---|---|---|
| ~~**SampleApp VirtualBox appliance**~~ | — | **UNAVAILABLE as of 2026-08-16.** Not published on oracle.com or edelivery; no Oracle licence held. Risk materialised. |
| **Pinned MDS XML repositories** (`VasiliKorzun/BI-Analytics-2013`, `rvijay17/obiee`) | The Test Corpus: RPD semantic layer only | **Neither carries a licence** — an open legal question, unresolved. One contains personal names in Subject Area names. No Web Catalog and no live data. |
| ~~**OBIEE server utilities** (`biserverxmlgen`)~~ | — | **Not used (amended 2026-08-16).** No OBIEE instance is obtainable. The extractor targets MDS XML instead — see Architecture Spine AD-20. |
| **Web Catalog export** | Report layer extraction | Export mechanism unconfirmed; Phase 1 |
| ~~**Oracle BI Administration Tool**~~ | — | **UNAVAILABLE (amended 2026-08-16).** Constructed Cases are hand-authored as MDS XML; see FR-31 and the circularity risk in §11. |
| **BMad installation** | The entire agent pipeline | Low — already installed and operating |
| **AI client** (Claude Code locally; Copilot in the VDI) | Running the agents | Copilot's capability to read skill definitions and invoke Python is unconfirmed; highest portability risk |
| **MCP servers** | Live data access for Parity Checks | Installation under no-admin constraint unconfirmed |
| **Power BI Desktop / PBIP tooling** | Opening and validating generated output | Low |
| **Warehouse and OBIEE query access** | Parity Checks | Policy settled; programmatic mechanism unconfirmed |

## 11. Risk and Mitigations

Three conditions are treated as abandonment criteria rather than ordinary risks. If any of them holds after Phase 2, the product has failed regardless of what else works:

1. **Accuracy is too low** — measured by SM-1 and SM-7.
2. **Too many Operator hours are spent debugging output** — measured by SM-3.
3. **Defects reach production** — measured by SM-2 and gated by FR-20.

Each is a verification failure rather than a generation failure, which is why the mitigations below concentrate on the Group Spec and the Parity Agent rather than on generation quality.

| Risk | Impact | Mitigation |
|---|---|---|
| **Junior Operator produces junior work at senior speed** | The stated productivity goal directly amplifies this. Ten flawed migrations per day instead of one. This is the third project-killer arriving through the front door. | The Group Spec is the capture point for senior judgement (FR-14 surfaces judgement points explicitly). The Parity gate (FR-20) is the backstop. Operator skill level is treated as a design input, not an afterthought. |
| **Metric drift across Report Groups** | The same measure defined twice, slightly differently. Undermines trust in the whole Estate. | Estate-wide Knowledge Base (FR-9) and additive Specs (FR-13). Migrating the second Dashboard in a group is where this surfaces — hence the benchmark set requirement that two Dashboards share a Subject Area. |
| **Proving on SampleApp does not prove the real Estate** | SampleApp is clean by design. A tool that handles it beautifully may fail on a repository carrying ten years of undocumented irregularity — and that failure would arrive after approval, which is the worst possible timing. | Constructed Cases (FR-31) deliberately author the irregularity SampleApp lacks. Accuracy is reported per construct type, not as a single figure, so the claim made at approval is *"accurate on these constructs"* rather than *"accurate."* Re-baseline against real Estate content as soon as any becomes available. |
| **"Looks like the legacy report" is heard as pixel identity** | A reviewer rejects a correct migration over fonts or colours, and the demo is lost on a claim that was never achievable. | FR-34 requires the Comparison Report to claim structural and data equivalence explicitly, and to list expected presentation differences as expected. Stated as a Non-Goal in §5. |
| **SampleApp version differs from the organisation's OBIEE version** | The XML schema the parser is built against may not match the real Estate. | Confirm the organisation's OBIEE version early. Isolate schema handling in the parser so a version difference is a contained change rather than a rewrite. |
| **SampleApp is no longer downloadable** — **MATERIALISED 2026-08-16** | The original Test Corpus foundation is gone, and with it the Web Catalog and all live data. | Confirmed unavailable by Story 1.1 before any dependent effort was spent — the check worked. Corpus replaced with two pinned public MDS XML repositories. Cost: FR-30 rescoped to Subject Areas, FR-31 hand-authored, and §6.1's Parity Check removed. |
| **Hand-authored Ground Truth is circular** *(new, 2026-08-16)* | A misunderstanding of the MDS XML format produces a fixture **and** an expectation that agree with each other and disagree with reality. Because SM-7 is the accuracy figure led with at approval, a silent error here misleads the approval decision itself. | Model every case on a real corpus file rather than on a schema summary. Prefer strengthening a thin construct over inventing an absent one. Have Ground Truth reviewed by someone who did not author the case. Report hand-authored accuracy separately from corpus-evidenced accuracy. |
| **Web Catalog extraction has no fixture** *(new, 2026-08-16)* | FR-6 and FR-7 cannot be written or tested under AD-19 — Phase 1 would be planned around a parser with nothing to parse. | Surface before Phase 1 planning. Either obtain real catalog content or defer FR-6/FR-7 explicitly rather than scheduling them. |
| **VDI Copilot cannot drive the skills** | The tool works locally and cannot be delivered where it is needed. | Markdown-and-Python-only design keeps requirements minimal. Confirm client capability before Phase 1 completes, and treat a thin manual-invocation mode as the fallback. |
| **MCP servers not installable without admin** | Parity validation blocked, and with it the answer to all three project-killers. | Identify required servers early and validate the no-admin path during Phase 1, not Phase 2. |
| **Token cost exceeds the value delivered** | The business case fails. | Deterministic-first architecture. Cost per Dashboard measured from Phase 0 and reported alongside accuracy. |
| **Silent extraction gaps** | The most dangerous failure: a missing content filter produces a plausible wrong number. | FR-5 coverage reporting; parity checks as the ultimate detector. |

## 12. Rollout and Change Management

- **Phase 0 — prove and win approval (two weeks).** Benchmark set, measured accuracy, measured cost, demo. Ends at an internal go/no-go.
- **Phase 1 — analysis and design depth.** Full parity-critical extraction, Web Catalog parser, Migration Spine hardening, Group Spec generation at estate scale. The critical path: if the Spec is right, generation is largely mechanical.
- **Phase 2 — generation and verification.** Power BI generation, Parity Agent, MCP connectivity, the accuracy-versus-complexity curve that forecasts remaining effort and locates the human review gate.
- **VDI deployment** follows approval, not precedes it.
- **Adoption** is per-Operator and incremental. Because the unit of work is one Dashboard, a hesitant Operator can adopt the tool for a single Dashboard without committing to it.
- **Training** is deliberately minimal by design. There is no framework to learn; the artifacts are markdown and CSV, and an OBIEE-literate person can read, review, and edit both. `[NOTE FOR PM]` Revisit after Phase 1 — if training is needed, that is evidence the design has drifted.

## 13. Business Case

**Cost avoided:** analyst-days per Dashboard spent manually decoding the RPD, plus rework caused by numbers that do not match after migration. `[ASSUMPTION: manual analyst-days per Dashboard is a measurable current baseline available for comparison.]`

**Cost incurred:** build effort, token cost per Dashboard, and Operator review time per Group Spec.

**Standalone return:** the Knowledge Base automates work the team performs manually today. If the agent pipeline never ships, this alone returns value — which is why it is Phase 0 and why the phasing is genuinely de-risked rather than nominally so.

**Residual asset:** on completion, the organisation owns a complete machine-readable and human-readable map of every metric in the Estate, serving ongoing maintenance of the Power BI estate. This would not be funded as a project in its own right; the migration pays for it.

**Reporting commitment:** Phase 0 publishes an actual accuracy figure and an actual cost-per-Dashboard figure rather than asserting a benefit. `[NOTE FOR PM]` This commitment appears in the approval pitch. It must be honoured or removed.

## 14. Success Metrics

**Primary**

- **SM-1: Group Spec accuracy.** Percentage of measures in a generated Group Spec judged correct by an OBIEE expert on first review, reported per difficulty tier. Phase 0 target: an established baseline with the tangled tier measured, not avoided. Validates FR-12, FR-14.
- **SM-2: Parity pass rate.** Percentage of Parity Checks passing on first generation, per difficulty tier. Validates FR-16 through FR-19. **Not measurable in Phase 0 (amended 2026-08-16)** — no obtainable data source. First measurable in Phase 2.
- **SM-3: Operator hours per Dashboard.** End-to-end, including review and rework, against the current manual baseline. This is the metric the effort crunch is measured in. Validates the product as a whole.

**Secondary**

- **SM-4: Token cost per Dashboard.** Measured, reported alongside SM-3. Validates §8.1.
- **SM-5: Extraction coverage.** Percentage of Estate objects parsed without skips. Validates FR-5.
- **SM-6: Semantic Model reuse rate.** Percentage of Dashboards after the first in a Report Group requiring no new model objects. Validates FR-13.
- **SM-7: Constructed Case accuracy.** Percentage of Constructed Cases extracted and specified correctly, measured against recorded Ground Truth and reported per construct type. Validates FR-4, FR-31.
  **Qualified 2026-08-16.** Cases are hand-authored as MDS XML, so their Ground Truth is authorial intent rather than observed OBIEE behaviour. SM-7 is therefore reported in two parts that are never merged: accuracy against **real corpus evidence** (the stronger figure, and the one to lead with) and accuracy against **hand-authored cases** (which carries the circularity caveat in §11).

**Counter-metrics (do not optimize)**

- **SM-C1: Dashboards migrated per week.** Must not be optimized. Throughput bought by weakening the Parity gate converts this product into a defect generator. Counterbalances SM-3.
- **SM-C2: Token cost.** Must not be optimized below the level required for verification. Cost reductions achieved by skipping Parity Checks or thinning Specs defeat the product's purpose. Counterbalances SM-4.
- **SM-C3: Spec brevity.** A shorter Spec is not a better Spec. Judgement points surfaced (FR-14) should not be suppressed to make Specs look clean. Counterbalances SM-1.

## 15. Open Questions

1. **Is the SampleApp appliance still obtainable?** Now the highest-priority open item; the Test Corpus and therefore Phase 0 depend on it. *(Supersedes the previous question about obtaining the organisation's own RPD, which is settled: it is not obtainable, and SampleApp replaces it.)*
2. **Which OBIEE version does the organisation actually run,** and how far does its XML schema diverge from SampleApp's 12c? Determines how much of the Phase 0 parser transfers.
3. **Can the Web Catalog be exported to a parseable form,** and by what mechanism? Blocks Phase 1. Now testable inside SampleApp rather than blocked on organisational access.
4. **What exactly is the VDI's Copilot client,** and can it read markdown skill definitions and invoke local Python?
5. **Can the required MCP servers be installed without administrator rights?**
6. **How can a generated Power BI Semantic Model be queried for parity** before publication?
7. **What is the Estate's size** — how many Dashboards, Analyses, and Subject Areas? Needed to convert per-Dashboard metrics into a migration forecast.
8. **Who approves Phase 0,** and what evidence do they require?
9. **How many Operators** will use the tool, and at what OBIEE skill level?
10. **What is the tolerance for a Parity Check** to count as passing, and who sets it?
11. **What happens to hand-edits** when a Dashboard is regenerated? Not a Phase 0 question, but it determines whether generated models are owned or regenerated forever.
12. **Does every reviewer and approver have GitHub access?** The plain-text delivery decision assumes the repository is where people read artifacts. A stakeholder without access would need documents circulated another way, which reintroduces a conversion step §9 has excluded.
13. **Where does the repository live** — GitHub.com, GitHub Enterprise, or an internal instance reachable from the VDI? Determines whether the review loop works in the environment the tool is actually deployed to.
14. **Can `bmad-create-epics-and-stories` consume a Group Spec unmodified?** Phase 1 spike. If not, a custom adapter is real work and the Spec-not-LLD argument weakens.
15. **Is the Estate Knowledge Base committed to the repository or generated on demand?** Committing it makes extraction diffs visible and gives the team a browsable metric map; it also puts Estate metadata in version control, which may have data-governance implications.

## 16. Assumptions Index

- **§4.1** — The RPD is supplied as an XML export from `biserverxmlgen`; binary parsing is out of scope. Now low-risk, since the export is generated inside SampleApp rather than requested from anyone.
- ~~**§4.11** — The SampleApp appliance is obtainable.~~ **FALSIFIED 2026-08-16.** Replaced by: the corpus is two pinned public MDS XML repositories, and their OBIEE version is close enough to the organisation's that the parser transfers. The transfer risk is now **wider**, not narrower — the sources date from 2013–2014.
- **§4.11** — Constructed Cases are representative enough of real-world irregularity for the accuracy claim to hold when the tool meets a real Estate. **Weakened 2026-08-16:** cases are hand-authored as MDS XML rather than generated by the Administration Tool, so they are additionally assumed to match what OBIEE actually emits. Unverified.
- **§4.1 (new, 2026-08-16)** — The corpus repositories, though unlicensed, may be used for internal development. **Unresolved legal question**, owned by the Operator, and to be settled before any derived artifact leaves the team.
- **§4.12** — The approval audience accepts structural and data equivalence, demonstrated side by side, as sufficient evidence. Visual identity is not expected of a platform migration.
- **§4.2** — The Web Catalog can be exported to a parseable XML form.
- **§4.5 (FR-15)** — `bmad-create-epics-and-stories` can consume a Group Spec without a custom adapter. Unverified; the Spec-not-LLD naming decision rests on it. Validated by a Phase 1 spike.
- **§4.6** — PBIP with TMDL is the correct Power BI target format.
- **§4.8** — Programmatic query access to OBIEE and the warehouse is available, not only human UI access.
- **§4.8 (FR-22)** — A query path exists against a generated Semantic Model prior to publication.
- **§4.9 (FR-25)** — The VDI Copilot client can read markdown skill definitions and invoke local Python. Largest portability risk.
- **§4.10** — The Migration Module and its outputs live in a GitHub repository, and the people who review Group Specs have access to it.
- **§4.10** — GitHub's markdown rendering and inline review comments are an acceptable review loop for Group Specs; no circulated document format is required.
- **§4.10** — Reviewers are willing to open CSV in a spreadsheet application rather than receiving a formatted workbook.
- **§6.1** — Two weeks is sufficient for Phase 0 given the Operator's availability.
- **§13** — Manual analyst-days per Dashboard is a measurable current baseline available for comparison.
