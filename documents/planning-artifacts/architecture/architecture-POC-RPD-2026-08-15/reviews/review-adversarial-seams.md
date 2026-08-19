# Adversarial review — two compliant units that still build incompatibly

*Lens: construct pairs of units one level down that each obey every AD to the letter and still diverge. Every pair found is a hole.*

**Verdict:** four genuine seams found. Three are missing invariants; one is a direct conflict between a stated convention and a required feature.

---

## S-1 — Two Report Groups may claim the same Subject Area *(high)*

**The pair.** Operator declares Report Group `finance-core` mapping `(rpd-fin, Sales)`. Later, Operator declares `exec-dashboards` mapping `(rpd-fin, Sales)` and `(rpd-ops, Orders)`. Both declarations are valid under AD-9 — it fixes that grouping is declared, not that a Subject Area belongs to one group.

**How they diverge.** Two Group Specs are generated, each specifying a Semantic Model containing the `Sales` measures. Two models, same measures, independently maintained. AD-8 does not catch this because there is no name collision *across RPDs* — it is the same object claimed twice. This is metric drift arriving through the grouping layer rather than the naming layer.

**Fix:** a new AD. A `(RPD, Subject Area)` pair belongs to at most one Report Group; a second claim is an error surfaced at read time, not a silent second model.

## S-2 — `rpd-id` derivation is unspecified *(high)*

**The pair.** Extractor run A is given `SampleApp_prod.xml` and derives `rpd-id` from the filename. Extractor run B, three weeks later, is given the same repository exported as `sampleapp-2026-09.xml`. Both obey AD-7 — identifiers are RPD-qualified — and both obey AD-6, since each run is individually idempotent over *its* input.

**How they diverge.** Every identifier changes. Every Group Spec citation, every Parity Check reference, and every Comparison Report now points at identifiers that no longer exist. AD-7's "stable across regenerations" is stated but nothing makes it true, because the qualifier's *source* is undefined.

**Fix:** tighten AD-7. `rpd-id` is declared by the Operator at extraction time and recorded in the manifest. It is never derived from the export filename, the export timestamp, or any content hash. Re-extraction with a different declared `rpd-id` is a new source, not a regeneration.

## S-3 — Whole-file rewrite destroys human-supplied evidence *(high)*

**The pair.** The Parity Agent regenerates a Comparison Report after a second parity run, obeying the convention that artifacts are rewritten whole and never patched in place. The Operator has, in the meantime, added screenshots to that report per FR-32.

**How they diverge.** The rewrite is compliant and destroys the screenshots. The convention and FR-32 are in direct conflict; a builder obeying the convention produces a feature-incomplete product, and a builder preserving the screenshots violates a stated invariant.

**Fix:** separate generated content from supplied evidence. Human-captured screenshots live in a subfolder the agent never writes, and the generated report references them by convention. Whole-file rewrite then holds without exception.

## S-4 — Generated Power BI output has no home *(medium)*

**The pair.** Amelia generates PBIP/TMDL under AD-14 and AD-15; the Parity Agent reads the generated model under AD-4. Neither is told where it lives, and the structural seed has no location for it.

**How they diverge.** Amelia writes to a working directory of her choosing; the Parity Agent looks somewhere else and reports the model as absent — correctly, under AD-4, which requires it to state missing prerequisites and stop. Both are compliant and the workflow cannot complete.

**Fix:** add `estate/models/` to the structural seed and to the Capability → Architecture Map.

---

## Attempted and did not break

- **Two skills writing the Knowledge Base** — closed by AD-2 (sole writer).
- **A skill assuming extraction ran** — closed by AD-4 (must determine state and stop).
- **Cross-RPD measure collapse** — closed by AD-8 and AD-10.
- **One client's capability leaking into a skill** — closed by AD-11 and AD-12.
- **Extractor reading back its own output** — closed by AD-1.
- **Partial artifact appearing complete** — closed by AD-3 and the error convention.
