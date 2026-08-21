# Constructed Cases — Ground Truth

**What this covers:** five deliberately authored OBIEE constructs, why each is a parity hazard, and the known-correct extraction result for each.
**Who it is for:** anyone reading an SM-7 accuracy figure, and anyone changing the `mds_xml` adapter.

**Writer: Operator.** `estate/test-corpus/` has one writer (AD-18).

`rpd-id`: **`constructed`** — distinct from every corpus `rpd-id`, so case identifiers can never collide with real content (AD-7, AD-8).

## ⚠️ These cases are hand-authored. Read this before quoting any figure from them.

The Oracle BI Administration Tool is unavailable — there is no obtainable OBIEE instance and no licence. These cases were **written directly as MDS XML**, modelled on real corpus files (FR-31, amended 2026-08-16).

**What that costs.** Ground Truth here is *authorial intent*, not observed OBIEE behaviour. If our understanding of the MDS XML format is wrong, a case and its expectation will agree with each other and both disagree with what OBIEE actually emits. This is the circularity risk recorded in PRD §11.

**What limits it.** Every case is modelled on the structure of a real corpus object of the same type, changing only what the case exercises. None was authored from the schema summary alone.

**One honest note on process.** FR-31 requires Ground Truth recorded before the extractor is run against a case. Here the expected values below are *literally the values written into the case XML* — they are the input, not an inference from output — so there is no back-fitting risk. But the extractor was in fact run before this document was written, and the accurate statement is that: the values are traceable to the authored source, not that this file predates the first run.

**Accuracy derived from these cases is reported separately from accuracy measured against real corpus content, and the two are never merged** (FR-31).

## Why these five

Measured coverage (`estate/test-corpus/environment.md` §3b and `benchmark-set.md`) showed the corpus already exercises content filters, BMM join types, multi-source mapping, session and repository variables, RLS roles, the rename chain, and `TODATE`. A real example always beats a constructed one, so those are **not** re-authored here.

These five are the genuine gaps:

| # | Construct | Corpus coverage | Why it is a parity hazard |
|---|---|---|---|
| 1 | **LTS fragmentation predicate** | `FragmentContent` on all 92 sources, **0 populated** | Determines which source answers which slice of data. Miss it and the query reads the wrong table for a date range — a wrong number, not an error |
| 2 | **LTS priority order** | No attribute in corpus | When two sources can both answer, priority decides. Get it wrong and a query silently hits an aggregate table that lacks the needed grain |
| 3 | **`PERIODROLLING`** | **0 occurrences** | Rolling-window time intelligence. A DAX translation that ignores the window bounds returns a plausible total over the wrong period |
| 4 | **Implicit fact column** | 1 of 21 Subject Areas | Governs how a query behaves when only dimension columns are selected. Missing it changes row counts without changing any measure |
| 5 | **Dimension-specific aggregation override** | **All 35 rules are `isDefault=true`** | A measure that sums across products but takes the last value across time. Collapse the override into the default and every time-sliced total is wrong |

Case 5 was added after Story 1.8's analysis found no non-default aggregation rule anywhere in the corpus — the original four-construct list in the Sprint Change Proposal understated the gap by one.

## Expected extraction results

### Case 1 & 2 — fragmentation and priority, on two sources

`logical_table_sources.csv`, two rows:

| `name` | `priority` | `fragment_text_desc` |
|---|---|---|
| `LTS_DETAIL` | `0` | `"CC_SCHEMA"."FCT_SALES_DETAIL"."DAY_DT" >= TIMESTAMP '2020-01-01 00:00:00'` |
| `LTS_MONTHLY_AGG` | `1` | `"CC_SCHEMA"."FCT_SALES_MONTHLY"."MONTH_DT" <  TIMESTAMP '2020-01-01 00:00:00'` |

Both identified as `constructed::bmm::Constructed BM.Fact Sales.src.<name>`.

**The double space in `<  TIMESTAMP` is deliberate and significant.** FR-2 forbids whitespace collapsing anywhere in the chain; if it comes back single-spaced, verbatim capture is broken.

The two predicates are complementary and non-overlapping — the classic date-based fragmentation shape. A parser that captured only one, or merged them, would produce a Knowledge Base implying either source can answer any date.

### Case 3 — `PERIODROLLING`

`logical_columns.csv`, row `constructed::bmm::Constructed BM.Fact Sales.Rolling Amount 3M`:

| Field | Expected |
|---|---|
| `derived_expr_text` | `PERIODROLLING("%1", -2, 0)` |
| `derived_expr_text_desc` | `PERIODROLLING("Constructed BM"."Fact Sales"."Amount", -2, 0)` |
| `derived_expr_refs` | `constructed::bmm::Constructed BM.Fact Sales.Amount` |
| `is_measure` | `false` — it has no `MeasureDefn` |

The window bounds `-2, 0` are the parity-critical part: a three-period trailing window including the current period. All three expression forms must survive (AD-21).

### Case 4 — implicit fact column

`presentation_subject_areas.csv`, row `constructed::pres::Constructed SA`:

| Field | Expected |
|---|---|
| `implicit_fact_column_id` | `constructed::bmm::Constructed BM.Fact Sales.Amount` |

Resolved from `@defaultFactColumnRef` to a Knowledge Base identifier, not left as a GUID (AD-20).

### Case 5 — aggregation override

`aggregation_rules.csv`, **exactly two rows** for `constructed::bmm::Constructed BM.Fact Sales.Amount`:

| `name` | `is_default` | `expr_text` |
|---|---|---|
| `AggRule_Default` | `true` | `` SUM("%1")`` |
| `AggRule_Override_Time` | `false` | `LAST("%1")` |

**Two rows, never one.** This is the case that fails loudest if `AggrRule` elements are collapsed — and collapsing is the natural implementation shortcut, which is exactly why the case exists.

The leading space on `` SUM("%1")`` mirrors real corpus `AggrRule` expressions and must survive.

## Coverage expectations

21 objects parsed, **0 unparsed**. Every reference resolves and every object type present is modelled.

| Object type | Parsed |
|---|---|
| `PhysicalTable` | 2 |
| `PhysicalColumn` | 4 |
| `LogicalTable` | 1 |
| `LogicalColumn` | 2 |
| `AggrRule` | 2 |
| `LogicalTableSource` | 2 |
| `ColumnMapping` | 2 |
| `PresentationCatalog` | 1 |
| `PresentationTable` | 1 |
| `PresentationColumn` | 2 |
| `Schema`, `BusinessModel` | 1 each — index-only |

## Rebuilding

The cases are plain text in this directory and are committed — we authored them, so no licensing question arises, and AD-19 wants fixtures with recorded Ground Truth under version control.

They are a **separate corpus root** from the pinned repositories, which stay unmodified:

```sh
python3 -m tools.rpd_extract.cli \
  --corpus estate/test-corpus/constructed-cases \
  --out <output>
```

---

## The constructed pair — `constructed-catalog/`

**What it covers:** one estate whose *both* halves are present, so a single extraction run carries a repository and a Web Catalog into one Knowledge Base.

**What it does not cover:** anything about how real OBIEE names things. Read the warning at the top of this file again before quoting it — this pair is authored, and both halves were authored by the same hand.

### Why it exists

Pairing was tested only as directory shape. `test_catalog.py` creates an empty `catalog/` beside a stub `<x/>` repository and asserts `is_paired()` — correct, and it says nothing about extraction. No test anywhere ran both adapters into one `Estate`.

That gap mattered because the two real fixtures **are not a pair**. The catalog fixture asks for `"A - Sample Sales"`; the repository fixture defines `Sample Sales`, `Population` and `Densification - US Crime By State`. They are different SampleApp releases, so `analysis_criteria.subject_area` matches nothing — 0 of 1680. Pairing them proves the tool refuses to invent a link (AD-22), which is worth knowing, but it leaves the paired path itself unexercised.

### What it is

Four catalog objects under `constructed-catalog/constructed/`, authored against the presentation layer the constructed repository already defines in `PresentationCatalog/cc-sa.xml`:

| Object | On disk | References |
|---|---|---|
| `sawd:dashboard` | `_portal/sales+overview/dashboard+layout` | `Page One` |
| `sawd:dashboardPage` | `_portal/sales+overview/page+one` | the Analysis, and the saved filter |
| `saw:report` | `revenue+by+month` | Subject Area `"Constructed SA"`, columns `"Sales Facts"."Amount"` and `"Sales Facts"."Rolling Amount 3M"` |
| `sawsf:savedFilterObject` | `_filters/recent+periods` | Subject Area `"Constructed SA"` |

Names are percent-encoded and lowercased on disk exactly as the real fixture's are, which is why every resolution below is `case_normalised` rather than `exact` — the same ratio the real catalog shows.

### Expected extraction result

`--corpus <estate-holding-both> --rpd-id constructed-pair`, where `rpd/` is a copy of `constructed/` and `catalog/` a copy of `constructed-catalog/`:

| Table | Rows |
|---|---|
| `dashboards` / `dashboard_pages` | 1 / 1 |
| `dashboard_contents` | 3 — all three resolved |
| `analyses` / `analysis_criteria` / `analysis_columns` | 1 / 1 / 2 |
| `analysis_filters` | 3 — one dashboard-scope, two analysis-scope |
| `saved_filters` | 1 |
| `presentation_subject_areas` / `presentation_columns` | 1 / 2 |
| `errors` | **0** |

**`errors.csv` empty is the point.** The real fixture cannot make that claim — 1583 of its references point into `/company_shared/`, a catalog root nobody has. Here every reference has a target that exists, so an error row is a regression signal rather than a known condition to be read past. `test_constructed_pair.py` asserts it, and breaking one reference path in the fixture turns the assertion red.

### The one cross-half fact, stated exactly

`analysis_criteria.subject_area` holds `"Constructed SA"` — **quotes included, as the catalog wrote it** — and `presentation_subject_areas.name` holds `Constructed SA`. Strip the quotes and they are equal.

**That is a name matching a name, not a resolved key.** There is no `presentation_subject_area_id`; nothing in `catalog_xml.py` consults the presentation layer. FR-7 is unimplemented, `ARCHITECTURE-SPINE.md` records it as not verifiable against the fixture, and this pair does not change that. What it demonstrates is that the halves *can* be named consistently and land in one Knowledge Base — the mechanism, not the evidence.

**This fixture must never be cited as evidence that real catalogs and real repositories agree.** Both halves were authored here, so agreement is a property of the author, not of OBIEE. That is the circularity FR-31 requires be kept separate, and it is why a matched pair from one service instance — a BAR archive, per `vdi-readiness-checklist.md` — remains the real unlock.

### Rebuilding

The catalog half is not an estate on its own: it declares no `rpd/` or `catalog/` and is not a repository tree, so the multi-estate command above skips it and still reports exactly one `rpd-id`, `constructed`. To assemble the pair, put the two halves under one folder:

```sh
mkdir -p /tmp/pair/constructed-pair
cp -r estate/test-corpus/constructed-cases/constructed         /tmp/pair/constructed-pair/rpd
cp -r estate/test-corpus/constructed-cases/constructed-catalog /tmp/pair/constructed-pair/catalog

python3 -m tools.rpd_extract.cli --corpus /tmp/pair --out <output>
```

They are assembled at run time rather than committed as a third tree so that each half has exactly one copy and the two cannot drift apart.
