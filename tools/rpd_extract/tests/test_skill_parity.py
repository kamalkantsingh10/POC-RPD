"""AD-24 — an added skill exists in every client's discovery location.

BMad ships each skill as byte-identical copies in `.claude/skills/` (Claude Code)
and `.agents/skills/` (the location `.github/agents/*.agent.md` points Copilot at).
An added skill present in only one is invisible to the other client — which is
FR-25 failing silently, and it would be discovered in the VDI rather than here.

Duplication rather than a symlink: AD-16 makes deployment a plain file copy, and
the VDI may be Windows, where symlinks survive a cross-platform copy unreliably.

Standard library only (NFR13).
"""

from __future__ import annotations

import filecmp
import unittest
from pathlib import Path

CLAUDE = Path(".claude/skills")
AGENTS = Path(".agents/skills")

#: Skills this project adds. Shipped BMad skills are the installer's problem.
ADDED = ("obiee-as-is-analysis",)


class SkillParity(unittest.TestCase):
    def test_added_skills_exist_in_both_locations(self):
        for skill in ADDED:
            self.assertTrue((CLAUDE / skill).is_dir(), f"{skill} missing from {CLAUDE}")
            self.assertTrue(
                (AGENTS / skill).is_dir(),
                f"{skill} missing from {AGENTS} — invisible to Copilot (AD-24, FR-25)",
            )

    def test_copies_are_identical(self):
        for skill in ADDED:
            left, right = CLAUDE / skill, AGENTS / skill
            comparison = filecmp.dircmp(left, right)
            self._assert_same(comparison, skill)

    def _assert_same(self, comparison: filecmp.dircmp, skill: str) -> None:
        self.assertEqual(comparison.left_only, [], f"{skill}: only in .claude/skills")
        self.assertEqual(comparison.right_only, [], f"{skill}: only in .agents/skills")
        self.assertEqual(comparison.diff_files, [], f"{skill}: content differs")
        for sub in comparison.subdirs.values():
            self._assert_same(sub, skill)

    def test_added_skills_are_client_neutral(self):
        # A hard-coded client path would work from one location and break in the
        # other. Skills resolve through {skill-root} and {project-root} instead.
        for skill in ADDED:
            for path in (CLAUDE / skill).rglob("*.md"):
                text = path.read_text(encoding="utf-8")
                for hardcoded in (".claude/skills", ".agents/skills"):
                    self.assertNotIn(
                        hardcoded, text,
                        f"{path} hard-codes {hardcoded} — use {{skill-root}} (AD-24)",
                    )


if __name__ == "__main__":
    unittest.main()
