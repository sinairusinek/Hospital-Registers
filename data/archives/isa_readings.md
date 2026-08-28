# Israel State Archives — file readings

Source list: Google Sheet "תיקים נוספים - ארכיון המדינה" (owner eliezer.baumgarten@gmail.com),
id `1krOA22jhvskCgKNisuw3kuLC-1ZWjRmMpee8DZCkAdo`.

Files are fetched with `pipeline/isa_fetch.py` (drives the shared Chrome on port 9222;
ISA serves scans to a pdf.js iframe from a presigned S3 URL that 403s outside the
browser session, so the bytes are pulled from `PDFViewerApplication.pdfDocument.getData()`).

Deposit for the health files: **גופים מנדטוריים / מחלקת הבריאות - ממשלת ארץ ישראל**
(Mandate Department of Health fonds) — i.e. the ISA holds the DOH's own working
papers even though the DOH *printed annual reports* are not online.

---

## 000nxlg — Quarantine Lazaret & Infectious Hospital at Haifa, Aug 1928
**6 pp, typed + manuscript minutes, fully legible.** ISA phys. ref מ-29/4783;
Secretariat C.S. 1/101, P.10734/28. **Read in full.**

The single most useful thing here: it shows the **infectious-diseases block and the
quarantine lazaret were conceived as one adjoining project in 1928 — and were
deferred for cost**, a decade before Bat Galim.

### p.6 — Dept. of Lands to Chief Secretary, 1 Aug 1928 (ref G.507-5/967)
Signed **M. Doukhan, Acting Director of Lands**. Replying to Chief Secretary's
10734/28 of 28 June 1928. Subject: "Quarantine Lazaret and Infectious Hospital at Haifa."
- Neighbouring property valued by **Mr. M. Doukhan in August 1927 at £140–£160/dunum**.
- **District Commissioner, Northern District** concurs, but notes values tending to rise
  "in view of possible harbour development". £P.160/dunum judged fair.
- Acquisition costing, four plots:

| Plot | Area | Cost |
|---|---|---|
| 1 | 16 d. 453 sq m | £P.2640 |
| 2 | 2 d. 041 sq m | £P.330 |
| 3 | 1 d. 041 sq m | £P.170 |
| 4 | 0 d. 222 sq m | £P.35 |
| **total** | **19 d. 759 sq m** | **£P.3175** |

### p.4 — Secretariat minute, 9 Aug 1928
States "**two admitted needs**":
1. enlargement of the Haifa Quarantine Lazaret;
2. the building of an **Infectious Diseases Block at Haifa**.

"It is clearly advantageous that the Infectious Diseases Block should adjoin the Lazaret."
Land for both is available and **approved by a Siting Board**.
- Site purchase £P.3175; **Infectious Diseases Block estimated £P.4071.785 mils (£3970)**;
  total liability **£P.7246**. **No provision in the current Estimates.**
- Argues Government will not incur this "in the absence of very special reasons"; prices
  will rise "as the inception of harbour works at Haifa draws nearer".
- **Emergency fallback**: "If an emergency arises it could be met by the establishment of a
  **tented or hutted camp**" — either by expropriating a short lease of the site, or on the
  **Government reserve in the sand dunes further north**.
- Objection to the dunes: "**they are distant from the existing Lazaret and the Railway
  Station whereas proximity thereto is necessary for the purpose of quarantining of
  pilgrims or travellers from an infected country**." Moving the Lazaret "from its present
  suitable location" to the reserve would be "unwarranted".
- Recommends: "**Defer both projects for the present but allow provision to be inserted in
  1929 Estimates for consideration.**"
- Marginal note (initialled, 9/8): Director of Lands "states that £P.160 per dunum is a fair
  & reasonable price for this site."

### p.5 — further minutes
- Minute to Treasurer, 9.8.28: prudent to postpone; asks whether "**space for Quarantine
  Lazaret should be found on land reclaimed from the sea in the harbour scheme?**"
- **Treasurer to Chief Secretary, 13.9.28**: "**I cannot advise acquisition of land until the
  building project has been decided upon.**"

### Leads (not yet interpretations)
- There was an **existing Lazaret** at Haifa in 1928, near the Railway Station, in a location
  described as "present suitable location" — a *pre-1928* quarantine site to locate.
- Ties the lazaret's siting to **pilgrim/traveller quarantine**, not only to town epidemics.
- The 1928 deferral is the likely reason the infectious-diseases provision reappears later;
  connects forward to the 1942 plague department beside the hospital.
- Named officials to trace: **M. Doukhan** (Acting Director of Lands), **Col. Symes**
  (Chief Secretary's office routing).

---

## 000zbri — Monthly Returns, Infectious Diseases, Haifa, 1/1942–10/1944
**388 pp**, image-only (no text layer), scanned **sideways**; file mark **1533/N**, also 15/32.
Deposit: Mandate Dept of Health. Reading in progress.

Sample already read — p.4: **Senior Medical Officer, District Health Office Haifa, to
A/Director Medical Services, Jerusalem, 20 Oct 1944** (DOH Jerusalem stamp 23 OCT 1944,
No. 1203). Subject: "Haifa Monthly Infectious Diseases Return – **Plague Cases**. My Return
for the month of August, 1944." Amends the August 1944 return "for plague cases" with a
table broken down **by religion** (Christians / Moslems / Jews / Others) across
**Existing / New Cases / Cured / Died / Remaining**.
This is the same 1944 plague episode already counted from the press
(see memory `project_press_epidemic_leadlag`) — here in the health administration's own numbers.

### Structure of 000zbri (established by survey)
The file runs **backwards in time** (late 1944 at the front, 1942 at the back) and is built
of repeating **pairs**:
1. a printed form **"DAILY RETURN OF INFECTIOUS DISEASES"** — "To be sent to Headquarters
   Jerusalem and to the S.M.O. District", with District / Date / Serial No., and columns
   *Town or Village | Disease | Existing | New cases | Cured | DIED (In Hospital / Out of
   Hospital) | Remaining | Reference to report on back of form or to previous Serial No.*
   Sent only "when a change in the daily state has occurred since the last return".
2. its verso, **"REPORT ON CASES AND DEATHS"** — a **nominal** list, i.e. named individuals.

**The nominal reports are the register-linkable layer.** Their columns are:
*Disease | Case Reference | Name | Age | Sex | Nationality and Religion | Period of Residence
in Palestine | Source of Infection | Where Treated | When Inoculated or Vaccinated | Date of
Onset of Disease | Remarks.*

#### Worked example — p.21 (verso of the 9.8.44 return), plague
| Ref | Name | Age | Sex | Nat./Religion | Residence | Source | Where treated | Onset | Remarks |
|---|---|---|---|---|---|---|---|---|---|
| Rep.A.1 | Eliahu Zamir | 45y | M | Palest. Jew | 10 years | Local | **Isolation Haifa** | 9.8.44 | B. Pestis + **patient died** |
| A.2 | Mohamed Hassan Khaled | 40y | M | Moslem | Native | Local | " | 9.8.44 | B. Pestis + |
| A.3 | Anis Nseir | 34y | M | Christian | Native | Local | " | 6.8.44 | B. Pestis + |

Note "**Where Treated: Isolation Haifa**" — the isolation section named in the Palestine Post
material (memory `project_english_press_next`). Bacteriological confirmation ("B. Pestis +")
is recorded per case.

#### Worked example — p.6, daily return Haifa 30.8.44, Serial No. 45
(DOH Jerusalem stamp 31 AUG 1944; signature of M.O.)
| Disease | Existing | New | Cured | Remaining |
|---|---|---|---|---|
| Typhoid | 6 | 6 | 3 | 9 |
| **Plague (Bubonic)** | **10** | **1** | **2** | **9** |
| Smallpox | 1 | – | 1 | – |
| Undulant Fever | 1 | – | 1 | – |
| Murine Typhus | – | 1 | 1 | – |

Diseases seen across the file: typhoid, paratyphoid (A), **bubonic plague**, **smallpox**,
murine typhus, undulant fever, erysipelas, dysentery.

### Why this file matters for the registers
- It is a **daily, named, religion-coded** epidemic series for Haifa 1942–44 — the same
  population and years as the registers, from the health administration's side.
- It should let named plague/smallpox cases be **matched against admissions** (cf.
  `project_press_register_linkage`, where only two exact corroborations existed).
- The **smallpox** volume flagged in the source spreadsheet is visible in the returns.
- Correspondence in the file shows Jerusalem policing the data: one letter (p.7-8) instructs
  the S.M.O. that "**all cases of death should be stated as 'died' in the remarks column**"
  because a case had not been so noted, and that "epidemiological reports are demanded from
  the statistical returns" — a caution about how these numbers were produced.

---

## 000b0ms — Site of proposed new Government Hospital, Haifa, 1935–1937
**66 pp**, Dept of Lands & Surveys file **AC/8(5)**, ISA phys. ref גל-16647/12. Deposit:
Ministry of Construction & Housing / Israel Land Authority. **Surveyed; key items read.**

This is the land-acquisition file for the **Bat Galim** hospital — the second building of
the two in `project_hospital_two_buildings`.

- **Sketch plan 1/2500, dated 21.6.36**, "compiled from block plans by L.D. Surveyor":
  shows the hospital site as **parcels 3 and 5 (outlined red), lettered B, C, D, F**, in
  **Block 22**, with **Blocks 17, 20, 21, 87** around it. Landmarks drawn: **Carmelites
  Convent** immediately west of the site, the **Main Break Water** to the east, **Moslem
  Cemetery**, **German Cemetery**, **British War Cemetery**, and a Carmel station.
  This fixes the site "next to the monastery" precisely and ties it to the harbour works.
- **5 Oct 1937**, District Commissioner Northern District → Commissioner for Lands and
  Surveys, subject "New Hospital Site, Haifa": encloses a sketch plan, asks whether
  **Mr. Edgar Clark**, registered owner of **parcel No. 5**, is willing to sell.
- **Nov 1937 minute**: Mr Edgar Clark "is at present in Europe and is expected back about
  the middle of November 1937"; the District Commissioner will ascertain his willingness.
- **23 Sept 1937**, Registrar of Lands, Haifa → Commissioner for Lands & Surveys, subject
  "Urban Assessment Block 22": Block 22 Parcel 3 registered in the name of the heirs of the
  late **Fuda Said** under vol. 64 fol. 97; Block 22 parcel 5 registered to **Mr. Edgar
  Clark** under vol. 5 folio 30 & 81.
- Includes **Register of Deeds** extract sheets and a costing sheet ("Govt to Hotel …
  Plot A … Total").

### Leads
- Named private owners of the Bat Galim hospital land: **Edgar Clark** (parcel 5) and the
  **heirs of Fuda Said** (parcel 3) — worth tracing; the acquisition ran 1935–37, i.e.
  immediately before the 1938 move.
- The file is *Lands*, not *Health* — so building/ward detail is likely elsewhere; but the
  cadastral blocks give a hook for any address work.

---

## 000xxd6 — Infectious diseases & quarantine, Haifa District, 7/1948–8/1953
**89 pp**, Hebrew typescript (Israeli Ministry of Health era) + at least one statistical
table. Post-dates the registers; useful for aftermath/continuity only. Surveyed, not read.

---

## Fetch status (2026-08-27)
| Signature | Title | Status |
|---|---|---|
| 000zbri | Monthly Returns – Infectious Diseases, Haifa 1942–44 | **fetched, 388 pp** |
| 000nxlg | Quarantine Lazaret & Infectious Hospital, 8/1928 | **fetched, 6 pp, read in full** |
| 000b0ms | Site of proposed new Government Hospital 1935–37 | **fetched, 66 pp** |
| 000xxd6 | Infectious diseases, Haifa District 1948–53 | **fetched, 89 pp** |
| 000b7vc | Venereal diseases, Haifa 1930–47 | **fetched, 23 MB** (spreadsheet marks it not relevant) |
| 000b33x | Quarantine Lazareth Infectious Diseases Hospital 1927–34 | retry pending — page is "גלוי" (open) and *does* load a pdf.js frame, so this is a slow-load problem, not a restriction |
| 000i5yq | פנקס המחלות המדבקות, Haifa 1921–28 (nominal register) | retry pending |
| 000zbrf | Annual Board of Survey, District Health Office 1934 | retry pending (spreadsheet: not relevant) |
| 000ykkw | Haifa district infectious disease reports 1948–53 | spreadsheet says **closed to online access** |

---

## 000b33x — Quarantine Lazaret & Infectious Diseases Hospital, Haifa, 1927–1934
**197 pp**, Dept of Lands & Surveys file **AC/8(6)**, ISA phys. ref גל-16647/13.
(Slow to load in the viewer — needed ~10 min; it is NOT restricted.)

**This is the sequel to 000nxlg**: the 1928 project was deferred, then the land was taken by
**expropriation**, and the file is the resulting valuation dispute.

### Award of Committee (office copy, p.6) — the core document
"IN THE MATTER OF THE ASSESSMENT OF THE VALUE OF **TWO PLOTS OF LAND EXPROPRIATED BY THE
GOVERNMENT OF PALESTINE** FROM THE HEIRS OF **MUSTAFA AMER MIKHAIL TOUMA, RAJA RAIS** AND THE
ESTATE OF **ISKANDER KASSAB**, CLAIMING TO BE THE OWNERS OF THE SAID LAND."

Arbitrators: **MAURICE CHRISTMAS BENNETT** (Office of the Commissioner of Lands, Jerusalem),
**IBRAHIM SAHYOUN, Vice-Mayor of Haifa**, and **VICTOR KONN** of the **Palestine Jewish
Colonization Association (PJCA)**.

Chronology recited in the award:
- **16 Jan 1932** — the High Commissioner certified that occupation of two plots (**marked B2
  and C2** on the attached plan) by Government "was an undertaking of a **public nature within
  the meaning of the Expropriation Ordinance, 1926**"; the necessary proceedings, namely
  notices to treat, were taken.
- **15 July 1932** — Government offered **£P.160 per dunum**; refused by **Mr. John Asfour,
  Advocate of Haifa**, on behalf of the reputed owners. (Same £P.160/dunum figure the Director
  of Lands called "fair and reasonable" in 1928 — the owners had had four years to disagree.)
- The reputed owners demanded **£P.436 per dunum**; refused by Government.
- **27 Oct 1933** — Government and reputed owners subscribed to a submission to assessment.
- **Award: the land is assessed at £P.277.500 mils per dunum** — i.e. splitting the
  difference well above the Government's offer.

Also in the file: correspondence with **The Palestine Jewish Colonization Association**
(Director's letter, 15 March 1934, forwarding the original award signed by Mr Sahyoun to the
Attorney General); **Land Registry transaction-price schedules** ("Quarantine Lazaret – Haifa,
Land Registry Transaction Prices") listing comparable sales 1924–1933 with grantee names —
Palestine Salt Works Corporation, Vacuum Oil Company, Shell Oil, Consolidated Near East Co.,
Abdallah Shukalla & others, daughters of Abdul Bane Ahmad, Ismail Sabtoun, and others — with
areas in Turkish dunums, considerations, and price per sq. metre; plus a **cadastral plan**.

### Leads
- Names the actual dispossessed landowners of the lazaret/infectious-hospital site:
  **heirs of Mustafa Amer Mikhail Touma**, **Raja Rais**, **estate of Iskander Kassab**;
  their advocate **John Asfour**.
- **Ibrahim Sahyoun, Vice-Mayor of Haifa**, sat as arbitrator — a municipal figure worth
  tracing against the press corpus.
- The comparable-sales schedule is a small, dated **Haifa land-price dataset for 1924–33**
  around the port, incidentally useful for the harbour-development context.
- The expropriation ran under the **Expropriation Ordinance 1926**; certified by the High
  Commissioner **Jan 1932**; still unsettled in **1934**. So the infectious-diseases site was
  a live legal matter right up to the years the Bat Galim hospital was being planned.

---

## 000zbrf — Annual Board of Survey, District Health Office, Haifa, 5–6/1934
Fetched (915 KB). The source spreadsheet judges it "לא רלבנטי, דו״ח על מלאים" (not relevant,
a stores/inventory report). Not read in detail; keep as a stores/equipment source if the
hospital's material culture ever matters.

## 000ykkw — Haifa district infectious-disease reports, 1948–53
**Confirmed unavailable online.** The details page serves only a reCAPTCHA and no pdf.js
viewer — consistent with the spreadsheet's note "התיק עדיין סגור לגישה מקוונת".
Would need a reading-room visit or a digitisation request.

## 000b7vc — Venereal diseases, Haifa, 1930–47
Fetched (23 MB). Spreadsheet marks it not relevant; personal patient details were redacted by
ISA. Not surveyed. Note it *is* 1930–47, i.e. exactly the registers' span, so if the article
ever touches VD wards or the international VD-centres agreement it is already in hand.

---

## 000i5yq — פנקס המחלות המדבקות / INFECTIOUS DISEASES RECORD BOOK, Haifa, 12/1921–12/1928
**393 pp**, 60 MB, ISA phys. ref ג-1/9655. Deposit: Mandate Dept of Health.
A **bound ledger**, large landscape format, stamped by the **Principal Medical Officer,
Department of Health**. Printed headings are **trilingual — English / Arabic (سجل الأمراض
السارية) / Hebrew (פנקס המחלות המתדבקות)**. ~30 named cases per page ⇒ on the order of
**10,000 named infectious-disease cases** for Haifa, 1921–28.

**NOTE:** the source spreadsheet's note on this row ("1948-1953 דהוי מאד ולא קריא" — very
faded and unreadable) appears to have been **misplaced from another row**. At 250 dpi the
ledger is *highly legible*.

### Columns (left to right)
Serial No. | Monthly No. | **Date of receipt** | **Name of Patient** | **Address** |
**Occupation, and if a child, name of school** | Age | Sex | **Religion** | **Diagnosis** |
**Date of commencement of illness** | **Attending Physician** | **Date cured** | **Date died**

### Worked example — Page No. 4, entries 52–67, Feb–Mar 1922
| Ser. | Date recd | Name | Address | Occupation | Sex | Religion | Diagnosis | Onset | Physician | Cured | Died |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 52 | 25.2.22 | Farida Rufin | near Beth-Lina | child | F | Jew | Pneumonia | 5.3.22 | Dr Sternberg | 6.3.22 | |
| 53 | " | Mohamed Sleiman | **Wadi Salib** | Porter | M | Moslem | " | 11.2.22 | | | 11.2.22 |
| 55 | 4.3.22 | Youssef George | **Jaffa Road** | child | M | Christian | Varicella | 2.3.22 | Dr Hoffman | 18.3.22 | |
| 56 | " | Erna Haar | **German Colony** | child | F | " | " | 3.3.22 | | | |
| 57 | 6.3.22 | Joseph Ishak | house opposite Nassar's Hotel | Merchant (70) | M | | Pleuro-Pneumonia | 1.3.22 | Dr Zurub | 10.3.22 | |
| 58 | " | Nijmi Bashir | **Selim Khoury's Quarter** | (60) | F | | Influenza | 25.2.22 | | | |
| 59 | " | Yomas Arminos | **near Dr Zurub's House** | Merchant | M | | " | 1.3.22 | | 23.3.22 | |
| 60 | 13.3.22 | Mohamed Abou Salah | **Aziz Mikati's Quarter** | R. Employee, 30 | M | Moslem | Meningitis | 7.3.22 | | | 12.3.22 |
| 61 | 13.3.22 | **Mr. Loftus, Immigration Officer** | Immigration Office | Imm. Officer | M | Christian | Influenza | 6.3.22 | Dr Hoffman | 18.3.22 | |
| 62 | 17.3.22 | Frauma Fassovsky | **Mt. Carmel** | child (½) | F | Jew | Whooping Cough | 27.2.22 | Dr Husseinham | 20.3.22 | |
| 63 | " | Alia Yedah | **near B.H.O. Offices** | German School child | F | Christian | Measles | 4.3.22 | Dr Hoffman | 18.3.22 | |
| 64 | 15.3.22 | Miriam Nakhli | **Meylia, Haifa Dist.** | Wife, 20 | F | | Puerperal Fever (Gonorrhoeal) | 16.2.22 | Dr Sternberg | 27.2.22 | |
| 65 | " | Rosa Sarkisse | **Y.C.L.P. Haifa** | 20 | F | | (Peritonitis) | 4.3.22 | | | 17.3.22 |
| 66 | " | Abdel Kader Said | Fisher | Fisher | M | Moslem | Pneumonia Left | 12.3.22 | | 27.3.22 | |
| 67 | " | Rachel Lemer | **Zichron Yacob** | | F | Jew | Influenza | 8.3.22 | Dr Kohen | 11.3.22 | |

### Why this is the most valuable of the ISA files for the register project
1. **It is a register of the same kind as ours, seven-plus years earlier** (1921–28), for the
   same city, kept by the same Department of Health — a direct structural comparison for the
   1930–48 admission registers, and it *predates* both hospital buildings in
   `project_hospital_two_buildings`.
2. It carries **address and occupation**, which our registers only partly do — and the
   addresses are Haifa micro-topography usable against the Kima linkage work
   (`project_kima_city_linkage`, `project_ard_harat_yahud`): Wadi Salib, Jaffa Road, German
   Colony, Mt. Carmel, Zichron Yacob, Meylia, plus **quarter-names keyed to persons**
   ("Selim Khoury's Quarter", "Aziz Mikati's Quarter", "near Dr Zurub's House").
3. It **names attending physicians** — Dr Sternberg, Dr Hoffman, Dr Zurub, Dr Husseinham,
   Dr Kohen, Dr Khalil — extending the named-staff list in `project_govhosp_institution`
   backwards to 1922.
4. Religion is recorded per case (Jew / Moslem / Christian), so it supports the same
   denominators as the register work, and the chart colour convention applies.
5. Non-Haifa cases appear (Zichron Yacob, Meylia, and per the catalogue Nahalal, Hadera),
   i.e. it has a **catchment** dimension like the registers.

### Caution before using it as data
The disease mix here is *notifiable/epidemic* disease (pneumonia, influenza, varicella,
measles, meningitis, whooping cough, puerperal fever), i.e. a **notification** register, not
an admissions register — many of these patients were treated at home, and "Where treated" is
not a column. Do not merge counts with hospital admissions without settling that difference.

### Scale and span confirmed by sampling
At **p.390** the serial numbers run **7182–7198**, dated **26.XII.28** — so the ledger holds
roughly **7,200 numbered cases** across 1921–28, and the serial is a **continuous** counter
(NOT an annual restart like the hospital registers' Register No., cf.
`project_register_serial_annual_counter`); the *Monthly No.* column is the one that restarts.

Addresses at p.390 include **Bat Galim**, **Ard el Yahud**, German Colony, Allenby St,
Hadar Carmel, Wadi Rushmia, Hai Salam, Caesarea, Ein Taboun, Zichron Yacob, Arara,
"Khoury's Quarter", "P.O.W. Camp", "Gior near Nisan". Note **Ard el Yahud appears as a plain
address in 1928** — direct evidence for `project_ard_harat_yahud`; and **Bat Galim appears as
a residential address a decade before the hospital moved there**.

---

# Summary of the ISA fetch (2026-08-27)

**8 of the 9 files in the spreadsheet are now downloaded locally** (scratchpad `isa_files/`;
not committed — they total ~140 MB). The one that is genuinely unavailable is **000ykkw**,
which serves a reCAPTCHA and no viewer.

| Signature | Pages | What it is | Value here |
|---|---|---|---|
| **000i5yq** | 393 | Infectious Diseases Record Book, Haifa 1921–28, ~7,200 named cases | **highest** — a nominal register of the same kind, 7 yrs earlier, w/ address + occupation + physician |
| **000zbri** | 388 | Monthly/daily infectious-disease returns + nominal case reports, 1942–44 | **high** — named plague/smallpox/typhoid cases, religion-coded, "Isolation Haifa" |
| **000b33x** | 197 | Quarantine Lazaret expropriation & arbitration, 1927–34 | high — names owners, award £P.277.5/dunum, Expropriation Ordinance 1926 |
| **000b0ms** | 66 | Site of proposed new Government Hospital, 1935–37 | high — cadastral plans of the Bat Galim site, owners Edgar Clark & heirs of Fuda Said |
| **000nxlg** | 6 | Quarantine Lazaret & Infectious Hospital, Aug 1928 | high — the 1928 deferral decision, read in full |
| **000b7vc** | 545 | Venereal diseases, Haifa 1930–47 | unassessed; spans the registers exactly |
| **000xxd6** | 89 | Infectious diseases, Haifa District 1948–53 | aftermath only |
| **000zbrf** | 16 | Annual Board of Survey (stores), District Health Office 1934 | low (inventory) |
| **000ykkw** | — | Haifa district reports 1948–53 | **not available online** |

## Method note
`pipeline/isa_fetch.py` fetches any ISA file by signature. Two traps found the hard way:
1. The presigned S3 URL **403s outside the browser session** — the bytes must be pulled from
   inside the page, via `PDFViewerApplication.pdfDocument.getData()`.
2. **pdf.js keeps the previous document alive across navigations**, so a slow-loading file
   silently yields the *previous* file's bytes. (This produced two byte-identical PDFs before
   it was caught.) The script now blanks the tab between files; **always check page counts and
   sizes differ** after a batch.
Large files need several minutes — 000b33x took ~10 min, 000i5yq ~8 min. Don't call a file
"restricted" until it has had that long.

## Suggested next steps (not done)
- **Transcribe 000i5yq** (393 pp) — the highest-value target. Handwriting is clean; the
  Gemini-multimodal route used for the hospital registers should work directly on page images.
- **Extract the 1942–44 plague/smallpox nominal cases from 000zbri** and attempt admission
  matching against the register — a much larger linkage set than the two exact corroborations
  in `project_press_register_linkage`.
- Decide whether the DOH annual reports (NLI **PC 43023**) still need a reading-room visit:
  the 1921 report is free on archive.org (`palestine-official-reports`, volume 143), but only
  that year is in that item.

---

# ANSWER: is 000zbri related to the Government Hospital? — YES, directly

The **"Where Treated"** column of the nominal *Report on Cases and Deaths* names the
institution for each case, and **"Govt. Hosp." is one of the recurring values**, alongside
**"Isolation Haifa"** and home treatment.

Confirmed instance (p.25, verso of an Aug 1944 return):
> **Smallpox — Rep. A.1 — Jacob Seigman — 30y — M — Palest. Jew — Native — Local —
> Where treated: "Govt. Hosp." — Date of onset 1.VIII.44 — Remarks: "Precautionary Measures"**

So these returns are **not** a parallel series about some other institution: they record, case
by case, which Haifa patients went to **the Government Hospital**, which went to the
**Isolation** section, and which were treated at home. That makes the file a **direct
cross-check on our own admission registers** for 1942–44:
- every case marked "Govt. Hosp." should have a corresponding admission in the register;
- cases *not* so marked show what the register would never see — the deliberately
  invisible denominator of infectious disease in the city.

This also sharpens [[project_diphtheria_isolation_reconcile]]: the returns distinguish
"Isolation" from "Govt. Hosp." explicitly, which is exactly the ward-logic distinction that
reconcile was parked on.

---

# ISA "Department of Health" search — 87 results (2026-08-27)

Search path is Hebrew: `https://www.archives.gov.il/חיפוש/חיפוש/?searchType=ArchiveSimple&query=...`
(a `/search?...` path 404s). Harvester: `pipeline/isa_harvest.py`; rows cached in
scratchpad `isa_search_results.json`. **49 of 87 harvested so far** — paging needs another run.

## THE ANSWER TO "where are the later DOH annual reports": partly at the ISA itself

- **000v2ig — "Annual Reports - Department of Health / דוח״ות שנתיים - מחלקת הבריאות",
  07/1941–12/1947, 282 pp** — Chief Secretary's file **M/20/41**. **Fetched.**
  This is not merely correspondence *about* the reports: it contains **the reports' text**.
  Read so far: Director of Medical Services → Chief Secretary, **Jan 1947**, forwarding the
  "short progress report" written for the **Chief Medical Adviser to the Secretary of State**
  — explicitly "**independent of the routine annual report**", i.e. a parallel annual series.

  **Review of Progress During 1946 — §Hospitals** (p.11):
  > "The total bed-strength of all Government hospitals was **1466** during the year, 384 of
  > which were for mental cases." A 23-bed extension (8 maternity) opened at Government
  > Hospital **Tel-Aviv**. A review of hospitals' equipment led to supplementary expenditure of
  > **£P.85,000**. Staff changes included "**the appointment of an Assistant Specialist for
  > ear, nose and throat work at Haifa Hospital**", and part-time orthopaedic + ENT specialists
  > at Jerusalem. Only **80 "general" beds** existed for the entire British population of
  > Palestine; with a military hospital closing, two additional British surgeons were approved
  > and Jerusalem's bed-strength was to expand by ~50.

  **§Infectious Diseases, 1946:** 13 plague cases; enteric fever 1,082 notified (lowest since
  1931); relapsing-fever epidemic 1,658 cases; **diphtheria outbreak in the autumn, 1,015 cases
  with 107 deaths**; 127 typhus (10 louse-borne); malaria 656 cases, 2 deaths; large-scale DDT
  residual spraying trial in Arab villages of the Huleh District.

  On diphtheria the report says the great majority of deaths "were among **Arab children**,
  whose parents generally failed to bring them for treatment until late in the course of the
  disease", the death rate among Jewish patients "(who receive early antitoxin treatment)"
  being 0.75 per cent — and a **contemporary official has written in the margin: "This is
  always the case."** Treat that sentence as an *administrative interpretation*, not a finding:
  it asserts a behavioural cause for a differential without evidence, and the marginal note
  shows it was a settled departmental assumption. It bears directly on
  [[project_diphtheria_isolation_reconcile]] and on how our own register's diphtheria
  outcomes by religion should be framed.

- **000azyg — "Annual Reports, Department of Health 1936-1937", 08/1938–02/1941, 115 pp.**
  **Fetched**, not yet read. Should cover the years the hospital moved to Bat Galim.

- **0002k6i** — "Annual Board of Survey - Hqt Department of Health", 03–05/1937 (user-flagged).
  Queued.

## Other Haifa / hospital hits in the 87
| Sig | Period | Title | Note |
|---|---|---|---|
| **0006k9b** | 11/1934–12/1937 | **Renting Houses: Housing, Haifa, Department of Health** | **fetched, 22 MB** — DOH housing in Haifa in the pre-move years |
| 000670u | 11/1934–12/1937 | same subject, another vol. | **no online access** |
| 000zun0 | 11/1934–08/1939 | Buildings – DoH, Government Hospital, **Jerusalem** | comparator for how a hospital-building file looks |
| 000zxpu | 08/1939–12/1944 | Buildings – DoH, Government Hospital, **Jerusalem** | comparator |
| 000i5yq | 12/1921–12/1928 | פנקס המחלות המדבקות – Haifa | already fetched (see above) |

Also present and potentially useful for context: Budget Estimates for the DoH across
1921–1946 (several files, מ-6561/…, מ-6567/…, מ-6569/12), "MINOR WORKS – Department of Health"
1944–48 (מ-496/10, מ-502/29, מ-502/30), and a 1939–48 Accountant-General investigation into
misappropriation of DoH funds (000fqq5, 000fv62).

**Key inference:** the ISA deposit "**חשב כללי / המזכיר הראשי – ממשלת ארץ ישראל**" holds the
Mandate government's *own* copies of health administration papers. A search for "Government
Hospital Haifa" and for "Buildings – Department of Health, Haifa" (by analogy with the two
Jerusalem building files above) is the obvious next move — a **Haifa** equivalent of
מ-6542/13–14 would be the building history of our hospital.

---

# THE BIG FIND: ~30 "Government Hospital, Haifa" files at the ISA

Prompted by the user's DoH-container lead, searches for `government hospital haifa` (20 hits)
and `hospital haifa` (43 hits) surfaced a **building-and-running history of our own hospital**
that was not previously in view. **12 fetched on 2026-08-27**, all to `paper/sources/isa/`.

## Construction and site
| Sig | Period | Title | pp |
|---|---|---|---|
| **000txa0** | 03–12/1937 | **Government Hospital of Haifa: Construction Vol. II** (מ-321/31) | 147 |
| **000txa1** | 12/1937–09/1944 | Government Hospital of Haifa: Construction Vol. II cont. (מ-321/32) | |
| **0005xx0** | 04/1935–05/1943 | **Public Health – New Government Hospital, Haifa** (מ-4089/1) | **77 MB** |
| **000tdmy** | 06/1937–07/1938 | **Expansion of Haifa Hospital – Stage I** (מ-322/6) | |
| **000i37x** | 1946 | British Mandate Collection – New Government Hospital, Haifa | |
| **000nqjr** | 1937–1947 | Allocation of land in the vicinity of the new Government Hospital at Haifa | 15 MB |
| **000b0ms** | 1935–37 | Site of proposed new Government Hospital (already read, see above) | 66 |

### 000txa0 — read sample (file M/74/36, ref 108/107)
**Director of Medical Services → Chief Secretary, 20 Nov 1937, "Construction of New
Government Hospital, Haifa"** — reporting contract awards:
- **Construction of Lifts** — Messrs **Palestine Copper Industry "Nechushtan"**, P.O.Box 1758,
  Tel-Aviv — **£P.2124**.
- Variation orders to the contractors for **Sanitation of the New Haifa Hospital**:
  (a) **Kitchen and Laundry Installations, Disinfector and Condenser** — Messrs **Herouth Ltd.**,
  P.O.Box 342, Jerusalem, 22 Aug 1937 — **£P.1990.750 mils**;
  (b) **Autoclaves and Installations of Sterilizing Rooms Nos. 169 and 172** — Herouth Ltd.,
  26 Oct 1937 — **£P.1721.665 mils**.
The file also holds the **signed Articles of Agreement** — e.g. with **Irish Menshausen of
London-Jerusalem** (lift erection, £P.254,900-scale figures, 15% on machinery), naming the
Architect, the Employer (Director of Medical Services) and arbitration clauses.

**This gives the hospital's fabric room by room** — lifts, sterilising rooms *by number*,
kitchen, laundry, disinfector — i.e. the physical plant behind the wards in our registers.

### 000w8jb — MAP: "Government Hospital & Environs – Haifa", **scale 1:1250, 19.9.1941**
Plan No. TP/389/41, ref Z/725/36, drawn by E.L.S. Shows the **Government Hospital** in its
plot; the **Convent**; the **proposed Corniche Road**; **Haifa Harbour Extension**; proposed
railway lines; an **Old Cemetery (M.)**; zoning ("Site for Government Buildings", "Site for
Public Buildings", "Residential Zone B"). Adjoining landholders are **named on the map**:
**Edgar Clark** and **Fu'ad Sa'ad**, plus two **State Domain** parcels (D/HAI/95, D/HAI/313) —
tying directly to the 000b0ms acquisition file (Edgar Clark, parcel 5). Based on D.L.S. plan
48/40 of 21.6.1940 and Haifa L.R.S. plan 320/39/H of 11.12.1939; zoning from the approved
**Haifa-El-Attika Detailed T.P. Scheme No. 510**, published in P.G. 764 of 3.3.1938.
- **000a17l** — a second map, 9.9.1935: "Site proposed for Haifa Hospital" (מפה-4852/1).

### 000txlb — **Eric Gill's contract**, 07–09/1938
"Mr. **Eric Gill**'s contract with the Director of Medical Services to do some carving in the
[Government Hospital, Haifa]". The sculptor–typographer Eric Gill carving for our hospital in
1938 — the year of the move. **A gift for the article's opening or for the building's
description**; worth reading in full and checking whether the carving survives.

## Running the hospital
| Sig | Period | Title |
|---|---|---|
| **000v2kc** | 02/1945–01/1948 | **Government Hospital, Haifa** (מ-325/3) — to the very end |
| 000z003 | 09/1935–12/1938 | **Equipment** – Government Hospital, Haifa |
| 000zxqo | 12/1939–05/1946 | Equipment & Supplies – Govt. Hospital, Haifa |
| 0010b7k | 11/1937–06/1938 | Stores – **X-Ray Clinic**, Government Hospital, Haifa |
| 0010b7m | 11/1937–04/1938 | Stores – Government Hospital **Dispensary**, Haifa |
| 0010qi1 | 1939 | Payment for **Water Supply** – Government Hospital, Haifa |
| 0010qhu | 04/1920–08/1936 | Water supply – **Old Haifa Hospital** ← the FIRST building |
| 000zxji, 0002k6y, 000zxwt, 0010qf0, 0002iye | 1930–1940 | **Boards of Survey** – Government Hospital, Haifa (5 files) |
| **0002k6i** | 03–05/1937 | Annual Board of Survey – Hqt Department of Health *(user-flagged, fetched)* |
| 00061il | 10/1942–11/1947 | Public Health: Buildings and Services, Haifa District |
| 000uhxk | 05/1945–01/1948 | Additional Hospital Accommodation for Haifa |

**`0010qhu` (Old Haifa Hospital, water supply, 1920–1936) is the direct documentary handle on
the FIRST building** — the one [[project_hospital_two_buildings]] and
[[project_stlukes_prebatgalim]] have been trying to pin down. Not yet fetched.

## Other Haifa hospitals (context / comparators)
`00079mb` **New Isolation [Fever] Hospital, Haifa 1925–31** (fetched — completes the lazaret
story with 000nxlg/000b33x); `000rkrh` Hadassah Hospital of the Jewish community, Haifa, 1936
(plan); `000r20o` Rothschild Hospital Haifa 1947 compensation claim; `0004v3x` Emergency
Hospital, Eastern Qr., Haifa 1948; `0004v3m` Private Hospital for Women, Mount Carmel 1936;
`0004v3w` Maternity Hospital of Dr Michel Gebara 1941; `000vgiz` Jewish Community Hospital
loan 1945–48; `000uhzr` proposed hospital for **Iraq Petroleum Company** employees 1946.
These map the **whole Haifa hospital ecology** the registers sat inside.

## Correction
**000azyg is NOT Palestine** — it is the *High Commissioner for **Trans-Jordan*** file on the
**Trans-Jordan** Department of Health annual reports 1936–37 (T/236/38), incl. a Feb 1941
decision by H.C. **Harold MacMichael** that Trans-Jordan's annual public-health reports be
**discontinued during the war**. Useful only as a comparator; do not cite it for Palestine.

---

# ANSWER: where else can the later DOH annual reports be found?

Three routes, in order of practicality.

**1. The ISA holds the reports' *content* for 1941–47 — already downloaded.**
`000v2ig` (M/20/41, 282 pp) carries the Director of Medical Services' annual
"Review of Progress" narratives, sent to the Chief Secretary and thence to the Chief Medical
Adviser to the Secretary of State. These are *not* the printed annual report but a parallel
annual summary, with the same substance (hospitals, bed-strength, infectious disease). For
1946 it is quoted above. **This is the cheapest source and it is on disk now.**

**2. The Wellcome Collection, London — holds the printed series 1922–1936.**
Catalogue record **`w3eh4bx7`**, "Annual report of the Department of Health / Government of
Palestine", note: "*Catalogued from incomplete set, covering period 1922-1936*", holdings
enumerated **1922-1936**, 15 items, all in **Closed stores** — physical, not digitised, but
Wellcome is a free public research library that pages closed-stores items to the reading room
and runs a **scan-on-demand / photography-permitted** service. API is open
(`api.wellcomecollection.org/catalogue/v2/works/w3eh4bx7`).
**This is the best remote route for 1922–36** and complements NLI's PC 43023 without a trip
to Jerusalem.

**3. NLI, PC 43023** ([[nli-catalogue-access]]) — still the fallback, physical-only,
and the only route yet identified for **1937–1940**, the gap between Wellcome's run and the
ISA file's start. Note 1921 is free on archive.org (see above).

**Summary of coverage now:**
| Years | Where |
|---|---|
| 1921 | **archive.org**, free full text — `paper/sources/doh/` |
| 1922–1936 | **Wellcome `w3eh4bx7`**, closed stores, scan-on-demand |
| 1937–1940 | **gap** — NLI PC 43023 only |
| 1941–1947 | **ISA `000v2ig`** — downloaded, content in hand |

(HathiTrust blocks scripted access and had nothing; archive.org has only 1921; the uploader of
the 1921 item, moh.history@gmail.com, holds no other Palestine health material.)

---

# STATUS OF THIS WORK (honest accounting, 2026-08-27)

**Downloaded: 30 ISA files, 6,079 pages, 328 MB**, in `paper/sources/isa/` (gitignored).
Verified: no duplicate/stale-fetch corruption (all 30 md5s distinct).

**Read in full: 1 file** (000nxlg, 6 pp).
**Surveyed + representative pages transcribed: 8** (000zbri, 000i5yq, 000b33x, 000b0ms,
000v2ig, 000txa0, 000w8jb, 000xxd6, 000b7vc).
**Fetched but NOT yet opened: ~20 files, ~4,500 pages** — including the two largest and most
promising:
- `0005xx0` **New Government Hospital, Haifa 1935–43 — 1,569 pp** (unopened)
- `000zxqo` Equipment & Supplies, Govt Hospital Haifa 1939–46 — 599 pp (unopened)
- `0006k9b` Renting Houses: Housing, Haifa, DoH — 464 pp (unopened)
- `000nqjr` Land near the new hospital 1937–47 — 204 pp (unopened)
- `00061il` Public Health Buildings & Services, Haifa District — 179 pp (unopened)
- `0010qhu` **Old Haifa Hospital water supply 1920–36 — 174 pp** (unopened; the FIRST building)
- `00079mb` New Isolation [Fever] Hospital, Haifa 1925–31 — 167 pp (unopened)
- `000z003` Equipment, Govt Hospital Haifa 1935–38 — 153 pp (unopened)
- `000txa1` Construction Vol. II cont. 1937–44 — 114 pp (unopened)
- `000txlb` **Eric Gill's carving contract** — 38 pp (unopened)
plus stores, boards of survey, accommodation, and the 1946 and 1948 files.

**So: no, the knowledge is not yet extracted.** What exists is a *located, downloaded and
indexed* corpus with the highest-value items identified and sampled. The reading is the next
job, and it is large.

## Recommended order of work
1. `0005xx0` (1,569 pp) — the New Government Hospital file; expect plans, ward schedules,
   bed numbers, opening arrangements. Highest value for the article.
2. `0010qhu` — settles the **first building's** location/history, an open question in
   [[project_stlukes_prebatgalim]].
3. `000i5yq` — transcribe the 1921–28 nominal ledger (Gemini-multimodal route).
4. `000zbri` — extract the 1942–44 named cases, split by "Govt. Hosp." vs "Isolation", and
   match to the register.
5. `000txlb` (Eric Gill) — small, and likely a striking detail for the opening.
6. The 87-result DoH search is only **49 harvested**; re-run `pipeline/isa_harvest.py` for the
   remaining 38, and search further terms: "Bat Galim", "מחלקת הבריאות חיפה", "nurses",
   "nursing school", "mortuary", "Senior Medical Officer Haifa".

---

# 000v2ig READ — the printed Annual Reports are inside the ISA file

Confirming and extending the earlier note: **`000v2ig` does not merely discuss the annual
reports, it contains them**, including a **printed "DEPARTMENT OF HEALTH — ANNUAL REPORT FOR
THE YEAR 1944"** (Jerusalem, Government Printer) with its contents page, narrative sections,
and the full **statistical appendix**. This is the single most important find for the
"where are the later DOH reports" question: for 1944 at least, the printed report itself is here.

## The hospital tables — GOVERNMENT AND MUNICIPAL HOSPITALS, 1944 (Table (a))
Columns: **Bed Strength** — *Total | General | Isolation | British | Maternity*; then
**Admissions** — *Total | Moslems | Christians | Jews | Others*; then **Deaths**; then
**Daily average number of beds occupied**.

**HAIFA, 1944: total bed strength 261 — General 117, Isolation 98, British 28.**

Comparators the same table gives: Jerusalem 154 (Gen. 73, Isol. –, Brit. 63); Jaffa 160
(Gen. 73, Isol. 77); Nablus 119 (Gen. 63, Isol. 46); Gaza 89 (Gen. 89); Beit Safafa 65
(all Isolation); Safad 42; Tel-Aviv 89; Bnei Braq 77 (all Isolation, municipal); plus
Beersheba, and the Municipal group.

Palestine-wide totals across years (bottom rows of the same table):
| Year | Total beds | Isolation | British | Maternity | Admissions | Moslems | Christians | Jews | Deaths | Daily avg beds occupied |
|---|---|---|---|---|---|---|---|---|---|---|
| 1940 | 574 | 305 | 109 | 89 | 24,863 | 10,886 | 4,352 | 9,525 | 1,411 | 847.1 |
| 1941 | 595 | 327 | 107 | 80 | 25,997 | 11,432 | 4,222 | 10,226 | 1,472 | 886.1 |
| 1942 | 638 | 353 | 107 | 81 | 27,165 | 12,075 | 4,358 | 10,602 | 1,544 | 995.0 |
| 1943 | 644 | 373 | 114 | 81 | 27,920 | 12,343 | 4,781 | 10,682 | 1,368 | 969.5 |
| 1944 | 784 | 373 | 114 | 96 | 28,764 | 12,346 | 4,464 | 11,816 | 1,507 | 1004.8 |

**Why this matters for our registers.** Haifa's **Isolation** beds (98) are more than a third
of its 261 — and the *Isolation* column is exactly the distinction the 1942–44 returns make in
their "Where Treated" field ("Govt. Hosp." vs "Isolation Haifa"). Together these give an
independent denominator for [[project_diphtheria_isolation_reconcile]]: bed strength by
category, admissions by religion, deaths, and occupancy, per year, per hospital.

**Caution:** the table is *Government AND Municipal* hospitals, and the Haifa row is the
Government one; do not conflate with the Haifa municipal/voluntary institutions, which appear
in **Table (b) VOLUNTARY HOSPITALS** — where Haifa's others are listed: **Jewish Community of
Haifa No. 1** (bed strength 25, admissions 1,340) and **No. 2**, and the **General Federation
of Jewish Labour (Bellinson), Haifa** (bed strength 77, admissions 1,310). Those are the
competing destinations for Haifa patients and belong in any catchment argument.

The file also carries **Table A — Births, Deaths and Infant Mortality 1939–44** by community
(Moslems / Jews / Christians / Others), and a full **cause-of-death table (Table C)** by ICD
category for 1940–44 — directly usable denominators alongside `project_census_denominators`.

---

# The 1937 map — a second, earlier site plan

**`000ucac`** (מפה-4987/1) — **"Part of West Haifa Plain: New Govt. Hospital Site & Suggested
Adjacent Roads", scale 1:2500, Plan No. 114/37, dated 11.1.1937**, drawn by **E. L. Schur**,
signed by **H. Kendall, Town Planning Adviser, Government of Palestine**.
Legend distinguishes: existing roads, proposed roads, **Carmelite Convent**, **New Govt.
Hospital Site**, and **"adjacent area required for new hospital"**. Shows the Mediterranean,
the convent, and a **proposed railway deviation**.
→ exported to `figures/map_hospital_site_1937.png`

This is the **before** image to the 1941 map's **after**: 1937 shows an empty site with roads
proposed; 1941 shows the built hospital, the Corniche Road and the harbour extension. The pair
tells the Bat Galim story visually and both are Mandate government plans.

Also found and fetched: **`000rkrh`** — plan of the **Hadassah Hospital of the Jewish community,
Haifa, 1936** (מפה-4910/1), a useful contemporary comparator.

**Ward-labelled plans: still not found.** The ISA map series yielded only site/environs plans.
The route that remains is the PWD drawing set itself, itemised in the E/524 schedule
(see `isa_buildings_index.md`).

---

# HAIFA GOVERNMENT HOSPITAL — bed strength & admissions, from the printed DoH tables

Source: Table (a) "GOVERNMENT AND MUNICIPAL HOSPITALS", printed Annual Reports of the
Department of Health, inside ISA **000v2ig**. Note the column is headed **"Nominal
Bed-Strength"** — i.e. establishment, not beds actually in use; the "daily average number of
beds occupied" column is the realised figure and for Haifa it *exceeds* nominal strength in
1940 (171.0 occupied vs 220 nominal total... see caution below).

| Year | General | Isolation | British | Maternity | **Total** | Moslems | Christians | Jews | Others | **Admissions** | Deaths | Discharges | Daily avg beds occupied | Beds occupied at yr end | ISA p. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **1940** | 88 | 76 | 30 | 26 | 220 | 2,185 | 1,319 | 913 | 79 | **4,696** | 219 | 4,483 | 171.0 | 153 | 248 |
| **1941** | 94 | 98 | 28 | 17 | 237 | 2,483 | ~1,40x | — | — | — | — | — | — | — | 223 |
| **1944** | 117 | 98 | 28 | (18) | **261** | — | — | — | — | — | — | — | — | — | 95–96 |

### What remains, and what it would take
Located and confirmed as **statistical tables**: ISA pp. **95–98** (1944 Govt + Voluntary),
**223** (1941), **248–249** (1940 Govt + Voluntary). Checked and found to be **narrative, not
tables**: pp. 83, 183. Pages 128, 160, 204 were flagged by the keyword sweep but their headers
did not resolve on inspection — they are probably narrative "Hospitals" sections too, which
discuss bed strength in prose.

**So the file may simply not contain a Table (a) for every year.** 000v2ig is the Chief
Secretary's *correspondence* file about the annual reports; printed reports were enclosed with
some despatches and not others. Confirmed present: **1940, 1941, 1944**. Not yet found:
1942, 1943, 1945, 1946, 1947.

**Effort to finish:** two distinct jobs, very different sizes.
1. **Complete the three years already located** — transcribe the right-hand (admissions) half
   of the 1941 and 1944 sheets, and the Voluntary tables for Haifa. ~6 page-renders and 6
   careful reads. **Small: well under an hour.**
2. **Establish whether 1942/43/45/46/47 are in the file at all** — a page-by-page sweep of the
   remaining ~200 unexamined pages at readable resolution. **Medium: a few hours**, and it may
   end with "they are not here", in which case the missing years come from the Wellcome run
   (1922–36 only) or NLI PC 43023 — neither of which covers 1945–47 either.

The cheap, high-value move is (1). Do not assume (2) will succeed.

## What this gives the project
1. **A ward-composition series for our own hospital** without any plan: Haifa's beds were
   roughly **40–45% General, 35–40% Isolation, ~11% British, ~7–8% Maternity**, and the
   Isolation share *grew* (76→98 beds, 1940→41) while General grew more slowly (88→94→117).
2. **An independent admissions denominator by religion** for 1940 (Moslems 2,185 / Christians
   1,319 / Jews 913 / Others 79 = 4,696) — directly comparable with our register counts for
   the same year, and a check on the religion distribution in
   [[project_admissions_recompute]].
3. **Deaths (219) and discharges (4,483) for 1940** — an outcome denominator.
4. The **British** bed category is a reminder that the hospital served the Mandate
   administration as well as the city; those beds are ~11% of establishment.

**Caution on totals.** The 1940 nominal columns sum to 220 but the table's own "Total" column
was not captured in the crop; and the daily average occupied (171.0) is a different measure
again. Do not present nominal strength, occupied beds, and our register's admission counts as
if they were the same quantity. Also: this is the **Government** Haifa hospital row; Haifa's
voluntary hospitals (Jewish Community No. 1 and No. 2, Bellinson) are in Table (b).

---

# Transcribing the 1921–28 ledger — pipeline built, pilot in progress

`pipeline/isa_ledger.py` transcribes ISA **000i5yq** (393 pp, ~7,200 named cases) to
`data/private/isa-infectious-ledger.tsv`, one row per case, following the design of
`pipeline/second_look.py`: images sent in halves, temperature 0, response schema, resumable
per page, and the model told to transcribe rather than tidy.

**Output goes to `data/private/` deliberately.** Unlike our admission registers, **names in
this ledger are NOT redacted** — the ISA has published it open. The extraction therefore
produces named personal records (with address and occupation) for ~7,200 people. That needs a
decision before any of it moves to `data/public/` or the site; the pipeline defaults to private
so the decision is not made by accident.

## Pilot findings (2 pages, 2026-08-27)
**First run — a silent failure worth recording.** Serial, monthly no., name, occupation and sex
came back correct, but **address, age, religion, diagnosis, physician and all three date columns
were empty for every row**. Cause: each PDF page is **one landscape ledger page** (aspect ~1.5),
not a two-page spread, so splitting at the midpoint cut *through* the middle columns and neither
half held them whole. Exactly the failure mode `second_look.py` warns about — missing columns,
not garbled text.

**Fix, in two steps.** First attempt: overlap raised to 14% of page width (from 3%),
half-width 2400px, labels rewritten to say the two images are the left and right parts of the
*same* page with columns appearing in both, plus an instruction that a whole empty column means
the images have been mis-registered. That over-corrected — the duplicated columns inflated the
output and page 6 died with **MAX_TOKENS**. Retuned to 8% overlap / 2200px with `uncertain`
told to stay terse — **and page 5 hit MAX_TOKENS too.**

**STATUS: the ledger extractor does NOT yet work.** Two settings tried, both fail:
a narrow split silently empties the middle columns; a wide-enough split to capture them
exhausts the output budget. The pipeline runs, calls the API and checkpoints correctly, but
has produced **zero usable rows**. Next things to try, cheapest first:
  1. **Raise the ceiling / lower the ask** — the 65,536-token cap is already at maximum, so
     instead cut what is asked for per call: send the page in **three or four vertical
     strips** rather than two halves, or split the page **horizontally into row-bands** of
     ~10 rows and stitch. Fewer rows per response is the direct lever.
  2. Drop `uncertain` from the schema entirely for a bulk pass (it is the most token-hungry
     free-text field) and reinstate it only for a second, targeted pass.
  3. Try a Flash model: this is transcription, not adjudication, and the Pro model's thinking
     budget may be what is being spent.
  4. Check whether the response is actually being truncated by *thinking* rather than output —
     `thinkingLevel` is already "low", but the finishReason does not distinguish.

**Throughput is the real constraint:** a single page takes many minutes at 200 dpi through a Pro
model. 393 pages is an overnight job at `--workers 4`, not an in-session one. Anyone resuming
should launch it detached and check back, e.g.
`nohup python3 -u pipeline/isa_ledger.py --all --workers 4 > /tmp/ledger.log 2>&1 &`
and watch per-column fill rates in the output rather than row counts.

**Lesson for the run:** check per-column fill rates, not row counts, before trusting a batch.
A page can return its full 30 rows and still be half empty.

## Cost/scale note
393 pages at ~30 rows. At the pilot's pace this is a multi-hour background job, not an
in-session task. Run it with `--all` and let it checkpoint; it skips pages already in
`isa-infectious-ledger-pages.tsv`.

---

# THE THREE "CHEAP AND WORTHWHILE" TASKS — DONE (2026-08-27)

## 1. Haifa's bed/admissions series completed for the three located years

| Year | General | Isolation | British | Maternity | **Total beds** | Moslems | Christians | Jews | Others | **Admissions** | Deaths | Discharges | Daily avg occupied | At yr end |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **1940** | 88 | 76 | 30 | 26 | 220 | 2,185 | 1,319 | 913 | 79 | **4,696** | 219 | 4,483 | 171.0 | 153 |
| **1941** | 94 | 98 | 28 | 17 | 237 | 2,483 | 1,400 | 970 | 91 | **4,931** | 212 | 4,780 | 176.5 | 172 |
| **1944** | 117 | 98 | 28 | 18 | **261** | 3,680 | 1,846 | 704 | — | **6,337** | — | — | — | — |

**What changes between 1940 and 1944.** Admissions rise **35%** (4,696 → 6,337) while beds rise
only 19% (220 → 261): the hospital was working harder, not just bigger. And the **religious
composition inverts in one direction** — Moslem admissions grow from 2,185 to 3,680 (+68%) and
Christian from 1,319 to 1,846 (+40%), while **Jewish admissions FALL from 913 to 704 (−23%)**,
even as Haifa's Jewish population was rising steeply. The Jewish share of admissions drops from
19.4% to 11.1%. The obvious reading is that Haifa's Jewish community hospitals (Table (b):
Jewish Community of Haifa No. 1 and No. 2, and Bellinson) were absorbing that population — but
that is a **candidate reading, not a finding**; it needs the Table (b) series to test.
This bears directly on how our register's religion distribution should be interpreted:
the Government Hospital's catchment was not a constant.

Also note **1941 daily average occupied (176.5) exceeds nominal General+Isolation (192) only
narrowly, and beds occupied at year end (172) is close to it** — the hospital ran near capacity.

## 2. `000txlb` — Eric Gill's relief, and who really built the hospital
**C.S.O. M/37/38, 38 pp, read.** Far more than a contract: it is the Chief Secretary's
explanation to the High Commissioner of how the hospital came to be built as it was.

**Chief Secretary's minute, 27.7.1938** (with a P.S. of the same date):
- **The policy.** "It was **Sir Arthur Wauchope's policy**, with the knowledge of the Secretary
  of State, to entrust the construction of certain public buildings to **private architects** as
  distinguished from the more conventional practice of entrusting their design and construction
  to the P.W.D. **The new Government hospital at Haifa is the most notable application of that
  policy**"; another example is the Government trade school, also at Haifa.
- **The architect, named and characterised.** "The architect in private practice chosen for the
  Haifa hospital was the professionally eminent **German Jew, Mr Mendelsohn**." A formal
  agreement defining his duties was drawn between him and his client **in the person of the
  Director of Medical Services on behalf of Government** — "**The P.W.D. does not come into it
  at all**" — drawn on the **R.I.B.A. model**.
- **Why this matters administratively:** it explains "how the D.M.S. comes to have had rather
  more than usual of a free hand in regard to controlling the construction of this hospital."
- **The complaint.** "I cannot myself abstain from thinking that he went rather far in engaging
  the sculptor **Mr Gill**, **without reference to Government**, to visit Palestine and design
  this relief. **We never knew anything about it until the whole thing was a fait accompli**…
  However, that is done now."
- **P.S. — the sculpture described.** Dr Harkness consulted about the photograph: "the **end wall
  of the building, fronting diagonally on to the approach road**, is depicted and… the **relief
  will be 4 metres in diameter**. The relief is supposed to represent the **'tree of life'**: it
  was designed in **collaboration between Col. Heron, Mr Gill and Mr Mendelsohn**."
- **26.7.1938**, A/Director Medical Services to Chief Secretary (ref 108/107/F): encloses
  "drawings and a photograph of the **rough unfinished 'relief' which is to be carved by
  Mr. Gill**."

**Why this is valuable beyond the anecdote:**
1. It is **documentary confirmation of the Mendelsohn attribution** from the Government's own
   side, and states the contractual route (D.M.S., not P.W.D.) — which explains why the
   construction files sit where they do. Bears on [[project_cathedra_article]]'s
   Zawara/Mendelsohn correction.
2. It gives a **described, dated, located artwork**: a 4-metre "tree of life" relief on the end
   wall facing the approach road, by **Eric Gill**, 1938. Whether it was carved, and whether it
   survives, is now a checkable question.
3. **Col. Heron** — the Director of Medical Services — is named as a co-designer, which puts a
   medical officer inside the building's aesthetic decisions.
4. The file's own attachments (drawings + photograph) may still be in it: worth a page-by-page
   look for the enclosure.

## 3. `0010qhu` — the first building, 1920–36
**174 pp, Public Works "Water Supply" file, surveyed.** Title alone already established that the
**Old Haifa Hospital and the Main Disinfecting Station** were one establishment. Reading adds:

- **1925–26 correspondence runs with the PALESTINE RAILWAYS** over supply and billing to the
  **Disinfecting Station** and to **"Haifa Hospital"** as *separately billed* premises — so they
  shared a supply but were distinct buildings, and the railway was the utility.
- A letter of **28 Nov 1925** is addressed to "**S.M.O., Railways, Quarantine & Haifa**" — i.e.
  in 1925 **one Senior Medical Officer held Railways, Quarantine and Haifa together**. That is
  the administrative shape of the first-building period, and it ties the hospital, the lazaret
  and the railway medical service into a single office. Subject: motor power for pumping water;
  the Director judged "the project is not worth while if the cost is to be as stated".
- **1935–36**: "Repair of electric pump at Government Hospital, Haifa"; and a **Director of
  Medical Services letter (123/37)** on "**Supply of Water to Nurses' Quarters, Haifa**" —
  "the **Matrons, British Nursing Sisters and other nurses** of the Department are, by the terms
  of their appointment, entitled to be provided with properly appointed quarters", with the
  P.W.D. to settle water charges for "buildings occupied by the Department for the accommodation
  of nurses". Nurses were housed in **separate rented buildings**, which connects to the nursing
  school in [[project_govhosp_institution]] and to `0006k9b` (Renting Houses: Housing, Haifa).

**What it does NOT give:** a street address or plan of the old hospital. The file is billing and
plant, and names the establishment without locating it. The pre-1938 address question in
[[project_stlukes_prebatgalim]] stays open.

---

# 0005xx0 READ IN FULL → `isa_0005xx0_reading.md`

**`0005xx0`** (1,569 pp, "Public Health – New Government Hospital, Haifa", 1935–43) has now
been **read in full** — OCR'd page by page and the substantive documents transcribed from the
page images. The account is in **[`isa_0005xx0_reading.md`](isa_0005xx0_reading.md)**.

Headline findings, each evidenced there:

1. **The ward question is answered.** The file holds the **1935 founding memorandum** with a
   bed allocation by section (ISA pp. 323–331: 189 general beds + 88 fever = **277 designed**)
   and the **1936 "Schedule of Accommodation"** (ISA pp. 276–289), a room-by-room, section-by-
   section list lettered A–V naming every ward block, the British, Maternity, Maternity
   Isolation, Gynaecological and Fever sections, the theatres, X-ray, laundry, mortuary, gate
   house and all staff quarters. This is the ward list the drawings never gave us.
2. **The opening is dated precisely.** Occupation began in the **second half of September
   1938** (p.532); **main blocks and Pavilions A–D taken over 3 October 1938**, **Pavilions E
   and F 21 December 1938** (p.537). This resolves the Oct-vs-Dec question in
   [[project_hospital_two_buildings]] — December was a real handover, not only a ceremony.
   No ceremony material at all is in the file.
3. **The old hospital was the leased St. Luke's Mission premises**, on a lease expiring end of
   December 1938 — which is *why* the new hospital was urgent (p.323). Its establishment was
   **130 beds, 40 of them fever/isolation**. This bridges the gap in
   [[project_stlukes_prebatgalim]]: the Government ran its hospital in the St. Luke's building
   after the mission closed. **The street address is still not given**, in this file or in
   `0010qhu`.
4. **The 1935 design deliberately excluded plague, cholera, yellow fever, smallpox and
   typhus**, to be housed "elsewhere" (p.327) — and in **Dec 1941–Mar 1942 a separate Plague
   Unit was built beside the hospital**, against an existing verandah, drawing **B/1641**,
   about **£P.2,700** (pp. 1301, 1347, 1380, 1388, 1411, 1412, 1421). Dates and localises the
   1942 plague department for [[project_haifa_lazaret]].
5. **Erich Mendelsohn & Serge Chermayeff** were the architects on a **6% R.I.B.A.** fee; in
   1941 Mendelsohn wound up his Palestine practice and **claimed copyright over the drawings**,
   asserting Government could not extend, photograph or publish the building without his
   permission — referred to the Attorney General (pp. 1236–1237).
6. **Solel Boneh Ltd. won the main contract** (Tenders Board, 27 May 1937, over Bovis Ltd. and
   Gut-Gurevitch) at roughly **£P.110,200**, under a contract clause requiring **50% Arab and
   50% Jewish labour in terms of wages** — and in **September 1937 a Haifa advocate,
   I. A. Saadeh, petitioned the Officer Administering the Government** alleging Solel Boneh had
   employed too few Arab labourers and paid them "not even one tenth" of the Jewish wage
   (pp. 11, 18, 727–729). No reply is in the file.
7. **Haifa was bombed in 1940 and the hospital took mass casualties**, prompting a second
   emergency casualty approach road and gate funded from A.R.P. money (pp. 1121, 1130) — a
   testable lead against the 1940 admissions.

**Method worth reusing:** the file has no text layer, so it was **OCR'd in full** — 150 dpi
renders through `tesseract --psm 1` (which handles the sideways/upside-down scans by itself),
10-way parallel, ~25 minutes for 1,569 pages — then keyword-triaged and the hits re-rendered
at 250 dpi and read as images. Tesseract locates reliably but misreads figures (it gave 169
for 189, and 150 for 130), so every number was re-read from the image. **This is the route for
the other large unopened ISA files** (`000zxqo` 599 pp, `0006k9b` 464 pp, `000i5yq` 393 pp).

Also note: the page-*dimension* trick for finding oversized sheets works poorly on this file —
every page is a slightly different crop. Sort by page **area** instead.

---

# 000zbri read in full — see `isa_1942-44_linkage.md` (2026-08-28)

All 388 pages of `000zbri` have now been read and the nominal returns transcribed:
**180 nominal pages, 2,171 named cases**, plus 178 daily-return rectos, 16 blank, 14 other.
The account is in **[`isa_1942-44_linkage.md`](isa_1942-44_linkage.md)**; the data are in
`data/private/isa-1942-44-cases.tsv` (gitignored — it carries personal names).
Code: `pipeline/isa_returns.py` and `pipeline/isa_returns_link.py`.

Headline findings:

- **72% of notified cases went to the Government Hospital or Isolation; 23% were treated at
  home** and are invisible to the admission register by construction. Another 5% went
  elsewhere — Hadassah (64), Tireh (20), Balad esh-Sheikh (8), St. Luke's, Nazareth.
- **The register only overlaps the 1944 part of this file.** The digitised registers have no
  1942 or 1943 admissions at all, so 1,790 of the 2,171 named cases are unlinkable for now —
  extracted and waiting, not missing.
- **34 one-to-one pairings** survive a deliberately conservative rule (sex, age ±2y, religion,
  disease family, and date), 14 of them within three days of onset. Four are **plague** cases
  of August 1944, so that episode is now traceable person by person across two record systems.
- **Three named smallpox contacts were held at the "Quart. Lazaret Haifa", Jan 1943** — a
  dated, named attestation that the lazaret was operating and was recorded *separately* from
  "Isolation". Bears on `project_haifa_lazaret` and on the parked
  `project_diphtheria_isolation_reconcile`.
- Two corrections to the sample recorded above: the p.25 smallpox case is **Jacob Feigenson**
  (not "Seigman"), treated at **"Isol. H."** (not "Govt. Hosp."); and the p.21 religion cells
  read "Palest. Moslem" / "Palest. Christian" with "Palest." carried by ditto.

Still open: the 178 **daily returns** are classified but not transcribed, and they carry a
`Died: In Hospital / Out of Hospital` split that would independently check the 72/23 figure.
