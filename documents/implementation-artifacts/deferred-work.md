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
