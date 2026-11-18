"""Command line entry point.

No installation step and no build (AD-16): run it straight from a checkout as
``python -m tools.rpd_extract.cli``.

Deliberately absent: any argument that narrows extraction to one Dashboard or
Subject Area. FR-9 makes the Knowledge Base estate-wide, because per-Dashboard
extraction would make cross-Dashboard reuse undetectable and cause metric drift.

Also deliberately absent: a BAR code path. A BAR is a zip in front of the two
adapters we already have, and it carries a **binary** ``.rpd``, which AD-20 puts
out of scope. Unpacking it is an Operator instruction, documented in README.md,
not a third serialisation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.rpd_extract import layout
from tools.rpd_extract.adapters.inbound import catalog_xml, mds_xml
from tools.rpd_extract.adapters.outbound import knowledge_base
from tools.rpd_extract.core import identifiers, report_lineage
from tools.rpd_extract.core.model import Estate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rpd_extract",
        description=(
            "Extract an OBIEE estate into the Estate Knowledge Base. An estate "
            "is a repository (MDS XML), a Web Catalog, or both — and pairing "
            "them is something the Operator declares by putting them in one "
            "folder, never something the tool infers (AD-22)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=layout.ACCEPTED,
    )
    parser.add_argument("--corpus", required=True, type=Path,
                        help="the estate folder, repository tree, or directory "
                             "of estates. See the layouts listed below.")
    parser.add_argument("--out", required=True, type=Path,
                        help="output directory for the Knowledge Base")
    parser.add_argument("--rpd-id", default=None,
                        help="declare the rpd-id when --corpus IS one estate "
                             "(lower-kebab). Omit when --corpus holds one "
                             "folder per estate.")
    parser.add_argument("--clean", action="store_true",
                        help="delete existing Knowledge Base tables in --out before "
                             "writing. Refuses if the directory is non-empty and has "
                             "no manifest.csv")
    parser.add_argument("--timestamp", default=None,
                        help="override the manifest timestamp (for reproducible tests)")
    return parser


def extract(found: layout.Layout) -> Estate:
    """Read every half the Operator supplied into one Estate."""
    estate = Estate()
    estate.rpd_ids = found.rpd_ids
    for rpd_id in found.rpd_ids:
        estate.halves_present[rpd_id] = found.halves_of(rpd_id)

    for half in found.halves:
        if half.kind == layout.RPD:
            estate.merge(mds_xml.load(half.root, half.rpd_id))
        else:
            estate.merge(catalog_xml.load(half.root, half.rpd_id))

    # Both after the merge, for the same reason: neither adapter can see the
    # other half. Report lineage joins the two by name (FR-7, AD-23), and only
    # ever for halves the Operator declared as one estate (AD-22).
    report_lineage.resolve(estate)
    estate.check_identifier_uniqueness()
    return estate


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Resolved BEFORE anything is deleted or written. A layout that matches
    # nothing must leave the output directory exactly as it found it: a
    # half-written Knowledge Base, or a cleaned one with nothing to replace it,
    # reads as an estate containing very little rather than as a failed run.
    try:
        found = layout.resolve(args.corpus, args.rpd_id)
    except (layout.LayoutError, identifiers.IdentifierError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        estate = extract(found)
    except (mds_xml.CorpusError, catalog_xml.CatalogError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except identifiers.IdentifierError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.clean:
        try:
            removed = knowledge_base.clean(args.out)
        except knowledge_base.NotAKnowledgeBase as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"cleaned:  {len(removed)} table(s) removed from {args.out}")

    knowledge_base.write(
        estate, args.out, corpus_root=str(args.corpus), timestamp=args.timestamp
    )

    parsed = sum(c["parsed"] for c in estate.coverage.values())
    print(f"rpd-ids:  {', '.join(estate.rpd_ids)}")
    for rpd_id in estate.rpd_ids:
        halves = estate.halves_present.get(rpd_id) or ["none"]
        print(f"  {rpd_id}: {' + '.join(halves)}")
    print(f"parsed:   {parsed} objects")
    print(f"gaps:     {len(estate.unparsed)} not modelled  -> {args.out}/unparsed.csv")
    print(f"errors:   {len(estate.errors)}                 -> {args.out}/errors.csv")
    print(f"written:  {args.out}")
    # Errors are reported, not fatal: AD-3 says record and continue. The exit
    # code makes them scriptable without changing that.
    return 3 if estate.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
