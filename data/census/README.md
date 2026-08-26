# Census backdrop data: 1922 / 1931 / 1945

Population denominators for the Haifa Government Hospital registers (1930–1948):
the 1931 Census of Palestine (with its 1922 appendix) and the 1945 Village
Statistics, transcribed from page scans into CSV. Run `python3 validate.py` to
re-check every row sum, column sum, and cross-table identity; the transcription
passes all of them.

## Sources

- **Census of Palestine 1931, Volume II (Tables)**, ed. E. Mills, Alexandria 1933.
  Scans hosted by Brendan McKay (ANU): <https://users.cecs.anu.edu.au/~bdm/yabber/yabber_census.html>
  — Volume II is split into seven PDFs (`Census1931_ContentsTabI-VI.pdf` … `Census1931_TabXXI.pdf`).
  The *Population of Villages, Towns and Administrative Areas* volume (1932) is also on
  archive.org (CC0, expired Crown copyright): <https://archive.org/details/palestine-census-1931>.
  Census night: 18 November 1931.
- **Village Statistics, April 1945** (Government of Palestine), via the PLO Research
  Center 1970 reprint hosted on the same ANU page (per-sub-district JPGs + full PDF).
  The reprint combines the demographic columns into Moslems/Jews/Christians/Others,
  **rounded to the nearest 10**. Source sheets for what is transcribed here are kept
  as `scans-vs1945-haifa.jpg` and `scans-vs1945-summary.jpg`.
- **Census 1922** figures come from the Appendix to Volume II (pp. 594–595), which
  restates the 1922 results **within the 1931 administrative boundaries** — so they
  are directly comparable with the 1931 files (and not always identical to the 1922
  census report itself).

## Files

| file | source table | content |
|---|---|---|
| `census-1931-religion-by-subdistrict.csv` | Vol. II Table VII Part I (pp. 24–25) | Total population (settled + nomadic) by district/sub-district × religion × sex. Religions here are the census's full list: Moslems, Jews, Christians, Druzes, Bahais, Samaritans, "No religion". |
| `census-1931-towns-religion.csv` | Table VI Part I (p. 18) | The 23 municipalities × religion × sex ("others" = Druzes+Bahais+Samaritans+Agnostics). |
| `census-1931-towns-minor-religions.csv` | Table VI preface (p. 17) | The split of each town's "others" into Druzes/Bahais/Samaritans/Agnostics. |
| `census-1931-rural-religion.csv` | Table VI Part II (p. 19) | Rural (incl. nomadic) population by sub-district × religion × sex. Urban+rural sums to the sub-district totals (checked). |
| `census-1931-christian-churches.csv` | Table VII Part II (pp. 26–28) | Christians by denomination (16 groups) × sex, per sub-district. |
| `census-1931-haifa-subdistrict-age.csv` | Table VIII Part II (pp. 84–85) | **Haifa sub-district**: age × sex × civil condition × religion. |
| `census-1931-haifa-town-age.csv` | Table VIII Part IV (pp. 106–107) | **Haifa town**: age × sex × civil condition × religion. No printed all-religions panel on these pages; the sum of the four panels is verified against Table VI's Haifa row (50,403 / 27,043 M / 23,360 F). |
| `census-1931-subdistricts-age.csv` | Table VIII Parts I–II (pp. 46–89) | Age × sex × religion **population** for Palestine, the 3 districts and all 17 other sub-districts (Haifa has its own file with civil-condition detail; for district sums use it together with this file). Settled population only (Part V nomads not included). The Jerusalem District panel and the Jaffa all/Moslems panels are poor scans and are entered as the exact sums/differences of the surrounding crisp panels, verified against their printed totals. Civil-condition columns for these units remain in the scans. |
| `census-1931-literacy-by-district.csv` | Table IX (A) Parts I–II (pp. 110–113) | Literate/illiterate × sex × religion in four age bands (0–7, 7–14, 14–21, 21+), Palestine and districts. |
| `census-1931-literacy-towns.csv` | Table IX (A) Part III (pp. 114–120) | Same for each of the 23 towns (all religions), and by religion for Jaffa, Tel Aviv, Jerusalem and **Haifa**. |
| `census-1931-infirmities-by-subdistrict.csv` | Table XV Parts II–III (pp. 276–280) | The census's four infirmities — insane, blind of one eye, totally blind, totally deaf, deaf-and-dumb — total and "from birth", × sex, per sub-district, for all religions together and for Moslems/Christians/Jews/Others separately. "Population dealt with" = settled population. |
| `census-1931-infirmities-by-age.csv` | Table XV Part I (pp. 272–275) | Same by age group, Palestine-wide. Complete for all-religions and Moslems; for Christians/Jews/Others the population, cases and insane columns are transcribed and the four sight/hearing columns are left blank (below confident-transcription threshold in our scan copy; their totals are in the by-subdistrict file). |
| `census-1931-occupations-by-unit.csv` | Table XVI Part II (a) (pp. 315–396) | Occupation or means of livelihood, **settled population**, for all 27 units the table prints (Palestine, the 3 districts, all 18 sub-districts, the Four Main Towns and each of the four towns) × the classification's 58 orders (plus Order 1's six sub-orders and Order 2 (a)) × total / earners by sex / partly agriculturists by sex / dependants. Order-level only — see "Table XVI: what is and is not here". |
| `census-1931-industry-haifa-town.csv` | Table XXI Part II (pp. 588–593) | **Organized industry, Haifa town**: the census's 16 industry groups (plus the town total) × all religions / Moslems / Jews / Christians / Others × the table's 58 columns — total population engaged, then managers, supervising & technical, clerical, operatives under 17 and operatives 17 and over, each split by sex and by Palestinian Arabs / Palestinian Jews / Palestinian others / non-Palestinians. Long format: one row per religion × industry × column. Haifa town engaged 1,881 persons (713 Moslems, 822 Jews, 307 Christians, 39 others). |
| `census-1922-religion.csv` | Appendix to Vol. II (pp. 594–595) | 1922 population by religion × sex, urban (per town) and rural (per sub-district), in 1931 boundaries. |
| `vs1945-haifa-subdistrict-villages.csv` | Village Statistics 1945, Haifa sheet | All 84 territorial units of Haifa sub-district × religion, with the sheet's footnotes in a `note` column. Haifa town row: 35,940 M / 75,500 J / 26,570 C / 290 others = 138,300. |
| `vs1945-acre-subdistrict-villages.csv` | Village Statistics 1945, Acre sheet | All 57 territorial units (serials 1–51 villages, 52–57 tribal units) of Acre sub-district × religion, 65 rows because several serials brace two to four named settlements. TOTAL: 47,290 M / 2,950 J / 11,150 C / 6,940 others = 68,330. |
| `vs1945-subdistrict-summary.csv` | Village Statistics 1945, summary sheet | All Palestine sub-districts × religion (1945 district boundaries: Haifa is its own district; Galilee/Samaria/Lydda districts exist by now). |

### Age-table format

Rows are as printed: single years `0-1`…`4-5`, their subtotal `0-5`, then
five-year groups to `75+` and `not_recorded`, plus a `total` row. **Do not sum
single-year rows together with `0-5`.** Columns: population, unmarried, married,
divorced, widowed — each as persons/males/females.

### Table XVI: what is and is not here

Part II (a) is **not** laid out as one section per geographic unit, the way the
age and infirmity tables are. It runs the other way round: the 27 units are the
*rows*, repeated identically on all 82 pages, and the occupational classification
marches across the pages as *columns*. Every occupation group has its own
six-column block (total earners and dependants; earners, males and females;
partly agriculturists, males and females; dependants and working dependants),
and each order, each sub-order of Order 1, and Order 2 (a) also carries a
printed **Total** block.

`census-1931-occupations-by-unit.csv` holds those Total blocks — 66 of them,
covering the whole classification at order level — for all 27 units. The
individual occupation-group columns (roughly 180 of them, "orange growers",
"woodcutters and charcoal burners", and so on) are **not** transcribed; they
remain in the scans. Nothing is lost from the order-level picture: the 58 order
totals sum exactly to `TOTAL ALL CLASSES`, in every unit and every column, and
`validate.py` checks it.

The class and sub-class columns in the CSV are the classification's own
structure (four classes, twelve sub-classes) attached to each order; Part II (a)
prints no class or sub-class subtotals of its own, so those levels are obtained
by summing orders.

### Table XXI: what is and is not here

There is no "Part III — details for principal towns". Haifa town is a section of
**Part II**, and it is not one table but ten half-page blocks: five community
blocks (all religions, Moslems, Jews, Christians, Others) printed twice over, on
pp. 588–590 for columns 2–26 and again on pp. 591–593 for columns 27–59. Page 588
and page 591 each carry the all-religions block alone; the other four pages carry
two stacked blocks apiece. `census-1931-industry-haifa-town.csv` holds all of it.

The table counts **persons engaged**, not establishments — it has no
establishments column. "Organized industry" here means those who returned
themselves as in salaried employment or in receipt of wages, so the numbers are
much smaller than the occupational totals in Table XVI (1,881 persons against
Haifa town's 50,403 inhabitants).

The other units of Table XXI's Part II — the districts and the other principal
towns — remain untranscribed in the scans, as does its Part I (the Palestine-wide
summary, pp. 546–551).

## Transcription notes

- Zero (`0`) stands for the census's "…" (nil).
- The scans carry occasional broken type. Where a printed digit was ambiguous or
  wrong, the value entered is the one **forced by the table's own marginal sums**
  (each cell is constrained by row total, column total, persons=males+females, and
  for Haifa SD by the all-religions panel). Cells resolved this way:
  Ramle SD Moslems 57,887; Ramle rural Moslems 39,674; Beisan rural Moslems 9,973;
  Nazareth town Moslems 3,226; SD age 0-1 all-religions 3,192; SD others 30-35
  married 171 / divorced 3; town Christians 75+ widowed 116; 1922 Gaza urban
  17,480; 1922 Nazareth rural 15,257; 1922 Nazareth urban Christian males 2,321;
  1922 Beisan rural females 4,110; 1922 Tiberias rural Jews 1,812; 1922 Beersheba
  rural females 34,913 (persons − males; printed digit unclear).
- Further cells resolved the same way in the session-2 tables: Table VIII —
  Southern jews 15-20 (6,252), Ramle moslems 30-35 (3,888), Hebron moslems 20-25
  (4,065), Bethlehem all 65-70/75+ (368/508), Jerusalem SD jews 10-15 (4,909),
  Nazareth jews 20-25/60-65/65-70 (384/55/37), Beisan christians 20-25 (62),
  Tiberias jews 20-25 (818), Acre all 25-30 (4,210), Safad jews 45-50 (126),
  christians 15-20 (96), others 35-40 (30), Northern moslems 35-40 (20,383),
  Jaffa christians 15-20/20-25 (832/1,188 — the printed 831/1,189 sum identically
  in-column, but the district column and the religion identity pin the former);
  Table IX(A) — Jerusalem town christians illiterate total (6,733/2,638);
  Table XV — Tulkarm cases/deaf (1,558/72), Beisan cases/blind-one-eye (267/153),
  Beersheba totally-blind m/f (26/21), Bethlehem/Jerusalem-SD several cells via
  the religion identity (see validate.py).
- **Source-level inconsistencies kept as printed** (each printed panel's own row
  and column sums are exact, but panels of the source contradict each other by
  1–5 persons; verified at 4× zoom where legibility allowed): Table VIII —
  Hebron 40-45 & 65-70 (religions vs all, ±1 m/f, cancelling in-column);
  Northern District 50-55/55-60/60-65 (±1); the printed Northern District panel
  vs the sum of its nine printed sub-district panels at 30-35/35-40 (5 males
  shifted between the two age groups, "others" and hence "all") and at
  65-70/70-75 (±1 in moslems and jews); printed Palestine Part I vs the sum of
  the three district panels at 40-45–65-70 (±1 in several columns). The
  tolerated cells are listed in `SDA_EXC` in validate.py. Similarly Table IX(A):
  the printed Jerusalem-district towns total shifts 10 persons (f) between ages
  0-7 and 21+ relative to the printed town rows, and Jaffa's all-religions row
  exceeds its religion panels by 2 literate persons; Table XV's tiny "from
  birth" sub-columns carry ±1–3 inconsistencies between Parts I/II/III (their
  cross-aggregation checks are relaxed in validate.py).
- 1945 Ijzim: Moslems printed garbled ("28,30"); 2,830 restored from the row total.
- 1945 Karkur: footnote components sum to 2,180, not the printed 2,380; the cell
  keeps the printed 2,380.
- 1945 Acre sheet: the reprint's `3` and `8` are near-identical at this scan
  resolution. El Birwa's Christians print ambiguously; 130 is forced both by the
  row total (1,330 + 130 = 1,460) and by the Christians column total, which
  lands exactly on the printed 11,150 only with 130. All five columns of the
  sheet sum to their printed totals with no other cell in doubt.
- 1945 Acre sheet, blank vs nil: serials 53, 54, 56 and 57 ('Arab el Hujeirat,
  el Mureisat, es Sawa'id, es Suweitat) print **no figures at all** — they are
  tribal units enumerated inside Sakhnin, Deir Hanna, Er Rama or Tarshiha. Their
  numeric cells are left empty and are excluded from the sums, unlike the
  all-nil rows (Acre Rural, Khirbat Jiddin) which print the nil sign and count
  as zeros.
- 1945 Acre serials 6, 7, 14, 15, 32 and 47 brace two to four separately
  counted settlements under one serial; each is its own CSV row, repeating the
  serial, exactly as done for Haifa's serials 16 and 22.
- Table XVI Part II (a), cells resolved by the table's own margins: Order 9
  (Metals) Ramle total 596 (the last digit is clipped by the column rule; the row
  identity and the Southern District column both give 596); Order 15 (Building
  industries) Jenin dependants 268 (printed 266 — the row identity, 386 = 115 +
  3 + …, and the printed Northern District dependants total, 7,909, each force
  268); Order 22 (Transport by road) Haifa town total 3,618 (printed as an inky
  "8,618"); Order 26 (Brokerage) Southern District total 2,354 (printed 2,345 —
  legible at high magnification, so a typesetting transposition rather than a
  broken glyph; the row identity, the four sub-district rows and the Palestine
  row all give 2,354).
- Table XVI Order 2 (a), Nomads, is printed nil throughout Part II (a), which
  covers the settled population only. It is kept as a row of zeros so that the
  order list matches the printed classification.
- Table XXI, Haifa town: the scan's `3` and `8` are near-identical in this face.
  Industry II (salt and bitumen), persons engaged, is read as 3 rather than 8 in
  both the all-religions and the Jews block, which is what the block totals
  (1,881 and 822) and the male/female split require. Column 18 (supervising and
  technical staff, females) falls on a crop boundary; its three non-nil entries
  are fixed exactly by column 16 minus column 17 row by row, and by columns
  20/22/24/26.
- Nomadic population (all Moslem) is included in the 1931 sub-district totals; the
  Haifa sub-district had none, so its total = settled.
- 'Atlit appears in the 1945 sheet (90 M / 510 J / 60 C); the Atlit clearance-camp
  register (notebook 25) remains excluded from hospital statistics as decided.

## Not transcribed (available in the scans)

Volume II also holds language (X), birthplace (XI), residence (XII),
citizenship (XIII), years-at-school (IX B), Table VIII Part III–IV (per-town age
tables other than Haifa) and Part V (nomads), and the civil-condition columns of
the non-Haifa age tables. Of the occupation tables, Table XVI Part II (a) is here
at order level and Table XXI's Haifa town section in full; still in the scans are
Table XVI's individual occupation-group columns, its Part I summaries and Part
II (b) (nomads), Table XVII (occupations of working dependants), Tables XVIII–XX,
and Table XXI for every unit other than Haifa town. The 1945 sheets for the
sub-districts beyond Haifa and Acre (Nazareth, Tiberias, Beisan, Safad, Jenin,
Tulkarm, …) are JPGs on the ANU page and remain untranscribed; `validate.py`'s
`vs1945_villages()` takes a sub-district name, so each new sheet is checked by
adding one call. `TODO.md` holds the remaining hand-off brief (occupations
Haifa).
