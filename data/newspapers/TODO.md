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
