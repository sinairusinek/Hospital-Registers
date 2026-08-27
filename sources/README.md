# sources/

Primary sources, public. The rule that separates this folder from `paper/`:

- **Here**: primary material — the Mandate press, the Government's own annual
  reports, archival catalogues. Mostly Crown copyright, long expired.
- **`paper/`** (gitignored): secondary literature and private drafts — Sufian,
  Ziadat, Mahmoud, Davidovitch, the bibliography, the article in progress.

The split exists because the site has to build without `paper/`. A GitHub
Actions run checks out the repo and nothing else, so anything the published
site needs must live on this side of the line.

## What is here

    press/hand-authored-sources.json   35 citations: 29 English, 3 Arabic,
                                       3 German. Read and translated by hand,
                                       so no generator can rebuild them.
    archives/mandate-reports/          The Colonial Office annual reports on
                                       Palestine, 1928-1938, as text.
    archives/doh/                      Department of Health annual report, 1921.
    archives/meca-jem-catalogue.txt    Middle East Centre Archive catalogue.

## The source registry

`data/public/sources-registry.json` is the clickable-source payload behind the
history document and the site's Timeline drawer. It is **generated** — do not
edit it by hand:

    python3 pipeline/source_registry.py

It merges two inputs, both public:

  - 243 Hebrew entries built from `data/newspapers/heb_article_readings.md`,
    which is the system of record for the Hebrew corpus (human reads, not OCR).
  - the 35 hand-authored entries in `press/hand-authored-sources.json`, which
    is the file to edit when an Arabic, German or English citation changes.

The generator also renders each reading note's Markdown to HTML, escaping it
first, because the app injects these with `dangerouslySetInnerHTML`.

## What is deliberately not here

The scanned PDFs — the Israel State Archives files are 345 MB, and two are over
GitHub's 50 MB warning threshold. The site needs the citation data, not the
scans. The three extracted ISA figures (15 MB of PNG) are scans too and stay
private for the same reason; if the app ever displays them they should come
back as web-sized derivatives, not originals.
