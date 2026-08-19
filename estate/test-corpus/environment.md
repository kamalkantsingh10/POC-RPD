# Test Corpus Environment

**What this covers:** the environment the Test Corpus is built on — how it was obtained, how to rebuild it, and what it contains.
**Who it is for:** any Operator who needs to reproduce the corpus from scratch, and anyone assessing whether findings from this corpus transfer to a real Estate.

**Status: INCOMPLETE — AC #1 resolved (negative), environment not yet chosen or built.** See §1 and §2.

**Writer: Operator.** Per AD-18, `estate/test-corpus/` has exactly one writer. No agent and no extractor writes to this area.

## 1. Availability Investigation (AC #1) — SampleApp appliance NOT obtainable from Oracle

Checked 2026-08-16, in a browser against `oracle.com` and via GitHub search.

### Verdict

**The SampleApp v607 virtual appliance is no longer published by Oracle on its public site.**

| Check | Result |
|---|---|
| Historic SampleApp URL (`obiee-samples-167534.html`) | Redirects to `.../obiee-samples-downloads.html` → **Page not found** |
| `oracle.com` site search, "SampleApp" | 22 results — JavaFX demos, EPM Cloud threads, analytics docs. **No OBIEE appliance** |
| Automated HTTP fetch of Oracle pages | HTTP 403 anti-bot. Inconclusive alone — the browser check is what settled it |

**Not checked:** Oracle Software Delivery Cloud (`edelivery.oracle.com`), which needs an authenticated Oracle account. **The Operator must check this personally** — credentials never pass through the tool (NFR11, PRD §8.2).

PRD §4.11's assumption — *"the SampleApp appliance is obtainable"* — is **falsified for the public download path**.

### What is still obtainable

| Asset | Where | Notes |
|---|---|---|
| OBIEE 11.1.1.9.0 full installers | `oracle.com/middleware/technologies/bi-downloads.html` — **verified live** | Linux x86-64: 5 files, ~8.7 GB |
| **Oracle BI Developer Client Tool 11.1.1.9.0** (Administration Tool) | Same page, Windows x86-64, 273 MB | **Story 1.9 depends on this and it is available now** |
| Repository Creation Utility 11.1.1.9.0 | Same page | Needed to configure a BI domain |
| `SampleAppLite.rpd` | Ships as the default repository with any Oracle BI EE install | Per Oracle docs. Small, but real and Oracle-authored |
| OBIEE 12c / OAS Docker build files | `github.com/gianniceresa/docker-images` | 54 stars, updated 2026-03-26. See §2 option B |
| A real OBIEE MDS XML repository | `github.com/VasiliKorzun/BI-Analytics-2013` | See "Format discovery" below |

### Format discovery — architecturally significant

`VasiliKorzun/BI-Analytics-2013` contains a **genuine** OBIEE repository serialised as **MDS XML**: namespace `http://www.oracle.com/obis/repository`, opaque MDS GUIDs, and full object-type coverage — `BusinessModel`, `ConnectionPool`, `Database`, `Dimension`, `Group`, `InitBlock`, `LogicalComplexJoin`, `LogicalTable`, `LogicalTableSource`, `ObjectPrivilege`, `PhysicalTable`, `PresentationCatalog`, `PresentationHierarchy`, `PresentationTable`, `PrivilegePackage`, `Project`, `QueryPrivilege`, `Schema`, `Variable`.

That object set covers most of FR-4's parity-critical metadata: `LogicalTableSource` (priority, content filters), `Dimension` (aggregation), `InitBlock` + `Variable` (session and repository variables), `Group` + `ObjectPrivilege` + `QueryPrivilege` (RLS), `LogicalComplexJoin` (join types).

**But it is a different serialisation from the one the PRD assumes.** OBIEE emits repository metadata two ways:

| Format | Shape | PRD position |
|---|---|---|
| `biserverxmlgen` single-file XML | One large XML document | **Assumed by PRD §4.1 and by FR-1** |
| **MDS XML** | Exploded directory, one XML per object, cross-referenced by GUID paths | Not mentioned anywhere in the PRD or Architecture Spine |

This is a real finding for the architecture, not a detail. AD-1 puts every format at an adapter boundary precisely so this kind of surprise is contained — but the Spine's inbound adapter list names only `rpd_xml` and `catalog_xml`. Whether the product targets one format or both is a decision for Winston, and it changes Stories 1.4–1.7. **Raise before Story 1.4 starts.**

### Licensing and privacy caveats on the GitHub finds

- `VasiliKorzun/BI-Analytics-2013` carries **no licence** — default is all rights reserved, so there is no grant to reuse it. It also contains personal names inside Subject Area names (e.g. `Iryna_Bradzetskaya_MT_Full`). Usable as a read-only reference for understanding MDS XML structure; **not** something to vendor into this repository without a decision.
- `cyphou/OACToFabric` was examined and **rejected**. Its six "RPD XML" samples are synthetic — box-drawing comment separators, human-readable `mdsid="phys_cust_001"` where real MDS IDs are opaque GUIDs, a namespace-less `<Repository>` root, and `<LogicalTableSource physicalTable="..."/>` as an empty attribute-only element where a real LTS carries priority, content filters, and column mappings as children. Building a parser against it would encode a fiction. Also unlicensed, and AI-generated (25 KB `AGENTS.md`, zero stars).

## 1a. Real RPD content IS reachable without an Oracle licence

The Operator has no Oracle licence, so every edelivery path is closed. Searching GitHub for the authentic MDS XML structure found **two genuine OBIEE repositories**, both free to read, no download, no VM, no licence.

### Source A — `rvijay17/obiee` — SampleApp content

512 KB, pushed 2014-07-30, no licence. **This is SampleApp-derived**, confirmed three ways: physical table `SAMP_REVENUE_F`, physical schema `SAMPLESALES`, and Subject Areas named **"Sample Sales"**, "Densification - US Crime By State", "Population".

| Object type | Count | | Object type | Count |
|---|---|---|---|---|
| PhysicalTable | 22 | | PresentationTable | 10 |
| LogicalTableSource | 17 | | LogicalComplexJoin | 9 |
| LogicalTable | 11 | | PresentationHierarchy | 5 |
| LogicalSourceFolder | 11 | | Dimension | 5 |
| PresentationCatalog (Subject Areas) | 3 | | Group / ObjectPrivilege | 6 / 6 |

### Source B — `VasiliKorzun/BI-Analytics-2013` — a real-world estate

632 KB, 1253 files, pushed 2013-10-08, no licence. Not SampleApp — a genuine working repository, and far more irregular than SampleApp is by design.

| Object type | Count | | Object type | Count |
|---|---|---|---|---|
| Variable | 343 | | QueryPrivilege | 72 |
| InitBlock | 152 | | LogicalTable | 71 |
| PresentationTable | 118 | | ObjectPrivilege | 62 |
| PhysicalTable | 78 | | PresentationHierarchy | 53 |
| LogicalTableSource | 75 | | Group | 22 |
| LogicalComplexJoin | 75 | | Dimension | 20 |
| Project | 30 | | **PresentationCatalog** | **18** |

**Source B supplies the irregularity PRD §11 says SampleApp cannot.** 343 variables, 152 init blocks and 72 query privileges is accumulated real-world mess, not a demo. Together the two sources give a graded corpus that maps onto FR-30's tiers better than SampleApp alone would.

### Verified structure

A 20 KB `LogicalTableSource` from Source A confirms real MDS XML carrying FR-4 material:

```xml
<LogicalTableSource mdsid="m0000029a-..." name="SAMP_REVENUE_F"
  xmlns="http://www.oracle.com/obis/repository" isActive="true"
  logicalTableRef="/oracle/bi/server/base/LogicalTable/...xml#m000001c9-...">
<ColumnMapping>
  <LogicalColumnExpr ...>
    <ExprText><![CDATA["%1"]]></ExprText>
    <ExprTextDesc><![CDATA["SAMPLESALES"."Fact Revenue"."Bill Day Dt"]]></ExprTextDesc>
    <ObjectRefList><RefObject objectTypeId="2006" objectRef="..."/></ObjectRefList>
  </LogicalColumnExpr>
  <Expr ...>
    <ExprTextDesc><![CDATA["xe".""."SAMPLESALES"."SAMP_REVENUE_F"."BILL_DAY_DT"]]></ExprTextDesc>
  </Expr>
</ColumnMapping>
```

34 `ColumnMapping` blocks and 3 `WhereClause` elements in that one file.

### ⚠️ This changes what FR-2 "verbatim" means — decide before Story 1.5

MDS XML stores an expression **three ways at once**: `ExprText` holds a parameterised form (`"%1"`), `ExprTextDesc` holds the fully-qualified readable form, and `ObjectRefList` holds the actual object references. There is no single "the formula as written" field.

FR-2 requires formula logic captured character-for-character. **Which of the three is the verbatim artifact?** Capturing only `ExprTextDesc` is readable but is a rendering; capturing only `ExprText` is faithful but meaningless without the refs. This is a real decision, it is not answered anywhere in the PRD or the Architecture Spine, and it lands squarely on Story 1.5. Settle it with the Operator.

### What these sources do NOT provide

| Need | Status |
|---|---|
| RPD semantic layer (FR-1..FR-5, FR-8, FR-9) | **Covered** |
| Web Catalog — Dashboards, Analyses (FR-6, FR-7) | Absent. Already deferred to Phase 1 |
| **Six Dashboards across three tiers (FR-30)** | **Not satisfiable.** No catalog, no dashboards |
| **Live data for Parity Checks** | **Absent.** PRD §6.1's one hand-run Parity Check cannot be done |
| Administration Tool for Constructed Cases (FR-31, Story 1.9) | Absent. MDS XML is text, so cases *could* be hand-authored — but hand-written XML may not match what the Admin Tool emits, which weakens the Ground Truth claim |

The first is the bulk of Epic 1. The rest need re-scoping, and that is a `bmad-correct-course` conversation, not a silent adjustment.

### Licensing and privacy — unresolved

**Neither repository carries a licence, so the default is all rights reserved.** Source A additionally contains Oracle's SampleApp metadata, which is Oracle's IP regardless of who posted it. Source B contains personal names inside Subject Area names (e.g. `Iryna_Bradzetskaya_MT_Full`).

Reading them to understand MDS XML structure is one thing. **Vendoring either into this repository is a separate decision** with legal and privacy dimensions, and it should be made deliberately — especially as this POC is intended to be shown to stakeholders. A middle path: keep the corpus outside version control, reference it by URL and commit SHA, and record the fixtures derived from it rather than the source files.

## 2. Environment Options — decision required

The corpus need splits in two, and the options serve them differently:

- **(i) RPD content to parse** — Stories 1.3–1.7, 1.10
- **(ii) A live OBIEE instance** — Story 1.2 (`biserverxmlgen`), Story 1.9 (Administration Tool), and Phase 2 parity against live data

| Option | Serves (i) | Serves (ii) | Cost |
|---|---|---|---|
| **A. SampleApp v607 via edelivery or an archived copy** | Yes | Yes | Lowest, if it exists. ~24 GB, five zips, names documented so a copy is verifiable |
| **B. OBIEE 12c in Docker** (`gianniceresa/docker-images`) | Yes — `SampleAppLite` | Yes | Needs Oracle installer binaries from edelivery, plus a separate Oracle DB for RCU. Docker is already installed on this host |
| **C. OBIEE 11g from the live public installers** | Yes — `SampleAppLite` | Yes | Installers are public *now*. Heavier setup; puts the corpus on **11g**, not 12c |
| **D. MDS XML reference repo** | Partially | No | Free and immediate, but wrong serialisation, unlicensed, and no live data |

**Option B prerequisites** (12.2.1.4.0, from the repo's `Checksum.md5`):

```
fmw_12.2.1.3.0_infrastructure_Disk1_1of1.zip
fmw_12.2.1.4.0_bi_linux64_Disk1_1of2.zip
fmw_12.2.1.4.0_bi_linux64_Disk1_2of2.zip
jdk-8u172-linux-x64.rpm
```

Plus an external Oracle Database reachable at `BI_CONFIG_RCU_DBSTRING` for the Repository Creation Utility. All four binaries come from edelivery — so **option B still depends on the same account check that option A does.** Do that check first; it resolves the choice between A, B, and C in one step.

**None of these options supply a populated Web Catalog with real dashboards** except option A. That matters for FR-30's requirement of six Dashboards across three tiers with two sharing a Subject Area, and for Phase 2 parity work. If option A fails, FR-30 needs re-scoping and that is a `bmad-correct-course` conversation, not a silent adjustment.

**Do not substitute a synthetic corpus.** PRD §4.11 rests the accuracy argument on real Oracle-authored content plus deliberately authored irregularity. A synthetic corpus proves only that the parser handles its own author's assumptions — see the `OACToFabric` rejection above for what that looks like in practice.

## 3. Provenance — corpus acquired 2026-08-16

**Location: `~/Documents/Garage/obiee-corpus/` — deliberately outside this repository.**

Nothing unlicensed enters version control, and nothing ships to the VDI under AD-16 (deployment is a file copy of *this* repo). The extractor reaches the corpus through a path argument, exactly as it will reach a real customer estate. Fixtures derived from it — which we author, and which carry recorded Ground Truth — are what get committed.

| Source | Repository | Pinned commit | Date | XML files | Size |
|---|---|---|---|---|---|
| Real estate | `VasiliKorzun/BI-Analytics-2013` | `19bef42a9574a039a90a40d986c10194aa3376f5` | 2013-10-08 | 1252 | 8.3 MB |
| SampleApp | `rvijay17/obiee` | `9a1c0a28211d981f320e38247b416c754c334398` | 2014-07-30 | 131 | 1.6 MB |

Re-acquisition is `git clone` followed by `git checkout <sha>`. Both are public; no credentials are involved (NFR11 trivially satisfied).

## 3a. Verified structure — what the parser must handle

Attribute and element census across all 1383 XML files, via `ElementTree`.

**Namespace:** `http://www.oracle.com/obis/repository` on every object.

**Cross-referencing:** objects point at each other by `<path>.xml#<mdsid>` — e.g. `logicalTableRef`, `subjectAreaRef`, `presentationTableRef`, `logicalColumnRef`, `variableRef`, `initBlockRef`, `logicalTableSourceRef`. Resolving these is the lineage work in Story 1.7.

**Expressions** appear as `ExprText` (parameterised, `"%1"`) plus `ExprTextDesc` (fully qualified) plus `ObjectRefList`. Confirmed on `AggrRule`, `WhereClause`, `FragmentContent`, and `ColumnMapping`.

Key attributes observed: `mdsid`, `name`, `refId`, `objectRef`, `objectTypeId`, `dataType`, `specialType`, `precision`, `nullable`, `overrideLogicalName` (1484 — the rename chain), `isSessionVar` (179), `refreshPeriod` (152), `isActive`, `isPrimary`, `multiplicity1/2`, `isAggregate1/2`.

Key elements observed: `AggrRule`, `WhereClause`, `FragmentContent`, `LogicalComplexJoin`, `Join`, `LogicalKey`, `LogicalLevel`, `PresentationLevel`, `PhysicalKey`, `PhysicalForeignKey`, `ColumnMapping`.

## 3b. FR-4 coverage — what the corpus proves and what it cannot

Measured by parsing every file and counting elements that are **populated**, not merely present. `FragmentContent` and `WhereClause` exist on all 92 Logical Table Sources; most are empty shells. That distinction is the whole point — an empty element is not a fixture.

| FR-4 construct | Real estate | SampleApp | Status |
|---|---|---|---|
| Aggregation rule | 22 populated | 13 populated | **Covered** |
| Content-level filter | **6 populated** | 0 | **Covered** — incl. a real RLS filter using `valueof(NQ_SESSION.ROLEGUIDS)` |
| BMM join type | 75 `LogicalComplexJoin` | 9 | **Covered** |
| Session / repository variables | 179 files, 1294 `VALUEOF` | 4 files | **Covered, strongly** |
| RLS per application role | Group 22 / ObjPriv 62 / QueryPriv 72 | 6 / 6 / 1 | **Covered** |
| Rename chain | `overrideLogicalName` ×1484 | ×59 | **Covered** |
| `TODATE` | 9 files | 1 file | **Covered** |
| `AGO` | 1 file | 0 | **Thin** |
| LTS priority order | 0 | 1 file | **Thin** |
| **Fragmentation predicates** | **0 populated / 75** | **0 / 17** | **ABSENT** |
| Implicit fact column | `@defaultFactColumnRef` on 1 of 21 catalogs | — | **Thin** |
| **`PERIODROLLING`** | 0 | 0 | **ABSENT** |

*Correction, 2026-08-16:* the implicit fact column was first recorded as absent. That was a bad search term — the attribute is `defaultFactColumnRef` on `PresentationCatalog`, not `implicitFact`. It is thin, not missing. The full observed schema is in `mds-xml-schema.md`, derived by parsing every file rather than grepping for guessed names.

**Consequence for Story 1.10, under AD-19.** *A construct without a fixture is treated as unimplemented.* Three constructs are absent and two are thin, so **five of FR-4's constructs cannot be claimed from this corpus alone**. They require Constructed Cases.

**Consequence for Story 1.9.** There is no Administration Tool, so cases cannot be authored the intended way. MDS XML is plain text and we now hold 1383 real files to model the syntax on, so hand-authoring is viable — and far better grounded than it would have been without the corpus. It remains weaker Ground Truth than Admin-Tool output, and the accuracy claim must say so rather than imply otherwise.

**This is a good outcome, not a shortfall.** The corpus honestly reports which constructs it exercises, which is exactly what FR-5 and NFR7 demand of the tool itself. Accuracy will be reported per construct type (SM-7), so "accurate on these constructs" stays a true statement.

## 4. Versions

*Pending.*

**PRD Open Question 2:** the organisation's own OBIEE version is unknown. Option C would put the corpus on 11g, which widens rather than narrows this gap — accuracy claims made on an 11g corpus are claims about 11g. Record whichever version is chosen; the Architecture Spine's guidance is to isolate schema handling in the inbound adapter so a version difference stays a contained change.

## 5. Host

Verified 2026-08-16 on the development machine.

| Field | Value | Adequate? |
|---|---|---|
| CPU cores | 16 | Yes |
| RAM | 94 GB | Yes |
| Free disk | 383 GB | Yes |
| Hardware virtualization | Present (VT-x/AMD-V, all cores) | Yes |
| Docker | Installed | **Enables option B** |
| VirtualBox | Not installed | Needed only for option A |
| QEMU / virt-manager | Not installed | — |

Installing VirtualBox needs root here. That does **not** conflict with FR-23 — the no-admin constraint governs the product in the VDI, not this development host.

## 6. Import / Build Procedure

*Pending the §2 decision.*

## 7. Start and Stop Procedure

*Pending.* Record service start order and wait times verbatim.

## 8. What Is Present

*Pending.* Record: Dashboard count, Subject Areas, whether `biserverxmlgen` is present (Story 1.2), and whether the Administration Tool is reachable (Story 1.9).

## 9. Programmatic Query Path

*Pending.* Record which of nqcmd / JDBC / ODBC is available. Nothing in Epic 1 consumes it, but it is material to PRD Open Question 5 and to Phase 2, and it is cheap to observe while the instance is up.

## 10. Read-Only Statement

All access to the OBIEE source and the warehouse is **read-only**, in this story and every later one (NFR12, PRD §8.3). No component of this product writes to either.
