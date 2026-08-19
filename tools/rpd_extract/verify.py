"""Per-construct accuracy report (SM-7).

Checks each FR-4 parity-critical construct against evidence and writes a CSV
reporting the result **per construct type, never as a single aggregate figure**
(PRD §14).

Two rules govern the output:

* **AD-19** — a construct without a fixture is reported as ``unimplemented``,
  never claimed as working. Silence is not success.
* **FR-31** — accuracy from hand-authored Constructed Cases is reported
  separately from accuracy measured against real corpus content, and the two
  are never merged. The ``evidence`` column carries that distinction.

Standard library only (NFR13).
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from tools.rpd_extract.adapters.inbound import mds_xml
from tools.rpd_extract.core import identifiers
from tools.rpd_extract.adapters.outbound.csv_writer import write_table
from tools.rpd_extract.core.model import Estate

CORPUS = "corpus"
CONSTRUCTED = "constructed"

PASS = "pass"
FAIL = "fail"
UNIMPLEMENTED = "unimplemented"


def _check(estate: Estate, evidence: str, name: str, predicate, detail: str):
    """Run one construct check. A predicate returning 0 means no fixture."""
    try:
        count = predicate(estate)
    except Exception as exc:  # a broken check is a failure, never a silent pass
        return [name, evidence, FAIL, "0", f"check raised: {exc}"]
    if not count:
        return [name, evidence, UNIMPLEMENTED, "0",
                f"no fixture exercises this construct — {detail}"]
    return [name, evidence, PASS, str(count), detail]


def _corpus_checks(estate: Estate) -> list[list[str]]:
    return [
        _check(estate, CORPUS, "aggregation rule (default)",
               lambda e: sum(1 for r in e.aggregation_rules if r.is_default == "true"),
               "AggrRule with isDefault=true"),
        _check(estate, CORPUS, "aggregation rule (dimension-specific override)",
               lambda e: sum(1 for r in e.aggregation_rules if r.is_default == "false"),
               "AggrRule with isDefault=false"),
        _check(estate, CORPUS, "LTS priority order",
               lambda e: sum(1 for s in e.logical_table_sources if s.priority),
               "priority recorded on a Logical Table Source"),
        _check(estate, CORPUS, "LTS fragmentation predicate",
               lambda e: sum(1 for s in e.logical_table_sources if not s.fragment.is_empty),
               "populated FragmentContent"),
        _check(estate, CORPUS, "content-level filter",
               lambda e: sum(1 for s in e.logical_table_sources if not s.where_clause.is_empty),
               "populated WhereClause"),
        _check(estate, CORPUS, "BMM join type (inner)",
               lambda e: sum(1 for j in e.bmm_joins if j.join_type == "Inner"),
               "LogicalComplexJoin type=Inner"),
        _check(estate, CORPUS, "BMM join type (outer)",
               lambda e: sum(1 for j in e.bmm_joins if "Outer" in j.join_type),
               "LogicalComplexJoin type containing Outer"),
        _check(estate, CORPUS, "time-series function",
               lambda e: sum(1 for c in e.logical_columns if c.time_series),
               "AGO / TODATE / PERIODROLLING flagged on a logical column"),
        _check(estate, CORPUS, "session and repository variables",
               lambda e: len(e.variables), "Variable objects captured"),
        _check(estate, CORPUS, "rename chain",
               lambda e: sum(1 for c in e.presentation_columns if c.logical_column_id),
               "presentation column resolved to a logical column"),
        _check(estate, CORPUS, "implicit fact column",
               lambda e: sum(1 for s in e.subject_areas if s.implicit_fact_column_id),
               "Subject Area with defaultFactColumnRef"),
        _check(estate, CORPUS, "row-level security filter per role",
               lambda e: sum(1 for r in e.security_rules if r.kind == "row_filter"),
               "row filter on a Logical Table Source"),
    ]


#: Expected values, transcribed from
#: estate/test-corpus/constructed-cases/GROUND-TRUTH.md.
GROUND_TRUTH = {
    "priority": {"LTS_DETAIL": "0", "LTS_MONTHLY_AGG": "1"},
    "fragment_contains": {
        "LTS_DETAIL": '"CC_SCHEMA"."FCT_SALES_DETAIL"."DAY_DT" >= TIMESTAMP',
        "LTS_MONTHLY_AGG": '"CC_SCHEMA"."FCT_SALES_MONTHLY"."MONTH_DT" <  TIMESTAMP',
    },
    "periodrolling_text": 'PERIODROLLING("%1", -2, 0)',
    "implicit_fact": "constructed::bmm::Constructed BM.Fact Sales.Amount",
    "aggr_rules": {"AggRule_Default": "true", "AggRule_Override_Time": "false"},
}


def _constructed_checks(estate: Estate) -> list[list[str]]:
    """Compare extraction against recorded Ground Truth, value by value."""
    results: list[list[str]] = []
    sources = {s.name: s for s in estate.logical_table_sources}

    # LTS priority — exact values.
    bad = [n for n, want in GROUND_TRUTH["priority"].items()
           if n not in sources or sources[n].priority != want]
    results.append(["LTS priority order", CONSTRUCTED, FAIL if bad else PASS,
                    str(len(GROUND_TRUTH["priority"]) - len(bad)),
                    f"mismatched: {bad}" if bad else "priorities match Ground Truth"])

    # Fragmentation — substring, because the full predicate is long.
    bad = [n for n, want in GROUND_TRUTH["fragment_contains"].items()
           if n not in sources or want not in sources[n].fragment.text_desc]
    results.append(["LTS fragmentation predicate", CONSTRUCTED, FAIL if bad else PASS,
                    str(len(GROUND_TRUTH["fragment_contains"]) - len(bad)),
                    f"mismatched: {bad}" if bad else
                    "predicates match Ground Truth, including the double space"])

    # PERIODROLLING — exact template text, verbatim.
    rolling = [c for c in estate.logical_columns
               if c.derived.text == GROUND_TRUTH["periodrolling_text"]]
    results.append(["time-series function (PERIODROLLING)", CONSTRUCTED,
                    PASS if rolling else FAIL, str(len(rolling)),
                    "expression verbatim incl. window bounds" if rolling
                    else "PERIODROLLING text does not match Ground Truth"])

    # Implicit fact column — resolved identifier, not a GUID.
    areas = [s for s in estate.subject_areas
             if s.implicit_fact_column_id == GROUND_TRUTH["implicit_fact"]]
    results.append(["implicit fact column", CONSTRUCTED, PASS if areas else FAIL,
                    str(len(areas)),
                    "resolved to a Knowledge Base identifier" if areas
                    else "defaultFactColumnRef did not resolve as expected"])

    # Aggregation override — both rules, never collapsed.
    got = {r.name: r.is_default for r in estate.aggregation_rules}
    want = GROUND_TRUTH["aggr_rules"]
    ok = all(got.get(n) == v for n, v in want.items())
    results.append(["aggregation rule (dimension-specific override)", CONSTRUCTED,
                    PASS if ok else FAIL, str(len(want) if ok else 0),
                    "both rules survive; override not collapsed into default" if ok
                    else f"expected {want}, got {got}"])
    return results


def build_report(
    corpus_root: Path, cases_root: Path, rpd_id: str | None = None
) -> list[list[str]]:
    rows = _corpus_checks(mds_xml.load(corpus_root, rpd_id))
    rows += _constructed_checks(mds_xml.load(cases_root))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rpd_extract.verify",
        description="Per-construct accuracy report against recorded Ground Truth (SM-7).",
    )
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--rpd-id", default=None,
                        help="declare the rpd-id when --corpus IS one repository tree")
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        rows = build_report(args.corpus, args.cases, args.rpd_id)
    except (mds_xml.CorpusError, identifiers.IdentifierError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    write_table(
        args.out,
        ["construct", "evidence", "status", "instances", "detail"],
        rows,
        guard_columns=("detail",),
    )

    tally: dict[str, int] = {}
    for row in rows:
        tally[row[2]] = tally.get(row[2], 0) + 1
    for status in (PASS, FAIL, UNIMPLEMENTED):
        print(f"  {status:<14} {tally.get(status, 0)}")
    print(f"  written        {args.out}")
    # Unimplemented is a reportable state, not an error: AD-19 wants it visible.
    return 1 if tally.get(FAIL) else 0


if __name__ == "__main__":
    raise SystemExit(main())
