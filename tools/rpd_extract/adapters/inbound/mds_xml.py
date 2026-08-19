"""Inbound adapter: OBIEE MDS XML.

MDS XML is an exploded tree — one XML file per object under
``<rpd-id>/oracle/bi/server/base/<ObjectType>/<guid>.xml`` — cross-referenced by
``<path>.xml#<mdsid>``. This adapter is the *only* place those concepts exist
(AD-20). Everything handed to the core is expressed in Knowledge Base
identifiers; a GUID or a file path reaching ``core/`` is a defect.

Where a construct cannot be resolved with certainty the adapter records an
unparsed entry and continues. It never approximates and never guesses (AD-3).

Standard library only (NFR13).
"""

from __future__ import annotations

import collections
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from pathlib import Path

from tools.rpd_extract.core import identifiers as ids
from tools.rpd_extract.core.model import (
    AggregationRule,
    ColumnMapping,
    Estate,
    Expression,
    LineageRow,
    LogicalColumn,
    LogicalTable,
    LogicalTableSource,
    PhysicalColumn,
    PhysicalJoin,
    PhysicalTable,
    PresentationColumn,
    PresentationTable,
    SecurityRule,
    SubjectArea,
    Variable,
    InitBlock,
    BmmJoin,
    time_series_used,
    is_credential_name,
    RECOVERABLE_ELSEWHERE,
    TARGET_NOT_IN_KB,
    VALUE_NOT_CAPTURED,
)

NAMESPACE = "http://www.oracle.com/obis/repository"
BASE = ("oracle", "bi", "server", "base")

#: Object type directory -> the layer its identifiers belong to.
OBJECT_LAYER = {
    "PhysicalTable": ids.PHYSICAL,
    "Database": ids.PHYSICAL,
    "Schema": ids.PHYSICAL,
    "ConnectionPool": ids.PHYSICAL,
    "ComplexJoin": ids.PHYSICAL,
    "LogicalTable": ids.BUSINESS_MODEL,
    "LogicalTableSource": ids.BUSINESS_MODEL,
    "LogicalComplexJoin": ids.BUSINESS_MODEL,
    "LogicalSourceFolder": ids.BUSINESS_MODEL,
    "Dimension": ids.BUSINESS_MODEL,
    "BusinessModel": ids.BUSINESS_MODEL,
    "PresentationCatalog": ids.PRESENTATION,
    "PresentationTable": ids.PRESENTATION,
    "PresentationHierarchy": ids.PRESENTATION,
    "Group": ids.SECURITY,
    "User": ids.SECURITY,
    "ObjectPrivilege": ids.SECURITY,
    "QueryPrivilege": ids.SECURITY,
    "PrivilegePackage": ids.SECURITY,
    "Variable": ids.VARIABLE,
    "InitBlock": ids.VARIABLE,
    "Project": ids.VARIABLE,
}

_REF = re.compile(r"^/oracle/bi/server/base/(?P<type>[^/]+)/[^#]+#(?P<mdsid>.+)$")


class CorpusError(ValueError):
    """The corpus root is not a recognisable MDS XML tree."""


def _tag(element: ET.Element) -> str:
    return element.tag.split("}")[-1]


def _text(element: ET.Element | None) -> str:
    """Verbatim text. No stripping — FR-2 forbids reformatting anywhere.

    The single chokepoint for text access, which is what lets the audit observe
    it: every parser reads element text through here.
    """
    if element is None:
        return ""
    # Marked before the empty check: asking an element for text that turns out to
    # be absent is still a read. Marking only non-empty text would report every
    # empty <ExprText/> as content we ignored.
    if isinstance(element, _Observed):
        element.text_read = True
    if element.text is None:
        return ""
    return element.text


class _RecordingAttrib(dict):
    """An attribute map that remembers which keys the parsers asked for.

    Only the two accessors a parser uses record. ``keys``/``items``/iteration
    stay silent so the audit can inspect what is *present* without that
    inspection counting as a read.
    """

    __slots__ = ("owner",)

    def __init__(self, source, owner: "_Observed") -> None:
        super().__init__(source)
        self.owner = owner

    def get(self, key, default=None):
        self.owner.attributes_read.add(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self.owner.attributes_read.add(key)
        return super().__getitem__(key)


class _Observed(ET.Element):
    """An element that records what the parsers actually took from it.

    This is the mechanism that replaces a hand-written declaration of what the
    adapter reads. A declaration states an intention and drifts from the code
    silently; this states what the code demonstrably did on this very run, so
    the audit cannot claim a field was consumed when nothing consumed it.
    """

    def __init__(self, tag, attrib):
        super().__init__(tag, {})
        self.attributes_read: set[str] = set()
        self.text_read = False
        self.sought = False
        self.attrib = _RecordingAttrib(attrib, self)


def _observing_parser() -> ET.XMLParser:
    return ET.XMLParser(target=ET.TreeBuilder(element_factory=_Observed))


@dataclass(frozen=True)
class _Indexed:
    """One addressable object, keyed by its mdsid. Adapter-internal only."""

    rpd_id: str
    object_type: str
    tag: str
    name: str
    owner_mdsid: str
    container_mdsid: str = ""


class _Index:
    """mdsid -> object, built in a first pass so references can be resolved.

    MDS XML is a graph, not a tree: a physical table names its container by
    reference, and a column mapping names columns in other files. Resolving
    those needs every name in hand before any identifier can be built.
    """

    def __init__(self) -> None:
        self._by_mdsid: dict[str, _Indexed] = {}
        self._identifier: dict[str, str] = {}

    def add(self, mdsid: str, entry: _Indexed) -> None:
        self._by_mdsid[mdsid] = entry

    def get(self, mdsid: str) -> _Indexed | None:
        return self._by_mdsid.get(mdsid)

    def bind(self, mdsid: str, row_id: str) -> None:
        """Record the Knowledge Base identifier a source object resolved to."""
        self._identifier[mdsid] = row_id

    def identifier(self, mdsid: str) -> str:
        return self._identifier.get(mdsid, "")

    def resolve_ref(self, ref: str) -> tuple[str, str]:
        """``/…/<Type>/<file>.xml#<mdsid>`` -> ``(object_type, mdsid)``."""
        match = _REF.match(ref or "")
        if not match:
            return "", ""
        return match.group("type"), match.group("mdsid")


def _single_repository_files(
    root: Path, rpd_id: str
) -> tuple[list[tuple[str, str, Path]], list[tuple[str, str]]]:
    """Files for one repository tree whose ``rpd-id`` the Operator declared.

    This is the ordinary case: you exported one repository and you are naming
    it. AD-7 is satisfied because the name is declared on the command line, not
    derived from a filename, a timestamp, or a hash.
    """
    found: list[tuple[str, str, Path]] = []
    unreadable: list[tuple[str, str]] = []
    base = root.joinpath(*BASE)
    try:
        type_dirs = sorted(p for p in base.iterdir() if p.is_dir())
    except OSError as exc:
        raise CorpusError(f"cannot list {base}: {exc}") from None
    for type_dir in type_dirs:
        try:
            xml_files = sorted(type_dir.glob("*.xml"))
        except OSError as exc:
            unreadable.append((rpd_id, f"cannot list {type_dir}: {exc}"))
            continue
        for xml in xml_files:
            found.append((rpd_id, type_dir.name, xml))
    return found, unreadable


def _object_files(
    corpus_root: Path,
) -> tuple[list[tuple[str, str, Path]], list[tuple[str, str]]]:
    """Every ``(rpd_id, object_type, path)`` under the corpus root.

    Also returns directories that could not be read. An unreadable directory is
    skipped and reported, never allowed to abort the run and never ignored in
    silence (AD-3, NFR7) — a corpus root sitting beside another user's private
    directory is an ordinary situation, not a corrupt corpus.
    """
    found: list[tuple[str, str, Path]] = []
    unreadable: list[tuple[str, str]] = []

    try:
        candidates = sorted(p for p in corpus_root.iterdir() if p.is_dir())
    except OSError as exc:
        raise CorpusError(f"cannot read corpus root {corpus_root}: {exc}") from None

    for rpd_dir in candidates:
        base = rpd_dir.joinpath(*BASE)
        try:
            if not base.is_dir():
                continue
        except OSError as exc:
            unreadable.append((rpd_dir.name, f"cannot probe {base}: {exc}"))
            continue

        rpd_id = ids.validate_rpd_id(rpd_dir.name)
        try:
            type_dirs = sorted(p for p in base.iterdir() if p.is_dir())
        except OSError as exc:
            unreadable.append((rpd_id, f"cannot list {base}: {exc}"))
            continue

        for type_dir in type_dirs:
            try:
                xml_files = sorted(type_dir.glob("*.xml"))
            except OSError as exc:
                unreadable.append((rpd_id, f"cannot list {type_dir}: {exc}"))
                continue
            for xml in xml_files:
                found.append((rpd_id, type_dir.name, xml))

    return found, unreadable


def _parse_all(
    files: list[tuple[str, str, Path]], estate: Estate
) -> list[tuple[str, str, ET.Element]]:
    """Parse every file once, into trees that observe what is read from them.

    Parsing once and keeping the trees is what makes the audit possible: reads
    happen across several passes, and they must all accumulate on the *same*
    elements for the audit to see the whole picture. Re-parsing per pass would
    give each pass a fresh tree that forgets what the previous one read.

    Measured at 28 MB for the 1383-file corpus, against roughly 9 MB of source.
    """
    trees: list[tuple[str, str, ET.Element]] = []
    for rpd_id, object_type, path in files:
        try:
            root = ET.parse(path, parser=_observing_parser()).getroot()
        except ET.ParseError as exc:
            estate.record_error(rpd_id, "malformed_xml", path.name, object_type, str(exc))
            continue
        trees.append((rpd_id, object_type, root))
    return trees


def _build_index(trees: list[tuple[str, str, ET.Element]]) -> _Index:
    index = _Index()
    for rpd_id, object_type, root in trees:
        stack = [(root, "")]
        while stack:
            element, owner = stack.pop()
            # Read through ``dict`` deliberately, bypassing the recording
            # accessor. Indexing touches mdsid, name and containerRef on every
            # element in the corpus purely to build the reference graph; letting
            # that count as consumption would mark every nested structure as
            # read and silence the audit exactly where it is needed. A LogicalKey
            # whose only reader is the index has not been modelled, and must
            # still be reported as a gap.
            mdsid = dict.get(element.attrib, "mdsid", "")
            if mdsid:
                # The containment chain is recorded during indexing so it can be
                # walked when identifiers are built: a container's name alone does
                # not identify it, because OBIEE permits the same Schema name under
                # more than one Database.
                _, container_mdsid = index.resolve_ref(
                    dict.get(element.attrib, "containerRef", "")
                )
                index.add(
                    mdsid,
                    _Indexed(
                        rpd_id=rpd_id,
                        object_type=object_type,
                        tag=_tag(element),
                        name=dict.get(element.attrib, "name", ""),
                        owner_mdsid=owner,
                        container_mdsid=container_mdsid,
                    ),
                )
                owner = mdsid
            for child in element:
                stack.append((child, owner))
    return index


def _read_expression(
    container: ET.Element,
    index: _Index,
    estate: Estate,
    rpd_id: str,
    owner_id: str,
) -> Expression:
    """Read an ``Expr``-shaped element into all three forms (AD-21).

    A reference that cannot be resolved is recorded as an unparsed entry, never
    dropped. A silently missing reference leaves an expression that still looks
    complete — the plausible-wrong-answer failure NFR7 names as primary.
    """
    text = text_desc = ""
    refs: list[str] = []
    for child in container:
        tag = _tag(child)
        if tag == "ExprText":
            text = _text(child)
        elif tag == "ExprTextDesc":
            text_desc = _text(child)
        elif tag == "ObjectRefList":
            for ref_object in child:
                if _tag(ref_object) != "RefObject":
                    continue
                raw = ref_object.attrib.get("objectRef", "")
                object_type, mdsid = index.resolve_ref(raw)
                resolved = index.identifier(mdsid) if mdsid else ""
                if resolved:
                    refs.append(resolved)
                else:
                    # Recorded as blank rather than as a raw GUID: AD-20 keeps
                    # source-format concepts out of the core, and a dangling
                    # GUID in the Knowledge Base is worse than a recorded gap.
                    estate.record_error(
                        rpd_id, "unresolved_reference", owner_id, "ExpressionRef",
                        f"reference to {object_type or 'unknown type'} could not be "
                        f"resolved to a Knowledge Base identifier",
                    )
    return Expression(text=text, text_desc=text_desc, refs=tuple(refs))


def _sought(element: ET.Element) -> ET.Element:
    """Mark an element as one a parser deliberately went looking for.

    Traversal is consumption too. A wrapper the parser walks through on purpose —
    ``RefColumns``, ``ObjectRefList`` — has been handled even though nothing is
    read off the wrapper itself, and reporting it as a gap would bury the real
    findings in noise.
    """
    if isinstance(element, _Observed):
        element.sought = True
    return element


def _first_child(element: ET.Element, name: str) -> ET.Element | None:
    for child in element:
        if _tag(child) == name:
            return _sought(child)
    return None


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [_sought(child) for child in element if _tag(child) == name]


def _container_path(element: ET.Element, index: _Index) -> tuple[str, ...]:
    """Resolve ``@containerRef`` to the full containment chain, outermost first.

    A single container *name* does not identify a container. In the pinned corpus
    three distinct ``Schema`` objects are all named ``SH``, each under a different
    ``Database``, and two different physical tables named ``COSTS`` live in two of
    them. Keying on the name alone collapsed those onto one identifier, which
    breaks FR-8: an identifier cited from a Group Spec must name exactly one row.

    Walking the chain gives ``<Database>.<Schema>.<Table>`` where a Database is
    present, and ``<Schema>.<Table>`` where it is not, so a repository that never
    had the ambiguity keeps the identifiers it already had.

    Cycles are possible in a hand-edited repository, so the walk is bounded by the
    set of mdsids already visited rather than trusting the data to terminate.
    """
    _, mdsid = index.resolve_ref(element.attrib.get("containerRef", ""))
    parts: list[str] = []
    seen: set[str] = set()
    while mdsid and mdsid not in seen:
        seen.add(mdsid)
        entry = index.get(mdsid)
        if entry is None or not entry.name:
            break
        parts.append(entry.name)
        mdsid = entry.container_mdsid
    parts.reverse()
    return tuple(parts)


def _parse_physical(rpd_id: str, root: ET.Element, index: _Index, estate: Estate) -> None:
    name = root.attrib.get("name", "")
    container = _container_path(root, index)
    if not name or not container:
        estate.record_error(
            rpd_id, "missing_name", root.attrib.get("mdsid", "?"), "PhysicalTable",
            "table name or container could not be resolved",
        )
        return

    table_id = ids.make_id(rpd_id, ids.PHYSICAL, *container, name)
    index.bind(root.attrib.get("mdsid", ""), table_id)
    estate.physical_tables.append(
        PhysicalTable(
            row_id=table_id,
            rpd_id=rpd_id,
            # Dotted, matching the identifier: a reader joining this column to a
            # row_id should not have to reconstruct the separator.
            container=".".join(container),
            name=name,
            table_type=root.attrib.get("type", ""),
            max_conn=root.attrib.get("maxConn", ""),
        )
    )
    estate.count(rpd_id, "PhysicalTable", "parsed")

    for column in _children(root, "PhysicalColumn"):
        column_name = column.attrib.get("name", "")
        if not column_name:
            estate.record_error(
                rpd_id, "missing_name", column.attrib.get("mdsid", "?"),
                "PhysicalColumn", "column has no name",
            )
            continue
        column_id = ids.make_id(rpd_id, ids.PHYSICAL, *container, name, column_name)
        index.bind(column.attrib.get("mdsid", ""), column_id)
        estate.physical_columns.append(
            PhysicalColumn(
                row_id=column_id,
                rpd_id=rpd_id,
                table_id=table_id,
                name=column_name,
                data_type=column.attrib.get("dataType", ""),
                special_type=column.attrib.get("specialType", ""),
                precision=column.attrib.get("precision", ""),
                nullable=column.attrib.get("nullable", ""),
                external_name=column.attrib.get("extName", ""),
            )
        )
        estate.count(rpd_id, "PhysicalColumn", "parsed")

    for foreign_key in _children(root, "PhysicalForeignKey"):
        fk_name = foreign_key.attrib.get("name", "")
        columns = []
        ref_columns = _first_child(foreign_key, "RefColumns")
        if ref_columns is not None:
            for ref in _children(ref_columns, "RefColumn"):
                _, mdsid = index.resolve_ref(ref.attrib.get("columnRef", ""))
                columns.append(mdsid)
        estate.physical_joins.append(
            PhysicalJoin(
                row_id=ids.make_id(
                    rpd_id, ids.PHYSICAL, *container, name, fk_name or "fk"
                ),
                rpd_id=rpd_id,
                kind="foreign_key",
                name=fk_name,
                table1_id=table_id,
                columns=tuple(columns),
            )
        )
        estate.count(rpd_id, "PhysicalForeignKey", "parsed")


def _parse_complex_join(rpd_id: str, root: ET.Element, index: _Index, estate: Estate) -> None:
    name = root.attrib.get("name", "")
    if not name:
        estate.record_error(
            rpd_id, "missing_name", root.attrib.get("mdsid", "?"), "ComplexJoin",
            "join has no name",
        )
        return
    _, t1 = index.resolve_ref(root.attrib.get("table1Ref", ""))
    _, t2 = index.resolve_ref(root.attrib.get("table2Ref", ""))
    expression = Expression("", "", ())
    expr = _first_child(root, "Expr")
    if expr is not None:
        expression = _read_expression(expr, index, estate, rpd_id, name)
    estate.physical_joins.append(
        PhysicalJoin(
            row_id=ids.make_id(rpd_id, ids.PHYSICAL, "joins", name),
            rpd_id=rpd_id,
            kind="complex_join",
            name=name,
            table1_id=index.identifier(t1),
            table2_id=index.identifier(t2),
            cardinality=root.attrib.get("cardinality", ""),
            expression=expression,
        )
    )
    estate.count(rpd_id, "ComplexJoin", "parsed")


def _parse_logical(rpd_id: str, root: ET.Element, index: _Index, estate: Estate) -> None:
    name = root.attrib.get("name", "")
    if not name:
        estate.record_error(
            rpd_id, "missing_name", root.attrib.get("mdsid", "?"), "LogicalTable",
            "table has no name",
        )
        return

    _, model_mdsid = index.resolve_ref(root.attrib.get("subjectAreaRef", ""))
    model_entry = index.get(model_mdsid) if model_mdsid else None
    business_model = model_entry.name if model_entry else ""
    if not business_model:
        # The business model is the identifier's container. Without it the
        # identifier would be ambiguous across models, so refuse rather than
        # invent a placeholder (AD-3).
        estate.record_error(
            rpd_id, "unresolved_reference", root.attrib.get("mdsid", "?"), "LogicalTable",
            f"business model for logical table {name!r} could not be resolved",
        )
        return

    sources = _first_child(root, "RefTableSources")
    source_refs = _children(sources, "RefLogicalTableSource") if sources is not None else []

    table_id = ids.make_id(rpd_id, ids.BUSINESS_MODEL, business_model, name)
    index.bind(root.attrib.get("mdsid", ""), table_id)
    estate.logical_tables.append(
        LogicalTable(
            row_id=table_id,
            rpd_id=rpd_id,
            business_model=business_model,
            name=name,
            source_count=len(source_refs),
        )
    )
    estate.count(rpd_id, "LogicalTable", "parsed")

    for column in _children(root, "LogicalColumn"):
        column_name = column.attrib.get("name", "")
        if not column_name:
            estate.record_error(
                rpd_id, "missing_name", column.attrib.get("mdsid", "?"),
                "LogicalColumn", "column has no name",
            )
            continue
        column_id = ids.make_id(
            rpd_id, ids.BUSINESS_MODEL, business_model, name, column_name
        )
        index.bind(column.attrib.get("mdsid", ""), column_id)

        derived = Expression("", "", ())
        own_expr = _first_child(column, "Expr")
        if own_expr is not None:
            derived = _read_expression(own_expr, index, estate, rpd_id, column_id)

        mapping = Expression("", "", ())
        attr_defn = _first_child(column, "AttrDefn")
        if attr_defn is not None:
            attr_expr = _first_child(attr_defn, "Expr")
            if attr_expr is not None:
                mapping = _read_expression(attr_expr, index, estate, rpd_id, column_id)

        measure = _first_child(column, "MeasureDefn")
        estate.logical_columns.append(
            LogicalColumn(
                row_id=column_id,
                rpd_id=rpd_id,
                table_id=table_id,
                name=column_name,
                is_writeable=column.attrib.get("isWriteable", ""),
                is_measure=measure is not None,
                source_count=len(source_refs),
                derived=derived,
                mapping=mapping,
            )
        )
        estate.count(rpd_id, "LogicalColumn", "parsed")

        if measure is not None:
            # A measure may carry several rules: one default plus dimension
            # specific overrides. FR-4 requires the overrides, so every rule
            # gets its own row — collapsing them loses the detail silently.
            for position, rule in enumerate(_children(measure, "AggrRule")):
                rule_expr = _first_child(rule, "Expr")
                estate.aggregation_rules.append(
                    AggregationRule(
                        row_id=f"{column_id}#aggr{position}",
                        rpd_id=rpd_id,
                        logical_column_id=column_id,
                        name=rule.attrib.get("name", ""),
                        is_default=rule.attrib.get("isDefault", ""),
                        expression=(
                            _read_expression(
                                rule_expr, index, estate, rpd_id, column_id
                            )
                            if rule_expr is not None
                            else Expression("", "", ())
                        ),
                    )
                )
                estate.count(rpd_id, "AggrRule", "parsed")


def _parse_subject_area(rpd_id: str, root: ET.Element, index: _Index, estate: Estate) -> None:
    name = root.attrib.get("name", "")
    if not name:
        estate.record_error(
            rpd_id, "missing_name", root.attrib.get("mdsid", "?"),
            "PresentationCatalog", "no name",
        )
        return
    _, model_mdsid = index.resolve_ref(root.attrib.get("subjectAreaRef", ""))
    model_entry = index.get(model_mdsid) if model_mdsid else None

    _, fact_mdsid = index.resolve_ref(root.attrib.get("defaultFactColumnRef", ""))

    row_id = ids.make_id(rpd_id, ids.PRESENTATION, name)
    index.bind(root.attrib.get("mdsid", ""), row_id)
    estate.subject_areas.append(
        SubjectArea(
            row_id=row_id,
            rpd_id=rpd_id,
            name=name,
            business_model=model_entry.name if model_entry else "",
            implicit_fact_column_id=index.identifier(fact_mdsid) if fact_mdsid else "",
            is_auto_aggregate=root.attrib.get("isAutoAggr", ""),
            aliases=tuple(a.attrib.get("name", "") for a in _children(root, "Alias")),
        )
    )
    estate.count(rpd_id, "PresentationCatalog", "parsed")


def _parse_presentation_table(
    rpd_id: str, root: ET.Element, index: _Index, estate: Estate
) -> None:
    name = root.attrib.get("name", "")
    _, catalog_mdsid = index.resolve_ref(root.attrib.get("containerRef", ""))
    subject_area_id = index.identifier(catalog_mdsid) if catalog_mdsid else ""
    if not name or not subject_area_id:
        estate.record_error(
            rpd_id, "unresolved_reference", root.attrib.get("mdsid", "?"),
            "PresentationTable",
            "table name or owning Subject Area could not be resolved",
        )
        return

    _, _, area_path = ids.parse_id(subject_area_id)
    table_id = ids.make_id(rpd_id, ids.PRESENTATION, area_path, name)
    index.bind(root.attrib.get("mdsid", ""), table_id)
    estate.presentation_tables.append(
        PresentationTable(
            row_id=table_id,
            rpd_id=rpd_id,
            subject_area_id=subject_area_id,
            name=name,
            display_name=root.attrib.get("dispName", ""),
            aliases=tuple(a.attrib.get("name", "") for a in _children(root, "Alias")),
        )
    )
    estate.count(rpd_id, "PresentationTable", "parsed")

    for column in _children(root, "PresentationColumn"):
        column_name = column.attrib.get("name", "")
        if not column_name:
            estate.record_error(
                rpd_id, "missing_name", column.attrib.get("mdsid", "?"),
                "PresentationColumn", "no name",
            )
            continue
        _, logical_mdsid = index.resolve_ref(column.attrib.get("logicalColumnRef", ""))
        logical_id = index.identifier(logical_mdsid) if logical_mdsid else ""
        if logical_mdsid and not logical_id:
            estate.record_error(
                rpd_id, "unresolved_reference", f"{table_id}.{column_name}",
                "PresentationColumn",
                "logical column reference does not resolve to a known logical column",
            )
        column_id = ids.make_id(rpd_id, ids.PRESENTATION, area_path, name, column_name)
        index.bind(column.attrib.get("mdsid", ""), column_id)
        estate.presentation_columns.append(
            PresentationColumn(
                row_id=column_id,
                rpd_id=rpd_id,
                table_id=table_id,
                name=column_name,
                logical_column_id=logical_id,
                override_logical_name=column.attrib.get("overrideLogicalName", ""),
                display_name=column.attrib.get("dispName", ""),
            )
        )
        estate.count(rpd_id, "PresentationColumn", "parsed")


def _parse_table_source(rpd_id: str, root: ET.Element, index: _Index, estate: Estate) -> None:
    name = root.attrib.get("name", "")
    _, table_mdsid = index.resolve_ref(root.attrib.get("logicalTableRef", ""))
    logical_table_id = index.identifier(table_mdsid) if table_mdsid else ""
    if not name or not logical_table_id:
        estate.record_error(
            rpd_id, "unresolved_reference", root.attrib.get("mdsid", "?"),
            "LogicalTableSource",
            "source name or owning logical table could not be resolved",
        )
        return

    _, _, table_path = ids.parse_id(logical_table_id)
    source_id = ids.make_id(rpd_id, ids.BUSINESS_MODEL, table_path, "src", name)
    index.bind(root.attrib.get("mdsid", ""), source_id)

    def optional(tag: str) -> Expression:
        element = _first_child(root, tag)
        if element is None:
            return Expression("", "", ())
        return _read_expression(element, index, estate, rpd_id, source_id)

    estate.logical_table_sources.append(
        LogicalTableSource(
            row_id=source_id,
            rpd_id=rpd_id,
            logical_table_id=logical_table_id,
            name=name,
            is_active=root.attrib.get("isActive", ""),
            # Empty means NOT RECORDED, never "lowest". Inferring an order from
            # document position is the guess AD-3 forbids.
            priority=root.attrib.get("priorityGroup", ""),
            fragment=optional("FragmentContent"),
            where_clause=optional("WhereClause"),
            group_by=optional("GroupBy"),
        )
    )
    estate.count(rpd_id, "LogicalTableSource", "parsed")

    for position, mapping in enumerate(_children(root, "ColumnMapping")):
        logical_expr_el = _first_child(mapping, "LogicalColumnExpr")
        physical_expr_el = _first_child(mapping, "Expr")
        logical_expr = (
            _read_expression(logical_expr_el, index, estate, rpd_id, source_id)
            if logical_expr_el is not None
            else Expression("", "", ())
        )
        physical_expr = (
            _read_expression(physical_expr_el, index, estate, rpd_id, source_id)
            if physical_expr_el is not None
            else Expression("", "", ())
        )
        estate.column_mappings.append(
            ColumnMapping(
                row_id=f"{source_id}#map{position}",
                rpd_id=rpd_id,
                source_id=source_id,
                logical_column_id=logical_expr.refs[0] if logical_expr.refs else "",
                physical_column_id=physical_expr.refs[0] if physical_expr.refs else "",
                logical_expression=logical_expr,
                physical_expression=physical_expr,
            )
        )
        estate.count(rpd_id, "ColumnMapping", "parsed")


def _count_mapped_sources(estate: Estate) -> None:
    """Record, per logical column, how many sources actually map it.

    Distinct from the owning table's source count: a table with four sources
    may map a given column in only two of them. Conflating the two produces a
    false mismatch, and — worse — hides the real signal, which is the gap.
    """
    mapped: dict[str, set[str]] = {}
    for mapping in estate.column_mappings:
        if mapping.logical_column_id:
            mapped.setdefault(mapping.logical_column_id, set()).add(mapping.source_id)
    estate.logical_columns = [
        replace(column, mapped_source_count=len(mapped.get(column.row_id, ())))
        for column in estate.logical_columns
    ]


def _build_lineage(estate: Estate) -> None:
    """Walk presentation → logical → source → physical, one row per path.

    A logical column satisfied by three sources produces three rows. That is
    FR-3's requirement and the reason the count is asserted downstream: a
    dropped source is a missing row, and a missing row looks like normal output.
    """
    physical_table_of = {c.row_id: c.table_id for c in estate.physical_columns}
    mappings_by_logical: dict[str, list] = {}
    for mapping in estate.column_mappings:
        if mapping.logical_column_id:
            mappings_by_logical.setdefault(mapping.logical_column_id, []).append(mapping)

    for column in estate.presentation_columns:
        if not column.logical_column_id:
            continue
        for mapping in mappings_by_logical.get(column.logical_column_id, []):
            estate.lineage.append(
                LineageRow(
                    row_id=f"{column.row_id}#{mapping.source_id}",
                    rpd_id=column.rpd_id,
                    presentation_column_id=column.row_id,
                    logical_column_id=column.logical_column_id,
                    source_id=mapping.source_id,
                    physical_table_id=physical_table_of.get(mapping.physical_column_id, ""),
                    physical_column_id=mapping.physical_column_id,
                )
            )


def _parse_bmm_join(rpd_id: str, root: ET.Element, index: _Index, estate: Estate) -> None:
    name = root.attrib.get("name", "")
    if not name:
        estate.record_error(rpd_id, "missing_name", root.attrib.get("mdsid", "?"),
                            "LogicalComplexJoin", "no name")
        return
    _, t1 = index.resolve_ref(root.attrib.get("logicalTable1Ref", ""))
    _, t2 = index.resolve_ref(root.attrib.get("logicalTable2Ref", ""))
    estate.bmm_joins.append(
        BmmJoin(
            row_id=ids.make_id(rpd_id, ids.BUSINESS_MODEL, "joins", name),
            rpd_id=rpd_id,
            name=name,
            # The inner / left-outer distinction FR-4 names.
            join_type=root.attrib.get("type", ""),
            table1_id=index.identifier(t1),
            multiplicity1=root.attrib.get("multiplicity1", ""),
            is_aggregate1=root.attrib.get("isAggregate1", ""),
            table2_id=index.identifier(t2),
            multiplicity2=root.attrib.get("multiplicity2", ""),
            is_aggregate2=root.attrib.get("isAggregate2", ""),
        )
    )
    estate.count(rpd_id, "LogicalComplexJoin", "parsed")


def _parse_variable(rpd_id: str, root: ET.Element, index: _Index, estate: Estate) -> None:
    name = root.attrib.get("name", "")
    if not name:
        estate.record_error(rpd_id, "missing_name", root.attrib.get("mdsid", "?"),
                            "Variable", "no name")
        return
    row_id = ids.make_id(rpd_id, ids.VARIABLE, name)
    index.bind(root.attrib.get("mdsid", ""), row_id)
    _, ib = index.resolve_ref(root.attrib.get("initBlockRef", ""))
    expr_el = _first_child(root, "Expr")
    expression = (
        _read_expression(expr_el, index, estate, rpd_id, row_id)
        if expr_el is not None
        else Expression("", "", ())
    )

    # NFR11: a credential must never reach the Knowledge Base. Withhold the
    # value, keep the row so the variable is still visible, and record the
    # withholding — AD-3 forbids doing it silently.
    redacted = is_credential_name(name)
    if redacted:
        expression = Expression("", "", ())
        estate.record_gap(
            rpd_id, "redacted_value", "Variable",
            f"{name} — value withheld: the name indicates a credential (NFR11)",
        )

    estate.variables.append(
        Variable(
            row_id=row_id,
            rpd_id=rpd_id,
            name=name,
            is_session=root.attrib.get("isSessionVar", ""),
            init_block_id=index.identifier(ib) if ib else "",
            security_mask=root.attrib.get("securityMask", ""),
            expression=expression,
            redacted=redacted,
        )
    )
    estate.count(rpd_id, "Variable", "parsed")


def _parse_init_block(rpd_id: str, root: ET.Element, index: _Index, estate: Estate) -> None:
    name = root.attrib.get("name", "")
    if not name:
        estate.record_error(rpd_id, "missing_name", root.attrib.get("mdsid", "?"),
                            "InitBlock", "no name")
        return
    row_id = ids.make_id(rpd_id, ids.VARIABLE, "init", name)
    index.bind(root.attrib.get("mdsid", ""), row_id)
    init_string = _first_child(root, "InitString")
    estate.init_blocks.append(
        InitBlock(
            row_id=row_id,
            rpd_id=rpd_id,
            name=name,
            refresh_period=root.attrib.get("refreshPeriod", ""),
            is_session=root.attrib.get("isSessionVar", ""),
            is_enabled=root.attrib.get("isEnabled", ""),
            init_string=_text(init_string),
        )
    )
    estate.count(rpd_id, "InitBlock", "parsed")


def _parse_group(rpd_id: str, root: ET.Element, index: _Index, estate: Estate) -> None:
    name = root.attrib.get("name", "")
    if name:
        index.bind(root.attrib.get("mdsid", ""), ids.make_id(rpd_id, ids.SECURITY, name))
        estate.count(rpd_id, "Group", "parsed")


def _parse_privilege_package(rpd_id: str, root: ET.Element, index: _Index, estate: Estate) -> None:
    name = root.attrib.get("name", "")
    _, role_mdsid = index.resolve_ref(root.attrib.get("roleRef", ""))
    role_entry = index.get(role_mdsid) if role_mdsid else None
    role = role_entry.name if role_entry else ""
    index.bind(root.attrib.get("mdsid", ""), ids.make_id(rpd_id, ids.SECURITY, "pkg", name or "?"))
    for position, mapping in enumerate(_children(root, "QueryPrivilegeMapping")):
        _, qp = index.resolve_ref(mapping.attrib.get("queryPrivilegeRef", ""))
        qp_entry = index.get(qp) if qp else None
        estate.security_rules.append(
            SecurityRule(
                row_id=ids.make_id(rpd_id, ids.SECURITY, "pkg", name or "?", f"q{position}"),
                rpd_id=rpd_id,
                kind="query_privilege",
                role=role,
                subject_id=qp_entry.name if qp_entry else "",
                detail=name,
            )
        )
    estate.count(rpd_id, "PrivilegePackage", "parsed")


def _parse_object_privilege(rpd_id: str, root: ET.Element, index: _Index, estate: Estate) -> None:
    name = root.attrib.get("name", "")
    _, pkg = index.resolve_ref(root.attrib.get("privilegePackageRef", ""))
    targets = _first_child(root, "RefObjects")
    refs = _children(targets, "RefObject") if targets is not None else []
    for position, ref in enumerate(refs or [None]):
        _, target = index.resolve_ref(ref.attrib.get("objectRef", "")) if ref is not None else ("", "")
        estate.security_rules.append(
            SecurityRule(
                row_id=ids.make_id(rpd_id, ids.SECURITY, "obj", name or "?", f"o{position}"),
                rpd_id=rpd_id,
                kind="object_privilege",
                role="",
                subject_id=index.identifier(target) if target else "",
                detail=f"{root.attrib.get('type', '')} via {index.identifier(pkg) if pkg else ''}",
            )
        )
    estate.count(rpd_id, "ObjectPrivilege", "parsed")


def _collect_row_filters(estate: Estate) -> None:
    """Row-level predicates live on Logical Table Sources, not on roles.

    A role with privileges but no predicate, and a predicate not reachable from
    any role, are both real states. Recording the predicate where it actually
    sits keeps both visible rather than forcing a join that does not exist.
    """
    for source in estate.logical_table_sources:
        if source.where_clause.is_empty:
            continue
        estate.security_rules.append(
            SecurityRule(
                row_id=f"{source.row_id}#filter",
                rpd_id=source.rpd_id,
                kind="row_filter",
                role="",
                subject_id=source.logical_table_id,
                detail=source.name,
                expression=source.where_clause,
            )
        )


def _flag_time_series(estate: Estate) -> None:
    estate.logical_columns = [
        replace(c, time_series=time_series_used(c.derived, c.mapping))
        for c in estate.logical_columns
    ]



def _audit_unread(
    trees: list[tuple[str, str, ET.Element]], index: _Index, estate: Estate
) -> None:
    """Report source content the parsers never took, observed rather than declared.

    Whole-object honesty is not enough. An object can parse "successfully" while
    attributes, child elements and text on it are discarded without a word —
    the silent omission NFR7 names as the primary failure mode, one level below
    where AD-3 was watching.

    This used to compare each file against ``_CONSUMED``, a hand-written list of
    what each parser was believed to read. That list was the audit's only source
    of truth and nothing tied it to the code, so it could — and did — silence a
    field no parser touched: ``PrivilegePackage@userRef`` was declared consumed
    while the parser read only ``roleRef``, so three privilege grants to named
    users were dropped and reported as fully understood.

    So the audit no longer asks what the adapter *claims* to read. It watches
    what the adapter *did* read, on this run, through `_Observed`. The list
    cannot disagree with the code because it is no longer a list.

    Reachability is computed over the real tree rather than by tag name, so a
    tag that is read in one context is not assumed read in another. A container
    element counts as traversed when anything beneath it was read — otherwise
    every wrapper the parsers pass through would be reported as a gap.

    Drift now fails safe in the only direction left: a branch this corpus never
    exercises reports a gap that is merely noise, never silence.
    """
    gaps: dict[tuple[str, str, str], int] = collections.Counter()
    #: Every value seen for an unread attribute, so the cost of not reading it
    #: can be derived from the data rather than judged by its name.
    values: dict[tuple[str, str, str], list[str]] = collections.defaultdict(list)

    def touched(element: ET.Element) -> bool:
        if isinstance(element, _Observed):
            return (
                bool(element.attributes_read) or element.text_read or element.sought
            )
        return False

    reached: dict[int, bool] = {}

    def mark(element: ET.Element) -> bool:
        """Was anything in this subtree read? Computed once, bottom-up."""
        below = [mark(child) for child in element]
        here = touched(element) or any(below)
        reached[id(element)] = here
        return here

    def visit(rpd_id: str, object_type: str, element: ET.Element) -> None:
        tag = _tag(element)
        # An element nothing in the subtree touched is unhandled as a whole. A
        # wrapper the parsers walked through is not, even though nothing was read
        # off the wrapper itself.
        if not reached[id(element)]:
            gaps[(rpd_id, object_type, tag)] += 1
        # Reported at every level regardless, including inside an unhandled
        # subtree: rolling a branch up to its root hides what is in it, and
        # ``Join@type`` is exactly the parity-critical detail that must not be
        # summarised away.
        present = set(dict.keys(element.attrib))
        read = element.attributes_read if isinstance(element, _Observed) else set()
        for attribute in sorted(present - read):
            key = (rpd_id, object_type, f"{tag}@{attribute}")
            gaps[key] += 1
            values[key].append(dict.get(element.attrib, attribute, ""))
        text = element.text or ""
        if text.strip() and isinstance(element, _Observed) and not element.text_read:
            gaps[(rpd_id, object_type, f"{tag}#text")] += 1
        for child in element:
            visit(rpd_id, object_type, child)

    for rpd_id, object_type, root in trees:
        if object_type not in _HANDLED:
            continue  # unmodelled types are already reported whole
        mark(root)
        visit(rpd_id, object_type, root)

    def assess(key: tuple[str, str, str]) -> str:
        """What does not reading this cost? Decided from the values, not the name.

        A reference whose targets the Knowledge Base already identifies costs
        nothing — the link is in the output by another path. A reference whose
        target is absent costs the whole link, and is the case worth acting on.
        Anything that is not a reference costs its own value.
        """
        seen = [v for v in values.get(key, []) if v]
        if not seen:
            return VALUE_NOT_CAPTURED
        targets = [index.resolve_ref(v)[1] for v in seen]
        if not all(targets):
            return VALUE_NOT_CAPTURED  # not reference-shaped at all
        # Conservative: one unresolvable target makes the whole attribute a loss.
        # Reporting "recoverable" for a mixed case would understate it.
        if all(index.identifier(mdsid) for mdsid in targets):
            return RECOVERABLE_ELSEWHERE
        return TARGET_NOT_IN_KB

    for (rpd_id, object_type, detail), occurrences in sorted(gaps.items()):
        key = (rpd_id, object_type, detail)
        if "@" in detail:
            kind, assessment = "unread_attribute", assess(key)
        elif detail.endswith("#text"):
            kind, assessment = "unread_text", VALUE_NOT_CAPTURED
        else:
            kind, assessment = "unread_element", VALUE_NOT_CAPTURED
        estate.record_gap(rpd_id, kind, object_type, detail, occurrences, assessment)



#: unparsed object type rather than passed over in silence (FR-5, AD-3).
_HANDLED = {
    "PhysicalTable",
    "ComplexJoin",
    "LogicalTable",
    "PresentationCatalog",
    "PresentationTable",
    "LogicalTableSource",
    "LogicalComplexJoin",
    "Variable",
    "InitBlock",
    "Group",
    "PrivilegePackage",
    "ObjectPrivilege",
}

#: Types deliberately consumed by the index alone — they contribute names and
#: containers rather than Knowledge Base rows of their own at this stage.
_INDEX_ONLY = {"Database", "Schema", "ConnectionPool", "BusinessModel"}


def _looks_like_base_dir(path: Path) -> bool:
    """Is this the ``base/`` directory itself, rather than its grandparent?"""
    try:
        for child in path.iterdir():
            if child.is_dir() and any(child.glob("*.xml")):
                return True
    except OSError:
        return False
    return False


def _wrong_root_message(corpus_root: Path) -> str:
    """Explain a mis-aimed --corpus, naming the likely fix.

    Aiming at ``base/`` is the easy mistake, because that is the path the
    documentation shows when describing the expected layout. Saying only
    "must contain oracle/bi/server/base" is useless to someone standing in it.
    """
    if corpus_root.name == "base" or _looks_like_base_dir(corpus_root):
        suggestion = corpus_root
        for _ in BASE:
            suggestion = suggestion.parent
        return (
            f"{corpus_root} looks like the 'base' directory itself. --corpus wants "
            f"the directory CONTAINING 'oracle/', so the whole path "
            f"oracle/bi/server/base/ sits underneath it.\n"
            f"       Try:  --corpus {suggestion}"
        )
    return (
        f"--rpd-id was given, so {corpus_root} must itself contain "
        f"oracle/bi/server/base/ — it does not. Either point --corpus at the "
        f"repository root, or drop --rpd-id to treat this directory as holding "
        f"one folder per repository."
    )


def load(corpus_root: Path | str, rpd_id: str | None = None) -> Estate:
    """Parse every MDS XML object under ``corpus_root`` into an Estate.

    Two shapes are accepted:

    * ``rpd_id`` given — ``corpus_root`` **is** one repository tree containing
      ``oracle/bi/server/base/``. The single-repository case.
    * ``rpd_id`` omitted — ``corpus_root`` holds one directory per repository,
      each directory name being that repository's declared ``rpd-id``.

    Either way the identifier is declared by the Operator, never derived (AD-7).
    """
    corpus_root = Path(corpus_root)
    if not corpus_root.is_dir():
        raise CorpusError(f"corpus root {corpus_root} is not a directory")

    if rpd_id is not None:
        ids.validate_rpd_id(rpd_id)
        if not corpus_root.joinpath(*BASE).is_dir():
            raise CorpusError(_wrong_root_message(corpus_root))
        files, unreadable = _single_repository_files(corpus_root, rpd_id)
    else:
        files, unreadable = _object_files(corpus_root)

    if not files:
        raise CorpusError(
            f"no MDS XML found under {corpus_root}. Expected either "
            f"<corpus>/oracle/bi/server/base/<ObjectType>/*.xml with --rpd-id, or "
            f"<corpus>/<rpd-id>/oracle/bi/server/base/<ObjectType>/*.xml without it. "
            f"See README.md."
        )

    estate = Estate()
    estate.rpd_ids = sorted({rpd_id for rpd_id, _, _ in files})
    for rpd_id, reason in unreadable:
        estate.record_error(rpd_id, "unreadable", str(corpus_root), "Directory", reason)
    trees = _parse_all(files, estate)
    index = _build_index(trees)

    # Order matters: each pass resolves references into the identifiers the
    # previous pass bound. Physical before logical, Subject Areas before their
    # tables, and everything before the sources that map across them.
    passes = {
        "PhysicalTable": _parse_physical,
        "ComplexJoin": _parse_complex_join,
        "LogicalTable": _parse_logical,
        "PresentationCatalog": _parse_subject_area,
        "PresentationTable": _parse_presentation_table,
        "LogicalTableSource": _parse_table_source,
        "LogicalComplexJoin": _parse_bmm_join,
        "InitBlock": _parse_init_block,
        "Variable": _parse_variable,
        "Group": _parse_group,
        "PrivilegePackage": _parse_privilege_package,
        "ObjectPrivilege": _parse_object_privilege,
    }
    for wanted, handler in passes.items():
        for rpd_id, object_type, root in trees:
            if object_type != wanted:
                continue
            handler(rpd_id, root, index, estate)

    _count_mapped_sources(estate)
    _flag_time_series(estate)
    _build_lineage(estate)
    _collect_row_filters(estate)
    # After every pass, so the audit sees the reads all of them made.
    _audit_unread(trees, index, estate)
    # Last, so it sees every row every pass produced, including lineage.
    estate.check_identifier_uniqueness()

    for rpd_id, object_type, path in files:
        if object_type in _HANDLED:
            continue
        if object_type in _INDEX_ONLY:
            estate.count(rpd_id, object_type, "parsed")
            continue
        estate.record_unmodelled(rpd_id, object_type, path.name)

    return estate
