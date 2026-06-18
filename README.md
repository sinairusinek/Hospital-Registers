# Hospital Registers

Digitization and analysis of the Haifa Government Hospital admission registers, 1930–1934. ~6,000 patient records across ten handwritten notebooks, structured via AI-assisted transcription into ~30 normalized fields (religion, nationality, occupation, address, ward, ICD-9-coded diagnosis, length of stay, outcome, confidence).

## Layout

- `data/private/` — full transcribed dataset (gitignored, includes PII).
- `data/public/` — redacted artifact powering the public site (names, full addresses, next-of-kin removed; city/locality retained).
- `pipeline/` — transforms, including `redact.py` (private → public).
- `kimatch/` — Kima Historical Gazetteer matching for the `city` column; pluggable on column name.
- `site/` — Datasette configuration; published via GitHub Actions.
- `notebooks/` — analysis notebooks feeding both the site and `paper/figures/`.
- `paper/` — Hebrew Cathedra article skeleton.

## Workstreams

1. YBZ 2026 conference abstract (submitted June 2026).
2. Public exploration site (Datasette + GH Pages/Cloudflare).
3. Settlement-name matching against Kima.
4. Cathedra article (Hebrew, autumn 2026 submission).

See `CFP. Illness Health and Healing. YBZ 2026.pdf` for the conference call.
