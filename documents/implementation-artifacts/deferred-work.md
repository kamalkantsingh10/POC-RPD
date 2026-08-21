# Deferred work

Findings recorded rather than fixed, each with the evidence that produced it.
Every one is visible in the Knowledge Base's own output — none needs
re-derivation from the source corpus to confirm.

- summary: `row_filter` security rows carry no application role
  evidence: `security_rls.csv` has 6 rows of kind `row_filter`, all with an
    empty `role`, while all 73 `query_privilege` rows carry one. FR-4 requires
    "row-level security filters per application role", so the filter is captured
    and the role it belongs to is not. Found by profiling the table per `kind`.

- summary: `PrivilegePackage@userRef` is never read, so grants to named users lose their grantee
  evidence: `unparsed.csv`, `unread_attribute` / `target_not_in_kb`, 3
    occurrences. All 3 packages have no `roleRef` and no children, so the user is
    the only information they carry. Reading it properly also needs the `User`
    object type modelled — it is currently reported as `unmodelled_type`.

- summary: alias tables are not modelled, so an alias does not name what it aliases
  evidence: `unparsed.csv` reports `PhysicalTable@sourceTableRef` (8) and
    `PhysicalColumn@sourceColumnRef` (101) unread. `physical_tables.csv` has no
    column for it, so nothing records that a table IS an alias or of what. In
    OBIEE aliasing is how one physical table is joined several ways, so this is
    a real physical-modelling gap, not bookkeeping.

- summary: logical keys and LTS joins are not modelled
  evidence: `unparsed.csv` reports `RefLogicalColumn@logicalColumnRef` (57,
    inside `LogicalKey`) and `Join@physicalTable1Ref`/`2Ref` (36 each) unread.
    No table carries either concept, so "these columns form the key" and the
    source's own join specification are absent.

- summary: further unread references worth reading, largest first
  evidence: `unparsed.csv`, `unread_attribute`. `PhysicalForeignKey@counterPartKeyRef`
    (100), `QueryPrivilegeMapping@databaseRef` (73),
    `RefPresentationHierarchy@presentationHierarchyRef` (58),
    `Join@physicalJoinRef` (38), `InitBlock@connectionPoolRef` (6).

## Deferred by Epic 2

**Prompts live where this epic does not look.** 991 of the fixture's 995 `saw:columnFilterPrompt` elements sit in `saw:view`
roots — 530 objects the epic lists as unmodelled — and only 4 are inside an Analysis. Story 2.6 AC #4 is therefore satisfied
in mechanism and nearly empty in content: `analysis_prompts.csv` holds 4 rows. Since `prompted` is the most common filter
operator in the whole fixture (1615 occurrences), the values those filters receive at runtime are defined almost entirely in
objects nobody has parsed. **Modelling `saw:view` is the single highest-value addition to catalog extraction**, and it is a
new object type, not a tweak. A test asserts the 4/530 split so the gap is stated rather than discovered.

**Visual Analyzer projects are Analyses by root element and a different thing by content.** Files named `_projectdefn` carry a
`saw:report` root, declare no `xmlVersion`, reference uploaded datasets as `XSA('prodney'.'Sample Pharma')` rather than a
Subject Area, and hold 42 formulas in `saw:paSimpleColumnFormula` hanging off `saw:propertyAddition`. Those 42 are reported as
`unread_element`, not captured. Capturing them means modelling VA project structure. **40 of the 67 distinct `subjectArea`
values in the fixture are XSA forms**, which also bears on FR-7: a resolver must not treat them as Subject Area names.

**`sawbsc:*` scorecards, `sawkpi:kpi`, `saw:action` and `saw:ibot`** remain unmodelled — 918 objects between them, enumerated
by parsing and reported per type. Each is a distinct object shape rather than a variation on the four this epic models.

**FR-7 is unchanged and still Epic 4.** `saw:criteria[@subjectArea]` is captured verbatim and resolved to nothing; there is
still no matched RPD-plus-catalog pair to verify a resolver against.

## Where lineage stops short of the real table — recorded 2026-08-21

**`lineage.csv` ends at the object OBIEE names, which is not always a table.** Two distinct gaps, and only one of them needs
anything from outside the repository.

**In the RPD already, and currently dropped.** `physical_tables.table_type` reports **21 of 100 tables as `select`** — they are
SQL statements, not tables. The SQL is present in the MDS XML, in `PhysicalTable/DBMapItem/Value`:

```xml
<PhysicalTable name="FactCrossJoin" type="select">
  <DBMapItem name="DefaultMulDB"><Value>select 1 Preserve from dual</Value></DBMapItem>
```

It is not captured. `unparsed.csv` reports `PhysicalTable Value#text` as `unread_text` at **44 occurrences** across the two
repositories, with `DBMapItem` and `DBMapItem@name` alongside it. **No database access is needed to fix this** — the text is in
the file. Until it is captured, a `select`-type table appears in `lineage.csv` as a physical endpoint whose definition the
Knowledge Base does not hold, and the tables it actually reads are invisible.

**Outside the RPD, and not fixable by reading files.** Of the 79 tables typed `none`, **the repository cannot say which are real
tables, which are database views, and which are synonyms** — OBIEE records a schema object name and does not care what it is.
So "ultimate physical table" in `lineage.csv` means *as far as OBIEE knows*, never *as far as the database knows*. Resolving a
view to its base tables, or reading a function or procedure body, requires the database.

**The answer to that is not credentials.** `what-we-need-to-ask-for.md` §2.3 and §2.4 already ask for **stored procedure and
function bodies, and source DDL or an information-schema dump** — explicitly **not query access**, because AD-11 says a skill
must never require it and NFR11 forbids opening an access path the Operator did not already have. §2 also refuses the OBIEE
connection-pool credentials by name, for the same reason. A DDL dump answers the question without becoming a new way into the
warehouse.

**Consequence for the As-Is document.** Epic 3 already states that physical detail excludes DDL and that external routine
bodies are unresolved. This entry records the sharper version: for 21 tables the gap is ours and cheap to close, and for the
rest it is the database's and needs an artefact nobody has asked for yet.
