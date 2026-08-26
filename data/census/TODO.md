# Census transcription — remaining tasks (hand-off briefs)

Each task below is self-contained and can be done in a fresh session. Read
`README.md` first for the conventions. The golden rule of this package: **every
number transcribed must be covered by arithmetic checks** (p = m+f, rows sum to
printed totals, columns sum to printed totals, religions sum to all-religions,
sub-districts sum to districts) implemented in `validate.py`. Transcribe,
extend `validate.py`, run it, and resolve every failure before finishing.
Where a printed digit is ambiguous, enter the value forced by the marginal
sums and note it in README's "Transcription notes". Where the printed source
itself is internally inconsistent (rare, ±1–5), keep both printed values and
add a documented exception in `validate.py`.

Source PDFs (Census of Palestine 1931, Vol. II, ed. Mills): download from
https://users.cecs.anu.edu.au/~bdm/yabber/census/ — files
`Census1931_TabXVI-XVII.pdf`, `Census1931_TabXXI.pdf`, etc. Page images can be
rendered at high resolution with PyMuPDF when a scan is blurry:

```python
import fitz
doc = fitz.open("Census1931_TabXVI-XVII.pdf")
page = doc[PAGE_INDEX]          # PDF index = book page - offset; probe page 1 to find offset
pix = page.get_pixmap(matrix=fitz.Matrix(4, 4), colorspace=fitz.csGRAY,
                      clip=fitz.Rect(...))   # clip to half/third of page for legibility
pix.save("out.png")
```

## Task 1 — DONE (2026-08-26)

Both halves are transcribed and `validate.py` prints ALL CHECKS PASSED:

- `census-1931-occupations-by-unit.csv` — Table XVI Part II (a), all 27 units ×
  66 order-level column blocks × 6 measures (1,782 rows).
- `census-1931-industry-haifa-town.csv` — Table XXI Part II, Haifa town, all
  five community blocks × 17 industry rows × 58 columns (4,930 rows).

**Where the brief above was wrong**, for whoever writes the next one:

- Table XVI Part II (a) is not "~4 pp./unit". The units are the *rows*, repeated
  on all 82 pages; the classification runs across the pages as *columns*. There
  is no Haifa section to locate, so a Haifa-only file made no sense and the
  transcription covers every unit at once — the Northern District sum check the
  brief wanted comes free, and so do 25 others.
- The PDF's own text layer is far too lossy for Part II (a) (whole columns drop
  out, and it silently mis-assigns rows on skewed pages). The pages had to be
  read as images. What made that affordable was transcribing only the printed
  **Total** blocks — one per order — rather than all ~180 occupation-group
  columns; the 58 order totals sum exactly to `TOTAL ALL CLASSES`, so nothing is
  unverified. The group columns are still in the scans if anyone wants them.
- Table XXI has no "Part III — details for principal towns", and no
  establishments column. Haifa town is a section of **Part II**, split into five
  community blocks (all religions / Moslems / Jews / Christians / Others) printed
  twice over: pp. 588–590 carry columns 2–26 and pp. 591–593 columns 27–59, with
  two stacked 17-row blocks on four of the six pages.
- Two mechanical traps worth knowing about both tables: the row pitch in
  Table XVI Part II (a) is *not* uniform (the 27 units print in blocks of
  1/5/6/10/5 separated by blank lines), and every page is skewed by up to a
  degree, which shifts a label strip cropped from the left of the page by a full
  row against data cropped from the right. Deskew, or anchor on the block
  structure and let the arithmetic settle the alignment.

## Task 2 — DONE (2026-08-25)

Acre sub-district is transcribed to `vs1945-acre-subdistrict-villages.csv`
(57 serials, 65 rows) from `scans-vs1945-acre.jpg`; every row sum, all five
column sums and the cross-check against `vs1945-subdistrict-summary.csv` pass.
Transcription decisions are in README ("Transcription notes").

The optional other sheets remain: Nazareth.jpg, Tiberias.jpg, Beisan.jpg,
Safad.jpg, Jenin.jpg, Tulkarm.jpg at
https://users.cecs.anu.edu.au/~bdm/yabber/census/VillageStatistics1945/ .
To add one: follow the column format of the Haifa/Acre files, save the JPG as
`scans-vs1945-<sd>.jpg`, and add a `vs1945_villages("<Sd>")` call plus the
sub-district's entry in the summary cross-check loop in `validate.py` — the
sheet-level checks are already generic. Watch for the reprint's near-identical
`3`/`8` glyphs; the column totals are what settles them.

## Task 3 — DONE (2026-08-25)

The age-table cleanup is complete: `validate.py` prints ALL CHECKS PASSED.
The residual printed-source inconsistencies are documented in README
("Source-level inconsistencies kept as printed") and tolerated via `SDA_EXC`
in validate.py.

## Nothing is outstanding

All three tasks are done. What remains untranscribed in the scans is listed in
README under "Not transcribed"; the optional 1945 sheets beyond Haifa and Acre
are described under Task 2 above.
