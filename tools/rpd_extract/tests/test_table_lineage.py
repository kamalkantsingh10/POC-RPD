"""The table-level lineage sheet says what the Knowledge Base says, per chain.

The shared fixture carries one Presentation Table reaching one physical table
through two sources, which fixes the grain. Aliases and opaque views are added
to that Estate in memory, so each case differs from the base by one thing.

Standard-library ``unittest`` only (NFR13).
"""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from tools.rpd_extract import table_lineage
from tools.rpd_extract.adapters.inbound import mds_xml
from tools.rpd_extract.adapters.outbound import knowledge_base
from tools.rpd_extract.adapters.outbound.csv_writer import read_table
from tools.rpd_extract.core.model import (
    Estate,
    PhysicalTable,
    PhysicalTableDefinition,
    PresentationTable,
)

FIXTURES = Path(__file__).parent / "fixtures"
FACT = "testrpd::phys::SALES_SCHEMA.SAMP_REVENUE_F"
VIEW = "testrpd::phys::SALES_SCHEMA.V_REVENUE"
SQL = " select *\nfrom SAMP_REVENUE_F where 1=1 "


def definition(table_id: str, text: str, database: str = "DefaultMulDB"):
    return PhysicalTableDefinition(
        f"{table_id}.def.{database}", "testrpd", table_id, database, text
    )


class TableLineage(unittest.TestCase):

    def rows(self, change=None) -> list[dict[str, str]]:
        estate = mds_xml.load(FIXTURES)
        if change:
            change(estate)
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_base.write(estate, tmp, corpus_root="-", timestamp="-")
            built = table_lineage.build(tmp)
            out = Path(tmp) / "sheet" / "table-lineage.csv"
            table_lineage.write(built, out)
            header, written = read_table(out)
        self.assertEqual(header, table_lineage.HEADER)
        self.assertEqual(written, built, "the file does not round-trip what was built")
        return [dict(zip(header, row)) for row in written]

    def test_one_row_per_chain_not_per_column(self):
        rows = self.rows()
        self.assertEqual(
            [(r["subject_area"], r["presentation_table"], r["logical_table"],
              r["logical_table_source"]) for r in rows],
            [("Sample Sales SA", "Facts", "Fact Revenue", "SRC_AGG"),
             ("Sample Sales SA", "Facts", "Fact Revenue", "SRC_DETAIL")],
        )

    def test_an_ordinary_table_is_its_own_final_table(self):
        for row in self.rows():
            self.assertEqual(row["physical_table_alias"], "")
            self.assertEqual(row["physical_table_original"], "SALES_SCHEMA.SAMP_REVENUE_F")
            self.assertEqual(row["intermediate_view"], "")
            self.assertEqual(row["final_table"], "SAMP_REVENUE_F")

    def test_comment_is_left_empty(self):
        self.assertEqual({r["comment"] for r in self.rows()}, {""})

    def test_the_database_name_wins_over_the_repository_name(self):
        def rename(estate: Estate) -> None:
            estate.physical_table_definitions.append(definition(FACT, "FCT_REVENUE_DD"))

        self.assertEqual({r["final_table"] for r in self.rows(rename)}, {"FCT_REVENUE_DD"})

    def test_an_opaque_view_shows_its_sql_verbatim(self):
        def make_view(estate: Estate) -> None:
            estate.physical_tables[0] = replace(
                estate.physical_tables[0], table_type="select"
            )
            estate.physical_table_definitions.append(definition(FACT, SQL))

        for row in self.rows(make_view):
            self.assertEqual(row["physical_table_alias"], "")
            self.assertEqual(row["intermediate_view"], "SALES_SCHEMA.SAMP_REVENUE_F")
            self.assertEqual(row["final_table"], SQL)

    def test_an_alias_is_followed_to_the_view_behind_it(self):
        def alias_a_view(estate: Estate) -> None:
            estate.physical_tables[0] = replace(
                estate.physical_tables[0], source_table_id=VIEW
            )
            estate.physical_tables.append(
                PhysicalTable(VIEW, "testrpd", "SALES_SCHEMA", "V_REVENUE", "select")
            )
            estate.physical_table_definitions.append(definition(VIEW, SQL))

        for row in self.rows(alias_a_view):
            self.assertEqual(row["physical_table_alias"], "SALES_SCHEMA.SAMP_REVENUE_F")
            self.assertEqual(row["physical_table_original"], "SALES_SCHEMA.V_REVENUE")
            self.assertEqual(row["intermediate_view"], "SALES_SCHEMA.V_REVENUE")
            self.assertEqual(row["final_table"], SQL)

    def test_definitions_that_disagree_are_all_shown(self):
        def two_databases(estate: Estate) -> None:
            estate.physical_table_definitions.append(definition(FACT, "FCT_A"))
            estate.physical_table_definitions.append(definition(FACT, "FCT_B", "Oracle"))

        self.assertEqual(
            {r["final_table"] for r in self.rows(two_databases)},
            {"[DefaultMulDB] FCT_A\n[Oracle] FCT_B"},
        )

    def test_a_presentation_table_with_no_lineage_still_gets_a_row(self):
        def add_empty_table(estate: Estate) -> None:
            estate.presentation_tables.append(
                PresentationTable(
                    row_id="testrpd::pres::Sample Sales SA.Empty",
                    rpd_id="testrpd",
                    subject_area_id="testrpd::pres::Sample Sales SA",
                    name="Empty",
                )
            )

        rows = [r for r in self.rows(add_empty_table) if r["presentation_table"] == "Empty"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["subject_area"], "Sample Sales SA")
        self.assertEqual(rows[0]["physical_table_original"], "")

    def test_rerun_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_base.write(
                mds_xml.load(FIXTURES), tmp, corpus_root="-", timestamp="-"
            )
            first, second = Path(tmp) / "a.csv", Path(tmp) / "b.csv"
            table_lineage.write(table_lineage.build(tmp), first)
            table_lineage.write(table_lineage.build(tmp), second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_the_sheet_is_plain_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_base.write(
                mds_xml.load(FIXTURES), tmp, corpus_root="-", timestamp="-"
            )
            out = Path(tmp) / "plain.csv"
            table_lineage.write(table_lineage.build(tmp), out)
            first_line = out.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(
            first_line, ",".join(f'"{name}"' for name in table_lineage.HEADER)
        )

    def test_guarded_adds_a_companion_to_every_text_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_base.write(
                mds_xml.load(FIXTURES), tmp, corpus_root="-", timestamp="-"
            )
            built = table_lineage.build(tmp)
            out = Path(tmp) / "guarded.csv"
            table_lineage.write(built, out, guarded=True)
            raw_header = out.read_text(encoding="utf-8").splitlines()[0]
            header, rows = read_table(out)
        self.assertEqual(raw_header.count("_guarded"), 9)
        self.assertEqual((header, rows), (table_lineage.HEADER, built))

    def test_a_value_a_spreadsheet_would_alter_is_written_as_is_and_counted(self):
        """Plain is a choice with a cost, and the cost is reported (NFR7)."""
        hazardous = "-- revenue by day\nselect * from SAMP_REVENUE_F"

        def make_view(estate: Estate) -> None:
            estate.physical_tables[0] = replace(
                estate.physical_tables[0], table_type="select"
            )
            estate.physical_table_definitions.append(definition(FACT, hazardous))

        rows = self.rows(make_view)
        self.assertEqual({r["final_table"] for r in rows}, {hazardous})
        self.assertEqual(
            table_lineage.at_risk([list(r.values()) for r in rows]), len(rows)
        )
        self.assertEqual(table_lineage.at_risk([list(r.values()) for r in self.rows()]), 0)

    def test_a_knowledge_base_from_an_older_extractor_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_base.write(
                mds_xml.load(FIXTURES), tmp, corpus_root="-", timestamp="-"
            )
            manifest = Path(tmp) / "manifest.csv"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    "physical_table_definitions ", ""
                ),
                encoding="utf-8",
            )
            with self.assertRaises(table_lineage.TableLineageError) as raised:
                table_lineage.build(tmp)
            self.assertIn("physical_table_definitions", str(raised.exception))

    def test_a_directory_that_is_not_a_knowledge_base_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                table_lineage.main(["--kb", tmp, "--out", str(Path(tmp) / "x.csv")]), 2
            )
            self.assertFalse((Path(tmp) / "x.csv").exists())


if __name__ == "__main__":
    unittest.main()
