# Sample Sales — the semantic model as it exists today

**What this is.** A plain-language description of the *Sample Sales* subject area in OBIEE: what business questions it answers, what each number means, how the pieces relate, and where the data comes from. It describes the existing system only. It proposes nothing for Power BI.

**Who it is for.** Anyone who needs to understand or confirm this model without opening the repository or the code — business owners, report authors, Data Engineering, and the people who will design the replacement.

**How to read it.** Everything in sections 1–8 was read from the OBIEE repository export and is stated as fact. Where the export does not answer something, the text says so and points to a numbered **open point** in section 9. Those are questions for you: each has an empty *Answer* line to fill in.

| | |
|---|---|
| Subject area | Sample Sales |
| Repository | `sampleapp` |
| Read from the repository export on | 18 November 2026 |
| Reports and dashboards | **Not examined** — see section 10 |

---

## 1. The model in one page

Sample Sales answers two kinds of question:

- **What did we sell?** Revenue, units and discounts from orders — by date, product, office and sales representative.
- **What did we plan to sell?** Revenue and unit targets — by date, product and office.

It is a classic star: two sets of numbers (*facts*) surrounded by four ways of slicing them (*dimensions*).

| Dimension | Slices **Revenue** (actuals) | Slices **Target** (plan) |
|---|:---:|:---:|
| Time | yes | yes |
| Products | yes | yes |
| Offices | yes | yes |
| Sales Rep | yes | **no** |

So actuals can be compared with targets by time, product and office, but **not by sales representative** — targets are not set at that level.

In numbers: 6 business tables, 49 fields that report authors can pick, 8 of them measures, 4 drill-down hierarchies, 12 database tables and one helper query behind it. (*Preferred Currency* is listed with the measures below but OBIEE does not flag it as one.)

Three behaviours are worth knowing before reading further, because each changes what a user sees:

1. **Revenue is stored four times**, at different levels of detail, and OBIEE picks one per question (section 5).
2. **Currency and language are personal.** One field shows revenue in the user's preferred currency; one shows product names in the user's language (section 6).
3. **Targets can be written back** by users with the right permission (section 7).

---

## 2. The measures

A measure is a number that gets added up (or otherwise summarised) as the user slices it.

### Actuals — table *Fact Revenue*

| Measure | What it is | How it is summarised | Comes from |
|---|---|---|---|
| **Revenue** | Order revenue | Sum | Database column `REVENUE`, in any of four revenue tables |
| **Units** | Units sold | Sum | Database column `UNITS`, in any of four revenue tables |
| **Discnt Value** | Discount amount | Sum | Database column `DISCNT_VALUE`, in two revenue tables |
| **All Products Revenue** | Revenue — *intended meaning not recorded* | Sum | Same column as Revenue |
| **All Months Revenue** | Revenue — *intended meaning not recorded* | Sum | Same column as Revenue |
| **Preferred Currency** | Revenue in the user's chosen currency | Picks one of three revenue measures | See section 6 |
| **Preserve** | A technical helper, always the value 1 | Maximum | A one-row helper query |

- *All Products Revenue* and *All Months Revenue* are, as far as the export shows, **identical to Revenue**. Their names suggest "revenue across all products" and "revenue across all months" — totals that stay fixed while the user drills — but the setting that would make them behave that way was not captured. **Open point 1.**
- *Preserve* is not a business number. **Open point 6.**

Three more revenue measures exist in the model but are **not offered to report authors** in this subject area. They matter because *Preferred Currency* uses two of them:

| Hidden measure | How it is calculated |
|---|---|
| Revenue (EUR) | Revenue × 0.76 |
| Revenue (GBP) | Revenue × 0.62 |
| Revenue (INR) | Revenue × 54.68 |

The exchange rates are fixed numbers written into the model. They are not looked up from a rates table. **Open point 2.**

### Plan — table *Fact Target*

| Measure | What it is | How it is summarised | Comes from |
|---|---|---|---|
| **Revenue** | Target revenue | Sum | `SAMP_TARGETS_F.REVENUE` |
| **Units** | Target units | Sum | `SAMP_TARGETS_F.UNITS` |

Both are marked **writeable**: OBIEE allows users to type new values in (section 7). Target Revenue is also the model's *default measure* — the number OBIEE uses when a user builds a query from dimensions only and has not chosen a measure.

### What is *not* here

- No measure has a special rule for a particular dimension (for example "sum by product but take the last value over time"). Every measure is summarised the same way in every direction.
- No built-in time comparisons — no "year ago", "year to date" or "rolling" measures. If reports show those, they are calculated inside the reports. **Open point 12.**

---

## 3. The dimensions

Each dimension is listed with the fields a report author can pick and its **drill path** — the order in which a user drills from the total down to the detail.

### Time

| Field | Meaning | Type |
|---|---|---|
| Per Name Year | Year | text, 4 characters |
| Per Name Half | Half-year | text |
| Per Name Qtr | Quarter | text |
| Per Name Month | Month | text |
| Per Name Week | Week | text |
| Calendar Date | The day | date |

**Drill path:** Total → Year → Half Year → Quarter → Month → Week → Day.

- Week sits *below* Month in this path. Weeks normally straddle month ends, so this needs confirming. **Open point 14.**
- The names users actually see for this table and its six fields are not fixed text. They are fetched per user, which is how OBIEE shows them in the user's language (section 6).

### Products

| Field | Meaning |
|---|---|
| Brand, Brand Key | Brand and its identifier |
| Lob, Lob Key | Line of business and its identifier |
| Type, Type Key | Product type and its identifier |
| Prod Dsc, Prod Key | Product name and its identifier |
| Prod Dsc (Translated) | Product name in the user's language (section 6) |

**Drill path:** Total → Brand → Line of Business → Product Type → Product.

### Offices

| Field | Meaning |
|---|---|
| Company, Company Key | Company and its identifier |
| Organization, Org Key | Organisation and its identifier |
| Department, Dept Key | Department and its identifier |
| Office Dsc, Office Key | Office name and its identifier |
| Area Name | Area — **not part of the drill path** |

**Drill path:** Total → Company → Organization → Department → Office.

### Sales Rep

| Field | Meaning |
|---|---|
| Employee ID | The employee |
| Employee Name | Their name |
| Manager ID | Their manager |
| Office ID | Their office |
| Distance | How many reporting levels separate two employees |

**Drill path:** this is a **reporting-line hierarchy** — manager, then their reports, then *their* reports, to whatever depth the organisation has. It is not a fixed set of levels. It is shown by Employee Name.

This kind of hierarchy relies on a helper table that lists every manager-and-subordinate pair with the distance between them. How that helper is wired to the employee table was not captured. **Open point 7.**

### Fields that sit on the fact tables

*Fact Revenue* also offers order details: **Order Number, Order Status, Order Type, Order Day Dt** (date and time of the order), **Bill Day Dt** (billing date), and the keys **Bill Mth Key, Prod Key, Office Key**. *Fact Target* offers the keys **Bill Mth Key, Prod Key, Office Key**.

---

## 4. How the tables relate

Seven relationships, all between a fact and a dimension. The two fact tables are not related to each other directly; they are compared through the dimensions they share.

| Fact | Dimension | Kind |
|---|---|---|
| Revenue | Time | Many revenue rows per date |
| Revenue | Products | Many revenue rows per product |
| Revenue | Offices | Many revenue rows per office |
| Revenue | Sales Rep | Many revenue rows per employee |
| Target | Time | Many target rows per date |
| Target | Products | Many target rows per product |
| Target | Offices | Many target rows per office |

**All seven are *inner* relationships.** In practice: a revenue row whose product, office, date or employee is missing from the dimension **drops out of the result** rather than appearing under "unknown". Whether such rows exist is a data question. **Open point 15.**

The relationships above are the model's own, and they are complete. The matching database-level links (which column joins to which) were only partly captured. **Open point 7.**

---

## 5. Where the data comes from

Everything is read from one database schema, `SAMPLESALES`.

### Revenue is stored four times

| Database table | Level of detail | Holds |
|---|---|---|
| `SAMP_REVENUE_F` | One row per order line — by day, product, office and sales rep | Everything: revenue, units, discount, order details |
| `SAMP_REVENUE_A` | Summarised by **month and product** | Revenue, units, discount |
| `SAMP_REVENUE_A_MTH` | Summarised by **month** | Revenue, units |
| `SAMP_REVENUE_A_YR` | Summarised by **year** | Revenue, units |

The three summary tables exist for speed. OBIEE generally answers from the most summarised table that can satisfy the question, and falls back to the detailed table when the user asks for something only it holds (a single order, an office, a sales rep). One of the four — the month-and-product table — is explicitly marked as preferred; the others carry no preference. **Open point 9.**

**This matters for the migration:** the same number can come from four places. They only agree if the summary tables are kept in step with the detail table, and the export says nothing about how they are loaded. **Open point 13.**

It also explains one oddity already visible in the model — see the currency note in section 6.

### The other tables

| Database table | Feeds | Notes |
|---|---|---|
| `SAMP_TARGETS_F` | Target revenue and units | Recorded as day / office / product detail, yet its only date key is a **month** key. **Open point 8** |
| `SAMP_TIME_DAY_D` | Time, one row per day | Holds all six time fields |
| `SAMP_TIME_MTH_D` | Time, one row per month | Has no date or week — used with the monthly summaries |
| `SAMP_PRODUCTS_D` | Products | |
| `SAMP_PRODUCTS_D_TRANSLATION` | Translated product names | One row per product per language |
| `SAMP_OFFICES_D` | Offices | |
| `EMPLOYEE` | Sales Rep | |
| `EMP_PARENT_CHILD` | Sales Rep reporting line | The helper table described in section 3 |
| *FactCrossJoin* | The *Preserve* helper | **Not a table** — a one-line query defined inside OBIEE: `select 1 Preserve from dual` |

No table is filtered: OBIEE reads every row of each. No table is split into slices by date or region.

None of these tables is an alias of another. Where the repository records a table's name in the database, it is the same as the name OBIEE shows.

---

## 6. Behaviour that depends on who is logged in

### Preferred currency

The field **Preferred Currency** shows revenue in a currency chosen per user. A per-user setting holds a code, and the field picks a measure accordingly:

| Setting | Field shows |
|---|---|
| `gc1` (the default) | Revenue |
| `gc2` | Revenue (EUR) = Revenue × 0.76 |
| `gc3` | Revenue (GBP) = Revenue × 0.62 |

Things the export does not settle:

- **What currency plain Revenue is in.** The model does not say. **Open point 2.**
- **INR is defined but cannot be selected.** A rupee measure exists (× 54.68) but no setting leads to it. **Open point 2.**
- **Conversion is applied only on the detailed table.** When OBIEE answers from the month-and-product summary table, Revenue (EUR), (GBP) and (INR) are read straight from the revenue column **with no exchange rate applied**. So the same "Revenue in euros" figure could come back converted or unconverted depending on how detailed the question is. This is either a defect in the model or the summary table is expected to be used differently. **Open point 3.**
- **How a user's currency gets set.** At login OBIEE runs a small query to set it, and that query refers to a setting spelled `PREFERED_CURRENCY` (one R) while the setting itself is `PREFERRED_CURRENCY` (two). **Open point 4.**

### Language

- **Prod Dsc (Translated)** looks up the product's name in the translation table for the user's language. The lookup is given the ordinary product name as its fallback, which under OBIEE's rules for this kind of lookup is what a user sees where no translation exists.
- **The Time table and its six field names** are shown under names fetched per user at login. The model has a login step that reads a `TRANSLATIONS` table for the user's language, which is the likely source — but the link between that step and these seven names was not captured. **Open point 5.**

---

## 7. Security and write-back

**Row-level security: none.** No rule in the repository restricts which rows a user sees in this subject area. Every user who can open it sees all offices, products and sales reps. **Open point 11** asks you to confirm that is intended.

**Permissions on targets.** Target Revenue and Target Units carry explicit read and write permissions — the only fields in this subject area recorded with their own. (The repository holds two further grants whose target was not captured.) The export records *that* the grants exist but identifies who holds them only by an internal code, not by a role name. **Open point 10.**

---

## 8. What was confirmed, at a glance

| Area | Status |
|---|---|
| Tables, fields and their database columns | Complete |
| How each measure is summarised | Complete |
| Drill paths | Complete for Time, Products, Offices; Sales Rep partly (open point 7) |
| Relationships between business tables | Complete |
| Which database table serves which level of detail | Complete |
| Currency and language behaviour | Understood, with four open points |
| Row-level security | Confirmed absent |
| Who may read and write targets | **Open** |
| Fixed-level measures (*All Products*, *All Months*) | **Open** |
| Database keys and column-to-column joins | **Open** |
| Reports and dashboards built on this model | **Not examined** |

---

## 9. Open points

These are the questions the repository export cannot answer. Please write the answer under each one; the document will be updated from them.

**1. What are *All Products Revenue* and *All Months Revenue* meant to show?**
As recorded they equal Revenue. Are they pinned totals — revenue for all products regardless of the product the user drills into, and likewise for months — typically used to calculate "share of total"?
*Who can answer:* the OBIEE developer, or anyone who uses these in a report.
*Answer:*

**2. Currency basics.** (a) What currency is plain Revenue in? (b) Are the fixed rates 0.76, 0.62 and 54.68 still what the business wants, or should the new model use real exchange rates? (c) Rupees are defined but cannot be chosen — is that deliberate?
*Who can answer:* finance, and the business owner of these reports.
*Answer:*

**3. Should converted revenue differ between the detailed and the summarised table?**
Euro, sterling and rupee revenue apply an exchange rate when read from order detail, and apply none when read from the month-and-product summary. Is the summary table already converted, is this a known defect, or does nobody use these measures at summary level?
*Who can answer:* the OBIEE developer; Data Engineering for what the summary table holds.
*Answer:*

**4. How does a user's preferred currency get set?**
The default is `gc1`. Is there a screen, a profile setting or a table where users choose, and does the one-R spelling in the login query matter?
*Who can answer:* the OBIEE administrator.
*Answer:*

**5. Where do the per-user names for the Time fields come from?**
Is it the `TRANSLATIONS` table, and which languages are in use? The same question applies to translated product names: which languages have translations?
*Who can answer:* the OBIEE administrator.
*Answer:*

**6. What is *Preserve* for?**
A helper that always returns 1, connected to offices, products and employees with no join condition. The usual purpose is to keep every office, product or employee in a report even when it has no sales. Is it used that way, and do any reports depend on it?
*Who can answer:* the OBIEE developer; report authors.
*Answer:*

**7. How are the database tables joined, column to column?**
Thirteen database-level links are recorded, but not which column each one points to. In particular: how revenue links to the employee table (the detail table has an `EMPLOYEE_KEY`), and how the employee table links to its reporting-line helper.
*Who can answer:* Data Engineering or the database administrator — the table definitions will settle it.
*Answer:*

**8. Are targets set by day or by month?**
The model treats the target table as daily, but its only date key is a month key.
*Who can answer:* whoever loads or maintains targets.
*Answer:*

**9. Which revenue table should answer which question?**
Only one of the four is marked as preferred. Is the choice otherwise left to OBIEE, and has anyone seen totals differ depending on how a report is built?
*Who can answer:* the OBIEE developer.
*Answer:*

**10. Who may see and who may change targets?**
Is write-back on targets actually used? By which group of users?
*Who can answer:* the OBIEE administrator; the planning team.
*Answer:*

**11. Is it correct that every user sees all the data?**
No row-level restriction exists in the repository for this subject area. Restrictions may exist elsewhere — in the database, or on the reports themselves.
*Who can answer:* the business owner; the security administrator.
*Answer:*

**12. Which reports and dashboards use this subject area, and do they add their own calculations?**
Reports were not examined (section 10). Year-on-year comparisons, percentages and rankings are typically defined inside reports and would be invisible here.
*Who can answer:* report authors; the OBIEE administrator, who can export the report catalog.
*Answer:*

**13. How are the three revenue summary tables loaded, and how often?**
They must agree with the detail table for the same number to come back whichever one is used.
*Who can answer:* Data Engineering.
*Answer:*

**14. Do weeks really sit inside months?**
The time drill path goes Month → Week → Day. How are weeks that span two months handled?
*Who can answer:* whoever maintains the calendar table.
*Answer:*

**15. Can a revenue or target row have a missing product, office, date or employee?**
If so it is silently left out of every report today, and the new model would need to decide whether to keep doing that.
*Who can answer:* Data Engineering — a data check will settle it.
*Answer:*

---

## 10. What this document did not look at

- **Reports and dashboards.** Only the repository was available for this estate, not its report catalog. Any calculation, filter or prompt defined inside a report is missing from this picture.
- **The database itself.** No table definitions, keys, indexes, row counts or load processes. Field types above are what OBIEE believes the columns to be.
- **Data.** No values were read. Nothing here confirms that the numbers are correct, only how they are defined.
- **Other subject areas.** The same repository contains two more (*Population* and *Densification – US Crime By State*); they are separate models and not covered.

---

## Appendix A — Formulas exactly as OBIEE stores them

For anyone who needs the precise text. Nothing in the main document depends on reading this.

**Summarising rule** (Revenue; the others differ only in the name, and *Preserve* uses `MAX`):

```
 SUM("SAMPLESALES"."Fact Revenue"."Revenue")
```

**Preferred Currency:**

```
 INDEXCOL( CASE  VALUEOF(NQ_SESSION."PREFERRED_CURRENCY") WHEN 'gc1' THEN 0 WHEN 'gc2' THEN 1 WHEN 'gc3' THEN 2 END , "SAMPLESALES"."Fact Revenue"."Revenue", "SAMPLESALES"."Fact Revenue"."Revenue (EUR)", "SAMPLESALES"."Fact Revenue"."Revenue (GBP)")
```

**Currency conversions, from the detail table:**

```
"xe".""."SAMPLESALES"."SAMP_REVENUE_F"."REVENUE" * 0.76      (EUR)
"xe".""."SAMPLESALES"."SAMP_REVENUE_F"."REVENUE" * 0.62      (GBP)
"xe".""."SAMPLESALES"."SAMP_REVENUE_F"."REVENUE" * 54.68     (INR)
```

**The same three, from the month-and-product summary table** — no rate:

```
"xe".""."SAMPLESALES"."SAMP_REVENUE_A"."REVENUE"
```

**Prod Dsc (Translated):**

```
Lookup(SPARSE   "SAMPLESALES"."Dim Products (Translated)"."PROD_DESC" ,  "SAMPLESALES"."Dim Products"."Prod Dsc"  , "SAMPLESALES"."Dim Products"."Prod Key", VALUEOF(NQ_SESSION.WEBLANGUAGE) ) 
```

**Login queries:**

```
select 'VALUEOF(NQ_SESSION.PREFERED_CURRENCY)' from dual
select MSG_NUM, MSG_TEXT from TRANSLATIONS where MSG_LANG_ID = 'VALUEOF(NQ_SESSION.WEBLANGUAGE)'
```

**The Preserve helper**, and its three joins (each with the condition `1=1`, to offices, products and employees):

```
select 1 Preserve from dual
```

## Appendix B — Field-to-column map

| Business field | Database column | Type |
|---|---|---|
| Time · Calendar Date | `SAMP_TIME_DAY_D.CALENDAR_DATE` | date |
| Time · Per Name Week | `SAMP_TIME_DAY_D.PER_NAME_WEEK` | text (12) |
| Time · Per Name Month / Qtr / Half / Year | `SAMP_TIME_DAY_D` and `SAMP_TIME_MTH_D`, columns `PER_NAME_MONTH`, `_QTR`, `_HALF`, `_YEAR` | text (9 / 7 / 8 / 4) |
| Products · Brand, Lob, Type, Prod Dsc | `SAMP_PRODUCTS_D.BRAND`, `.LOB`, `.TYPE`, `.PROD_DSC` | text (8 / 13 / 12 / 26) |
| Products · Brand Key, Lob Key, Type Key, Prod Key | `SAMP_PRODUCTS_D.BRAND_KEY`, `.LOB_KEY`, `.TYPE_KEY`, `.PROD_KEY` | number |
| Products · translation lookup | `SAMP_PRODUCTS_D_TRANSLATION.PROD_KEY`, `.LANG_ID`, `.PROD_DESC` | number, text (2), text (50) |
| Offices · Company, Organization, Department, Office Dsc, Area Name | `SAMP_OFFICES_D.COMPANY`, `.ORGANIZATION`, `.DEPARTMENT`, `.OFFICE_DSC`, `.AREA_NAME` | text (14 / 18 / 25 / 17 / 25) |
| Offices · Company Key, Org Key, Dept Key, Office Key | `SAMP_OFFICES_D.COMPANY_KEY`, `.ORG_KEY`, `.DEPT_KEY`, `.OFFICE_KEY` | number |
| Sales Rep · Employee ID, Manager ID, Office ID | `EMPLOYEE.EMP_ID`, `.MANAGER_ID`, `.OFFICE_ID` | number |
| Sales Rep · Employee Name | `EMPLOYEE.EMP_NAME` | text (40) |
| Sales Rep · Distance | `EMP_PARENT_CHILD.DISTANCE` | whole number |
| Revenue · Revenue, Units | `REVENUE`, `UNITS` in `SAMP_REVENUE_F`, `SAMP_REVENUE_A`, `SAMP_REVENUE_A_MTH`, `SAMP_REVENUE_A_YR` | number |
| Revenue · Discnt Value | `DISCNT_VALUE` in `SAMP_REVENUE_F`, `SAMP_REVENUE_A` | number |
| Revenue · Order Number, Order Status, Order Type | `SAMP_REVENUE_F.ORDER_NUMBER`, `.ORDER_STATUS`, `.ORDER_TYPE` | number, text (11), text (8) |
| Revenue · Order Day Dt, Bill Day Dt | `SAMP_REVENUE_F.ORDER_DAY_DT`, `.BILL_DAY_DT` | date-time, date |
| Revenue · Bill Mth Key, Prod Key | `BILL_MTH_KEY`, `PROD_KEY` in `SAMP_REVENUE_F`, `SAMP_REVENUE_A` | number |
| Revenue · Office Key | `SAMP_REVENUE_F.OFFICE_KEY` | number |
| Target · Revenue, Units, Bill Mth Key, Prod Key, Office Key | `SAMP_TARGETS_F.REVENUE`, `.UNITS`, `.BILL_MTH_KEY`, `.PROD_KEY`, `.OFFICE_KEY` | number |

## Appendix C — Where this came from, and how to check a statement

Every statement was derived from the extracted repository tables in `estate/knowledge-base` (repository `sampleapp`, extracted 2026-11-18T09:32:58Z, extractor 0.2.0). The subject-area extract is in the CSV files beside this document. To challenge a statement, name it; it can be traced to the rows below and re-derived on its own.

| Section | Tables used | Rows are identified by |
|---|---|---|
| 2 Measures | `logical_columns`, `aggregation_rules`, `lts_column_map` | `sampleapp::bmm::SAMPLESALES.Fact Revenue.<measure>`, `…Fact Target.<measure>` |
| 3 Dimensions | `presentation_columns`, `logical_columns` | `sampleapp::pres::Sample Sales.<table>.<field>` |
| 3 Drill paths | `logical_dimensions`, `logical_levels`, `presentation_hierarchies` † | `sampleapp::bmm::SAMPLESALES.<hierarchy>.<level>` |
| 4 Relationships | `bmm_joins` | `sampleapp::bmm::joins.Relationship_2004:…` |
| 5 Data sources | `logical_table_sources`, `lineage`, `physical_tables`, `physical_table_definitions` † | `sampleapp::bmm::SAMPLESALES.<table>.src.<source>`, `sampleapp::phys::xe.SAMPLESALES.<table>` |
| 6 Currency, language | `logical_columns` and `lts_column_map` for `Revenue (EUR/GBP/INR)` and `Dim Products (Translated)` †, `variables`, `init_blocks` | `sampleapp::var::PREFERRED_CURRENCY`, `sampleapp::var::init.…` |
| 7 Security | `security_rls` † | `sampleapp::sec::obj.ObjPriv_1500:…` |

† Read from the full Knowledge Base, because the subject-area extract does not yet include these rows.

## Appendix D — Notes for the tool team

Not for business readers. These are why some open points exist, and fixing them would close points without asking anyone.

| Gap | Effect | Open point |
|---|---|---|
| The level a measure is pinned to is not extracted (`Dimension` → level → column references are unread) | Level-based measures look like ordinary ones | 1 |
| The far side of a database foreign key is not extracted (`counterPartKeyRef`), nor are primary keys | Column-to-column joins unknown | 7 |
| Joins inside a logical table source are not extracted (`Join`, `Link`) | Multi-table sources cannot be described | 7 |
| A reference from a formula to a logical *table* or to a session variable does not resolve | Two formulas reported as errors although both targets exist | — |
| Privilege grants name the grantee by an internal code | Roles cannot be named | 10 |
| The subject-area extract omits hierarchies, table definitions, columns referenced only from formulas, and object privileges | This document had to read the full Knowledge Base for them | — |
| The subject-area extract matches variables by name across repositories | A `bi-analytics-2013` variable appears in this extract; it was ignored here | — |
