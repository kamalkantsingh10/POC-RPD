# Web Catalog — what we established, and what is still open

**What this covers:** whether the OBIEE Web Catalog can be extracted, what a real one looks like, and where the search for a matched RPD-plus-catalog pair got to.
**Who it is for:** whoever picks up FR-6 / FR-7.

**Writer: Operator.** `estate/test-corpus/` has one writer (AD-18).

*Recorded 2026-08-17. The search for a repository containing both an RPD and a catalog is **unfinished**, paused on GitHub rate limiting — see §5.*

## 1. What the Web Catalog is

OBIEE's store for the **report layer**, entirely separate from the RPD: Analyses, Dashboards, pages, prompts, saved filters, agents, KPIs, scorecards. The RPD holds what a metric *means*; the catalog holds what someone *built* with it.

It is a filesystem tree. Each object is two files:

| File | Format | Contents |
|---|---|---|
| `<object>` | **XML** | The definition — the Analysis, the Dashboard layout |
| `<object>.atr` | **Binary** | Permissions, ACL, owner, timestamps |

**The content is XML**, so parsing it is the same class of problem as MDS XML: a second inbound adapter under AD-1/AD-20, not a rewrite. The `.atr` files are binary and share the binary `.rpd`'s status — out of scope, with the loss stated (who could see what).

Extraction needs a **one-time export, not server access**: `runcat.sh` (`$DOMAIN_HOME/bitools/bin` in 12c) archive/unarchive, or a plain copy of the catalog directory.

## 2. A real catalog was found

**`github.com/gittestbyat/obiee_sample_git`** — SampleApp **v607**'s catalog. Cloned to `~/Documents/Garage/obiee-corpus/obiee_sample_git`, pinned at:

```
5266344cbf9f319c86cad5718eb456c0a9b290a6   (2019-08-06)
```

5371 files, 420 MB expanded. Object types by root element:

| Root element | Count | What it is |
|---|---|---|
| `saw:report` | 1607 | Analyses |
| `sawd:dashboardPage` | 1036 | Dashboard pages |
| `saw:view` | 530 | Views |
| `saw:action` | 115 | Actions |
| `sawd:dashboard` | 111 | Dashboards |
| `sawsf:savedFilterObject` | 96 | Saved filters |
| `sawbsc:*`, `sawkpi:kpi` | 263 | Scorecard objects and KPIs |

**⚠️ Counts corrected 2026-08-20.** This table previously read 1108 / 854 / 355 / 101 / 77 / 58 / 95 — understated by roughly a
third across every type. The figures above come from parsing every one of the 5371 files and counting root elements; the epic's
own *Measured before planning* table agrees with them exactly. The original survey appears to have covered a subdirectory rather
than the tree.

**The same undercount reached the architecture.** AD-21 recorded `saw:columnFormula` as *"verified across 409 expressions"*; the
measured count is **10,866**. AD-21's rule is unaffected — the catalog does store exactly one representation — but its evidence
line was corrected on the same date.

**Two populations this survey missed entirely:**

- **1030 of the 5371 files are not XML at all.** Catalog objects are extensionless, so they cannot be filtered out before
  parsing. Their content is described in §7 — it is **ten distinct binary formats, not two**, and a majority sit outside BI
  Publisher folders.
- **59 distinct root element types are present**, not seven. Beyond OBIEE's own objects the tree holds a second product
  (`xdm:dataModel` 162, an undeclared-prefix `oxp/xmlp:report` 156, `oxp/config:config` 85), raw data exports (`DATA_DS` 86,
  `ROWSET` 14) and around thirty one-off business-document roots.

**`xmlVersion` is absent more often than it is present in any single value:** `201201160` on 1504 roots, `200810300` on 1147,
`201106170` on 47, and **none at all on 1643** — 38% of parseable roots, including every saved filter and 103 Analyses.

**No `.atr` files** — permissions were not committed. Content is intact; access control is absent.

### Verified structure

Object names are URL-encoded in filenames (`%2e` for `.`, `+` for space). Dashboards live under `_portal/`:

```
01%2e+quickstart/_portal/1%2e00+general+index/dashboard+layout
01%2e+quickstart/_portal/1%2e00+general+index/page+1
```

A dashboard layout:

```xml
<sawd:dashboard xmlns:saw="com.siebel.analytics.web/report/v1.1"
                xmlns:sawd="com.siebel.analytics.web/dashboard/v1.1"
                xmlVersion="200810300">
  <sawd:dashboardPageGroup>
    <saw:caption><saw:text>Main Index</saw:text></saw:caption>
    <sawd:dashboardPageRef path="Main Index" type="catalog"/>
```

An Analysis — **note `subjectArea` and `columnFormula`**:

```xml
<saw:report xmlns:saw="com.siebel.analytics.web/report/v1.1"
            xmlns:sawx="com.siebel.analytics.web/expression/v1.1">
  <saw:criteria subjectArea="&quot;A - Sample Sales&quot;">
    <saw:column columnID="cbf6d0054ff5f743c">
      <saw:columnFormula>
        <sawx:expr xsi:type="sawx:sqlExpression">"Base Facts"."1- Revenue"</sawx:expr>
```

`saw:criteria/@subjectArea` is the join key FR-7 needs. **`saw:columnFormula` is report-level logic** — calculations defined in the Analysis rather than the RPD, which the as-is analysis document currently has to declare invisible.

## 3. It does not pair with our RPD

Subject Areas referenced by the catalog versus those in our extracted Knowledge Base:

| | Count | Examples |
|---|---|---|
| Catalog | 86 | `A - Sample Sales`, `X - Airlines Delay`, `U - Usage Tracking`, `Y13 - Sports Demo` |
| Our RPD | 21 | `Sample Sales`, `Population`, `Densification - US Crime By State` |
| **Overlap** | **0** | — |

The catalog is SampleApp **v607**; our `sampleapp` RPD is a different, older instance. **They are separate estates and cannot be joined.**

**Do not attempt to pair them by name similarity.** That is AD-8 verbatim — *name equality is not semantic equality* — and pairing a catalog to an RPD must be a human declaration, exactly like a Report Group.

## 4. What this changes

| Requirement | Before | Now |
|---|---|---|
| **FR-6** parse catalog structure | No fixture — unwritable under AD-19 | **Unblocked.** Real fixture, 1607 analyses, 111 dashboards |
| **FR-7** resolve catalog to semantic layer | No fixture | Buildable, **still unverifiable** — needs a catalog and RPD from one estate |
| Report-level logic in the as-is document | Declared permanently invisible | Extractable, once FR-6 lands |
| Dashboard-first analysis | Impossible | Possible for a catalog-only estate; end-to-end lineage still needs a pair |

## 5. The matched pair — searched, not found

Searched 2026-08-17 via browser and web index after GitHub's code-search API throttled (empty results, then 403, then 503 — a throttled search returns `total_count: 0`, which must not be read as absence).

### What was searched

| Fingerprint | Finds |
|---|---|
| `com.siebel.analytics.web` · `sawd:dashboardPageRef` · `saw:columnFormula` | Catalog content |
| `oracle/bi/server/base` · `www.oracle.com/obis/repository` | MDS XML RPD |
| Both in one repository | The matched pair |

### Results

- **Catalog only:** `gittestbyat/obiee_sample_git` (§2). Also two incidental hits — `ccci/obiee`, a Java client library whose repository now 404s, and a gist by `rmoff` containing a single Analysis fragment. Neither is a corpus.
- **RPD only:** `VasiliKorzun/BI-Analytics-2013`, `rvijay17/obiee`, plus one indexed file under a `src/oracle/server/base/` layout whose repository could not be identified — the direct search for it returned nothing.
- **Both:** **none found.**
- **`.bar` files on GitHub:** none found.

### How strong is that

**Reasonably strong for public GitHub, and it fits the incentives.** Publishing a matched pair means publishing an organisation's entire semantic layer *and* every report — a far larger disclosure than either half alone. The two sources we did find look like personal backups or accidents; a full pair is a different order of exposure.

**Not proof.** GitHub's own code index was unreachable throughout, so this rests on third-party web indexes, which cover repository *contents* poorly. Worth one retry when the API is healthy — but do not hold work for it.

### What it costs us

Only **FR-7** (resolve catalog columns to the semantic layer). **FR-6 is unblocked** by the catalog-only source: 1607 Analyses and 111 Dashboards is ample to build and test the parser. The gap is one requirement, not the report layer.

## 6. The better route — BAR files

A **BI Archive (BAR) file** is OBIEE 12c's service-instance export and contains **the RPD, the Web Catalog and the security model in one archive**. It guarantees both halves come from the same instance, which is precisely the pairing problem in §3 and §5.

### What we established (2026-08-17)

**A BAR is a zip in a BI-readable layout**, with separate folders for RPD, catalog and security. A 12c or OAS BAR can be opened directly; **BICS BARs are protected and cannot**.

**`SampleAppLite.bar` ships with OBIEE 12c itself** — not a separate download:

```
$ORACLE_HOME/bi/bifoundation/samples/sampleapplite/SampleAppLite.bar
```

It is installed when *Oracle sample application (SampleAppLite)* is selected on the **Initial Application** screen during `config.sh`, alongside `SampleAppLite-datafiles.zip`. Contents: a file-based data source, **2 subject areas**, a set of reports, and read/write/admin application roles.

**Why that matters:** it is a genuine matched pair — RPD *and* catalog from one instance — which is exactly what FR-7 needs to be verifiable. It is small (2 subject areas, not 86), so it proves the resolver rather than exercising it at scale.

**Why we do not have it:** it exists only inside an OBIEE installation. No public download was found, and Oracle's own note on the subject sits behind a support login. Same wall as the SampleApp appliance.

### How to get one

| Route | Cost | Gives |
|---|---|---|
| **Ask the team for a BAR export of a real estate** | One export request | Real RPD + catalog + security, matched. **Best outcome** |
| Anyone with OBIEE 12c installed copies `SampleAppLite.bar` | A colleague with an install | Small matched pair, ideal as an FR-7 fixture |
| Install OBIEE 12c ourselves | Blocked — no licence | — |

**Ask for the BAR before asking for separate RPD and catalog exports.** One request, guaranteed-matched halves, and it carries the security model too.

### What the OAS 2026 download actually contained (verified 2026-08-17)

`V1055080-01.zip`, 4.3 GB, Oracle Analytics Server 2026 for Linux. Unpacked and searched across all **449 payload jars** without installing.

**`SampleAppLite.bar` is NOT in OAS 2026.** Oracle changed it. What ships now is `bifoundation/server/samples/SampleAppLite/` containing **seven XML data files only** — `SAMP_REVENUE_F`, `SAMP_TIME_DAY_D`, `SAMP_OFFICES_D`, `SAMP_PRODUCTS_D`, `SAMP_TARGETS_F`, `SAMP_REVENUE_A`, `SAMP_TIME_MTH_D`. No RPD, no catalog, no `.bar`. The only `.bar` files present are `ee.bar` / `se.bar` / `datalake.bar` — 10 KB edition definitions, not sample content.

Searched and confirmed absent across the whole installer: any MDS XML tree, any catalog content.

### ⚠️ A BAR contains a BINARY `.rpd`, not MDS XML

Verified by opening `ee.bar`. **This is the finding that changes what to ask for:**

```
META-INF/MANIFEST.MF
authmodel/jazn/jazn-data.xml            security model
authmodel/jazn/mappings.json
content/init/bootstrapapproles.xml
content/catalog/                        ← Web Catalog — WE CAN PARSE THIS
content/msgdb/
datamodel/rpd/default.rpd               ← BINARY RPD — WE CANNOT PARSE THIS
datamodel/customizations/default/default_diff.xml
```

A BAR alone is **not** a parseable matched pair. Its catalog half is usable; its RPD half is the proprietary binary that AD-20 puts out of scope.

**Therefore the ask is: RPD exported as MDS XML *and* the catalog, in one folder** — the estate-folder layout in Epic 2 Story 2.3. A BAR is useful but insufficient on its own; it still needs the RPD converted.

### Two tools found in the installer, both relevant

| Tool | Path | Why it matters |
|---|---|---|
| **`biserverxmlgen`** | `bifoundation/server/bin/` (Linux binary + `.sh`) | Converts a binary `.rpd` to MDS XML — the missing step for a BAR-sourced RPD |
| **`nqcmd`** | `bifoundation/server/bin/` | Programmatic query path. Bears on PRD §15 Q5 and the §4.8 assumption that programmatic access exists at all |

Neither needs a configured domain to exist on disk — they are binaries in the installed home. Whether they run without a configured instance is unverified.

### Note for whoever writes the adapter

A BAR is a zip: unpack it and the RPD and catalog fall out as the formats we already understand. It is therefore **not a third parser** — it is an unpacking step in front of the two adapters we have or plan. Do not model it as a new serialisation.

## 7. Re-derived independently, 2026-08-20

*Story 2.1 AC #7 required the corrected §2 and §4 counts to be **re-derived**, not copied forward, because they were wrong once
already. A corrected number nobody re-measured is still a number nobody measured.*

**Method.** `tools/catalog_survey.py`, committed alongside this document, parses every file under the catalog root with
`ElementTree` and counts root elements, attributes, `xsi:type` values, `@path` references and their resolution. It is a
committed tool rather than a shell one-liner precisely because the figures it replaces came from surveys nobody could re-run:

```sh
python3 -m tools.catalog_survey --catalog ~/Documents/Garage/obiee-corpus/obiee_sample_git
```

**The fixture is pinned and unchanged**: `5266344cbf9f319c86cad5718eb456c0a9b290a6`, committed 2019-08-06, 5371 files.
Its census is now recorded in `corpus-manifest.csv` under `rpd_id` **`sampleapp-v607`** — 59 root-element rows plus one
`(not XML)` row, summing to exactly 5371. It sits beside the two RPD sources, which are a **different estate** (§3).

**This fixture is a sample, not the target.** The tool targets any OBIEE estate. This corpus is one catalog from one 2019
SampleApp instance, and every count below describes it alone — the same position `corpus.md` takes for the RPD corpus. A
number here is evidence that a construct exists and can be read, never evidence of what another estate contains.

### Confirmed

| Figure | §2/§4 said | Re-derived | |
|---|---:|---:|---|
| Files | 5371 | 5371 | ✅ |
| Parse as XML | 4341 | 4341 | ✅ |
| Do not parse | 1030 | 1030 | ✅ |
| Distinct root types | 59 | 59 | ✅ |
| `saw:report` | 1607 | 1607 | ✅ |
| `sawd:dashboardPage` | 1036 | 1036 | ✅ |
| `saw:view` | 530 | 530 | ✅ |
| `saw:action` | 115 | 115 | ✅ |
| `sawd:dashboard` | 111 | 111 | ✅ |
| `sawsf:savedFilterObject` | 96 | 96 | ✅ |
| `saw:columnFormula` (AD-21's evidence line) | 10,866 | 10,866 | ✅ |
| Distinct attribute names | 618 | 618 | ✅ |
| Attribute occurrences | 572,357 | 572,357 | ✅ |
| `xmlVersion` `201201160` / `200810300` / `201106170` / none | 1504 / 1147 / 47 / 1643 | 1504 / 1147 / 47 / 1643 | ✅ |

**The corrected counts hold.** Every figure the 2026-08-20 correction introduced survives an independent parse.

### Three things the re-derivation changed

**1. The 1030 non-XML files are ten formats, not two.** §2 and Story 2.1 both described them as "`.rtf` templates and `.png`
previews inside `.xdo` folders, plus `.gitignore`". Classified by leading bytes:

| Content | Files | | Containing folder | Files |
|---|---:|---|---|---:|
| PNG image | 561 | | elsewhere | 504 |
| ZIP container (Office document or archive) | 182 | | `*.xdo` (BI Publisher report) | 376 |
| RTF template | 112 | | `screenshots/` (VA project thumbnails) | 87 |
| OLE compound document (legacy Office) | 58 | | `*.xdm` (BI Publisher data model) | 63 |
| JPEG image | 53 | | | |
| unrecognised | 23 | | | |
| `data:` URI text | 17 | | | |
| PDF document | 12 | | | |
| GIF image | 6 | | | |
| Flash movie | 6 | | | |

RTF and PNG together are 673 of 1030, and only 439 sit in a BI Publisher folder. The rest are Visual Analyzer project
thumbnails, embedded Office documents and PDFs attached to dashboards. **The conclusion is unchanged and is what matters** —
none is a catalog object, and Story 2.7 classifies them as *present, not a catalog object* rather than as parse failures. But
the stated reason has to be the true one: a reader who believes the population is BI Publisher templates will look for it in
`.xdo` folders and find under half of it.

*The `.xdo` claim was not baseless — it was measured against the raw on-disk names, where the folder is
`sales+history+report%2exdo`. A test for a `.xdo` suffix finds nothing there and returns zero, and zero was read as
"none outside". Membership has to be tested on the **decoded** path. This is the fourth time on this project a measurement has
been taken through the wrong lens and reported as fact; it is why the survey is now a committed, re-runnable tool.*

**2. A prefix is not an element's name.** `xmlp:dataModel` and `xmlp:report` name nothing that exists: **both BI Publisher
roots sit in `http://xmlns.oracle.com/oxp/xmlp` and declare no prefix on themselves**, using it as their default namespace. The
prefix `xdm` is declared for that URI elsewhere in the corpus, so `xdm:dataModel` is a defensible *rendering* — but it is a
rendering, not what the document says.

This is not pedantry. Keying on the rendered string splits one root type into two: `sawbsc:kpiWatchlistView` is written
prefixed in 10 files and default-namespaced in 5, and counting rendered names reports **60 root types where 59 exist**. The
only stable identity is **namespace URI plus local name**, and the survey now counts on that and renders only for the reader.
Seven namespaces are used as a default namespace somewhere in the corpus; the survey lists them.

The same rule catches two real traps: `saw:reportRef` (21) and `sawd:reportRef` (1722) share a local name across namespaces,
and so do `xsi:type` (62,867) and `xdoeft:type` (1).

**3. Attribute names must be namespace-qualified to reach 618.** Counting local names gives 615 — `xsi:type` merges with
`xdoeft:type`, and two XML Schema instance namespaces are present (`.../2001/...` and a single-occurrence `.../1999/...`,
recorded rather than corrected, per AD-3).

### The fixture's limits, stated rather than left to inference

**No `.atr` files.** Content is intact; **access control is absent entirely** — no permissions, no ACLs, no ownership, no
timestamps. Whoever reads the catalog half of a Knowledge Base built from this fixture **cannot learn who could see what**, and
must not read that silence as "no restrictions applied".

**Licensing: unresolved, and recorded as such.** Oracle SampleApp content in a repository carrying no licence. Same position as
the RPD corpus: the clone lives **outside this repository**, at `~/Documents/Garage/obiee-corpus/obiee_sample_git`, acquired at
a pinned commit rather than vendored in. `.gitignore` already covers `/corpus/` and `/obiee-corpus/`. Treat it as a read-only
reference.

## Licensing

Unresolved, as with the RPD corpus. This is Oracle SampleApp content regardless of who published it, and the repository carries no licence. Treat it as a read-only reference; do not vendor it. See `corpus.md`.
