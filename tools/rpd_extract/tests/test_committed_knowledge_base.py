"""The committed Knowledge Base is what the extractor writes — nothing else.

``estate/knowledge-base/`` is committed so the estate can be read without the
corpus. That makes it a file somebody can edit, and nothing compared it with the
extractor's own output. So ``bmm_joins.csv`` sat in a commit with three stray
characters in front of its header — the first column named ``ok "row_id"``
instead of ``row_id`` — while 207 tests passed. No consumer happened to read
that column, which is the only reason nothing broke.

Two checks, and they are not equally strong:

* **Shape — always runs, needs no corpus.** The files present are exactly the
  ones the manifest lists, each header is byte-for-byte the one the writer
  emits, and every row has as many fields as its header. This catches the defect
  above. It does **not** catch an edited value.

* **Reproduction — needs the corpus, and skips without it.** Re-extract with the
  manifest's own timestamp and require every table to be byte-identical (AD-6).
  This catches an edited value, and it catches the other direction too: a change
  to the extractor that was never regenerated into the committed files. A bare
  checkout gets the shape check only; the skip says so rather than passing.

Standard-library ``unittest`` only (NFR13).
"""

from __future__ import annotations

import csv
import os
import tempfile
import unittest
from pathlib import Path

from tools.rpd_extract import cli, layout
from tools.rpd_extract.adapters.outbound import knowledge_base
from tools.rpd_extract.adapters.outbound.csv_writer import read_table
from tools.rpd_extract.core.model import Estate

KB = Path(__file__).resolve().parents[3] / "estate" / "knowledge-base"


def _manifest(kb: Path) -> dict[str, str]:
    _, rows = read_table(kb / "manifest.csv")
    return {row[0]: row[1] for row in rows}


def _first_line(path: Path) -> bytes:
    with path.open("rb") as handle:
        return handle.readline()


def shape_problems(kb: Path, reference: Path) -> list[str]:
    """Every way ``kb`` is not shaped like ``reference``, the writer's own output.

    ``reference`` is any Knowledge Base the current writer produced; an empty
    Estate is enough, because a header does not depend on the rows beneath it.
    """
    problems: list[str] = []

    expected = {p.name for p in reference.glob("*.csv")}
    present = {p.name for p in kb.glob("*.csv")}
    for name in sorted(expected - present):
        problems.append(f"{name}: the extractor writes this table, and it is absent")
    for name in sorted(present - expected):
        problems.append(f"{name}: present, but the extractor writes no such table")

    listed = {f"{t}.csv" for t in _manifest(kb).get("tables", "").split()}
    listed.add("manifest.csv")
    for name in sorted(listed ^ present):
        problems.append(f"{name}: manifest.csv and the directory disagree about it")

    for name in sorted(expected & present):
        want, got = _first_line(reference / name), _first_line(kb / name)
        if want != got:
            problems.append(f"{name}: header is {got!r}, the writer emits {want!r}")
            continue
        with (kb / name).open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            width = len(next(reader))
            for row in reader:
                if len(row) != width:
                    problems.append(
                        f"{name}: line {reader.line_num} has {len(row)} fields, "
                        f"header has {width}"
                    )
                    break
    return problems


class Shape(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.reference = Path(cls._tmp.name) / "reference"
        knowledge_base.write(Estate(), cls.reference, corpus_root="-", timestamp="-")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_the_committed_knowledge_base_has_the_writers_shape(self):
        self.assertEqual(shape_problems(KB, self.reference), [])

    def _damaged(self, damage) -> list[str]:
        """Problems reported for a writer-produced Knowledge Base after ``damage``."""
        with tempfile.TemporaryDirectory() as tmp:
            kb = Path(tmp)
            knowledge_base.write(Estate(), kb, corpus_root="-", timestamp="-")
            damage(kb)
            return shape_problems(kb, self.reference)

    def test_the_check_detects_the_defect_it_was_written_for(self):
        """The check fires. A check that cannot fail proves nothing."""
        def prefix_the_header(kb: Path) -> None:
            path = kb / "bmm_joins.csv"
            path.write_bytes(b"ok " + path.read_bytes())

        problems = self._damaged(prefix_the_header)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("bmm_joins.csv: header is", problems[0])

    def test_the_check_detects_a_missing_and_a_stray_table(self):
        def swap_a_table(kb: Path) -> None:
            (kb / "bmm_joins.csv").rename(kb / "bmm_joins_old.csv")

        problems = "\n".join(self._damaged(swap_a_table))
        self.assertIn("bmm_joins.csv: the extractor writes this table", problems)
        self.assertIn("bmm_joins_old.csv: present, but", problems)

    def test_the_check_detects_a_row_of_the_wrong_width(self):
        def append_a_short_row(kb: Path) -> None:
            with (kb / "bmm_joins.csv").open("a", encoding="utf-8") as handle:
                handle.write('"only","two"\n')

        problems = self._damaged(append_a_short_row)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("bmm_joins.csv: line 2 has 2 fields", problems[0])


#: Where the corpus is. Defaults to the path the committed manifest recorded;
#: overridable so the check can run where the corpus is kept somewhere else.
CORPUS = Path(os.environ.get("OBIEE_CORPUS", _manifest(KB)["corpus_root"]))


@unittest.skipUnless(
    CORPUS.is_dir(),
    f"corpus not present at {CORPUS} — the committed Knowledge Base was checked "
    f"for shape only, NOT against a fresh extraction",
)
class Reproduction(unittest.TestCase):

    def test_a_fresh_extraction_is_byte_identical_to_what_is_committed(self):
        manifest = _manifest(KB)
        estate = cli.extract(layout.resolve(CORPUS, None))

        with tempfile.TemporaryDirectory() as tmp:
            fresh = Path(tmp)
            # The manifest's own corpus_root and timestamp, so the manifest is
            # held to byte-identity along with everything else.
            written = knowledge_base.write(
                estate,
                fresh,
                corpus_root=manifest["corpus_root"],
                timestamp=manifest["extracted_at"],
            )
            differing = [
                f"{name}.csv"
                for name in sorted(written)
                if not (KB / f"{name}.csv").is_file()
                or (KB / f"{name}.csv").read_bytes()
                != (fresh / f"{name}.csv").read_bytes()
            ]

        self.assertEqual(
            differing, [],
            "committed tables differ from a fresh extraction. Either a committed "
            "file was edited, or the extractor changed and the Knowledge Base was "
            "not regenerated (see estate/knowledge-base/README.md)",
        )


if __name__ == "__main__":
    unittest.main()
