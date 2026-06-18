# data/private/

Local-only working copies of the unredacted master dataset. Everything in this directory except this README is gitignored.

Drop here:

- `hospital-registers-2025-08-10.xlsx` — full master from Drive (file ID `1jB6tl09c_bBBm2RilA8MG0a4-SLEm5CR`).
- Any intermediate transcription artifacts that contain raw addresses with house numbers, or any field that should not appear in `data/public/`.

The `pipeline/build.py` script reads from `data/public/` only. If you need to regenerate `data/public/hospital-registers-2025-08-10.tsv` from the private master, do that step manually and commit the resulting public TSV.
