# Processed inputs — what the extractor actually read

**Writer: Operator.** Like `estate/test-corpus/`, this directory has one writer (AD-18).

This is the answer to *"what did you run it against?"*, in two parts: a complete manifest of every input file, and a small sample of real ones so the shapes are visible without an OBIEE licence.

## `inputs-manifest.csv` — all 6754 files, no content

One row per file the extractor read, across three estates:

| Estate | Half | Files |
|---|---|---:|
| `sampleapp-v607` | catalog | 5371 |
| `bi-analytics-2013` | rpd | 1249 |
| `sampleapp` | rpd | 134 |

Columns: `path`, `estate`, `half`, `bytes`, `root_element`, `classification`.

`root_element` comes from **parsing every file**, not from its extension — catalog objects are extensionless, so the only way to know what one is is to open it. `classification` uses each adapter's own rule:

| Classification | Catalog | RPD |
|---|---:|---:|
| `modelled` | 2850 | 1139 |
| `unmodelled_object` | 1491 | 200 |
| `not_a_catalog_object` | 1030 | — |
| `index_only` | — | 44 |

**The catalog figures reconcile exactly with `coverage_summary.csv`** — 2850 / 1491 / 1030 — and this manifest was built by a separate script from a separate walk of the tree. Two independent counts agreeing is the point; a manifest derived from the extractor's own output could only ever agree with itself.

## `samples/` — 26 real files, 36 KB

One file per object type, the **smallest** of its kind so the directory stays a sample rather than a second corpus. Every type either adapter handles is represented, plus the largest unmodelled populations and one genuine non-catalog file. `samples/SAMPLES.csv` maps each to its type and to how many of that type exist in the full corpus.

These are **real corpus files**, which is the whole point of including them — the constructed fixtures in `estate/test-corpus/constructed-cases/` show what we *think* the format is, and these show what it actually is.

## ⚠️ Licensing

The full corpora are **not** in this repository and are excluded deliberately — see `estate/knowledge-base/.gitignore` and `estate/test-corpus/sample-data/.gitignore`, and PRD §16. They are 522 MB of Oracle SampleApp and BI-Analytics content whose licence for redistribution is an open question.

**The 26 files under `samples/` are an exception made knowingly**, on the judgement that a token excerpt sized to document a format is defensible where republishing the estate is not. If that judgement is wrong, `samples/` is the only thing here that has to go — `inputs-manifest.csv` contains no file content at all, only paths, sizes and element names.

## Reproducing

```sh
python3 -m tools.rpd_extract.cli \
  --corpus <corpus>/clean \
  --out estate/knowledge-base --clean
```

`<corpus>/clean` must declare the halves; see `estate/knowledge-base/.gitignore` for the layout, and `README.md` for the accepted shapes. The catalog half is declared as its own estate because it is a different SampleApp release from the `sampleapp` repository — 0 of 1680 Subject Area names match — and pairing them would put a false provenance claim in `manifest.csv` (AD-22).
