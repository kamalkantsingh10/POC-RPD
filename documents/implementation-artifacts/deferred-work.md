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

- summary: nine further references are read by nothing, led by the foreign key counterpart
  evidence: `unparsed.csv`, `assessment = target_not_in_kb`, 11 items / 278
    occurrences total. Largest: `PhysicalForeignKey@counterPartKeyRef` (100),
    `QueryPrivilegeMapping@databaseRef` (73),
    `RefPresentationHierarchy@presentationHierarchyRef` (58),
    `Join@physicalJoinRef` (38), `InitBlock@connectionPoolRef` (6).

- summary: files the walker never reaches are invisible to every report
  evidence: a constructed estate with `PhysicalTable/nested/buried.xml` and a
    file with no `.xml` extension extracted cleanly and reported neither. The
    unknown object type beside them WAS reported correctly, so the gap is
    specifically in file discovery, not in the audit. Did not occur on the
    pinned corpus (1383 of 1383 found), but an estate exported differently
    would hit it.
