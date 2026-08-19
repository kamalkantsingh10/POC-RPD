"""Spreadsheet-safe CSV writing and reading for Knowledge Base tables.

Outbound adapter (AD-15): depends on nothing in ``core`` and is never imported
by it. Standard library only, at any version (NFR13, FR-23).

The guard mechanism and the precise claim it supports are recorded in
``documents/planning-artifacts/decisions/csv-formula-guard.md``. In short: a
value a spreadsheet would corrupt is written with a single leading apostrophe,
and a companion boolean column records that it was. Reversal is therefore
deterministic rather than heuristic, and the artifact is self-describing (AD-5).

Conventions enforced here come from the Architecture Spine: UTF-8, comma
delimiter, LF line endings, one header row, every field quoted.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Sequence
from pathlib import Path

#: Prepended to a value a spreadsheet would otherwise reinterpret.
GUARD = "'"

#: Suffix of the companion column recording whether a value was guarded.
GUARD_SUFFIX = "_guarded"

TRUE = "true"
FALSE = "false"

# A spreadsheet treats a leading one of these as the start of a formula, even
# when the field is quoted.
_FORMULA_LEADERS = ("=", "+", "-", "@")

# Leading whitespace that spreadsheets handle inconsistently. A plain leading
# space is deliberately absent: it round-trips reliably and guarding it would
# fire on ordinary formula text.
_WHITESPACE_LEADERS = ("\t", "\r", "\n")

# Numeric coercion. These are the same defect as formula injection arriving by
# another route, and FR-28 requires them handled.
_LEADING_ZERO = re.compile(r"^0\d+$")
_SCIENTIFIC = re.compile(r"^[+-]?\d+(?:\.\d+)?[eE][+-]?\d+$")
_PRECISION_LOSS = re.compile(r"^\d{16,}$")  # beyond a spreadsheet's exact range


def needs_guard(value: str) -> bool:
    """Whether a spreadsheet would alter ``value`` on open."""
    if not value:
        return False
    if value.startswith(_FORMULA_LEADERS) or value.startswith(_WHITESPACE_LEADERS):
        return True
    return bool(
        _LEADING_ZERO.match(value)
        or _SCIENTIFIC.match(value)
        or _PRECISION_LOSS.match(value)
    )


def _companion(column: str) -> str:
    return f"{column}{GUARD_SUFFIX}"


def _expand_header(header: Sequence[str], guard_columns: frozenset[str]) -> list[str]:
    """Insert each companion column immediately after the column it describes."""
    out: list[str] = []
    for name in header:
        out.append(name)
        if name in guard_columns:
            out.append(_companion(name))
    return out


def _validate(header: Sequence[str], guard_columns: frozenset[str]) -> None:
    if len(set(header)) != len(header):
        raise ValueError(f"duplicate column name in header: {list(header)}")

    unknown = guard_columns - set(header)
    if unknown:
        raise ValueError(f"guard_columns not present in header: {sorted(unknown)}")

    existing = set(header)
    for name in sorted(guard_columns):
        if _companion(name) in existing:
            raise ValueError(
                f"companion column {_companion(name)!r} collides with an existing "
                f"column; rename the column or the guard suffix"
            )


def write_table(
    path: Path | str,
    header: Sequence[str],
    rows: Iterable[Sequence[str]],
    *,
    guard_columns: Iterable[str] = (),
) -> None:
    """Write one Knowledge Base table.

    Row and column order is the caller's contract and is never altered here.
    Determinism of content belongs to the caller; determinism of encoding
    belongs to this function, and together they satisfy AD-6.

    Every value must already be ``str``. Coercion is refused because it would
    change the bytes a caller believes it supplied.

    Raises ``ValueError`` if a value requiring a guard appears in a column that
    was not declared guardable. Failing loudly is deliberate: silently mangling
    a formula is the defect this module exists to prevent (NFR7).
    """
    path = Path(path)
    guards = frozenset(guard_columns)
    _validate(header, guards)

    out_header = _expand_header(header, guards)
    width = len(header)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        # csv defaults to QUOTE_MINIMAL and CRLF; both violate the conventions.
        writer = csv.writer(fh, quoting=csv.QUOTE_ALL, lineterminator="\n")
        writer.writerow(out_header)

        for index, row in enumerate(rows):
            if len(row) != width:
                raise ValueError(
                    f"row {index} has {len(row)} values, expected {width} "
                    f"to match header {list(header)}"
                )

            out_row: list[str] = []
            for name, value in zip(header, row):
                if not isinstance(value, str):
                    raise TypeError(
                        f"row {index}, column {name!r}: expected str, got "
                        f"{type(value).__name__}. Convert before writing so the "
                        f"stored representation is the caller's choice."
                    )

                guarded = needs_guard(value)
                if name in guards:
                    out_row.append(GUARD + value if guarded else value)
                    out_row.append(TRUE if guarded else FALSE)
                elif guarded:
                    raise ValueError(
                        f"row {index}, column {name!r}: value would be altered by a "
                        f"spreadsheet (starts {value[:1]!r}) but the column is not "
                        f"declared in guard_columns. Declare it, or store the value "
                        f"in a column that is."
                    )
                else:
                    out_row.append(value)

            writer.writerow(out_row)


def read_table(path: Path | str) -> tuple[list[str], list[list[str]]]:
    """Read a table written by :func:`write_table`, reversing every guard.

    Returns the logical header — companion columns removed — and rows whose
    values equal, byte for byte, what was passed to ``write_table``.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        try:
            raw_header = next(reader)
        except StopIteration:
            raise ValueError(f"{path} is empty; expected at least a header row") from None

        # A column is guarded when the very next column is its companion. The
        # adjacency is what write_table guarantees, so it is what we rely on.
        header: list[str] = []
        guarded_at: list[bool] = []
        skip_next = False
        for position, name in enumerate(raw_header):
            if skip_next:
                skip_next = False
                continue
            follows = raw_header[position + 1] if position + 1 < len(raw_header) else None
            if follows == _companion(name):
                header.append(name)
                guarded_at.append(True)
                skip_next = True
            else:
                header.append(name)
                guarded_at.append(False)

        rows: list[list[str]] = []
        for index, raw_row in enumerate(reader):
            if len(raw_row) != len(raw_header):
                raise ValueError(
                    f"{path}: row {index} has {len(raw_row)} fields, expected "
                    f"{len(raw_header)}"
                )
            row: list[str] = []
            cursor = 0
            for is_guarded in guarded_at:
                value = raw_row[cursor]
                if is_guarded:
                    flag = raw_row[cursor + 1]
                    if flag == TRUE:
                        if not value.startswith(GUARD):
                            raise ValueError(
                                f"{path}: row {index} is flagged guarded but does not "
                                f"begin with {GUARD!r}; the file has been edited"
                            )
                        value = value[len(GUARD) :]
                    elif flag != FALSE:
                        raise ValueError(
                            f"{path}: row {index} has guard flag {flag!r}, expected "
                            f"{TRUE!r} or {FALSE!r}"
                        )
                    cursor += 2
                else:
                    cursor += 1
                row.append(value)
            rows.append(row)

    return header, rows
