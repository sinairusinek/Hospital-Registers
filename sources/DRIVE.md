# The Drive mirror of the primary sources

`מאמר לקתדרה/מקורות ראשוניים` on Google Drive holds the primary sources and
everything extracted from them, organized for colleagues who do not have a
checkout. Built 28 August 2026.

- Folder: <https://drive.google.com/drive/folders/1o184-P0II0N1tn9EUTeo922J8Soipfh4>
- Drive root folder ID: `0B1TlfouSwHTnfmNWZ0JFdGdodHRqYnBpYkRjVnNmU19WS0NUTVdybDg1V2pSckpYemhDNlE`

## Layout

| folder | source in this repo |
|---|---|
| `00 מדריך — קראו קודם` | authored for the Drive collection; a Google Doc, no repo original |
| `01 הפנקסים` | `data/public/` (iiif-pages, derived tables), `data/private/page-cache/`, `pipeline/prompts/`, `kimatch/`, `data/eval/` |
| `02 ארכיון המדינה` | `paper/sources/isa/` (PDFs, `pages/`, `figures/`), `data/archives/*.md`, `data/private/isa-*` |
| `03 דוחות רשמיים` | `sources/archives/`, `paper/sources/doh/`, and the eight `data/haifa_hospital_*.txt` grep lists |
| `04 עיתונות` | `data/newspapers/`, `sources/press/`, `data/public/sources-registry.json`, `paper/press-register-cases.md` |
| `05 מפקדים` | `data/census/` |
| `06 סינתזה` | `paper/hospital-history.html`, `paper/timeline.svg.html`, `paper/figures/` |
| `07 ספרות משנית` | shortcut only — the bibliography keeps its existing home |

Not mirrored: `hospital-registers-normalized.tsv` and `timeline.json` (derived),
the pipeline `.py` files, `hospital-institutional-history.md` (superseded; its §1
siglum key is copied into the guide), and `paper/sources-registry.json` (stale).

Shortcuts, not copies: the master `Hospital-Registers-2025-08-10.xlsx`/`.csv`,
`11-26data`, `ביבליוגרפיה`, and Eliezer's ISA file list.

## How it was built

The scripts are in `sources/drive-sync/`: `rc.sh` (rclone wrapper), `stage.sh`
(builds the local staging tree), `md2html.py` (Markdown → importable HTML), and
`manifest.py` (builds the file-map CSV). All transfers use the `jeckedrive:`
rclone remote — the Drive connector is far more expensive for files this size,
and direct Google API calls with rclone's token are rate-limited.

Wrapper that pins the root folder (note `--drive-root-folder-id=VALUE`; the
space-separated form is parsed as an unknown flag and the command dies):

```sh
#!/bin/zsh
ROOT=0B1TlfouSwHTnfmNWZ0JFdGdodHRqYnBpYkRjVnNmU19WS0NUTVdybDg1V2pSckpYemhDNlE
exec rclone "$@" --drive-root-folder-id="$ROOT"
```

**Markdown readings → Google Docs.** rclone will not import `.md` (Drive's
import API rejects it) and the remote is configured with `export_formats=docx`,
which blocks HTML import too. The working route is Markdown → HTML → import,
overriding the export format on the command line:

```sh
python3 md2html.py reading.md reading.html          # markdown lib, adds dir="rtl" for Hebrew
rc.sh copy staged/ "jeckedrive:<dest>" \
  --drive-import-formats html --drive-export-formats html
```

`md2html.py` decides direction by counting Hebrew against Latin characters, so
the Hebrew guide imports right-to-left and the English readings do not.

**Everything else** goes up raw — CSV and TSV are deliberately *not* converted
to Sheets, so the data stays byte-exact:

```sh
rc.sh copy staged/ "jeckedrive:<dest>" --exclude "*.html" --exclude ".DS_Store"
```

**Shortcuts:**

```sh
rc.sh backend shortcut jeckedrive: "<source path>" "<destination path>"
```

The `context/` folder that used to sit at the Drive root was folded into this
collection with server-side moves (`rc.sh move`), which preserve file IDs, so
any existing links into `context/census` and friends still resolve.

## Re-syncing

The collection is a snapshot, not a live mirror. To refresh a section after
changing files here, rebuild the staging tree and re-run the copy for that
section only. Re-running a copy over a Google Doc will not update it — the Doc
is a converted artifact; delete and re-import if a reading changes materially.

## Caution

`02 ארכיון המדינה/חילוצים (שמות — לא להפצה)` and
`04 עיתונות/קריאות/12 ימי אסון` carry personal names beside medical
information. They are gitignored here for that reason and are in Drive only
because the collaborators are co-investigators. Anyone given access to the
folder gets them.
