# The ward column: 5,190 legible wards that standardize to nothing

**Status: open.** Found 28 August 2026 while fixing a smaller, related bug
(commit `fa56f20`). Not acted on, because it changes a figure the published
institutional history argues from and that argument needs rereading by a
historian, not a rerun of the build.

## What is wrong

`pipeline/build.py` carries two maps of ward names:

- `WARD` — used to standardize the `Ward` column into `standardized ward`.
- `WARD_WRITTEN` — used to *read* a written ward when recovering one that the
  extraction misfiled into another column.

`WARD_WRITTEN` knows the clerk's abbreviations. `WARD` does not. So a record
whose ward column plainly reads `Isolation`, `Surg`, `Is.`, `Isol`, `Med`,
`Gen` or `Maternity` standardizes to an empty string and lands in the
no-ward bucket.

**5,190 records are affected.** A further 2,156 have a written ward that is
genuinely unreadable (`C`, `B`, `D`, `G`, `Hut`, `Isolation Ward`,
`[uncertain_ward]`, `Surgical Section`) and should stay empty — some of those
are lettered pavilions, which the ISA drawing schedule shows ran A–F, so they
are a separate question and possibly recoverable from the archive.

The recoverable values, most common first:

| written | records |
|---|---|
| `Isolation` | 2,120 |
| `Surg` | 715 |
| `Maternity` | 486 |
| `Is.` | 485 |
| `Isol` | 373 |
| `Surg.` | 261 |
| `Surgical` | 209 |
| `Med` | 171 |
| `Infectious Diseases` | 108 |
| `Med.` | 71 |
| `Gen` | 57 |
| `Gen.` | 36 |

## What fixing it does to the figures

| ward | now | after | change |
|---|---|---|---|
| *(empty)* | 11,593 | 6,087 | **−5,506** |
| Isolation | 2,321 | 5,299 | **+2,978** |
| Surgical | 4,046 | 5,232 | +1,186 |
| Maternity | 1,506 | 2,046 | +540 |
| General | 1,651 | 1,987 | +336 |
| Medical | 3,604 | 3,877 | +273 |
| Infectious Diseases | 149 | 286 | +137 |
| British Section | 2,717 | 2,758 | +41 |
| Venereal Diseases | 90 | 95 | +5 |

A handful resolve to a combination (`Isolation | Infectious Diseases`, 5
records; `Surgical | General`, 2), which the existing `WARD_SPLIT` handling
already produces for other values.

## Why it was not just done

§08 of the institutional history — *The isolation hospital, and the lazaret
question* — argues from **"2,278 admissions recorded as Isolation, with a
further 356 as Infectious Diseases"** and from the observation that the value
*disappears* rather than fading, concluding: *"the clerks changed what they
wrote in the ward column."*

Those 5,190 records are very likely that same phenomenon. Checked by year, the
recoverable Isolation records cluster in **1931–1940** and are essentially
absent after 1944 — the same shape the section describes. So the correction
**sharpens** the argument rather than refuting it. But it doubles the number
the argument quotes, and the published sentence becomes false the moment the
build runs.

That is a historian's call on a published document, not a mechanical fix.

## The fix itself

Roughly ten lines. In `pipeline/build.py`, `WARD` needs the abbreviations that
`WARD_WRITTEN` already carries. The cleanest form is probably to build `WARD`
from `WARD_WRITTEN` rather than maintaining two lists that disagree — but keep
`GYNECOLOGY_IS_GENERAL` applying, and keep the unreadable tokens (`C`, `B`,
`Hut`, `[uncertain_ward]`) resolving to nothing.

Verify with:

```sh
python3 pipeline/build.py     # the "wards" summary line reports what moved
```

and check `data/public/normalization-report.tsv` for the merge decisions.

## What else has to move with it

1. **`paper/hospital-history.html` §08** — the 2,278 figure, the 356, and the
   surrounding argument. Republish the artifact afterwards
   (`Artifact(action:"publish", file_path:"paper/hospital-history.html",
   url:"https://claude.ai/code/artifact/f0cc1896-1a84-4572-a14d-b93d2648da2b")`)
   and the site carries it automatically via `app/public/`.
2. **The site's Statistics view** — ward breakdowns change; no code change
   expected, but the figures should be eyeballed.
3. **`pipeline/isa_returns_link.py`** — it joins the ISA 1942–44 returns to
   the register partly on ward; check whether more matches appear.
4. **The memory note** `project_ward_gynecology_error.md`, which records the
   ward column as usable — it stays true, but this is the second correction to
   the same column and belongs in the record.
5. **The lettered pavilions** (`C`, `B`, `D`, `G`, 238+111+68+31 records) are
   a separate open question. ISA drawing schedule E/524 shows pavilions A–F
   but no page says what any pavilion was used for; sheet `E/R 286 "KEY PLAN"`
   would name them and is not in the file. See
   `data/archives/isa_buildings_index.md`.
