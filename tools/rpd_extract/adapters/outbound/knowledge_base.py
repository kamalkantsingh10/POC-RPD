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

VERSION = "0.1.0"

#: Columns that can carry expression text or identifier-like values. Declaring
#: them lets the writer guard values a spreadsheet would corrupt; an undeclared
#: guardable value raises, which is the intended loud failure.
_EXPR_COLUMNS = ("expr_text", "expr_text_desc", "expr_refs")

#: Tables that report ON the extraction rather than carrying estate content.
#: Profiling them would be meaningless — "how populated is errors.csv" answers
#: nothing — and `completeness` profiling itself would be circular.
REPORT_TABLES = frozenset(
    {"coverage", "errors", "unparsed", "manifest", "completeness"}
)

#: Columns whose blankness carries meaning and must not be read as a gap. Each
#: is a *deliberate* empty: the source records nothing, and the model says so
#: rather than inventing a default. Named here so the completeness report can
#: say "expected" instead of leaving a reader to guess.
_MEANINGFUL_BLANKS = {
    ("logical_table_sources", "priority"): (
        "empty means the source records no priority — never 'lowest'. "
        "Inferring an order from document position would silently repoint a measure"
    ),
    ("presentation_subject_areas", "implicit_fact_column_id"): (
        "empty means the Subject Area declares no defaultFactColumnRef"
    ),
}

COMPLETE = "complete"
PARTIAL = "partly_populated"
NEVER = "never_populated"
NO_ROWS = "no_rows"


def _profile(
    profiled: list[tuple[str, list[str], list[list[str]]]]
) -> list[list[str]]:
    """Per column, how much of it is actually there — and what to do about it.

    A dev reading the Knowledge Base cannot tell a blank cell that means "OBIEE
    never set this" from one that means "we failed to read it". Both are empty
    strings. This report is the difference between data that is good — which it
    measurably is — and data a dev can *know* is good without re-deriving it by
    hand from the source corpus.

    Split by ``rpd_id`` where the table has one: a column can be complete in one
    repository and absent in another, and an estate-wide average would hide it.
    """
    out: list[list[str]] = []
    for name, header, rows in profiled:
        rpd_at = header.index("rpd_id") if "rpd_id" in header else None
        # Where a table holds more than one kind of row, profile each kind
        # separately. A foreign key carries no join expression and a complex
        # join does; averaged together the column reads as "never populated",
        # which a dev would fairly take for a failure to read it.
        kind_at = header.index("kind") if "kind" in header else None
        groups: dict[tuple[str, str], list[list[str]]] = {}
        for row in rows:
            key = (
                row[rpd_at] if rpd_at is not None else "",
                row[kind_at] if kind_at is not None else "",
            )
            groups.setdefault(key, []).append(row)
        # A table that produced no rows must still appear. Omitting it makes an
        # empty table indistinguishable from one nobody profiled, which is the
        # silence this report exists to remove.
        if not groups:
            groups[("", "")] = []
        for (rpd_id, kind), group in sorted(groups.items()):
            for index, column in enumerate(header):
                if column in ("rpd_id", "kind") or column.endswith("_guarded"):
                    continue  # the guard flags describe the CSV, not the estate
                filled = sum(1 for row in group if index < len(row) and row[index].strip())
                total = len(group)
                blank = total - filled
                if not total:
                    verdict, note = NO_ROWS, "no rows extracted for this rpd-id"
                elif filled == total:
                    verdict, note = COMPLETE, "every row carries a value"
                elif filled:
                    verdict, note = PARTIAL, "blank where the source object sets nothing"
                else:
                    verdict, note = NEVER, (
                        "NO row in this estate carries a value. Confirm against "
                        "unparsed.csv whether the source has it and we do not read it"
                    )
                expected = _MEANINGFUL_BLANKS.get((name, column))
                if expected and verdict in (PARTIAL, NEVER):
                    note = f"expected: {expected}"
                out.append([
                    rpd_id, name, kind, column, str(total), str(filled), str(blank),
                    f"{100 * filled / total:.1f}" if total else "0.0",
                    verdict, note,
                ])

    # Where a column is empty for one kind and populated for another, say so —
    # and stop there. It is tempting to call that "not applicable" and clear the
    # row, and for `physical_joins` that is right: a foreign key has no join
    # expression. For `security_rls` it is wrong: `row_filter` rows carry no
    # role, and FR-4 requires row-level security filters per application role,
    # so that blank is a genuine shortfall. Nothing here can tell the two apart
    # without knowing what the column means, and a rule that guesses would bury
    # the second case under a reassuring note. State the fact; let a human judge.
    populated_for = {
        (row[1], row[3]): row[2] for row in out if int(row[5]) and row[2]
    }
    for row in out:
        table, kind, column, verdict = row[1], row[2], row[3], row[8]
        other = populated_for.get((table, column))
        if verdict == NEVER and other and other != kind:
            row[9] = (
                f"empty for kind '{kind}' but populated for kind '{other}'. "
                f"Either it does not apply to this kind, or it is missing — "
                f"the extractor cannot tell which"
            )
    return sorted(out)


def _expr_cells(expression: Expression) -> list[str]:
    """All three forms, verbatim, in fixed order (AD-21)."""
    return [expression.text, expression.text_desc, " ".join(expression.refs)]


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
    profiled: list[tuple[str, list[str], list[list[str]]]] = []

    def emit(name, header, rows, guard=()):
        write_table(out_dir / f"{name}.csv", header, rows, guard_columns=guard)
        written.append(name)
        # Every estate table profiles itself. Capturing here rather than from a
        # declared list means a table added later is covered without anyone
        # remembering to add it.
        if name not in REPORT_TABLES:
            profiled.append((name, list(header), rows))

    emit(
        "physical_tables",
        ["row_id", "rpd_id", "container", "name", "table_type", "max_conn"],
        sorted(
            [[t.row_id, t.rpd_id, t.container, t.name, t.table_type, t.max_conn]
             for t in estate.physical_tables]
        ),
        guard=("name", "container"),
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

    # Two files, deliberately. "We have not built this" and "this went wrong"
    # are different questions, and conflating them buries the second in the
    # first — 200 unmodelled types would hide 31 broken references.
    emit(
        "unparsed",
        ["rpd_id", "kind", "object_type", "detail", "occurrences", "assessment"],
        sorted(
            [[u.rpd_id, u.kind, u.object_type, u.detail, str(u.occurrences),
              u.assessment]
             for u in estate.unparsed]
        ),
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

    emit(
        "coverage",
        ["rpd_id", "object_type", "parsed", "skipped"],
        sorted(
            [[rpd_id, object_type, str(counts["parsed"]), str(counts["skipped"])]
             for (rpd_id, object_type), counts in estate.coverage.items()]
        ),
    )

    emit(
        "completeness",
        ["rpd_id", "table", "kind", "column", "rows", "populated", "blank",
         "populated_pct", "verdict", "what_to_check"],
        _profile(profiled),
        guard=("what_to_check",),
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
            ["tables", " ".join(sorted(written))],
        ],
        guard=("value",),
    )

    return written
