"""Cut one Subject Area out of the Knowledge Base.

The Knowledge Base is ~474k tokens; one Subject Area is 1k–40k. That difference
is what makes an agent skill affordable at all, and AD-12 requires it: a skill
whose task cannot fit one context window must partition its input, "which is why
the Knowledge Base is selectively-readable tables rather than one document".

The traversal is deterministic, so it belongs here rather than in a prompt. An
LLM following foreign keys across 1543 rows will occasionally get one wrong, and
a wrong join produces plausible wrong lineage — the precise failure this product
exists to prevent, reintroduced at the last step.

Reads the table list from ``manifest.csv``, never from a directory listing, so a
stale file left by an older extractor is invisible here.

Standard library only (NFR13).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.rpd_extract.adapters.outbound.csv_writer import read_table, write_table

#: Columns that may carry expression text or identifier-like values and so must
#: be re-guarded on write. Mirrors the Knowledge Base writer.
_GUARDABLE = (
    "name", "detail", "reason", "container", "business_model", "display_name",
    "aliases", "external_name", "precision", "init_string", "role", "source_id",
)


class SliceError(ValueError):
    """The Knowledge Base or the requested Subject Area could not be used."""


def _load(kb: Path) -> dict[str, tuple[list[str], list[list[str]]]]:
    manifest = kb / "manifest.csv"
    if not manifest.is_file():
        raise SliceError(
            f"{kb} has no manifest.csv, so it is not a Knowledge Base. Run the "
            f"extractor first: python3 -m tools.rpd_extract.cli --corpus … --out {kb}"
        )
    _, rows = read_table(manifest)
    listed = dict((r[0], r[1]) for r in rows).get("tables", "").split()

    tables: dict[str, tuple[list[str], list[list[str]]]] = {}
    for name in listed:
        path = kb / f"{name}.csv"
        if not path.is_file():
            raise SliceError(
                f"manifest lists table {name!r} but {path} is missing. "
                f"Re-run the extractor with --clean."
            )
        tables[name] = read_table(path)
    return tables


def _as_dicts(table: tuple[list[str], list[list[str]]]) -> list[dict[str, str]]:
    header, rows = table
    return [dict(zip(header, row)) for row in rows]


def subject_areas(kb: Path) -> list[tuple[str, str, str]]:
    """Every Subject Area available, as ``(row_id, rpd_id, name)``."""
    tables = _load(kb)
    if "presentation_subject_areas" not in tables:
        return []
    return sorted(
        (r["row_id"], r["rpd_id"], r["name"])
        for r in _as_dicts(tables["presentation_subject_areas"])
    )


def _select(records: list[dict[str, str]], column: str, keep: set[str]) -> list[dict[str, str]]:
    return [r for r in records if r.get(column) in keep]


def build(kb: Path, subject_area: str) -> dict[str, tuple[list[str], list[list[str]]]]:
    """Every Knowledge Base row reachable from one Subject Area.

    Walks the same foreign keys the ER diagram documents, downward through the
    three layers and outward to variables and security.
    """
    tables = _load(kb)
    D = {name: _as_dicts(t) for name, t in tables.items()}

    areas = [
        r for r in D.get("presentation_subject_areas", [])
        if subject_area in (r["row_id"], r["name"])
    ]
    if not areas:
        available = ", ".join(sorted(r["name"] for r in D.get("presentation_subject_areas", [])))
        raise SliceError(
            f"no Subject Area named {subject_area!r}. Available: {available or '(none)'}"
        )
    if len(areas) > 1:
        raise SliceError(
            f"{subject_area!r} matches {len(areas)} Subject Areas across different "
            f"repositories: {', '.join(a['row_id'] for a in areas)}. "
            f"Use the full row_id to disambiguate — AD-8 keeps them distinct."
        )

    area_ids = {areas[0]["row_id"]}

    pres_tables = _select(D.get("presentation_tables", []), "subject_area_id", area_ids)
    pres_table_ids = {r["row_id"] for r in pres_tables}
    pres_columns = _select(D.get("presentation_columns", []), "table_id", pres_table_ids)

    logical_column_ids = {r["logical_column_id"] for r in pres_columns if r["logical_column_id"]}
    # The implicit fact column may sit outside the presentation columns.
    logical_column_ids |= {a["implicit_fact_column_id"] for a in areas if a["implicit_fact_column_id"]}
    logical_columns = _select(D.get("logical_columns", []), "row_id", logical_column_ids)

    logical_table_ids = {r["table_id"] for r in logical_columns}
    logical_tables = _select(D.get("logical_tables", []), "row_id", logical_table_ids)
    aggregation_rules = _select(D.get("aggregation_rules", []), "logical_column_id", logical_column_ids)

    sources = _select(D.get("logical_table_sources", []), "logical_table_id", logical_table_ids)
    source_ids = {r["row_id"] for r in sources}
    column_map = [
        r for r in D.get("lts_column_map", [])
        if r["source_id"] in source_ids and r["logical_column_id"] in logical_column_ids
    ]

    pres_column_ids = {r["row_id"] for r in pres_columns}
    lineage = _select(D.get("lineage", []), "presentation_column_id", pres_column_ids)

    physical_column_ids = {r["physical_column_id"] for r in lineage if r["physical_column_id"]}
    physical_column_ids |= {r["physical_column_id"] for r in column_map if r["physical_column_id"]}
    physical_columns = _select(D.get("physical_columns", []), "row_id", physical_column_ids)
    physical_table_ids = {r["table_id"] for r in physical_columns}
    physical_tables = _select(D.get("physical_tables", []), "row_id", physical_table_ids)

    # Joins where BOTH sides are in scope; a join reaching outside the Subject
    # Area is not part of its picture.
    physical_joins = [
        r for r in D.get("physical_joins", [])
        if r["table1_id"] in physical_table_ids
        and (not r["table2_id"] or r["table2_id"] in physical_table_ids)
    ]
    bmm_joins = [
        r for r in D.get("bmm_joins", [])
        if r["table1_id"] in logical_table_ids or r["table2_id"] in logical_table_ids
    ]

    # Variables referenced by any expression that made it into the slice.
    blob = " ".join(
        v for records in (logical_columns, aggregation_rules, sources, column_map)
        for r in records for k, v in r.items() if "expr" in k or k.startswith(("where", "fragment", "group_by"))
    )
    variables = [r for r in D.get("variables", []) if r["name"] and r["name"] in blob]
    init_block_ids = {r["init_block_id"] for r in variables if r["init_block_id"]}
    init_blocks = _select(D.get("init_blocks", []), "row_id", init_block_ids)

    security = [
        r for r in D.get("security_rls", [])
        if r["subject_id"] in logical_table_ids or r["subject_id"] in source_ids
    ]

    selected = {
        "presentation_subject_areas": areas,
        "presentation_tables": pres_tables,
        "presentation_columns": pres_columns,
        "logical_tables": logical_tables,
        "logical_columns": logical_columns,
        "aggregation_rules": aggregation_rules,
        "logical_table_sources": sources,
        "lts_column_map": column_map,
        "lineage": lineage,
        "physical_tables": physical_tables,
        "physical_columns": physical_columns,
        "physical_joins": physical_joins,
        "bmm_joins": bmm_joins,
        "variables": variables,
        "init_blocks": init_blocks,
        "security_rls": security,
    }

    out: dict[str, tuple[list[str], list[list[str]]]] = {}
    for name, records in selected.items():
        if name not in tables:
            continue
        header = tables[name][0]
        # Sorted for byte-identical re-runs (AD-6); the header order is the
        # Knowledge Base's, never re-derived from a dict.
        out[name] = (header, sorted([r[c] for c in header] for r in records))
    return out


def write(sliced: dict, out_dir: Path, kb: Path, subject_area: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (header, rows) in sliced.items():
        guard = tuple(c for c in header if c in _GUARDABLE or "expr" in c
                      or c.startswith(("where", "fragment", "group_by")))
        write_table(out_dir / f"{name}.csv", header, rows, guard_columns=guard)

    write_table(
        out_dir / "slice-manifest.csv",
        ["key", "value"],
        [
            ["subject_area", subject_area],
            ["knowledge_base", str(kb)],
            ["tables", " ".join(sorted(sliced))],
            ["rows", str(sum(len(rows) for _, rows in sliced.values()))],
        ],
        guard_columns=("value",),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rpd_extract.slice",
        description="Cut one Subject Area out of the Knowledge Base for review or analysis.",
    )
    parser.add_argument("--kb", required=True, type=Path, help="Knowledge Base directory")
    parser.add_argument("--subject-area", default=None,
                        help="Subject Area name, or its full row_id. Omit to list them.")
    parser.add_argument("--out", type=Path, default=None, help="output directory")
    args = parser.parse_args(argv)

    try:
        if not args.subject_area:
            for row_id, rpd_id, name in subject_areas(args.kb):
                print(f"  {rpd_id:<20} {name}")
            return 0

        if args.out is None:
            parser.error("--out is required when --subject-area is given")

        sliced = build(args.kb, args.subject_area)
        write(sliced, args.out, args.kb, args.subject_area)
    except SliceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    total = sum(len(rows) for _, rows in sliced.values())
    print(f"subject area: {args.subject_area}")
    print(f"tables:       {len(sliced)}")
    print(f"rows:         {total}")
    print(f"written:      {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
