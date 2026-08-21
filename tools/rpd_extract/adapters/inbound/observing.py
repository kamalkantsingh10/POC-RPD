"""Parse trees that record what the parsers actually read from them.

Shared by both inbound adapters. This is the mechanism behind `unparsed.csv`'s
`unread_attribute` / `unread_element` / `unread_text` rows, and the reason those
rows can be trusted: the audit does not consult a declaration of what each
parser is *supposed* to read, it observes what the code *did* read on this run.

That distinction is not academic. The audit was previously driven by a
hand-maintained list, and six of its entries had drifted from the code — one of
them, ``PrivilegePackage@userRef``, silenced three privilege grants to named
users while reporting the file as fully understood. A declaration records an
intention and can disagree with the code. An observation cannot.

Standard library only (NFR13).
"""

from __future__ import annotations

import collections
import xml.etree.ElementTree as ET
from collections.abc import Callable


class RecordingAttrib(dict):
    """An attribute map that remembers which keys the parsers asked for.

    Only the two accessors a parser uses record. ``keys``/``items``/iteration
    stay silent so the audit can inspect what is *present* without that
    inspection counting as a read.
    """

    __slots__ = ("owner",)

    def __init__(self, source, owner: "Observed") -> None:
        super().__init__(source)
        self.owner = owner

    def get(self, key, default=None):
        self.owner.attributes_read.add(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self.owner.attributes_read.add(key)
        return super().__getitem__(key)


class Observed(ET.Element):
    """An element that records what the parsers actually took from it."""

    def __init__(self, tag, attrib):
        super().__init__(tag, {})
        self.attributes_read: set[str] = set()
        self.text_read = False
        self.sought = False
        self.attrib = RecordingAttrib(attrib, self)


def observing_parser() -> ET.XMLParser:
    return ET.XMLParser(target=ET.TreeBuilder(element_factory=Observed))


def read_text(element: ET.Element | None) -> str:
    """Verbatim text. No stripping — FR-2 forbids reformatting anywhere.

    The single chokepoint for text access, which is what lets the audit observe
    it: every parser reads element text through here.
    """
    if element is None:
        return ""
    # Marked before the empty check: asking an element for text that turns out to
    # be absent is still a read. Marking only non-empty text would report every
    # empty container as content we ignored.
    if isinstance(element, Observed):
        element.text_read = True
    if element.text is None:
        return ""
    return element.text


def sought(element: ET.Element) -> ET.Element:
    """Mark that a parser looked for this element, whatever it took from it."""
    if isinstance(element, Observed):
        element.sought = True
    return element


def audit_unread(
    trees: list[tuple[str, str, ET.Element]],
    estate,
    handled: set[str],
    *,
    tag_of: Callable[[ET.Element], str],
    out_of_scope: Callable[[str, str], bool] = lambda tag, attribute: False,
    out_of_scope_kind: str = "",
) -> None:
    """Report source content the parsers never took, observed not declared.

    Whole-object honesty is not enough. An object can parse "successfully" while
    attributes, child elements and text on it are discarded without a word — the
    silent omission NFR7 names as the primary failure mode, one level below
    where AD-3 was watching.

    Reachability is computed over the real tree rather than by tag name, so a
    tag read in one context is not assumed read in another. A container counts
    as traversed when anything beneath it was read — otherwise every wrapper the
    parsers pass through would be reported as a gap.

    ``out_of_scope`` names content excluded by a **scope decision** rather than
    missed. Styling is the case that needs it: 97,498 attribute occurrences that
    FR-34 puts outside the product's claim would otherwise fill `unparsed.csv`
    and bury the real signal. Excluded content is still recorded — under its own
    kind, counted, once per (type, name) — because an exclusion that leaves no
    trace is indistinguishable from an oversight.

    Drift now fails safe in the only direction left: a branch this corpus never
    exercises reports a gap that is merely noise, never silence.
    """
    gaps: dict[tuple[str, str, str], int] = collections.Counter()
    excluded: dict[tuple[str, str, str], int] = collections.Counter()
    reached: dict[int, bool] = {}

    def touched(element: ET.Element) -> bool:
        if isinstance(element, Observed):
            return bool(element.attributes_read) or element.text_read or element.sought
        return False

    def mark(element: ET.Element) -> bool:
        """Was anything in this subtree read? Computed once, bottom-up."""
        below = [mark(child) for child in element]
        here = touched(element) or any(below)
        reached[id(element)] = here
        return here

    def visit(rpd_id: str, object_type: str, element: ET.Element) -> None:
        tag = tag_of(element)
        # An element nothing in the subtree touched is unhandled as a whole. A
        # wrapper the parsers walked through is not, even though nothing was
        # read off the wrapper itself.
        if not reached[id(element)]:
            gaps[(rpd_id, object_type, tag)] += 1
        # Reported at every level regardless, including inside an unhandled
        # subtree: rolling a branch up to its root hides what is in it.
        present = set(dict.keys(element.attrib))
        read = element.attributes_read if isinstance(element, Observed) else set()
        for attribute in sorted(present - read):
            if out_of_scope(tag, attribute):
                excluded[(rpd_id, object_type, f"{tag}@{attribute}")] += 1
            else:
                gaps[(rpd_id, object_type, f"{tag}@{attribute}")] += 1
        text = element.text or ""
        if text.strip() and isinstance(element, Observed) and not element.text_read:
            gaps[(rpd_id, object_type, f"{tag}#text")] += 1
        for child in element:
            visit(rpd_id, object_type, child)

    for rpd_id, object_type, root in trees:
        if object_type not in handled:
            continue  # unmodelled types are already reported whole
        mark(root)
        visit(rpd_id, object_type, root)

    for (rpd_id, object_type, detail), occurrences in sorted(gaps.items()):
        if "@" in detail:
            kind = "unread_attribute"
        elif detail.endswith("#text"):
            kind = "unread_text"
        else:
            kind = "unread_element"
        estate.record_gap(rpd_id, kind, object_type, detail, occurrences)

    for (rpd_id, object_type, detail), occurrences in sorted(excluded.items()):
        estate.record_gap(rpd_id, out_of_scope_kind, object_type, detail, occurrences)
