# Hospital Registers

Digitization and analysis of the Haifa Government Hospital admission registers, 1930–1948. ~29,880 patient records across 33 handwritten notebooks, structured via multimodal LLM transcription into ~50 fields — raw and normalized pairs for religion, nationality, occupation, address, ward, class/rate, ICD-9-coded diagnosis, length of stay, outcome, plus per-record confidence and date-quality flags.

## PII policy

Patient names were redacted at the image stage before transcription (hence the `Anon_*` source tables). The consolidated dataset in `data/public/` contains no patient names. The full unredacted master sits in `data/private/` (gitignored, local only).

Street addresses are coarsened by `pipeline/build.py` — house numbers, box numbers and unit numbers stripped, street or neighbourhood retained — in `hospital-registers-normalized.tsv`, which is what the site serves. **The consolidated `hospital-registers-2025-08-10.tsv` in this repo is not coarsened**: 2,017 of its addresses carry a number. It has been committed and public since the first push, so treat it as already disclosed.

Two things the coarsening does not reach, both still open:

- `Next of Kin` holds 2,379 personal names of third parties.
- Some `Address` and `Occupation` values embed a person's name or a service number ("Mother. Mrs Barr 38 Oakford Road Walthamstow London", "Soldier No. 3127205"). Coarsening removes the digits, not the name.

## Layout

Built:

- `data/public/hospital-registers-2025-08-10.tsv` — consolidated dataset, 29,879 records × 53 columns.
- `data/private/` — local-only working copies (gitignored).
- `data/eval/` — ground-truth accounting for the Transkribus comparison: `gt_inventory.tsv` (57 Transkribus documents, GT page counts) and `gt_provenance.tsv` (95 training/validation pages traced back to source document and page).
- `hospitals11-26/` — per-notebook `Anon_*_tables.xlsx` source transcriptions (10 of the 33 notebooks; the rest live in Drive).
- `pipeline/transkribus/` — Transkribus API client plus inventory/provenance extraction, feeding `data/eval/`.
- `pipeline/prompts/gemini-v1.md` — the multimodal extraction prompt.
- `app/` — "Hospital Registry Observer", the React + Vite exploration app (browse, facet, filter, chart). Deployed to GitHub Pages at https://sinairusinek.github.io/Hospital-Registers/ by `.github/workflows/pages.yml`. Run locally with `npm install && npm run dev` from `app/`; the dataset is staged out of `data/public/` by `app/scripts/copy-data.mjs`. The AI-synthesis panel asks the visitor for their own Gemini API key — the site is public and static, so none is bundled.
- `paper/` — Cathedra article materials: chapter template, bibliography TSVs, extract bank, acquired sources. **Gitignored** — local only.

- `pipeline/build.py` — builds the published artifact: a second normalization pass over the `standardized *` columns plus address coarsening, writing `data/public/hospital-registers-normalized.tsv` (gitignored, derived) and `data/public/normalization-report.tsv` (every merge and the low-frequency tail, for review). Run `python3 pipeline/build.py`; the Pages workflow runs it on every deploy.

Planned, still empty:

- `kimatch/` — Kima Historical Gazetteer matching for the `City` column; column-pluggable.
- `site/` — Datasette database + metadata (build artifact; gitignored).
- `notebooks/` — analysis notebooks feeding `paper/figures/`.

## Workstreams

1. YBZ 2026 conference abstract — submitted June 2026; conference 4–5 November 2026.
2. Cathedra article (Hebrew) — outline at `paper/cathedra_template_v4.docx`; submission autumn 2026, before the conference.
3. Public exploration site — `app/` on GitHub Pages (live); a Datasette Lite view over the same data remains an option for SQL access.
4. Settlement-name matching against Kima.
5. DH methods paper — multimodal LLM extraction vs. a trained Transkribus model; `pipeline/` + `data/eval/`.

## Known data issues

- Column 45 of the consolidated TSV carries a corrupted header (`<info@doctorsonly.co.i`). By position and content it is the standardized ICD-9 name for the primary diagnosis; `build.py` renames it to `standardPrimaryICD9Name`. Worth confirming against the source spreadsheets.
- `Standardized Diagnosis` is not a normalization: it holds 13,992 distinct values against `Original Diagnosis`'s 13,851, i.e. more. The column that actually groups diagnoses is `standardPrimaryICD9Name` (3,860 distinct ICD-9 labels), which is what the site facets on.
- One repeated header line sits inside the data (dropped by `build.py`, leaving 29,879 records). Eight legitimate records carry `Ward = "Ward"` or `Rate = "Rate"`, so it cannot be found by a single self-matching field.
- The registers contain bare double quotes (inches, gershayim), so the published TSV is written **unquoted by design** (`build.py` strips only tabs and newlines from values). **Any consumer must disable quote handling.** PapaParse's defaults silently merge rows and yield 19,718 records; Python's `csv` and pandas defaults are quieter and worse — they return **29,727 records instead of 29,880**, losing 153 without any error. Use `csv.reader(..., delimiter='\t', quoting=csv.QUOTE_NONE)` or `pd.read_csv(..., sep='\t', quoting=3)`; a bare `split('\t')` is also correct for this file.
- Years were widely misread, a page at a time, and `build.py` repairs them from the register's own order: 360 admissions that ran backwards against their notebook's sequence, 17 discharge years standing a year over the clerk's own count, and 5 dates outside 1930–48 repaired from the other date on the record. Two remain, both notebook 8's `17/5/63` with no discharge date to anchor them; the notebook is otherwise entirely 1934, so 63 is almost certainly 34, but that is inference from the notebook rather than from the record. They are flagged `date-out-of-span` and still stretch the date range to 1963.
- 95 values survive normalization on fewer than 20 records each; see `data/public/normalization-report.tsv` for the list.

See `CFP. Illness Health and Healing. YBZ 2026.pdf` for the conference call.
