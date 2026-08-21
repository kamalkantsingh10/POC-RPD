"""Inbound adapter: OBIEE Web Catalog XML.

The Web Catalog is the **report layer** store — Dashboards, pages, Analyses,
filters, prompts and saved filters — and it is a different store from the RPD,
read under identifier layer ``cat`` (AD-22). This adapter is the only place its
concepts exist; everything handed to the core is expressed in Knowledge Base
identifiers.

Three things make it a different problem from MDS XML, each measured rather
than assumed:

* **References are by path, not GUID.** Epic 1's mechanic — index every
  ``mdsid``, resolve ``#fragment`` — does not transfer. Resolution is string
  normalisation over decoded on-disk paths.
* **Objects are extensionless**, so every file must be attempted and 1030 of
  5371 in the fixture will not parse. They are classified as *not a catalog
  object*, never reported as parse failures.
* **One representation, not three.** Catalog XML stores an expression once, as
  the text inside ``sawx:expr``. AD-21 is satisfied by capturing it verbatim;
  the RPD's ``ExprTextDesc`` and ``ObjectRefList`` have no counterpart and are
  **absent**, not synthesised.

Where a construct cannot be resolved with certainty the adapter records it and
continues. It never approximates and never guesses (AD-3).

Standard library only (NFR13).
"""

from __future__ import annotations

import collections
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote_plus

from tools.rpd_extract.adapters.inbound import observing
from tools.rpd_extract.core import identifiers as ids
from tools.rpd_extract.core.model import (
    Analysis,
    AnalysisColumn,
    AnalysisCriteria,
    AnalysisFilter,
    AnalysisPrompt,
    AnalysisView,
    Dashboard,
    DashboardContent,
    DashboardPage,
    Estate,
    NO_VIEW_TYPE,
    RESOLVED_AMBIGUOUS,
    RESOLVED_CASE,
    RESOLVED_EXACT,
    RESOLVED_NONE,
    SCOPE_ANALYSIS,
    SCOPE_DASHBOARD,
    SavedFilter,
)

LAYER = ids.CATALOG

SAW = "com.siebel.analytics.web/report/v1.1"
SAWD = "com.siebel.analytics.web/dashboard/v1.1"
SAWX = "com.siebel.analytics.web/expression/v1.1"
SAWSF = "com.siebel.analytics.web/savedfilter/v1.1"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
XSI_TYPE = f"{{{XSI}}}type"


def q(namespace: str, local: str) -> str:
    return f"{{{namespace}}}{local}"


#: Root elements this adapter models. Four of the 59 present in the fixture.
DASHBOARD = q(SAWD, "dashboard")
DASHBOARD_PAGE = q(SAWD, "dashboardPage")
REPORT = q(SAW, "report")
SAVED_FILTER = q(SAWSF, "savedFilterObject")

MODELLED = {DASHBOARD, DASHBOARD_PAGE, REPORT, SAVED_FILTER}

#: Elements inside an Analysis that describe what it renders as.
VIEWS = q(SAW, "views")
VIEW = q(SAW, "view")
CV_CELL = q(SAW, "cvCell")
DISPLAY = q(SAW, "display")

#: How the nested view population is labelled in ``coverage.csv``. Spelled out
#: rather than left as the bare element name because the standalone ``saw:view``
#: root objects are counted under that, and the two populations differ by a
#: factor of 21 — 10,879 elements inside Analyses against 530 root objects. One
#: row carrying both would restate the frame confusion Story 2.8 exists to end.
VIEW_IN_ANALYSIS = "saw:view (element, inside an Analysis)"

#: Version-control and tooling files, not catalog content.
SKIP_DIRS = {".git"}

#: A reference beginning with this names the root the tree starts below.
SHARED_ROOT = "/shared/"

#: What a decoded path names on disk.
OBJECT = "object"
FOLDER = "folder"

#: The ``xsi:type`` of a plain column reference. Everything else is a
#: computation — which is what makes the is-a-computation flag derivable
#: without parsing the expression, and therefore free of AD-3 exposure.
REGULAR_COLUMN = "saw:regularColumn"

#: A direct database function call. The calculation is not defined in OBIEE at
#: all — it lives in the target schema — so no artifact this tool produces can
#: show its logic, and a rebuild must resolve it against the database.
EVAL_TYPE = "sawx:eval"

#: The ``xsi:type`` that makes an ordinary expression a saved-filter reference.
#: **No element named ``sawx:savedFilter`` exists** — zero occurrences. Matching
#: on element name finds nothing and reads as *the construct is absent*, which
#: is the false-absence failure AD-3 exists to prevent.
SAVED_FILTER_TYPE = "sawx:savedFilter"

#: Substrings that make an attribute name styling, and the exceptions.
#: Mirrors ``tools/catalog_survey.py``, where the rule and the evidence for each
#: exception are recorded, and ``catalog-xml-schema.md``, which states it for a
#: reader. Styling is out of scope per FR-34 — 97,498 attribute occurrences that
#: would otherwise bury the real signal in ``unparsed.csv``.
STYLING_MARKERS = (
    "align", "bgcolor", "border", "color", "fmt", "font", "format", "height",
    "indent", "padding", "style", "width", "wraptext",
)

#: Names the rule catches that change **displayed data** rather than appearance.
#: FR-34 puts a difference in displayed data on the defect side, so these stay
#: in scope however format-ish they look. ``fmt`` is the one worth noticing:
#: 12,124 occurrences, values only ``text`` and ``html``, deciding whether cell
#: content is interpreted as markup or shown literally.
STYLING_EXCEPTIONS = frozenset({
    "fmt", "textFormat", "customFormat", "formatMask", "biFormat",
    "defaultFormat", "outputFormat", "format", "formatOutputType",
    "renderFormat",
})


def is_styling(attribute: str) -> bool:
    """Whether an attribute name is out of scope as styling."""
    local = attribute.rpartition("}")[2]
    if local in STYLING_EXCEPTIONS:
        return False
    lowered = local.lower()
    return any(marker in lowered for marker in STYLING_MARKERS)


class CatalogError(ValueError):
    """The catalog root could not be read at all."""


def decode_path(relative: Path) -> str:
    """An on-disk relative path as its decoded catalog path.

    ``+`` is a space and ``%XX`` is a byte, in that order — decoding ``%2b``
    first and then folding ``+`` would turn an escaped plus into a space.

    **The rule is general, not a lookup table.** The two examples anyone
    happens to have seen are ``%2e`` for ``.`` and ``+`` for space; the fixture
    also contains ``co%6dponents``, where ``%6d`` is ``m``.
    """
    return "/".join(unquote_plus(part) for part in relative.parts)


# ------------------------------------------------------------------ the index


class Index:
    """Every decoded path in the tree, and what it names.

    Folders are indexed alongside objects because the reference vocabulary
    targets both: ``sawd:folderView[@path]`` names a catalog **folder**. An
    index of files alone reports all 27 of them as dangling, and a false error
    in the honesty artifact is worse than a missing feature — it teaches a
    reader to discount the file.

    The case-folded index exists because the on-disk tree is lowercased while
    references keep display case. **Exact matching resolves 11 references out of
    4171; case-insensitive resolves 2999.**
    """

    def __init__(self) -> None:
        self._kind: dict[str, str] = {}
        self._folded: dict[str, list[str]] = collections.defaultdict(list)

    def add(self, decoded: str, kind: str) -> None:
        if decoded in self._kind:
            return
        self._kind[decoded] = kind
        self._folded[decoded.lower()].append(decoded)

    def add_object(self, decoded: str) -> None:
        self.add(decoded, OBJECT)
        parts = decoded.split("/")
        for depth in range(1, len(parts)):
            self.add("/".join(parts[:depth]), FOLDER)

    def kind_of(self, decoded: str) -> str:
        return self._kind.get(decoded, "")

    def lookup(self, candidate: str) -> tuple[str, str, str]:
        """``(outcome, target, kind)`` for one already-normalised path."""
        if candidate in self._kind:
            return RESOLVED_EXACT, candidate, self._kind[candidate]
        matches = sorted(set(self._folded.get(candidate.lower(), [])))
        if len(matches) == 1:
            return RESOLVED_CASE, matches[0], self._kind[matches[0]]
        if len(matches) > 1:
            return RESOLVED_AMBIGUOUS, " | ".join(matches), ""
        return RESOLVED_NONE, "", ""


def normalise_reference(reference: str, owner: str) -> str:
    """A reference as a path relative to the tree root, or '' if out of tree.

    Three rules, each measured. References are absolute from the catalog root
    while the tree begins one level below it, so ``/shared`` is stripped. A
    reference with no leading ``/`` is relative to the folder of the object
    making it — overwhelmingly a dashboard page naming a sibling page. A
    reference under any other root, ``/company_shared/`` above all, names
    content this tree does not contain.
    """
    if reference.startswith(SHARED_ROOT):
        return reference[len(SHARED_ROOT):]
    if reference.startswith("/"):
        return ""
    owner_folder = owner.rsplit("/", 1)[0] if "/" in owner else ""
    return f"{owner_folder}/{reference}" if owner_folder else reference


class Resolver:
    """Resolves ``@path`` references, recording how each one resolved.

    **Exact first, case-insensitive second, and which happened is recorded per
    reference.** AD-3 says Python never guesses and AD-8 says name equality is
    not semantic equality, so folding case silently is exactly the
    approximation those rules exist to stop: on an estate that distinguishes
    case it would join two different objects and nothing downstream would
    detect it. Equally, refusing to fold reports 99.7% of a real fixture as
    broken, which is not honest either.

    So both are done, and the difference stays visible. An Operator on a
    case-sensitive estate can see at a glance whether the fallback is carrying
    their extraction.

    An **ambiguous** case-insensitive match — two on-disk objects differing only
    in case — is not a resolution at all. It is recorded as an error naming both
    candidates, because picking one would be the guess in its purest form.
    """

    def __init__(self, index: Index, rpd_id: str, estate: Estate) -> None:
        self.index = index
        self.rpd_id = rpd_id
        self.estate = estate

    def resolve(
        self, reference: str, owner: str, element: str, source_id: str,
        expected: str = OBJECT,
    ) -> tuple[str, str, str, str]:
        """``(outcome, target_id, target_kind, detail)`` for one reference."""
        candidate = normalise_reference(reference, owner)
        if not candidate:
            detail = "names a catalog root this tree does not contain"
            self._record_unresolved(reference, element, source_id, detail)
            return RESOLVED_NONE, "", "", detail

        outcome, target, kind = self.index.lookup(candidate)

        if outcome == RESOLVED_NONE:
            detail = "no object or folder at this path"
            self._record_unresolved(reference, element, source_id, detail)
            return RESOLVED_NONE, "", "", detail

        if outcome == RESOLVED_AMBIGUOUS:
            detail = f"two paths differ only in case: {target}"
            self.estate.record_error(
                self.rpd_id, "ambiguous_reference", source_id, element,
                f"{reference!r} matches more than one object once case is "
                f"folded — {target}. Choosing between them would be a guess, "
                f"so it is recorded as unresolved.",
                layer=LAYER,
            )
            return RESOLVED_AMBIGUOUS, "", "", detail

        detail = ""
        if kind != expected:
            # Not an error: the reference resolved. But a reportRef landing on a
            # folder is a type mismatch, and counting it as a hit would overstate
            # what was understood.
            detail = f"expected a catalog {expected}, resolved to a {kind}"
        return outcome, ids.make_id(self.rpd_id, LAYER, target), kind, detail

    def _record_unresolved(
        self, reference: str, element: str, source_id: str, detail: str
    ) -> None:
        self.estate.record_error(
            self.rpd_id, "unresolved_reference", source_id, element,
            f"{reference!r} did not resolve: {detail}. Recorded rather than "
            f"repaired (AD-3).",
            layer=LAYER,
        )


# ---------------------------------------------------------------- small tools


def _tag(element: ET.Element) -> str:
    """Namespace-qualified, always.

    ``saw:reportRef`` and ``sawd:reportRef`` are different elements sharing a
    local name, 21 and 1722 occurrences. So are ``xsi:type`` and
    ``xdoeft:type``. Matching on the local name merges them.
    """
    return element.tag


def _attr(element: ET.Element, name: str, default: str = "") -> str:
    return element.attrib.get(name, default)


def _xsi_type(element: ET.Element) -> str:
    return element.attrib.get(XSI_TYPE, "")


def _find(element: ET.Element, path: str) -> ET.Element | None:
    found = element.find(path)
    return observing.sought(found) if found is not None else None


def _findall(element: ET.Element, path: str) -> list[ET.Element]:
    return [observing.sought(item) for item in element.findall(path)]


def _caption_text(element: ET.Element | None) -> str:
    """The text of a ``saw:caption/saw:text`` under this element, verbatim."""
    if element is None:
        return ""
    text = _find(element, f"{q(SAW, 'caption')}/{q(SAW, 'text')}")
    return observing.read_text(text)


def _name_of(decoded: str) -> str:
    return decoded.rsplit("/", 1)[-1] if "/" in decoded else decoded


def _folder_of(decoded: str) -> str:
    return decoded.rsplit("/", 1)[0] if "/" in decoded else ""


# ---------------------------------------------------------------- discovery


def _catalog_files(catalog_root: Path) -> list[tuple[Path, str]]:
    """Every file under the catalog root, with its decoded path.

    No extension filter, because **catalog objects are extensionless**. Every
    file is attempted and the ones that are not XML are classified, not
    reported as failures.
    """
    found: list[tuple[Path, str]] = []
    for path in sorted(catalog_root.rglob("*")):
        try:
            if not path.is_file():
                continue
        except OSError:
            continue
        relative = path.relative_to(catalog_root)
        if SKIP_DIRS.intersection(relative.parts):
            continue
        found.append((path, decode_path(relative)))
    return found


#: Leading bytes -> what a non-XML file actually is. Classified by content
#: because there is no extension to read: the suffixes that do appear are
#: percent-encoded inside FOLDER names, so a test against the on-disk name finds
#: none of them and returns zero.
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
    for signature, name in MAGIC:
        if head.startswith(signature):
            return name
    return "unrecognised binary or text"


def _parse_all(
    files: list[tuple[Path, str]], rpd_id: str, estate: Estate
) -> list[tuple[str, ET.Element]]:
    """Parse every file once, into trees that observe what is read from them.

    A file that will not parse is classified rather than failed. Two wrong
    answers are available and both are the failure this project exists to
    prevent: 1030 rows in ``errors.csv`` bury the handful of genuinely dangling
    references that matter, and skipping them silently loses 19% of the input
    with nothing recorded. So they are counted as *present, not a catalog
    object*, aggregated by what they actually are.
    """
    trees: list[tuple[str, ET.Element]] = []
    not_catalog: collections.Counter = collections.Counter()

    for path, decoded in files:
        estate.census(rpd_id, "files_seen")
        try:
            root = ET.parse(path, parser=observing.observing_parser()).getroot()
        except ET.ParseError:
            try:
                with path.open("rb") as handle:
                    head = handle.read(16)
            except OSError as exc:
                estate.record_error(
                    rpd_id, "unreadable", decoded, "File", str(exc), layer=LAYER
                )
                continue
            not_catalog[classify_bytes(head)] += 1
            estate.census(rpd_id, "not_a_catalog_object")
            continue
        except OSError as exc:
            estate.record_error(
                rpd_id, "unreadable", decoded, "File", str(exc), layer=LAYER
            )
            continue
        estate.census(rpd_id, "parsed_as_xml")
        trees.append((decoded, root))

    for content, count in sorted(not_catalog.items()):
        estate.record_gap(
            rpd_id, "not_a_catalog_object", "File",
            f"{content} — present in the tree, never a catalog object", count,
        )
    return trees


def _build_index(trees: list[tuple[str, ET.Element]], files) -> Index:
    """Index every path in the tree, objects and folders alike.

    Built from **every file**, not only the parseable ones: a reference can
    point at a BI Publisher template as legitimately as at an Analysis, and an
    index that omits the 1030 non-XML files would report those as dangling.
    """
    index = Index()
    for _, decoded in files:
        index.add_object(decoded)
    return index


# ------------------------------------------------------------- Story 2.4


def _parse_dashboard(
    decoded: str, root: ET.Element, rpd_id: str, resolver: Resolver, estate: Estate
) -> None:
    """A ``sawd:dashboard`` — the layout object naming its pages, in order.

    The dashboard's **name is its containing folder**, not its filename. Every
    dashboard in the fixture is a file called ``dashboard layout`` inside
    ``_portal/<dashboard name>/``, so taking the last path segment would name
    all 111 of them the same thing. The identifier still uses the full path, so
    nothing collides.
    """
    row_id = ids.make_id(rpd_id, LAYER, decoded)
    folder = _folder_of(decoded)
    name = _name_of(folder) if folder else _name_of(decoded)
    version = _attr(root, "xmlVersion")

    refs = _findall(root, f".//{q(SAWD, 'dashboardPageRef')}")
    for position, ref in enumerate(refs):
        reference = _attr(ref, "path")
        outcome, target, kind, detail = resolver.resolve(
            reference, decoded, q(SAWD, "dashboardPageRef"), decoded
        )
        estate.dashboard_contents.append(
            DashboardContent(
                row_id=ids.make_id(rpd_id, LAYER, f"{decoded}#page{position}"),
                rpd_id=rpd_id, container_id=row_id,
                element=q(SAWD, "dashboardPageRef"), reference=reference,
                position=position, resolution=outcome, target_id=target,
                target_kind=kind, detail=detail,
            )
        )

    estate.dashboards.append(
        Dashboard(row_id=row_id, rpd_id=rpd_id, name=name, catalog_path=decoded,
                  xml_version=version, page_count=len(refs))
    )
    estate.count(rpd_id, DASHBOARD, "parsed", layer=LAYER)
    estate.record_version(rpd_id, DASHBOARD, version)


def _parse_dashboard_page(
    decoded: str, root: ET.Element, rpd_id: str, resolver: Resolver, estate: Estate
) -> None:
    """A ``sawd:dashboardPage`` and everything placed on it.

    ``dashboard_id`` is filled in a later pass from the Dashboards that
    reference this page, never inferred from the folder it sits in.
    """
    row_id = ids.make_id(rpd_id, LAYER, decoded)
    version = _attr(root, "xmlVersion")

    position = 0
    for element_name in (q(SAWD, "reportRef"), q(SAWD, "globalFilterView"),
                         q(SAWD, "scorecardViewRef"), q(SAWD, "folderView")):
        expected = FOLDER if element_name == q(SAWD, "folderView") else OBJECT
        for ref in _findall(root, f".//{element_name}"):
            reference = _attr(ref, "path")
            outcome, target, kind, detail = resolver.resolve(
                reference, decoded, element_name, decoded, expected=expected
            )
            estate.dashboard_contents.append(
                DashboardContent(
                    row_id=ids.make_id(rpd_id, LAYER, f"{decoded}#item{position}"),
                    rpd_id=rpd_id, container_id=row_id, element=element_name,
                    reference=reference, position=position, resolution=outcome,
                    target_id=target, target_kind=kind, detail=detail,
                )
            )
            position += 1

    # A dashboard-scope filter applies to every Analysis on the page, so it is
    # recorded with its scope rather than folded in with Analysis filters.
    for order, view in enumerate(_findall(root, f".//{q(SAWD, 'globalFilterView')}")):
        reference = _attr(view, "path")
        outcome, target, _, _ = resolver.resolve(
            reference, decoded, q(SAWD, "globalFilterView"), decoded
        )
        estate.analysis_filters.append(
            AnalysisFilter(
                row_id=ids.make_id(rpd_id, LAYER, f"{decoded}#gfilter{order}"),
                rpd_id=rpd_id, scope=SCOPE_DASHBOARD, owner_id=row_id,
                position=order, reference=reference, target_id=target,
                resolution=outcome,
            )
        )

    estate.dashboard_pages.append(
        DashboardPage(row_id=row_id, rpd_id=rpd_id, name=_name_of(decoded),
                      catalog_path=decoded, xml_version=version)
    )
    estate.count(rpd_id, DASHBOARD_PAGE, "parsed", layer=LAYER)
    estate.record_version(rpd_id, DASHBOARD_PAGE, version)


def _link_pages_to_dashboards(estate: Estate) -> None:
    """Fill each page's owning Dashboard from the references that resolved.

    Done as a pass rather than during parsing because a page is parsed before
    the Dashboard that names it as often as after. A page no Dashboard
    references keeps an empty ``dashboard_id`` — a real state, and a different
    thing from a page whose Dashboard was not understood.
    """
    owner: dict[str, tuple[str, int]] = {}
    for content in estate.dashboard_contents:
        if content.element != q(SAWD, "dashboardPageRef") or not content.target_id:
            continue
        owner.setdefault(content.target_id, (content.container_id, content.position))

    estate.dashboard_pages[:] = [
        page if page.row_id not in owner else DashboardPage(
            row_id=page.row_id, rpd_id=page.rpd_id, name=page.name,
            catalog_path=page.catalog_path, xml_version=page.xml_version,
            dashboard_id=owner[page.row_id][0], position=owner[page.row_id][1],
        )
        for page in estate.dashboard_pages
    ]


# ------------------------------------------------------- Stories 2.5 and 2.6


def _expression(container: ET.Element | None) -> tuple[str, str]:
    """``(xsi:type, text)`` of the ``sawx:expr`` inside this container.

    **Verbatim, character for character.** No stripping, no normalising, no
    unquoting — FR-2 forbids reformatting anywhere, and the verbatim guarantee
    is the product's central claim.

    Only one representation exists to capture. Where the RPD's three-form shape
    has no counterpart the field is **absent**, never filled with something
    made up: a fabricated ``ExprTextDesc`` would be indistinguishable from one
    the source provided.
    """
    if container is None:
        return "", ""
    expr = _find(container, q(SAWX, "expr"))
    if expr is None:
        return "", ""
    return _xsi_type(expr), observing.read_text(expr)


def _owned_by_nearest(root: ET.Element, owner_tag: str, wanted: str):
    """``{id(owner) -> [element…]}``, each element under its NEAREST owner.

    Criteria **nest**: 182 of the fixture's 1789 blocks sit inside another one,
    because a set operation wraps its operands in criteria of their own. A
    descendant search from every block therefore counts a shared column once per
    enclosing block — it reported 13,091 columns where 11,143 exist, and 12,424
    ``columnFormula`` elements where the file holds 10,474. Ownership has to be
    nearest-ancestor, not any-ancestor.
    """
    parent: dict[int, ET.Element] = {}
    for container in root.iter():
        for child in container:
            parent[id(child)] = container

    def nearest(element: ET.Element) -> ET.Element | None:
        current = parent.get(id(element))
        while current is not None:
            if current.tag == owner_tag:
                return current
            current = parent.get(id(current))
        return None

    # Deliberately NOT marked as read here. Ownership is bookkeeping; only a
    # parser that actually consumes an element may mark it. Marking here would
    # silence the 132 columnFormula elements that belong to no column and the
    # second formula on the two columns that own two — the exact silent
    # omission the audit exists to catch.
    owned: dict[int, list[ET.Element]] = collections.defaultdict(list)
    for element in root.iter(wanted):
        owner = nearest(element)
        if owner is not None:
            owned[id(owner)].append(element)
    return owned


def _uses_eval(container: ET.Element) -> bool:
    """Does any expression under this container call a database function?

    ``sawx:eval`` is **never the outermost type** — all 356 occurrences are
    nested inside another expression, so a check on the top-level ``xsi:type``
    finds none of them. ``EVALUATE`` passes a function straight through to the
    database, so the calculation is not defined in OBIEE at all: it lives in the
    target schema, and whoever rebuilds must resolve it there. The flag turns
    that from a discovery into a listed task.
    """
    return any(
        expr.attrib.get(XSI_TYPE) == EVAL_TYPE
        for expr in container.iter(q(SAWX, "expr"))
    )


def _parse_analysis(
    decoded: str, root: ET.Element, rpd_id: str, resolver: Resolver, estate: Estate
) -> None:
    """A ``saw:report`` root — an Analysis, and the logic defined inside it."""
    row_id = ids.make_id(rpd_id, LAYER, decoded)
    version = _attr(root, "xmlVersion")

    # An Analysis can carry more than one criteria block — combined requests and
    # set operations — and there are 1789 of them against 1607 Analyses. A
    # one-per-report model drops the extras, and each dropped block is an entire
    # query definition.
    criteria_blocks = [
        observing.sought(item) for item in root.iter(q(SAW, "criteria"))
    ]
    columns_of = _owned_by_nearest(root, q(SAW, "criteria"), q(SAW, "column"))
    filters_of = _owned_by_nearest(root, q(SAW, "criteria"), q(SAW, "filter"))
    # Owned by the nearest column rather than taken as a direct child: 72 of the
    # fixture's columnFormula elements sit deeper inside their column, and a
    # direct-child read drops them. FR-2 makes a dropped formula the failure
    # this story exists to prevent.
    formulas_of = _owned_by_nearest(root, q(SAW, "column"), q(SAW, "columnFormula"))

    columns = 0
    for order, criteria in enumerate(criteria_blocks):
        criteria_id = ids.make_id(rpd_id, LAYER, f"{decoded}#criteria{order}")
        estate.analysis_criteria.append(
            AnalysisCriteria(
                row_id=criteria_id, rpd_id=rpd_id, analysis_id=row_id,
                position=order,
                # Verbatim, unresolved, quotes intact — values arrive as
                # ``"A - Sample Sales"``. Resolving it is FR-7, which has no
                # matched fixture, and lands in report_lineage.csv (AD-23).
                subject_area=_attr(criteria, "subjectArea"),
            )
        )
        columns += _parse_columns(decoded, columns_of.get(id(criteria), []),
                                  formulas_of, criteria_id, row_id, rpd_id,
                                  order, estate)
        _parse_filters(decoded, filters_of.get(id(criteria), []), row_id,
                       rpd_id, order, resolver, estate)

    _parse_prompts(decoded, root, row_id, rpd_id, estate)
    _parse_views(decoded, root, row_id, rpd_id, estate)

    estate.analyses.append(
        Analysis(row_id=row_id, rpd_id=rpd_id, name=_name_of(decoded),
                 catalog_path=decoded, xml_version=version,
                 criteria_count=len(criteria_blocks), column_count=columns)
    )
    estate.count(rpd_id, REPORT, "parsed", layer=LAYER)
    estate.record_version(rpd_id, REPORT, version)


def _parse_views(
    decoded: str, root: ET.Element, analysis_id: str, rpd_id: str,
    estate: Estate,
) -> int:
    """Every ``saw:view`` inside an Analysis — what the report renders as.

    Story 2.5 captured what an Analysis computes; this is what it displays, and
    the two are independent. The type is recorded and never interpreted, so an
    OBIEE version carrying a view this tool has never seen produces a row rather
    than an error.

    ``references_views`` and ``bound_column_count`` are counted from structure
    the source states, not decided from a list of type names: a container
    arranges other views by name, a data visual binds columns. A hardcoded list
    would misclassify the twenty-seventh type the day it arrives.
    """
    for container in root.iter(VIEWS):
        observing.sought(container)
        _attr(container, "currentView")

    views = [observing.sought(view) for view in root.iter(VIEW)]
    for order, view in enumerate(views):
        references = 0
        for cell in view.iter(CV_CELL):
            observing.sought(cell)
            if _attr(cell, "viewName"):
                references += 1

        # Every descendant is asked, because a column binding sits at a
        # different depth in a pivot, a chart and a trellis, and reading only
        # the shape this fixture happens to use is how the next estate loses
        # rows in silence.
        bound = sum(
            1 for element in view.iter()
            if element is not view and _attr(element, "columnID")
        )

        display = _find(view, DISPLAY)
        declared = _xsi_type(view)
        estate.analysis_views.append(
            AnalysisView(
                row_id=ids.make_id(rpd_id, LAYER, f"{decoded}#view{order}"),
                rpd_id=rpd_id, analysis_id=analysis_id, position=order,
                # Absence is a state of its own. An empty string here would be
                # indistinguishable from a type the parser failed to read.
                view_type=declared or NO_VIEW_TYPE,
                name=_attr(view, "name"),
                references_views=references,
                bound_column_count=bound,
                display_type=_attr(display, "type") if display is not None else "",
                display_subtype=(
                    _attr(display, "subtype") if display is not None else ""
                ),
            )
        )

    if views:
        estate.count(rpd_id, VIEW_IN_ANALYSIS, "parsed", len(views), layer=LAYER)
    return len(views)


def _parse_columns(
    decoded: str, columns: list[ET.Element], formulas_of: dict,
    criteria_id: str, analysis_id: str, rpd_id: str, criteria_order: int,
    estate: Estate,
) -> int:
    """Every column of one criteria block, with its formula verbatim."""
    count = 0
    for order, column in enumerate(columns):
        construct = ""
        formula_type = ""
        formula = ""

        held = formulas_of.get(id(column), [])
        if held:
            construct = q(SAW, "columnFormula")
            formula_type, formula = _expression(held[0])

        column_type = _xsi_type(column)
        estate.analysis_columns.append(
            AnalysisColumn(
                row_id=ids.make_id(
                    rpd_id, LAYER, f"{decoded}#c{criteria_order}.{order}"
                ),
                rpd_id=rpd_id, analysis_id=analysis_id, criteria_id=criteria_id,
                position=order, column_id=_attr(column, "columnID"),
                heading=_caption_text(_find(column, q(SAW, "columnHeading"))),
                table_heading=_caption_text(_find(column, q(SAW, "tableHeading"))),
                formula_construct=construct, formula_type=formula_type,
                formula=formula,
                # Derived from xsi:type, never by parsing the expression: a
                # plain reference is saw:regularColumn and everything else is a
                # computation. Deterministic, so no AD-3 exposure.
                is_computation=bool(column_type) and column_type != REGULAR_COLUMN,
                uses_eval=any(_uses_eval(item) for item in held),
            )
        )
        count += 1
    return count


def _parse_filters(
    decoded: str, filters: list[ET.Element], analysis_id: str, rpd_id: str,
    criteria_order: int, resolver: Resolver, estate: Estate,
) -> None:
    """Filters on one criteria block, and any saved filter they reference.

    A filter is a thin wrapper around one expression tree: 1086 ``saw:filter``
    elements carry 1087 ``sawx:expr`` children. Every expression in the tree is
    recorded, not only the outermost, because nesting is where the predicates
    are — ``sawx:logical`` at the top with ``sawx:comparison`` at the leaves.
    """
    order = 0
    for holder in filters:
        for expr in _findall(holder, f".//{q(SAWX, 'expr')}"):
            expr_type = _xsi_type(expr)
            reference = _attr(expr, "path")
            target = ""
            outcome = ""
            if expr_type == SAVED_FILTER_TYPE and reference:
                outcome, target, _, _ = resolver.resolve(
                    reference, decoded, q(SAWX, "expr"), decoded
                )
            estate.analysis_filters.append(
                AnalysisFilter(
                    row_id=ids.make_id(
                        rpd_id, LAYER, f"{decoded}#f{criteria_order}.{order}"
                    ),
                    rpd_id=rpd_id, scope=SCOPE_ANALYSIS, owner_id=analysis_id,
                    position=order,
                    # Captured, never validated against a closed list: multiply,
                    # union and the arithmetic operators share this attribute,
                    # so it is a general expression operator.
                    op=_attr(expr, "op"), expr_type=expr_type,
                    expr_text=observing.read_text(expr), reference=reference,
                    target_id=target, resolution=outcome,
                    uses_eval=expr_type == EVAL_TYPE or _uses_eval(expr),
                )
            )
            order += 1


def _parse_prompts(
    decoded: str, root: ET.Element, analysis_id: str, rpd_id: str, estate: Estate
) -> None:
    """Prompts, the column each binds to, and any variable each sets."""
    for order, prompt in enumerate(_findall(root, f".//{q(SAW, 'prompt')}")):
        prompt_type = _xsi_type(prompt)
        if not prompt_type:
            continue  # a bare <saw:prompt>text</saw:prompt> parameter, not a prompt
        column_type, column_formula = _expression(_find(prompt, q(SAW, "formula")))
        operator = _find(prompt, q(SAW, "promptOperator"))
        control = _find(prompt, q(SAW, "promptUIControl"))
        # A prompt that sets a presentation variable is not merely filtering:
        # the variable may be read by a column formula elsewhere in the report.
        # That dependency is invisible if only the column binding is captured.
        variables = _findall(
            prompt, f".//{q(SAW, 'setPromptVariable')}"
        )
        set_variable = " | ".join(
            v for v in (_attr(item, "variableFormula") for item in variables) if v
        )
        estate.analysis_prompts.append(
            AnalysisPrompt(
                row_id=ids.make_id(rpd_id, LAYER, f"{decoded}#p{order}"),
                rpd_id=rpd_id, analysis_id=analysis_id, position=order,
                prompt_type=prompt_type, column_formula=column_formula,
                column_type=column_type,
                set_variable=set_variable,
                operator=_attr(operator, "op") if operator is not None else "",
                ui_control=_xsi_type(control) if control is not None else "",
            )
        )


def _parse_saved_filter(
    decoded: str, root: ET.Element, rpd_id: str, resolver: Resolver, estate: Estate
) -> None:
    """A ``sawsf:savedFilterObject`` root — a filter stored for reuse."""
    row_id = ids.make_id(rpd_id, LAYER, decoded)
    version = _attr(root, "xmlVersion")
    holder = _find(root, q(SAW, "filter"))
    expr_type, expr_text = _expression(holder)
    outer = _find(holder, q(SAWX, "expr")) if holder is not None else None

    estate.saved_filters.append(
        SavedFilter(row_id=row_id, rpd_id=rpd_id, name=_name_of(decoded),
                    catalog_path=decoded, xml_version=version,
                    op=_attr(outer, "op") if outer is not None else "",
                    expr_type=expr_type, expr_text=expr_text,
                    uses_eval=holder is not None and _uses_eval(holder))
    )
    estate.count(rpd_id, SAVED_FILTER, "parsed", layer=LAYER)
    estate.record_version(rpd_id, SAVED_FILTER, version)


# ------------------------------------------------------------- Story 2.7


def _report_unmodelled(
    trees: list[tuple[str, ET.Element]], rpd_id: str, estate: Estate
) -> None:
    """Every root type present and not modelled, enumerated by parsing.

    **Not from a list.** A hard-coded set of expected unmodelled types silently
    drops the fifty-fourth, and the whole point of this reporting is that
    nothing is dropped in silence. The rule is: every root type encountered that
    no parser handles produces a row.

    Grouped by type with a count rather than one row per file: 1491 individual
    rows would bury the handful of genuinely dangling references that matter,
    which is the same signal-in-noise failure that reporting non-XML files as
    errors would cause.
    """
    counts: collections.Counter = collections.Counter()
    example: dict[str, str] = {}
    for decoded, root in trees:
        if root.tag in MODELLED:
            continue
        counts[root.tag] += 1
        example.setdefault(root.tag, decoded)
        estate.record_version(rpd_id, root.tag, _attr(root, "xmlVersion"))

    for object_type, count in sorted(counts.items()):
        estate.unparsed.append(
            _unmodelled_row(rpd_id, object_type, example[object_type], count)
        )
        estate.count(rpd_id, object_type, "skipped", count, layer=LAYER)
        estate.census(rpd_id, "unmodelled_object", count)


def _unmodelled_row(rpd_id: str, object_type: str, example: str, count: int):
    from tools.rpd_extract.core.model import Unparsed

    return Unparsed(
        rpd_id, "unmodelled_type", object_type,
        f"{count} object(s), e.g. {example}", count,
    )


def _audit(trees: list[tuple[str, ET.Element]], rpd_id: str, estate: Estate) -> None:
    """Report catalog content the parsers never took, styling excluded by name.

    The styling exclusion is a **scope decision**, and it is recorded as one:
    excluded attributes land in ``unparsed.csv`` under ``excluded_by_scope``
    with their counts, not dropped. An exclusion recorded only in a schema
    document nobody opens is indistinguishable, from the coverage report, from
    an oversight.
    """
    observing.audit_unread(
        [(rpd_id, root.tag, root) for _, root in trees],
        estate,
        MODELLED,
        tag_of=_tag,
        out_of_scope=lambda tag, attribute: is_styling(attribute),
        out_of_scope_kind="excluded_by_scope",
    )


def load(catalog_root: Path | str, rpd_id: str) -> Estate:
    """Read a Web Catalog tree into ``estate`` under layer ``cat``.

    The directory is a catalog **because the Operator declared it one** by
    putting it there — never because of anything found inside it. If it holds
    something that is not a catalog, extraction reports what it could not read;
    it does not reclassify the folder.
    """
    catalog_root = Path(catalog_root)
    if not catalog_root.is_dir():
        raise CatalogError(f"catalog root {catalog_root} is not a directory")
    ids.validate_rpd_id(rpd_id)
    estate = Estate()
    estate.rpd_ids = [rpd_id]

    files = _catalog_files(catalog_root)
    if not files:
        estate.record_error(
            rpd_id, "unreadable", str(catalog_root), "Catalog",
            "the declared catalog directory holds no files. Extraction "
            "continues; the manifest records that the catalog half was present "
            "and empty, which is not the same as absent.",
            layer=LAYER,
        )
        return estate

    trees = _parse_all(files, rpd_id, estate)
    index = _build_index(trees, files)
    resolver = Resolver(index, rpd_id, estate)

    passes = {
        DASHBOARD: _parse_dashboard,
        DASHBOARD_PAGE: _parse_dashboard_page,
        REPORT: _parse_analysis,
        SAVED_FILTER: _parse_saved_filter,
    }
    for wanted, handler in passes.items():
        for decoded, root in trees:
            if root.tag != wanted:
                continue
            handler(decoded, root, rpd_id, resolver, estate)
            estate.census(rpd_id, "modelled_object")

    _link_pages_to_dashboards(estate)
    _report_unmodelled(trees, rpd_id, estate)
    # After every pass, so the audit sees the reads all of them made.
    _audit(trees, rpd_id, estate)
    return estate
