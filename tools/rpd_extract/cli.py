"""Command line entry point.

No installation step and no build (AD-16): run it straight from a checkout as
``python -m tools.rpd_extract.cli``.

Deliberately absent: any argument that narrows extraction to one Dashboard or
Subject Area. FR-9 makes the Knowledge Base estate-wide, because per-Dashboard
extraction would make cross-Dashboard reuse undetectable and cause metric drift.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.rpd_extract.adapters.inbound import mds_xml
from tools.rpd_extract.core import identifiers
from tools.rpd_extract.adapters.outbound import knowledge_base


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rpd_extract",
        description=(
            "Extract an OBIEE repository into the Estate Knowledge Base. "
            "The corpus root holds one directory per rpd-id; that directory "
            "name IS the rpd-id, declared by the Operator (AD-7)."
        ),
    )
    parser.add_argument("--corpus", required=True, type=Path,
                        help="corpus root containing <rpd-id>/oracle/bi/server/base/")
    parser.add_argument("--out", required=True, type=Path,
                        help="output directory for the Knowledge Base")
    parser.add_argument("--rpd-id", default=None,
                        help="declare the rpd-id when --corpus IS one repository "
                             "tree (lower-kebab). Omit when --corpus holds one "
                             "folder per repository.")
    parser.add_argument("--clean", action="store_true",
                        help="delete existing Knowledge Base tables in --out before "
                             "writing. Refuses if the directory is non-empty and has "
                             "no manifest.csv")
    parser.add_argument("--timestamp", default=None,
                        help="override the manifest timestamp (for reproducible tests)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.clean:
        try:
            removed = knowledge_base.clean(args.out)
        except knowledge_base.NotAKnowledgeBase as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"cleaned:  {len(removed)} table(s) removed from {args.out}")

    try:
        estate = mds_xml.load(args.corpus, args.rpd_id)
    except mds_xml.CorpusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except identifiers.IdentifierError as exc:
        # Almost always the corpus root pointing at raw clones rather than the
        # clean set. A traceback here would bury a one-line fix.
        print(f"error: {exc}", file=sys.stderr)
        print(
            "\nhint: --corpus must name the directory CONTAINING one folder per "
            "rpd-id,\n      where each folder holds oracle/bi/server/base/. "
            "Pointing it at raw\n      clones fails, because their names are not "
            "valid rpd-ids.\n      See README.md §2 for building the clean set.",
            file=sys.stderr,
        )
        return 2

    knowledge_base.write(
        estate, args.out, corpus_root=str(args.corpus), timestamp=args.timestamp
    )

    parsed = sum(c["parsed"] for c in estate.coverage.values())
    print(f"rpd-ids:  {', '.join(estate.rpd_ids)}")
    print(f"parsed:   {parsed} objects")
    print(f"gaps:     {len(estate.unparsed)} not modelled  -> {args.out}/unparsed.csv")
    print(f"errors:   {len(estate.errors)}                 -> {args.out}/errors.csv")
    print(f"written:  {args.out}")
    # Errors are reported, not fatal: AD-3 says record and continue. The exit
    # code makes them scriptable without changing that.
    return 3 if estate.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
