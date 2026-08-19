"""Structural invariants the Knowledge Base must hold for any estate.

These are not construct-accuracy checks — `verify.py` covers those against
recorded Ground Truth. These assert properties that must be true of *every*
extraction, including estates nobody has seen, and each exists because its
absence let a real defect through:

* **Identifier uniqueness (FR-8).** 152 identifiers in the pinned corpus named
  more than one row, because physical identifiers were built from a Schema's
  *name* and three Schemas share the name ``SH``. Both rows parsed, no error was
  raised, and the totals looked right. Ten stories and 104 passing tests did not
  notice.

* **The unread audit reports what was not read.** The audit used to compare each
  file against ``_CONSUMED``, a hand-maintained list of what the parsers were
  believed to read. Listing a field silenced it whether or not anything read it,
  and six entries had drifted — ``PrivilegePackage@userRef`` among them, which
  dropped three privilege grants while reporting the file as fully understood.
  The audit now observes the parsers instead, so these tests exist to prove the
  observation can still fail: a check that cannot fail proves nothing.

Standard-library ``unittest`` only (NFR13).
"""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

from tools.rpd_extract.adapters.inbound import mds_xml
from tools.rpd_extract.adapters.outbound import knowledge_base
from tools.rpd_extract.core import model
from tools.rpd_extract.core.model import Estate

FIXTURES = Path(__file__).parent / "fixtures"
CASES = Path("estate/test-corpus/constructed-cases")


class IdentifierUniqueness(unittest.TestCase):
    """Every row_id must name exactly one row, in every table."""

    def test_the_check_detects_a_collision(self):
        """The check fires. A check that cannot fail proves nothing."""
        estate = mds_xml.load(FIXTURES)
        self.assertTrue(estate.physical_tables, "fixture produced no physical tables")

        # Two distinct rows sharing one identifier — exactly what happens when a
        # container name is not unique and the identifier does not say which.
        original = estate.physical_tables[0]
        estate.physical_tables.append(replace(original, name=original.name + "_OTHER"))
        estate.physical_tables[-1] = replace(
            estate.physical_tables[-1], row_id=original.row_id
        )

        before = len(estate.errors)
        estate.check_identifier_uniqueness()
        new = estate.errors[before:]

        self.assertEqual(len(new), 1, f"expected one duplicate reported, got {new}")
        self.assertEqual(new[0].kind, "duplicate_identifier")
        self.assertEqual(new[0].source_id, original.row_id)
        self.assertEqual(new[0].object_type, "physical_tables")

    def test_a_duplicate_is_not_counted_as_skipped(self):
        """Coverage must not be told an object was skipped when it parsed fine."""
        estate = mds_xml.load(FIXTURES)
        original = estate.physical_tables[0]
        estate.physical_tables.append(replace(original, name="DUPLICATE"))
        estate.physical_tables[-1] = replace(
            estate.physical_tables[-1], row_id=original.row_id
        )

        before = dict(estate.coverage)
        estate.check_identifier_uniqueness()
        self.assertEqual(estate.coverage, before, "coverage must not move")

    def test_the_check_covers_tables_nobody_remembered_to_list(self):
        """The sweep is generic, so a table added later is covered for free."""
        estate = Estate()
        checked = [
            name
            for name, rows in vars(estate).items()
            if isinstance(rows, list)
        ]
        # Every row-bearing collection on Estate, not a hand-maintained subset.
        for expected in ("physical_tables", "lineage", "presentation_columns"):
            self.assertIn(expected, checked)

    def test_the_fixture_estate_is_clean(self):
        estate = mds_xml.load(FIXTURES)
        self.assertEqual(
            [e for e in estate.errors if e.kind == "duplicate_identifier"], []
        )

    def test_the_constructed_cases_are_clean(self):
        if not CASES.is_dir():
            self.skipTest(f"{CASES} not present")
        estate = mds_xml.load(CASES / "constructed", "constructed")
        self.assertEqual(
            [e for e in estate.errors if e.kind == "duplicate_identifier"], []
        )


SAMPLE = (
    '<PhysicalTable xmlns="http://www.oracle.com/obis/repository" '
    'mdsid="m1" name="T" surpriseAttribute="x">'
    "<Description>notes nobody reads</Description>"
    "<UnknownChild deep=\"y\"/>"
    "</PhysicalTable>"
)


class UnreadAudit(unittest.TestCase):
    """The audit must report content the parsers did not take."""

    def audit(self, reader=None):
        """Parse SAMPLE observing reads, optionally read some of it, then audit."""
        root = ET.fromstring(SAMPLE, parser=mds_xml._observing_parser())
        if reader is not None:
            reader(root)
        estate = Estate()
        trees = [("test", "PhysicalTable", root)]
        mds_xml._audit_unread(trees, mds_xml._build_index(trees), estate)
        return {(g.kind, g.detail): g.occurrences for g in estate.unparsed}

    def test_an_attribute_nothing_reads_is_reported(self):
        """The userRef case: present, never read, must not pass in silence."""
        gaps = self.audit(lambda r: r.attrib.get("name"))
        self.assertIn(("unread_attribute", "PhysicalTable@surpriseAttribute"), gaps)

    def test_an_attribute_the_parser_reads_is_not_reported(self):
        """Observation must not cry wolf about content that was consumed."""
        gaps = self.audit(lambda r: (r.attrib.get("name"), r.attrib.get("mdsid")))
        self.assertNotIn(("unread_attribute", "PhysicalTable@name"), gaps)
        self.assertNotIn(("unread_attribute", "PhysicalTable@mdsid"), gaps)

    def test_reading_nothing_reports_everything(self):
        """With no reads at all, every field present must surface."""
        gaps = self.audit()
        for expected in (
            ("unread_attribute", "PhysicalTable@name"),
            ("unread_attribute", "PhysicalTable@mdsid"),
            ("unread_attribute", "PhysicalTable@surpriseAttribute"),
            ("unread_element", "UnknownChild"),
            ("unread_attribute", "UnknownChild@deep"),
        ):
            self.assertIn(expected, gaps, f"{expected} was not reported")

    def test_element_text_is_audited(self):
        """Text was invisible to the old audit, which only saw tags and attributes."""
        gaps = self.audit()
        self.assertIn(("unread_text", "Description#text"), gaps)

    def test_text_the_parser_reads_is_not_reported(self):
        gaps = self.audit(lambda r: mds_xml._text(mds_xml._first_child(r, "Description")))
        self.assertNotIn(("unread_text", "Description#text"), gaps)

    def test_a_wrapper_the_parser_walks_through_is_not_a_gap(self):
        """Traversal is consumption; otherwise every wrapper becomes noise."""
        gaps = self.audit(lambda r: mds_xml._children(r, "UnknownChild"))
        self.assertNotIn(("unread_element", "UnknownChild"), gaps)
        # ...but its unread attribute is still reported, at every level.
        self.assertIn(("unread_attribute", "UnknownChild@deep"), gaps)

    def assess(self, xml, reader=None):
        root = ET.fromstring(xml, parser=mds_xml._observing_parser())
        if reader is not None:
            reader(root)
        estate = Estate()
        trees = [("test", "PhysicalTable", root)]
        mds_xml._audit_unread(trees, mds_xml._build_index(trees), estate)
        return {g.detail: g.assessment for g in estate.unparsed}

    def test_a_reference_whose_target_is_absent_is_a_real_loss(self):
        """The userRef shape: points at an object the Knowledge Base has no id for."""
        xml = (
            '<PhysicalTable xmlns="http://www.oracle.com/obis/repository" mdsid="m1"'
            ' ghostRef="/oracle/bi/server/base/User/u.xml#mu1"/>'
        )
        self.assertEqual(
            self.assess(xml)["PhysicalTable@ghostRef"], model.TARGET_NOT_IN_KB
        )

    def test_a_reference_whose_target_is_known_costs_nothing(self):
        """The presentationTableRef shape: the same link exists by another path."""
        xml = (
            '<PhysicalTable xmlns="http://www.oracle.com/obis/repository" mdsid="m1">'
            '<Ref twinRef="/oracle/bi/server/base/PhysicalTable/t.xml#m2"/>'
            '<Inner mdsid="m2"/>'
            "</PhysicalTable>"
        )
        root = ET.fromstring(xml, parser=mds_xml._observing_parser())
        trees = [("test", "PhysicalTable", root)]
        index = mds_xml._build_index(trees)
        index.bind("m2", "test::phys::already.identified")  # the target IS in the KB
        estate = Estate()
        mds_xml._audit_unread(trees, index, estate)
        got = {g.detail: g.assessment for g in estate.unparsed}
        self.assertEqual(got["Ref@twinRef"], model.RECOVERABLE_ELSEWHERE)

    def test_a_plain_value_is_not_treated_as_a_reference(self):
        xml = (
            '<PhysicalTable xmlns="http://www.oracle.com/obis/repository" mdsid="m1"'
            ' cardinality="many"/>'
        )
        self.assertEqual(
            self.assess(xml)["PhysicalTable@cardinality"], model.VALUE_NOT_CAPTURED
        )

    def test_every_assessment_is_one_of_the_declared_values(self):
        estate = mds_xml.load(FIXTURES)
        for gap in estate.unparsed:
            if gap.kind == "unmodelled_type":
                continue
            self.assertIn(gap.assessment, model.ASSESSMENTS, f"{gap.detail}")

    def test_reads_are_counted_per_element_not_per_tag_name(self):
        """Reading a tag in one place must not silence the same tag elsewhere.

        The old audit matched by name, so `RefColumn@columnRef` declared once was
        silenced everywhere it appeared — including under `PhysicalKey`, which no
        parser touches.
        """
        xml = (
            '<PhysicalTable xmlns="http://www.oracle.com/obis/repository" mdsid="m">'
            '<A><Ref pick="1"/></A><B><Ref pick="2"/></B>'
            "</PhysicalTable>"
        )
        root = ET.fromstring(xml, parser=mds_xml._observing_parser())
        # Read `pick` under A only.
        mds_xml._first_child(mds_xml._first_child(root, "A"), "Ref").attrib.get("pick")
        estate = Estate()
        trees = [("test", "PhysicalTable", root)]
        mds_xml._audit_unread(trees, mds_xml._build_index(trees), estate)
        gaps = [g for g in estate.unparsed if g.detail == "Ref@pick"]
        self.assertEqual(
            [g.occurrences for g in gaps],
            [1],
            "the unread Ref under B must still be reported",
        )


if __name__ == "__main__":
    unittest.main()


class CompletenessReport(unittest.TestCase):
    """`completeness.csv` must let a dev tell a real gap from a real blank.

    Without it, an empty cell means three different things — OBIEE never set it,
    we failed to read it, or the value lives in another table — and nothing on
    the row says which. Establishing that by hand means re-parsing the source
    corpus, which is the work this report exists to remove.
    """

    def profile(self, tables):
        return {
            (r[1], r[2], r[3]): r
            for r in knowledge_base._profile(tables)
        }

    def test_a_fully_populated_column_is_complete(self):
        got = self.profile([("t", ["row_id", "rpd_id", "a"],
                             [["1", "r", "x"], ["2", "r", "y"]])])
        self.assertEqual(got[("t", "", "a")][8], knowledge_base.COMPLETE)

    def test_a_column_no_row_populates_is_flagged_for_checking(self):
        got = self.profile([("t", ["row_id", "rpd_id", "a"],
                             [["1", "r", ""], ["2", "r", ""]])])
        row = got[("t", "", "a")]
        self.assertEqual(row[8], knowledge_base.NEVER)
        self.assertIn("unparsed.csv", row[9])

    def test_a_partly_populated_column_says_so(self):
        got = self.profile([("t", ["row_id", "rpd_id", "a"],
                             [["1", "r", "x"], ["2", "r", ""]])])
        row = got[("t", "", "a")]
        self.assertEqual(row[8], knowledge_base.PARTIAL)
        self.assertEqual((row[4], row[5], row[6]), ("2", "1", "1"))

    def test_each_rpd_id_is_profiled_separately(self):
        """A column complete in one repository and absent in another must not average."""
        rows = knowledge_base._profile([("t", ["row_id", "rpd_id", "a"],
                                         [["1", "one", "x"], ["2", "two", ""]])])
        by_rpd = {r[0]: r for r in rows if r[3] == "a"}
        self.assertEqual(by_rpd["one"][8], knowledge_base.COMPLETE)
        self.assertEqual(by_rpd["two"][8], knowledge_base.NEVER)

    def test_kinds_are_profiled_separately(self):
        """A foreign key carries no expression; a complex join does."""
        got = self.profile([("physical_joins", ["row_id", "rpd_id", "kind", "expr_text"],
                             [["1", "r", "foreign_key", ""],
                              ["2", "r", "complex_join", "a=b"]])])
        self.assertEqual(
            got[("physical_joins", "complex_join", "expr_text")][8],
            knowledge_base.COMPLETE,
        )
        self.assertEqual(
            got[("physical_joins", "foreign_key", "expr_text")][8],
            knowledge_base.NEVER,
        )

    def test_a_blank_explained_by_another_kind_states_the_fact_not_a_verdict(self):
        """It must NOT claim "not applicable" — that guess buries real gaps.

        For `physical_joins` a foreign key genuinely has no join expression. For
        `security_rls` a `row_filter` with no role is a genuine FR-4 shortfall.
        Same shape, opposite meaning; the extractor cannot tell them apart, so it
        reports the comparison and leaves the judgement to a human.
        """
        got = self.profile([("physical_joins", ["row_id", "rpd_id", "kind", "expr_text"],
                             [["1", "r", "foreign_key", ""],
                              ["2", "r", "complex_join", "a=b"]])])
        note = got[("physical_joins", "foreign_key", "expr_text")][9]
        self.assertIn("complex_join", note)
        self.assertIn("cannot tell which", note)
        self.assertNotIn("not applicable", note)

    def test_report_tables_are_not_profiled(self):
        """"How populated is errors.csv" answers nothing, and self-profiling loops."""
        for name in ("errors", "unparsed", "coverage", "manifest", "completeness"):
            self.assertIn(name, knowledge_base.REPORT_TABLES)

    def test_the_written_report_covers_every_estate_table(self):
        import tempfile, csv as _csv
        estate = mds_xml.load(FIXTURES)
        with tempfile.TemporaryDirectory() as d:
            written = knowledge_base.write(estate, d, corpus_root=str(FIXTURES))
            rows = list(_csv.DictReader(
                open(Path(d) / "completeness.csv", newline='', encoding='utf-8')))
        profiled = {r['table'] for r in rows}
        expected = set(written) - knowledge_base.REPORT_TABLES
        self.assertEqual(profiled, expected, "every estate table must be profiled")
