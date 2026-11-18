"""Tests for Stories 1.4 and 1.5 — physical and BMM extraction.

Ground Truth for every assertion here is recorded in `fixtures/GROUND-TRUTH.md`,
written when the fixtures were authored (AD-19). Standard-library ``unittest``
only: the stack table admits no third-party package at any version.

No test requires a live OBIEE instance. The core is exercised directly because
it performs no I/O; the adapter is exercised against captured samples.
"""

from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path

from tools.rpd_extract.adapters.inbound import mds_xml
from tools.rpd_extract.adapters.outbound import knowledge_base
from tools.rpd_extract.adapters.outbound.csv_writer import read_table
from tools.rpd_extract.core import identifiers as ids

FIXTURES = Path(__file__).parent / "fixtures"
CORE = Path("tools/rpd_extract/core")


def load_fixture():
    return mds_xml.load(FIXTURES)


class Identifiers(unittest.TestCase):
    def test_builds_qualified_identifier(self):
        self.assertEqual(
            ids.make_id("testrpd", ids.PHYSICAL, "SALES_SCHEMA", "SAMP_REVENUE_F"),
            "testrpd::phys::SALES_SCHEMA.SAMP_REVENUE_F",
        )

    def test_rejects_non_kebab_rpd_id(self):
        for bad in ("TestRPD", "test_rpd", "test rpd", "-test", ""):
            with self.assertRaises(ids.IdentifierError, msg=bad):
                ids.validate_rpd_id(bad)

    def test_rejects_empty_path_part(self):
        # An unresolved container would otherwise yield an identifier that looks
        # valid and points nowhere.
        with self.assertRaises(ids.IdentifierError):
            ids.make_id("testrpd", ids.PHYSICAL, "", "TABLE")

    def test_round_trips(self):
        row_id = ids.make_id("testrpd", ids.BUSINESS_MODEL, "Sample Sales", "Fact Revenue")
        self.assertEqual(
            ids.parse_id(row_id), ("testrpd", "bmm", "Sample Sales.Fact Revenue")
        )


class PhysicalLayer(unittest.TestCase):
    """Story 1.4 — Ground Truth: fixtures/GROUND-TRUTH.md#Physical layer."""

    @classmethod
    def setUpClass(cls):
        cls.estate = load_fixture()

    def test_table_identifier_resolves_container(self):
        self.assertEqual(
            [t.row_id for t in self.estate.physical_tables],
            ["testrpd::phys::SALES_SCHEMA.SAMP_REVENUE_F"],
        )

    def test_columns_are_qualified_by_table(self):
        self.assertEqual(
            sorted(c.row_id for c in self.estate.physical_columns),
            [
                "testrpd::phys::SALES_SCHEMA.SAMP_REVENUE_F.00123_CODE",
                "testrpd::phys::SALES_SCHEMA.SAMP_REVENUE_F.REVENUE",
            ],
        )

    def test_column_attributes(self):
        revenue = next(c for c in self.estate.physical_columns if c.name == "REVENUE")
        self.assertEqual(revenue.data_type, "DOUBLE")
        self.assertEqual(revenue.nullable, "true")


class BusinessModelLayer(unittest.TestCase):
    """Story 1.5 — Ground Truth: fixtures/GROUND-TRUTH.md#BMM layer."""

    @classmethod
    def setUpClass(cls):
        cls.estate = load_fixture()

    def test_logical_table_resolves_business_model(self):
        self.assertEqual(
            [t.row_id for t in self.estate.logical_tables],
            ["testrpd::bmm::Sample Sales.Fact Revenue"],
        )

    def test_measure_flag(self):
        by_name = {c.name: c for c in self.estate.logical_columns}
        self.assertTrue(by_name["Revenue"].is_measure)
        self.assertFalse(by_name["Negative Margin"].is_measure)

    def test_both_aggregation_rules_survive(self):
        # FR-4 requires dimension-specific overrides. Collapsing the two rules
        # into one loses exactly that, and loses it silently.
        rules = sorted(self.estate.aggregation_rules, key=lambda r: r.name)
        self.assertEqual([r.name for r in rules], ["AggRule_default", "AggRule_override"])
        self.assertEqual([r.is_default for r in rules], ["true", "false"])

    def test_leading_space_in_expression_is_preserved(self):
        # Real AggrRule expressions begin with a space. FR-2 forbids
        # reformatting anywhere in the chain, including stripping.
        default = next(
            r for r in self.estate.aggregation_rules if r.name == "AggRule_default"
        )
        self.assertEqual(default.expression.text, ' SUM("%1")')
        self.assertEqual(
            default.expression.text_desc, ' SUM("Sample Sales"."Fact Revenue"."Revenue")'
        )

    def test_all_three_expression_forms_captured(self):
        # AD-21: template, rendering, and bindings all travel together.
        default = next(
            r for r in self.estate.aggregation_rules if r.name == "AggRule_default"
        )
        self.assertEqual(default.expression.text, ' SUM("%1")')
        self.assertIn("Fact Revenue", default.expression.text_desc)
        self.assertEqual(
            default.expression.refs,
            ("testrpd::phys::SALES_SCHEMA.SAMP_REVENUE_F.REVENUE",),
        )

    def test_refs_are_not_inherited_between_sibling_rules(self):
        override = next(
            r for r in self.estate.aggregation_rules if r.name == "AggRule_override"
        )
        self.assertEqual(override.expression.refs, ())

    def test_derived_expression_is_verbatim(self):
        margin = next(
            c for c in self.estate.logical_columns if c.name == "Negative Margin"
        )
        self.assertEqual(margin.derived.text, '-1 * "%1", "x"\nnext')

    def test_references_resolve_to_core_identifiers_not_guids(self):
        margin = next(
            c for c in self.estate.logical_columns if c.name == "Negative Margin"
        )
        self.assertEqual(
            margin.derived.refs,
            ("testrpd::phys::SALES_SCHEMA.SAMP_REVENUE_F.REVENUE",),
        )


class PresentationLayer(unittest.TestCase):
    """Story 1.6 — Ground Truth: fixtures/GROUND-TRUTH.md#Presentation layer."""

    @classmethod
    def setUpClass(cls):
        cls.estate = load_fixture()

    def test_subject_area_resolves_business_model(self):
        area = self.estate.subject_areas[0]
        self.assertEqual(area.row_id, "testrpd::pres::Sample Sales SA")
        self.assertEqual(area.business_model, "Sample Sales")

    def test_implicit_fact_column_is_captured(self):
        # FR-4. Present on just 1 of 21 Subject Areas in the real corpus, so
        # this fixture is the primary evidence the construct is handled.
        self.assertEqual(
            self.estate.subject_areas[0].implicit_fact_column_id,
            "testrpd::bmm::Sample Sales.Fact Revenue.Revenue",
        )

    def test_aliases_are_kept(self):
        # Former names are how a Spec stays valid across a rename; dropping
        # them loses information that cannot be recovered later.
        self.assertEqual(self.estate.subject_areas[0].aliases, ("Old Sales SA",))

    def test_rename_chain_components_are_stored_separately(self):
        column = next(
            c for c in self.estate.presentation_columns if c.name == "Total Revenue"
        )
        self.assertEqual(
            column.logical_column_id, "testrpd::bmm::Sample Sales.Fact Revenue.Revenue"
        )
        self.assertEqual(column.override_logical_name, "true")
        self.assertEqual(column.display_name, "Revenue $")

    def test_presentation_columns_are_qualified_by_subject_area(self):
        self.assertEqual(
            sorted(c.row_id for c in self.estate.presentation_columns),
            [
                "testrpd::pres::Sample Sales SA.Facts.Margin",
                "testrpd::pres::Sample Sales SA.Facts.Total Revenue",
            ],
        )


class Lineage(unittest.TestCase):
    """Story 1.7 — Ground Truth: fixtures/GROUND-TRUTH.md#Logical Table Sources."""

    @classmethod
    def setUpClass(cls):
        cls.estate = load_fixture()

    def test_sources_are_qualified_by_logical_table(self):
        self.assertEqual(
            sorted(s.row_id for s in self.estate.logical_table_sources),
            [
                "testrpd::bmm::Sample Sales.Fact Revenue.src.SRC_AGG",
                "testrpd::bmm::Sample Sales.Fact Revenue.src.SRC_DETAIL",
            ],
        )

    def test_every_source_of_a_column_produces_a_lineage_row(self):
        # FR-3. A dropped source is a MISSING ROW, which reads as entirely
        # normal output — no error, no gap, nothing visibly wrong.
        revenue = [
            r for r in self.estate.lineage
            if r.logical_column_id.endswith("Fact Revenue.Revenue")
        ]
        self.assertEqual(len(revenue), 2)
        self.assertEqual(
            sorted(r.source_id.split(".src.")[-1] for r in revenue),
            ["SRC_AGG", "SRC_DETAIL"],
        )

    def test_lineage_count_matches_mapped_source_count_not_table_source_count(self):
        # The distinction the corpus forced: a table may declare more sources
        # than actually map a given column. Asserting against the table's count
        # would fail on correct data and hide the real signal.
        by_column: dict[str, set[str]] = {}
        for row in self.estate.lineage:
            by_column.setdefault(row.logical_column_id, set()).add(row.source_id)
        for column in self.estate.logical_columns:
            self.assertEqual(
                len(by_column.get(column.row_id, ())),
                column.mapped_source_count,
                column.row_id,
            )

    def test_partially_mapped_column_is_visible_as_a_gap(self):
        margin = next(
            c for c in self.estate.logical_columns if c.name == "Negative Margin"
        )
        self.assertEqual(margin.source_count, 2)
        self.assertEqual(margin.mapped_source_count, 1)

    def test_lineage_reaches_a_physical_column_and_its_table(self):
        row = next(
            r for r in self.estate.lineage
            if r.logical_column_id.endswith("Negative Margin")
        )
        self.assertEqual(
            row.physical_column_id,
            "testrpd::phys::SALES_SCHEMA.SAMP_REVENUE_F.00123_CODE",
        )
        self.assertEqual(
            row.physical_table_id, "testrpd::phys::SALES_SCHEMA.SAMP_REVENUE_F"
        )

    def test_content_filter_is_verbatim(self):
        source = next(
            s for s in self.estate.logical_table_sources if s.name == "SRC_DETAIL"
        )
        self.assertEqual(source.where_clause.text, "-1 = VALUEOF(NQ_SESSION.X)")

    def test_present_but_empty_fragment_is_not_the_same_as_absent(self):
        # All 92 real sources carry FragmentContent; none populate it. "This
        # corpus does not exercise fragmentation" must not read as "there is no
        # fragmentation" (NFR7).
        detail = next(
            s for s in self.estate.logical_table_sources if s.name == "SRC_DETAIL"
        )
        self.assertTrue(detail.fragment.is_empty)

    def test_priority_absence_is_not_invented(self):
        # MDS XML records no priority. Empty means NOT RECORDED, never lowest;
        # inferring order from document position is the guess AD-3 forbids.
        for source in self.estate.logical_table_sources:
            self.assertEqual(source.priority, "")


class KnowledgeBaseOutput(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)
        knowledge_base.write(
            load_fixture(), self.out, corpus_root="fixtures",
            timestamp="2026-08-16T00:00:00Z",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _lookup(self, table: str, name_column: str, value: str) -> dict[str, str]:
        """Read a row by header name.

        Indexing by position breaks silently whenever a column is added — which
        is exactly what happened when `mapped_source_count` was introduced.
        """
        header, rows = read_table(self.out / f"{table}.csv")
        for row in rows:
            record = dict(zip(header, row))
            if record[name_column] == value:
                return record
        raise AssertionError(f"{value!r} not found in {table}.{name_column}")

    def test_hazardous_expression_round_trips_through_csv(self):
        # Leading '-', embedded comma, embedded quotes, embedded newline —
        # every FR-28 hazard in one real value.
        margin = self._lookup("logical_columns", "name", "Negative Margin")
        self.assertEqual(margin["derived_expr_text"], '-1 * "%1", "x"\nnext')

    def test_content_filter_round_trips_through_csv(self):
        source = self._lookup("logical_table_sources", "name", "SRC_DETAIL")
        self.assertEqual(source["where_text"], "-1 = VALUEOF(NQ_SESSION.X)")
        self.assertEqual(source["priority"], "")

    def test_lineage_table_is_written(self):
        _, rows = read_table(self.out / "lineage.csv")
        self.assertEqual(len(rows), 3)

    def test_implicit_fact_column_round_trips(self):
        area = self._lookup("presentation_subject_areas", "name", "Sample Sales SA")
        self.assertEqual(
            area["implicit_fact_column_id"],
            "testrpd::bmm::Sample Sales.Fact Revenue.Revenue",
        )

    def test_hazardous_value_is_guarded_on_disk(self):
        raw = (self.out / "logical_columns.csv").read_text(encoding="utf-8")
        self.assertIn('"\'-1 * ""%1"", ""x""', raw)
        self.assertIn('"derived_expr_text_guarded"', raw)

    def test_numeric_looking_column_name_survives(self):
        _, rows = read_table(self.out / "physical_columns.csv")
        self.assertIn("00123_CODE", [r[3] for r in rows])

    def test_manifest_is_self_describing(self):
        _, rows = read_table(self.out / "manifest.csv")
        manifest = dict((r[0], r[1]) for r in rows)
        self.assertEqual(manifest["extractor_version"], knowledge_base.VERSION)
        self.assertEqual(manifest["extracted_at"], "2026-08-16T00:00:00Z")
        self.assertEqual(manifest["rpd_ids"], "testrpd")
        self.assertIn("logical_columns", manifest["tables"])

    def test_referential_integrity(self):
        _, tables = read_table(self.out / "physical_tables.csv")
        _, columns = read_table(self.out / "physical_columns.csv")
        known = {r[0] for r in tables}
        for column in columns:
            self.assertIn(column[2], known)

    def test_rerun_is_byte_identical(self):
        first = {p.name: p.read_bytes() for p in sorted(self.out.glob("*.csv"))}
        with tempfile.TemporaryDirectory() as other:
            knowledge_base.write(
                load_fixture(), other, corpus_root="fixtures",
                timestamp="2026-08-16T00:00:00Z",
            )
            second = {p.name: p.read_bytes() for p in sorted(Path(other).glob("*.csv"))}
        self.assertEqual(first, second)


class LoudFailure(unittest.TestCase):
    def test_missing_corpus_root_raises(self):
        with self.assertRaises(mds_xml.CorpusError):
            mds_xml.load(Path("/nonexistent/corpus"))

    def test_corpus_without_mds_xml_names_expected_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "empty-rpd").mkdir()
            with self.assertRaises(mds_xml.CorpusError) as ctx:
                mds_xml.load(tmp)
            self.assertIn("oracle/bi/server/base", str(ctx.exception))

    def test_single_repository_mode_uses_the_declared_rpd_id(self):
        # The ordinary case: one exported repository, named on the command line.
        estate = mds_xml.load(FIXTURES / "testrpd", "my-estate")
        self.assertEqual(estate.rpd_ids, ["my-estate"])
        self.assertTrue(
            all(t.row_id.startswith("my-estate::") for t in estate.physical_tables)
        )

    def test_single_repository_mode_rejects_a_bad_rpd_id(self):
        with self.assertRaises(ids.IdentifierError):
            mds_xml.load(FIXTURES / "testrpd", "My_Estate")

    def test_rpd_id_given_but_root_is_not_a_repository_explains_both_shapes(self):
        with self.assertRaises(mds_xml.CorpusError) as ctx:
            mds_xml.load(FIXTURES, "my-estate")
        self.assertIn("oracle/bi/server/base", str(ctx.exception))
        self.assertIn("drop --rpd-id", str(ctx.exception))

    def test_pointing_at_base_directory_names_the_fix(self):
        # The easy mistake, because `oracle/bi/server/base/` is the path the
        # documentation shows. "must contain oracle/bi/server/base" is useless
        # advice to someone standing inside it.
        base = FIXTURES / "testrpd" / "oracle" / "bi" / "server" / "base"
        with self.assertRaises(mds_xml.CorpusError) as ctx:
            mds_xml.load(base, "my-estate")
        message = str(ctx.exception)
        self.assertIn("looks like the 'base' directory itself", message)
        self.assertIn(str(FIXTURES / "testrpd"), message)

    def test_unreadable_directory_is_skipped_and_recorded(self):
        # A corpus root sitting beside another user's private directory is an
        # ordinary situation. It must not abort the run, and it must not vanish
        # silently either (AD-3, NFR7).
        import os
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(
                FIXTURES / "testrpd", root / "testrpd", dirs_exist_ok=True
            )
            blocked = root / "blocked" / "oracle" / "bi" / "server" / "base"
            blocked.mkdir(parents=True)
            os.chmod(blocked, 0o000)
            try:
                estate = mds_xml.load(root)
            finally:
                os.chmod(blocked, 0o755)

        # Readable content still extracted...
        self.assertTrue(estate.physical_tables)
        # ...and the unreadable directory is an ERROR, not a known gap.
        directory_errors = [e for e in estate.errors if e.object_type == "Directory"]
        self.assertEqual(len(directory_errors), 1)
        self.assertEqual(directory_errors[0].rpd_id, "blocked")
        self.assertEqual(directory_errors[0].kind, "unreadable")
        self.assertIn("cannot list", directory_errors[0].reason)

    def test_unmodelled_object_type_is_recorded_not_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "testrpd" / "oracle" / "bi" / "server" / "base"
            (base / "Widget").mkdir(parents=True)
            (base / "Widget" / "w1.xml").write_text(
                '<?xml version="1.0"?><Widget mdsid="mw1" name="W" '
                'xmlns="http://www.oracle.com/obis/repository"/>',
                encoding="utf-8",
            )
            estate = mds_xml.load(tmp)
            # An unmodelled type is a known GAP, not an error — nothing broke.
            gaps = [u for u in estate.unparsed if u.kind == "unmodelled_type"]
            self.assertEqual(len(gaps), 1)
            self.assertEqual(gaps[0].object_type, "Widget")
            self.assertEqual(estate.errors, [])


class CleanRebuild(unittest.TestCase):
    """--clean removes stale tables, and refuses to touch anything else."""

    def test_removes_stale_tables_from_a_knowledge_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            knowledge_base.write(load_fixture(), out, corpus_root="fixtures",
                                 timestamp="2026-01-01T00:00:00Z")
            stale = out / "old_table_from_v0.csv"
            stale.write_text("junk\n", encoding="utf-8")

            removed = knowledge_base.clean(out)

            self.assertIn("old_table_from_v0.csv", removed)
            self.assertFalse(stale.exists())
            self.assertEqual(list(out.glob("*.csv")), [])

    def test_refuses_a_directory_it_did_not_write(self):
        # Without this guard, `--out ~/Documents --clean` would delete every
        # CSV in a real directory. The manifest is the proof of ownership.
        with tempfile.TemporaryDirectory() as tmp:
            precious = Path(tmp) / "quarterly_results.csv"
            precious.write_text("important,data\n", encoding="utf-8")

            with self.assertRaises(knowledge_base.NotAKnowledgeBase):
                knowledge_base.clean(tmp)

            self.assertTrue(precious.exists())

    def test_empty_or_missing_directory_is_fine(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(knowledge_base.clean(tmp), [])
            self.assertEqual(knowledge_base.clean(Path(tmp) / "nope"), [])

    def test_non_csv_content_is_left_alone(self):
        # AD-6: re-running disturbs nothing else. Cleaning is still a re-run.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            knowledge_base.write(load_fixture(), out, corpus_root="fixtures",
                                 timestamp="2026-01-01T00:00:00Z")
            keep = out / ".gitignore"
            keep.write_text("*.csv\n", encoding="utf-8")
            (out / "notes").mkdir()

            knowledge_base.clean(out)

            self.assertTrue(keep.exists())
            self.assertTrue((out / "notes").is_dir())


class CredentialRedaction(unittest.TestCase):
    """NFR11 — credentials never reach the Knowledge Base, and never silently."""

    def _variable(self, name: str):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "testrpd" / "oracle" / "bi" / "server" / "base"
            (base / "Variable").mkdir(parents=True)
            (base / "Variable" / "v.xml").write_text(
                '<?xml version="1.0"?>'
                f'<Variable mdsid="mv" name="{name}" '
                'xmlns="http://www.oracle.com/obis/repository">'
                "<Expr mdsid=\"me\" name=\"Expr\">"
                "<ExprText>hunter2xy</ExprText>"
                "<ExprTextDesc>hunter2xy</ExprTextDesc>"
                "</Expr></Variable>",
                encoding="utf-8",
            )
            estate = mds_xml.load(tmp)
        return estate

    def test_credential_named_variable_has_its_value_withheld(self):
        estate = self._variable("REP OLAP PASSWORD")
        variable = estate.variables[0]
        self.assertTrue(variable.redacted)
        self.assertEqual(variable.expression.text, "")
        self.assertEqual(variable.expression.text_desc, "")

    def test_the_row_survives_so_the_variable_stays_visible(self):
        # Withholding a value must not hide that the variable exists.
        estate = self._variable("REP OLAP PASSWORD")
        self.assertEqual(estate.variables[0].name, "REP OLAP PASSWORD")

    def test_redaction_is_recorded_not_silent(self):
        # AD-3 / NFR7: never remove something without saying so.
        estate = self._variable("db secret")
        gaps = [u for u in estate.unparsed if u.kind == "redacted_value"]
        self.assertEqual(len(gaps), 1)
        self.assertIn("NFR11", gaps[0].detail)

    def test_ordinary_variables_keep_their_values(self):
        estate = self._variable("CURRENT_YEAR")
        self.assertFalse(estate.variables[0].redacted)
        self.assertEqual(estate.variables[0].expression.text, "hunter2xy")

    def test_matcher_is_deliberately_broad(self):
        from tools.rpd_extract.core.model import is_credential_name
        for name in ("PASSWORD", "db_pwd", "API Key", "auth token", "client secret"):
            self.assertTrue(is_credential_name(name), name)
        for name in ("CURRENT_YEAR", "Passed", "REGION"):
            # 'Passed' must not match: over-redaction is cheap, but so is noise.
            self.assertFalse(is_credential_name(name), name)


class SubObjectHonesty(unittest.TestCase):
    """Whole-object honesty is not enough (AD-3, NFR7).

    An object can parse "successfully" while attributes and child elements on
    it are discarded silently — the same failure mode, one level down.
    """

    def test_unread_attribute_on_a_parsed_object_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "testrpd" / "oracle" / "bi" / "server" / "base"
            (base / "PhysicalTable").mkdir(parents=True)
            (base / "Schema").mkdir(parents=True)
            (base / "Schema" / "s.xml").write_text(
                '<?xml version="1.0"?><Schema mdsid="ms" name="S" '
                'xmlns="http://www.oracle.com/obis/repository"/>',
                encoding="utf-8",
            )
            (base / "PhysicalTable" / "t.xml").write_text(
                '<?xml version="1.0"?><PhysicalTable mdsid="mt" name="T" '
                'xmlns="http://www.oracle.com/obis/repository" '
                'rowCount="42.0" someBrandNewAttribute="x" '
                'containerRef="/oracle/bi/server/base/Schema/s.xml#ms"/>',
                encoding="utf-8",
            )
            estate = mds_xml.load(tmp)

        # The table itself parsed fine — no error.
        self.assertTrue(estate.physical_tables)
        self.assertEqual(estate.errors, [])
        # But the attributes we never read are reported, not dropped.
        unread = {u.detail for u in estate.unparsed if u.kind == "unread_attribute"}
        self.assertIn("PhysicalTable@rowCount", unread)
        self.assertIn("PhysicalTable@someBrandNewAttribute", unread)

    def test_the_object_root_is_not_reported_as_unread(self):
        # We read its attributes, so the element is consumed. Reporting it
        # would bury the real signal in noise.
        estate = mds_xml.load(FIXTURES)
        unread = {u.detail for u in estate.unparsed if u.kind == "unread_element"}
        self.assertNotIn("PhysicalTable", unread)
        self.assertNotIn("LogicalTable", unread)

    def test_gaps_and_errors_are_separate(self):
        # "We have not built this" and "this went wrong" are different
        # questions. 200 unmodelled types must not bury 31 broken references.
        estate = mds_xml.load(FIXTURES)
        self.assertTrue(hasattr(estate, "errors"))
        for gap in estate.unparsed:
            self.assertIn(
                gap.kind,
                {"unmodelled_type", "unread_attribute", "unread_element",
                 "unread_text", "undiscovered_file", "redacted_value"},
            )


class ArchitecturalInvariants(unittest.TestCase):
    def _imports(self, path: Path) -> set[str]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module)
        return roots

    def test_core_never_imports_an_adapter(self):
        """AD-15 — adapters depend on core, never the reverse."""
        for module in CORE.glob("*.py"):
            for imported in self._imports(module):
                self.assertNotIn("adapters", imported, f"{module} imports {imported}")

    def test_core_has_no_third_party_imports(self):
        """NFR13 / FR-23 — standard library only, at any version."""
        allowed = set(sys.stdlib_module_names) | {"__future__"}
        for module in CORE.glob("*.py"):
            for imported in self._imports(module):
                root = imported.split(".")[0]
                if root == "tools":
                    continue
                self.assertIn(root, allowed, f"{module} imports {imported}")

    def test_core_contains_no_serialisation_concepts(self):
        """AD-20 — no GUIDs, file paths, or #mdsid fragments reach the core.

        The whole point of naming the adapter `mds_xml` rather than building a
        format-neutral layer is that the core stays format-free. A leak here is
        a defect against AD-20, not a shortcut.
        """
        banned = ("mdsid", ".xml", "objectRef", "ExprTextDesc", "oracle/bi/server")
        for module in CORE.glob("*.py"):
            body = _code_without_prose(module)
            for token in banned:
                self.assertNotIn(
                    token, body, f"{module} mentions {token!r} — AD-20 keeps it in the adapter"
                )


def _code_without_prose(path: Path) -> str:
    """Executable source with docstrings and comments removed.

    AD-20 constrains what the core *does*, not what it explains about itself —
    a docstring stating "no #mdsid fragments here" is the rule being documented,
    not broken. Stripping via AST rather than by line prefix is what keeps the
    check honest in both directions.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(ast.fix_missing_locations(tree))


if __name__ == "__main__":
    unittest.main()


class ParityCriticalMetadata(unittest.TestCase):
    """Story 1.10 — FR-4 constructs, verified against Constructed Case Ground Truth."""

    @classmethod
    def setUpClass(cls):
        cls.estate = mds_xml.load(Path("estate/test-corpus/constructed-cases"))

    def test_lts_priority_is_captured_when_recorded(self):
        priorities = {s.name: s.priority for s in self.estate.logical_table_sources}
        self.assertEqual(priorities, {"LTS_DETAIL": "0", "LTS_MONTHLY_AGG": "1"})

    def test_fragmentation_predicate_is_verbatim(self):
        source = next(
            s for s in self.estate.logical_table_sources if s.name == "LTS_MONTHLY_AGG"
        )
        # The double space before TIMESTAMP is deliberate: FR-2 forbids
        # whitespace collapsing anywhere in the chain.
        self.assertIn('"MONTH_DT" <  TIMESTAMP', source.fragment.text_desc)

    def test_both_aggregation_rules_survive_including_the_override(self):
        rules = {r.name: r.is_default for r in self.estate.aggregation_rules}
        self.assertEqual(
            rules, {"AggRule_Default": "true", "AggRule_Override_Time": "false"}
        )

    def test_periodrolling_is_flagged_and_verbatim(self):
        column = next(
            c for c in self.estate.logical_columns if c.name == "Rolling Amount 3M"
        )
        self.assertEqual(column.derived.text, 'PERIODROLLING("%1", -2, 0)')
        self.assertEqual(column.time_series, ("PERIODROLLING",))

    def test_implicit_fact_column_resolves_to_an_identifier(self):
        area = self.estate.subject_areas[0]
        self.assertEqual(
            area.implicit_fact_column_id,
            "constructed::bmm::Constructed BM.Fact Sales.Amount",
        )

    def test_constructed_cases_parse_without_errors(self):
        self.assertEqual(self.estate.errors, [])


class AccuracyReport(unittest.TestCase):
    """SM-7 — reported per construct type, never as one aggregate figure."""

    @classmethod
    def setUpClass(cls):
        from tools.rpd_extract import verify

        cls.verify = verify
        cls.rows = verify.build_report(
            Path("estate/test-corpus/constructed-cases"),
            Path("estate/test-corpus/constructed-cases"),
        )

    def test_no_construct_fails(self):
        failures = [r for r in self.rows if r[2] == self.verify.FAIL]
        self.assertEqual(failures, [])

    def test_absent_construct_is_reported_unimplemented_not_passed(self):
        # AD-19: a construct without a fixture is unimplemented. Silence must
        # never read as success.
        report = self.verify.build_report(FIXTURES, FIXTURES)
        statuses = {r[0]: r[2] for r in report if r[1] == self.verify.CORPUS}
        self.assertEqual(
            statuses["LTS fragmentation predicate"], self.verify.UNIMPLEMENTED
        )

    def test_corpus_and_constructed_evidence_are_never_merged(self):
        # FR-31. The same construct may appear twice — once per evidence kind —
        # and the two must stay distinguishable.
        kinds = {r[1] for r in self.rows}
        self.assertEqual(kinds, {self.verify.CORPUS, self.verify.CONSTRUCTED})


class PresentationHierarchies(unittest.TestCase):
    """Story 2.9 Part 1 — the presentation layer stops being incomplete.

    Ground Truth is the fixture in ``fixtures/testrpd``: one Dimension with two
    logical levels, one PresentationHierarchy with two presentation levels, and
    two display columns on the lower level.
    """

    @classmethod
    def setUpClass(cls):
        cls.estate = load_fixture()

    def test_a_hierarchy_hangs_off_its_presentation_table(self):
        """AC 2.9-1."""
        hier = next(h for h in self.estate.presentation_hierarchies
                    if h.name == "Time")
        table = {t.row_id for t in self.estate.presentation_tables}
        self.assertIn(hier.table_id, table)
        self.assertEqual(hier.level_count, 2)

    def test_levels_keep_their_drill_order(self):
        """AC 2.9-2: position is the drill order, and reordering changes meaning."""
        time_id = next(h for h in self.estate.presentation_hierarchies
                       if h.name == "Time").row_id
        levels = sorted((l for l in self.estate.presentation_levels
                         if l.hierarchy_id == time_id), key=lambda l: l.position)
        self.assertEqual([l.name for l in levels], ["Total", "Year"])
        self.assertEqual([l.position for l in levels], [0, 1])
        hier = next(h for h in self.estate.presentation_hierarchies
                    if h.name == "Time").row_id
        levels = [l for l in levels if l.hierarchy_id == hier]
        for level in levels:
            self.assertEqual(level.hierarchy_id, hier)

    def test_the_drill_path_maps_levels_to_presentation_columns(self):
        """AC 2.9-3: this is what a Power BI hierarchy is built from."""
        cols = self.estate.presentation_level_columns
        self.assertEqual(len(cols), 2)
        known = {c.row_id for c in self.estate.presentation_columns}
        for entry in cols:
            self.assertIn(entry.presentation_column_id, known)
        # Both hang off the lower level; the grand-total level displays nothing.
        self.assertEqual(len({c.level_id for c in cols}), 1)

    def test_a_logical_level_reference_resolves_to_a_row(self):
        """AC 2.9-4: no dangling identifier — FR-8 wants exactly one row."""
        levels = {l.row_id for l in self.estate.logical_levels}
        self.assertTrue(levels)
        for level in self.estate.presentation_levels:
            self.assertIn(level.logical_level_id, levels)

    def test_drill_semantics_are_carried_not_dropped(self):
        """AC 2.9-4: ragged and skip-level change what a hierarchy means."""
        dim = next(d for d in self.estate.logical_dimensions
                   if d.name == "Time Dim")
        self.assertTrue(dim.is_ragged)
        self.assertFalse(dim.is_skipped)
        self.assertFalse(dim.is_value_based)
        self.assertEqual(dim.level_count, 2)

    def test_the_two_types_no_longer_report_as_unmodelled(self):
        """AC 2.9-5."""
        unmodelled = {u.object_type for u in self.estate.unparsed
                      if u.kind == "unmodelled_type"}
        self.assertNotIn("PresentationHierarchy", unmodelled)
        self.assertNotIn("Dimension", unmodelled)


class ParentChildHierarchies(unittest.TestCase):
    """Story 2.9 — a value-based hierarchy has no levels at all.

    One of the fixture corpus's 25 dimensions is parent-child, and its
    PresentationHierarchy carries the display column directly rather than on a
    level. Reading display columns only from levels loses it silently.
    """

    @classmethod
    def setUpClass(cls):
        cls.estate = load_fixture()


    def test_a_value_based_hierarchy_declares_itself(self):
        dim = next(d for d in self.estate.logical_dimensions if d.name == "Rep Tree")
        self.assertTrue(dim.is_value_based)

    def test_it_has_no_levels_and_that_is_not_a_failure(self):
        hier = next(h for h in self.estate.presentation_hierarchies
                    if h.name == "Rep Tree")
        self.assertEqual(hier.level_count, 0)
        self.assertEqual(
            [l for l in self.estate.presentation_levels
             if l.hierarchy_id == hier.row_id], []
        )

    def test_its_display_column_is_kept_on_the_hierarchy(self):
        """Otherwise the only column a parent-child hierarchy names is dropped."""
        hier = next(h for h in self.estate.presentation_hierarchies
                    if h.name == "Rep Tree")
        self.assertTrue(hier.display_column_id)
        known = {c.row_id for c in self.estate.presentation_columns}
        self.assertIn(hier.display_column_id, known)

    def test_a_dimension_identifier_is_qualified_by_its_business_model(self):
        """FR-8: four dimensions named 'Times' exist in the corpus.

        Falling back to the dimension's own name as its container collapses
        them onto one identifier, which is a duplicate_identifier error, not a
        naming preference.
        """
        for dim in self.estate.logical_dimensions:
            _, _, path = ids.parse_id(dim.row_id)
            container = path.rsplit(".", 1)[0]
            self.assertNotEqual(container, dim.name, dim.row_id)


class AliasesAndTableDefinitions(unittest.TestCase):
    """What a physical table really is: an alias of another, an opaque view's
    SQL, or a database object under a different name.

    Built here rather than added to the shared fixture, whose recorded Ground
    Truth every other class counts against.
    """

    NS = 'xmlns="http://www.oracle.com/obis/repository"'
    SQL = " Select tm.*,\n  to_number(tm.year) as key_year\nfrom DIM_TIME tm "

    def load(self, extra: dict[str, str] | None = None) -> Estate:
        container = 'containerRef="/oracle/bi/server/base/Schema/s.xml#ms"'
        files = {
            # Named so the alias is parsed BEFORE the table it points at.
            "a_alias.xml": (
                f'<PhysicalTable mdsid="malias" name="Time" type="select" {self.NS} '
                f'{container} sourceTableRef="/oracle/bi/server/base/PhysicalTable/'
                f'z_view.xml#mview"/>'
            ),
            "z_view.xml": (
                f'<PhysicalTable mdsid="mview" name="DIM_TIME_DD" type="select" '
                f'{self.NS} {container}><DBMapItem name="DefaultMulDB"><Value>'
                f'<![CDATA[{self.SQL}]]></Value></DBMapItem></PhysicalTable>'
            ),
            "renamed.xml": (
                f'<PhysicalTable mdsid="mren" name="Operations" type="none" '
                f'{self.NS} {container}><DBMapItem name="DefaultMulDB"><Value>'
                f'FCT_OPERATIONS_DD</Value></DBMapItem><DBMapItem name="Oracle">'
                f'<Value>FCT_OPS_ORA</Value></DBMapItem></PhysicalTable>'
            ),
            "plain.xml": (
                f'<PhysicalTable mdsid="mplain" name="CHANNELS" type="none" '
                f'{self.NS} {container}/>'
            ),
            **(extra or {}),
        }
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "testrpd" / "oracle" / "bi" / "server" / "base"
            (base / "PhysicalTable").mkdir(parents=True)
            (base / "Schema").mkdir(parents=True)
            (base / "Schema" / "s.xml").write_text(
                f'<?xml version="1.0"?><Schema mdsid="ms" name="S" {self.NS}/>',
                encoding="utf-8",
            )
            for name, body in files.items():
                (base / "PhysicalTable" / name).write_text(
                    '<?xml version="1.0"?>' + body, encoding="utf-8"
                )
            return mds_xml.load(tmp)

    def test_an_alias_names_the_table_it_stands_for(self):
        tables = {t.name: t for t in self.load().physical_tables}
        self.assertEqual(tables["Time"].source_table_id, "testrpd::phys::S.DIM_TIME_DD")

    def test_a_table_that_is_not_an_alias_has_no_source(self):
        tables = {t.name: t for t in self.load().physical_tables}
        for name in ("DIM_TIME_DD", "Operations", "CHANNELS"):
            self.assertEqual(tables[name].source_table_id, "", name)

    def test_view_sql_is_verbatim(self):
        """Leading space, line breaks and trailing space all survive (FR-2)."""
        estate = self.load()
        texts = {d.table_id: d.text for d in estate.physical_table_definitions
                 if d.table_id.endswith("DIM_TIME_DD")}
        self.assertEqual(texts, {"testrpd::phys::S.DIM_TIME_DD": self.SQL})

    def test_every_database_type_gets_its_own_row(self):
        estate = self.load()
        rows = sorted(
            (d.database, d.text) for d in estate.physical_table_definitions
            if d.table_id == "testrpd::phys::S.Operations"
        )
        self.assertEqual(
            rows, [("DefaultMulDB", "FCT_OPERATIONS_DD"), ("Oracle", "FCT_OPS_ORA")]
        )

    def test_a_table_with_no_definition_has_no_row(self):
        estate = self.load()
        self.assertFalse([d for d in estate.physical_table_definitions
                          if d.table_id.endswith("CHANNELS")])

    def test_nothing_read_here_is_still_reported_as_unread(self):
        estate = self.load()
        self.assertEqual(estate.errors, [])
        estate.check_identifier_uniqueness()
        self.assertEqual(estate.errors, [])
        unread = {u.detail for u in estate.unparsed}
        for detail in ("PhysicalTable@sourceTableRef", "DBMapItem", "DBMapItem@name",
                       "Value", "Value#text"):
            self.assertNotIn(detail, unread)

    def test_an_alias_whose_source_does_not_resolve_is_an_error_not_a_table(self):
        estate = self.load({
            "dangling.xml": (
                f'<PhysicalTable mdsid="mdang" name="Orphan" type="none" {self.NS} '
                f'containerRef="/oracle/bi/server/base/Schema/s.xml#ms" '
                f'sourceTableRef="/oracle/bi/server/base/PhysicalTable/gone.xml#mgone"/>'
            ),
        })
        orphan = next(t for t in estate.physical_tables if t.name == "Orphan")
        self.assertEqual(orphan.source_table_id, "")
        self.assertEqual(
            [(e.kind, e.source_id) for e in estate.errors],
            [("unresolved_reference", "testrpd::phys::S.Orphan")],
        )

    def test_both_survive_the_knowledge_base(self):
        with tempfile.TemporaryDirectory() as out:
            knowledge_base.write(self.load(), out, corpus_root="-", timestamp="-")
            header, rows = read_table(Path(out) / "physical_tables.csv")
            alias = next(dict(zip(header, r)) for r in rows if "Time" in r)
            self.assertEqual(alias["source_table_id"], "testrpd::phys::S.DIM_TIME_DD")
            header, rows = read_table(Path(out) / "physical_table_definitions.csv")
            texts = {dict(zip(header, r))["text"] for r in rows}
            self.assertIn(self.SQL, texts)
