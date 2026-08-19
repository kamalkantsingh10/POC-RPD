# Generating the as-is: two decisions taken, one still open

**What this covers:** how the as-is analysis should be produced from the Estate Knowledge Base, and why. Written 2026-08-20, from a working discussion. **Nothing here is built** — Story 3.3 remains `backlog`, and this note exists so the reasoning is not re-derived.

**Who it is for:** whoever implements Story 3.3, and whoever plans the Migration Spine after it.

---

## 1. Agreed: generate via a workflow, not a single skill pass

The current design is `slice.py` (deterministic traversal) feeding the `obiee-as-is-analysis` skill (one agent, one pass). The skill is written and has never been run.

**A workflow that fans out is a better fit**, for three reasons that Story 3.3's own acceptance criteria name:

| AC | Why it favours a workflow |
|---|---|
| *"every rule is listed with its default flag, because a dropped override changes numbers silently"* | Fan-out makes coverage **structural**. N rules produce N sections; a dropped one is a missing array element, which is visible. One agent writing continuous prose can forget a sentence and nothing notices. |
| *"every factual statement cites the `row_id` it came from"* | Citation checking is **decidable** — a cited id either resolves against the Knowledge Base or does not. That is a script, not a judgement, so traceability can be verified deterministically and only prose quality needs an agent. |
| *"**Review intensity: Keen** — a Data Engineering team builds physical tables from this. An error here becomes wrong infrastructure, and nothing in the pipeline detects it."* | This is the one place in the pipeline with **no downstream detector**. Parity checks validate numbers, not documents. An independent adversarial pass earns its cost here specifically. |

### Shape

```
enumerate work items          code — measures and logical tables, from the Knowledge Base
   ↓
pipeline per item
     document it with citations      agent, ~6 rows of context per item
     verify every cited row_id       script — decidable, no judgement
     check the claim matches the row adversarial agent
   ↓
synthesise                    three reader sections, plus the honesty preamble
                              (extraction errors and unparsed counts for this slice)
```

### Scale, measured

**45 measures across the whole estate**, 2–4 per Subject Area, 1543 presentation columns. This is a modest fan-out, not a hundred-agent job. Several Subject Areas carry **zero** measures (`Anton_Tserakhau_SH` 123 columns, `SH - SALES` 117, `Vera_Yakimovich_SH` 106), so the work unit is probably the **logical table**, not the measure — decide when implementing.

### What this does to slicing

`slice.py` stops being the context mechanism — each agent queries the handful of rows for its own item. It keeps its other job: Story 3.3 requires the document *"alongside the CSV slice it was derived from"*, so the slice is the **evidence attachment**. Both survive; neither is redundant.

### Start small

Run it against **`Anton_Tserakhau`** first — 89 columns, 4 measures. Small enough to read the entire output and judge whether the document is any good before scaling to 21 Subject Areas.

### Honest caveats

- **Prose will not be deterministic.** Structure and citations will be reproducible; wording will not. Everything upstream is byte-identical, so this is a real change in character and should be stated in the document itself.
- **N independent sections need a genuine synthesis pass**, or the result reads like N documents stapled together.
- **A workflow replaces the generation half of the existing skill**, ~250 lines of unrun design. It does not reuse it.

---

## 2. Kamal's approach: a template the agent fills, and asks about

> *"we define a template of how a dashboard is to be built — an LLD. The agent will then create it, and ask questions where it is stuck or if something is missing."*

**This is the same principle as the extraction audit, pointed at the output instead of the input.**

The failure this project keeps designing against is *plausible completeness* — an artifact that looks finished while something is silently absent. Extraction solves it by observing what was read and reporting the difference. A template solves it the same way at the document end: **the slots exist whether or not they can be filled**, so an unfilled slot is visible by construction rather than being an absence nobody notices.

Compare the two failure modes:

| | Free-form generation | Template + questions |
|---|---|---|
| Missing information | prose simply omits it; the document reads complete | the slot is present and empty; the gap is a position on the page |
| Ambiguous information | the agent picks a plausible reading | the agent raises it as a question |
| What the reader sees | a finished-looking document | a document plus an explicit list of what is unresolved |

**This is already a requirement.** FR-14: *"unmapped constructs raised as Operator decisions, never silently resolved; ambiguous multi-LTS precedence raised for confirmation."* The template is the mechanism that makes FR-14 structural instead of aspirational — the agent cannot silently resolve something when the template requires it to answer or ask.

### Two things to settle when defining the template

**Which LLD is it?** *"How a dashboard is to be built"* is ambiguous between:
- the **as-is** — how the existing OBIEE dashboard is built (Epic 3), or
- the **to-be** — how the Power BI dashboard should be built (Migration Spine / Group Spec, FR-12).

The template shape differs: the first cites Knowledge Base rows, the second proposes DAX and target objects. They may share a skeleton, but the question each slot asks is different.

**A dashboard LLD needs report-layer data that does not exist yet.** Dashboards, pages, placed analyses and prompts live in the Web Catalog — **Epic 2, not built**. Pointed at today's Knowledge Base, a dashboard template would leave most slots empty and generate a long list of questions.

That is not an argument against the approach. It is the approach working: it would state precisely which slots the RPD alone can never fill, which is a far more useful answer than a document that quietly describes only the semantic layer and lets a reader assume it covered the reports. **Worth doing deliberately as a dry run** — the empty slots become the specification for what Epic 2 must supply.

---

## 3. Still open

- Whether the workflow's work unit is the measure or the logical table.
- Which LLD the template describes — as-is, to-be, or a shared skeleton with two fillings.
- Whether the questions the agent raises are an appendix, an inline marker, or a separate file that a later run can consume as answers.
