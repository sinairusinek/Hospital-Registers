# ISA 000zbri — the named infectious cases, 1942–44, and what the register can see of them

**File:** ISA `000zbri`, "Monthly Returns – Infectious Diseases, Haifa", Jan 1942 – Oct 1944,
388 pp, image-only, scanned sideways, file mark 1533/N. Structure already established in
[`isa_readings.md`](isa_readings.md) (`## 000zbri`); this document reports the full extraction
and the attempted case-by-case linkage to the admission register.

**Outputs** (all gitignored, under `data/private/` because they carry personal names):

| file | what it is |
|---|---|
| `isa-1942-44-cases.tsv` | 2,171 named cases, one row per person, every column of the form |
| `isa-1942-44-pages.tsv` | one row per page: what kind of page it is, its date, its serial no. |
| `isa-1942-44-candidates.tsv` | one row per candidate pairing with the register |
| `isa-1942-44-linkage-summary.txt` | the counts below, regenerable |

**Code:** `pipeline/isa_returns.py` (stage 1, extraction), `pipeline/isa_returns_link.py`
(stage 2, linkage). Both are resumable and both record their own reasoning in their docstrings.

---

## 1. What the file is made of

All 388 pages were read, none failed.

| page kind | pages |
|---|---|
| `nominal` — REPORT ON CASES AND DEATHS, the named list | **180** |
| `daily` — DAILY RETURN OF INFECTIOUS DISEASES, the tally, no names | 178 |
| `blank` | 16 |
| `other` — letters, covers, monthly summaries | 14 |

The near-perfect 180/178 split confirms the pairing described in the earlier survey: each
nominal list is the verso of its daily return. The 180 nominal pages hold **2,171 named cases**.

**The file's own form changed during the period, and it matters.** The later (1944, typed)
form has twelve columns ending *Where Treated | When Inoculated | Date of Onset | Remarks*.
The earlier (1942–43, mostly handwritten) form has **thirteen**: it inserts an **Admitted to
Hospital** column after Date of Onset, and its last column is the wider *"Bacteriological
Examination Results. Disposal of Case and Precautions taken. In the case of deaths give
reference to original report."* Both layouts are captured; `admitted_to_h` is populated only
for the earlier form. Reading the thirteen-column form against the twelve-column header shifts
every field by one, which was the main failure mode during development.

Cases by year of onset: **1941: 18 · 1942: 822 · 1943: 948 · 1944: 332.** The file thins
towards its own front because it stops in October 1944.

---

## 2. Where the notified were treated — the headline figure

This is the column the whole exercise was for. Over all 2,171 named cases, as written:

| where treated | cases | share |
|---|---|---|
| Government Hospital / Isolation | **1,566** | **72%** |
| at home | **493** | **23%** |
| elsewhere or not recorded | 112 | 5% |

So **roughly one notified infectious case in four was never sent to a hospital at all**, and is
invisible to our register by construction — not missed by it, but outside what it records.
That is the number the prompt asked for, and it is a property of the notification system, not
of our transcription.

The "elsewhere" residue is itself informative. It names other institutions and villages where
cases were kept: **Hadassah** (43 + 15 + 5 + 1 spelling variants = 64), **Tireh/Tira** (20),
**Balad esh-Sheikh** (8), **Kiryat Amal** (6), **St. Luke's** (1), **Nazareth** (1),
**Damun, Birqin, Zib, Hishis** (1 each). The Government Hospital was one destination among
several, and the Jewish cases in particular had Hadassah as an alternative.

**Three cases were held at the "Quart. Lazaret Haifa"** — Mohd. Ali Ahmed Awad, Hamzeh Ahmed
Awad and Yassin Hassallah, all smallpox contacts of one Haj Awad Abdallah Tayeh, onset 22–24
January 1943 (ISA p.254). This is a dated, named, first-person attestation that the Haifa
quarantine lazaret was in operational use in early 1943, distinct from the hospital's own
isolation section, which bears directly on the open question in memory `project_haifa_lazaret`.

**184 cases are recorded as having died** — typhoid 69, measles 42, typhus 37, diphtheria 8,
plague 6, smallpox 6, hydrophobia 4, pneumonia 4.

---

## 3. The linkage — and the constraint the prompt did not know about

**The register does not cover most of this file.** The digitised registers run
1930–1940, **1944**, 1946–1948. There are **no 1942 or 1943 admissions at all**, and 1944 runs
only from roughly March to November (notebooks 27, 28, 29; 2,968 admissions, 495 of them with
a recognised infectious diagnosis).

The ISA returns run Jan 1942 – Oct 1944. The two sources therefore overlap for **1944 only**,
which is 332 of the 2,171 named cases. Everything earlier is reported as
*OUT OF REGISTER WINDOW* — **not** as evidence that a patient was not admitted. Confusing
those two would be the easiest way to produce a false finding from this material.

Of the 2,171 named cases:

| | cases |
|---|---|
| named cases extracted | 2,171 |
| outside the register's years (1942–43) | 1,790 |
| no usable date | 49 |
| in window, treated outside a hospital | 11 |
| **in window and marked hospital/isolation — the linkable set** | **321** |

### The matching rule, stated so it can be argued with

Names cannot be matched: the register's are image-redacted and unrecoverable. What is left is
demographic-and-date matching, so **nothing here is an identification**. A pairing is a
candidate only if *all* of:

* **sex** agrees exactly;
* **age** agrees within ±2 years;
* **religion** agrees, after mapping the returns' combined nationality-and-religion cell
  ("Palest. Mosl.", "Germ. Jew", "Palest Ch.") onto the register's Muslim / Christian / Jewish;
* **disease** agrees at the level of the disease family, through a synonym table
  (so "Murine Typhus" matches "Typhus", "P. Typhoid B" does not match "Typhoid");
* **date**: the admission falls between onset and onset+30 days — a notified case is admitted
  after onset, and typhoid's tail is long — or within ±3 days of the return's own
  admission date where the earlier form gives one.

**Uniqueness is required in both directions.** Counting only "this case has exactly one
candidate row" is not enough: two different named people cannot be the same admission. On a
first pass, seven register rows were each claimed by two or three cases all calling themselves
unique. Any register row claimed by more than one case now demotes every claimant to
CONTESTED.

### Result

| outcome | cases | |
|---|---|---|
| **UNIQUE** | **34** | one register admission fits, and no other named case claims it |
| CONTESTED | 16 | one candidate each, but two or more cases claim the same admission |
| AMBIGUOUS | 71 | several register admissions fit |
| NO MATCH | 200 | no register admission fits |

### The no-matches are mostly a coverage artefact, not a finding

Broken down by month against the register's own coverage, the pattern is unmistakable:

| month | register admissions | notified cases | UNIQUE | CONTESTED | AMBIG | NO MATCH |
|---|---|---|---|---|---|---|
| 1944-01 | **0** | 33 | 0 | 0 | 0 | **33** |
| 1944-02 | **1** | 54 | 1 | 4 | 9 | 40 |
| 1944-03 | 262 | 52 | 5 | 3 | 28 | 16 |
| 1944-04 | 416 | 39 | 7 | 0 | 18 | 14 |
| 1944-05 | 322 | 57 | 5 | 4 | 4 | 44 |
| 1944-06 | **3** | 33 | 1 | 0 | 0 | **32** |
| 1944-07 | 344 | 31 | 9 | 3 | 9 | 10 |
| 1944-08 | 581 | 21 | 6 | 2 | 3 | 10 |

Where the register is empty the match rate is zero; where it is well covered it is roughly
two-thirds. **Restricted to the months the register actually covers, 106 of 200 linkable
cases (53%) find at least one candidate.** The 200 NO MATCH figure over the whole window
should not be quoted on its own.

### The reverse direction

Of the register's 495 infectious admissions in 1944, **388 are never claimed by any ISA case**.
The largest unclaimed group is **malaria (127)** — which does not appear in these returns at
all, because it was handled under a separate malaria-control regime, not as a daily notifiable
return. The rest of the asymmetry is the same coverage problem read from the other side.

---

## 4. The best-evidenced pairings

Fourteen of the 34 UNIQUE pairings sit within three days of onset with every demographic field
agreeing. A selection, closest first:

| disease | name (ISA) | age | sex | religion | onset | register admission | outcome | notebook/page | gap |
|---|---|---|---|---|---|---|---|---|---|
| Erysipelas | Nada Elias | 65 | F | Palest Ch. | 16.V.44 | 1944-05-16 Erysipelas | Recovered | nb29/p102 | 0d |
| Typhoid | Jamileh Sim'an | 16 | F | Palest Ch. | 16.V.44 | 1944-05-16 Typhoid Fever | Recovered | nb29/p101 | 0d |
| Typhus | Yusef Saleh | 20 | M | Palest. Mosl | 13.V.44 | 1944-05-13 Typhus | Recovered | nb29/p95 | 0d |
| Typhus | Mohd 'Adas | 50 | M | Palest. Mosl | 3.4.44 | 1944-04-03 Typhus | **Died** | nb29/p32 | 0d |
| Murine typhus | Ahmad T. Jangi | 30 | M | Palest. Mosl. | 27.3.44 | 1944-03-28 Typhus | Recovered | nb29/p24 | 1d |
| **Plague** | Ibrahim As'ad Tusky | 11 | M | Palest. Moslem | 16.8.44 | 1944-08-17 Plague | Recovered | nb27/p79 | 1d |
| German Measles | John Thompson | 16 | M | British Ch. | 1.8.44 | 1944-08-03 German Measles | Recovered | nb27/p38 | 2d |
| **Plague** | Renee Hawa | 16 | F | Palest Ch. | 7.8.44 | 1944-08-09 Plague | Recovered | nb27/p48 | 2d |
| **Plague** | Misleh Awad | 22 | M | Palest. Moslem | 20.8.44 | 1944-08-22 Plague | Recovered | nb27/p72 | 2d |
| Scarlet fever | Yoel Disbekin | 14 | M | Palest Jew | 29.4.44 | 1944-05-01 Scarlet Fever | Recovered | nb29/p76 | 2d |
| **Plague** | Salim Taher Moh'd | 16 | M | Palest. Moslem | 21.8.44 | 1944-08-24 Plague | Recovered | nb27/p75 | 3d |

The **plague** rows are the strongest material in the file. The register holds ~34 plague
admissions in 1944; the returns name 23 plague cases; four pair one-to-one and two more are
contested only against each other. This is the 1944 plague episode already counted from the
press (`project_press_epidemic_leadlag`, `project_haifa_lazaret`) now traceable **person by
person** across two independent record systems.

**A household, incidentally.** Fruz Habhan (6, M) and Muyassar Habhan (10, F), both Palest.
Mosl., onset 4 and 3 May 1944, both pair to admissions on **1944-05-11 on the same register
page** (nb29/p92). Two children of one family notified together and admitted together on the
same day. The shared page is corroboration, not a collision.

**A caution about outcome.** Where both sources record a death they agree
(Mohd 'Adas, Abdallah Lublawi, Yusef Flan, Barbari Mohd. Hamad). But the returns' `remarks`
were written when the return was filed, often before the case resolved, so a blank there is
not evidence of survival. Compare outcomes only in the direction return-says-died →
register-says-died.

---

## 5. Corrections to the earlier survey

Reading the file in full corrected two things recorded from the initial sample:

1. **The smallpox case on p.25 is "Jacob Feigenson", not "Jacob Seigman"**, and his
   `Where Treated` reads **"Isol. H."**, not "Govt. Hosp." Verified against a 300 dpi crop.
2. The p.21 plague rows' religion cells read **"Palest. Moslem"** and **"Palest. Christian"**
   (with "Palest." carried down by ditto), not bare "Moslem" / "Christian". Same people, same
   reading, fuller cell.

---

## 6. What is still open

* **The 1942–43 half is extracted but unlinkable** until registers for those years are
  digitised — 1,790 named cases, already transcribed, waiting. If notebooks for 1942–43 exist,
  this file is a strong argument for prioritising them: the linkage machinery is built and the
  other side of the join is already in hand.
* ~~The daily returns were classified but not transcribed.~~ **Done — see §7 below.**
* **The `where_treated` vocabulary deserves a controlled reading.** "Isol.", "Isolation",
  "Isolation Haifa", "Govt. Hosp.", "G.H." are currently distinct strings pooled by regex.
  Whether "Isolation" always means the Government Hospital's isolation section, or sometimes
  the lazaret, is exactly the distinction `project_diphtheria_isolation_reconcile` is parked on.
  The three "Quart. Lazaret Haifa" cases show the clerks *could* name the lazaret separately
  when they meant it — which is weak evidence that bare "Isolation" means the hospital.

---

## 7. The daily returns transcribed, and what they do to §2 (added 2026-08-28)

All **178 daily-return rectos** have now been read as well (`pipeline/isa_daily.py`, output
`data/private/isa-1942-44-daily.tsv`, **840 tally rows**, no page failed). 30 of the 178 carry
a heading and a signature but an **empty grid** — a return was to be sent "only when a change
in the daily state has occurred", and multi-sheet returns exist (p.332 is headed "Sheet III"
and tallies nothing). An empty grid is a fact about the return, not a failed read.

The tallies are overwhelmingly **Haifa** (772 of 840 rows), with outlying places appearing by
name: Tireh 7, Balad esh-Sheikh 5, **Athlit 5**, Hawassa 4, Kiryat Amal 3, Hadera 3, Ein Ghazal,
Kfar Ata, Nesher 2 each.

### The check the daily returns were fetched for

They record deaths already split **In Hospital / Out of Hospital** by the clerks themselves —
an independent measurement of the division §2 derived from the nominal `where_treated` column.

| | in hospital | out of hospital |
|---|---|---|
| **deaths** (daily returns, n=196) | 145 (**74%**) | 51 (**26%**) |
| **cases** (nominal returns, n=2,171) | 1,566 (**72%**) | 493 at home (**23%**) |

The two land close, which is reassuring — but they are shares of *different things*, cases
versus deaths, and the small gap runs the **wrong way**. A referral hospital takes the sicker
patients, so deaths should be *more* hospital-concentrated than cases, not less.

**The whole anomaly is one disease.** Measles supplies **34 of the 51 out-of-hospital deaths
and none of the in-hospital ones**. Set measles aside and the picture inverts to what it should
be:

| excluding measles | deaths |
|---|---|
| died in hospital | 145 (**90%**) |
| died out of hospital | 17 (**10%**) |

The nominal returns say the same thing from the case side, and the contrast is stark:

| disease | named cases | in hospital | at home |
|---|---|---|---|
| **measles** | 451 | 33 | **384** |
| **typhoid** | 1,010 | **939** | 9 |

**So the headline "23% treated at home" is very largely a single disease.** Measles was nursed
at home and killed children there; typhoid was hospitalised almost without exception. The
figure should be quoted per disease, not as one rate — and the corrected reading of §2 is that
the Government Hospital captured nearly all of the *serious* notified infectious disease in
Haifa, while measles was managed almost entirely outside it. That is a sharper and more useful
statement than the aggregate, and it is the check paying for itself.

### Disease series, 1942–44

New cases and deaths as tallied on the returns (top of the list; spelling variants pooled
by family, the clerks' own variants — "chikin pox", "diphteria", "w. cough" — left visible
in the TSV):

| disease | new cases | died in hosp. | died out |
|---|---|---|---|
| typhoid | 1,018 | 98 | 5 |
| measles | 440 | 0 | **62** |
| typhus | 254 | 33 | 3 |
| diphtheria | 62 | 10 | 0 |
| smallpox | 61 | 18 | 0 |
| erysipelas | 37 | 1 | 0 |
| chickenpox | 31 | 2 | 0 |
| meningitis | 25 | 3 | 1 |
| scarlet fever | 25 | 0 | 0 |
| undulant fever | 24 | 0 | 0 |
| **plague** | 23 | 7 | 2 |
| hydrophobia | 4 | 4 | 0 |

`Existing` and `Remaining` are **stocks, not flows**, and must never be summed across returns;
only `New Cases` accumulates. Hydrophobia is worth noting: four cases, four deaths, all in
hospital.

### How complete the series is

Serial numbers are an annual counter, so gaps are countable. **1942 is complete** (serials
2–45, no gaps). **1943 is not**: 54 returns present out of serials 1–112, so **58 are missing**
from the file. **1944** has 33 of 45, missing serials 7, 10, 11, 13, 18, 26, 29–32, 36, 39.
The 1943 gap is large enough that 1943 rates must not be treated as a complete series.

### Caveats carried forward

* A **dash means zero and a blank means not stated**; both are preserved as written in the TSV
  and neither is silently converted.
* Figures were sometimes struck through and corrected by a later hand (p.341: Remaining "92"
  corrected to "96" in pink). The final value is taken and the correction recorded in
  `uncertain`.
* The daily and nominal counts of death rest on different bases — a running daily state versus
  a case note written when the return was filed — so the 260 tallied deaths and the 184 named
  cases remarked "died" are not expected to agree, and do not.
