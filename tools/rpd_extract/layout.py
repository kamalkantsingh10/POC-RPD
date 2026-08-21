"""What shape of input the Operator pointed us at, and which halves are present.

An estate has two halves — the repository (RPD) and the Web Catalog — and
either may be absent. This module decides, from the directory layout alone,
which halves are present and under which ``rpd-id``, and refuses anything it
does not recognise.

**Nothing here sniffs content.** The RPD half announces itself with a fixed
path, ``oracle/bi/server/base/`` (AD-20). The catalog half has no equivalent:
its top level is arbitrary user-named folders, its objects are extensionless,
and the nearest thing to a marker — ``_portal/`` for dashboards, ``_filters/``
for saved filters — is a convention inside user folders, not a root signature.

So the catalog half is accepted **because the Operator put it in ``catalog/``**.
Deciding it by inspecting what is inside would be the same class of inference
AD-22 forbids for pairing, arriving one level further down, and a wrong answer
produces a Knowledge Base whose provenance is fiction. If ``catalog/`` holds
something that is not a catalog, extraction reports what it could not read; it
never reclassifies the folder.

No I/O beyond reading directory entries, and no parsing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tools.rpd_extract.core import identifiers as ids

#: The fixed path inside a repository tree that identifies the RPD half.
BASE = ("oracle", "bi", "server", "base")

#: Subdirectory names an Operator uses to declare each half of an estate.
RPD_DIR = "rpd"
CATALOG_DIR = "catalog"

RPD = "rpd"
CATALOG = "catalog"


class LayoutError(ValueError):
    """The input matches no accepted layout. Always names all of them."""


@dataclass(frozen=True)
class Half:
    """One half of one estate, and the act that declared it.

    ``declared_by`` is recorded rather than inferred so the manifest can say
    *how* the Operator said this — AD-22 requires a pairing to be a declaration,
    and a declaration nobody can point at is indistinguishable from a guess.
    """

    rpd_id: str
    kind: str  # RPD | CATALOG
    root: Path
    declared_by: str


@dataclass(frozen=True)
class Layout:
    """Every half found, and the shape that was matched."""

    shape: str
    halves: tuple[Half, ...]

    @property
    def rpd_ids(self) -> list[str]:
        return sorted({half.rpd_id for half in self.halves})

    def halves_of(self, rpd_id: str) -> list[str]:
        """Which halves are present for this ``rpd-id``, in a fixed order."""
        present = {half.kind for half in self.halves if half.rpd_id == rpd_id}
        return [kind for kind in (RPD, CATALOG) if kind in present]

    def is_paired(self, rpd_id: str) -> bool:
        return self.halves_of(rpd_id) == [RPD, CATALOG]

    def root_of(self, rpd_id: str, kind: str) -> Path | None:
        for half in self.halves:
            if half.rpd_id == rpd_id and half.kind == kind:
                return half.root
        return None


ACCEPTED = """accepted layouts:

  1. estate folder, with either half optional  (needs --rpd-id)
       <corpus>/rpd/oracle/bi/server/base/...
       <corpus>/catalog/...

  2. one repository tree, RPD only             (needs --rpd-id)
       <corpus>/oracle/bi/server/base/...

  3. several estates, one folder each          (no --rpd-id; the folder
       <corpus>/<rpd-id>/...                    name IS the rpd-id)
                        ...where each <rpd-id> folder is layout 1 or 2

A BAR archive is not a layout. Unzip it, put content/catalog/ into catalog/,
and supply the repository as MDS XML in rpd/ — a BAR carries a binary .rpd,
which is out of scope. See README.md."""


def _is_repository(path: Path) -> bool:
    try:
        return path.joinpath(*BASE).is_dir()
    except OSError:
        return False


def _is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def _estate_halves(root: Path, rpd_id: str, declared_by: str) -> list[Half]:
    """Halves declared by ``rpd/`` and ``catalog/`` subdirectories."""
    halves: list[Half] = []
    rpd_dir = root / RPD_DIR
    if _is_dir(rpd_dir):
        halves.append(Half(rpd_id, RPD, rpd_dir, declared_by))
    catalog_dir = root / CATALOG_DIR
    if _is_dir(catalog_dir):
        halves.append(Half(rpd_id, CATALOG, catalog_dir, declared_by))
    return halves


def _resolve_one(root: Path, rpd_id: str, declared_by: str) -> list[Half]:
    """Halves for one estate whose ``rpd-id`` is already settled."""
    halves = _estate_halves(root, rpd_id, declared_by)
    if halves:
        return halves
    if _is_repository(root):
        return [Half(rpd_id, RPD, root, declared_by)]
    return []


def resolve(corpus_root: Path | str, rpd_id: str | None = None) -> Layout:
    """Decide which halves the Operator is offering, and under which names.

    Raises :class:`LayoutError` naming every accepted layout when nothing
    matches. It raises rather than returning an empty layout because a run that
    finds nothing must not reach the writer: a Knowledge Base written from no
    input is a directory of empty tables that reads exactly like an estate
    containing nothing.
    """
    corpus_root = Path(corpus_root)
    if not _is_dir(corpus_root):
        raise LayoutError(f"{corpus_root} is not a directory.\n\n{ACCEPTED}")

    if rpd_id is not None:
        ids.validate_rpd_id(rpd_id)
        halves = _resolve_one(corpus_root, rpd_id, "--rpd-id with --corpus")
        if halves:
            shape = "estate" if (corpus_root / RPD_DIR).is_dir() or (
                corpus_root / CATALOG_DIR
            ).is_dir() else "repository"
            return Layout(shape, tuple(halves))
        raise LayoutError(_no_match_message(corpus_root, rpd_id))

    halves: list[Half] = []
    try:
        children = sorted(p for p in corpus_root.iterdir() if p.is_dir())
    except OSError as exc:
        raise LayoutError(f"cannot read {corpus_root}: {exc}\n\n{ACCEPTED}") from None

    for child in children:
        found = _resolve_one(child, child.name, "the folder name under --corpus")
        if not found:
            continue
        # Validated only once a directory has proved to be an estate. Validating
        # every child would reject a corpus root that merely sits beside an
        # unrelated directory whose name is not lower-kebab.
        ids.validate_rpd_id(child.name)
        halves.extend(found)

    if not halves:
        raise LayoutError(_no_match_message(corpus_root, None))
    return Layout("multi", tuple(halves))


def _looks_like_base_dir(path: Path) -> bool:
    """Is this ``base/`` itself, rather than the directory containing it?"""
    try:
        for child in path.iterdir():
            if child.is_dir() and any(child.glob("*.xml")):
                return True
    except OSError:
        return False
    return False


def _no_match_message(corpus_root: Path, rpd_id: str | None) -> str:
    """Explain a mis-aimed --corpus, naming the likely fix before the list.

    Aiming at ``base/`` is the easy mistake, because that is the path the
    documentation shows. Saying only "must contain oracle/bi/server/base" is
    useless to somebody standing in it.
    """
    hint = ""
    if corpus_root.name == "base" or _looks_like_base_dir(corpus_root):
        suggestion = corpus_root
        for _ in BASE:
            suggestion = suggestion.parent
        hint = (
            f"{corpus_root} looks like the 'base' directory itself. --corpus wants "
            f"the directory CONTAINING 'oracle/'.\n       Try:  --corpus "
            f"{suggestion}\n\n"
        )
    elif rpd_id is None and _is_repository(corpus_root):
        hint = (
            f"{corpus_root} is itself a repository tree, so it needs a name. "
            f"Add --rpd-id.\n\n"
        )
    elif rpd_id is not None:
        hint = (
            f"--rpd-id was given, so {corpus_root} must hold rpd/, catalog/, or "
            f"oracle/bi/server/base/ — it holds none of them.\n\n"
        )
    return f"{hint}{corpus_root} matches no accepted layout.\n\n{ACCEPTED}"
