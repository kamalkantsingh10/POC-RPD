# As-Is Analysis — document structure

One document, **three readers with different needs**. It serves all three only if each has
its own section; blending them serves none.

| Reader | Needs | Section |
|---|---|---|
| Human reviewer | Verbatim logic + citations, to judge correctness | §3, §4 |
| Data Engineering | Requirements — grain, filters, joins, volumes | §5, §6 |
| Architect (later) | The semantic contract — measures, dimensions, RLS | §3, §7 |

---

## 1. What this covers, and who it is for

Subject Area name, `rpd-id`, extraction timestamp, extractor version. One short paragraph
on what the Subject Area appears to be about, drawn from its tables and measures.

## 2. What this document cannot see

**Before anything else.** Extraction errors and unparsed counts for this slice; report-level
logic absent (Web Catalog); physical detail partial (no DDL, indexes, partitioning, ETL,
stored-procedure bodies). A reader who assumes completeness is the failure mode.

## 3. Measures

The heart of the document. One subsection per measure:

- Presentation name, and the logical column behind it (both `row_id`s).
- **Formula verbatim**, in a fenced code block. Give `expr_text_desc` for readability and
  note that `expr_text` plus `expr_refs` is the authoritative form.
- Aggregation rule. **If more than one rule exists, list every one** and mark which is the
  default — the non-default ones are dimension-specific overrides, and losing them changes
  numbers silently.
- Time-series function, if any (`AGO`, `TODATE`, `PERIODROLLING`), with its window.
- Source count: `mapped_source_count` of `source_count`. **If they differ, say so** — a
  source that cannot supply this column cannot answer a query needing it.

## 4. Attributes and hierarchies

Non-measure columns grouped by presentation table. For each: presentation name, logical
column, physical column, datatype, and the rename chain where the names differ.

## 5. Physical objects — what Data Engineering needs

Tables in a table, each with: name, schema, type (`table` vs `select`), row count where
recorded, and which measures depend on it.

**Call out `select`-type tables separately.** They are SQL-defined rather than physical, so
a rebuild must reproduce the query, not just the table.

Then joins: physical joins with their columns, and BMM joins with their **type** — inner
versus left outer changes row counts without changing any measure.

## 6. Filters, fragmentation and variables

- **Content filters** (`WhereClause`) per Logical Table Source, verbatim.
- **Fragmentation** (`FragmentContent`) per source, verbatim. **Present-but-empty is not the
  same as absent** — say which it is.
- **Priority** per source. Empty means *not recorded*, never *lowest*.
- **Variables** referenced, with their initialisation SQL and whether session or repository.

## 7. Security

Roles, privileges, and row-level predicates. Predicates live on Logical Table Sources, not
on roles, so show both and how they connect. A role with no predicate and a predicate
reachable from no role are both real states — show them rather than tidying them away.

## 8. Open questions for review

Anything the extractor recorded but could not resolve, plus anything genuinely ambiguous —
a measure with multiple sources and no recorded priority, an expression whose references
did not resolve. **Surfacing these is the point, not a blemish.** A reviewer's disagreement
here is the most valuable output the document produces.

## 9. Provenance

Knowledge Base path, `extracted_at`, `extractor_version`, slice row counts, and the command
that regenerates this document.

---

## Citations

**Every factual statement carries the `row_id` it came from.** Not decoration: it is what
lets a reviewer challenge one claim and have it re-derived, rather than regenerating the
document and hoping.

Inline is fine — `(sampleapp::bmm::SAMPLESALES.Fact.Revenue)` — or a trailing column in a
table. Consistency matters more than the form.
