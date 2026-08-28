# The two buildings — ISA file index (shallow, index only)

Everything at the ISA to do with the *fabric* of the hospital(s): site, construction, plant,
equipment, maintenance. **Listed so it can be found and cited, not processed.** Files about the
hospital's *work* are at the bottom — those are the ones worth reading.

PDFs in `paper/sources/isa/<sig>.pdf` (gitignored). Fetch more with `pipeline/isa_fetch.py <sig>`;
search with `pipeline/isa_harvest.py "<query>"`. Readings: `isa_readings.md`.

## Building one — the old hospital (pre-Oct 1938)
| Sig | Period | pp | |
|---|---|---|---|
| 0010qhu | 1920–36 | 174 | Water supply, **"Old Haifa Hospital & Main Disinfecting Station"** — the title is the finding: one establishment |
| 00079mb | 1925–31 | 167 | New Isolation [Fever] Hospital site selection; notes an **Infectious Diseases Annex at the *Municipal* Hospital, 1927** |
| 0010b40 | 1928–29 | — | British community admissions returns, Haifa District *(not fetched)* |

Already read: **000nxlg** (1928 deferral), **000b33x** (1927–34 expropriation, £P.277.5/dunum).

## Building two — Bat Galim
| Sig | Period | pp | |
|---|---|---|---|
| 000b0ms | 1935–37 | 66 | Site file; cadastral plans 1/2500; owners Edgar Clark, heirs of Fuda Said |
| 000a17l | 1935 | 2 | Map: site proposed for Haifa Hospital |
| **000ucac** | 1937 | 2 | **Map "New Govt. Hospital Site & Suggested Adjacent Roads", 1:2500**, H. Kendall, Town Planning Adviser → `figures/map_hospital_site_1937.png` — the *before* image |
| **000w8jb** | 1941 | 2 | **Map "Government Hospital & Environs", 1:1250** → `figures/map_govhosp_environs_1941.png` — the *after* image |
| 000rkrh | 1936 | | Plan of the Hadassah Hospital of the Jewish community, Haifa — comparator |
| 000nqjr | 1937–47 | 204 | Land allocation near the hospital; 4 oversized plan sheets |
| 000txa0 | 1937 | 147 | Construction contracts (lifts £P.2124; kitchen/laundry/autoclaves, Herouth Ltd) |
| 000txa1 | 1937–44 | 114 | Construction finance, steel/concrete checking |
| **0005xx0** | 1935–43 | **1569** | **READ IN FULL → `isa_0005xx0_reading.md`.** Bundle of PWD HQ vols (File No.1 1935–37, No.8 1937–39, Vol.3 1939–42, Vol.5). Holds the **ward schedule**, the **277-bed design**, the **St Luke's lease**, the **Sept/Oct/Dec 1938 handover dates**, the **1942 Plague Unit**, Solel Boneh + the 50/50 labour petition, Mendelsohn's copyright claim |
| 000tdmy | 1937–38 | 44 | Expansion Stage I |
| 000i37x | 1946 | 11 | New Government Hospital, Haifa |
| 000zxqo / 000z003 / 0010b7k / 0010b7m | 1935–46 | 599/153/19/32 | Equipment & supplies; X-ray clinic and dispensary stores |
| 000v2kc | 1945–48 | 29 | Lift maintenance to the end of the Mandate |
| 00061il | 1942–47 | 179 | Haifa District buildings & services |
| 000uhxk | 1945–48 | 37 | Additional hospital accommodation |
| 000zxji, 0002k6y, 000zxwt, 0002iye, 0010qf0, 0002k6i, 000zbrf | 1930–40 | | Boards of Survey (stores write-offs) |
| 0010qi1 | 1939 | — | Water supply payments *(not fetched)* |

---

## The ward question — ANSWERED (2026-08-28)

**The ward list was found — as text, not as a plan.** `0005xx0` holds the **1935 bed
allocation by section** (ISA pp. 323–331: 189 general + 88 fever = **277 beds designed**) and
the **1936 "Schedule of Accommodation"** (ISA pp. 276–289), an 8-page room-by-room list
lettered A–V naming every ward block, section, theatre, store and staff quarter. Full
transcription in **`isa_0005xx0_reading.md` §1**. Register ward names can now be matched to
designed units.

**Still missing: the key plan.** No ward-labelled *plan* is in any ISA file yet, and sweeps
across all 1,569 pages of `0005xx0` for "key plan"/"block plan"/"floor plan" return nothing.
The pavilions are lettered A–F throughout the correspondence but no page says what any
pavilion was *used for*. The drawing set is catalogued and its index survives:

`0005xx0` p.1223 = **PWD Drawing E/524, 18.3.1941, "Government Hospital Haifa — Schedule of
Received Record Drawings"** → `figures/drawings_schedule_E524_1941.png`. It lists ~65 as-built
drawings (E/R 224–286) and so describes the building:

- **Six storeys** — Basement, Ground, First, Second, Third, Fourth, Fifth
- **Pavilions A, B, C, D, E, F**, each with its own drawing
- **Block 9** — garage/workshop below, **Attendants' Quarters** above
- Basement air-conditioning room, gatekeeper, power plant, intercommunication telephone,
  light-signals system, battery for clocks & bells
- Numbered units 1–24 spread across the floors (e.g. "7 First Floor", "17 Fifth Floor") —
  almost certainly the ward/department units
- **E/R 286 = "KEY PLAN"** — the sheet that would name them

So: **a six-storey block plus six pavilions plus a service block.** Usable as a description of
the building now, and comparable against the ward names in the registers.

**Searched since:** the ISA `מפה-` map series has now been swept ("תכנית בית חולים" 167 hits,
"מפה בת גלים" 15) — it yields only **site/environs** plans, no ward or floor plans.

**Where the plans themselves may be:** the
oversized sheets already downloaded in `000nqjr` (pp. 102/103/115/162) and `000b0ms`, so far
only thumbnailed; or the PWD drawing set itself, which the schedule says was forwarded to the
Department's Haifa office — the schedule gives exact drawing numbers to request.

---

## Process these instead — about the hospital's work
| Sig | Period | pp | Why |
|---|---|---|---|
| **000i5yq** | 1921–28 | 393 | Infectious Diseases Record Book, ~7,200 named cases w/ address, occupation, religion, physician, outcome |
| **000zbri** | 1942–44 | 388 | Daily returns + nominal case reports; **"Where Treated" = "Govt. Hosp." / "Isolation Haifa"** |
| **000v2ig** | 1941–47 | 282 | DMS annual "Review of Progress" — bed-strength, Haifa staff appointments, epidemics |
| 000z003 | 1935–38 | 153 | Furnishing tenders quantified per ward/block, incl. the Infectious Diseases block |
| 000txlb | 1938 | 38 | Eric Gill's carving contract — how the institution presented itself |
| 000b7vc | 1930–47 | 545 | VD policy to the S.M.O. Haifa; spans the registers exactly |
| 00061il | 1942–47 | 179 | Holds a 1934 Carmelite Convent→hospital discussion in explicit ward language |
