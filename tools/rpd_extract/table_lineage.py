"""Table-level lineage, one row per chain, as a single flat CSV.

    Subject Area -> Presentation Table -> Logical Table -> Logical Table Source
        -> Physical Table (alias) -> Physical Table (original)
        -> Intermediate View -> Final Table

``lineage.csv`` answers this per column — 1573 rows on the development corpus.
A person planning a migration asks it per table, and wants it in one sheet. This
script folds the column-level rows to that grain and adds what the physical
layer says each table really is. It reads the Knowledge Base only; it never
opens a repository.

How each cell is filled:

* **physical_table_alias / physical_table_original** — when the table a source
  maps to is an alias, the alias is named in the first and the table it stands
  for in the second. When it is not an alias, the first is empty.
* **intermediate_view** — the name of the opaque view, when the original table
  is one (``table_type`` ``select``). Otherwise empty.
* **final_table** — for an opaque view, **its SQL, verbatim**. For an ordinary
  table, the name the repository records for it in the database, which need not
  be the name the repository shows; where none is recorded, the table's own
  name. The SQL is not parsed, so the tables a view reads from are in the query
  text and nowhere else — and a view defined in the database rather than in the
  repository looks like an ordinary table here (AD-3: nothing is inferred).
* **comment** — always empty. It is there for whoever reads the sheet.

**Nothing drops out for lack of lineage.** A Presentation Table whose columns
reach no physical column still gets a row, with the cells it could not fill left
empty, so an empty cell means *not recorded* and a missing row cannot happen.

Rows are sorted, so a re-run is byte-identical (AD-6).

**The sheet is written plain by default — no ``_guarded`` companion columns.**
It is a handout read by eye, and nine companions double its width to say
``false`` 1413 times. The cost is real and is not hidden: a value a spreadsheet
would alter (SQL opening with ``--``, a name like ``00123``) is written as it
is, so the run **counts those values and says so**. ``--guarded`` writes the
Knowledge Base's spreadsheet-safe form instead (FR-28), for when the count is
not zero and the sheet is going to be opened in one.

Standard library only (NFR13).
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from tools.rpd_extract.adapters.outbound.csv_writer import (
    needs_guard,
    read_table,
    write_table,
)

HEADER = [
    "rpd_id",
    "subject_area",
    "presentation_table",
    "logical_table",
    "logical_table_source",
    "physical_table_alias",
    "physical_table_original",
    "intermediate_view",
    "final_table",
    "comment",
]

#: Every cell but ``rpd_id`` is a name or SQL taken from the estate, so every
#: one of them may begin with a character a spreadsheet would act on.
_GUARD = tuple(HEADER[1:])

#: ``physical_tables.table_type`` of a table defined by SQL in the repository.
OPAQUE_VIEW = "select"

_NEEDED = (
    "presentation_subject_areas",
    "presentation_tables",
    "presentation_columns",
    "logical_tables",
    "logical_columns",
    "logical_table_sources",
    "lineage",
    "physical_tables",
    "physical_table_definitions",
)


class TableLineageError(ValueError):
    """The Knowledge Base could not be used."""


def _load(kb: Path) -> dict[str, list[dict[str, str]]]:
    manifest = kb / "manifest.csv"
    if not manifest.is_file():
        raise TableLineageError(
            f"{kb} has no manifest.csv, so it is not a Knowledge Base. Run the "
            f"extractor first: python3 -m tools.rpd_extract.cli --corpus … --out {kb}"
        )
    _, rows = read_table(manifest)
    # From the manifest, never a directory listing: a file left behind by an
    # older extractor is not part of this Knowledge Base.
    listed = set(dict((r[0], r[1]) for r in rows).get("tables", "").split())

    missing = [name for name in _NEEDED if name not in listed]
    if missing:
        raise TableLineageError(
            f"{kb} was written by an extractor that does not produce "
            f"{', '.join(missing)}. Re-run the extractor with --clean."
        )

    tables: dict[str, list[dict[str, str]]] = {}
    for name in _NEEDED:
        path = kb / f"{name}.csv"
        if not path.is_file():
            raise TableLineageError(
                f"manifest lists table {name!r} but {path} is missing. "
                f"Re-run the extractor with --clean."
            )
        header, rows = read_table(path)
        if name == "physical_tables" and "source_table_id" not in header:
            raise TableLineageError(
                f"{path} has no source_table_id column, so aliases cannot be "
                f"told from ordinary tables. Re-run the extractor with --clean."
            )
        tables[name] = [dict(zip(header, row)) for row in rows]
    return tables


def _qualified(table: dict[str, str]) -> str:
    """``<container>.<name>`` — a bare name does not identify a table.

    The development corpus holds two different tables named ``COSTS`` in two
    schemas both named ``SH``; printed bare they are one row repeated.
    """
    return f"{table['container']}.{table['name']}" if table["container"] else table["name"]


def _definition(texts: list[tuple[str, str]]) -> str:
    """One definition verbatim; several, each on its own line under its database."""
    distinct = sorted(set(texts))
    if len({text for _, text in distinct}) == 1:
        return distinct[0][1]
    return "\n".join(f"[{database}] {text}" for database, text in distinct)


def _physical_cells(
    table_id: str,
    physical: dict[str, dict[str, str]],
    definitions: dict[str, list[tuple[str, str]]],
) -> list[str]:
    """``alias, original, intermediate_view, final_table`` for one mapped table."""
    table = physical.get(table_id)
    if table is None:
        # Lineage names a table the physical layer does not carry. Shown as the
        # identifier it was given rather than dropped or dressed up as a name.
        return ["", table_id, "", ""]

    original = physical.get(table["source_table_id"]) if table["source_table_id"] else None
    if original is None:
        alias, original = "", table
    else:
        alias = _qualified(table)

    # The original's definition, then the alias's own: in the development corpus
    # every alias repeats its original's exactly, and where an estate has them
    # disagree both are shown rather than one chosen.
    texts = list(definitions.get(original["row_id"], []))
    if alias:
        texts += definitions.get(table["row_id"], [])
    recorded = _definition(texts) if texts else ""

    if original["table_type"] == OPAQUE_VIEW:
        return [alias, _qualified(original), _qualified(original), recorded]
    return [alias, _qualified(original), "", recorded or original["name"]]


def build(kb: Path | str) -> list[list[str]]:
    """Every chain in the Knowledge Base, as rows matching :data:`HEADER`."""
    tables = _load(Path(kb))
    by_id = lambda name: {row["row_id"]: row for row in tables[name]}  # noqa: E731

    subject_areas = by_id("presentation_subject_areas")
    presentation_columns = by_id("presentation_columns")
    logical_tables = by_id("logical_tables")
    logical_columns = by_id("logical_columns")
    sources = by_id("logical_table_sources")
    physical = by_id("physical_tables")

    definitions: dict[str, list[tuple[str, str]]] = {}
    for row in tables["physical_table_definitions"]:
        definitions.setdefault(row["table_id"], []).append((row["database"], row["text"]))

    def logical_table_of(logical_column_id: str) -> str:
        column = logical_columns.get(logical_column_id)
        return column["table_id"] if column else ""

    # (presentation table, logical table) -> the (source, physical table) pairs
    # reached from it. Keyed on identifiers, never names: two chains that print
    # alike are still two chains.
    chains: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for column in tables["presentation_columns"]:
        key = (column["table_id"], logical_table_of(column["logical_column_id"]))
        chains.setdefault(key, set())
    for row in tables["lineage"]:
        column = presentation_columns.get(row["presentation_column_id"])
        if column is None:
            continue
        key = (column["table_id"], logical_table_of(row["logical_column_id"]))
        chains.setdefault(key, set()).add((row["source_id"], row["physical_table_id"]))

    def name_of(rows: dict[str, dict[str, str]], row_id: str) -> str:
        # An identifier that resolves to nothing is shown as itself.
        return rows[row_id]["name"] if row_id in rows else row_id

    out: list[list[str]] = []
    reached = {presentation_table for presentation_table, _ in chains}
    for presentation_table in tables["presentation_tables"]:
        head = [
            presentation_table["rpd_id"],
            name_of(subject_areas, presentation_table["subject_area_id"]),
            presentation_table["name"],
        ]
        if presentation_table["row_id"] not in reached:
            # No column at all: the table is still part of the Subject Area.
            out.append([*head, "", "", "", "", "", "", ""])
            continue
        for (table_id, logical_table_id), pairs in chains.items():
            if table_id != presentation_table["row_id"]:
                continue
            logical = [*head, name_of(logical_tables, logical_table_id)]
            if not pairs:
                # Presented, but nothing it shows is sourced from a physical
                # column — computed columns only, or an unmapped source.
                out.append([*logical, "", "", "", "", "", ""])
                continue
            for source_id, physical_table_id in pairs:
                out.append([
                    *logical,
                    name_of(sources, source_id),
                    *_physical_cells(physical_table_id, physical, definitions),
                    "",
                ])
    return sorted(out)


def at_risk(rows: list[list[str]]) -> int:
    """How many values a spreadsheet would alter on opening the plain sheet."""
    return sum(1 for row in rows for value in row if needs_guard(value))


def write(rows: list[list[str]], out: Path | str, *, guarded: bool = False) -> None:
    """Write the sheet: plain by default, spreadsheet-safe when ``guarded``.

    Plain means every value exactly as the Knowledge Base holds it and no
    companion columns. Same encoding conventions either way: UTF-8, LF, every
    field quoted.
    """
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if guarded:
        write_table(out, HEADER, rows, guard_columns=_GUARD)
        return
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_ALL, lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rpd_extract.table_lineage",
        description=(
            "Write table-level lineage — Subject Area to physical table, with "
            "aliases and opaque views resolved — as one flat CSV."
        ),
    )
    parser.add_argument("--kb", required=True, type=Path, help="Knowledge Base directory")
    parser.add_argument("--out", required=True, type=Path, help="the CSV file to write")
    parser.add_argument("--guarded", action="store_true",
                        help="add a <column>_guarded companion to every text column "
                             "and protect values a spreadsheet would alter")
    args = parser.parse_args(argv)

    try:
        rows = build(args.kb)
    except TableLineageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    write(rows, args.out, guarded=args.guarded)

    column = HEADER.index
    print(f"rows:          {len(rows)}")
    print(f"aliases:       {sum(1 for r in rows if r[column('physical_table_alias')])}")
    print(f"opaque views:  {sum(1 for r in rows if r[column('intermediate_view')])}")
    print(f"no physical:   {sum(1 for r in rows if not r[column('physical_table_original')])}")
    print(f"written:       {args.out}")
    risky = at_risk(rows)
    if risky and not args.guarded:
        print(
            f"warning: {risky} value(s) would be altered by a spreadsheet on "
            f"opening this file. Re-run with --guarded to protect them.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
