# Rubric walk — good-spine checklist

**Verdict:** the spine fixes the real divergence points and its rules are enforceable rather than aspirational. The paradigm split is the strongest call in it — recognising that the extractor and the skill set are different kinds of system prevented a single wrong paradigm being imposed on both. Two gaps: one dimension the altitude owns is thinner than it should be, and one Deferred item could let units diverge.

---

## Does it fix the real divergence points, and miss none?

**Largely yes.** The divergences that matter here are all about a shared store with a human controller — out-of-order invocation (AD-4), unknown artifact provenance (AD-5), unsafe re-runs (AD-6), identifier collision (AD-7, AD-8). Those are the right four, and they follow from the paradigm rather than being bolted on.

The adversarial pass found three the spine missed; see `review-adversarial-seams.md`. All three are in the same family — the blackboard's *write* discipline is specified, its *ownership* discipline is not. AD-2 names one owner for one area and stops.

### Findings
- **high** Ownership is specified for the Knowledge Base only (AD-2) — Every other blackboard area has an implied owner that is never stated, which is what let S-1, S-3, and S-4 through. *Fix:* one AD assigning a single writer to every `estate/` area, or a column in the layout table.

## Is every Rule enforceable, and does it prevent its stated divergence?

**Yes, with one exception.** Most rules are checkable by inspection — AD-2 (grep for writers), AD-12 (grep for delegation), AD-14 (diff against shipped BMad), AD-16 (is there a build step?). AD-13's naming firewall is enforceable by a text search, which is unusually good for a naming rule.

AD-7 is the exception: it *states* stability across regenerations without making it true, because the qualifier's source is undefined. See S-2.

### Findings
- **high** AD-7's rule does not achieve its Prevents (§AD-7) — Covered by S-2. *Fix:* as recommended there.

## Could anything under Deferred let two units diverge?

**One item.** *Concurrency* is deferred on the grounds of a single Operator working one Dashboard at a time — reasonable for Phase 0. But the blackboard sits in Git, and Git's merge behaviour on CSV is not the same as on markdown. Two Operators is the stated trigger to revisit; two *branches* is not, and that is nearer.

The others are clean. Catalog internals, PBIP approach, MCP transport, and CI are all genuinely below this altitude or gated on facts nobody has.

### Findings
- **medium** Concurrency deferral's revisit trigger is too late (§Deferred) — The stated trigger is two simultaneous Operators; branching reaches the same hazard sooner. *Fix:* widen the trigger to "a second concurrent line of work on the same Estate, whether a second Operator or a second branch."

## Is every dimension this altitude owns decided, deferred, or open?

**Nearly.** The operational envelope is covered — two environments, no infrastructure, no provider, deployment as file copy under AD-16, data access under the Operator's own rights. That is the dimension most often left silent and it is present.

The thin one is **testing**. The spine is for a tool whose entire purpose is verification, and it says nothing about how the *tool itself* is tested. AD-3's unparsed list is a runtime quality signal, not a test strategy. The PRD supplies a Test Corpus (FR-30, FR-31) with recorded Ground Truth — which is close to a test fixture specification — but the spine never connects it, and "how is the extractor's core tested" is exactly the kind of thing two builders answer incompatibly.

### Findings
- **high** Testing is a silent dimension (whole spine) — For a product whose thesis is verification, the absence of a rule about verifying the tool is conspicuous. *Fix:* an AD binding the extractor core to Ground-Truth fixtures — the pure, I/O-free core is directly testable, which is one of the reasons the paradigm was chosen, and that reason should be written down as a rule rather than left as a benefit.

## Does it cover the driving spec's capabilities?

**Yes.** The Capability → Architecture Map covers all twelve PRD feature areas and every FR range. Spot-checked FR-13 (additive spec) → AD-9/AD-10, FR-28 (CSV integrity) → conventions, FR-25 (client portability) → AD-11/AD-12. No orphans.

## Does it contradict a brownfield codebase or an inherited parent?

**Not applicable.** Greenfield repository; no parent spine. The one existing reality it must ratify is BMad's own conventions, and AD-14 does exactly that rather than inventing new ones.

## Named technology verified current?

**Yes** — see `review-versions.md`. Two findings there, both about over-strong pinning.

---

## Mechanical

- `AD` IDs 1–16, contiguous, no reuse.
- Both mermaid diagrams parse and are non-empty.
- Frontmatter complete; `binds` maps to FR ranges; `sources` resolve to real files.
- No template comments survive.
- Deferred items each carry a reason.
