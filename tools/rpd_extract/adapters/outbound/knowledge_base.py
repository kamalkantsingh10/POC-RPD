"""Outbound adapter: write an Estate as the Knowledge Base.

The extractor is the sole writer of ``estate/knowledge-base/`` (AD-2). Every
table goes through the spreadsheet-safe writer, every row is sorted by its
identifier so re-runs are byte-identical (AD-6), and the manifest records what
produced the output and from what (AD-5).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from tools.rpd_extract.adapters.outbound.csv_writer import write_table
from tools.rpd_extract.core.model import Estate, Expression

VERSION = "0.2.0"

#: Columns that can carry expression text or identifier-like values. Declaring
#: them lets the writer guard values a spreadsheet would corrupt; an undeclared
#: guardable value raises, which is the intended loud failure.
_EXPR_COLUMNS = ("expr_text", "expr_text_desc", "expr_refs")

def _expr_cells(expression: Expression) -> list[str]:
    """All three forms, verbatim, in fixed order (AD-21)."""
    return [expression.text, expression.text_desc, " ".join(expression.refs)]


def _summary_rows(estate: Estate) -> list[list[str]]:
    """Modelled-proportion rows, one per population, per rpd-id."""
    seen: dict[str, int] = {}
    for (rpd_id, measure), count in estate.input_census.items():
        if measure == "files_seen":
            seen[rpd_id] = count
    rows = []
    for (rpd_id, measure), count in estate.input_census.items():
        total = seen.get(rpd_id, 0)
        percent = f"{round(100 * count / total)}%" if total else "n/a"
        rows.append([rpd_id, measure, str(count), str(total), percent])
    return rows


def _halves_rows(estate: Estate) -> list[list[str]]:
    """Which halves the Operator supplied, and whether that is a declared pair.

    Recorded because *"no dashboards"* and *"dashboards not extracted"* are
    different facts, and a reader holding the Knowledge Base cannot otherwise
    tell them apart. AD-22 makes pairing a **human declaration**, so what is
    recorded is the act — the Operator put both halves in one estate folder
    under one rpd-id — never an inference from matching Subject Area names.
    """
    rows = []
    for rpd_id in sorted(estate.halves_present):
        halves = estate.halves_present[rpd_id]
        rows.append([f"halves_present:{rpd_id}", " ".join(halves) or "none"])
        rows.append([
            f"pairing:{rpd_id}",
            "declared by the Operator: both halves supplied in one estate "
            "folder under one rpd-id (AD-22). Never inferred."
            if len(halves) > 1 else
            f"not paired: only the {halves[0]} half was supplied"
            if halves else "not paired: no half was supplied",
        ])
    return rows


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class NotAKnowledgeBase(ValueError):
    """Refused to clean a directory that this extractor did not write."""


def clean(out_dir: Path | str) -> list[str]:
    """Delete the Knowledge Base tables in ``out_dir`` before a fresh write.

    Refuses unless the directory is empty or already contains ``manifest.csv``.
    Without that check, ``--out ~/Documents --clean`` would delete every CSV in
    a real directory; the manifest is proof this extractor wrote here.

    Only ``*.csv`` is removed, and only at the top level. Anything else — a
    ``.gitignore``, a subdirectory — is left alone: AD-6 says re-running
    disturbs nothing else, and cleaning is still a re-run.
    """
    out_dir = Path(out_dir)
    if not out_dir.exists():
        return []

    contents = [p for p in out_dir.iterdir() if p.name != ".gitignore"]
    if contents and not (out_dir / "manifest.csv").exists():
        raise NotAKnowledgeBase(
            f"refusing to clean {out_dir}: it is not empty and has no manifest.csv, "
            f"so this extractor did not write it. Point --out at a Knowledge Base "
            f"directory, or at a new one."
        )

    removed = []
    for csv_file in sorted(out_dir.glob("*.csv")):
        csv_file.unlink()
        removed.append(csv_file.name)
    return removed


def write(
    estate: Estate,
    out_dir: Path | str,
    *,
    corpus_root: str,
    timestamp: str | None = None,
) -> list[str]:
    """Write every Knowledge Base table. Returns the table names written."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    def emit(name, header, rows, guard=()):
        write_table(out_dir / f"{name}.csv", header, rows, guard_columns=guard)
        written.append(name)

    emit(
        "physical_tables",
        ["row_id", "rpd_id", "container", "name", "table_type", "max_conn",
         "source_table_id"],
        sorted(
            [[t.row_id, t.rpd_id, t.container, t.name, t.table_type, t.max_conn,
              t.source_table_id]
             for t in estate.physical_tables]
        ),
        guard=("name", "container"),
    )

    # The SQL of an opaque view, or the database name of an ordinary table —
    # ``physical_tables.table_type`` says which. Verbatim, never parsed.
    emit(
        "physical_table_definitions",
        ["row_id", "rpd_id", "table_id", "database", "text"],
        sorted(
            [[d.row_id, d.rpd_id, d.table_id, d.database, d.text]
             for d in estate.physical_table_definitions]
        ),
        guard=("database", "text"),
    )

    emit(
        "physical_columns",
        ["row_id", "rpd_id", "table_id", "name", "data_type", "special_type",
         "precision", "nullable", "external_name"],
        sorted(
            [[c.row_id, c.rpd_id, c.table_id, c.name, c.data_type, c.special_type,
              c.precision, c.nullable, c.external_name]
             for c in estate.physical_columns]
        ),
        guard=("name", "external_name", "precision"),
    )

    emit(
        "physical_joins",
        ["row_id", "rpd_id", "kind", "name", "table1_id", "table2_id", "cardinality",
         *_EXPR_COLUMNS, "columns"],
        sorted(
            [[j.row_id, j.rpd_id, j.kind, j.name, j.table1_id, j.table2_id, j.cardinality,
              *_expr_cells(j.expression), " ".join(j.columns)]
             for j in estate.physical_joins]
        ),
        guard=("name", *_EXPR_COLUMNS),
    )

    emit(
        "logical_tables",
        ["row_id", "rpd_id", "business_model", "name", "source_count"],
        sorted(
            [[t.row_id, t.rpd_id, t.business_model, t.name, str(t.source_count)]
             for t in estate.logical_tables]
        ),
        guard=("name", "business_model"),
    )

    emit(
        "logical_columns",
        ["row_id", "rpd_id", "table_id", "name", "is_writeable", "is_measure",
         "source_count", "mapped_source_count", "time_series",
         "derived_expr_text", "derived_expr_text_desc", "derived_expr_refs",
         "mapping_expr_text", "mapping_expr_text_desc", "mapping_expr_refs"],
        sorted(
            [[c.row_id, c.rpd_id, c.table_id, c.name, c.is_writeable,
              "true" if c.is_measure else "false", str(c.source_count),
              str(c.mapped_source_count), " ".join(c.time_series),
              *_expr_cells(c.derived), *_expr_cells(c.mapping)]
             for c in estate.logical_columns]
        ),
        guard=("name", "derived_expr_text", "derived_expr_text_desc",
               "derived_expr_refs", "mapping_expr_text", "mapping_expr_text_desc",
               "mapping_expr_refs"),
    )

    emit(
        "aggregation_rules",
        ["row_id", "rpd_id", "logical_column_id", "name", "is_default", *_EXPR_COLUMNS],
        sorted(
            [[r.row_id, r.rpd_id, r.logical_column_id, r.name, r.is_default,
              *_expr_cells(r.expression)]
             for r in estate.aggregation_rules]
        ),
        guard=("name", *_EXPR_COLUMNS),
    )

    emit(
        "presentation_subject_areas",
        ["row_id", "rpd_id", "name", "business_model", "implicit_fact_column_id",
         "is_auto_aggregate", "aliases"],
        sorted(
            [[s.row_id, s.rpd_id, s.name, s.business_model, s.implicit_fact_column_id,
              s.is_auto_aggregate, " | ".join(s.aliases)]
             for s in estate.subject_areas]
        ),
        guard=("name", "business_model", "aliases"),
    )

    emit(
        "presentation_tables",
        ["row_id", "rpd_id", "subject_area_id", "name", "display_name", "aliases"],
        sorted(
            [[t.row_id, t.rpd_id, t.subject_area_id, t.name, t.display_name,
              " | ".join(t.aliases)]
             for t in estate.presentation_tables]
        ),
        guard=("name", "display_name", "aliases"),
    )

    emit(
        "presentation_columns",
        ["row_id", "rpd_id", "table_id", "name", "logical_column_id",
         "override_logical_name", "display_name"],
        sorted(
            [[c.row_id, c.rpd_id, c.table_id, c.name, c.logical_column_id,
              c.override_logical_name, c.display_name]
             for c in estate.presentation_columns]
        ),
        guard=("name", "display_name"),
    )

    emit(
        "presentation_hierarchies",
        ["row_id", "rpd_id", "table_id", "name", "dimension_id", "level_count",
         "display_column_id"],
        sorted(
            [[h.row_id, h.rpd_id, h.table_id, h.name, h.dimension_id,
              str(h.level_count), h.display_column_id]
             for h in estate.presentation_hierarchies]
        ),
        guard=("name",),
    )

    emit(
        "presentation_levels",
        ["row_id", "rpd_id", "hierarchy_id", "position", "name",
         "logical_level_id"],
        sorted(
            [[l.row_id, l.rpd_id, l.hierarchy_id, str(l.position), l.name,
              l.logical_level_id]
             for l in estate.presentation_levels]
        ),
        guard=("name",),
    )

    emit(
        "presentation_level_columns",
        ["row_id", "rpd_id", "level_id", "position", "presentation_column_id"],
        sorted(
            [[c.row_id, c.rpd_id, c.level_id, str(c.position),
              c.presentation_column_id]
             for c in estate.presentation_level_columns]
        ),
    )

    emit(
        "logical_dimensions",
        ["row_id", "rpd_id", "name", "business_model", "is_value_based",
         "is_ragged", "is_skipped", "default_root_level_id", "level_count"],
        sorted(
            [[d.row_id, d.rpd_id, d.name, d.business_model,
              "true" if d.is_value_based else "false",
              "true" if d.is_ragged else "false",
              "true" if d.is_skipped else "false",
              d.default_root_level_id, str(d.level_count)]
             for d in estate.logical_dimensions]
        ),
        guard=("name",),
    )

    emit(
        "logical_levels",
        ["row_id", "rpd_id", "dimension_id", "position", "name", "member_count",
         "is_grand_total", "drill_key_column_id"],
        sorted(
            [[l.row_id, l.rpd_id, l.dimension_id, str(l.position), l.name,
              l.member_count, "true" if l.is_grand_total else "false",
              l.drill_key_column_id]
             for l in estate.logical_levels]
        ),
        guard=("name", "member_count"),
    )

    emit(
        "logical_table_sources",
        ["row_id", "rpd_id", "logical_table_id", "name", "is_active", "priority",
         "fragment_text", "fragment_text_desc", "fragment_refs",
         "where_text", "where_text_desc", "where_refs",
         "group_by_text", "group_by_text_desc", "group_by_refs"],
        sorted(
            [[s.row_id, s.rpd_id, s.logical_table_id, s.name, s.is_active, s.priority,
              *_expr_cells(s.fragment), *_expr_cells(s.where_clause),
              *_expr_cells(s.group_by)]
             for s in estate.logical_table_sources]
        ),
        guard=("name", "fragment_text", "fragment_text_desc", "fragment_refs",
               "where_text", "where_text_desc", "where_refs",
               "group_by_text", "group_by_text_desc", "group_by_refs"),
    )

    emit(
        "lts_column_map",
        ["row_id", "rpd_id", "source_id", "logical_column_id", "physical_column_id",
         "logical_expr_text", "logical_expr_text_desc", "logical_expr_refs",
         "physical_expr_text", "physical_expr_text_desc", "physical_expr_refs"],
        sorted(
            [[m.row_id, m.rpd_id, m.source_id, m.logical_column_id, m.physical_column_id,
              *_expr_cells(m.logical_expression), *_expr_cells(m.physical_expression)]
             for m in estate.column_mappings]
        ),
        guard=("logical_expr_text", "logical_expr_text_desc", "logical_expr_refs",
               "physical_expr_text", "physical_expr_text_desc", "physical_expr_refs"),
    )

    emit(
        "lineage",
        ["row_id", "rpd_id", "presentation_column_id", "logical_column_id",
         "source_id", "physical_table_id", "physical_column_id"],
        sorted(
            [[r.row_id, r.rpd_id, r.presentation_column_id, r.logical_column_id,
              r.source_id, r.physical_table_id, r.physical_column_id]
             for r in estate.lineage]
        ),
    )

    emit(
        "bmm_joins",
        ["row_id", "rpd_id", "name", "join_type", "table1_id", "multiplicity1",
         "is_aggregate1", "table2_id", "multiplicity2", "is_aggregate2"],
        sorted(
            [[j.row_id, j.rpd_id, j.name, j.join_type, j.table1_id, j.multiplicity1,
              j.is_aggregate1, j.table2_id, j.multiplicity2, j.is_aggregate2]
             for j in estate.bmm_joins]
        ),
        guard=("name",),
    )

    emit(
        "variables",
        ["row_id", "rpd_id", "name", "is_session", "init_block_id", "security_mask",
         "redacted", *_EXPR_COLUMNS],
        sorted(
            [[v.row_id, v.rpd_id, v.name, v.is_session, v.init_block_id, v.security_mask,
              "true" if v.redacted else "false", *_expr_cells(v.expression)]
             for v in estate.variables]
        ),
        guard=("name", *_EXPR_COLUMNS),
    )

    emit(
        "init_blocks",
        ["row_id", "rpd_id", "name", "refresh_period", "is_session", "is_enabled",
         "init_string"],
        sorted(
            [[b.row_id, b.rpd_id, b.name, b.refresh_period, b.is_session, b.is_enabled,
              b.init_string]
             for b in estate.init_blocks]
        ),
        guard=("name", "init_string"),
    )

    emit(
        "security_rls",
        ["row_id", "rpd_id", "kind", "role", "subject_id", "detail", *_EXPR_COLUMNS],
        sorted(
            [[r.row_id, r.rpd_id, r.kind, r.role, r.subject_id, r.detail,
              *_expr_cells(r.expression)]
             for r in estate.security_rules]
        ),
        guard=("role", "detail", *_EXPR_COLUMNS),
    )

    # ------------------------------------------------------------ Web Catalog

    emit(
        "dashboards",
        ["row_id", "rpd_id", "name", "catalog_path", "xml_version", "page_count"],
        sorted(
            [[d.row_id, d.rpd_id, d.name, d.catalog_path, d.xml_version,
              str(d.page_count)]
             for d in estate.dashboards]
        ),
        guard=("name", "catalog_path"),
    )

    emit(
        "dashboard_pages",
        ["row_id", "rpd_id", "dashboard_id", "position", "name", "catalog_path",
         "xml_version"],
        sorted(
            [[p.row_id, p.rpd_id, p.dashboard_id, str(p.position), p.name,
              p.catalog_path, p.xml_version]
             for p in estate.dashboard_pages]
        ),
        guard=("name", "catalog_path"),
    )

    emit(
        "dashboard_contents",
        ["row_id", "rpd_id", "container_id", "position", "element", "reference",
         "resolution", "target_id", "target_kind", "detail"],
        sorted(
            [[c.row_id, c.rpd_id, c.container_id, str(c.position), c.element,
              c.reference, c.resolution, c.target_id, c.target_kind, c.detail]
             for c in estate.dashboard_contents]
        ),
        guard=("element", "reference", "detail"),
    )

    emit(
        "analyses",
        ["row_id", "rpd_id", "name", "catalog_path", "xml_version",
         "criteria_count", "column_count"],
        sorted(
            [[a.row_id, a.rpd_id, a.name, a.catalog_path, a.xml_version,
              str(a.criteria_count), str(a.column_count)]
             for a in estate.analyses]
        ),
        guard=("name", "catalog_path"),
    )

    emit(
        "analysis_criteria",
        ["row_id", "rpd_id", "analysis_id", "position", "subject_area"],
        sorted(
            [[c.row_id, c.rpd_id, c.analysis_id, str(c.position), c.subject_area]
             for c in estate.analysis_criteria]
        ),
        guard=("subject_area",),
    )

    emit(
        "analysis_columns",
        ["row_id", "rpd_id", "analysis_id", "criteria_id", "position",
         "column_id", "heading", "table_heading", "formula_construct",
         "formula_type", "formula", "is_computation", "uses_eval"],
        sorted(
            [[c.row_id, c.rpd_id, c.analysis_id, c.criteria_id, str(c.position),
              c.column_id, c.heading, c.table_heading, c.formula_construct,
              c.formula_type, c.formula,
              "true" if c.is_computation else "false",
              "true" if c.uses_eval else "false"]
             for c in estate.analysis_columns]
        ),
        guard=("heading", "table_heading", "formula_construct", "formula_type",
               "formula", "column_id"),
    )

    emit(
        "analysis_views",
        ["row_id", "rpd_id", "analysis_id", "position", "view_type", "name",
         "references_views", "bound_column_count", "display_type",
         "display_subtype"],
        sorted(
            [[v.row_id, v.rpd_id, v.analysis_id, str(v.position), v.view_type,
              v.name, str(v.references_views), str(v.bound_column_count),
              v.display_type, v.display_subtype]
             for v in estate.analysis_views]
        ),
        guard=("view_type", "name", "display_type", "display_subtype"),
    )

    emit(
        "report_lineage",
        ["row_id", "rpd_id", "analysis_id", "criteria_id", "analysis_column_id",
         "subject_area", "subject_area_id", "reference_text",
         "presentation_column_id", "resolution", "logical_column_id",
         "physical_column_id", "source_state"],
        sorted(
            [[r.row_id, r.rpd_id, r.analysis_id, r.criteria_id,
              r.analysis_column_id, r.subject_area, r.subject_area_id,
              r.reference_text, r.presentation_column_id, r.resolution,
              r.logical_column_id, r.physical_column_id, r.source_state]
             for r in estate.report_lineage]
        ),
        guard=("subject_area", "reference_text"),
    )

    emit(
        "analysis_filters",
        ["row_id", "rpd_id", "scope", "owner_id", "position", "op", "expr_type",
         "expr_text", "reference", "target_id", "resolution", "uses_eval"],
        sorted(
            [[f.row_id, f.rpd_id, f.scope, f.owner_id, str(f.position), f.op,
              f.expr_type, f.expr_text, f.reference, f.target_id, f.resolution,
              "true" if f.uses_eval else "false"]
             for f in estate.analysis_filters]
        ),
        guard=("op", "expr_type", "expr_text", "reference"),
    )

    emit(
        "analysis_prompts",
        ["row_id", "rpd_id", "analysis_id", "position", "prompt_type",
         "column_type", "column_formula", "set_variable", "operator",
         "ui_control"],
        sorted(
            [[p.row_id, p.rpd_id, p.analysis_id, str(p.position), p.prompt_type,
              p.column_type, p.column_formula, p.set_variable, p.operator,
              p.ui_control]
             for p in estate.analysis_prompts]
        ),
        guard=("prompt_type", "column_type", "column_formula", "set_variable",
               "operator", "ui_control"),
    )

    emit(
        "saved_filters",
        ["row_id", "rpd_id", "name", "catalog_path", "xml_version", "op",
         "expr_type", "expr_text", "uses_eval"],
        sorted(
            [[f.row_id, f.rpd_id, f.name, f.catalog_path, f.xml_version, f.op,
              f.expr_type, f.expr_text, "true" if f.uses_eval else "false"]
             for f in estate.saved_filters]
        ),
        guard=("name", "catalog_path", "op", "expr_type", "expr_text"),
    )

    # Two files, deliberately. "We have not built this" and "this went wrong"
    # are different questions, and conflating them buries the second in the
    # first — 200 unmodelled types would hide 31 broken references.
    emit(
        "unparsed",
        ["rpd_id", "kind", "object_type", "detail", "occurrences"],
        sorted(
            [[u.rpd_id, u.kind, u.object_type, u.detail, str(u.occurrences)]
             for u in estate.unparsed]
        ),
        # ``object_type`` is deliberately NOT guarded. Catalog object types are
        # ``{namespace}local`` names, which no spreadsheet reinterprets, so
        # declaring a guard here would add a companion column to every existing
        # Knowledge Base for a value that can never need one. A type that did
        # need guarding raises loudly, which is the intended failure.
        guard=("detail",),
    )

    emit(
        "errors",
        ["rpd_id", "kind", "source_id", "object_type", "reason"],
        sorted(
            [[e.rpd_id, e.kind, e.source_id, e.object_type, e.reason]
             for e in estate.errors]
        ),
        guard=("source_id", "reason"),
    )

    # ``layer`` since Epic 2: a Knowledge Base now holds two stores, and a
    # coverage table that cannot tell an RPD object type from a catalog one
    # makes the proportion figures below unreadable.
    emit(
        "coverage",
        ["rpd_id", "layer", "object_type", "parsed", "skipped"],
        sorted(
            [[rpd_id, layer, object_type,
              str(counts["parsed"]), str(counts["skipped"])]
             for (rpd_id, layer, object_type), counts in estate.coverage.items()]
        ),
        guard=("object_type",),
    )

    # Absence is a value in its own right, written as "(none)" rather than left
    # empty: 38% of parseable roots declare no version, and a spread reporting
    # only declared values describes 62% of an estate while reading as though it
    # describes all of it.
    emit(
        "catalog_versions",
        ["rpd_id", "object_type", "xml_version", "objects"],
        sorted(
            [[rpd_id, object_type, version or "(none)", str(count)]
             for (rpd_id, object_type, version), count in
             estate.catalog_versions.items()]
        ),
        guard=("object_type",),
    )

    # What proportion of the input the extraction models, in whole numbers a
    # reader can check by adding them up. The failure this exists to prevent is
    # specific and quiet: counting what the adapter modelled, dividing by what
    # the adapter attempted, and reporting 100% — both numbers true, and 2521
    # files unmentioned.
    emit(
        "coverage_summary",
        ["rpd_id", "measure", "count", "of_files_seen", "percent"],
        sorted(_summary_rows(estate)),
        guard=("percent",),
    )

    stamp = timestamp or _timestamp()
    emit(
        "manifest",
        ["key", "value"],
        [
            ["extractor_version", VERSION],
            ["extracted_at", stamp],
            ["corpus_root", corpus_root],
            ["rpd_ids", " ".join(estate.rpd_ids)],
            *_halves_rows(estate),
            ["tables", " ".join(sorted(written))],
        ],
        guard=("value",),
    )

    return written
