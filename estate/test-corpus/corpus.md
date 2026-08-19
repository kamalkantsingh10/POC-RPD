# RPD Corpus — Acquisition and Layout

**What this covers:** where the Test Corpus comes from, how to rebuild it from nothing, and how it is laid out for loading.
**Who it is for:** any Operator setting up a working environment, and anyone checking that an extraction run is reproducible.

**Writer: Operator.** `estate/test-corpus/` has exactly one writer (AD-18). No agent and no extractor writes here.

## Why the corpus lives outside this repository

The corpus sits at `~/Documents/Garage/obiee-corpus/`, not under `estate/`. Three reasons, in order of weight:

1. **Licensing.** Neither source carries a licence, so the default is all rights reserved. Source `sampleapp` additionally contains Oracle's SampleApp metadata, which is Oracle's IP wherever it is hosted. Reading them is one thing; redistributing them inside a repository shown to stakeholders is another.
2. **AD-16 — deployment is a file copy.** Every byte in this repository ships to the VDI. 1383 files of someone else's metadata are not part of the deliverable.
3. **AD-19 — adapters are tested against captured sample exports.** Small fixtures that *we* author, with recorded Ground Truth, are what belong in version control. The corpus is an input, not an artifact.

This also makes the setup honest: in production the extractor is pointed at a customer's estate by path. It is pointed at this corpus the same way.

**What is committed:** `corpus-manifest.csv` (this manifest, authored by us) and the fixtures derived from the corpus in later stories. **What is not:** any source XML.

## Sources

| `rpd-id` | Origin | Pinned commit | Source date | XML files |
|---|---|---|---|---|
| `bi-analytics-2013` | `github.com/VasiliKorzun/BI-Analytics-2013` | `19bef42a9574a039a90a40d986c10194aa3376f5` | 2013-10-08 | 1252 |
| `sampleapp` | `github.com/rvijay17/obiee` | `9a1c0a28211d981f320e38247b416c754c334398` | 2014-07-30 | 131 |

**The `rpd-id` values are declared here by the Operator**, per AD-7 — never derived from a filename, an acquisition timestamp, or a content hash, since all three change without the repository changing. They become the permanent prefix of every Knowledge Base identifier (`<rpd-id>::<layer>::<object-path>`), so changing one later invalidates every citation that uses it. Treat them as fixed.

`bi-analytics-2013` is a real working estate. `sampleapp` is SampleApp-derived — confirmed by physical table `SAMP_REVENUE_F`, schema `SAMPLESALES`, and Subject Areas "Sample Sales", "Densification - US Crime By State", "Population".

## Rebuilding from nothing

Both sources are public. No credentials are involved (NFR11).

```sh
mkdir -p ~/Documents/Garage/obiee-corpus
cd ~/Documents/Garage/obiee-corpus

git clone https://github.com/VasiliKorzun/BI-Analytics-2013.git
git -C BI-Analytics-2013 checkout 19bef42a9574a039a90a40d986c10194aa3376f5

git clone https://github.com/rvijay17/obiee.git
git -C obiee checkout 9a1c0a28211d981f320e38247b416c754c334398
```

Then build the clean set:

```sh
cd ~/Documents/Garage/obiee-corpus
rm -rf clean && mkdir -p clean
for pair in "bi-analytics-2013:BI-Analytics-2013" "sampleapp:obiee"; do
  id="${pair%%:*}"; src="${pair##*:}"
  mkdir -p "clean/$id/oracle/bi/server"
  cp -r "$src/oracle/bi/server/base" "clean/$id/oracle/bi/server/base"
done
```

Verify: `find clean -name '*.xml' | wc -l` → **1383**, and `find clean -type f ! -name '*.xml' | wc -l` → **0**.

## Clean set layout

```text
~/Documents/Garage/obiee-corpus/
  BI-Analytics-2013/          # raw clone — pinned, not loaded directly
  obiee/                      # raw clone — pinned, not loaded directly
  clean/                      # ← the extractor is pointed here
    bi-analytics-2013/        # rpd-id
      oracle/bi/server/base/<ObjectType>/<guid>.xml
    sampleapp/                # rpd-id
      oracle/bi/server/base/<ObjectType>/<guid>.xml
```

The raw clones carry material that is not repository metadata — `obiee` includes a Java project, an `.ear`, and a `.jdb` database file. The clean set holds **only** `oracle/bi/server/base/**`: 1383 XML files, nothing else.

**Every source has an identical internal layout.** That is what makes the demo requirement work — one path, `clean/`, reaches every source, and the directory name immediately beneath it is the `rpd-id`. A loader walks `clean/*/oracle/bi/server/base/*/*.xml` and knows each file's `rpd-id` from its path. This is the shape Story 1.4's CLI should expect.

## Manifest

`estate/test-corpus/corpus-manifest.csv` — 40 rows, one per `(rpd-id, object type)`, totalling 1383 objects. Columns: `rpd_id`, `source_url`, `commit_sha`, `acquired`, `object_type`, `object_count`.

It is produced by the Story 1.3 CSV writer rather than by hand, so it carries the same spreadsheet-safety guarantees as every Knowledge Base table and is verified by the same round trip. `commit_sha` is declared a guarded column: a SHA that happened to be all digits would otherwise be coerced by a spreadsheet.

## Re-acquisition triggers

- A source repository changes. Both are years dormant, so this is unlikely — and because the corpus is pinned by SHA, an upstream change has no effect until the pin is moved deliberately.
- Constructed Cases are authored (Story 1.9). Those are **authored by us**, do not belong in the pinned sources, and get their own location so the pins stay clean.
- A real customer estate becomes available. Then it is added as a third `rpd-id` and the existing two stay put — AD-8 keeps identically-named objects from different RPDs distinct by default.

## ⚠️ Personal data in `bi-analytics-2013`

Source B is a real working repository and carries personal names inside Subject Area and Business Model names — for example `Iryna_Bradzetskaya_MT_Full` and `Anton_Tserakhau`.

Anything derived from this source — a Knowledge Base table, a Group Spec, a screenshot in a demo — can surface those names. **Review derived artifacts before showing them outside the team.** Where a demo needs this source, prefer the `sampleapp` source, which carries only Oracle's fictional data.
