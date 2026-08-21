# Web Catalog XML — Observed Schema

**What this covers:** the element, attribute and type vocabulary actually present in the Web Catalog fixture, per object type.
**Who it is for:** whoever writes or reviews the `catalog_xml` inbound adapter (Stories 2.4–2.7).

**Writer: Operator.** `estate/test-corpus/` has one writer (AD-18).

Derived 2026-08-20 by parsing **all 5371 files** of the pinned fixture with `ElementTree`. This is the catalog counterpart of
`mds-xml-schema.md`, and it exists for the same reason: **Oracle publishes no schema for this format**, so this is the only
specification there is.

```sh
python3 -m tools.catalog_survey --catalog ~/Documents/Garage/obiee-corpus/obiee_sample_git
```

## Read this first: observed, never exhaustive

**Everything below records what one catalog contained.** Absence here means absent *from this fixture* — never absent from
OBIEE. The fixture is SampleApp v607, exported in 2019 from one instance; another estate will carry constructs this one does
not, and the adapter must meet them without pretending they cannot exist.

That is not a disclaimer, it is the operating rule. **Under AD-3 an unrecognised construct is recorded in `unparsed.csv` and
extraction continues** — it is never guessed at, and never assumed absent because it is missing from this page. An adapter
written to accept only what is listed here would treat a newer estate's vocabulary as corruption. The audit in Story 2.7
reports every element and attribute no column carried, which is what turns this document from a specification into a
*starting point that announces its own gaps*.

**Trust a parse over any name quoted in prose, this document included.** Three constructs on this project have been searched
for under names they do not have: `implicitFact` for `defaultFactColumnRef` (Story 1.6), `sawd:report` for `sawd:reportRef`,
and `sawx:savedFilter` as an element when it is only ever an `xsi:type`. In every case the count was right and the name was
wrong, because it was transcribed from a summary rather than read from the source.

## Identity is namespace plus local name, never the prefix

**A prefix is a document's local convenience, not an element's name.** Two consequences, both measured:

- `saw:reportRef` (21) and `sawd:reportRef` (1722) are **different elements** sharing a local name. So are `xsi:type`
  (62,867) and `xdoeft:type` (1). Matching on local name alone merges them.
- The **same** element is written prefixed in some documents and default-namespaced in others.
  `sawbsc:kpiWatchlistView` is 10 of the first and 5 of the second. Counting rendered names reports **60 root types where 59
  exist**.

Seven namespaces appear as a document's default namespace somewhere, declaring no prefix on the element itself — including
`com.siebel.analytics.web/report/v1.1` and both BI Publisher roots. Names below are rendered with the prefixes the corpus
itself declares, purely for readability.

| Prefix | Namespace |
|---|---|
| `saw` | `com.siebel.analytics.web/report/v1.1` |
| `sawd` | `com.siebel.analytics.web/dashboard/v1.1` |
| `sawx` | `com.siebel.analytics.web/expression/v1.1` |
| `sawsf` | `com.siebel.analytics.web/savedfilter/v1.1` |
| `sawbsc` | `com.siebel.analytics.web/scorecard/v1` |
| `sawkpi` | `com.siebel.analytics.web/kpi/v1` |
| `sawsel` | `com.siebel.analytics.web/dashselections/v1` |
| `sawst` | `com.siebel.analytics.web/state/v1` |
| `sawwb` | `com.siebel.analytics.web/writeback/v1` |
| `cond` | `com.oracle.bi/conditions/v1` |
| `xdm` | `http://xmlns.oracle.com/oxp/xmlp` — BI Publisher; **both its roots declare no prefix themselves** |
| `xsi` | `http://www.w3.org/2001/XMLSchema-instance`, and a single-occurrence `.../1999/...` recorded rather than corrected |

## The tree holds three products, not one

**59 distinct root element types** across the 4341 files that parse. Classified by namespace, not by name:

| Product | Root types | Files | Share of all 5371 |
|---|---:|---:|---:|
| **OBIEE catalog** | 25 | 3772 | 70% |
| **BI Publisher** | 4 | 404 | 8% |
| Raw data and business documents (no namespace) | 28 | 161 | 3% |
| XSLT stylesheet, Adobe form data | 2 | 4 | <1% |
| **Not XML at all** | — | 1030 | 19% |

59 root types and 4341 parsed files, summing exactly.

**BI Publisher is a different product sharing the catalog tree.** `xdm:dataModel` (162), the BI Publisher `report` root (156)
and `oxp/config:config` (85) are not OBIEE Analyses, and the adapter does not model them. Story 2.7 reports them as
unmodelled types; **this is where a reader learns they are a separate product rather than a gap in coverage.**

The 28 no-namespace roots — `DATA_DS` (86), `data` (22), `ROWSET` (14), and around thirty one-offs such as `SalesData`,
`INVOICELIST`, `EMPLOYEES`, `PROFILE` — are raw data exports and business documents. Same status: present, not catalog
constructs.

## `xmlVersion` — and its absence

| `xmlVersion` on root | Objects | Share of parseable roots |
|---|---:|---:|
| `201201160` | 1504 | 35% |
| `200810300` | 1147 | 26% |
| **none** | **1643** | **38%** |
| `201106170` | 47 | 1% |

Sorted by frequency the order is **none (1643)**, `201201160` (1504), `200810300` (1147), `201106170` (47).

**No version at all is the most common state of all** — more common than any declared value, and more common than the largest
of them by 139 objects. Any design keying behaviour off `xmlVersion` must handle its absence as the *ordinary* case, not as an
error and not as an edge.

*Corrected 2026-08-20. The epic, Story 2.1 and Story 2.7 all called absence the **second** most common state. Measured across
all 4341 parseable roots it ranks first: 1643 against 1504. The 38% figure those documents quote is right; the ranking was
not, and a design that treats "no version" as the runner-up will size its handling of it wrongly.* A fourth value, `200811100`, occurs **once**, on a nested element, never on a root — so
"four `xmlVersion` values" and "three" are both defensible and neither is meaningful without saying which was counted.

### Version-conditional vocabulary, and the limit of the evidence

**Exactly one root type carries more than one version**: `saw:report`, split `201201160` (1504) and none (103). Every other
object type is uniform, so version drift can be measured for Analyses and for nothing else.

Within `saw:report`, 138 constructs appear under both versions and 781 under one only. **Almost all of that is sampling, not
drift**: 766 constructs appear only under the 1504-object population, which is what a rare construct missing from a
103-object sample looks like. Reporting those as version-conditional would be a claim the evidence does not support.

**Fifteen constructs go the other way** — present only in the 103 versionless Analyses, which sampling cannot explain:

| Construct | Why it matters |
|---|---|
| **`saw:paSimpleColumnFormula`** | **A second formula-bearing construct — 42 occurrences.** Holds its expression as element text, with no `sawx:expr` child and no `xsi:type` |
| `saw:snapshot`, `saw:snapshots`, `@hash`, `@id`, `@modified` | Cached result snapshots |
| `saw:canvasConfig`, `saw:filterControlConfig`, `saw:filterUIControl` | Visual Analyzer canvas layout |
| `saw:filterByColumns`, `saw:filterUIControl@displayTimeZone` | Filter binding |
| `saw:view@masterViewName`, `@syncViews`, `saw:column@advancedAnalyticsType` | View linkage |

These are **Visual Analyzer projects** — files named `_projectdefn`, carrying a `saw:report` root but referencing uploaded
datasets via `XSA('weblogic'.'Sample Orders R Examples')` rather than a Subject Area. They are Analyses by root element and a
different thing by content.

**`saw:paSimpleColumnFormula` is the load-bearing finding.** It is a second formula-bearing construct, invisible to any
search for `columnFormula`, and it exists only in the population that declares no version — so a survey of versioned Analyses
would never meet it.

*Refined 2026-08-20, after parsing rather than assuming where it sits.* It is **not** a column formula: all 42 hang off
`saw:propertyAddition`, not off `saw:column`, and never inside a `saw:criteria`. Epic 2's adapter therefore does not capture
them, and the honest consequence is the one that matters: they surface in `unparsed.csv` as
`unread_element` × 42 rather than vanishing. Capturing them properly means modelling Visual Analyzer project structure, which
is a different object shape and is recorded as deferred work — not smuggled into an Analysis parser as though it belonged
there.

## `xsi:type` is a first-class axis

Type carries meaning the element name does not, and a schema recorded by element name alone would miss it: a saved-filter
reference and a SQL expression are **the same element**, `sawx:expr`, distinguished only by type.

| `xsi:type` | Occurrences |
|---|---:|
| `sawx:sqlExpression` | 14771 |
| `saw:regularColumn` | 10606 |
| `xsd:decimal` | 3632 |
| `sawx:comparison` | 2173 |
| `saw:dvtchart` | 1739 |
| `saw:simpleCriteria` | 1680 |
| `sawx:special` | 1608 |
| `saw:compoundView` | 1581 |
| `saw:titleView` | 1482 |
| `saw:pluginView` | 1288 |
| `sawx:columnRefExpr` | 1280 |
| `saw:number` | 1271 |
| `saw:tableView` | 1207 |
| `saw:pivotTableView` | 1156 |
| `xsd:string` | 1151 |
| `saw:columnFilterPrompt` | 995 |
| `saw:stringMembers` | 865 |
| `saw:htmlview` | 796 |
| `saw:percent` | 738 |
| `sawx:logical` | 639 |
| `saw:allChoices` | 612 |
| `saw:stringAssign` | 567 |
| `saw:integerMembers` | 531 |
| `saw:globalFilterPrompt` | 530 |

## The `@path` reference vocabulary

Path resolution is Story 2.4's central mechanic, and **the reference vocabulary is much larger than `sawd:reportRef`**.
Fourteen elements carry `@path`, across three products:

| Element | With `@path` |
|---|---:|
| `sawd:reportRef` | 1722 |
| `sawd:dashboardPageRef` | 1041 |
| `sawd:globalFilterView` | 887 |
| `sawx:expr` | 417 |
| `{http://xmlns.oracle.com/oxp/config/}truetype` | 312 |
| `sawd:scorecardViewRef` | 41 |
| `sawbsc:perspectiveRef` | 32 |
| `sawd:folderView` | 27 |
| `saw:reportRef` | 21 |
| `saw:catalogColumnRef` | 15 |
| `saw:requestMapping` | 3 |
| `saw:column` | 1 |
| `cond:conditionRef` | 1 |
| `saw:reference` | 1 |

Three warnings a reader needs before writing the resolver:

- **`saw:reportRef` and `sawd:reportRef` are different elements.** Report namespace and dashboard namespace, 21 and 1722.
- **`@path` alone does not mean *catalog reference*.** `oxp/config:truetype[@path]` (312) is a font file path inside a BI
  Publisher configuration. All 312 are unresolvable against the catalog tree, and correctly so — they do not point at it.
- **References target two kinds of thing.** `sawd:folderView[@path]` (27) names a catalog **folder**, not an object. An index
  built from files alone reports all 27 as dangling, which is a false error in the one artifact whose value is that a reader
  can trust it. Index folders too, and record which kind a reference resolved to, so a `reportRef` landing on a folder is a
  type mismatch rather than a silent hit.

## Styling — the membership rule, stated before counting

FR-34 claims **structural and data equivalence, not visual identity**, so styling is out of scope. But the epic carried two
irreconcilable counts of it — *35 names against 660 non-styling*, and *60 names, 112,100 occurrences* — and 35 + 660 exceeds
the 618 attributes that exist. Neither was wrong so much as unstated: **neither recorded which attributes it counted.**

### The rule

An attribute is **styling** when its name contains any of:

`align` · `bgcolor` · `border` · `color` · `fmt` · `font` · `format` · `height` · `indent` · `padding` · `style` · `width` ·
`wraptext`

**unless it is named as an exception below.** The rule lives in `tools/catalog_survey.py` as `STYLING_MARKERS`, applied by one
function, so the document and the code cannot drift apart.

### The exceptions, each decided by reading the values

FR-34 puts *"any difference in displayed data, column set, filter behaviour, or ordering"* on the **defect** side. So an
attribute that changes what a reader sees as **data** stays in scope however format-ish its name looks. Ten do:

| Attribute | Occurrences | Values it actually carries | Decision |
|---|---:|---|---|
| `fmt` | 12,124 | only `text` and `html` | **Structural.** Whether cell content is interpreted as markup or shown literally. `<b>x</b>` renders bold or displays as markup — that is displayed data |
| `textFormat` | 121 | `html`, `plain`, `plainNBSP`, `imageURL` | **Structural.** Same interpretation switch |
| `customFormat` | 71 | `#.00 M`, `dd-MMM-yy`, `dddd, MMMM dd, yyyy` | **Structural.** A mask decides whether 1500000 reads as `1.50 M` |
| `formatMask` | 1 | (empty) | **Structural.** Same class as `customFormat` |
| `biFormat` | 1 | `dateODBC` | **Structural.** How a date value is encoded |
| `defaultFormat` | 218 | `analyze`, `html`, `pdf` | **Structural.** Which delivery format a link opens in — behaviour |
| `outputFormat` | 263 | `html,pdf,rtf,xlsx,pptx` | **Structural.** The delivery formats a report offers |
| `format` | 7 | `html`, `pdf`, `excel` | **Structural.** A delivery format |
| `formatOutputType` | 4 | `delimited` | **Structural.** A delivery encoding |
| `renderFormat` | 1792 | only `default` | **Structural.** A delivery selector |

**`fmt` is the reversal worth noticing.** It is the second-largest name the naive rule catches, and it is not styling at all.
A rule applied without reading the values would have excluded 12,124 occurrences of a data-affecting attribute and called it
formatting.

### Two exclusions with a consequence

These stay excluded — they are CSS and geometry — but the exclusion is not the same as *cannot matter*:

| Attribute | Caveat |
|---|---|
| `style` | 138 of 1003 values are `display:none`. Styling can **hide content**, and hidden content is a column-set difference, which FR-34 calls a defect |
| `height` | 565 of 4237 values are `0`, which hides as effectively as `display:none` |

Recorded here rather than silently, because "excluded as styling" and "cannot affect the numbers" are different claims and
only the first is true.

### The result

| Population | Distinct names | Occurrences |
|---|---:|---:|
| Styling — excluded from the audit per FR-34 | **50** | **97,498** |
| Structural — in scope | **568** | **474,859** |
| **Total** | **618** | **572,357** |

Both partitions reconcile against the total, which is the check the earlier counts could not pass.

| Styling attribute | Occurrences |
|---|---:|
| `wrapText` | 14060 |
| `fontSize` | 7190 |
| `width` | 6033 |
| `borderPosition` | 5551 |
| `color` | 5306 |
| `fontColor` | 4848 |
| `lineStyle` | 4536 |
| `paddingTop` | 4262 |
| `paddingBottom` | 4245 |
| `height` | 4237 |
| `paddingLeft` | 4101 |
| `paddingRight` | 4001 |
| `backgroundColor` | 3951 |
| `fontStyle` | 3522 |
| `lineWidth` | 3193 |
| `vAlign` | 2858 |
| `borderColor` | 2766 |
| `hAlign` | 2475 |
| `barStyle` | 1683 |
| `fillStyle` | 1652 |
| `scatterStyle` | 1628 |
| `symbolColor` | 1075 |
| `style` | 1003 |
| `borderStyle` | 972 |
| `fontFamily` | 681 |
| `bgColor` | 569 |
| `setWidthToAllPrompts` | 237 |
| `needleStyle` | 225 |
| `showBorder` | 172 |
| `autoCreateFormats` | 136 |
| `labelFormat` | 59 |
| `bubbleColor` | 51 |
| `strokeWidth` | 42 |
| `fontEffects` | 27 |
| `heightPixels` | 20 |
| `cellWidthType` | 14 |
| `fontWeight` | 13 |
| `backgroundColorFrom` | 11 |
| `backgroundColorTo` | 11 |
| `nodeLabelColor` | 11 |
| `behindTheWheelColor` | 11 |
| `fillSectorsWithStatusColor` | 11 |
| `underLineStyle` | 11 |
| `cellWidthValue` | 10 |
| `useIncDecColor` | 7 |
| `strokeColor` | 6 |
| `indentPixels` | 5 |
| `valueHierarchyIndent` | 5 |
| `inputHeight` | 4 |
| `fillColor` | 1 |

## Vocabulary of the four modelled object types

Epic 2 models four of the 59 root types — **2850 files, 53% of the tree**. The other 55 are reported as `unmodelled_type` by
Story 2.7, enumerated by parsing rather than from a list.

Elements and structural attributes below are the 20 most frequent of each; styling attributes are counted but not listed,
per the rule above.


### `sawd:dashboard` — 111 objects · Story 2.4

`xmlVersion`: `200810300` on 111.

7 distinct elements; 12 structural and 1 styling attributes.

| Element | Occurrences |
|---|---:|
| `sawd:dashboardPageRef` | 1041 |
| `sawd:dashboard` | 111 |
| `sawd:dashboardPageGroup` | 85 |
| `saw:caption` | 85 |
| `saw:text` | 85 |
| `sawd:dashboardHiddenPromptRef` | 34 |
| `sawd:dashboardFiltersAndVariables` | 19 |

| Structural attribute | Occurrences |
|---|---:|
| `sawd:dashboardPageRef@path` | 1041 |
| `sawd:dashboardPageRef@type` | 1041 |
| `sawd:dashboardPageRef@hidden` | 1041 |
| `sawd:dashboard@xmlVersion` | 111 |
| `sawd:dashboardPageGroup@id` | 85 |
| `sawd:dashboardPageGroup@showAddToBBLink` | 84 |
| `sawd:dashboard@fitContent` | 70 |
| `sawd:dashboard@promptsAutoComplete` | 29 |
| `sawd:dashboard@links` | 17 |
| `sawd:dashboard@promptApplyButtonsState` | 7 |
| `sawd:dashboard@promptResetButtonsState` | 5 |
| `sawd:dashboardPageRef@showAddToBBLink` | 5 |

### `sawd:dashboardPage` — 1036 objects · Story 2.4

`xmlVersion`: `200810300` on 1036.

68 distinct elements; 145 structural and 34 styling attributes.

| Element | Occurrences |
|---|---:|
| `saw:displayFormat` | 4881 |
| `saw:formatSpec` | 4881 |
| `saw:caption` | 4431 |
| `saw:text` | 4431 |
| `sawd:dashboardSection` | 3113 |
| `sawd:dashboardColumn` | 1905 |
| `sawd:htmlView` | 1754 |
| `sawd:HTML` | 1754 |
| `sawd:reportView` | 1722 |
| `sawd:reportRef` | 1722 |
| `sawd:dashboardPage` | 1036 |
| `sawd:globalFilterView` | 887 |
| `sawd:kpiRef` | 777 |
| `sawd:linkCaption` | 631 |
| `sawd:linkView` | 630 |
| `sawd:image` | 602 |
| `sawd:sectionHeading` | 523 |
| `saw:zone` | 275 |
| `saw:bipLayout` | 227 |
| `sawd:dimensionValue` | 201 |

| Structural attribute | Occurrences |
|---|---:|
| `sawd:dashboardSection@name` | 3113 |
| `sawd:dashboardSection@duid` | 3113 |
| `sawd:dashboardSection@showSectionTitle` | 3113 |
| `sawd:dashboardSection@collapsible` | 2866 |
| `sawd:dashboardSection@layoutType` | 2604 |
| `sawd:dashboardColumn@name` | 1905 |
| `sawd:dashboardColumn@duid` | 1905 |
| `sawd:htmlView@name` | 1754 |
| `sawd:htmlView@duid` | 1754 |
| `sawd:HTML@fmt` | 1749 |
| `sawd:dashboardColumn@canFreeze` | 1739 |
| `sawd:reportView@name` | 1722 |
| `sawd:reportView@display` | 1722 |
| `sawd:reportView@showView` | 1722 |
| `sawd:reportView@duid` | 1722 |
| `sawd:reportRef@type` | 1722 |
| `sawd:reportRef@path` | 1722 |
| `sawd:dashboardColumn@layoutType` | 1599 |
| `sawd:dashboardColumn@frozen` | 1432 |
| `sawd:dashboardSection@horizontalLayout` | 1065 |

*Truncated to the 20 most frequent of each. Full vocabulary: `python3 -m tools.catalog_survey --catalog <path> --section vocabulary`.*

### `saw:report` — 1607 objects · Stories 2.5, 2.6

`xmlVersion`: `201201160` on 1504, `(none)` on 103.

356 distinct elements; 486 structural and 77 styling attributes.

| Element | Occurrences |
|---|---:|
| `sawx:expr` | 23877 |
| `saw:formatSpec` | 20173 |
| `saw:displayFormat` | 19735 |
| `saw:caption` | 18818 |
| `saw:text` | 17657 |
| `saw:edge` | 16568 |
| `saw:column` | 14429 |
| `saw:edgeLayer` | 12436 |
| `saw:view` | 10879 |
| `saw:columnFormula` | 10474 |
| `saw:columnRef` | 7500 |
| `saw:edgeLayers` | 5999 |
| `saw:columnHeading` | 5891 |
| `saw:title` | 5504 |
| `saw:cvCell` | 5312 |
| `saw:seriesFormatRule` | 5250 |
| `saw:seriesCondition` | 5250 |
| `saw:visualFormats` | 5250 |
| `saw:visualFormat` | 5250 |
| `saw:measure` | 5009 |

| Structural attribute | Occurrences |
|---|---:|
| `sawx:expr@xsi:type` | 23877 |
| `saw:edge@axis` | 16568 |
| `saw:edgeLayer@type` | 12436 |
| `saw:column@columnID` | 11143 |
| `saw:column@xsi:type` | 11143 |
| `saw:view@xsi:type` | 10879 |
| `saw:view@name` | 10879 |
| `saw:edgeLayer@columnID` | 10360 |
| `saw:caption@fmt` | 10240 |
| `saw:edge@showColumnHeader` | 10052 |
| `saw:columnRef@columnID` | 7500 |
| `saw:cvCell@viewName` | 5312 |
| `saw:seriesCondition@position` | 5250 |
| `saw:measure@columnID` | 5009 |
| `saw:title@mode` | 4547 |
| `sawx:expr@op` | 4058 |
| `saw:visualFormat@symbol` | 3538 |
| `saw:axisFormat@axis` | 3193 |
| `saw:formatSpec@suppress` | 3075 |
| `saw:caption@captionID` | 3056 |

*Truncated to the 20 most frequent of each. Full vocabulary: `python3 -m tools.catalog_survey --catalog <path> --section vocabulary`.*

### `sawsf:savedFilterObject` — 96 objects · Story 2.6

`xmlVersion`: `(none)` on 96.

5 distinct elements; 12 structural and 0 styling attributes.

| Element | Occurrences |
|---|---:|
| `sawx:expr` | 1360 |
| `sawsf:savedFilterObject` | 96 |
| `saw:filter` | 96 |
| `saw:columnFormula` | 46 |
| `saw:catalogColumnRef` | 1 |

| Structural attribute | Occurrences |
|---|---:|
| `sawx:expr@xsi:type` | 1360 |
| `sawx:expr@op` | 658 |
| `sawsf:savedFilterObject@subjectArea` | 96 |
| `sawx:expr@path` | 76 |
| `sawx:expr@name` | 76 |
| `sawx:expr@formulaUse` | 46 |
| `sawx:expr@displayUse` | 46 |
| `saw:columnFormula@formulaUse` | 46 |
| `sawx:expr@protected` | 4 |
| `sawx:expr@default` | 4 |
| `saw:catalogColumnRef@path` | 1 |
| `saw:catalogColumnRef@columnID` | 1 |

## `saw:criteria[@subjectArea]` is not always a Subject Area

FR-7's join key, captured verbatim and unresolved. **67 distinct values, and only 27 of them are Subject Area names.**

| Form | Distinct values | Example |
|---|---:|---|
| Quoted Subject Area | 27 | `"A - Sample Sales"` |
| **Uploaded dataset** | **40** | `XSA('prodney'.'Sample Pharma')` |

The `XSA(...)` form names a **Visual Analyzer uploaded dataset**, not a Subject Area — there is no semantic layer for it to
resolve into, in this estate or any other. Whatever eventually implements FR-7 must not join an XSA value against
`presentation_subject_areas`: the names will never match, and a resolver that treats a non-match as a broken reference would
report 40 of 67 values as dangling when they are nothing of the kind.

This is the reason the value is stored **untouched, quotes included**. Normalising it — stripping quotes, unwrapping the
XSA form, lowercasing — would erase the very distinction that tells a later reader which values are joinable at all.

## Constructs Epic 2 depends on, measured

Named here because a story quoting a count is not the same as a parse producing one.

| Construct | Count | Owner |
|---|---:|---|
| `saw:report` roots (Analyses) | 1607 | 2.5 |
| `saw:criteria` | 1789 | 2.5 |
| `saw:criteria[@subjectArea]` | 1680 | 2.5 |
| `saw:column` | 14,749 | 2.5 |
| `saw:columnFormula` | 10,866 total, **10,474 inside `saw:report`** | 2.5 |
| `saw:paSimpleColumnFormula` | 42 | 2.5 |
| `sawd:dashboard` roots | 111 | 2.4 |
| `sawd:dashboardPage` roots | 1036 | 2.4 |
| `sawd:dashboardPageGroup` | 85 | 2.4 |
| `sawd:reportRef[@path]` | 1722 | 2.4 |
| `sawd:dashboardPageRef[@path]` | 1041 | 2.4 |
| `saw:filter` | 1086 | 2.6 |
| `sawsf:savedFilterObject` roots | 96 | 2.6 |
| `sawx:expr[@xsi:type="sawx:savedFilter"]` | 417 | 2.6 |
| `saw:prompt` | 1997 | 2.6 |
| `saw:setPromptVariable` | 1311 | 2.6 |
| `sawd:globalFilterView[@path]` | 887 | 2.6 |

**`saw:columnFormula` is 10,866 across the tree but only 10,474 inside Analyses.** The remaining 392 sit in `saw:view`,
`sawsf:savedFilterObject` and other roots Epic 2 does not model — so a Knowledge Base built by this epic carries 10,474 of
them, and the difference is content the coverage report must account for rather than an extraction failure.

## What is absent from this fixture

Stated so a later reader can tell "not present here" from "not supported":

- **No `.atr` files.** No permissions, ACLs, ownership or timestamps anywhere. Access control is absent entirely, and silence
  must not be read as *unrestricted*.
- **`/company_shared/`** — a second catalog root that 1161 references point into and this fixture does not contain. A partial
  catalog export is a normal state the tool will meet in the field.
- **No matched RPD.** The catalog references 86 Subject Areas, the available RPD holds 21, overlap zero. FR-7 is therefore
  buildable and unverifiable, which is why it is Epic 4 (`web-catalog-findings.md` §3).
