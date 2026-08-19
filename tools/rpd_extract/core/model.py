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
    kind: str  # "unmodelled_type" | "unread_attribute" | "unread_element"
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


@dataclass
class Estate:
    """Everything extracted from one corpus, across every ``rpd-id``."""

    physical_tables: list[PhysicalTable] = field(default_factory=list)
    physical_columns: list[PhysicalColumn] = field(default_factory=list)
    physical_joins: list[PhysicalJoin] = field(default_factory=list)
    logical_tables: list[LogicalTable] = field(default_factory=list)
    logical_columns: list[LogicalColumn] = field(default_factory=list)
    aggregation_rules: list[AggregationRule] = field(default_factory=list)
    subject_areas: list[SubjectArea] = field(default_factory=list)
    presentation_tables: list[PresentationTable] = field(default_factory=list)
    presentation_columns: list[PresentationColumn] = field(default_factory=list)
    logical_table_sources: list[LogicalTableSource] = field(default_factory=list)
    column_mappings: list[ColumnMapping] = field(default_factory=list)
    lineage: list[LineageRow] = field(default_factory=list)
    bmm_joins: list[BmmJoin] = field(default_factory=list)
    variables: list[Variable] = field(default_factory=list)
    init_blocks: list[InitBlock] = field(default_factory=list)
    security_rules: list[SecurityRule] = field(default_factory=list)
    unparsed: list[Unparsed] = field(default_factory=list)
    errors: list[ExtractionError] = field(default_factory=list)
    #: (rpd_id, object_type) -> {"parsed": n, "skipped": n}
    coverage: dict[tuple[str, str], dict[str, int]] = field(default_factory=dict)
    rpd_ids: list[str] = field(default_factory=list)

    def count(self, rpd_id: str, object_type: str, outcome: str, n: int = 1) -> None:
        bucket = self.coverage.setdefault((rpd_id, object_type), {"parsed": 0, "skipped": 0})
        bucket[outcome] += n

    def record_error(
        self, rpd_id: str, kind: str, source_id: str, object_type: str, reason: str
    ) -> None:
        """Something broke. Always counted as skipped so coverage stays honest."""
        self.errors.append(ExtractionError(rpd_id, kind, source_id, object_type, reason))
        self.count(rpd_id, object_type, "skipped")

    def record_gap(
        self, rpd_id: str, kind: str, object_type: str, detail: str, occurrences: int = 1
    ) -> None:
        """A known gap. Not counted as skipped — the object itself parsed fine."""
        self.unparsed.append(Unparsed(rpd_id, kind, object_type, detail, occurrences))

    def record_unmodelled(self, rpd_id: str, object_type: str, source_id: str) -> None:
        self.unparsed.append(
            Unparsed(rpd_id, "unmodelled_type", object_type, source_id)
        )
        self.count(rpd_id, object_type, "skipped")
