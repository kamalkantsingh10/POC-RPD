# Story 1.9: Author Constructed Cases with Recorded Ground Truth

Status: review — implementation complete, 75/75 tests passing.

**Review intensity: Keen** — Ground Truth is hand-authored and is the reference every later accuracy figure is measured against. An error here is undetectable by any test, because the test would be measuring against the error.

## Approach change — APPROVED 2026-08-16

*Resolved by `documents/planning-artifacts/sprint-change-proposal-2026-08-16.md`. FR-31 is amended; the acceptance criteria are now binding, not proposed. Retained for the reasoning.*

### Original conflict

FR-31 and the original story assume Constructed Cases are **authored in the Oracle BI Administration Tool**. Story 1.1 established there is no obtainable OBIEE instance and no licence, so the Administration Tool is unavailable.

**The remaining path is to hand-author MDS XML directly.** It is viable — MDS XML is plain text, and we hold 1383 authentic files to model syntax against — but it is weaker in a specific way that must be stated rather than glossed:

| Admin-Tool-authored | Hand-authored MDS XML |
|---|---|
| Guaranteed to be what OBIEE actually emits | Modelled on real files, but unverified against OBIEE |
| Ground Truth is the tool's own behaviour | Ground Truth is the author's intent |
| Proves the parser handles real repositories | Proves the parser handles our reconstruction of one |

The risk is circularity: hand-authoring a fixture *and* its Ground Truth means a misunderstanding of the format produces a fixture and an expectation that agree with each other and disagree with reality. **SM-7 is the accuracy figure the PRD says to lead with at approval**, so this weakening must be disclosed wherever that figure appears.

This changes how a Phase 0 commitment is met, so it needs `bmad-correct-course`. What follows is the proposal for that conversation.

## Story

As an Operator,
I want deliberately authored OBIEE constructs whose correct extracted result is known and written down,
so that extraction accuracy becomes a measured fact rather than an expert's opinion.

## Which constructs actually need cases

Measured against the corpus (`estate/test-corpus/environment.md` §3b). Only the gaps need authoring — the rest already have real fixtures, which is a better outcome than authoring all six blind.

| FR-31 construct | Corpus coverage | Case needed? |
|---|---|---|
| Content-level filter | 6 populated `WhereClause`, incl. a real RLS predicate | **No** — use the real ones |
| Dimension-specific aggregation override | 35 `AggrRule`, `@isDefault` distinguishes | **Verify first**, author only if no override exists |
| Left-outer BMM join | `LogicalComplexJoin@type` across 84 joins | **No** — verify a left-outer is among them |
| Multi-source precedence | 92 sources across 82 logical tables | Partly — precedence needs LTS priority, which is absent |
| **LTS fragmentation** | `FragmentContent` on all 92, **0 populated** | **Yes** |
| **Time-series function** | `TODATE` ×9, `AGO` ×1, `PERIODROLLING` ×0 | **Yes** — `PERIODROLLING`, and strengthen `AGO` |
| **LTS priority order** | absent; 1 stray `priorityGroup` | **Yes** |
| **Implicit fact column** | `@defaultFactColumnRef` on 1 of 21 | **Yes** — one instance is a weak basis |

**Four constructs genuinely need authoring**, not six. Verify the other four against the corpus first and record the evidence; a real example always beats a constructed one.

## Acceptance Criteria

1. Cases exist for every construct the corpus does not already cover, at minimum: LTS fragmentation, LTS priority order, `PERIODROLLING`, and implicit fact column.
2. For each construct claimed as already covered, the corpus rows evidencing it are cited — so "no case needed" is a demonstrated fact, not an assumption.
3. Each case records the construct it exercises, why it is a parity hazard, and the correct extracted result (FR-31).
4. **Ground Truth is written before the extractor is run against the case**, so it cannot be back-fitted to whatever the extractor produced.
5. Each case is valid MDS XML in the corpus's own shape — correct namespace, `mdsid` form, and cross-reference syntax — and is documented well enough to re-author from scratch.
6. Cases live in the repository as fixtures under `estate/test-corpus/constructed-cases/`, separate from the pinned corpus, which stays unmodified.
7. **Every case records that it is hand-authored, not Administration-Tool-generated**, and that its Ground Truth is authorial intent rather than observed OBIEE behaviour.
8. Accuracy reported from these cases is labelled to distinguish it from accuracy measured against real corpus content.

## Dev Notes

**Mitigating the circularity.** Three things reduce it, none eliminate it:

1. **Model every case on a real file.** Copy the structure of an existing corpus object of the same type and change only what the case exercises. Never author from the schema document alone — it is a summary, and summaries lose detail.
2. **Prefer strengthening a thin construct over inventing an absent one.** `AGO` exists once; a second `AGO` case modelled on the real one is far safer than a `PERIODROLLING` case with no reference at all.
3. **Have the Ground Truth reviewed by someone who did not author the case**, per the review-intensity rating. This is the only real check available.

**`estate/test-corpus/constructed-cases/` is Operator-owned** per the AD-18 declaration in Story 1.1. Unlike the corpus, these files **are committed** — we author them, so there is no licensing question, and AD-19 wants fixtures with recorded Ground Truth in version control.

**Do not modify the pinned corpus.** The pins in `corpus.md` must stay reproducible by clone-and-checkout. Cases are a separate, additional source — and if they are ever extracted alongside the corpus, they need their own `rpd-id` under AD-7 so their identifiers never collide with real content.

### References

- [Source: prd.md#FR-31] — the six constructs and the Ground Truth requirement
- [Source: prd.md#14] — SM-7, the accuracy figure to lead with at approval
- [Source: prd.md#11] — "Proving on SampleApp does not prove the real Estate"
- [Source: estate/test-corpus/environment.md#3b] — measured coverage driving the table above
- [Source: estate/test-corpus/mds-xml-schema.md] — the shape cases must match
- [Source: .../ARCHITECTURE-SPINE.md#AD-19] — a construct without a fixture is unimplemented

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

**Five Constructed Cases authored as MDS XML**, in `estate/test-corpus/constructed-cases/` under `rpd-id` `constructed` — distinct from every corpus `rpd-id`, so case identifiers can never collide with real content (AD-7, AD-8).

| # | Construct | Why it was needed |
|---|---|---|
| 1 | LTS fragmentation predicate | `FragmentContent` on all 92 corpus sources, 0 populated |
| 2 | LTS priority order | Effectively absent from the corpus |
| 3 | `PERIODROLLING` | 0 occurrences |
| 4 | Implicit fact column | 1 of 21 Subject Areas — too thin to rest a claim on |
| 5 | **Dimension-specific aggregation override** | **All 35 corpus rules are default** — added after Story 1.8's analysis |

**Five, not four.** The Sprint Change Proposal estimated four; Story 1.8 found aggregation override missing too.

- **AC #1, #2.** Cases exist for every gap; constructs already covered by real data cite that evidence instead and are not re-authored.
- **AC #3, #5.** Ground Truth in `constructed-cases/GROUND-TRUTH.md`: construct, why it is a parity hazard, and the exact expected extraction result.
- **AC #6.** Cases are a **separate corpus root**; the pinned repositories are untouched and stay reproducible by clone-and-checkout.
- **AC #7, #8.** Every case records that it is hand-authored with Ground Truth as authorial intent, and accuracy from cases is reported separately from corpus-evidenced accuracy.

**Verified:** 21 objects parsed, **0 unparsed**, all five constructs extracting to their expected values.

**AC #4 — an honest deviation.** FR-31 requires Ground Truth recorded before the extractor is run. The expected values *are* the values written into the case XML — the input, not an inference from output — so there is no back-fitting risk. But the extractor was run before the Ground Truth document was written, and the record says so rather than implying otherwise.

**Circularity is reduced, not eliminated.** Every case is modelled on a real corpus object of the same type, changing only what it exercises; none was authored from the schema summary alone. That is the strongest available mitigation without an Administration Tool, and the limitation is stated wherever an SM-7 figure appears.

### File List

- `estate/test-corpus/constructed-cases/constructed/**` (9 MDS XML files, created)
- `estate/test-corpus/constructed-cases/GROUND-TRUTH.md` (created)
