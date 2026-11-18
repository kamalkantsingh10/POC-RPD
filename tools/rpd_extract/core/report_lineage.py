"""Trace an Analysis column toward the semantic layer — FR-7.

A post-pass over a merged Estate, not an adapter. Everything it reads was
already extracted: the catalog contributed ``analysis_criteria.subject_area``
and ``analysis_columns.formula`` verbatim, the repository contributed the
presentation layer and ``lineage``. The join is arithmetic over rows, so this
pass cannot invent a fact an adapter did not record.

**It resolves by name, because a name is all the catalog stores.** OBIEE writes
``"A - Sample Sales"`` into an Analysis and nothing more — no identifier, no
GUID. Matching names across two halves is therefore the only mechanism
available, and AD-22 is why it happens here rather than in an adapter: pairing
is the Operator's declaration, and this pass only acts on halves they put in one
estate folder.

Standard library only (NFR13).
"""

from __future__ import annotations

import re

from tools.rpd_extract.core import identifiers as ids
from tools.rpd_extract.core.model import (
    COMPUTED_NOT_SOURCED,
    Estate,
    NOT_A_COLUMN_REFERENCE,
    OUTSIDE_SEMANTIC_MODEL,
    RESOLVED_CASE,
    RESOLVED_EXACT,
    RESOLVED_NONE,
    ReportLineageRow,
    SOURCED,
)

#: A formula that is nothing but a reference: ``"Table"."Column"``. Anything
#: else is a computation whose column references sit inside an expression this
#: pass deliberately does not parse (AC 2.9-9).
_BARE = re.compile(r'^"([^"]+)"\."([^"]+)"$')

#: A Visual Analyzer uploaded dataset. Named here rather than treated as an
#: unresolved reference because the data was never in the repository at all.
_XSA = re.compile(r"^XSA\(")


def _index_presentation(estate: Estate) -> dict:
    """(rpd_id, subject area, table, column) -> presentation column identifier."""
    areas = {a.row_id: a.name for a in estate.subject_areas}
    tables = {t.row_id: (areas.get(t.subject_area_id, ""), t.name)
              for t in estate.presentation_tables}
    index = {}
    for column in estate.presentation_columns:
        area, table = tables.get(column.table_id, ("", ""))
        if area:
            index[(column.rpd_id, area, table, column.name)] = column.row_id
    return index


def resolve(estate: Estate) -> None:
    """Append one ``report_lineage`` row per Analysis column. Idempotent."""
    estate.report_lineage.clear()
    if not estate.analysis_columns:
        return

    columns = _index_presentation(estate)
    folded = {(r, a.lower(), t.lower(), c.lower()): v
              for (r, a, t, c), v in columns.items()}
    areas = {(a.rpd_id, a.name): a.row_id for a in estate.subject_areas}
    areas_folded = {(r, n.lower()): v for (r, n), v in areas.items()}
    criteria = {c.row_id: c for c in estate.analysis_criteria}
    lineage = {row.presentation_column_id: row for row in estate.lineage}

    for column in estate.analysis_columns:
        block = criteria.get(column.criteria_id)
        # Quotes are the catalog's own, and stripping them is a normalisation,
        # not a repair — the verbatim value stays in analysis_criteria.
        stated = block.subject_area if block else ""
        area_name = stated.strip('"')
        area_id = areas.get((column.rpd_id, area_name), "")
        if not area_id:
            area_id = areas_folded.get((column.rpd_id, area_name.lower()), "")

        formula = column.formula.strip()
        match = _BARE.match(formula)
        if not formula or (not match and _XSA.match(formula)):
            resolution = OUTSIDE_SEMANTIC_MODEL if formula else NOT_A_COLUMN_REFERENCE
        elif not match:
            resolution = NOT_A_COLUMN_REFERENCE
        else:
            resolution = RESOLVED_NONE

        presentation_id = ""
        if match and area_name:
            key = (column.rpd_id, area_name, match.group(1), match.group(2))
            presentation_id = columns.get(key, "")
            if presentation_id:
                resolution = RESOLVED_EXACT
            else:
                presentation_id = folded.get(
                    (column.rpd_id, area_name.lower(), match.group(1).lower(),
                     match.group(2).lower()), ""
                )
                if presentation_id:
                    resolution = RESOLVED_CASE

        logical_id = physical_id = source_state = ""
        if presentation_id:
            row = lineage.get(presentation_id)
            if row is not None:
                logical_id = row.logical_column_id
                physical_id = row.physical_column_id
                source_state = SOURCED
            else:
                # Resolved, but calculated in the BMM rather than stored. An
                # empty physical column here is a fact about the metric.
                source_state = COMPUTED_NOT_SOURCED

        estate.report_lineage.append(
            ReportLineageRow(
                # Built from the column's own path rather than by nesting its
                # identifier: an identifier already contains "::" separators,
                # and embedding one inside another is not parseable back out.
                row_id=ids.make_id(
                    column.rpd_id, ids.CATALOG,
                    f"{ids.parse_id(column.row_id)[2]}#lineage",
                ),
                rpd_id=column.rpd_id,
                analysis_id=column.analysis_id,
                criteria_id=column.criteria_id,
                analysis_column_id=column.row_id,
                subject_area=stated,
                reference_text=column.formula,
                resolution=resolution,
                subject_area_id=area_id,
                presentation_column_id=presentation_id,
                logical_column_id=logical_id,
                physical_column_id=physical_id,
                source_state=source_state,
            )
        )
