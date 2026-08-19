"""Tests for the spreadsheet-safe CSV writer (Story 1.3).

Standard-library ``unittest`` only. The Architecture Spine's stack table reads
"Python third-party packages | none, at any version", and that includes test
dependencies — so no pytest.

The spreadsheet half of FR-28's round trip is performed manually, once, by a
human, and recorded in documents/planning-artifacts/decisions/csv-formula-guard.md.
Automating it would pull a spreadsheet library into the product and breach
NFR15, which exists precisely because LibreOffice and openpyxl are easy to
reach for on this machine.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.rpd_extract.adapters.outbound.csv_writer import (
    GUARD,
    needs_guard,
    read_table,
    write_table,
)

# Values that must survive write -> read byte for byte. Drawn from FR-28's
# consequence list plus real OBIEE and MDS XML expression shapes.
CORPUS = [
    # Ordinary text
    "Revenue",
    "",
    # Embedded CSV metacharacters (FR-28)
    'SUM("Sample Sales"."Fact - Sales"."Revenue")',
    "AGO(Revenue, Year, 1), TODATE(Revenue, Year)",
    'CASE WHEN "X" = \'a\' THEN 1 ELSE 0 END',
    "line one\nline two",
    "trailing comma,",
    # Formula leaders (FR-28)
    '-1 * "Sample Sales"."Fact - Sales"."Revenue"',
    "=CASE WHEN 1=1 THEN 2 END",
    "+Revenue",
    "@variable",
    # Numeric coercion (FR-28)
    "00123",
    "1E5",
    "1e5",
    "-1.5e-3",
    "1234567890123456",
    # A value that already begins with the guard character. Without the
    # companion flag this is indistinguishable from a guarded value.
    "'quoted start",
    # Non-ASCII
    "Umsatz pro Händler — Ø",
    # Real MDS XML expression text
    '"SAMPLESALES"."Fact Revenue"."Bill Day Dt"',
    '"xe".""."SAMPLESALES"."SAMP_REVENUE_F"."BILL_DAY_DT"',
    '"%1"',
]


class NeedsGuard(unittest.TestCase):
    def test_flags_formula_leaders(self):
        for value in ("=a", "+a", "-a", "@a"):
            self.assertTrue(needs_guard(value), value)

    def test_flags_numeric_coercion(self):
        for value in ("00123", "1E5", "1e5", "-1.5e-3", "1234567890123456"):
            self.assertTrue(needs_guard(value), value)

    def test_leaves_ordinary_text_alone(self):
        for value in ("", "Revenue", "123", "0", '"quoted"', " leading space"):
            self.assertFalse(needs_guard(value), value)


class RoundTrip(unittest.TestCase):
    """FR-28 / AC #3, #4, #5 — the verbatim guarantee, enforced."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "logical_columns.csv"

    def tearDown(self):
        self._tmp.cleanup()

    def test_every_corpus_value_survives_byte_for_byte(self):
        header = ["row_id", "formula"]
        rows = [[f"sampleapp::bmm::c{i}", value] for i, value in enumerate(CORPUS)]

        write_table(self.path, header, rows, guard_columns=["formula"])
        read_header, read_rows = read_table(self.path)

        self.assertEqual(read_header, header)
        self.assertEqual(read_rows, rows)
        for original, returned in zip(rows, read_rows):
            self.assertEqual(original[1], returned[1])

    def test_guarded_value_and_unguarded_value_are_distinguishable(self):
        # "'quoted start" is stored unguarded; "=formula" is stored guarded and
        # gains a leading apostrophe. Both must come back exactly as supplied.
        header = ["formula"]
        rows = [["'quoted start"], ["=formula"]]

        write_table(self.path, header, rows, guard_columns=["formula"])
        _, read_rows = read_table(self.path)

        self.assertEqual(read_rows, rows)

    def test_guarded_field_is_neutralised_on_disk(self):
        write_table(
            self.path, ["formula"], [["=DANGEROUS()"]], guard_columns=["formula"]
        )
        raw = self.path.read_text(encoding="utf-8")

        self.assertIn(f'"{GUARD}=DANGEROUS()"', raw)
        self.assertIn('"formula_guarded"', raw)
        self.assertIn('"true"', raw)

    def test_unguarded_value_records_a_false_flag(self):
        write_table(self.path, ["formula"], [["Revenue"]], guard_columns=["formula"])
        raw = self.path.read_text(encoding="utf-8")

        self.assertIn('"Revenue","false"', raw)


class Encoding(unittest.TestCase):
    """AC #1 — UTF-8, comma delimited, LF endings, one header row, all quoted."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "t.csv"
        write_table(
            self.path,
            ["a", "b"],
            [["plain", "with,comma"], ["with\nnewline", 'with"quote']],
        )
        self.raw = self.path.read_bytes()

    def tearDown(self):
        self._tmp.cleanup()

    def test_line_endings_are_lf(self):
        self.assertNotIn(b"\r\n", self.raw)
        self.assertNotIn(b"\r", self.raw)

    def test_no_byte_order_mark(self):
        self.assertFalse(self.raw.startswith(b"\xef\xbb\xbf"))

    def test_is_utf8(self):
        self.raw.decode("utf-8")

    def test_every_field_is_quoted(self):
        text = self.raw.decode("utf-8")
        self.assertTrue(text.startswith('"a","b"\n'))
        self.assertIn('"plain","with,comma"', text)

    def test_non_ascii_survives(self):
        path = self.path.with_name("u.csv")
        write_table(path, ["a"], [["Ø — Händler"]])
        _, rows = read_table(path)
        self.assertEqual(rows, [["Ø — Händler"]])


class Determinism(unittest.TestCase):
    """AD-6 — re-running over unchanged input produces byte-identical output."""

    def test_writing_twice_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.csv"
            second = Path(tmp) / "b.csv"
            header = ["row_id", "formula"]
            rows = [["r1", "-1 * x"], ["r2", "Revenue"]]

            write_table(first, header, rows, guard_columns=["formula"])
            write_table(second, header, rows, guard_columns=["formula"])

            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_row_and_column_order_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.csv"
            header = ["z", "a", "m"]
            rows = [["3", "1", "2"], ["6", "4", "5"]]

            write_table(path, header, rows)
            read_header, read_rows = read_table(path)

            self.assertEqual(read_header, header)
            self.assertEqual(read_rows, rows)


class LoudFailure(unittest.TestCase):
    """NFR7 — never mangle silently; fail with the column and the reason."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "t.csv"

    def tearDown(self):
        self._tmp.cleanup()

    def test_guardable_value_in_undeclared_column_raises(self):
        with self.assertRaises(ValueError) as ctx:
            write_table(self.path, ["formula"], [["-1 * x"]])
        self.assertIn("formula", str(ctx.exception))
        self.assertIn("guard_columns", str(ctx.exception))

    def test_row_width_mismatch_raises(self):
        with self.assertRaises(ValueError) as ctx:
            write_table(self.path, ["a", "b"], [["only-one"]])
        self.assertIn("row 0", str(ctx.exception))

    def test_non_string_value_raises(self):
        with self.assertRaises(TypeError) as ctx:
            write_table(self.path, ["a"], [[123]])
        self.assertIn("expected str", str(ctx.exception))

    def test_unknown_guard_column_raises(self):
        with self.assertRaises(ValueError):
            write_table(self.path, ["a"], [["x"]], guard_columns=["nope"])

    def test_companion_name_collision_raises(self):
        with self.assertRaises(ValueError) as ctx:
            write_table(
                self.path,
                ["formula", "formula_guarded"],
                [["x", "y"]],
                guard_columns=["formula"],
            )
        self.assertIn("collides", str(ctx.exception))

    def test_duplicate_header_raises(self):
        with self.assertRaises(ValueError):
            write_table(self.path, ["a", "a"], [["x", "y"]])

    def test_tampered_guard_flag_raises_on_read(self):
        write_table(self.path, ["formula"], [["=x"]], guard_columns=["formula"])
        self.path.write_text('"formula","formula_guarded"\n"=x","true"\n', encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            read_table(self.path)
        self.assertIn("edited", str(ctx.exception))

    def test_empty_file_raises_on_read(self):
        self.path.write_text("", encoding="utf-8")
        with self.assertRaises(ValueError):
            read_table(self.path)


class NoThirdPartyImports(unittest.TestCase):
    """NFR13 / FR-23 — the extractor imports nothing outside the stdlib."""

    def test_module_imports_are_stdlib_only(self):
        import ast

        source = Path("tools/rpd_extract/adapters/outbound/csv_writer.py")
        tree = ast.parse(source.read_text(encoding="utf-8"))

        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])

        import sys

        allowed = set(sys.stdlib_module_names) | {"__future__"}
        self.assertEqual(roots - allowed, set(), f"non-stdlib imports: {roots - allowed}")


if __name__ == "__main__":
    unittest.main()
