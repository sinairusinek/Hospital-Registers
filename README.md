# Hospital Registers

Digitization and analysis of the Haifa Government Hospital admission registers, 1930–1948. ~29,880 patient records across 33 handwritten notebooks, structured via multimodal LLM transcription into ~50 fields — raw and normalized pairs for religion, nationality, occupation, address, ward, class/rate, ICD-9-coded diagnosis, length of stay, outcome, plus per-record confidence and date-quality flags.

## PII policy

Patient names were redacted at the image stage before transcription (hence the `Anon_*` source tables). The consolidated dataset in `data/public/` contains no patient names. Street addresses are coarsened in the published artifact — house numbers stripped, neighborhood / street name retained. City and locality fields are kept at full fidelity. The full unredacted master sits in `data/private/` (gitignored, local only).

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

Planned, still empty:

- `pipeline/build.py` — TSV → SQLite build including address coarsening.
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

Column 45 of the public TSV carries a corrupted header (`<info@doctorsonly.co.i`), an artifact of the source spreadsheets. To be cleaned in the build step.

See `CFP. Illness Health and Healing. YBZ 2026.pdf` for the conference call.
