"""The Estate model.

Pure data. No I/O, and deliberately no concept from any serialisation — no
GUIDs, no file paths, no ``#mdsid`` fragments (AD-20). Everything here is
expressed in Knowledge Base identifiers, which is what lets a second inbound
adapter be an addition rather than a rewrite.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Expression:
    """An expression in all three of the forms the source records (AD-21).

    Capturing one and discarding the others is a rewrite of the formula and
    breaches FR-2; choosing between them is the guess AD-3 forbids. So all
    three travel together, verbatim.

    ``text`` is the template (``SUM("%1")``); ``text_desc`` is that template
    rendered with names resolved — derived, never authoritative; ``refs`` are
    the resolved identifiers the placeholders bind to.
    """

    text: str
    text_desc: str
    refs: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.text.strip() or self.text_desc.strip())


EMPTY_EXPRESSION = Expression("", "", ())


@dataclass(frozen=True)
class PhysicalTable:
    row_id: str
    rpd_id: str
    container: str
    name: str
    table_type: str = ""
    max_conn: str = ""
    #: The table this one is an alias of. Empty means *not an alias* — the
    #: source records no such link — never *link not found*: one that is present
    #: and does not resolve is an error, and the cell stays empty beside it.
    source_table_id: str = ""


@dataclass(frozen=True)
class PhysicalTableDefinition:
    """What a physical table resolves to in the database, verbatim.

    The repository's name for a table is not necessarily the database's. The
    source carries, per database type, either the SQL of an opaque view
    (``table_type`` ``select``) or the name of the object actually queried —
    in the pinned corpus the table shown as ``Operations`` is
    ``FCT_OPERATIONS_DD`` in the database. Which of the two a row holds is told
    by the table's ``table_type``, never by inspecting the text (AD-3).

    One row per database type rather than a column on the table, because the
    source allows several and choosing one would be a guess. The text is never
    parsed: which tables a SELECT reads from is not recorded here.
    """

    row_id: str
    rpd_id: str
    table_id: str
    database: str
    text: str


@dataclass(frozen=True)
class PhysicalColumn:
    row_id: str
    rpd_id: str
    table_id: str
    name: str
    data_type: str = ""
    special_type: str = ""
    precision: str = ""
    nullable: str = ""
    external_name: str = ""


@dataclass(frozen=True)
class PhysicalJoin:
    """A physical join. ``kind`` distinguishes the two shapes the source uses.

    Foreign keys and complex joins are both physical joins and both belong in
    one table; dropping either would lose a real relationship.
    """

    row_id: str
    rpd_id: str
    kind: str  # "foreign_key" | "complex_join"
    name: str
    table1_id: str
    table2_id: str = ""
    cardinality: str = ""
    expression: Expression = EMPTY_EXPRESSION
    columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class LogicalTable:
    row_id: str
    rpd_id: str
    business_model: str
    name: str
    source_count: int = 0


@dataclass(frozen=True)
class LogicalColumn:
    """A logical column.

    ``derived`` is the column's own formula — present on very few columns and
    the primary target of FR-2. ``mapping`` is its ``AttrDefn`` physical
    mapping, present on most. Both are kept: they answer different questions.
    """

    row_id: str
    rpd_id: str
    table_id: str
    name: str
    is_writeable: str = ""
    is_measure: bool = False
    #: Time-series functions used, e.g. ("AGO",). FR-4 requires this flagged.
    time_series: tuple[str, ...] = ()
    #: Sources declared on the owning logical TABLE.
    source_count: int = 0
    #: Sources that actually map THIS column. Always <= source_count, and a
    #: gap between them is itself a parity hazard: a source that cannot supply
    #: this column cannot satisfy a query that needs it.
    mapped_source_count: int = 0
    derived: Expression = EMPTY_EXPRESSION
    mapping: Expression = EMPTY_EXPRESSION


@dataclass(frozen=True)
class AggregationRule:
    """One aggregation rule on a measure.

    A measure may carry several. ``is_default`` marks the default; the rest are
    dimension-specific overrides, which FR-4 requires captured. Never collapse
    them — the loss produces a plausible wrong number rather than an error.
    """

    row_id: str
    rpd_id: str
    logical_column_id: str
    name: str
    is_default: str
    expression: Expression


@dataclass(frozen=True)
class SubjectArea:
    """A Presentation Layer grouping — the natural unit of a Semantic Model.

    Not to be confused with the Web Catalog: the source calls this a
    ``PresentationCatalog``, but it is a Subject Area. The Web Catalog is the
    report store and is a different concern entirely.
    """

    row_id: str
    rpd_id: str
    name: str
    business_model: str
    implicit_fact_column_id: str = ""
    is_auto_aggregate: str = ""
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class PresentationTable:
    row_id: str
    rpd_id: str
    subject_area_id: str
    name: str
    display_name: str = ""
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class PresentationColumn:
    """A column as a report author sees it.

    ``logical_column_id``, ``override_logical_name`` and ``display_name``
    together make the physical → logical → presentation rename chain
    recoverable, which is what FR-4 asks for. The components are stored rather
    than a pre-joined string so every step stays traceable (NFR2).
    """

    row_id: str
    rpd_id: str
    table_id: str
    name: str
    logical_column_id: str = ""
    override_logical_name: str = ""
    display_name: str = ""


@dataclass(frozen=True)
class LogicalDimension:
    """A logical dimension — the drill semantics behind a hierarchy.

    ``is_ragged`` and ``is_skipped`` are carried because each changes what a
    drill path *means*: a ragged hierarchy has branches that stop early, and a
    skip-level one has members with no parent at the level above. Flattening
    either during a migration changes what a user can reach without changing a
    single number, so parity checking on values would never catch it.
    """

    row_id: str
    rpd_id: str
    name: str
    business_model: str = ""
    is_value_based: bool = False
    is_ragged: bool = False
    is_skipped: bool = False
    default_root_level_id: str = ""
    level_count: int = 0


@dataclass(frozen=True)
class LogicalLevel:
    """One level of a logical dimension, and the column that drills it.

    ``position`` is document order, which is the order OBIEE drills in. It is
    stored rather than derived from ``member_count`` because a level's member
    count is data and its place in the hierarchy is structure.
    """

    row_id: str
    rpd_id: str
    dimension_id: str
    position: int
    name: str
    member_count: str = ""
    is_grand_total: bool = False
    drill_key_column_id: str = ""


@dataclass(frozen=True)
class PresentationHierarchy:
    """A hierarchy as a report author sees it, on one presentation table.

    ``display_column_id`` is populated only for a **value-based** (parent-child)
    hierarchy, which has no levels at all — its display column hangs off the
    hierarchy itself. One of the corpus's 25 dimensions is of this kind, and
    reading display columns only from levels drops the single column it names.
    A level-based hierarchy leaves this empty and uses
    ``presentation_level_columns`` instead.
    """

    row_id: str
    rpd_id: str
    table_id: str
    name: str
    dimension_id: str = ""
    level_count: int = 0
    display_column_id: str = ""


@dataclass(frozen=True)
class PresentationLevel:
    """One level of a presentation hierarchy, in drill order."""

    row_id: str
    rpd_id: str
    hierarchy_id: str
    position: int
    name: str
    logical_level_id: str = ""


@dataclass(frozen=True)
class PresentationLevelColumn:
    """A column displayed at one level — the drill path, one row per step.

    Its own table rather than a repeated field on the level, because a level
    displays several columns and the order they appear in is part of the
    definition a Power BI hierarchy is rebuilt from.
    """

    row_id: str
    rpd_id: str
    level_id: str
    position: int
    presentation_column_id: str


@dataclass(frozen=True)
class LogicalTableSource:
    """One way a logical table can be satisfied from physical storage.

    ``priority`` is empty when the source records none. Empty means *not
    recorded*, never *lowest* — inferring an order from document position is
    the guess AD-3 forbids, and getting it wrong silently repoints a measure.
    """

    row_id: str
    rpd_id: str
    logical_table_id: str
    name: str
    is_active: str = ""
    priority: str = ""
    fragment: Expression = EMPTY_EXPRESSION
    where_clause: Expression = EMPTY_EXPRESSION
    group_by: Expression = EMPTY_EXPRESSION


@dataclass(frozen=True)
class ColumnMapping:
    """One logical column mapped to one physical column, through one source."""

    row_id: str
    rpd_id: str
    source_id: str
    logical_column_id: str
    physical_column_id: str
    logical_expression: Expression
    physical_expression: Expression


@dataclass(frozen=True)
class LineageRow:
    """One resolved path: presentation → logical → source → physical.

    A logical column with three sources yields three rows. Collapsing them
    would hide a source, and a hidden source is a missing row that reads as
    perfectly normal output.
    """

    row_id: str
    rpd_id: str
    presentation_column_id: str
    logical_column_id: str
    source_id: str
    physical_table_id: str
    physical_column_id: str


#: Time-series functions FR-4 requires flagged per column.
TIME_SERIES_FUNCTIONS = ("AGO", "TODATE", "PERIODROLLING")


def time_series_used(*expressions: "Expression") -> tuple[str, ...]:
    """Which time-series functions appear in these expressions.

    Domain logic, not serialisation: the function names are OBIEE's, not the
    file format's, so this belongs in the core (AD-20).
    """
    import re

    found = []
    blob = " ".join(e.text + " " + e.text_desc for e in expressions)
    for name in TIME_SERIES_FUNCTIONS:
        if re.search(rf"\b{name}\s*\(", blob, re.IGNORECASE):
            found.append(name)
    return tuple(found)


@dataclass(frozen=True)
class BmmJoin:
    """A logical join. ``join_type`` is the inner/left-outer distinction FR-4
    names: getting it wrong changes row counts without changing any measure."""

    row_id: str
    rpd_id: str
    name: str
    join_type: str
    table1_id: str
    multiplicity1: str
    is_aggregate1: str
    table2_id: str
    multiplicity2: str
    is_aggregate2: str


#: Variable names whose VALUE must never reach the Knowledge Base (NFR11).
#: A heuristic, and deliberately broad — over-redacting costs a lookup, while
#: under-redacting writes a credential to disk.
CREDENTIAL_NAME = re.compile(
    r"password|passwd|pwd|secret|token|credential|apikey|api[_ -]?key", re.I
)


def is_credential_name(name: str) -> bool:
    return bool(CREDENTIAL_NAME.search(name or ""))


@dataclass(frozen=True)
class Variable:
    """A repository or session variable.

    ``redacted`` marks a variable whose value was withheld because its name
    indicates a credential. NFR11 forbids credentials in the Knowledge Base,
    and AD-3 forbids doing it silently — so the withholding is recorded, and
    the row still exists so a reader knows the variable is there.
    """

    row_id: str
    rpd_id: str
    name: str
    is_session: str
    init_block_id: str
    security_mask: str
    expression: Expression
    redacted: bool = False


@dataclass(frozen=True)
class InitBlock:
    row_id: str
    rpd_id: str
    name: str
    refresh_period: str
    is_session: str
    is_enabled: str
    init_string: str


@dataclass(frozen=True)
class SecurityRule:
    """One row of the role -> privilege chain, or a row-level predicate.

    Security does not live in one object: a role reaches its privileges through
    a privilege package, while the actual predicate sits on a Logical Table
    Source. Both shapes land here, distinguished by ``kind``.
    """

    row_id: str
    rpd_id: str
    kind: str  # "object_privilege" | "query_privilege" | "row_filter"
    role: str
    subject_id: str
    detail: str
    expression: Expression = EMPTY_EXPRESSION


@dataclass(frozen=True)
class Unparsed:
    """A known, deliberate gap — content the extractor does not model yet.

    Expected and informational. An object type nobody has written a parser for,
    or an attribute present in the source that no Knowledge Base column carries.
    Nothing is broken; something is simply not covered.

    Kept separate from :class:`ExtractionError` so a reader can tell "we have
    not built this" from "this went wrong" at a glance — conflating them buries
    the second in the first.
    """

    rpd_id: str
    #: One of: unmodelled_type, unread_attribute, unread_element, unread_text,
    #: undiscovered_file, not_a_catalog_object, excluded_by_scope.
    #:
    #: ``not_a_catalog_object`` and ``excluded_by_scope`` are not gaps in
    #: understanding at all — the first is a file that was never a catalog
    #: object, the second is content a scope decision put outside the product's
    #: claim. Both are recorded here rather than dropped, because an exclusion
    #: that leaves no trace cannot be told from an oversight.
    kind: str
    object_type: str
    detail: str
    occurrences: int = 1


@dataclass(frozen=True)
class ExtractionError:
    """Something went wrong — content that should have been captured was not.

    AD-3: where the extractor cannot parse with certainty it records the source
    identifier and the reason, and continues. NFR7 makes silent omission the
    primary failure mode to design against, so this is a first-class output,
    not a log line.
    """

    rpd_id: str
    kind: str  # malformed_xml | unresolved_reference | missing_name | unreadable
    source_id: str
    object_type: str
    reason: str


# --------------------------------------------------------------- Web Catalog
#
# The Web Catalog is a separate store read into the same Knowledge Base under
# layer ``cat`` (AD-22). Its objects are addressed by decoded catalog path, not
# by GUID, and it stores exactly ONE representation of an expression — the text
# inside ``sawx:expr`` — where MDS XML stores three. AD-21 is satisfied by
# capturing that one verbatim; synthesising the missing two would be
# indistinguishable from a source that provided them, which is the lossy claim
# the verbatim guarantee exists to refuse.
#
# Several collections below get their own table rather than a repeated field.
# An Analysis can carry more than one ``saw:criteria`` (1680 against 1607
# Analyses), a page can place many reports, and a filter can be one of many.
# Folding any of those into a field drops the surplus, and each dropped item is
# an entire query definition, placement or restriction.


@dataclass(frozen=True)
class CatalogObject:
    """Fields every catalog object carries, whatever its type.

    ``xml_version`` is the object's declared ``xmlVersion``, and **empty means
    the object declared none** — which is the second most common state, 38% of
    parseable roots. Recorded as a value in its own right rather than defaulted,
    because a version spread that reports only declared values describes 62% of
    an estate and reads as though it describes all of it.
    """

    row_id: str
    rpd_id: str
    name: str
    catalog_path: str
    xml_version: str = ""


@dataclass(frozen=True)
class Dashboard(CatalogObject):
    page_count: int = 0


@dataclass(frozen=True)
class DashboardPage(CatalogObject):
    """One page. ``position`` preserves page order within its Dashboard.

    ``dashboard_id`` is empty for a page object that no Dashboard references —
    a real state in the fixture, and a different thing from an unplaced page,
    so it is left empty rather than filled with a guess.
    """

    dashboard_id: str = ""
    position: int = 0


#: How a ``@path`` reference resolved. ``case_normalised`` stays distinct from
#: ``exact`` because folding case is a judgement (AD-3), and on an estate that
#: distinguishes case it would join two different objects with nothing
#: downstream able to detect it.
RESOLVED_EXACT = "exact"
RESOLVED_CASE = "case_normalised"
RESOLVED_AMBIGUOUS = "ambiguous"
RESOLVED_NONE = "unresolved"

#: Report-lineage outcomes that are **not** resolution failures. Each names a
#: reason the chain legitimately stops, because "unresolved" applied to all of
#: them would report ~4500 defects where there are none (AD-3).
#:
#: ``NOT_A_COLUMN_REFERENCE`` — the formula is a computation, and its column
#: references are embedded in an expression this pass does not parse.
#: ``OUTSIDE_SEMANTIC_MODEL`` — the formula names an ``XSA('user'.'dataset')``
#: Visual Analyzer upload. The data was never in the repository, so no amount of
#: resolving will find it. That is a migration finding, not a gap.
NOT_A_COLUMN_REFERENCE = "not_a_column_reference"
OUTSIDE_SEMANTIC_MODEL = "outside_semantic_model"

#: Whether a resolved presentation column reaches physical storage.
#: ``COMPUTED_NOT_SOURCED`` is a BMM-derived column — ``PERIODROLLING`` and its
#: kind — which has no lineage row because it is calculated, not stored. An
#: empty cell would read as a lookup that failed.
SOURCED = "sourced"
COMPUTED_NOT_SOURCED = "computed_not_sourced"


@dataclass(frozen=True)
class ReportLineageRow:
    """One Analysis column, traced toward the semantic layer (FR-7, AD-23).

    Its own table, never an extension of ``lineage.csv``: that table describes
    the repository alone and is meaningful without a catalog. Merging report
    rows into it would make every existing consumer depend on a half that may
    not have been supplied.

    ``subject_area`` is the catalog's verbatim value, quotes intact, carried
    alongside the resolution rather than replaced by it — the same rule
    ``analysis_criteria`` follows, so a reader can always see what was asked for
    as well as what it matched.
    """

    row_id: str
    rpd_id: str
    analysis_id: str
    criteria_id: str
    analysis_column_id: str
    subject_area: str
    reference_text: str
    resolution: str
    subject_area_id: str = ""
    presentation_column_id: str = ""
    logical_column_id: str = ""
    physical_column_id: str = ""
    source_state: str = ""


@dataclass(frozen=True)
class DashboardContent:
    """One reference placed on a Dashboard or page, and how it resolved.

    Its own table because a page places many objects in a defined order, and a
    repeated field would lose both the order and the per-reference resolution
    outcome that AD-3 requires kept visible.

    ``reference`` is the raw ``@path`` string, kept verbatim including anything
    malformed in it — one reference in the fixture is
    ``/shared/03. Mobile/.../m\\/d linking_mob``, an escaped separator inside a
    name. Repairing it would hide that such names exist.
    """

    row_id: str
    rpd_id: str
    container_id: str
    element: str
    reference: str
    position: int
    resolution: str
    target_id: str = ""
    target_kind: str = ""
    detail: str = ""


@dataclass(frozen=True)
class Analysis(CatalogObject):
    criteria_count: int = 0
    column_count: int = 0


@dataclass(frozen=True)
class AnalysisCriteria:
    """One ``saw:criteria`` block — an entire query definition.

    ``subject_area`` is captured **verbatim, unresolved**, quotes included: the
    fixture writes ``"A - Sample Sales"``. Resolving it to a Knowledge Base
    Subject Area is FR-7, which needs a matched pair (AD-22) and lands in
    ``report_lineage.csv`` when one exists (AD-23) — never by extending this
    table.
    """

    row_id: str
    rpd_id: str
    analysis_id: str
    position: int
    subject_area: str


@dataclass(frozen=True)
class AnalysisColumn:
    """One column of an Analysis, with its formula verbatim.

    ``formula_type`` is the ``xsi:type`` on the expression, and it is where the
    meaning lives: ``saw:regularColumn`` is a bare reference to a semantic-layer
    column, and everything else is a computation. That makes
    ``is_computation`` derivable **without parsing the expression**, so the flag
    is deterministic and carries no AD-3 exposure.

    ``uses_eval`` marks ``sawx:eval`` — a direct database function call. The
    calculation is not defined in OBIEE at all; it lives in the target schema,
    so a rebuild must resolve it against the database. Flagged because no
    artifact this tool produces can show the logic.

    ``formula_construct`` names which element carried the expression.
    ``saw:columnFormula`` is the common case; ``saw:paSimpleColumnFormula``
    holds its text directly, appears only in Visual Analyzer projects, and is
    invisible to any search for the first.
    """

    row_id: str
    rpd_id: str
    analysis_id: str
    criteria_id: str
    position: int
    column_id: str
    heading: str = ""
    table_heading: str = ""
    formula_construct: str = ""
    formula_type: str = ""
    formula: str = ""
    is_computation: bool = False
    uses_eval: bool = False


#: Recorded when a view carries no ``xsi:type``. An empty string would be
#: indistinguishable from a type the parser failed to read, and AD-3 requires
#: those two states stay apart. No fixture view lacks one, which is exactly why
#: the sentinel matters: the first estate that does must not read as a bug.
NO_VIEW_TYPE = "(no xsi:type)"


@dataclass(frozen=True)
class AnalysisView:
    """One ``saw:view`` inside an Analysis — what the report renders as.

    ``view_type`` is the ``xsi:type`` **verbatim**: ``saw:pivotTableView``,
    never ``Pivot Table`` and never a Power BI visual name. Choosing a target
    visual is a migration judgement belonging to whoever reads the Knowledge
    Base; a friendly-name column would also drift silently the first time an
    estate carries a type this fixture never held.

    ``references_views`` and ``bound_column_count`` exist so a reader can tell a
    layout container from a data visual **without supplying a list of type
    names**. Both are counted from structure the source states: a
    ``compoundView`` arranges other views by name, and a table, pivot or chart
    binds columns. On the fixture that separates cleanly — 1580 of 1581
    ``compoundView`` reference views and bind nothing, while ``titleView``,
    ``htmlview`` and ``narrativeView`` bind nothing and reference nothing.
    Deriving it beats a hardcoded list, which would misclassify the twenty-
    seventh type the day it appears.

    ``display_type`` and ``display_subtype`` carry ``saw:display``'s own words —
    ``bar`` / ``stacked``. Only the ``dvt*`` family states them, and it is the
    single most useful fact for choosing a target visual, so it is not folded
    into the type.
    """

    row_id: str
    rpd_id: str
    analysis_id: str
    position: int
    view_type: str
    name: str = ""
    references_views: int = 0
    bound_column_count: int = 0
    display_type: str = ""
    display_subtype: str = ""


#: Filter scope. Sourced from which construct the filter came from, never from
#: a judgement: a dashboard-level filter applies to every Analysis on the page,
#: so folding the two populations into one would misstate what each report
#: restricts.
SCOPE_ANALYSIS = "analysis"
SCOPE_DASHBOARD = "dashboard"


@dataclass(frozen=True)
class AnalysisFilter:
    """One filter expression, with its operator and type.

    ``op`` is captured, never validated against a closed list: ``multiply``,
    ``union`` and the arithmetic operators appear in the same attribute, so it
    is a general expression operator rather than a filter-specific enum.

    ``prompted`` is the most common operator of all, and a prompted filter has
    **no value in the artifact** — the value arrives at runtime from a dashboard
    prompt. It is recorded as prompted; recording it as an empty comparison
    would read as *filters on blank*, which is wrong in a way that changes
    numbers.
    """

    row_id: str
    rpd_id: str
    scope: str
    owner_id: str
    position: int
    op: str = ""
    expr_type: str = ""
    expr_text: str = ""
    uses_eval: bool = False
    reference: str = ""
    target_id: str = ""
    resolution: str = ""
    #: A ``sawx:eval`` anywhere in this filter's expression tree — a direct
    #: database function call. Measured, this is where the construct actually
    #: lives: 297 of the fixture's occurrences are in Analysis filters and 4 in
    #: saved filters, and **none is inside a column formula**.
    uses_eval: bool = False


@dataclass(frozen=True)
class AnalysisPrompt:
    """One prompt, the column it binds to, and any variable it sets.

    ``set_variable`` matters beyond the column binding: a prompt that sets a
    presentation variable creates a dependency between the prompt and a column
    formula elsewhere in the report, and that dependency is invisible if only
    the binding is captured.
    """

    row_id: str
    rpd_id: str
    analysis_id: str
    position: int
    prompt_type: str = ""
    column_formula: str = ""
    column_type: str = ""
    set_variable: str = ""
    operator: str = ""
    ui_control: str = ""


@dataclass(frozen=True)
class SavedFilter(CatalogObject):
    """A ``sawsf:savedFilterObject`` root — a filter stored for reuse.

    96 objects carry the 417 references to them, so saved filters are reused
    heavily, which is the point of them.
    """

    op: str = ""
    expr_type: str = ""
    expr_text: str = ""
    uses_eval: bool = False


@dataclass
class Estate:
    """Everything extracted from one corpus, across every ``rpd-id``."""

    physical_tables: list[PhysicalTable] = field(default_factory=list)
    physical_table_definitions: list[PhysicalTableDefinition] = field(
        default_factory=list
    )
    physical_columns: list[PhysicalColumn] = field(default_factory=list)
    physical_joins: list[PhysicalJoin] = field(default_factory=list)
    logical_tables: list[LogicalTable] = field(default_factory=list)
    logical_columns: list[LogicalColumn] = field(default_factory=list)
    aggregation_rules: list[AggregationRule] = field(default_factory=list)
    subject_areas: list[SubjectArea] = field(default_factory=list)
    presentation_tables: list[PresentationTable] = field(default_factory=list)
    presentation_columns: list[PresentationColumn] = field(default_factory=list)
    presentation_hierarchies: list[PresentationHierarchy] = field(default_factory=list)
    presentation_levels: list[PresentationLevel] = field(default_factory=list)
    presentation_level_columns: list[PresentationLevelColumn] = field(
        default_factory=list)
    logical_dimensions: list[LogicalDimension] = field(default_factory=list)
    logical_levels: list[LogicalLevel] = field(default_factory=list)
    logical_table_sources: list[LogicalTableSource] = field(default_factory=list)
    column_mappings: list[ColumnMapping] = field(default_factory=list)
    lineage: list[LineageRow] = field(default_factory=list)
    bmm_joins: list[BmmJoin] = field(default_factory=list)
    variables: list[Variable] = field(default_factory=list)
    init_blocks: list[InitBlock] = field(default_factory=list)
    security_rules: list[SecurityRule] = field(default_factory=list)
    #: Web Catalog (AD-22). Every list here is layer ``cat``.
    dashboards: list[Dashboard] = field(default_factory=list)
    dashboard_pages: list[DashboardPage] = field(default_factory=list)
    dashboard_contents: list[DashboardContent] = field(default_factory=list)
    analyses: list[Analysis] = field(default_factory=list)
    analysis_criteria: list[AnalysisCriteria] = field(default_factory=list)
    analysis_columns: list[AnalysisColumn] = field(default_factory=list)
    analysis_filters: list[AnalysisFilter] = field(default_factory=list)
    analysis_prompts: list[AnalysisPrompt] = field(default_factory=list)
    analysis_views: list[AnalysisView] = field(default_factory=list)
    report_lineage: list[ReportLineageRow] = field(default_factory=list)
    saved_filters: list[SavedFilter] = field(default_factory=list)
    unparsed: list[Unparsed] = field(default_factory=list)
    errors: list[ExtractionError] = field(default_factory=list)
    #: (rpd_id, layer, object_type) -> {"parsed": n, "skipped": n}
    #:
    #: Layer-qualified since Epic 2: a Knowledge Base now holds two stores, and
    #: a coverage table that cannot tell an RPD object type from a catalog one
    #: makes the proportion figures unreadable.
    coverage: dict[tuple[str, str, str], dict[str, int]] = field(default_factory=dict)
    #: (rpd_id, object_type, xml_version) -> objects. Absence is a value.
    catalog_versions: dict[tuple[str, str, str], int] = field(default_factory=dict)
    #: (rpd_id, measure) -> count, for the modelled-proportion report.
    input_census: dict[tuple[str, str], int] = field(default_factory=dict)
    #: rpd_id -> the halves the Operator supplied, e.g. ["rpd", "catalog"].
    halves_present: dict[str, list[str]] = field(default_factory=dict)
    rpd_ids: list[str] = field(default_factory=list)

    def count(
        self, rpd_id: str, object_type: str, outcome: str, n: int = 1,
        layer: str = "rpd",
    ) -> None:
        bucket = self.coverage.setdefault(
            (rpd_id, layer, object_type), {"parsed": 0, "skipped": 0}
        )
        bucket[outcome] += n

    def census(self, rpd_id: str, measure: str, n: int = 1) -> None:
        """Count one input file against a population, for AC-7's proportions."""
        self.input_census[(rpd_id, measure)] = (
            self.input_census.get((rpd_id, measure), 0) + n
        )

    def record_version(self, rpd_id: str, object_type: str, version: str) -> None:
        """Record one object's ``xmlVersion``. Empty is a value, not a default."""
        key = (rpd_id, object_type, version)
        self.catalog_versions[key] = self.catalog_versions.get(key, 0) + 1

    def record_error(
        self, rpd_id: str, kind: str, source_id: str, object_type: str, reason: str,
        layer: str = "rpd",
    ) -> None:
        """Something broke. Always counted as skipped so coverage stays honest."""
        self.errors.append(ExtractionError(rpd_id, kind, source_id, object_type, reason))
        self.count(rpd_id, object_type, "skipped", layer=layer)

    def record_gap(
        self, rpd_id: str, kind: str, object_type: str, detail: str, occurrences: int = 1
    ) -> None:
        """A known gap. Not counted as skipped — the object itself parsed fine."""
        self.unparsed.append(Unparsed(rpd_id, kind, object_type, detail, occurrences))

    def record_unmodelled(
        self, rpd_id: str, object_type: str, source_id: str, layer: str = "rpd"
    ) -> None:
        self.unparsed.append(
            Unparsed(rpd_id, "unmodelled_type", object_type, source_id)
        )
        self.count(rpd_id, object_type, "skipped", layer=layer)

    def merge(self, other: "Estate") -> None:
        """Absorb another Estate's rows and counters. Additive only.

        An estate folder holds two halves, and each is read by its own adapter
        into its own Estate before being merged here. The alternative — letting
        both adapters append to one shared Estate — re-runs each adapter's
        post-passes over rows the other already contributed, which duplicated
        every lineage and security row and reported 1507 false
        ``duplicate_identifier`` errors on a corpus that has none.

        ``rpd_ids`` is deliberately not merged: the caller knows every estate it
        was asked for, including one whose half turned out to be empty, and a
        list assembled from what happened to parse would quietly drop it.
        """
        for name, rows in vars(other).items():
            if name == "rpd_ids":
                continue
            mine = getattr(self, name)
            if isinstance(rows, list):
                mine.extend(rows)
            elif isinstance(rows, dict) and name == "coverage":
                for key, counts in rows.items():
                    bucket = mine.setdefault(key, {"parsed": 0, "skipped": 0})
                    for outcome, value in counts.items():
                        bucket[outcome] = bucket.get(outcome, 0) + value
            elif isinstance(rows, dict) and name == "halves_present":
                mine.update(rows)
            elif isinstance(rows, dict):
                for key, value in rows.items():
                    mine[key] = mine.get(key, 0) + value

    def check_identifier_uniqueness(self) -> None:
        """FR-8: an identifier must name exactly one row, in every table.

        Identifiers are built from names, and OBIEE does not make names unique.
        The pinned corpus holds three ``Schema`` objects all called ``SH``, under
        three different ``Database`` objects, and two distinct physical tables
        named ``COSTS`` inside two of them. Any construction that drops a
        distinction the source made collapses two real objects onto one
        identifier, and every downstream citation of it becomes ambiguous.

        Nothing else detects this. Both rows are present, both are well-formed,
        both parse, and the totals look right — which is why it survived ten
        stories and a full test suite before anyone looked.

        Recorded as an error but deliberately **not** counted against coverage:
        the objects did parse, so marking them skipped would make coverage lie in
        the opposite direction.

        The sweep is generic — any list of rows carrying ``row_id`` is checked —
        so a table added later is covered without anyone remembering to add it.
        """
        for table, rows in sorted(vars(self).items()):
            if not isinstance(rows, list):
                continue
            seen: dict[str, str] = {}
            duplicated: dict[str, int] = {}
            for row in rows:
                row_id = getattr(row, "row_id", None)
                if not row_id:
                    continue
                if row_id in seen:
                    duplicated[row_id] = duplicated.get(row_id, 1) + 1
                else:
                    seen[row_id] = getattr(row, "rpd_id", "")
            for row_id, occurrences in sorted(duplicated.items()):
                self.errors.append(
                    ExtractionError(
                        seen[row_id],
                        "duplicate_identifier",
                        row_id,
                        table,
                        f"{occurrences} rows in {table} share this identifier; "
                        f"a Group Spec citing it cannot name which one. The "
                        f"identifier does not carry a distinction the source made.",
                    )
                )
