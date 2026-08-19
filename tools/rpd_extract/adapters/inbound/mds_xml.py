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
    """Verbatim text. No stripping — FR-2 forbids reformatting anywhere."""
    if element is None or element.text is None:
        return ""
    return element.text


@dataclass(frozen=True)
class _Indexed:
    """One addressable object, keyed by its mdsid. Adapter-internal only."""

    rpd_id: str
    object_type: str
    tag: str
    name: str
    owner_mdsid: str


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


def _build_index(files: list[tuple[str, str, Path]], estate: Estate) -> _Index:
    index = _Index()
    for rpd_id, object_type, path in files:
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            estate.record_error(rpd_id, "malformed_xml", path.name, object_type, str(exc))
            continue
        stack = [(root, "")]
        while stack:
            element, owner = stack.pop()
            mdsid = element.attrib.get("mdsid", "")
            if mdsid:
                index.add(
                    mdsid,
                    _Indexed(
                        rpd_id=rpd_id,
                        object_type=object_type,
                        tag=_tag(element),
                        name=element.attrib.get("name", ""),
                        owner_mdsid=owner,
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


def _first_child(element: ET.Element, name: str) -> ET.Element | None:
    for child in element:
        if _tag(child) == name:
            return child
    return None


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if _tag(child) == name]


def _container_name(element: ET.Element, index: _Index) -> str:
    """Resolve ``@containerRef`` to the owning schema or database name."""
    _, mdsid = index.resolve_ref(element.attrib.get("containerRef", ""))
    entry = index.get(mdsid) if mdsid else None
    return entry.name if entry else ""


def _parse_physical(rpd_id: str, root: ET.Element, index: _Index, estate: Estate) -> None:
    name = root.attrib.get("name", "")
    container = _container_name(root, index)
    if not name or not container:
        estate.record_error(
            rpd_id, "missing_name", root.attrib.get("mdsid", "?"), "PhysicalTable",
            "table name or container could not be resolved",
        )
        return

    table_id = ids.make_id(rpd_id, ids.PHYSICAL, container, name)
    index.bind(root.attrib.get("mdsid", ""), table_id)
    estate.physical_tables.append(
        PhysicalTable(
            row_id=table_id,
            rpd_id=rpd_id,
            container=container,
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
        column_id = ids.make_id(rpd_id, ids.PHYSICAL, container, name, column_name)
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
                row_id=ids.make_id(rpd_id, ids.PHYSICAL, container, name, fk_name or "fk"),
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



#: What each parser above actually consumes, declared per object type as
#: ``Tag@attribute`` and bare ``Tag`` for child elements.
#:
#: This is a declaration, so it can drift from the code. It drifts in the SAFE
#: direction: forgetting to declare something we do read reports a phantom gap
#: (noisy), while the dangerous case — content silently discarded — is exactly
#: what the audit catches. Over-reporting is the correct bias here.
_CONSUMED: dict[str, set[str]] = {
    "PhysicalTable": {
        "PhysicalTable@mdsid", "PhysicalTable@name", "PhysicalTable@type",
        "PhysicalTable@maxConn", "PhysicalTable@containerRef",
        "PhysicalColumn", "PhysicalColumn@mdsid", "PhysicalColumn@name",
        "PhysicalColumn@dataType", "PhysicalColumn@specialType",
        "PhysicalColumn@precision", "PhysicalColumn@nullable", "PhysicalColumn@extName",
        "PhysicalForeignKey", "PhysicalForeignKey@mdsid", "PhysicalForeignKey@name",
        "RefColumns", "RefColumn", "RefColumn@columnRef", "RefColumn@refId",
    },
    "ComplexJoin": {
        "ComplexJoin@mdsid", "ComplexJoin@name", "ComplexJoin@cardinality",
        "ComplexJoin@table1Ref", "ComplexJoin@table2Ref",
        "Expr", "Expr@mdsid", "Expr@name", "ExprText", "ExprTextDesc",
        "ObjectRefList", "RefObject", "RefObject@objectRef", "RefObject@refId",
        "RefObject@objectTypeId",
    },
    "LogicalTable": {
        "LogicalTable@mdsid", "LogicalTable@name", "LogicalTable@subjectAreaRef",
        "LogicalColumn", "LogicalColumn@mdsid", "LogicalColumn@name",
        "LogicalColumn@isWriteable",
        "AttrDefn", "AttrDefn@mdsid", "AttrDefn@name",
        "MeasureDefn", "MeasureDefn@mdsid", "MeasureDefn@name",
        "AggrRule", "AggrRule@mdsid", "AggrRule@name", "AggrRule@isDefault",
        "Expr", "Expr@mdsid", "Expr@name", "ExprText", "ExprTextDesc",
        "ObjectRefList", "RefObject", "RefObject@objectRef", "RefObject@refId",
        "RefObject@objectTypeId",
        "RefTableSources", "RefLogicalTableSource",
        "RefLogicalTableSource@logicalTableSourceRef", "RefLogicalTableSource@refId",
    },
    "LogicalTableSource": {
        "LogicalTableSource@mdsid", "LogicalTableSource@name",
        "LogicalTableSource@isActive", "LogicalTableSource@logicalTableRef",
        "LogicalTableSource@priorityGroup",
        "FragmentContent", "FragmentContent@mdsid", "FragmentContent@name",
        "WhereClause", "WhereClause@mdsid", "WhereClause@name",
        "GroupBy", "GroupBy@mdsid", "GroupBy@name",
        "ColumnMapping", "ColumnMapping@mdsid", "ColumnMapping@name",
        "LogicalColumnExpr", "LogicalColumnExpr@mdsid", "LogicalColumnExpr@name",
        "Expr", "Expr@mdsid", "Expr@name", "ExprText", "ExprTextDesc",
        "ObjectRefList", "RefObject", "RefObject@objectRef", "RefObject@refId",
        "RefObject@objectTypeId",
    },
    "PresentationCatalog": {
        "PresentationCatalog@mdsid", "PresentationCatalog@name",
        "PresentationCatalog@subjectAreaRef", "PresentationCatalog@isAutoAggr",
        "PresentationCatalog@defaultFactColumnRef",
        "Alias", "Alias@name",
        "RefTables", "RefPresentationTable", "RefPresentationTable@presentationTableRef",
        "RefPresentationTable@refId",
    },
    "PresentationTable": {
        "PresentationTable@mdsid", "PresentationTable@name",
        "PresentationTable@containerRef", "PresentationTable@dispName",
        "PresentationColumn", "PresentationColumn@mdsid", "PresentationColumn@name",
        "PresentationColumn@logicalColumnRef",
        "PresentationColumn@overrideLogicalName", "PresentationColumn@dispName",
        "Alias", "Alias@name",
    },
    "LogicalComplexJoin": {
        "LogicalComplexJoin@mdsid", "LogicalComplexJoin@name",
        "LogicalComplexJoin@type", "LogicalComplexJoin@logicalTable1Ref",
        "LogicalComplexJoin@multiplicity1", "LogicalComplexJoin@isAggregate1",
        "LogicalComplexJoin@logicalTable2Ref", "LogicalComplexJoin@multiplicity2",
        "LogicalComplexJoin@isAggregate2",
    },
    "Variable": {
        "Variable@mdsid", "Variable@name", "Variable@isSessionVar",
        "Variable@initBlockRef", "Variable@securityMask",
        "Expr", "Expr@mdsid", "Expr@name", "ExprText", "ExprTextDesc",
        "ObjectRefList", "RefObject", "RefObject@objectRef", "RefObject@refId",
        "RefObject@objectTypeId",
    },
    "InitBlock": {
        "InitBlock@mdsid", "InitBlock@name", "InitBlock@refreshPeriod",
        "InitBlock@isSessionVar", "InitBlock@isEnabled", "InitString",
    },
    "Group": {"Group@mdsid", "Group@name"},
    "PrivilegePackage": {
        "PrivilegePackage@mdsid", "PrivilegePackage@name",
        "PrivilegePackage@roleRef", "PrivilegePackage@userRef",
        "QueryPrivilegeMapping", "QueryPrivilegeMapping@databaseRef",
        "QueryPrivilegeMapping@queryPrivilegeRef",
    },
    "ObjectPrivilege": {
        "ObjectPrivilege@mdsid", "ObjectPrivilege@name", "ObjectPrivilege@type",
        "ObjectPrivilege@privilegePackageRef",
        "RefObjects", "RefObject", "RefObject@objectRef", "RefObject@refId",
        "RefObject@objectTypeId",
    },
}


def _audit_unread(
    files: list[tuple[str, str, Path]], estate: Estate
) -> None:
    """Report source content present on parsed objects but never consumed.

    Whole-object honesty is not enough. An object can parse "successfully"
    while attributes and child elements on it are discarded without a word —
    which is precisely the silent omission NFR7 names as the primary failure
    mode, one level below where AD-3 was watching.

    Doubles as a format-drift detector: a repository from a different OBIEE
    version carrying new attributes announces itself here instead of being
    quietly dropped.
    """
    present: dict[tuple[str, str], collections.Counter] = {}
    for rpd_id, object_type, path in files:
        if object_type not in _CONSUMED:
            continue  # unmodelled types are already reported whole
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue  # already reported as an error
        counter = present.setdefault((rpd_id, object_type), collections.Counter())
        for element in root.iter():
            tag = _tag(element)
            counter[tag] += 1
            for attribute in element.attrib:
                counter[f"{tag}@{attribute}"] += 1

    for (rpd_id, object_type), counter in sorted(present.items()):
        consumed = set(_CONSUMED[object_type])
        # Declaring `Tag@attr` implies the element itself is consumed — we read
        # its attributes, so it is not an unread element. Without this the root
        # object of every file reports as a gap, which is noise, not signal.
        consumed |= {item.split("@")[0] for item in consumed if "@" in item}
        for item, occurrences in sorted(counter.items()):
            if item in consumed:
                continue
            kind = "unread_attribute" if "@" in item else "unread_element"
            estate.record_gap(rpd_id, kind, object_type, item, occurrences)


#: Object types this adapter models today. Everything else is reported as an
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
    index = _build_index(files, estate)

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
        for rpd_id, object_type, path in files:
            if object_type != wanted:
                continue
            try:
                root = ET.parse(path).getroot()
            except ET.ParseError as exc:
                estate.record_error(rpd_id, "malformed_xml", path.name, object_type, str(exc))
                continue
            handler(rpd_id, root, index, estate)

    _count_mapped_sources(estate)
    _flag_time_series(estate)
    _build_lineage(estate)
    _collect_row_filters(estate)
    _audit_unread(files, estate)

    for rpd_id, object_type, path in files:
        if object_type in _HANDLED:
            continue
        if object_type in _INDEX_ONLY:
            estate.count(rpd_id, object_type, "parsed")
            continue
        estate.record_unmodelled(rpd_id, object_type, path.name)

    return estate
