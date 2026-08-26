# Newspaper workstream — open items

## 1. Extend the Palestine Post harvest to 1941–1948
`govhosp_haifa_pls.tsv` currently covers **1926–1940** only. The register runs
to 1948, and the years with the strongest Arabic-side material (1946–47) are
untouched on the English side. Re-run the `"Government Hospital" Haifa` search
on `--pub pls` for 1941–48, then harvest (stage 2 is not optional) and fold
into the existing concordance.

## 2. Institutional history in the Post
Staff appointments, bed numbers, budget debates, departmental reorganisations
— none of it visible in the registers. This matters more since the League of
Nations reports established a capacity discontinuity *inside* our series:
30 beds (1930) → +50 in the St. Luke's building (early 1933) → +20 pavilion
(1935) → +22 (1936) → 225 at Bat Galim (Dec 1938). The Post should date those
steps precisely and name the medical staff. Any admissions or occupancy trend
is unreadable until the bed-count steps are pinned down.

## 3. German-Jewish immigrant press — partly in Compact Memory
**Correction to an earlier note:** the *Mitteilungsblatt* is NOT unavailable.
Frankfurt's Compact Memory (sammlungen.ub.uni-frankfurt.de/cm) holds
**MB / Irgûn ʿÔlê Merkaz Êrôpā (Tel Aviv), vols 7.1943–16.1952, full text** —
covering 1943–48 of the register — and **Jüdische Weltrundschau (Jerusalem),
March 1939 – May 1940, weekly, full text**. Also *Bericht an den
Zionistenkongress* (Jerusalem, Central Bureau for the Settlement of German
Jews, 1935), reports rather than press. Those four (plus Erez Israel 1923, too
early, and La-Ḳore ha-tsaʿir 1950, campus-network only) are the *entire*
Palestine-published holding; the rest of Compact Memory is German- and
European-published.

*Jedioth Chadashoth*, *Blumenthal's Neueste Nachrichten* and *Orient* (Haifa,
1942–43) are still not located anywhere.

**Access notes.** The HTML interface sits behind a browser-verification wall
that `curl` and WebFetch cannot pass — drive it through the dedicated Chrome,
exactly as with Cloudflare. Two doors are open without it: the **OAI-PMH
endpoint** (`/cm/oai`, sets incl. `ubffmcm`, `journal`; 481 journal records via
`ListRecords&metadataPrefix=oai_dc`) and a JSON API root at `/cm/api`.
Caution: `oai_dc` `publisher` usually names the *digitizing partner* (RWTH, the
Frankfurt library), not the place of publication — use the Places cloud
(`/cm/nav/cloud/place`) for provenance instead.

**The search is article/metadata level, not full text.** `Haifa` returns 47
article *titles*, overwhelmingly from *Palästina* and *Die Welt* (Berlin and
Vienna Zionist journals) on the harbour, the Technion and economics;
`Regierungskrankenhaus` returns 5, none Palestine-published. No hospital
material surfaced — but that is a property of the index, not proof of absence.
Using MB 1943–48 would need page-level harvesting, the same two-stage design as
Jrayed and JPress.

**ON HOLD (2026-08-26):** do not start the MB harvest. Sinai is checking
whether access already exists through the diasporic memory project (Yiftach
worked on MB there). Wait for that before harvesting from Compact Memory.

**Worth fetching regardless:** Fritz Lorch, "Die deutsche Kolonie Haifa in
Palästina" (*Palästina*, two articles) — the German Colony is where the
pre-1938 hospital stood.

## 4. Fraktur ſ-variant sweep
Only `Hoſpital` was probed (42 hits vs 1 for `Hospital`). Other non-final-s
words in the German corpus have not been swept.

## 5. The 1922–1930 gap
The government ran a Haifa hospital in requisitioned Borromäerinnen premises
until January 1922; our register opens 1930 in rented St. Luke's premises.
What happened between is still unevidenced.

## 6. The lazaret referral question — Israel State Archives
`lazaret_concordance.tsv` assembles what the press says; it does not settle it.
Nearly every attestation puts the Kerentina **beside** the Government Hospital
(its own director Isa Matta, its own doctor, its own telephone; Filastin of
11 September 1941 names hospital, health offices and Kerentina as three things;
the Palestine Post of 1933–34 has an Infectious Diseases Hospital at Haifa and a
Government Isolation Hospital on Mountain Street). One notice, al-Difa' of
22 August 1946, puts it inside. Working hypothesis: the lazaret was separate and
the 1946 phrasing is loose usage for the hospital's own Isolation department —
which the register's own Isolation ward would make natural. **Question stays
open until the Israel State Archives documents are read.**

Until it is settled, cholera, plague and smallpox cannot be read off the
admission register: it is probably not their denominator. The register-side
trace is in the README — the Isolation ward runs to 26 February 1940, survives
the Bat Galim move, and is extinct when the notebooks resume in 1944, with the
change falling inside the four-year gap.

---

## Downstream deliverables (decided 2026-08-26) — gated on MB

Nothing below starts until the *Mitteilungsblatt* picture is complete (item 3).
The German-press results stay where they are, in this directory's README, until
then. When MB closes, the accumulated press work feeds **two** products:

### A. A general history of the hospital — essay + timeline
Narrative synthesis across all four press languages plus the League of Nations
annual reports and the census package. The spine already assembled: the
Anglican St. Luke's mission hospital (closed 31 March 1929); the government's
own 1918–January 1922 hospital in requisitioned Borromäerinnen premises; the
register opening 1930 in **rented** St. Luke's premises on Mountain Road; the
capacity steps 30 → +50 (early 1933) → +20 (1935) → +22 (1936); the move to Bat
Galim in **October 1938** and its opening on 21/22 December 1938 (the two
sources disagree — reconcile before citing); 225 beds thereafter; occupation
and looting at the 1948 handover. The timeline is the same material in
date order, and should carry the bed-count steps, since no admissions or
occupancy trend is readable without them.

### B. A newspaper-source reader, published on the explorer site
The **complete** list of press sources, presented for reading rather than as a
data dump — the passages themselves with translation and register context, as
in `paper/press-register-cases.md`. Covers Arabic (Filastin, al-Difa'), English
(Palestine Post, Palestine Bulletin), Hebrew (JPress titles), German (the four
Palestine titles, plus MB), and the archival sources.

**Privacy is settled, and is not a blocker (ruled 2026-08-26).** Presenting
press passages next to their matched register rows is approved, **including on
the public explorer site**. Names published in the newspapers are usable. Do not
re-litigate this or design around it.

What remains open is **editorial, not ethical**: whether the matched pairs
belong in the Cathedra article is a separate decision, to be taken later.
