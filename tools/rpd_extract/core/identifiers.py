"""Knowledge Base identifiers.

Format is fixed by AD-7: ``<rpd-id>::<layer>::<object-path>``. The ``rpd-id`` is
declared by the Operator — here, by the corpus directory name they chose — and
is never derived from a filename, a timestamp, or a content hash, because all
three change without the repository changing.

Core module: no I/O, and no concept from any serialisation (AD-20).
"""

from __future__ import annotations

import re

SEPARATOR = "::"

#: The three RPD layers, plus two groupings for objects that belong to none.
PHYSICAL = "phys"
BUSINESS_MODEL = "bmm"
PRESENTATION = "pres"
SECURITY = "sec"
VARIABLE = "var"

LAYERS = frozenset({PHYSICAL, BUSINESS_MODEL, PRESENTATION, SECURITY, VARIABLE})

_RPD_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class IdentifierError(ValueError):
    """An identifier could not be built or parsed. Always names the offender."""


def validate_rpd_id(rpd_id: str) -> str:
    """Lower-kebab, per the Spine's naming convention."""
    if not _RPD_ID.match(rpd_id):
        raise IdentifierError(
            f"rpd-id {rpd_id!r} is not lower-kebab. Use e.g. 'my-estate'. It is "
            f"declared by the Operator — as the --rpd-id argument, or as a corpus "
            f"directory name — and becomes the permanent prefix of every identifier, "
            f"so it must be stable and readable."
        )
    return rpd_id


def make_id(rpd_id: str, layer: str, *parts: str) -> str:
    """Build ``<rpd-id>::<layer>::<part>.<part>…``.

    Parts are joined with ``.`` in the order given — container, then object,
    then member. Empty parts are refused rather than silently collapsed: a
    missing container would produce an identifier that looks valid and points
    nowhere.
    """
    validate_rpd_id(rpd_id)
    if layer not in LAYERS:
        raise IdentifierError(f"unknown layer {layer!r}; expected one of {sorted(LAYERS)}")
    if not parts:
        raise IdentifierError(f"{rpd_id}::{layer}:: has no object path")
    for index, part in enumerate(parts):
        if not part or not part.strip():
            raise IdentifierError(
                f"{rpd_id}::{layer}:: object path part {index} is empty; "
                f"parts={parts!r}. Refusing to build an identifier that resolves "
                f"to nothing."
            )
    return f"{rpd_id}{SEPARATOR}{layer}{SEPARATOR}{'.'.join(parts)}"


def parse_id(row_id: str) -> tuple[str, str, str]:
    """Split an identifier back into ``(rpd_id, layer, object_path)``."""
    pieces = row_id.split(SEPARATOR)
    if len(pieces) != 3:
        raise IdentifierError(
            f"{row_id!r} is not a qualified identifier; expected "
            f"<rpd-id>{SEPARATOR}<layer>{SEPARATOR}<object-path>"
        )
    rpd_id, layer, path = pieces
    validate_rpd_id(rpd_id)
    if layer not in LAYERS:
        raise IdentifierError(f"{row_id!r} has unknown layer {layer!r}")
    return rpd_id, layer, path
