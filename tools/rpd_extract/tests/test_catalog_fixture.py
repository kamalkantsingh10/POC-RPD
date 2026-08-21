"""Claims that can only be made about the real Web Catalog fixture.

Separate from ``test_catalog.py`` because these need the 420 MB corpus, which a
bare checkout does not have. They **skip** when it is absent rather than
asserting against a corpus that may not be there — a test that silently passes
because its input is missing is the same class of false comfort this project
exists to remove.

Every number below was derived by ``tools/catalog_survey.py`` and is asserted
here so that a change to the adapter which quietly alters what it captures
fails loudly instead of moving a figure in a document nobody re-reads.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from tools.rpd_extract.adapters.inbound import catalog_xml
from tools.rpd_extract.core.model import (
    RESOLVED_CASE,
    RESOLVED_EXACT,
    RESOLVED_NONE,
)

#: Overridable so the suite can run against a catalog kept somewhere else.
FIXTURE = Path(
    os.environ.get(
        "OBIEE_CATALOG_FIXTURE",
        Path.home() / "Documents/Garage/obiee-corpus/obiee_sample_git",
    )
)

RPD_ID = "sampleapp-v607"


@unittest.skipUnless(FIXTURE.is_dir(), f"catalog fixture not present at {FIXTURE}")
class FixtureTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.estate = catalog_xml.load(FIXTURE, RPD_ID)

    def census(self) -> dict[str, int]:
        return {measure: n for (_, measure), n in self.estate.input_census.items()}

    def test_every_file_is_accounted_for(self):
        """Story 2.7 AC-7: the populations partition the input exactly."""
        census = self.census()
        self.assertEqual(census["files_seen"], 5371)
        self.assertEqual(census["parsed_as_xml"], 4341)
        self.assertEqual(census["not_a_catalog_object"], 1030)
        self.assertEqual(census["modelled_object"], 2850)
        self.assertEqual(census["unmodelled_object"], 1491)
        self.assertEqual(
            census["parsed_as_xml"] + census["not_a_catalog_object"],
            census["files_seen"],
        )
        self.assertEqual(
            census["modelled_object"] + census["unmodelled_object"],
            census["parsed_as_xml"],
        )

    def test_the_modelled_share_is_a_little_over_half(self):
        """Story 2.7: 53%, and a coverage report that does not say so invites a
        reader to assume the other 47% was understood."""
        census = self.census()
        share = round(100 * census["modelled_object"] / census["files_seen"])
        self.assertEqual(share, 53)

    def test_object_counts_match_the_recorded_measurements(self):
        self.assertEqual(len(self.estate.dashboards), 111)
        self.assertEqual(len(self.estate.dashboard_pages), 1036)
        self.assertEqual(len(self.estate.analyses), 1607)
        self.assertEqual(len(self.estate.saved_filters), 96)

    def test_criteria_outnumber_analyses(self):
        """Story 2.5 AC-8: a one-per-report model would drop 182 query
        definitions, and 109 criteria carry no subjectArea at all."""
        self.assertEqual(len(self.estate.analysis_criteria), 1789)
        with_area = [c for c in self.estate.analysis_criteria if c.subject_area]
        self.assertEqual(len(with_area), 1680)

    def test_subject_area_values_are_kept_exactly_as_written(self):
        """Story 2.5 AC-2: do not resolve, normalise, or strip the quotes.

        And **not every value is a Subject Area.** Of 67 distinct values, 27 are
        quoted Subject Area names and **40 are ``XSA('prodney'.'Sample Pharma')``
        forms** — uploaded datasets in Visual Analyzer projects, which have no
        semantic layer to resolve into at all. Whatever eventually implements
        FR-7 must not join an XSA value to a Subject Area name; capturing the
        string untouched is what keeps that distinction available.
        """
        areas = {c.subject_area for c in self.estate.analysis_criteria
                 if c.subject_area}
        self.assertIn('"A - Sample Sales"', areas)
        quoted = {a for a in areas if a.startswith('"')}
        datasets = {a for a in areas if a.startswith("XSA(")}
        self.assertEqual(len(quoted), 27)
        self.assertEqual(len(datasets), 40)
        self.assertEqual(quoted | datasets, areas)

    def test_every_column_formula_is_captured_or_visible(self):
        """Story 2.5 AC-3. The fixture holds 10,474 ``columnFormula`` elements
        inside criteria: 10,340 belong to a column and are captured here, 132
        sit inside filters and are captured as filter expressions, and 2 are a
        second formula on a column that already has one. None is lost."""
        with_formula = [c for c in self.estate.analysis_columns
                        if c.formula_construct]
        self.assertEqual(len(self.estate.analysis_columns), 11143)
        self.assertEqual(len(with_formula), 10340)

    def test_case_normalisation_is_carrying_this_fixture(self):
        """Story 2.4 AC-4. Exact matching resolves a handful of references and
        case folding resolves thousands. Both numbers must stay visible: an
        Operator on a case-sensitive estate needs to see which is load-bearing.
        """
        outcomes = [c.resolution for c in self.estate.dashboard_contents]
        exact = outcomes.count(RESOLVED_EXACT)
        folded = outcomes.count(RESOLVED_CASE)
        self.assertLess(exact, 20, "exact matching should resolve very few")
        self.assertGreater(folded, 2000, "case folding should resolve thousands")
        self.assertGreater(folded, exact * 100)

    def test_the_absent_second_catalog_root_is_recorded_not_repaired(self):
        """Story 2.4: 1161 references point into /company_shared/, a root this
        fixture does not contain. They are genuinely unresolvable here, and a
        partial catalog export is a normal state the tool will meet."""
        unresolved = [c for c in self.estate.dashboard_contents
                      if c.resolution == RESOLVED_NONE]
        company = [c for c in unresolved
                   if c.reference.startswith("/company_shared/")]
        self.assertGreater(len(company), 500)
        self.assertTrue(all(c.target_id == "" for c in unresolved))

    def test_no_version_is_the_most_common_state_of_all(self):
        """Story 2.7 AC-4: absence is a value in its own right.

        The epic, Story 2.1 and Story 2.7 all called it the *second* most
        common. Measured across all 4341 parseable roots it is the **first**:
        1643 declare no version, against 1504 for the largest declared value.
        Corrected here because a document nobody re-measures is how the last
        three wrong numbers on this project survived.
        """
        totals: dict[str, int] = {}
        for (_, _, version), count in self.estate.catalog_versions.items():
            totals[version] = totals.get(version, 0) + count
        ranked = sorted(totals.items(), key=lambda kv: -kv[1])
        self.assertEqual(ranked[0][0], "", "absence should rank first")
        self.assertEqual(totals[""], 1643)
        self.assertEqual(totals["201201160"], 1504)
        self.assertEqual(totals["200810300"], 1147)
        self.assertEqual(totals["201106170"], 47)

    def test_all_fifty_five_unmodelled_root_types_are_enumerated(self):
        """Story 2.7 AC-2: all of them, never a named subset. The five the epic
        named account for well under half."""
        unmodelled = {u.object_type for u in self.estate.unparsed
                      if u.kind == "unmodelled_type"}
        self.assertEqual(len(unmodelled), 55)

    def test_non_xml_files_are_classified_never_failed(self):
        """Story 2.7 AC-3."""
        classified = [u for u in self.estate.unparsed
                      if u.kind == "not_a_catalog_object"]
        self.assertEqual(sum(u.occurrences for u in classified), 1030)
        self.assertNotIn("malformed_xml", {e.kind for e in self.estate.errors})

    def test_styling_is_excluded_by_scope_and_the_exclusion_is_recorded(self):
        """Story 2.7 AC-5: distinguishable from content nobody understood."""
        excluded = [u for u in self.estate.unparsed
                    if u.kind == "excluded_by_scope"]
        self.assertTrue(excluded)
        names = {u.detail.rpartition("@")[2] for u in excluded}
        self.assertIn("wrapText", names)
        gaps = {u.detail.rpartition("@")[2] for u in self.estate.unparsed
                if u.kind == "unread_attribute"}
        self.assertFalse(names & gaps, "an attribute is excluded or a gap, never both")

    def test_a_database_call_is_flagged_where_it_actually_lives(self):
        """Story 2.5 AC-6, corrected by measurement: every ``sawx:eval`` in this
        fixture is in a filter, and none is inside a column formula."""
        self.assertTrue(any(f.uses_eval for f in self.estate.analysis_filters))
        self.assertFalse(any(c.uses_eval for c in self.estate.analysis_columns))

    def test_saved_filter_references_are_found_by_type(self):
        """Story 2.6 AC-6: matching the element name finds nothing at all."""
        refs = [f for f in self.estate.analysis_filters
                if f.expr_type == catalog_xml.SAVED_FILTER_TYPE]
        self.assertGreater(len(refs), 300)
        self.assertTrue(any(f.resolution == RESOLVED_CASE for f in refs))
        self.assertTrue(any(f.resolution == RESOLVED_NONE for f in refs))

    def test_prompts_mostly_live_in_an_object_type_this_epic_does_not_model(self):
        """Story 2.6 AC-4, and the limit on it.

        991 of the fixture's 995 ``saw:columnFilterPrompt`` elements sit in
        ``saw:view`` roots — 530 objects Epic 2 lists as unmodelled — and only
        4 are inside an Analysis. The prompts table is therefore nearly empty,
        and this test exists so that fact is asserted rather than discovered by
        someone reading four rows and concluding the estate has no prompts.
        """
        self.assertEqual(len(self.estate.analysis_prompts), 4)
        unmodelled = {u.object_type: u.occurrences for u in self.estate.unparsed
                      if u.kind == "unmodelled_type"}
        self.assertEqual(unmodelled["{com.siebel.analytics.web/report/v1.1}view"], 530)

    def test_extraction_is_deterministic(self):
        """AD-6: re-running over unchanged input produces the same rows."""
        again = catalog_xml.load(FIXTURE, RPD_ID)
        self.assertEqual([d.row_id for d in again.dashboards],
                         [d.row_id for d in self.estate.dashboards])
        self.assertEqual([c.formula for c in again.analysis_columns],
                         [c.formula for c in self.estate.analysis_columns])


if __name__ == "__main__":
    unittest.main()
