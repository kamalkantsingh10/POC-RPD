# Estate Knowledge Base

The extractor's output: one CSV per table, plus `manifest.csv` recording what
this run was pointed at. These files are committed rather than regenerated so
the estate can be read without holding the corpus, and so changes to the
extractor show up as a reviewable diff.

Regenerate with:

    python3 -m tools.rpd_extract.cli --corpus <corpus>/clean --out estate/knowledge-base --clean

## What is in here

Three estates, keyed by the `rpd_id` column present on every table:

| `rpd_id`           | half    | rows   |
| ------------------ | ------- | ------ |
| `sampleapp-v607`   | catalog | 51,393 |
| `bi-analytics-2013`| rpd     |  7,904 |
| `sampleapp`        | rpd     |    820 |

The catalog tables come out EMPTY unless `<corpus>/clean` declares a catalog
half. A repository tree alone is layout 2, and layout 2 has no catalog — so
dashboards, analyses and saved filters are legitimately zero and the manifest
says why. The catalog fixture is a different SampleApp release from the
`sampleapp` RPD (0 of 1680 Subject Area names match), so it is declared as its
OWN estate rather than paired:

    <corpus>/clean/sampleapp-v607/catalog -> the catalog tree

Pairing it with `sampleapp/` would put a false provenance claim in
`manifest.csv`, which is exactly what AD-22 makes a human declaration in order
to prevent.

Exit code 3 is expected: 1583 references point into `/company_shared/`, a second
catalog root this fixture does not contain. See
`estate/test-corpus/catalog-xml-schema.md`.

## Provenance and content

Derived from UNLICENSED corpus repositories, pinned by commit in
`estate/test-corpus/corpus-manifest.csv`. The CSVs carry verbatim names and
formulas from those repositories, including the personal names that the
`bi-analytics-2013` author and colleagues used for their Subject Areas
(`Anton_Tserakhau`, `Iryna_Bradzetskaya`, `Uladzislau_Dodu`, `Vasili_Korzun`,
`Vera_Yakimovich`). Publishing them here is a deliberate decision taken with
that known; the underlying licensing question stays open — PRD §16 and §15
Open Question 15.

Secrets are not published. `variables.csv` carries `security_mask` and
`redacted` columns, and values the RPD marks sensitive are withheld — the one
such variable in this estate, `internal - do not ship - REP OLAP PASSWORD`, has
`redacted=true` and an empty `expr_text`.
