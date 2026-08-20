"""The semantic model of one Subject Area, written out in full."""
import csv, sys
from pathlib import Path

kb = Path(sys.argv[1]); name = sys.argv[2]
L = lambda f: list(csv.DictReader(open(kb/f, newline='', encoding='utf-8')))

sa   = [r for r in L("presentation_subject_areas.csv") if r['name'] == name][0]
pt   = [r for r in L("presentation_tables.csv") if r['subject_area_id'] == sa['row_id']]
ptid = {r['row_id'] for r in pt}
pc   = [r for r in L("presentation_columns.csv") if r['table_id'] in ptid]
lc   = {r['row_id']: r for r in L("logical_columns.csv")}
lt   = {r['row_id']: r for r in L("logical_tables.csv")}
lts  = {r['row_id']: r for r in L("logical_table_sources.csv")}
agg  = [r for r in L("aggregation_rules.csv")]
lin  = [r for r in L("lineage.csv")]
bmm  = L("bmm_joins.csv")
pcol = {r['row_id']: r for r in L("physical_columns.csv")}
var  = {r['name']: r for r in L("variables.csv")}
sec  = [r for r in L("security_rls.csv") if r['kind'] == 'row_filter']

ltid  = {lc[c['logical_column_id']]['table_id'] for c in pc if c['logical_column_id'] in lc}
byLC  = {}
for r in lin: byLC.setdefault(r['logical_column_id'], []).append(r)
byAgg = {}
for a in agg: byAgg.setdefault(a['logical_column_id'], []).append(a)

o = print
o(f"# Semantic Model — {name}\n")
o(f"Business model `{sa['business_model']}` · {len(pt)} tables · {len(pc)} columns\n")
o("Formulas are OBIEE's own text, character for character. `%1`, `%2` are its")
o("placeholders; where a column has no physical source of its own the resolved")
o("form is given beneath, also OBIEE's own rendering.\n")

o("## Tables and columns\n")
for t in sorted(pt, key=lambda x: x['name']):
    cols = [c for c in pc if c['table_id'] == t['row_id']]
    o(f"\n### {t['name']}  ({len(cols)} columns)\n")
    o("| Column | Type | Kind | OBIEE logic | Physical source |")
    o("|---|---|---|---|---|")
    for c in sorted(cols, key=lambda x: x['name']):
        l = lc.get(c['logical_column_id'])
        if not l:
            o(f"| {c['name']} | — | *unresolved* | — | — |"); continue
        paths = byLC.get(l['row_id'], [])
        types = sorted({pcol.get(p['physical_column_id'],{}).get('data_type','') for p in paths}) or ['']
        rules = byAgg.get(l['row_id'], [])
        kind  = "**measure**" if l['is_measure']=='true' else "attribute"
        logic = (l['derived_expr_text'] or l['mapping_expr_text'] or '').strip()
        if rules: logic = " · ".join(f"`{a['expr_text'].strip()}`"
                     + ("" if a['is_default']=='true' else " *(override)*") for a in rules)
        elif logic: logic = f"`{logic}`"
        # A derived column has no physical column of its own, so there is no
        # lineage line to name its %1 / %2. Show OBIEE's own resolved rendering
        # instead — otherwise the formula is unreadable.
        resolved = (l['derived_expr_text_desc'] or '').strip()
        if resolved and not paths:
            logic += f"<br>= `{' '.join(resolved.split())}`"
        src = sorted({".".join(p['physical_table_id'].split('::')[-1].split('.')[-2:])
                      + "." + p['physical_column_id'].split('.')[-1] for p in paths})
        rename = f" *(logical: {l['name']})*" if l['name'] != c['name'] else ""
        o(f"| {c['name']}{rename} | {types[0]} | {kind} | {logic or '—'} | {'<br>'.join(src) or '—'} |")

o("\n## How each table is loaded\n")
o("| Logical table | Source | Priority | Content filter |")
o("|---|---|---|---|")
for tid in sorted(ltid):
    for s in sorted((x for x in lts.values() if x['logical_table_id']==tid), key=lambda x: x['name']):
        w = " ".join(s['where_text'].split())[:70]
        o(f"| {lt.get(tid,{}).get('name','?')} | {s['name']} | {s['priority'] or '—'} | {w or '—'} |")

o("\n## Relationships\n")
o("| From | To | Join type | Multiplicity |")
o("|---|---|---|---|")
rel = [j for j in bmm if j['table1_id'] in ltid and j['table2_id'] in ltid]
for j in rel:
    o(f"| {lt.get(j['table1_id'],{}).get('name','?')} | {lt.get(j['table2_id'],{}).get('name','?')} "
      f"| {j['join_type']} | {j['multiplicity1']} : {j['multiplicity2']} |")

o("\n## Row-level security\n")
mine = [r for r in sec if r['subject_id'] in ltid]
if mine:
    for r in mine:
        o(f"\n**{lt.get(r['subject_id'],{}).get('name','?')}** — role `{r['role'] or 'not recorded'}`\n")
        o("```")
        o(r['expr_text'].strip())
        o("```")
else:
    o("*None.*")

o("\n## Variables referenced\n")
used = set()
blob = " ".join((r.get('expr_text','') or '') for r in mine) + " ".join(
    (lc[c['logical_column_id']]['derived_expr_text'] if c['logical_column_id'] in lc else '') for c in pc)
for v in var:
    if v in blob: used.add(v)
if used:
    o("| Variable | Session? | Init block |")
    o("|---|---|---|")
    for v in sorted(used):
        o(f"| {v} | {var[v]['is_session']} | {var[v]['init_block_id'].split('.')[-1] or '—'} |")
else:
    o("*None referenced by this Subject Area's logic.*")

o("\n---\n")
o("**Not in this document:** hierarchies and drill paths. `PresentationHierarchy` and")
o("`Dimension` exist in the source repository but the extractor does not yet model them.")
