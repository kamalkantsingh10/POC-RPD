# PRD Quality Review — OBIEE → Power BI Migration Assistant

*Rubric walk, 2026-08-15. Stakes: internal tool. Shape: chain-top (feeds architecture → epics → stories).*

## Overall verdict

This PRD holds up. It has a genuine thesis — that the hard problem is verification rather than translation — and the feature priority, the phasing, and the metrics all follow from it rather than being decorated onto it. Requirements are testable, omissions are explicit, and the trade-offs that were actually made during discovery are recorded honestly rather than smoothed away.

The material risk is a coherence gap between the thesis and Phase 0: the PRD argues that verification is the whole problem, then scopes an MVP that contains no verification. That is defensible, but it is the seam a sceptic will find, and it deserves a deliberate decision rather than an inherited one.

## 1. Decision-readiness — **strong**

Decisions appear as decisions. §5 Non-Goals does real work — "not an autopilot," "not a redesign," "not a pixel-perfect replicator" each close off a specific misreading that the discovery conversation actually produced. §6.2 gives reasons for deferrals rather than listing them. The risk register in §11 names the uncomfortable one first (junior Operator producing junior work at senior speed) instead of leading with technical risk, which is the honest ordering.

Trade-offs are named with what was given up. §4.3 states why CSV was chosen over a workbook; the fuller cost of that choice — lost sheets, frozen headers, typed columns — is recorded in addendum A3b.

Open Questions are genuinely open. None of the fourteen has its answer in the following sentence.

### Findings
- **low** Trade-off cost lives only in the addendum (§4.3) — A reader of the PRD alone sees the CSV decision without its price. *Fix:* one clause in §4.3 naming what was given up, or accept that the addendum is the right home for it.

## 2. Substance over theater — **strong**

Three user journeys, each with a named protagonist, and each doing work: UJ-1 is the approval demo the whole of Phase 0 targets, UJ-2 is the iterative operating model that produced the additive-spec requirement, UJ-3 carries the maintenance argument that justifies §13. No persona section padding the document.

NFRs in §7 are product-specific, not boilerplate. "Failure honesty — silent omission is the primary failure mode to design against" is an earned requirement traceable to a real hazard, not a copied line about scalability. §9 Runtime and Dependency Policy would be administrative filler in most PRDs; here it is load-bearing and says so.

The Vision does not read as swappable. It names this bottleneck, this constraint, this thesis.

### Findings
- **low** UJ-3 drives no FR (§2.3) — Ravi's journey carries the strategic argument for §13 rather than generating a requirement. Justifiable, but it is the one journey that could be cut without losing a requirement. *Fix:* keep it; note that it is argument rather than specification.

## 3. Strategic coherence — **strong**, with one seam

The thesis is stated in §1 and the document obeys it. Deterministic-first architecture, the Group Spec as the judgement-capture point, the Parity Agent as the correctness gate, and the explicit ranking that "features that make generation more capable rank below features that make it checkable" — these are the same argument expressed in architecture, requirements, and metrics.

Counter-metrics are present and are the right ones. SM-C1 (dashboards per week must not be optimised) directly defends the thesis against the pressure the product will actually face.

The seam: **§1 argues verification is the whole problem; §6.1 scopes a Phase 0 containing no verification.** Phase 0 proves specification quality and defers every Parity Check to Phase 2. This is coherent as a de-risking sequence — documentation cannot introduce a production defect — but it means the approval demo does not demonstrate the product's central claim.

### Findings
- **high** Phase 0 proves specification, not verification (§6.1, §6.2) — The PRD's thesis is that verification economics is the risk. Phase 0 contains no Parity Check, so the demo's answer to "how do we know it can be trusted" is expert review of a document. A sceptic can grant that the Spec is well written and still refuse the underlying claim. §6.2 already flags this with a `[NOTE FOR PM]`, which is correct, but it is filed as a deferral rather than resolved. *Fix:* decide deliberately — either pull a single hand-built Parity Check into Phase 0 (SampleApp has the live data, so it is now possible where it previously was not), or state explicitly in §6.1 that Phase 0's claim is bounded to specification quality and the verification claim is made at Phase 2.
- **medium** Reuse is exercised in Phase 0 but its FR is not (§6.1, §6.2, FR-13, FR-30) — FR-30 requires two corpus Dashboards to share a Subject Area, so Phase 0 will encounter Semantic Model reuse. FR-13, which specifies additive behaviour, is out of MVP scope. Either reuse is tested in Phase 0 and needs its requirement, or it is not and the corpus requirement is premature. *Fix:* pull the reuse-detection half of FR-13 into Phase 0, or move the shared-Subject-Area corpus requirement to Phase 1.

## 4. Done-ness clarity — **strong**

Every one of the 34 FRs carries testable consequences, and they are specific rather than gestural. FR-28's round-trip test ("write, open in a spreadsheet, save, re-read, against a corpus including real OBIEE formula text") is a requirement an engineer can execute without interpretation. FR-4 enumerates nine named constructs rather than saying "capture the relevant metadata." FR-19 names the fields a divergence report must contain.

Weasel formulations were searched for. FR-30's tier definitions were vague at first pass and were tightened to structural criteria during finalize.

### Findings
- **medium** FR-15 asserts third-party behaviour as a testable consequence (§4.5) — "`bmad-create-epics-and-stories` produces stories from the Spec with no custom adapter" is a claim about a shipped skill's behaviour against a document format that does not yet exist. It may be false, and it is load-bearing: the naming decision in addendum A1.1 rests on it. *Fix:* restate as an `[ASSUMPTION]` to be validated in Phase 1, or keep the FR and add a Phase 1 spike to prove it.
- **low** FR-29's consequences are the least testable set (§4.10) — "No document restates the same information in two places" is judgeable but not mechanically checkable. Acceptable for a readability requirement; noted rather than objected to.

## 5. Scope honesty — **strong**

Non-Goals do real work. Deferrals in §6.2 carry reasons. `[NOTE FOR PM]` callouts sit at genuine tensions — the parity-forward question, the Knowledge Base's audience beyond this workflow, whether training being needed is evidence of design drift — not at safe checkpoints. The Assumptions Index round-trips completely: 14 inline tags, 14 index entries.

Open-items density: 14 Open Questions, 14 assumptions, 6 `[NOTE FOR PM]`. That is high in absolute terms. It is appropriate here — this is a feasibility PRD whose Phase 0 exists precisely to close unknowns, and most open questions are environment confirmations rather than product decisions. It would be a blocker on a green-light-to-build PRD; it is not one on this.

### Findings
- **low** Open-items density is high (§15, §16) — Defensible for a POC, but worth re-counting before Phase 1 begins. If the count has not fallen substantially by then, the PRD has not been doing its job. *Fix:* revisit at the Phase 0 → Phase 1 gate.

## 6. Downstream usability — **strong**

Glossary is present and used with discipline; domain nouns are consistent across FRs, UJs, and metric definitions. FR IDs run 1–34 contiguous with no gaps or duplicates. SM IDs run SM-1…SM-7 plus three counter-metrics, in order. Cross-references resolve. Sections stand alone when extracted — §4.7 makes sense pulled out without §4.5 for context.

The three-tier document model (Migration Spine → Group Spec → report layer) gives downstream architecture and story creation a clear structure to attach to, and the deliberate choice to name the artifact a Spec rather than an LLD is what lets the shipped BMad chain consume it.

### Findings
- None material.

## 7. Shape fit — **strong**

Internal tool, but genuinely multi-role — Operator, expert reviewer, approver, future maintainer — so three user journeys is proportionate rather than over-formalised. Success Metrics are operational (hours per Dashboard, cost per Dashboard, parity pass rate) rather than user-satisfaction proxies, which fits the product type. The Adapt-In clusters pulled in — dependency policy, risk register, rollout, business case — are the ones an internal enterprise initiative genuinely needs, and consumer-product clusters were correctly left out.

The addition of §9 as a first-class section rather than an appendix is the right call for a product whose defining constraint is a locked-down deployment target.

### Findings
- None material.

## Mechanical notes

- **Glossary drift:** none found. "Estate Knowledge Base / Knowledge Base" is a declared short form, not drift.
- **ID continuity:** FR-1…FR-34 contiguous. SM-1…SM-7, SM-C1…SM-C3, in order. UJ-1…UJ-3.
- **Assumptions Index roundtrip:** complete — 14 inline, 14 indexed, matched.
- **UJ protagonists:** all three named and carrying context inline (Kamal, Priya, Ravi). No standalone persona section, correctly.
- **Superseded content:** the Word/Excel delivery decision was fully reversed during drafting. No residue of `Renderer`, `python-docx`, `openpyxl`, or `.docx` remains in the requirements; the exclusions survive deliberately in §9 and addendum A3b, which is correct.
