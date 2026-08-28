# Three prompts for separate sessions

Each is self-contained: paste one into a fresh session started in the repo root
(`/Users/sinairusinek/Documents/GitHub/Hospital-Registers`). They are independent and can be
run in any order or in parallel — none writes to the same output as another.

Shared background all three assume:
- ISA files are already downloaded to `paper/sources/isa/<signature>.pdf` (gitignored).
- `pipeline/isa_fetch.py <sig>` fetches more; `pipeline/isa_harvest.py "<query>"` searches ISA.
- Readings so far: `data/archives/isa_readings.md`; shallow building index:
  `data/archives/isa_buildings_index.md`.

---

## PROMPT A — Job 2: are the missing DoH annual report tables in the file?

```
In this repo, ISA file 000v2ig (paper/sources/isa/000v2ig.pdf, 282 pages) is the Chief
Secretary's correspondence file "Annual Reports - Department of Health", 1941-1947. It turned
out to contain the PRINTED Department of Health annual reports themselves, not just letters
about them, including their statistical appendices.

From those appendices I have already transcribed Table (a) "GOVERNMENT AND MUNICIPAL
HOSPITALS" for three years. Haifa's row:

  1940 (ISA p.248-249): beds General 88, Isolation 76, British 30, Maternity 26;
       admissions 4,696 = Moslems 2,185 / Christians 1,319 / Jews 913 / Others 79;
       deaths 219, discharges 4,483, daily avg beds occupied 171.0, occupied at year end 153.
  1941 (ISA p.223): beds 94 / 98 / 28 / 17; admissions 4,931 = 2,483 / 1,400 / 970 / 91;
       deaths 212, discharges 4,780, daily avg 176.5, at year end 172.
  1944 (ISA p.95-98): beds 117 / 98 / 28 / 18; admissions 6,337 = 3,680 / 1,846 / 704.

YOUR TASK: establish whether Table (a) exists in this file for 1942, 1943, 1945, 1946 and
1947, and if so transcribe Haifa's row for each, in the same columns.

What I already know about the file, so you don't repeat it:
- Pages ALREADY CHECKED: 83 and 183 are narrative "Medical Services / Hospitals" sections
  (they discuss bed strength in prose, they are NOT the table). 95, 96, 97, 98, 223, 248, 249
  are the tables listed above. Pages 128, 160, 204 were flagged by a keyword sweep but did not
  resolve on inspection - probably narrative too, but unconfirmed.
- So roughly 200 pages have never been examined at readable resolution.
- The file is NOT in year order and reports were enclosed with some despatches and not others,
  so the missing years may simply not be present. A well-evidenced "they are not here" is a
  perfectly good answer - say so plainly rather than straining to find something.

Method that worked:
- Render with `pdftoppm -r 300 -png -f <p> -l <p> paper/sources/isa/000v2ig.pdf <out>`.
- Pages are scanned SIDEWAYS: rotate -90 (some are 180). Check orientation before reading.
- The table is wider than one screen. Crop it in two: the left band carries the hospital NAMES
  and the "Nominal Bed-Strength" columns (General / Isolation / British / Maternity); the right
  band carries Admissions (Moslems / Christians / Jews / Others / Total), Deaths, Discharges,
  Daily average beds occupied, and beds occupied at end of year. Haifa is the 3rd data row,
  after Jerusalem and Beit Safafa.
- For a fast sweep, render many pages at low resolution (90-120 dpi) and tile them into contact
  sheets, then go back at 300-400 dpi only for pages that look like tables. Tesseract is
  installed and helps locate candidates by keyword ("GOVERNMENT AND MUNICIPAL", "Bed-Strength")
  but is NOT reliable enough to transcribe from - read the rendered image yourself.

Append your findings to data/archives/isa_readings.md under a clear heading, extending the
existing Haifa table. Record explicitly which pages you examined and which years you could NOT
find, so the next person doesn't repeat the sweep. Do not overstate: if a figure is uncertain,
say which digit and why.
```

---

## PROMPT B — Substantial task 1: read 0005xx0, the New Government Hospital file

```
In this repo, ISA file 0005xx0 (paper/sources/isa/0005xx0.pdf) is "Public Health - New
Government Hospital, Haifa", 1935-1943, 1,569 pages, 73 MB. It is the largest unread thing in
the ISA corpus I have gathered and is expected to be the richest single source on the Bat Galim
hospital building. It has only ever been sampled - about nine pages.

Context: the Haifa Government Hospital moved from an older building to a new one at Bat Galim
in October 1938. The registers I work on (29,880 admissions, 1930-1948) span both buildings.

YOUR TASK: read this file and produce a structured account of what it contains, with the
substantive findings transcribed.

What sampling already established, so you can skip re-deriving it:
- It is a BUNDLE of several Public Works Department Headquarters files, not one file. Covers
  seen: "New Government Hospital - Haifa, P.W.D. Headquarters, File No. 8" (opened 6 July 1937,
  closed 14 Sept 1939) and "Vol. 3" (opened 15 Sept 1939, closed 3 Sept 1942), ISA ref 4089/1.
- Content sampled so far is works administration: architect's fees and the R.I.B.A. scale,
  P.W.D. vs contractor liability for maintenance, lift maintenance, electrical wiring, water
  supply, and 1939 water consumption figures.
- Page 1223 is PWD Drawing E/524, 18.3.1941, "Government Hospital Haifa - Schedule of Received
  Record Drawings", already read and transcribed in data/archives/isa_readings.md. It lists
  ~65 as-built drawings and tells us the building was six storeys (Basement to Fifth), plus
  Pavilions A-F, plus Block 9 (garage/workshop below, Attendants' Quarters above), with numbered
  units 1-24 across the floors and a KEY PLAN as drawing E/R 286.
- Oversized sheets (likely drawings or large tables) are at pages 2, 407, 408, 773, 1223, 1224.
  407, 773 and 1224 have been checked and are file covers or blank versos. Pages 2 and 408 have
  NOT been checked.

WHAT I MOST WANT, in priority order:
1. Anything that names or lays out the WARDS - a key plan, a room schedule, a floor-by-floor
   list, a bed allocation, a furnishing schedule quantified per ward. The registers record ward
   names and I cannot currently map them to the building. This is the single most valuable
   thing the file could contain.
2. Bed numbers, and any statement of the hospital's capacity as designed vs as built.
3. The opening: when the building was handed over, occupied, and formally opened; who attended;
   any ceremony. (A press chronology puts the move at October 1938 and a ceremony in December.)
4. Named people - architect, engineers, contractors, medical officers, matrons - and named firms.
5. Anything about the OLD hospital: what happened to it, when it was vacated, where it was.
6. Costs, and any dispute about them.

Method:
- 1,569 pages is too many to read one by one. Render at low resolution (90-120 dpi) in batches,
  tile into contact sheets of 12-24 pages, and triage: most of it will be routine warrants,
  vouchers and covering letters that need only a one-line note. Go back at 250-400 dpi for
  anything substantive.
- Find drawings and large tables by page dimensions - they are on oversized sheets. A script for
  this is described in data/archives/isa_readings.md.
- Pages may be rotated 90 or 180 degrees; check before reading.
- Tesseract is installed and useful for locating candidate pages by keyword, but not reliable
  enough to transcribe from.

Write your account to a NEW file, data/archives/isa_0005xx0_reading.md, and add a short pointer
to it at the end of data/archives/isa_readings.md. Structure it by what the file contains, not
by page order. Transcribe substantive documents properly - date, sender, recipient, reference,
and the passage that matters - rather than paraphrasing. Separate what the document says from
what you infer from it. If a section is routine, say so in one line and move on; do not pad.
```

---

## PROMPT C — Substantial task 3: link the 1942-44 named cases to the register

```
In this repo I have two sources for Haifa in 1942-44 that should be linkable case by case.

SOURCE 1 - the register (already digitised):
  data/public/hospital-registers-normalized.tsv, 29,880 admissions to the Haifa Government
  Hospital 1930-1948, one row per admission. Relevant columns include: Admission Date,
  Discharge Date, Age, Sex, Religion, Nationality, Occupation, Address, City, Ward,
  Diagnosis as written, Diagnosis as standardized, ICD-9 Code, Result as written, Result,
  Notebook_Number, Page_Number. PATIENT NAMES ARE REDACTED in this dataset and are not
  recoverable - the scans are image-redacted.

SOURCE 2 - ISA 000zbri (paper/sources/isa/000zbri.pdf, 388 pages, image-only, no text layer):
  "Monthly Returns - Infectious Diseases, Haifa", January 1942 - October 1944, from the Mandate
  Department of Health. It is built of repeating PAIRS:
    (a) a printed "DAILY RETURN OF INFECTIOUS DISEASES" - District, Date, Serial No., and
        columns Town or Village | Disease | Existing | New cases | Cured | DIED (In Hospital /
        Out of Hospital) | Remaining;
    (b) its verso, "REPORT ON CASES AND DEATHS" - a NOMINAL list, columns: Disease | Case
        Reference | Name | Age | Sex | Nationality and Religion | Period of Residence in
        Palestine | Source of Infection | WHERE TREATED | When Inoculated or Vaccinated | Date
        of Onset of Disease | Remarks.
  The file runs BACKWARDS in time - late 1944 at the front, 1942 at the back.
  Diseases seen: typhoid, paratyphoid, bubonic plague, smallpox, murine typhus, undulant fever,
  erysipelas, dysentery, measles, scarlet fever, C.S.M., anthrax, poliomyelitis, whooping cough.
  A large typhoid epidemic sits at the back of the file, around June 1942.

THE KEY COLUMN is "Where Treated". Its values include "Govt. Hosp." and "Isolation Haifa" as
well as home treatment. Worked example already transcribed (ISA p.21, verso of the 9.8.44
return): three plague cases, Eliahu Zamir 45 M Palest. Jew, Mohamed Hassan Khaled 40 M Moslem,
Anis Nseir 34 M Christian, all "Isolation Haifa", with "B. Pestis +" and one death. And ISA
p.25: a smallpox case, Jacob Seigman 30 M Palest. Jew, treated "Govt. Hosp.".

YOUR TASK, in two stages:

STAGE 1 - extract. Transcribe every nominal "Report on Cases and Deaths" in the file to a TSV,
one row per named case, keeping every column above plus the ISA page number and the date of the
return it backs. Write it to data/private/isa-1942-44-cases.tsv. NOTE: this output carries
personal names, so it goes in data/private/, NOT data/public/ - the ISA published this file
openly but that is a separate decision from us republishing it.
  There is a working precedent for this kind of extraction in pipeline/second_look.py (Gemini,
  GOOGLE_API_KEY is set in the environment, temperature 0, response schema, resumable per page).
  Two traps learned the hard way on a sibling file: pages are scanned SIDEWAYS and need
  rotating; and if you split a page image to get more pixels, CHECK PER-COLUMN FILL RATES, not
  row counts - a mis-registered split returns every row with half the columns silently empty.

STAGE 2 - link. For cases marked "Govt. Hosp." or "Isolation Haifa", attempt a match against
the register on the fields both sources share: date (onset/return date vs Admission Date),
age, sex, religion, and diagnosis. Names cannot be matched - the register's are redacted - so
this is fuzzy demographic-and-date matching, and you should treat it as generating CANDIDATES,
not identifications.
  Report: how many named cases the returns hold; how many are marked as treated at the
  Government Hospital or Isolation; how many find a plausible register match; and - the
  interesting number - how many infectious cases in Haifa were NOT sent to the hospital at all,
  which is the part of the epidemic our register can never see.
  Be conservative and state your matching rule explicitly. A small number of well-evidenced
  matches is worth more than a large number of loose ones. Where a match is ambiguous, say so.

Write your account to a NEW file, data/archives/isa_1942-44_linkage.md, with a pointer added at
the end of data/archives/isa_readings.md. Existing related work for context: memory notes
project_press_register_linkage (two exact press-to-register corroborations so far) and
project_diphtheria_isolation_reconcile (a parked disagreement about isolation-ward figures that
this file's Govt-Hosp/Isolation distinction may help settle).
```
