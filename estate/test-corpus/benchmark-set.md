# Benchmark Set — Subject Areas by Difficulty Tier

**What this covers:** the six Subject Areas accuracy is measured against, the tier each sits in, and the Knowledge Base evidence that placed it there.
**Who it is for:** anyone reading a per-tier accuracy figure who needs to know what "Simple" and "Medium" actually mean here.

**Writer: Operator.** `estate/test-corpus/` has one writer (AD-18).

*Tiers apply to **Subject Areas**, not Dashboards, per the FR-30 amendment of 2026-08-16. The corpus contains no Web Catalog. See `documents/planning-artifacts/sprint-change-proposal-2026-08-16.md`.*

## Scope limit — read before quoting any figure from this set

**Tiering measures the difficulty of the *semantic* migration only.** Report-layer difficulty — visual count, prompt complexity, drill paths, tab structure — is **unassessed and is not claimed**. There is no Web Catalog in the corpus, so no Dashboard exists to assess.

A "Simple" Subject Area here means its *metric logic* is simple. It says nothing about how hard the reports built on it would be to migrate.

## Criteria

Every criterion is a query against the Knowledge Base, not a judgement. That is the one respect in which this is stronger than the original Dashboard-based framing: another Operator running the same queries reaches the same assignment.

| Criterion | Knowledge Base source |
|---|---|
| Multiple Logical Table Sources | `logical_columns.mapped_source_count > 1` |
| Non-default aggregation rule | `aggregation_rules.is_default = false` |
| Time-series function | `AGO` / `TODATE` / `PERIODROLLING` in `logical_columns` expression columns |
| Shared logical tables | `logical_columns.table_id` reached from two Subject Areas via `presentation_columns` → `presentation_tables` |

**Simple** — no measure uses multiple sources, a non-default aggregation rule, or a time-series function.
**Medium** — at least one of the three is present.
**Tangled** — Constructed Cases (Story 1.9). Not drawn from this corpus, because the constructs that define the tier are absent from it.

## The set

| # | Subject Area | `rpd-id` | Tier | Criterion that placed it |
|---|---|---|---|---|
| 1 | Densification - US Crime By State | `sampleapp` | **Simple** | 7 columns, 1 measure, no multi-source, no override, no time-series |
| 2 | Population | `sampleapp` | **Simple** | 3 columns, 1 measure, none of the three criteria present |
| 3 | Anton_Tserakhau_demo | `bi-analytics-2013` | **Simple** | 27 columns, 2 measures, none of the three present — **and shares logical tables with #5** |
| 4 | Sample Sales | `sampleapp` | **Medium** | **11 multi-source columns**, 8 measures |
| 5 | Anton_Tserakhau | `bi-analytics-2013` | **Medium** | **Time-series function present** — and shares logical tables with #3 |
| 6 | HR_TEAM_VAV | `bi-analytics-2013` | **Medium** | **9 multi-source columns**, including partially-mapped ones |

Three Simple, three Medium — above the two-per-tier minimum.

## Evidence

### #4 Sample Sales — multi-source

```
sampleapp::bmm::SAMPLESALES.Dim Time.Per Name Half     mapped_sources 2/2
sampleapp::bmm::SAMPLESALES.Dim Time.Per Name Month    mapped_sources 2/2
```

### #5 Anton_Tserakhau — time-series

```
bi-analytics-2013::bmm::Anton_Tserakhau.Operations.Sales ago month ($)

Ago("Anton_Tserakhau"."Operations"."Total Sales ($)" ,
    "Anton_Tserakhau"."Time: Year-Quarter-Month-Week-Day"."Month" , 1)
```

**This is the only `AGO` expression in the entire corpus.** The Medium tier's time-series criterion rests on a single instance, which is thin and is stated as such rather than presented as a class of evidence.

### #6 HR_TEAM_VAV — multi-source, and the more interesting kind

```
bi-analytics-2013::bmm::HR_TEAM_VAV.DEPARTMENTS.CITY         mapped_sources 2/4
bi-analytics-2013::bmm::HR_TEAM_VAV.DEPARTMENTS.COUNTRY_ID   mapped_sources 3/4
```

These columns are **partially mapped**: the table declares four sources, but each column is supplied by only some of them. A source that cannot supply a column cannot satisfy a query needing it — a genuine parity hazard, and the reason `mapped_source_count` exists alongside `source_count` (Story 1.7).

### Model reuse — #3 and #5

```
bi-analytics-2013::bmm::Anton_Tserakhau.Time
bi-analytics-2013::bmm::Anton_Tserakhau.Operations with agregation
```

Both logical tables are reached from **Anton_Tserakhau** and **Anton_Tserakhau_demo**, so Semantic Model reuse is exercised rather than assumed (FR-30).

## Two honest limitations

**1. Reuse can only be exercised on the source carrying personal names.** Across 32 logical tables shared between Subject Areas, **every pair sits inside `bi-analytics-2013`**. The `sampleapp` source has no Subject Areas sharing logical tables at all. So the FR-30 reuse requirement and the recommendation to prefer `sampleapp` for external material are in direct tension. Reuse demonstrations must either use the `bi-analytics-2013` pair — reviewing for personal names first — or be shown structurally without naming objects.

**2. Non-default aggregation rules do not occur.** All 35 `AggrRule` rows in the corpus have `is_default = true`. The Medium tier therefore rests on multi-source mapping and one time-series expression; **dimension-specific aggregation override is not exercised anywhere**, and Story 1.9 must supply it if FR-4 is to claim the construct.

## Tangled tier

Supplied by Story 1.9's Constructed Cases, not by this corpus. The four constructs it must author — LTS fragmentation, LTS priority order, `PERIODROLLING`, implicit fact column — are absent or near-absent here, which is precisely why the tier cannot be drawn from real content. Coverage measurements are in `environment.md` §3b.
