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
        mds_xml._audit_unread(trees, estate)
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
        mds_xml._audit_unread(trees, estate)
        gaps = [g for g in estate.unparsed if g.detail == "Ref@pick"]
        self.assertEqual(
            [g.occurrences for g in gaps],
            [1],
            "the unread Ref under B must still be reported",
        )


if __name__ == "__main__":
    unittest.main()



class FileDiscovery(unittest.TestCase):
    """A file the walker never reaches must not vanish silently.

    It appears in no other artifact: not a parse error, not an unmodelled type,
    not an unread attribute. Before this check a constructed estate holding a
    nested file and an extensionless one extracted with zero errors and zero
    gaps — the run looked perfect and had never seen them.
    """

    def estate_with(self, extra):
        import shutil, tempfile
        src = FIXTURES / "testrpd"
        tmp = Path(tempfile.mkdtemp())
        shutil.copytree(src, tmp / "e" / "testrpd")
        base = tmp / "e" / "testrpd" / "oracle" / "bi" / "server" / "base"
        for relative in extra:
            target = base / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('<PhysicalTable mdsid="mx" name="X"/>', encoding="utf-8")
        return mds_xml.load(tmp / "e"), tmp

    def undiscovered(self, estate):
        return sorted(g.detail for g in estate.unparsed if g.kind == "undiscovered_file")

    def test_a_nested_file_is_reported(self):
        estate, tmp = self.estate_with(["PhysicalTable/nested/buried.xml"])
        self.assertTrue(
            any("buried.xml" in d for d in self.undiscovered(estate)),
            f"nested file not reported; got {self.undiscovered(estate)}",
        )

    def test_a_file_without_the_xml_extension_is_reported(self):
        estate, tmp = self.estate_with(["PhysicalTable/no-extension"])
        self.assertTrue(
            any("no-extension" in d for d in self.undiscovered(estate)),
            f"extensionless file not reported; got {self.undiscovered(estate)}",
        )

    def test_an_ordinary_corpus_reports_nothing(self):
        """The check must stay silent when discovery really did find everything."""
        estate, tmp = self.estate_with([])
        self.assertEqual(self.undiscovered(estate), [])
