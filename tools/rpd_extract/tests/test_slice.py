"""Tests for the Subject Area slice (Epic 2).

The slice exists so an agent skill reads 1k–40k tokens instead of ~474k, and so
the foreign-key traversal stays deterministic Python rather than an LLM
following joins across hundreds of rows.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.rpd_extract import slice as slicer
from tools.rpd_extract.adapters.inbound import mds_xml
from tools.rpd_extract.adapters.outbound import knowledge_base
from tools.rpd_extract.adapters.outbound.csv_writer import read_table

FIXTURES = Path(__file__).parent / "fixtures"


class SliceFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.kb = Path(self._tmp.name) / "kb"
        knowledge_base.write(
            mds_xml.load(FIXTURES), self.kb,
            corpus_root="fixtures", timestamp="2026-01-01T00:00:00Z",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_lists_subject_areas(self):
        areas = slicer.subject_areas(self.kb)
        self.assertEqual([name for _, _, name in areas], ["Sample Sales SA"])

    def test_slice_reaches_every_layer(self):
        sliced = slicer.build(self.kb, "Sample Sales SA")
        for table in ("presentation_columns", "logical_columns", "aggregation_rules",
                      "lineage", "physical_columns", "logical_table_sources"):
            self.assertTrue(sliced[table][1], f"{table} is empty")

    def test_slice_is_a_strict_subset(self):
        sliced = slicer.build(self.kb, "Sample Sales SA")
        whole_header, whole_rows = read_table(self.kb / "logical_columns.csv")
        self.assertEqual(sliced["logical_columns"][0], whole_header)
        for row in sliced["logical_columns"][1]:
            self.assertIn(row, whole_rows)

    def test_implicit_fact_column_is_pulled_in(self):
        # It can sit outside the presentation columns, so a naive traversal
        # would drop the one construct FR-4 names for Subject Areas.
        sliced = slicer.build(self.kb, "Sample Sales SA")
        header, rows = sliced["logical_columns"]
        names = {dict(zip(header, r))["name"] for r in rows}
        self.assertIn("Revenue", names)

    def test_unknown_subject_area_lists_what_is_available(self):
        with self.assertRaises(slicer.SliceError) as ctx:
            slicer.build(self.kb, "Does Not Exist")
        self.assertIn("Sample Sales SA", str(ctx.exception))

    def test_directory_without_a_manifest_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(slicer.SliceError) as ctx:
                slicer.subject_areas(Path(tmp))
            self.assertIn("not a Knowledge Base", str(ctx.exception))

    def test_slice_is_deterministic(self):
        a = slicer.build(self.kb, "Sample Sales SA")
        b = slicer.build(self.kb, "Sample Sales SA")
        self.assertEqual(a, b)

    def test_written_slice_round_trips_hazardous_expressions(self):
        # The slice re-writes CSVs, so the FR-28 guard must be reapplied — a
        # formula starting '-' must survive being cut out and written again.
        sliced = slicer.build(self.kb, "Sample Sales SA")
        with tempfile.TemporaryDirectory() as out:
            slicer.write(sliced, Path(out), self.kb, "Sample Sales SA")
            header, rows = read_table(Path(out) / "logical_columns.csv")
            by_name = {dict(zip(header, r))["name"]: dict(zip(header, r)) for r in rows}
            self.assertEqual(
                by_name["Negative Margin"]["derived_expr_text"], '-1 * "%1", "x"\nnext'
            )

    def test_manifest_records_provenance(self):
        sliced = slicer.build(self.kb, "Sample Sales SA")
        with tempfile.TemporaryDirectory() as out:
            slicer.write(sliced, Path(out), self.kb, "Sample Sales SA")
            _, rows = read_table(Path(out) / "slice-manifest.csv")
            manifest = dict((r[0], r[1]) for r in rows)
            self.assertEqual(manifest["subject_area"], "Sample Sales SA")
            self.assertIn("logical_columns", manifest["tables"])


if __name__ == "__main__":
    unittest.main()
