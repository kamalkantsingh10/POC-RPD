"""Survey an OBIEE Web Catalog tree and report what is measurably in it.

A measurement tool, not part of the extractor. It exists because three separate
numbers on this project — catalog object counts, `saw:columnFormula`
occurrences, the styling attribute population — were quoted from surveys that
covered a subdirectory rather than the tree, and nothing made them re-derivable.
A figure nobody can re-measure is a figure nobody has measured.

Reads a catalog directory and writes the measurements the Epic 2 documents cite:
root element types, `xmlVersion` spread including its absence, the attribute and
element vocabulary, `xsi:type` values, every element carrying `@path`, and how
those references resolve against the tree.

Standard library only (NFR13). Run it from the repository root:

    python3 -m tools.catalog_survey --catalog ~/…/obiee_sample_git --section roots
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote_plus

#: Directories that are version control or tooling, not catalog content.
SKIP_DIRS = {".git"}


def decode_segment(segment: str) -> str:
    """Decode one on-disk name into the display name a reference uses.

    ``+`` is a space and ``%XX`` is a byte, in that order — decoding ``%2b``
    first and then folding ``+`` would turn an escaped plus into a space. The
    rule is general: the fixture contains ``co%6dponents``, where ``%6d`` is
    ``m``, so a lookup table of the two examples anyone happens to have seen
    (``%2e`` and ``+``) silently mis-decodes the third.
    """
    return unquote_plus(segment)


def decode_path(relative: Path) -> str:
    """An on-disk relative path as its decoded, ``/``-separated catalog path."""
    return "/".join(decode_segment(part) for part in relative.parts)


#: Leading bytes -> what the file actually is.
#:
#: Non-XML files are classified by content rather than by name, because catalog
#: objects are extensionless: there is no suffix to read, and the extensions
#: that do appear are percent-encoded inside folder names rather than on the
#: files. Classifying by the folder they sit in was tried first and reported
#: every one of them as BI Publisher material, which is wrong for two thirds.
MAGIC = (
    (b"\x89PNG\r\n", "PNG image"),
    (b"\xff\xd8\xff", "JPEG image"),
    (b"GIF87a", "GIF image"),
    (b"GIF89a", "GIF image"),
    (b"%PDF-", "PDF document"),
    (b"{\\rtf", "RTF template"),
    (b"PK\x03\x04", "ZIP container (Office document or archive)"),
    (b"\xd0\xcf\x11\xe0", "OLE compound document (legacy Office)"),
    (b"CWS", "Flash movie"),
    (b"FWS", "Flash movie"),
    (b"data:", "data: URI text"),
)


def classify_bytes(head: bytes) -> str:
    """What a file is, from its leading bytes. '' when nothing matches."""
    for signature, name in MAGIC:
        if head.startswith(signature):
            return name
    return ""


@dataclass
class FileRecord:
    """One file under the catalog root, and what parsing it produced."""

    relative: Path
    decoded: str
    parsed: bool
    root_tag: str = ""
    xml_version: str | None = None
    parse_error: str = ""
    content_kind: str = ""


@dataclass
class Survey:
    """Everything one pass over the tree measured."""

    catalog_root: Path
    files: list[FileRecord] = field(default_factory=list)
    #: qualified root element name -> file count
    roots: collections.Counter = field(default_factory=collections.Counter)
    #: qualified element name -> occurrences, anywhere in any tree
    elements: collections.Counter = field(default_factory=collections.Counter)
    #: attribute local name -> occurrences
    attributes: collections.Counter = field(default_factory=collections.Counter)
    #: xsi:type value -> occurrences
    xsi_types: collections.Counter = field(default_factory=collections.Counter)
    #: qualified element name -> occurrences carrying @path
    path_elements: collections.Counter = field(default_factory=collections.Counter)
    #: @op value -> occurrences
    operators: collections.Counter = field(default_factory=collections.Counter)
    #: root xmlVersion (None when absent) -> file count
    root_versions: collections.Counter = field(default_factory=collections.Counter)
    #: (root tag, root xmlVersion) -> file count
    versions_by_type: collections.Counter = field(default_factory=collections.Counter)
    #: xmlVersion on a NON-root element -> occurrences
    nested_versions: collections.Counter = field(default_factory=collections.Counter)
    #: (root tag, qualified element name) -> occurrences
    elements_by_type: collections.Counter = field(default_factory=collections.Counter)
    #: (root tag, "element@attribute") -> occurrences
    attributes_by_type: collections.Counter = field(default_factory=collections.Counter)
    #: (root tag, root xmlVersion, qualified element name) -> occurrences
    elements_by_version: collections.Counter = field(default_factory=collections.Counter)
    #: (root tag, root xmlVersion, "element@attribute") -> occurrences
    attributes_by_version: collections.Counter = field(default_factory=collections.Counter)
    #: (qualified element name, reference string, owning decoded path)
    references: list[tuple[str, str, str]] = field(default_factory=list)
    #: uri -> prefix, as declared by the documents themselves
    prefixes: dict[str, str] = field(default_factory=dict)
    #: Namespaces some document uses as its DEFAULT namespace, declaring no
    #: prefix. Recorded because a name rendered with a prefix drawn from the
    #: corpus is a convenience, and a reader must be able to tell which roots
    #: never call themselves by it.
    default_namespaces: set = field(default_factory=set)

    @property
    def parsed_files(self) -> list[FileRecord]:
        return [f for f in self.files if f.parsed]

    @property
    def unparsed_files(self) -> list[FileRecord]:
        return [f for f in self.files if not f.parsed]


def _qualify(tag: str, prefixes: dict[str, str]) -> str:
    """``{uri}local`` -> ``prefix:local``, using the document's own prefixes.

    Namespace prefixes are recorded rather than assumed because two elements in
    this fixture share a local name across namespaces — ``saw:reportRef`` and
    ``sawd:reportRef``, 21 and 1722 occurrences — and collapsing them to
    ``reportRef`` would merge a report-scoped reference with a dashboard-scoped
    one.
    """
    if not tag.startswith("{"):
        return tag
    uri, _, local = tag[1:].partition("}")
    prefix = prefixes.get(uri)
    return f"{prefix}:{local}" if prefix else f"{{{uri}}}{local}"


def _uri(tag: str) -> str:
    """The namespace URI of a ``{uri}local`` tag, or '' when there is none."""
    return tag[1:].partition("}")[0] if tag.startswith("{") else ""


def _local(name: str) -> str:
    if name.startswith("{"):
        return name[1:].partition("}")[2]
    return name


#: The two XML Schema instance namespaces present. The 1999 one is a single
#: occurrence and almost certainly a typo in a hand-edited file, but it is
#: recorded rather than corrected — AD-3 does not permit repairing a source.
XSI_NAMESPACES = (
    "http://www.w3.org/2001/XMLSchema-instance",
    "http://www.w3.org/1999/XMLSchema-instance",
)


def _is_xsi_type(raw_key: str) -> bool:
    return any(raw_key == f"{{{uri}}}type" for uri in XSI_NAMESPACES)


def survey(catalog_root: Path) -> Survey:
    """Parse every file under ``catalog_root`` once and count what is there."""
    result = Survey(catalog_root=catalog_root)

    _DISPLAY_PREFIXES.clear()
    result.prefixes = _DISPLAY_PREFIXES

    for path in sorted(catalog_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(catalog_root)
        if SKIP_DIRS.intersection(relative.parts):
            continue
        _survey_file(path, relative, result)

    return result


def _survey_file(path: Path, relative: Path, result: Survey) -> None:
    decoded = decode_path(relative)
    local_prefixes: dict[str, str] = {}
    root_tag = ""
    root_version: str | None = None
    depth = 0

    try:
        for event, payload in ET.iterparse(path, events=("start-ns", "start", "end")):
            if event == "start-ns":
                prefix, uri = payload
                if prefix:
                    local_prefixes.setdefault(uri, prefix)
                    result.prefixes.setdefault(uri, prefix)
                continue
            if event == "end":
                depth -= 1
                payload.clear()
                continue

            element = payload
            # Counted under the canonical ``{uri}local`` name and rendered only
            # at report time. The same element is written prefixed in some
            # documents and default-namespaced in others —
            # ``sawbsc:kpiWatchlistView`` is 10 of one and 5 of the other — so
            # keying on the rendered string splits one root type into two and
            # reports 60 where 59 exist. Namespace plus local name is the only
            # stable identity.
            name = element.tag
            if not local_prefixes.get(_uri(element.tag), "") and _uri(element.tag):
                result.default_namespaces.add(_uri(element.tag))
            is_root = depth == 0
            depth += 1

            if is_root:
                root_tag = name
                root_version = element.attrib.get("xmlVersion")

            result.elements[name] += 1
            result.elements_by_type[(root_tag, name)] += 1
            result.elements_by_version[(root_tag, root_version, name)] += 1

            for raw_key, value in element.attrib.items():
                # Qualified, not local. Collapsing namespaces merges
                # ``xsi:type`` (62,867 occurrences) with an unrelated
                # ``xdoeft:type``, and reports 615 distinct attribute names
                # where 618 exist.
                # Keyed on the raw ``{uri}local`` name, rendered with prefixes
                # only at report time. Two XML Schema instance namespaces are
                # present and both declare the prefix ``xsi``, so keying on the
                # prefix form merges them and reports 617 where 618 exist.
                key = raw_key
                local = _local(raw_key)
                result.attributes[key] += 1
                qualified = f"{name}@{raw_key}"
                result.attributes_by_type[(root_tag, qualified)] += 1
                result.attributes_by_version[(root_tag, root_version, qualified)] += 1
                if _is_xsi_type(raw_key):
                    result.xsi_types[value] += 1
                elif local == "path" and not raw_key.startswith("{"):
                    result.path_elements[name] += 1
                    result.references.append((name, value, decoded))
                elif local == "op" and not raw_key.startswith("{"):
                    result.operators[value] += 1
                elif local == "xmlVersion" and not is_root:
                    result.nested_versions[value] += 1

    except ET.ParseError as exc:
        try:
            with path.open("rb") as handle:
                head = handle.read(16)
        except OSError:
            head = b""
        result.files.append(
            FileRecord(relative, decoded, parsed=False, parse_error=str(exc),
                       content_kind=classify_bytes(head) or "unrecognised")
        )
        return
    except OSError as exc:  # unreadable file; recorded, never fatal
        result.files.append(
            FileRecord(relative, decoded, parsed=False, parse_error=f"unreadable: {exc}")
        )
        return

    result.files.append(
        FileRecord(relative, decoded, parsed=True, root_tag=root_tag,
                   xml_version=root_version)
    )
    result.roots[root_tag] += 1
    result.root_versions[root_version] += 1
    result.versions_by_type[(root_tag, root_version)] += 1


# ---------------------------------------------------------------- resolution


#: A reference beginning with this names the catalog root the tree starts below.
SHARED_ROOT = "/shared/"


#: What a decoded path names on disk. A catalog reference can target either.
OBJECT = "object"
FOLDER = "folder"


@dataclass
class Resolution:
    """How one ``@path`` reference resolved. ``outcome`` is never inferred."""

    element: str
    reference: str
    owner: str
    outcome: str  # exact | case_normalised | ambiguous | unresolved
    target: str = ""
    target_kind: str = ""
    candidates: tuple[str, ...] = ()


def build_index(result: Survey) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Decoded on-disk path -> what it names, plus a case-folded index beside it.

    Folders are indexed alongside objects because the reference vocabulary
    targets both: ``sawd:folderView[@path]`` names a catalog *folder*, and all
    27 of them resolve to a directory. An index of files alone reports every
    one as a dangling reference, which is a false error — and a false error in
    the honesty artifact is worse than a missing feature, because it teaches a
    reader to discount the file.

    What is resolved is therefore recorded with its kind, so a caller expecting
    an object and receiving a folder can say so rather than count it as a hit.
    """
    exact: dict[str, str] = {}
    folded: dict[str, list[str]] = collections.defaultdict(list)
    seen_folders: set[str] = set()

    for record in result.files:
        exact[record.decoded] = OBJECT
        folded[record.decoded.lower()].append(record.decoded)
        # Every ancestor directory of a file is a catalog folder.
        parts = record.decoded.split("/")
        for depth in range(1, len(parts)):
            folder = "/".join(parts[:depth])
            if folder in seen_folders:
                break
            seen_folders.add(folder)
            exact.setdefault(folder, FOLDER)
            folded[folder.lower()].append(folder)

    return exact, {key: sorted(set(value)) for key, value in folded.items()}


def normalise_reference(reference: str, owner: str) -> str:
    """A reference as a path relative to the tree root, or '' if out of tree.

    Three rules, each measured rather than assumed. References are absolute from
    the catalog root while the tree begins one level below it, so ``/shared`` is
    stripped. A reference with no leading ``/`` is relative to the folder of the
    object making it — overwhelmingly a dashboard page naming a sibling page.
    A reference under any other root names content this tree does not contain.
    """
    if reference.startswith(SHARED_ROOT):
        return reference[len(SHARED_ROOT):]
    if reference.startswith("/"):
        return ""  # another catalog root; absent from this tree by definition
    owner_folder = owner.rsplit("/", 1)[0] if "/" in owner else ""
    return f"{owner_folder}/{reference}" if owner_folder else reference


def resolve_all(result: Survey) -> list[Resolution]:
    """Resolve every ``@path`` reference; record how each one resolved.

    Exact first, case-insensitive second, and which one happened is recorded per
    reference. Folding case is a judgement — AD-3 does not permit making it in
    silence, and on an estate that distinguishes case it would join two
    different objects with nothing downstream able to detect it. Refusing to
    fold at all is equally dishonest here: exact matching resolves 11 of 4171
    references in this fixture, and reporting 99.7% of a real catalog as broken
    is not a more accurate answer.
    """
    exact, folded = build_index(result)
    resolutions: list[Resolution] = []

    for element, reference, owner in result.references:
        candidate = normalise_reference(reference, owner)
        if not candidate:
            resolutions.append(Resolution(element, reference, owner, "unresolved"))
            continue
        if candidate in exact:
            resolutions.append(
                Resolution(element, reference, owner, "exact", candidate,
                           exact[candidate])
            )
            continue
        matches = folded.get(candidate.lower(), [])
        if len(matches) == 1:
            resolutions.append(
                Resolution(element, reference, owner, "case_normalised", matches[0],
                           exact[matches[0]])
            )
        elif len(matches) > 1:
            resolutions.append(
                Resolution(element, reference, owner, "ambiguous",
                           candidates=tuple(sorted(matches)))
            )
        else:
            resolutions.append(Resolution(element, reference, owner, "unresolved"))

    return resolutions


# -------------------------------------------------------------------- styling


#: Substrings that make an attribute name a styling or formatting attribute.
#:
#: A membership rule stated in one place and applied by one function, because
#: the alternative — a hand-listed set — cannot be re-derived, and an attribute
#: excluded by a rule nobody wrote down is indistinguishable from one that was
#: overlooked. That is the exact failure FR-34's exclusion has to be safe from.
STYLING_MARKERS = (
    "align", "bgcolor", "border", "color", "fmt", "font", "format", "height",
    "indent", "padding", "style", "width", "wraptext",
)

#: Names the rule above catches that are **not** styling, each with the reason.
#:
#: Every entry was decided by reading the values the attribute actually carries
#: in the fixture, not from the name. FR-34 draws the line at *visual identity*
#: and puts "any difference in displayed data, column set, filter behaviour, or
#: ordering" on the defect side — so an attribute that changes what a reader
#: sees as **data** stays in scope however format-ish its name looks.
#:
#: The decision is recorded beside the name because an attribute excluded by a
#: rule nobody wrote down is indistinguishable from one that was overlooked.
STYLING_EXCEPTIONS = {
    "fmt": "values are only 'text' and 'html' — whether cell content is "
           "interpreted as markup or shown literally. Changes displayed data, "
           "not appearance (12,124 occurrences)",
    "textFormat": "'html' / 'plain' / 'plainNBSP' / 'imageURL' — same "
                  "interpretation switch as fmt",
    "customFormat": "number and date masks such as '#.00 M' and 'dd-MMM-yy'. "
                    "A mask decides whether 1500000 reads as '1.50 M'",
    "formatMask": "a number mask, same class as customFormat",
    "biFormat": "'dateODBC' — how a date value is encoded",
    "defaultFormat": "'analyze' / 'html' / 'pdf' — which delivery format a link "
                     "opens in. Report behaviour, not visual identity",
    "outputFormat": "the delivery formats a report offers, e.g. "
                    "'html,pdf,rtf,xlsx,pptx'. Behaviour, not appearance",
    "format": "'html' / 'pdf' / 'excel' — a delivery format",
    "formatOutputType": "'delimited' — a delivery encoding",
    "renderFormat": "'default' — a delivery selector",
}

#: Styling attributes whose exclusion has a consequence a reader must know.
#:
#: These stay excluded — they are CSS and geometry — but each can hide content,
#: and a hidden column is a column-set difference, which FR-34 calls a defect.
#: Recorded so the exclusion is not mistaken for "these cannot matter".
STYLING_CAVEATS = {
    "style": "138 of 1003 values are 'display:none'. Excluded as CSS, but "
             "styling can hide content, and hidden content is a column-set "
             "difference rather than a visual one",
    "height": "565 of 4237 values are '0', which hides as effectively as "
              "display:none",
}


def is_styling(name: str) -> bool:
    """Whether an attribute name is styling under the rule above."""
    name = _local(name)
    if name in STYLING_EXCEPTIONS:
        return False
    lowered = name.lower()
    return any(marker in lowered for marker in STYLING_MARKERS)


# ------------------------------------------------------------------- products


#: Namespace URI prefix -> the product that writes it.
#:
#: Root types are classified by namespace rather than by a list of names,
#: because the list has 59 entries and around thirty are one-off business
#: documents. A reader meeting ``xdm:dataModel`` in the unmodelled-types report
#: needs to learn it is a **different product sharing the catalog tree**, not a
#: catalog construct the adapter failed to model.
PRODUCTS = (
    ("com.siebel.analytics.web", "OBIEE catalog"),
    # Conditions are an OBIEE construct in Oracle's newer namespace form;
    # ``cond:conditionRef[@path]`` resolves against the catalog tree like any
    # other catalog reference.
    ("com.oracle.bi", "OBIEE catalog"),
    ("http://xmlns.oracle.com/oxp", "BI Publisher"),
    ("http://xmlns.oracle.com/iby", "BI Publisher"),
    ("http://www.w3.org/1999/XSL/Transform", "XSLT stylesheet"),
    ("urn:oasis:names:tc:xliff", "XLIFF translation"),
    ("http://ns.adobe.com/xfdf", "Adobe form data"),
)

#: Root element names with no namespace at all. These are raw data exports and
#: business documents that happen to live in the catalog tree.
NO_NAMESPACE_PRODUCT = "raw data or business document (no namespace)"


def product_of(root_tag: str) -> str:
    """Which product writes this root element, read from its namespace URI.

    Never guessed from the name: ``saw:report`` and the BI Publisher ``report``
    share a local name and are different products.
    """
    uri = _uri(root_tag)
    return _match_product(uri) if uri else NO_NAMESPACE_PRODUCT


def _match_product(uri: str) -> str:
    for marker, product in PRODUCTS:
        if uri.startswith(marker):
            return product
    return f"unclassified namespace {uri}"


# --------------------------------------------------------------------- report


def display(name: str) -> str:
    """A canonical ``{uri}local`` name rendered for a reader.

    Prefixes come from the corpus's own declarations. Where no document
    declares one, the URI is shown rather than a prefix invented for the
    occasion. Handles the ``element@attribute`` composite keys too.
    """
    if "@" in name and not name.startswith("@"):
        element, _, attribute = name.partition("@")
        return f"{display(element)}@{display(attribute)}"
    return _qualify(name, _DISPLAY_PREFIXES)


#: Filled in by :func:`survey` so report rendering can use the document's own
#: prefixes without threading the map through every report function.
_DISPLAY_PREFIXES: dict[str, str] = {}


def _table(rows: list[tuple[str, int]], headers: tuple[str, str]) -> str:
    lines = [f"| {headers[0]} | {headers[1]} |", "|---|---:|"]
    lines += [f"| `{display(name)}` | {count} |" for name, count in rows]
    return "\n".join(lines)


def report_files(result: Survey) -> str:
    unparsed = result.unparsed_files
    kinds = collections.Counter(f.content_kind for f in unparsed)
    # Container membership is tested on the DECODED path. On disk the folder is
    # named ``sales+history+report%2exdo``, so a test against the raw name finds
    # no ``.xdo`` anywhere and reports zero.
    containers = collections.Counter()
    for record in unparsed:
        parts = record.decoded.split("/")
        parent = parts[-2] if len(parts) > 1 else "(root)"
        if any(p.endswith(".xdo") for p in parts):
            containers["*.xdo (BI Publisher report)"] += 1
        elif any(p.endswith(".xdm") for p in parts):
            containers["*.xdm (BI Publisher data model)"] += 1
        elif parent == "screenshots":
            containers["screenshots/ (VA project thumbnails)"] += 1
        else:
            containers["elsewhere"] += 1
    out = [
        f"files:            {len(result.files)}",
        f"parse as XML:     {len(result.parsed_files)}",
        f"do not parse:     {len(unparsed)}",
        f"distinct roots:   {len(result.roots)}",
        f"distinct attrs:   {len(result.attributes)} "
        f"({sum(result.attributes.values())} occurrences)",
        "",
        "Non-XML files by content:",
        _table(kinds.most_common(), ("Content", "Files")),
        "",
        "Non-XML files by containing folder:",
        _table(containers.most_common(), ("Folder", "Files")),
    ]
    return "\n".join(out)


def report_roots(result: Survey) -> str:
    return _table(result.roots.most_common(), ("Root element", "Files"))


def report_versions(result: Survey) -> str:
    rows = [
        (version or "(none)", count)
        for version, count in result.root_versions.most_common()
    ]
    out = [_table(rows, ("`xmlVersion` on root", "Objects"))]
    if result.nested_versions:
        out.append("\nOn nested elements only:")
        out.append(_table(result.nested_versions.most_common(),
                          ("`xmlVersion`", "Occurrences")))
    return "\n".join(out)


def report_styling(result: Survey) -> str:
    styling = {n: c for n, c in result.attributes.items() if is_styling(n)}
    structural = {n: c for n, c in result.attributes.items() if not is_styling(n)}
    out = [
        f"styling:      {len(styling)} names, {sum(styling.values())} occurrences",
        f"structural:   {len(structural)} names, {sum(structural.values())} occurrences",
        f"total:        {len(result.attributes)} names, "
        f"{sum(result.attributes.values())} occurrences",
        "",
        _table(sorted(styling.items(), key=lambda kv: -kv[1])[:20],
               ("Styling attribute", "Occurrences")),
    ]
    return "\n".join(out)


def report_paths(result: Survey) -> str:
    resolutions = resolve_all(result)
    by_element: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    for item in resolutions:
        by_element[item.element][item.outcome] += 1

    lines = [
        "| Element | Total | Exact | Case-insensitive only | Ambiguous | Unresolved |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for element in sorted(by_element, key=lambda e: -sum(by_element[e].values())):
        counts = by_element[element]
        lines.append(
            f"| `{element}` | {sum(counts.values())} | {counts['exact']} | "
            f"{counts['case_normalised']} | {counts['ambiguous']} | "
            f"{counts['unresolved']} |"
        )
    totals = collections.Counter()
    for counts in by_element.values():
        totals.update(counts)
    lines.append(
        f"| **Total** | **{sum(totals.values())}** | **{totals['exact']}** | "
        f"**{totals['case_normalised']}** | **{totals['ambiguous']}** | "
        f"**{totals['unresolved']}** |"
    )

    kinds = collections.Counter(
        (item.element, item.target_kind) for item in resolutions if item.target_kind
    )
    lines.append("\nWhat resolved references point at:")
    lines.append(_table(
        [(f"{element} -> {kind}", count)
         for (element, kind), count in kinds.most_common()],
        ("Element and target kind", "References"),
    ))

    roots = collections.Counter()
    for item in resolutions:
        if item.outcome != "unresolved":
            continue
        first = item.reference.lstrip("/").split("/", 1)[0] if "/" in item.reference else "relative"
        roots[first if item.reference.startswith("/") else "relative"] += 1
    lines.append("\nUnresolved by first path segment:")
    lines.append(_table(roots.most_common(), ("Segment", "Unresolved")))
    return "\n".join(lines)


def report_xsi_types(result: Survey) -> str:
    return _table(result.xsi_types.most_common(30), ("`xsi:type`", "Occurrences"))


def report_operators(result: Survey) -> str:
    return _table(result.operators.most_common(30), ("`@op`", "Occurrences"))


def report_elements(result: Survey) -> str:
    return _table(result.elements.most_common(60), ("Element", "Occurrences"))


def report_path_elements(result: Survey) -> str:
    return _table(result.path_elements.most_common(), ("Element", "With `@path`"))


def report_json(result: Survey) -> str:
    """Every counter, machine-readable, for a document generator to consume."""
    return json.dumps(
        {
            "files": len(result.files),
            "parsed": len(result.parsed_files),
            "unparsed": len(result.unparsed_files),
            "roots": {display(r): c for r, c in result.roots.most_common()},
            "root_versions": {
                (v or ""): c for v, c in result.root_versions.most_common()
            },
            "versions_by_type": {
                f"{display(root)}|{version or ''}": count
                for (root, version), count in sorted(
                    result.versions_by_type.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")
                )
            },
            "elements": {display(e): c for e, c in result.elements.most_common()},
            "elements_by_type": {
                f"{display(root)}|{display(name)}": count
                for (root, name), count in sorted(result.elements_by_type.items())
            },
            "attributes_by_type": {
                f"{display(root)}|{display(name)}": count
                for (root, name), count in sorted(result.attributes_by_type.items())
            },
            # Raw ``{uri}local`` keys, not prefix-rendered: two namespaces
            # here declare the prefix ``xsi``, and rendering would merge them
            # into 617 keys where 618 attributes exist.
            "attributes": dict(result.attributes.most_common()),
            "xsi_types": dict(result.xsi_types.most_common()),
            "operators": dict(result.operators.most_common()),
            "path_elements": {display(e): c for e, c in result.path_elements.most_common()},
            "prefixes": result.prefixes,
        },
        indent=2,
        sort_keys=False,
    )


def report_products(result: Survey) -> str:
    """Root types grouped by the product that writes them."""
    by_product: dict[str, list[tuple[str, int]]] = collections.defaultdict(list)
    for root, count in result.roots.most_common():
        by_product[product_of(root)].append((root, count))

    lines = []
    if result.default_namespaces:
        lines.append(
            "\nNamespaces some document uses as its **default** namespace, "
            "declaring no prefix on the element itself:\n"
        )
        for uri in sorted(result.default_namespaces):
            prefix = result.prefixes.get(uri)
            lines.append(
                f"- `{uri}`" + (f" — rendered `{prefix}:` from other documents"
                                if prefix else " — no prefix declared anywhere")
            )
    for product in sorted(by_product, key=lambda p: -sum(c for _, c in by_product[p])):
        entries = by_product[product]
        lines.append(
            f"\n**{product}** — {len(entries)} root types, "
            f"{sum(c for _, c in entries)} files\n"
        )
        lines.append(_table(entries, ("Root element", "Files")))
    return "\n".join(lines)


def report_version_drift(result: Survey) -> str:
    """Elements and attributes present under some `xmlVersion` and not others.

    Absence of a version is treated as a version — it is the second most common
    state, and excluding it would compare only the 62% of roots that declare one.

    **A construct absent from a small population is weak evidence.** Where one
    version covers 1504 objects and another 103, most of what appears "only
    under" the large one is a rare construct that the small sample never
    contained. Reported in both directions, with the populations beside them, so
    a reader can tell which claim is load-bearing: a construct present only
    under the *smaller* population cannot be explained by sampling, and is the
    genuine version-conditional finding.
    """
    versions_of: dict[str, set] = collections.defaultdict(set)
    for (root, version), _ in result.versions_by_type.items():
        versions_of[root].add(version)

    lines = []
    for root in sorted(versions_of, key=lambda r: -result.roots[r]):
        versions = sorted(versions_of[root], key=lambda v: -result.versions_by_type[(root, v)])
        if len(versions) < 2:
            continue
        files = {v: result.versions_by_type[(root, v)] for v in versions}
        present: dict[str, set] = {}
        for version in versions:
            present[version] = {
                name for (r, v, name) in result.elements_by_version
                if r == root and v == version
            } | {
                name for (r, v, name) in result.attributes_by_version
                if r == root and v == version
            }
        everywhere = set.intersection(*present.values())
        somewhere = set.union(*present.values())
        largest = versions[0]

        lines.append(
            f"\n**`{display(root)}`** — "
            + ", ".join(f"`{v or '(none)'}` ({files[v]} objects)" for v in versions)
            + f"\n\n{len(everywhere)} constructs appear under every version; "
            f"{len(somewhere) - len(everywhere)} under some only.\n"
        )

        informative = sorted(
            name for name in somewhere
            if name not in present[largest]
        )
        if informative:
            lines.append(
                f"Present under a smaller population but **absent from "
                f"`{largest or '(none)'}` ({files[largest]} objects)** — not "
                f"explainable by sampling:\n"
            )
            for name in informative[:30]:
                carriers = [v or "(none)" for v in versions if name in present[v]]
                lines.append(f"- `{display(name)}` — only under {', '.join(carriers)}")
            if len(informative) > 30:
                lines.append(f"- …and {len(informative) - 30} more")
        else:
            lines.append(
                f"Every construct seen anywhere also appears under "
                f"`{largest or '(none)'}`, the largest population. Nothing here "
                f"is version-conditional in the direction sampling cannot explain."
            )

        only_largest = len(present[largest] - everywhere)
        lines.append(
            f"\n{only_largest} further constructs appear only under "
            f"`{largest or '(none)'}`. With {files[largest]} objects against "
            f"{min(files[v] for v in versions[1:])}, that is what a rare "
            f"construct missing from a small sample looks like, and is reported "
            f"as sampling rather than as drift."
        )
    return "\n".join(lines) or "No root type carries more than one version."


def report_vocabulary(result: Survey) -> str:
    """Element paths and attributes per object type, with occurrence counts."""
    lines = []
    for root, files in result.roots.most_common():
        elements = sorted(
            ((name, count) for (r, name), count in result.elements_by_type.items()
             if r == root),
            key=lambda kv: -kv[1],
        )
        attributes = sorted(
            ((name, count) for (r, name), count in result.attributes_by_type.items()
             if r == root and not is_styling(name.partition("@")[2])),
            key=lambda kv: -kv[1],
        )
        lines.append(f"\n### `{root}` — {files} files\n")
        lines.append(_table(elements[:40], ("Element", "Occurrences")))
        lines.append("")
        lines.append(_table(attributes[:40], ("Structural attribute", "Occurrences")))
    return "\n".join(lines)


SECTIONS = {
    "files": report_files,
    "roots": report_roots,
    "versions": report_versions,
    "styling": report_styling,
    "paths": report_paths,
    "types": report_xsi_types,
    "operators": report_operators,
    "elements": report_elements,
    "path-elements": report_path_elements,
    "products": report_products,
    "version-drift": report_version_drift,
    "vocabulary": report_vocabulary,
    "json": report_json,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="catalog_survey",
        description="Measure an OBIEE Web Catalog tree. Reports what is there, "
                    "never what should be.",
    )
    parser.add_argument("--catalog", required=True, type=Path,
                        help="catalog root directory")
    parser.add_argument("--section", action="append", choices=sorted(SECTIONS),
                        help="report section; repeatable. Default: all but json")
    args = parser.parse_args(argv)

    if not args.catalog.is_dir():
        print(f"error: {args.catalog} is not a directory", file=sys.stderr)
        return 2

    result = survey(args.catalog)
    wanted = args.section or [s for s in SECTIONS if s != "json"]
    # ``json`` is meant to be piped into another program, so it is emitted bare.
    if wanted == ["json"]:
        print(report_json(result))
        return 0
    for name in wanted:
        print(f"\n## {name}\n")
        print(SECTIONS[name](result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
