---
name: obiee-as-is-analysis
description: "Produce an as-is analysis document for one OBIEE Subject Area from the Estate Knowledge Base — every metric's logic, its lineage to physical tables, aggregation, joins, variables and security — accompanied by the CSV slice it was derived from. Use when the user asks to analyse a Subject Area, reverse-engineer an OBIEE subject area, or produce an as-is document for migration."
---

# As-Is Analysis — one Subject Area

**Goal:** produce a document that describes what an OBIEE Subject Area *actually does*, accurate enough that a Data Engineering team can rebuild its tables and a BI developer can rebuild its reports — accompanied by the CSV slice every statement was derived from.

**What this is not.** It proposes no Power BI design, no DAX, no target schema. It describes the existing system only. Target mapping is the Migration Spine's job and comes later — which is why this skill has no dependency on it.

## Conventions

- Bare paths resolve from the skill root; `{project-root}`-prefixed paths from the project working directory.
- Run commands from the project root.

## On Activation

### Step 1 — Load config

Read `{project-root}/_bmad/bmm/config.yaml` and resolve `{user_name}`, `{communication_language}`, `{document_output_language}`.

### Step 2 — Check prerequisites, and stop if they are missing

**AD-4: never assume another skill has run.** Determine the current state by reading the blackboard.

Confirm `{project-root}/estate/knowledge-base/manifest.csv` exists. If it does not, tell the user the Knowledge Base has not been extracted, give them the command, and **stop**:

```
python3 -m tools.rpd_extract.cli --corpus <corpus> --rpd-id <name> --out estate/knowledge-base
```

Read `manifest.csv` for `extracted_at`, `rpd_ids`, and `extractor_version`. **Read the table list from the manifest, never from a directory listing** — a stale file from an older extractor is invisible that way.

### Step 3 — Report extraction health before analysing anything

Read `errors.csv` and `unparsed.csv` from the Knowledge Base and tell the user plainly:

- **Errors** mean content that should have been captured was not. Report the count and the kinds. If non-zero, say so before producing any document — an analysis built on a lossy extraction is worth less than the user thinks, and they may want to fix it first.
- **Unparsed** entries are known gaps. `unmodelled_type` means no parser exists for that object type; `unread_attribute` / `unread_element` mean source content that no Knowledge Base column carries.

Do not bury this. It is the difference between "here is the analysis" and "here is the analysis, and here is what it could not see".

## Execution

### Step 4 — Establish the target

List what is available:

```
python3 -m tools.rpd_extract.slice --kb estate/knowledge-base
```

Present the Subject Areas grouped by `rpd-id` and ask **{user_name}** which one to analyse. Accept a name or a full `row_id`.

**If the user asks for a Dashboard or a report instead**, explain rather than fail:

> Dashboards and Analyses live in the OBIEE Web Catalog, which is a separate store from the RPD. The Knowledge Base holds the semantic layer only, so the available unit of analysis is the Subject Area. A Dashboard-level analysis needs a Web Catalog export, which is not yet supported (FR-6, FR-7).

Then offer the Subject Areas the report most likely draws on, and let them choose.

**If a name matches more than one repository**, do not guess. AD-8 keeps identically-named objects from different repositories distinct; ask which `row_id` they mean.

### Step 5 — Cut the slice

```
python3 -m tools.rpd_extract.slice \
  --kb estate/knowledge-base \
  --subject-area "<chosen>" \
  --out estate/analysis/<subject-area-slug>/
```

Use a lower-kebab slug of the Subject Area name for the directory.

**The slice is deterministic and is the only thing you read.** Do not read the whole Knowledge Base — it is roughly 474k tokens, while a Subject Area is 1k–40k. Do not re-derive the joins yourself: following foreign keys is deterministic work the slice has already done correctly, and an LLM re-doing it across hundreds of rows will occasionally produce a plausible wrong lineage. That is the failure this product exists to prevent.

### Step 6 — Read the slice

Read the CSVs in the output directory. Start with `slice-manifest.csv` for the row counts, then read what the document needs. On a large Subject Area, read the expression-bearing tables (`logical_columns`, `aggregation_rules`, `logical_table_sources`) in full and sample the rest.

### Step 7 — Write the document

Write `estate/analysis/<subject-area-slug>/as-is-analysis.md`, alongside the CSVs it was derived from.

**Every factual statement cites the Knowledge Base `row_id` it came from.** NFR2 requires it, and it is load-bearing rather than decorative: it is what lets a reviewer later say *"I think X is wrong, can you check?"* and have you re-derive that single claim instead of regenerating everything.

Follow the structure in `references/document-structure.md`.

Writing standard (FR-29): direct and concrete, short sentences, structure visible at a glance. Reference material goes in tables, not prose. OBIEE formulas go in fenced code blocks so nothing reflows them. Do not restate the same fact in two places.

### Step 8 — State the limits in the document itself

The document must say what it could not see. Put this near the top, where a reader meets it before relying on anything:

- Extraction errors and unparsed counts for this run.
- **Report-level logic is absent.** Calculations and filters defined inside an OBIEE Analysis live in the Web Catalog, not the RPD. Some metric logic will not appear here.
- **Physical detail is partial.** No DDL, indexes, partitioning, ETL upstream, or stored-procedure bodies — only what the repository records about the objects it reads.
- Anything in this Subject Area's slice that landed in `unparsed.csv`.

A Data Engineering team assuming completeness is the failure mode to design against.

### Step 9 — Hand back

Tell the user:

- Where the document and CSVs are.
- Row counts, and which constructs were found (multi-source measures, time-series functions, aggregation overrides, RLS predicates, fragmentation).
- What could not be seen.
- That the document is markdown in git: they can edit it directly, and the diff is the correction record.

## Rules

- **Read the blackboard; never assume a predecessor ran** (AD-4).
- **Never write to `estate/knowledge-base/`** — the extractor is its sole writer (AD-2).
- **Write only under `estate/analysis/`** — this skill is that area's single writer (AD-18).
- **Never invent a value.** If the slice does not contain something, say it is not recorded. An empty `priority` means *not recorded*, never *lowest* (AD-3).
- **No subagent delegation** (AD-12). The slice exists so this fits one context window.
- **Capability floor** (AD-11): read a file, write a file, run a local command. Nothing else.
- **Propose no target design.** No DAX, no Power BI modelling, no new schema. That is later work and mixing it in makes the as-is document unreviewable.
