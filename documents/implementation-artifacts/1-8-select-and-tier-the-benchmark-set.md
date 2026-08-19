# Story 1.8: Select and Tier the Benchmark Set

Status: review — implementation complete, 75/75 tests passing.

**Review intensity: Normal** — tier assignment is judgement, but every assignment cites the Knowledge Base rows evidencing it, so it is checkable rather than asserted.

## Scope change — APPROVED 2026-08-16

*The conflict below was resolved by `documents/planning-artifacts/sprint-change-proposal-2026-08-16.md`. FR-30 is amended; the acceptance criteria are now binding, not proposed. Retained for the reasoning.*

### Original conflict

**FR-30 as written cannot be satisfied.** It requires *"six Dashboards across three difficulty tiers"* with *"at least two Dashboards sharing a Subject Area"*.

The corpus contains **no Web Catalog and therefore no Dashboards at all**. Dashboards live in the Web Catalog, which is a separate store from the RPD; FR-6 and FR-7 are deferred to Phase 1, and Story 1.1 established there is no obtainable OBIEE instance from which a catalog could be exported.

This is not a detail to work around silently. It changes agreed MVP scope (PRD §6.1), so it needs `bmad-correct-course`, not a rewritten acceptance criterion. **What follows is the proposal to take into that conversation, not a decision already made.**

### What the corpus supports instead

The unit of work FR-30 reaches for is a *thing to migrate whose difficulty varies*. Without Dashboards, the available unit is the **Subject Area** — 21 of them across two `rpd-id`s, which is the natural target of a Power BI Semantic Model anyway (PRD Glossary: *"Subject Area — the natural unit of a Power BI Semantic Model"*).

| FR-30 requirement | Achievable substitute |
|---|---|
| Six Dashboards | Six Subject Areas |
| Three difficulty tiers | Unchanged — tiered on measurable RPD properties |
| Two Dashboards sharing a Subject Area | Two Subject Areas sharing logical tables, which exercises model reuse the same way |
| Tier criteria recorded | Unchanged, and stronger — criteria become Knowledge Base queries rather than judgement |

**What is genuinely lost:** the report layer. Tiering by Subject Area measures the difficulty of the *semantic* migration only. Dashboard-level difficulty — visual count, prompt complexity, drill paths — cannot be assessed and should not be claimed. Say so in the record rather than letting a reader assume otherwise.

## Story

As an Operator,
I want six Subject Areas chosen and assigned to difficulty tiers against recorded, queryable criteria,
so that accuracy is reported per tier rather than as one unexplainable number.

## Acceptance Criteria

1. At least two Subject Areas assigned to the **Simple** tier: measures using a single Logical Table Source, a default aggregation rule, and no time-series function.
2. At least two assigned to the **Medium** tier: containing at least one measure with multiple Logical Table Sources, a non-default aggregation rule, or a time-series function.
3. Each assignment states the criterion that placed it there **and cites the Knowledge Base row identifiers evidencing it** (NFR2).
4. At least two Subject Areas share logical tables, and the shared tables are named explicitly, so Semantic Model reuse is exercised rather than assumed.
5. The record states that the Tangled tier is supplied by Story 1.9 rather than leaving it blank.
6. The record states plainly that tiering covers the semantic layer only, and that report-layer difficulty is unassessed.
7. The record is markdown, opens with what it covers and who it is for, presents assignments as a table, and renders on GitHub without conversion (FR-29).

## Dev Notes

**Depends on Stories 1.4–1.7.** Tier criteria are queries over the Knowledge Base, so they cannot be evaluated until it exists. This is why the story sits here rather than earlier.

Every criterion is answerable from a Knowledge Base table rather than by opinion:

| Criterion | Source |
|---|---|
| Multiple Logical Table Sources | `logical_columns.csv` source count (Story 1.5); confirmed in `lineage.csv` (Story 1.7) |
| Non-default aggregation rule | `AggrRule@isDefault` (Story 1.5) |
| Time-series function | `AGO` / `TODATE` / `PERIODROLLING` in expression columns (Story 1.5) |
| Shared logical tables | `logical_tables.csv` joined via `@subjectAreaRef` (Stories 1.5, 1.6) |

That is a real improvement over the original framing: tier assignment becomes reproducible from the Knowledge Base rather than resting on a reviewer's judgement.

**Corpus reality to expect.** `TODATE` appears in 9 files, `AGO` in 1, `PERIODROLLING` in none. Medium-tier candidates driven by time-series functions are therefore scarce; multi-source and non-default-aggregation candidates are plentiful. Do not manufacture a tier assignment the evidence does not support — an honest "only one Subject Area qualifies on this criterion" is the correct output.

**Prefer the `sampleapp` source for anything shown outside the team.** `bi-analytics-2013` carries personal names in Subject Area and Business Model names (`Iryna_Bradzetskaya_MT_Full`, `Anton_Tserakhau`). See `estate/test-corpus/corpus.md`.

### References

- [Source: prd.md#FR-30] — the requirement in conflict
- [Source: prd.md#6.1] — Phase 0 scope, the benchmark set commitment
- [Source: prd.md#Glossary] — Subject Area as the natural unit of a Semantic Model
- [Source: estate/test-corpus/environment.md#3b] — measured FR-4 coverage
- [Source: .../ARCHITECTURE-SPINE.md#Deferred] — catalog adapter has no fixture

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

**Six Subject Areas tiered against queryable Knowledge Base criteria** — `estate/test-corpus/benchmark-set.md`.

| Tier | Subject Areas |
|---|---|
| Simple | Densification - US Crime By State, Population, Anton_Tserakhau_demo |
| Medium | Sample Sales (11 multi-source), Anton_Tserakhau (time-series), HR_TEAM_VAV (9 multi-source) |

- **AC #1, #2.** Three Simple and three Medium, above the two-per-tier minimum.
- **AC #3.** Every assignment cites Knowledge Base row identifiers. Assignment is reproducible by re-running the queries, not a matter of judgement — a real gain over the original Dashboard framing.
- **AC #4.** Reuse pair found: `Anton_Tserakhau` and `Anton_Tserakhau_demo` share `Anton_Tserakhau.Time` and `Anton_Tserakhau.Operations with agregation`.
- **AC #5, #6, #7.** Tangled tier attributed to Story 1.9; the semantic-only scope limit is stated at the top of the record where a reader meets it before any figure.

**Two findings that change later work:**

**All 35 aggregation rules in the corpus are `isDefault=true`.** Dimension-specific override is exercised nowhere — a fifth construct for Story 1.9, one more than the Sprint Change Proposal estimated. Found only because tier criteria are queries rather than opinion.

**Every reuse pair sits inside `bi-analytics-2013`.** Across 32 shared logical tables, the `sampleapp` source has none. So FR-30's reuse requirement and the recommendation to prefer `sampleapp` for external material are in direct tension — recorded rather than resolved, because the resolution is the Operator's licensing and privacy call.

**Also recorded honestly:** the Medium tier's time-series criterion rests on a single `AGO` expression, the only one in the corpus.

### File List

- `estate/test-corpus/benchmark-set.md` (created)
- `estate/knowledge-base/**` (generated; gitignored pending the licensing decision)
- `estate/knowledge-base/.gitignore` (created)
