"""One estate, both halves, one Knowledge Base.

Every other test exercises a single half. ``test_catalog.py`` proves the layout
resolver *recognises* a paired estate, but it does so against an empty
``catalog/`` and a stub repository — directory shape only. Nothing anywhere runs
an extraction in which both adapters contribute to the same Estate.

That is the gap this file closes. The fixture is a constructed catalog authored
against the constructed repository's presentation layer, so the two halves name
the same Subject Area and the correspondence between them is checkable.

**These are hand-authored fixtures.** Read the warning in
``estate/test-corpus/constructed-cases/GROUND-TRUTH.md`` before quoting any
figure from them: a constructed pair proves the *mechanism* joins, never that a
real OBIEE catalog and a real repository name things this way.
"""

from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.rpd_extract import cli, layout
from tools.rpd_extract.adapters.outbound import knowledge_base
from tools.rpd_extract.core import identifiers as ids
from tools.rpd_extract.core.model import (
    COMPUTED_NOT_SOURCED,
    NOT_A_COLUMN_REFERENCE,
    OUTSIDE_SEMANTIC_MODEL,
    RESOLVED_CASE,
    RESOLVED_EXACT,
    RESOLVED_NONE,
    SOURCED,
)

CASES = Path("estate/test-corpus/constructed-cases")
RPD_HALF = CASES / "constructed"
CATALOG_HALF = CASES / "constructed-catalog"

#: Distinct from every corpus rpd-id and from ``constructed`` itself, so the
#: paired estate's identifiers can never collide with either (AD-7, AD-8).
RPD_ID = "constructed-pair"

#: The Subject Area the repository half defines, in PresentationCatalog/cc-sa.xml.
SUBJECT_AREA = "Constructed SA"


class ConstructedPairTests(unittest.TestCase):
    """A paired estate, assembled from the two committed halves."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        estate_dir = root / RPD_ID
        # Assembled here rather than committed as a third tree, so the two
        # halves keep exactly one copy each and cannot drift apart.
        shutil.copytree(RPD_HALF, estate_dir / "rpd")
        shutil.copytree(CATALOG_HALF, estate_dir / "catalog")

        cls.found = layout.resolve(root)
        cls.estate = cli.extract(cls.found)
        cls.out = root / "kb"
        knowledge_base.write(cls.estate, cls.out, corpus_root=str(root),
                             timestamp="2026-01-01T00:00:00Z")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def table(self, name: str) -> list[dict]:
        with open(self.out / f"{name}.csv", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_both_halves_are_declared_under_one_rpd_id(self):
        """The folder name is the declaring act (AD-22)."""
        self.assertEqual(self.found.rpd_ids, [RPD_ID])
        self.assertEqual(self.found.halves_of(RPD_ID),
                         [layout.RPD, layout.CATALOG])
        self.assertTrue(self.found.is_paired(RPD_ID))
        self.assertTrue(all(half.declared_by for half in self.found.halves))

    def test_one_extraction_carries_both_halves(self):
        """Both adapters contribute to the same Estate — the actual gap."""
        self.assertTrue(self.estate.subject_areas)
        self.assertTrue(self.estate.analyses)
        self.assertTrue(self.estate.dashboards)
        for row in (self.estate.subject_areas
                    + self.estate.analyses + self.estate.dashboards):
            self.assertEqual(ids.parse_id(row.row_id)[0], RPD_ID)

    def test_the_two_layers_coexist_without_collision(self):
        """``pres`` and ``cat`` rows share an rpd-id and stay distinguishable."""
        layers = {ids.parse_id(row.row_id)[1]
                  for row in self.estate.subject_areas}
        self.assertEqual(layers, {ids.PRESENTATION})
        layers = {ids.parse_id(row.row_id)[1] for row in self.estate.analyses}
        self.assertEqual(layers, {ids.CATALOG})
        # check_identifier_uniqueness already ran inside extract(); this asserts
        # it found nothing to report rather than trusting that it was called.
        self.assertEqual([e for e in self.estate.errors
                          if e.kind == "duplicate_identifier"], [])

    def test_the_manifest_records_the_pairing_as_declared(self):
        manifest = {row["key"]: row["value"] for row in self.table("manifest")}
        self.assertEqual(manifest[f"halves_present:{RPD_ID}"], "rpd catalog")
        self.assertIn("declared by the Operator", manifest[f"pairing:{RPD_ID}"])
        self.assertIn("Never inferred", manifest[f"pairing:{RPD_ID}"])

    def test_the_catalog_half_is_not_itself_an_estate(self):
        """``constructed-catalog/`` sits inside a multi-estate corpus root.

        ``--corpus estate/test-corpus/constructed-cases`` treats every child
        folder as an estate named after it. The catalog half declares no halves
        and is not a repository, so it is skipped — but *skipped* and *emitted
        as an empty estate called ``constructed-catalog``* look identical in a
        Knowledge Base, and only one of them is right.
        """
        self.assertEqual(layout.resolve(CASES).rpd_ids, ["constructed"])

    def test_the_fixture_is_a_clean_positive_control(self):
        """Nothing in this estate is meant to fail, so anything that does is news.

        The real fixture cannot make this claim — 1583 of its references point
        into a catalog root nobody has. Here every reference has a target that
        exists, which is what makes an error row a regression signal rather
        than a known condition to be read past.
        """
        self.assertEqual([f"{e.kind}: {e.reason}" for e in self.estate.errors], [])
        referencing = [row for row in self.table("dashboard_contents")
                       if row["reference"]]
        self.assertTrue(referencing)
        for row in referencing + [f for f in self.table("analysis_filters")
                                  if f["reference"]]:
            self.assertNotEqual(row["resolution"], RESOLVED_NONE, row["reference"])
            self.assertTrue(row["target_id"], row["reference"])

    def test_the_catalog_names_the_subject_area_the_repository_defines(self):
        """The cross-half correspondence, as a name — which is all it is.

        Both halves come from one authored estate, so this is the one place the
        two can be checked against each other at all.
        """
        defined = {row["name"] for row in self.table("presentation_subject_areas")}
        self.assertIn(SUBJECT_AREA, defined)
        asked = {row["subject_area"] for row in self.table("analysis_criteria")}
        self.assertTrue(asked)
        self.assertEqual({a.strip('"') for a in asked}, {SUBJECT_AREA})

    def test_the_subject_area_is_a_name_and_not_a_key(self):
        """FR-7 is not implemented, and this pins that rather than hiding it.

        ``subject_area`` is stored as the catalog wrote it, quotes intact, and
        is never resolved to a Knowledge Base identifier. A paired estate does
        not change that — only writing FR-7 would.
        """
        for row in self.table("analysis_criteria"):
            self.assertTrue(row["subject_area"].startswith('"'))
            self.assertNotIn("::", row["subject_area"])
        self.assertNotIn("presentation_subject_area_id",
                         self.table("analysis_criteria")[0].keys())


class ReportLineageTests(ConstructedPairTests):
    """Story 2.9 Part 2 — FR-7, demonstrated on the only matched pair there is.

    **This proves the mechanism, not the estate.** Both halves were authored by
    the same hand, so their agreement is a property of the author. FR-31 keeps
    accuracy measured here separate from accuracy measured against real corpus
    content, and the two are never merged.
    """

    def test_the_subject_area_resolves_without_overwriting_the_verbatim_value(self):
        """AC 2.9-7."""
        rows = self.table("report_lineage")
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row["subject_area"], '"Constructed SA"')
            self.assertTrue(row["subject_area_id"])
        # the source table is untouched
        for crit in self.table("analysis_criteria"):
            self.assertEqual(crit["subject_area"], '"Constructed SA"')

    def test_a_bare_column_reference_completes_the_four_layer_path(self):
        """AC 2.9-8: report column -> presentation -> logical -> physical."""
        rows = {r["reference_text"]: r for r in self.table("report_lineage")}
        amount = rows['"Sales Facts"."Amount"']
        self.assertTrue(amount["presentation_column_id"].endswith(
            "Constructed SA.Sales Facts.Amount"))
        self.assertTrue(amount["logical_column_id"])
        self.assertTrue(amount["physical_column_id"])
        self.assertEqual(amount["source_state"], SOURCED)

    def test_a_bmm_derived_column_says_computed_rather_than_blank(self):
        """AC 2.9-11: no physical row is a fact, not a lookup failure."""
        rows = {r["reference_text"]: r for r in self.table("report_lineage")}
        rolling = rows['"Sales Facts"."Rolling Amount 3M"']
        self.assertTrue(rolling["presentation_column_id"])
        self.assertEqual(rolling["physical_column_id"], "")
        self.assertEqual(rolling["source_state"], COMPUTED_NOT_SOURCED)

    def test_every_row_records_how_it_resolved(self):
        """AC 2.9-9."""
        allowed = {RESOLVED_EXACT, RESOLVED_CASE, RESOLVED_NONE,
                   NOT_A_COLUMN_REFERENCE, OUTSIDE_SEMANTIC_MODEL}
        for row in self.table("report_lineage"):
            self.assertIn(row["resolution"], allowed)

    def test_one_row_per_analysis_column(self):
        """AC 2.9-6: nothing is dropped for being unresolvable."""
        self.assertEqual(len(self.table("report_lineage")),
                         len(self.table("analysis_columns")))


if __name__ == "__main__":
    unittest.main()
