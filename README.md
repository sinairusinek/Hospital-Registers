# Hospital Registers

Digitization and analysis of the Haifa Government Hospital admission registers, 1930–1934. ~6,000 patient records across ten handwritten notebooks, structured via AI-assisted transcription into ~30 normalized fields (religion, nationality, occupation, address, ward, ICD-9-coded diagnosis, length of stay, outcome, confidence).

## PII policy

Patient names were redacted at the image stage before transcription (hence the `Anon_*` source tables). The consolidated dataset in `data/public/` contains no patient names. Street addresses are coarsened in the published artifact — house numbers stripped, neighborhood / street name retained. City and locality fields are kept at full fidelity. The full unredacted master sits in `data/private/` (gitignored, local only).

## Layout

- `data/public/hospital-registers-2025-08-10.tsv` — consolidated dataset powering the public site.
- `data/private/` — local-only working copies (gitignored).
- `hospitals11-26/` — per-notebook `Anon_*_tables.xlsx` source transcriptions.
- `pipeline/` — TSV → SQLite build (`build.py`), including address coarsening.
- `kimatch/` — Kima Historical Gazetteer matching for the `City` column; column-pluggable.
- `site/` — Datasette database + metadata (build artifact; gitignored).
- `docs/` — static GitHub Pages landing page that embeds Datasette Lite.
- `notebooks/` — analysis notebooks feeding `paper/figures/`.
- `paper/` — Hebrew Cathedra article skeleton.

## Workstreams

1. YBZ 2026 conference abstract — submitted June 2026.
2. Public exploration site — Datasette Lite over GitHub Pages.
3. Settlement-name matching against Kima.
4. Cathedra article (Hebrew, autumn 2026 submission).

See `CFP. Illness Health and Healing. YBZ 2026.pdf` for the conference call.
