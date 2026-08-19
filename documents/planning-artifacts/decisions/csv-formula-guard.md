# Decision: CSV formula guard

**What this covers:** how Knowledge Base CSV files stay safe to open in a spreadsheet without losing the character-for-character fidelity of OBIEE formula text.
**Who it is for:** anyone reading a Knowledge Base table, and anyone reviewing whether FR-2's verbatim claim actually holds.

**Status:** decided 2026-08-16, confirmed with the Operator per Story 1.3 AC #8.

## The conflict

Two requirements collide on the same bytes.

- **FR-2** — a logical column's formula is stored *verbatim, character-for-character*, never rewritten or reformatted.
- **FR-28** — the file survives being opened in a spreadsheet application, with a documented round trip proving values are unchanged.

They collide because spreadsheets rewrite values on open, **even when the field is quoted**:

| Input | Excel shows | Why |
|---|---|---|
| `-1 * "Sales"."Revenue"` | a formula, or an error | leading `-` is treated as a formula |
| `=CASE WHEN ...` | a formula | leading `=` |
| `00123` | `123` | numeric coercion drops leading zeros |
| `1E5` | `100000` | numeric coercion applies scientific notation |

Quoting alone does not prevent any of these. OBIEE formulas genuinely begin with `-` and `+`, and identifier-like values genuinely carry leading zeros, so this is not a theoretical case.

Note the scope: this is **wider than the four characters** named in the Architecture Spine's convention (`=` `+` `-` `@`). Numeric coercion is the same defect arriving by a different route, and FR-28's own consequence list requires leading zeros and scientific notation be handled. Any guard that covers only the four punctuation leaders is half a guard.

## Options considered

| Option | Spreadsheet-safe | Bytes on disk | Reversible | Verdict |
|---|---|---|---|---|
| Quoting alone (`QUOTE_ALL`) | No | Verbatim | n/a | Fails FR-28 |
| No guard; document "import as text" | No, if double-clicked | Verbatim | n/a | Rejected — a reviewer double-clicking the file *is* the demo scenario |
| Leading tab on affected fields | Partly; brittle across applications | Altered | Ambiguous | Weaker than the apostrophe with no compensating benefit |
| Leading apostrophe, no flag | Yes | Altered | **Heuristic** | Rejected — a value that legitimately begins `'` becomes indistinguishable from a guarded one |
| **Leading apostrophe + companion flag column** | Yes | Altered | **Deterministic** | **Chosen** |

## The decision

**Guard only affected fields with a single leading apostrophe (`'`), and emit a companion boolean column for every column declared guardable.**

- A column named `formula` gets a companion `formula_guarded`, written immediately after it.
- The flag is `true` or `false` per row.
- A reader strips **exactly one** leading apostrophe when, and only when, the flag is `true`.

The flag is what makes this correct rather than merely convenient. Without it, a formula that genuinely starts with `'` is indistinguishable from a guarded one, and reversal becomes a guess. With it, reversal is deterministic and the artifact is self-describing, satisfying AD-5.

**Undeclared columns fail loudly.** If a value needing a guard appears in a column the caller did not declare guardable, the writer raises, naming the column and row. Silent mangling is the primary failure mode this product is designed against (NFR7); a loud error at write time is the correct response.

**No UTF-8 BOM.** A BOM would help Excel detect encoding but changes the file's first bytes and contaminates the first header field for any reader that does not strip it. Revisit only if real corpus content proves it necessary — and record it here if so.

## What is claimed, precisely

> The stored value is verbatim and recoverable byte-for-byte. The on-disk representation carries a declared, reversible guard on fields that a spreadsheet would otherwise corrupt.

This wording matters. Claiming the file bytes are untouched would be false, and NFR7 makes honesty about limitations non-negotiable. The verbatim guarantee is a property of the **value**, enforced by a round-trip test, not a property of the byte stream.

## How it is verified

- Automated round trip over a corpus covering: embedded comma, embedded double quote, embedded newline, leading `-`, `=`, `+`, `@`, `00123`, `1E5`, a 16-digit integer, non-ASCII text, empty string, a value already beginning with `'`, and real OBIEE/MDS expression text. Every value must compare byte-equal after write → read.
- Automated assertions that output is UTF-8 with no BOM, LF line endings, and every field quoted.
- **One manual verification**, recorded below: open the produced CSV in a spreadsheet application, save, re-read, confirm equality.

### Manual verification record

*Pending — to be completed when a spreadsheet application is used against a produced Knowledge Base table.*

| Field | Value |
|---|---|
| Application and version | — |
| Date | — |
| Result | — |

## ⚠️ LibreOffice, pandoc, openpyxl are excluded

NFR15 excludes `pandoc`, `LibreOffice`, `python-docx`, and `openpyxl`, and the PRD records why: they are already installed on the development machine and **can be adopted by accident — working locally and failing in the VDI.**

The manual round trip above is performed **by a human, once**. Automating it would pull a spreadsheet library into the product and breach NFR15. A human using a spreadsheet to check a file is not a dependency; a script importing one is.
