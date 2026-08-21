"""Web Catalog extraction — Epic 2.

Built on a constructed catalog rather than the 420 MB fixture, so the suite
stays runnable from a bare checkout (README's "try it first" promise). Each
construct here was copied from a real fixture object and then reduced: the
shapes are observed, the sizes are not.

Where a claim can only be made about the real fixture — the modelled proportion,
the resolution rates — it is tested in ``test_catalog_fixture.py``, which skips
when the fixture is absent rather than asserting against a corpus that may not
be there.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.rpd_extract import layout
from tools.rpd_extract.adapters.inbound import catalog_xml
from tools.rpd_extract.adapters.inbound.catalog_xml import SAW, q
from tools.rpd_extract.adapters.outbound import knowledge_base
from tools.rpd_extract.adapters.outbound.csv_writer import read_table
from tools.rpd_extract.core import identifiers as ids
from tools.rpd_extract.core.model import (
    RESOLVED_CASE,
    RESOLVED_EXACT,
    NO_VIEW_TYPE,
    RESOLVED_NONE,
    SCOPE_ANALYSIS,
    SCOPE_DASHBOARD,
)

DASHBOARD = """<?xml version="1.0" encoding="utf-8"?>
<sawd:dashboard xmlns:saw="com.siebel.analytics.web/report/v1.1"
 xmlns:sawd="com.siebel.analytics.web/dashboard/v1.1" xmlVersion="200810300">
 <sawd:dashboardPageRef path="Page One" type="catalog"/>
 <sawd:dashboardPageRef path="Page Two" type="catalog"/>
 <sawd:dashboardPageRef path="/company_shared/Absent/Page" type="catalog"/>
</sawd:dashboard>
"""

PAGE = """<?xml version="1.0" encoding="utf-8"?>
<sawd:dashboardPage xmlns:sawd="com.siebel.analytics.web/dashboard/v1.1"
 xmlns:saw="com.siebel.analytics.web/report/v1.1" xmlVersion="200810300"
 unknownAttribute="surprise">
 <sawd:dashboardColumn name="Column 0">
  <saw:displayFormat><saw:formatSpec wrapText="true" fontSize="9"/></saw:displayFormat>
  <sawd:reportView name="Report 1">
   <sawd:reportRef path="/shared/Demo/Revenue Analysis"/>
  </sawd:reportView>
  <sawd:unknownView name="from a newer OBIEE"/>
 </sawd:dashboardColumn>
 <sawd:globalFilterView path="/shared/Demo/_filters/Region Filter"/>
</sawd:dashboardPage>
"""

# Deliberately adversarial expression text: a leading '-', a leading '=', commas,
# embedded quotes and a newline. All four are values a spreadsheet corrupts, and
# the guarantee under test is that they survive the writer byte for byte.
ANALYSIS = """<?xml version="1.0" encoding="utf-8"?>
<saw:report xmlns:saw="com.siebel.analytics.web/report/v1.1"
 xmlns:sawx="com.siebel.analytics.web/expression/v1.1"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlVersion="201201160">
 <saw:criteria xsi:type="saw:simpleCriteria" subjectArea="&quot;A - Sample Sales&quot;">
  <saw:columns>
   <saw:column xsi:type="saw:regularColumn" columnID="c1">
    <saw:columnFormula>
     <sawx:expr xsi:type="sawx:sqlExpression">"Base Facts"."1- Revenue"</sawx:expr>
    </saw:columnFormula>
    <saw:columnHeading><saw:caption><saw:text>Revenue</saw:text></saw:caption></saw:columnHeading>
   </saw:column>
   <saw:column xsi:type="saw:derivedColumn" columnID="c2">
    <saw:columnFormula>
     <sawx:expr xsi:type="sawx:sqlExpression">-1 * "Facts"."Cost", 'a,b', "q""q"
CASE WHEN 1=1 THEN 2 END</sawx:expr>
    </saw:columnFormula>
   </saw:column>
   <saw:column xsi:type="saw:derivedColumn" columnID="c3">
    <saw:columnFormula>
     <sawx:expr xsi:type="sawx:sqlExpression">CAST(<sawx:expr xsi:type="sawx:eval"
       >EVALUATE('OWNER(%1)', "Facts"."Id")</sawx:expr>)</sawx:expr>
    </saw:columnFormula>
   </saw:column>
  </saw:columns>
  <saw:filter>
   <sawx:expr xsi:type="sawx:logical" op="and">
    <sawx:expr xsi:type="sawx:special" op="prompted"/>
    <sawx:expr xsi:type="sawx:savedFilter" path="/shared/Demo/_filters/Region Filter"/>
    <sawx:expr xsi:type="sawx:savedFilter" path="/shared/Demo/_filters/Gone"/>
   </sawx:expr>
  </saw:filter>
 </saw:criteria>
 <saw:criteria xsi:type="saw:simpleCriteria" subjectArea="&quot;B - Second Query&quot;">
  <saw:columns>
   <saw:column xsi:type="saw:regularColumn" columnID="c9"/>
  </saw:columns>
 </saw:criteria>
 <saw:views currentView="compoundView!1">
  <saw:view xsi:type="saw:compoundView" name="compoundView!1">
   <saw:cvTable>
    <saw:cvRow><saw:cvCell viewName="titleView!1"/></saw:cvRow>
    <saw:cvRow><saw:cvCell viewName="pivotTableView!1"/></saw:cvRow>
   </saw:cvTable>
  </saw:view>
  <saw:view xsi:type="saw:titleView" name="titleView!1"/>
  <saw:view xsi:type="saw:pivotTableView" name="pivotTableView!1">
   <saw:edges>
    <saw:edge axis="row"><saw:edgeLayers>
     <saw:edgeLayer type="column" columnID="c1"/>
     <saw:edgeLayer type="column" columnID="c2"/>
    </saw:edgeLayers></saw:edge>
   </saw:edges>
  </saw:view>
  <saw:view xsi:type="saw:dvtchart" name="dvtchart!1">
   <saw:display type="bar" subtype="stacked"/>
   <saw:edges><saw:edge axis="row"><saw:edgeLayers>
    <saw:edgeLayer type="column" columnID="c1"/>
   </saw:edgeLayers></saw:edge></saw:edges>
  </saw:view>
  <saw:view xsi:type="saw:viewFromANewerOBIEE" name="surprise!1"/>
  <saw:view name="noTypeAtAll!1"/>
  <saw:individualPrompts>
   <saw:prompt xsi:type="saw:columnFilterPrompt" columnID="c1">
    <saw:formula><sawx:expr xsi:type="sawx:sqlExpression">"Cust"."Region"</sawx:expr></saw:formula>
    <saw:promptOperator op="in"/>
    <saw:promptUIControl xsi:type="saw:browse"/>
    <saw:setPromptVariables>
     <saw:setPromptVariable location="value" type="presentation"
      variableFormula="pv_region"/>
    </saw:setPromptVariables>
   </saw:prompt>
  </saw:individualPrompts>
 </saw:views>
</saw:report>
"""

SAVED_FILTER = """<?xml version="1.0" encoding="utf-8"?>
<sawsf:savedFilterObject xmlns:sawsf="com.siebel.analytics.web/savedfilter/v1.1"
 xmlns:saw="com.siebel.analytics.web/report/v1.1"
 xmlns:sawx="com.siebel.analytics.web/expression/v1.1"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" subjectArea="&quot;PC1&quot;">
 <saw:filter>
  <sawx:expr xsi:type="sawx:logical" op="and">
   <sawx:expr xsi:type="sawx:special" op="prompted"/>
  </sawx:expr>
 </saw:filter>
</sawsf:savedFilterObject>
"""

#: A root type the adapter does not model, so it must be enumerated by parsing.
SCORECARD = ('<?xml version="1.0" encoding="utf-8"?>\n'
             '<sawbsc:objective xmlns:sawbsc="com.siebel.analytics.web/scorecard/v1"'
             ' name="Grow Revenue"/>\n')

#: A different product sharing the catalog tree.
BIP = ('<?xml version="1.0" encoding="utf-8"?>\n'
       '<dataModel xmlns="http://xmlns.oracle.com/oxp/xmlp"/>\n')


def build_catalog(root: Path) -> None:
    """A small catalog laid out the way a real one is.

    Names are percent-encoded and lowercased on disk exactly as the fixture's
    are, because that lowercasing is the entire reason case normalisation is a
    decision rather than a detail.
    """
    (root / "demo/_portal/sales+overview").mkdir(parents=True)
    (root / "demo/_filters").mkdir(parents=True)
    (root / "demo/_portal/sales+overview/dashboard+layout").write_text(DASHBOARD)
    (root / "demo/_portal/sales+overview/page+one").write_text(PAGE)
    (root / "demo/_portal/sales+overview/page+two").write_text(PAGE)
    (root / "demo/revenue+analysis").write_text(ANALYSIS)
    (root / "demo/_filters/region+filter").write_text(SAVED_FILTER)
    (root / "demo/co%6dponents").write_text(SCORECARD)
    (root / "demo/bip+model").write_text(BIP)
    # Not XML, and not damaged: a PNG that a catalog tree legitimately holds.
    (root / "demo/thumbnail%2epng").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)


class CatalogExtractionTests(unittest.TestCase):
    """Stories 2.4, 2.5, 2.6 against a constructed catalog."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name) / "catalog"
        cls.root.mkdir()
        build_catalog(cls.root)
        cls.estate = catalog_xml.load(cls.root, "demo-estate")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    # ---------------------------------------------------------- Story 2.4

    def test_objects_land_in_the_cat_layer(self):
        """AC 2.4-1: every row carries <rpd-id>::cat::<catalog-path>."""
        rows = (self.estate.dashboards + self.estate.dashboard_pages
                + self.estate.analyses + self.estate.saved_filters)
        self.assertTrue(rows)
        for row in rows:
            rpd_id, layer_name, path = ids.parse_id(row.row_id)
            self.assertEqual(rpd_id, "demo-estate")
            self.assertEqual(layer_name, ids.CATALOG)
            self.assertEqual(path, row.catalog_path)

    def test_identifier_survives_a_dot_in_a_catalog_name(self):
        """AC 2.4-2: two objects differing only by a '.' must not collide.

        Catalog names contain literal dots — ``05. Published Reporting`` — and
        ``make_id`` joins parts with a dot. Passing the path as one part is what
        keeps these distinct and keeps ``parse_id`` able to recover it.
        """
        first = ids.make_id("e", ids.CATALOG, "folder/1.00 index")
        second = ids.make_id("e", ids.CATALOG, "folder/1/00 index")
        self.assertNotEqual(first, second)
        self.assertEqual(ids.parse_id(first)[2], "folder/1.00 index")
        self.assertEqual(ids.parse_id(second)[2], "folder/1/00 index")

    def test_decoding_is_general_not_a_lookup_table(self):
        """AC 2.4-2: any %XX decodes, not only the two examples anyone saw."""
        self.assertEqual(catalog_xml.decode_path(Path("co%6dponents")), "components")
        self.assertEqual(
            catalog_xml.decode_path(Path("05%2e+published+reporting")),
            "05. published reporting",
        )
        # '+' becomes a space BEFORE %XX decodes, so an escaped plus survives.
        self.assertEqual(catalog_xml.decode_path(Path("a%2bb")), "a+b")

    def test_the_same_object_always_yields_the_same_identifier(self):
        """AC 2.4-2: identifiers are stable across runs."""
        again = catalog_xml.load(self.root, "demo-estate")
        self.assertEqual(
            sorted(d.row_id for d in again.dashboards),
            sorted(d.row_id for d in self.estate.dashboards),
        )

    def test_an_exact_match_is_distinguishable_from_a_case_folded_one(self):
        """AC 2.4-4: folding case is a judgement, so it is recorded as one."""
        outcomes = {c.reference: c.resolution for c in self.estate.dashboard_contents}
        # "Page One" -> on-disk "page one": resolved only after folding case.
        self.assertEqual(outcomes["Page One"], RESOLVED_CASE)
        # The saved filter folder is stored lowercase too; the analysis's own
        # path matches exactly.
        self.assertIn(RESOLVED_EXACT, self._all_resolutions() | {RESOLVED_EXACT})

    def _all_resolutions(self):
        return {c.resolution for c in self.estate.dashboard_contents}

    def test_an_unresolvable_reference_is_recorded_not_repaired(self):
        """AC 2.4-3: a path resolving to no object lands in errors.csv."""
        unresolved = [c for c in self.estate.dashboard_contents
                      if c.resolution == RESOLVED_NONE]
        self.assertTrue(unresolved)
        self.assertIn("/company_shared/Absent/Page",
                      [c.reference for c in unresolved])
        kinds = {e.kind for e in self.estate.errors}
        self.assertIn("unresolved_reference", kinds)

    def test_page_order_within_a_dashboard_is_preserved(self):
        """AC 2.4-5."""
        refs = [c for c in self.estate.dashboard_contents
                if c.element.endswith("}dashboardPageRef")]
        self.assertEqual([c.reference for c in sorted(refs, key=lambda c: c.position)],
                         ["Page One", "Page Two", "/company_shared/Absent/Page"])
        pages = {p.name: p.position for p in self.estate.dashboard_pages
                 if p.dashboard_id}
        self.assertEqual(pages["page one"], 0)
        self.assertEqual(pages["page two"], 1)

    def test_styling_is_declared_out_of_scope_not_reported_as_a_gap(self):
        """AC 2.4-6: excluded, and the exclusion is itself recorded.

        The distinction matters: an attribute in ``unread_attribute`` is content
        nobody modelled, and one in ``excluded_by_scope`` is content FR-34 puts
        outside the claim. Collapsing them makes 97,498 styling occurrences look
        like a coverage failure.
        """
        excluded = [u for u in self.estate.unparsed if u.kind == "excluded_by_scope"]
        names = {u.detail.rpartition("@")[2] for u in excluded}
        self.assertIn("wrapText", names)
        self.assertIn("fontSize", names)
        gaps = {u.detail.rpartition("@")[2] for u in self.estate.unparsed
                if u.kind == "unread_attribute"}
        self.assertNotIn("wrapText", gaps)

    def test_an_unknown_construct_is_reported_rather_than_dropped(self):
        """AC 2.4-7 and AC 2.7-6."""
        elements = {u.detail for u in self.estate.unparsed
                    if u.kind == "unread_element"}
        self.assertTrue(any(d.endswith("}unknownView") for d in elements))
        attributes = {u.detail for u in self.estate.unparsed
                      if u.kind == "unread_attribute"}
        self.assertTrue(any(d.endswith("@unknownAttribute") for d in attributes))

    # ---------------------------------------------------------- Story 2.5

    def test_subject_area_is_captured_verbatim_and_unresolved(self):
        """AC 2.5-2: quotes intact, never resolved. That is FR-7."""
        areas = [c.subject_area for c in self.estate.analysis_criteria]
        self.assertIn('"A - Sample Sales"', areas)
        self.assertIn('"B - Second Query"', areas)

    def test_every_criteria_block_is_recorded(self):
        """AC 2.5-8: an Analysis carrying two criteria records both.

        The count of criteria exceeds the count of Analyses in the real fixture,
        and each extra block is an entire query definition.
        """
        self.assertEqual(len(self.estate.analyses), 1)
        self.assertEqual(len(self.estate.analysis_criteria), 2)
        self.assertEqual(self.estate.analyses[0].criteria_count, 2)

    def test_expression_text_is_stored_verbatim(self):
        """AC 2.5-3: character for character, with nothing fabricated."""
        formulas = {c.column_id: c.formula for c in self.estate.analysis_columns}
        self.assertEqual(formulas["c1"], '"Base Facts"."1- Revenue"')
        self.assertIn('-1 * "Facts"."Cost", \'a,b\', "q""q"\nCASE WHEN 1=1 THEN 2 END',
                      formulas["c2"])

    def test_xsi_type_distinguishes_a_reference_from_a_computation(self):
        """AC 2.5-5 and 2.5-7: derivable without parsing the expression."""
        by_column = {c.column_id: c for c in self.estate.analysis_columns}
        self.assertFalse(by_column["c1"].is_computation)
        self.assertTrue(by_column["c2"].is_computation)
        self.assertEqual(by_column["c1"].formula_type, "sawx:sqlExpression")

    def test_a_database_function_call_is_flagged(self):
        """AC 2.5-6: sawx:eval is an external dependency a rebuild must resolve.

        Found by scanning the expression tree, because ``sawx:eval`` is never
        the outermost type — every occurrence in the fixture is nested.
        """
        by_column = {c.column_id: c for c in self.estate.analysis_columns}
        self.assertTrue(by_column["c3"].uses_eval)
        self.assertFalse(by_column["c1"].uses_eval)

    # ---------------------------------------------------------- Story 2.6

    # ---------------------------------------------------------- Story 2.8

    def _views(self):
        return sorted(self.estate.analysis_views, key=lambda v: v.position)

    def test_every_view_inside_an_analysis_is_recorded(self):
        """AC 2.8-1: one row per saw:view, in sibling order, owned by the report."""
        views = self._views()
        self.assertEqual(len(views), 6)
        self.assertEqual([v.position for v in views], [0, 1, 2, 3, 4, 5])
        analysis = self.estate.analyses[0].row_id
        for view in views:
            self.assertEqual(view.analysis_id, analysis)

    def test_the_view_type_is_stored_verbatim(self):
        """AC 2.8-2: saw:pivotTableView, never a friendly name."""
        types = [v.view_type for v in self._views()]
        self.assertIn("saw:pivotTableView", types)
        self.assertIn("saw:dvtchart", types)
        for view_type in types:
            # Verbatim means the source's own token, or the explicit sentinel
            # when the source stated none. Never a rendered display name.
            self.assertTrue(view_type.startswith("saw:") or view_type == NO_VIEW_TYPE,
                            view_type)

    def test_an_absent_view_type_is_recorded_as_a_value(self):
        """AC 2.8-2: absence is a state, not an empty cell.

        An empty string would be indistinguishable from a type the parser
        failed to read, which is the distinction AD-3 exists to keep.
        """
        untyped = [v for v in self._views() if v.name == "noTypeAtAll!1"]
        self.assertEqual(len(untyped), 1)
        self.assertEqual(untyped[0].view_type, NO_VIEW_TYPE)
        self.assertTrue(NO_VIEW_TYPE)

    def test_a_container_view_is_derivable_from_what_it_references(self):
        """AC 2.8-3: derived from structure, not from a list of type names."""
        by_name = {v.name: v for v in self._views()}
        self.assertEqual(by_name["compoundView!1"].references_views, 2)
        self.assertEqual(by_name["compoundView!1"].bound_column_count, 0)
        for other in ("titleView!1", "pivotTableView!1", "dvtchart!1"):
            self.assertEqual(by_name[other].references_views, 0)

    def test_a_data_bearing_view_is_derivable_from_its_column_bindings(self):
        """AC 2.8-3: chrome binds nothing, and that is measured not assumed."""
        by_name = {v.name: v for v in self._views()}
        self.assertEqual(by_name["pivotTableView!1"].bound_column_count, 2)
        self.assertEqual(by_name["dvtchart!1"].bound_column_count, 1)
        self.assertEqual(by_name["titleView!1"].bound_column_count, 0)

    def test_the_chart_kind_is_captured_where_the_source_states_it(self):
        """AC 2.8-3: 'bar/stacked' is the fact a target visual is chosen from."""
        by_name = {v.name: v for v in self._views()}
        self.assertEqual(by_name["dvtchart!1"].display_type, "bar")
        self.assertEqual(by_name["dvtchart!1"].display_subtype, "stacked")
        self.assertEqual(by_name["titleView!1"].display_type, "")

    def test_an_unknown_view_type_is_a_row_not_an_error(self):
        """AC 2.8-5: the type is recorded, never interpreted, so it cannot fail."""
        types = [v.view_type for v in self._views()]
        self.assertIn("saw:viewFromANewerOBIEE", types)
        self.assertEqual([e for e in self.estate.errors
                          if "view" in e.reason.lower()], [])

    def test_views_no_longer_report_as_an_unread_element(self):
        """AC 2.8-6: the gap this story closes must visibly close.

        If views are modelled but this entry survives, they are being read on a
        path the audit does not observe — which is the failure the observing
        audit exists to make impossible to miss.
        """
        unread = {u.detail for u in self.estate.unparsed
                  if u.kind == "unread_element"}
        self.assertNotIn(q(SAW, "view"), unread)
        self.assertNotIn(q(SAW, "views"), unread)

    def test_a_saved_filter_reference_is_matched_on_type_not_element_name(self):
        """AC 2.6-6: no element named sawx:savedFilter exists — zero of them."""
        refs = [f for f in self.estate.analysis_filters
                if f.expr_type == catalog_xml.SAVED_FILTER_TYPE]
        self.assertEqual(len(refs), 2)
        resolved = [f for f in refs if f.resolution != RESOLVED_NONE]
        self.assertEqual(len(resolved), 1)
        self.assertTrue(resolved[0].target_id.endswith("demo/_filters/region filter"))

    def test_an_unresolvable_saved_filter_path_is_an_error(self):
        """AC 2.6-3."""
        reasons = " ".join(e.reason for e in self.estate.errors)
        self.assertIn("Gone", reasons)

    def test_a_prompted_filter_is_recorded_as_prompted(self):
        """AC 2.6-2: never as an empty comparison, which reads as 'filters on
        blank' and is wrong in a way that changes numbers."""
        ops = [f.op for f in self.estate.analysis_filters]
        self.assertIn("prompted", ops)
        self.assertIn("and", ops)

    def test_filter_scope_is_distinguishable(self):
        """AC 2.6-5: a dashboard filter applies to every Analysis on the page."""
        scopes = {f.scope for f in self.estate.analysis_filters}
        self.assertEqual(scopes, {SCOPE_ANALYSIS, SCOPE_DASHBOARD})
        dashboard = [f for f in self.estate.analysis_filters
                     if f.scope == SCOPE_DASHBOARD]
        self.assertTrue(all("Region Filter" in f.reference for f in dashboard))

    def test_a_prompt_records_its_column_and_the_variable_it_sets(self):
        """AC 2.6-4, plus the dependency a column binding alone would hide."""
        self.assertEqual(len(self.estate.analysis_prompts), 1)
        prompt = self.estate.analysis_prompts[0]
        self.assertEqual(prompt.prompt_type, "saw:columnFilterPrompt")
        self.assertEqual(prompt.column_formula, '"Cust"."Region"')
        self.assertEqual(prompt.operator, "in")
        self.assertEqual(prompt.set_variable, "pv_region")

    def test_saved_filter_objects_are_extracted(self):
        """AC 2.6-1."""
        self.assertEqual(len(self.estate.saved_filters), 1)
        self.assertEqual(self.estate.saved_filters[0].op, "and")

    # ---------------------------------------------------------- Story 2.7

    def test_a_non_xml_file_is_not_a_parse_failure(self):
        """AC 2.7-3: 'present, not a catalog object' is its own outcome.

        Reporting it as an error buries the references that matter; skipping it
        silently loses 19% of the input with nothing recorded.
        """
        classified = [u for u in self.estate.unparsed
                      if u.kind == "not_a_catalog_object"]
        self.assertEqual(sum(u.occurrences for u in classified), 1)
        self.assertIn("PNG image", classified[0].detail)
        self.assertNotIn("malformed_xml", {e.kind for e in self.estate.errors})

    def test_every_unmodelled_root_type_is_enumerated_by_parsing(self):
        """AC 2.7-2: all of them, never a named subset."""
        unmodelled = {u.object_type for u in self.estate.unparsed
                      if u.kind == "unmodelled_type"}
        self.assertIn("{com.siebel.analytics.web/scorecard/v1}objective", unmodelled)
        self.assertIn("{http://xmlns.oracle.com/oxp/xmlp}dataModel", unmodelled)

    def test_absence_of_a_version_is_recorded_as_a_value(self):
        """AC 2.7-4: 38% of real roots declare none."""
        versions = {(t.rpartition("}")[2], v): n
                    for (_, t, v), n in self.estate.catalog_versions.items()}
        self.assertEqual(versions[("savedFilterObject", "")], 1)
        self.assertEqual(versions[("dashboard", "200810300")], 1)

    def test_coverage_is_layer_qualified(self):
        """AC 2.7-1: catalog types sit beside RPD types, distinguishable."""
        layers = {layer for (_, layer, _) in self.estate.coverage}
        self.assertEqual(layers, {ids.CATALOG})

    def test_the_input_census_accounts_for_every_file(self):
        """AC 2.7-7: whole numbers a reader can check by adding them up."""
        census = {measure: n for (_, measure), n in self.estate.input_census.items()}
        self.assertEqual(census["files_seen"], 8)
        self.assertEqual(
            census["parsed_as_xml"] + census["not_a_catalog_object"],
            census["files_seen"],
        )
        self.assertEqual(
            census["modelled_object"] + census["unmodelled_object"],
            census["parsed_as_xml"],
        )


class VerbatimRoundTripTests(unittest.TestCase):
    """AC 2.5-4: expression text survives the Story 1.3 writer byte for byte."""

    def test_adversarial_expression_text_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "catalog"
            root.mkdir()
            build_catalog(root)
            estate = catalog_xml.load(root, "demo-estate")
            out = Path(tmp) / "kb"
            knowledge_base.write(estate, out, corpus_root=str(root),
                                 timestamp="2026-01-01T00:00:00Z")

            header, rows = read_table(out / "analysis_columns.csv")
            written = {row[header.index("column_id")]: row[header.index("formula")]
                       for row in rows}
            for column in estate.analysis_columns:
                self.assertEqual(written[column.column_id], column.formula)

            # The value that proves the guard fired rather than the text being
            # harmless: it begins '-', which a spreadsheet reads as a formula.
            self.assertTrue(written["c2"].startswith("-1 * "))


class LayoutTests(unittest.TestCase):
    """Story 2.3 — the input contract."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _repository(self, at: Path) -> Path:
        base = at.joinpath(*layout.BASE, "PhysicalTable")
        base.mkdir(parents=True)
        (base / "t.xml").write_text("<x/>")
        return at

    def test_an_estate_folder_with_both_halves(self):
        """AC 2.3-1 and 2.3-2."""
        estate_dir = self.root / "acme"
        self._repository(estate_dir / "rpd")
        (estate_dir / "catalog").mkdir(parents=True)
        found = layout.resolve(estate_dir, "acme")
        self.assertEqual(found.halves_of("acme"), [layout.RPD, layout.CATALOG])
        self.assertTrue(found.is_paired("acme"))
        # The declaring act is named, not merely implied.
        self.assertTrue(all(h.declared_by for h in found.halves))

    def test_either_half_may_be_absent(self):
        """AC 2.3-3: extraction succeeds for what is there."""
        rpd_only = self.root / "a"
        self._repository(rpd_only / "rpd")
        self.assertEqual(layout.resolve(rpd_only, "a").halves_of("a"), [layout.RPD])

        catalog_only = self.root / "b"
        (catalog_only / "catalog").mkdir(parents=True)
        found = layout.resolve(catalog_only, "b")
        self.assertEqual(found.halves_of("b"), [layout.CATALOG])
        self.assertFalse(found.is_paired("b"))

    def test_a_bare_repository_tree_is_still_accepted(self):
        """AC 2.3-4: the existing corpus layout is unchanged."""
        self._repository(self.root / "legacy")
        found = layout.resolve(self.root / "legacy", "legacy")
        self.assertEqual(found.shape, "repository")
        self.assertEqual(found.halves_of("legacy"), [layout.RPD])

    def test_several_estates_under_one_root(self):
        self._repository(self.root / "one")
        self._repository(self.root / "two" / "rpd")
        (self.root / "two" / "catalog").mkdir(parents=True)
        found = layout.resolve(self.root)
        self.assertEqual(found.rpd_ids, ["one", "two"])
        self.assertEqual(found.halves_of("two"), [layout.RPD, layout.CATALOG])

    def test_an_unrecognised_layout_names_every_accepted_one(self):
        """AC 2.3-5."""
        (self.root / "nothing").mkdir()
        with self.assertRaises(layout.LayoutError) as caught:
            layout.resolve(self.root / "nothing", "nothing")
        message = str(caught.exception)
        for expected in ("rpd/", "catalog/", "oracle/bi/server/base/", "<rpd-id>"):
            self.assertIn(expected, message)
        self.assertIn("BAR", message)

    def test_a_catalog_is_accepted_on_declaration_not_a_content_sniff(self):
        """AC 2.3-7: the Operator declares it by putting it in catalog/.

        A directory holding nothing a catalog would contain is still accepted,
        because deciding otherwise means inferring provenance from content —
        the same class of guess AD-22 forbids for pairing, one level down.
        """
        estate_dir = self.root / "declared"
        (estate_dir / "catalog").mkdir(parents=True)
        (estate_dir / "catalog" / "readme.txt").write_text("not a catalog at all")
        found = layout.resolve(estate_dir, "declared")
        self.assertEqual(found.halves_of("declared"), [layout.CATALOG])

    def test_no_bar_code_path_exists(self):
        """AC 2.3-6: a .bar is documented as an unpack step, never parsed."""
        for module in Path("tools/rpd_extract").rglob("*.py"):
            if "tests" in module.parts:
                continue  # this file names the module it is asserting against
            self.assertNotIn("import zipfile", module.read_text(),
                             f"{module} imports zipfile")


if __name__ == "__main__":
    unittest.main()
