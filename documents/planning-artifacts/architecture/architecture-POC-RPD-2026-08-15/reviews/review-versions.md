# Version and reality-check review

*Lens: was every committed technology reality-checked rather than asserted from training data — current versions, still exists, still fits.*

**Verdict:** the stack is unusually easy to verify because it commits to almost nothing. Two findings, both about claims that are stated more strongly than the evidence supports.

---

## V-1 — Git 2.43.0 is pinned but is not a requirement *(medium)*

The Stack table lists Git 2.43.0. That is the version observed on the development machine, not a constraint the product imposes. Pinning it implies the VDI must match, which is false and unenforceable — and under AD-16 the product performs no Git operations of its own at all.

**Fix:** state Git as a requirement without a version, or remove it from Stack and mention it under Environments where it belongs.

## V-2 — BMad is pinned to an exact version where a floor is meant *(medium)*

BMad 6.11.0 is recorded from `_bmad/bmm/config.yaml`, which is accurate as an observation. But AD-14 explicitly designs for BMad *upgrades* — the whole reason additions are `_bmad/custom/` overrides rather than forks is so that a newer BMad does not remove them. An exact pin contradicts the invariant it sits beside.

**Fix:** express as `>=6.11.0`, consistent with AD-14's intent.

---

## Verified

- **Python 3.11 floor** — checked against python.org. Python 3.14.7 is current as of August 2026; 3.11 remains a supported release. The floor is justified by two independent facts rather than habit: the runtime cannot be installed without admin rights, so the tool must run on whatever the VDI provides; and `>=3.11` is the floor BMad's own scripts already declare, so no stricter requirement is introduced than the dependency already carried. Development machine runs 3.12.3, comfortably above the floor.
- **Zero third-party Python packages** — verified as reachable rather than aspirational. `csv`, `xml.etree.ElementTree`, `pathlib`, `dataclasses`, `argparse`, and `tomllib` are all standard library at 3.11. `tomllib` in particular arrived in 3.11, which independently supports the floor choice.
- **`pandoc`, `LibreOffice`, `python-docx`, `openpyxl` excluded** — confirmed present on the development machine, which is precisely why the exclusion is recorded rather than assumed. No spine decision depends on any of them.
- **No framework, starter, or paved path** — correctly not recommended. A greenfield Python project would normally warrant one, but a zero-dependency stdlib tool with no service, no build, and no packaging step has nothing for a starter to pre-decide.

## Not verifiable here

- **SampleApp v607 availability.** Flagged in the PRD as the highest-priority open item. It is a Phase 0 corpus dependency, not a spine decision, and the spine correctly does not depend on it.
- **MCP server availability under no-admin installation.** Already deferred, and AD-11 prevents any skill from depending on it.
- **GitHub Copilot's exact capability set.** Asserted by the user as comparable to Claude Code with BMad available. AD-11's capability floor makes the spine safe under a narrower client, so the assertion is not load-bearing.
