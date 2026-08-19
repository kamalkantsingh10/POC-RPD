# MDS XML — Observed Schema

**What this covers:** the element and attribute shapes actually present in the corpus, per object type.
**Who it is for:** whoever writes or reviews the `mds_xml` inbound adapter (Stories 1.4–1.7, 1.10).

Derived by parsing all 1383 corpus XML files with `ElementTree` and counting element paths and attributes. **Observed, not documented** — Oracle publishes no schema for this format, so anything absent here is absent from the corpus, not necessarily from OBIEE. Under AD-3 an unrecognised construct is recorded in `unparsed.csv`, never guessed.

Namespace on every object: `http://www.oracle.com/obis/repository`.
Cross-references take the form `<path>.xml#<mdsid>`, where the `mdsid` is the target's own `mdsid` attribute prefixed `m`.

## Physical layer

**`PhysicalTable`** — `@mdsid @name @type @maxConn @containerRef`
- `PhysicalColumn` ×1096 — `@mdsid @name @dataType @specialType @precision @nullable @extName @sourceColumnRef`
- `PhysicalKey/RefColumns/RefColumn@columnRef`
- `PhysicalForeignKey/RefColumns/RefColumn@columnRef`
- `DBMapItem/Value`

**`Database`** — `@mdsid @name @type @persistConnectionPoolRef @dbFlag`
- `Feature@name @value` ×2739 — database capability flags
- `RefConnectionPools/RefConnectionPool@connectionPoolRef`

**`Schema`**, **`ConnectionPool`** — containers referenced by `@containerRef`.

**`ComplexJoin`** (physical) — `@mdsid @name @cardinality @table1Ref @table2Ref`, plus `Expr` carrying the join condition.

## Business Model & Mapping

**`LogicalTable`** — `@mdsid @name @subjectAreaRef`
- `LogicalColumn` ×1010 — `@mdsid @name @isWriteable`
  - `AttrDefn/Expr` ×933 — the column's physical mapping
  - `Expr` ×15 — **a derived column's own formula. FR-2's primary target.**
  - `MeasureDefn` ×35 — present when the column is a measure; `AggrRule` lives here
- `RefTableSources/RefLogicalTableSource@logicalTableSourceRef` ×92
- `LogicalKey/RefColumns/RefLogicalColumn`

**`LogicalTableSource`** — `@mdsid @name @isActive @logicalTableRef`
- `ColumnMapping` ×1035, each holding **both** `LogicalColumnExpr` (logical side) and `Expr` (physical side)
- `FragmentContent` ×92 — present on every source; **0 populated in this corpus**
- `GroupBy` ×92 — 21 populated
- `WhereClause` — content filter; **6 populated**
- `Link@startNodeTableRef` ×111 — the physical join path the source traverses

**`LogicalComplexJoin`** — `@mdsid @name @type @logicalTable1Ref @multiplicity1 @isAggregate1 @logicalTable2Ref @multiplicity2 @isAggregate2`
`@type` is the **join type** FR-4 requires; `@multiplicity1/2` give cardinality.

**`Dimension`** — hierarchies
- `LogicalLevel` ×106 — `@name @isGTA @isFDUC @memberCount @levelConst`
- `LogicalLevel/LogicalKey` — `@isPrimary @isForDrillDown @isChronKey` — **`@isChronKey` marks the chronological key, which time-series functions depend on**
- `RefChildLevels/RefLogicalLevel`, `RefPreferredDrillDown`

## Presentation layer

**`PresentationCatalog`** (a Subject Area) — `@mdsid @name @subjectAreaRef @isAutoAggr @isDefaultReadable @defaultFactColumnRef`
**`@defaultFactColumnRef` is the implicit fact column** required by FR-4. Present on 1 of 21 catalogs.
- `RefTables/RefPresentationTable@presentationTableRef` ×128
- `Alias` — former names, which matter for stability across renames

**`PresentationTable`** — `@mdsid @name @containerRef @hasDispName @dispName`
- `PresentationColumn` ×1543 — `@mdsid @name @logicalColumnRef @overrideLogicalName @hasDispName @dispName`
**`@overrideLogicalName` plus `@logicalColumnRef` is the rename chain** FR-4 requires.

**`PresentationHierarchy`** — `@logicalDimensionRef`; `PresentationLevel@logicalLevelRef` ×246.

## Variables and initialisation

**`Variable`** — `@mdsid @name @initBlockRef @isSessionVar @securityMask`, plus `Expr` holding the default. 345 total, 103 session variables.

**`InitBlock`** — `@mdsid @name @refreshPeriod @isSessionVar @isRowWiseCacheEnabled @isRowWiseInit @isEnabled @connectionPoolRef @baseTime`
- `InitString` — the SQL executed
- `RefVariables/RefVariable`, `RefPredecessors/RefInitBlock` (execution ordering)

## Security

Roles resolve through a chain, not a single object:

```
Group (@guid @displayName)            application role
  ← PrivilegePackage (@roleRef, @userRef)
      ├── ObjectPrivilege (@type @privilegePackageRef) → RefObjects/RefObject
      └── QueryPrivilegeMapping (@databaseRef @queryPrivilegeRef)
            → QueryPrivilege (@maxExecTime @maxRows @execPhysicalPrivilege)
```

Row-level security predicates appear as `WhereClause` on a `LogicalTableSource`, typically referencing a session variable — e.g. `Position(';Role_DW_Admin;' in ';' || valueof(NQ_SESSION.ROLEGUIDS) || ';') > 0`.

## Expressions — all three forms (AD-21)

Every expression container holds the same trio:

| Field | Example | Nature |
|---|---|---|
| `ExprText` | `SUM("%1")` | template with positional placeholders |
| `ExprTextDesc` | `SUM("Anton_Tserakhau"."Operations..."."FCT_UNIT_AMOUNT")` | rendered with names resolved — **derived, not authoritative** |
| `ObjectRefList/RefObject` | `@objectRef @objectTypeId @refId` | what the placeholders bind to |

All three are captured verbatim per AD-21. Containers observed: `LogicalColumn/Expr`, `AttrDefn/Expr`, `MeasureDefn/AggrRule/Expr`, `ColumnMapping/{LogicalColumnExpr,Expr}`, `LogicalTableSource/{WhereClause,GroupBy,FragmentContent}`, `Variable/Expr`, `ComplexJoin/Expr`.

## Absent or thin in this corpus

| Construct | Observation |
|---|---|
| LTS priority order | No priority attribute on `LogicalTableSource`. 1 stray `priorityGroup` in the SampleApp source |
| Fragmentation predicate | `FragmentContent` on all 92 sources, **0 populated** |
| Implicit fact column | `@defaultFactColumnRef` on **1 of 21** catalogs |
| `AGO` | 1 file |
| `PERIODROLLING` | 0 |

Under AD-19 these are unimplemented until a fixture exists, which is what Story 1.9's Constructed Cases must supply.
