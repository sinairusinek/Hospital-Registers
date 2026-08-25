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

## Task 1 — Occupations, Haifa focus (Table XVI + Table XXI)

- `Census1931_TabXVI-XVII.pdf` starts at book p. 281. Table XVI Part II
  ("General table — details for districts and sub-districts, (a) settled
  population") runs pp. 315–396, units in the geographic order used throughout
  (Southern District, Gaza, Beersheba, Jaffa, Ramle, Jerusalem District,
  Hebron, Bethlehem, Jerusalem, Jericho, Ramallah, Northern District, Tulkarm,
  Nablus, Jenin, Nazareth, Beisan, Tiberias, HAIFA, Acre, Safad; ~4 pp./unit).
  Locate and transcribe the **Haifa sub-district** section (occupational
  classes/orders × earners/working dependants/non-working dependants × sex) to
  `census-1931-occupations-haifa-subdistrict.csv`. Also transcribe the
  **Northern District** section if feasible (gives a sum check).
- `Census1931_TabXXI.pdf` starts at book p. 545. Table XXI Part III "Details
  for principal towns — Haifa" is book pp. 588–593. Transcribe to
  `census-1931-industry-haifa-town.csv` (organized industry: establishments,
  persons engaged, by industry group).
- Check columns/rows against the printed totals; note in README that the other
  units of Tables XVI–XXI remain untranscribed in the scans.

## Task 2 — Village Statistics 1945, Acre sub-district (+ optional others)

- Source sheets: https://users.cecs.anu.edu.au/~bdm/yabber/census/VillageStatistics1945/Acre.jpg
  (also Nazareth.jpg, Tiberias.jpg, Beisan.jpg, Safad.jpg, Jenin.jpg,
  Tulkarm.jpg if desired). PLO 1970 reprint; population by
  Moslems/Jews/Christians/Others/Total, rounded to nearest 10; footnotes name
  component settlements.
- Follow the exact format of `vs1945-haifa-subdistrict-villages.csv`
  (serial, village, moslems, jews, christians, others, total, note) →
  `vs1945-acre-subdistrict-villages.csv` etc.
- Checks (add to `validate.py`): each row M+J+C+O = total; each column sums to
  the sheet's printed TOTAL row; the TOTAL row equals the sub-district's row in
  `vs1945-subdistrict-summary.csv` (Acre: 47,290 / 2,950 / 11,150 / 6,940 /
  68,330). Save the source JPG as `scans-vs1945-acre.jpg`.

## Task 3 — DONE (2026-08-25)

The age-table cleanup is complete: `validate.py` prints ALL CHECKS PASSED.
The residual printed-source inconsistencies are documented in README
("Source-level inconsistencies kept as printed") and tolerated via `SDA_EXC`
in validate.py. Only Tasks 1-2 above remain.
