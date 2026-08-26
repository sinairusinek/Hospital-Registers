# Mitteilungsblatt / Compact Memory — handoff

**Written 2026-08-26 by session `hospital-registers-fd`, for integration in a
new session.** Everything below is either committed or sitting in a local file
named here. Nothing is left only in a session transcript.

---

## 1. What is committed

`a40fadb` — the Compact Memory harvest: 22 `cm_*.tsv` hit lists,
`pipeline/compactmemory.py` (the SRU client, with the traps documented in its
docstring), and the rewritten item 3 of `TODO.md`.

`17ad72d` — committed by a *different* session (`hospital-registers-96`),
already carries the full MB write-up in `data/newspapers/README.md` under the
heading "Session E — the *Mitteilungsblatt*, through Compact Memory's SRU
endpoint". **Read that section first**; it is the fullest account and this note
does not repeat it.

## 2. What is edited but NOT published — the one thing that needs your hand

`paper/hospital-history.html` ("Mountain Road to Bat Galim") has **four edits
applied and verified locally, which are not live.** `paper/` is gitignored, so
these exist only in that local file on this machine.

1. **§10, new subsection "And the press dates the gap from outside"** — the
   Lipschitz item: German quotation, translation, citation (MB der Hitachdut
   Olej Germania we Austria, 8 March 1940, p.4, page 12740472), and the
   argument that it fixes the gap from outside.
2. **Coverage table, 1940 row** — notebook cell now reads `24 — ends 1 March`,
   and a new gap row `1940 (from 2 Mar)` sits above 1941.
3. **Coverage table footnote** — states the gap opens 2 March 1940, not 1941;
   names Notebooks 24 and 29; notes NB25 (Atlit) covers part of the rest of
   1940 but is excluded; cross-refers §10.
4. **§14, new open item** — the 187 unread Mandate-era `Krankenhaus`×`Haifa`
   issues plus 54 in `cm_haifa_spital.tsv`, pointing at `cm_kh_and_haifa.tsv`.

HTML was validated after editing: no unclosed tags, blockquotes balanced
(8 open / 8 close), `<blockquote>` used rather than a `.quote` class that does
not exist in this document's CSS.

### The republish is blocked and needs `force:true`

Artifact URL:
`https://claude.ai/code/artifact/f0cc1896-1a84-4572-a14d-b93d2648da2b`

Publishing was refused four times on a view-tracking check that could not be
cleared, even after: reading the full live source, diffing it, `Read`-ing every
line of the saved copy, and re-fetching the URL in the required order. **This is
the same failure `project_hospital_history_document` records from the previous
session, which also needed `force:true`.**

**Forcing is safe here, and this was checked rather than assumed.** A direct
diff of the live version against the local edit base showed the live page
differs *only* by the four edits above, plus the publisher's own injected
frame-runtime wrapper and trailing `</body></html>`. No other session has
touched the artifact; nothing would be discarded but an older copy of the same
document. Sinai has not yet given the explicit confirmation `force:true`
requires — **ask before using it.**

Publish with the URL passed explicitly, or it will create a *separate*
artifact:

```
Artifact(action:"publish",
         file_path:"paper/hospital-history.html",
         url:"https://claude.ai/code/artifact/f0cc1896-1a84-4572-a14d-b93d2648da2b",
         force:true)
```

## 3. What the harvest found

Two findings, both reconciled against the register, both already written up in
the README section named above.

- **A death inside the archival gap.** MB, 8 March 1940: Lipmann Lipschitz, 27,
  from Latvia, died in the Regierungskrankenhaus in Haifa of injuries from the
  Land Transfer Regulations demonstrations; Tuesday evening = 5 March 1940.
  *Jüdische Weltrundschau* carries the same event on 11 March. Notebook 24 ends
  1 March 1940 and the general series resumes only with Notebook 29 on 8
  February 1944 — so this lands four days inside the gap and cannot be checked
  against the register at all. **That is its value**: it establishes from
  outside that the hospital was admitting and its deaths were being reported,
  so the missing notebooks are missing, not never-written. It also moves the
  gap's start from the repo's habitual "1941–1943" to **2 March 1940**.
- **The January 1948 removal.** MB, 23 January 1948, p.4, "Haifaer Notizen",
  datelined Haifa 11.1.48: "die jüdischen Kranken aus dem Regierungskrankenhaus
  herausgenommen werden". The register agrees to the month — Jewish admissions
  fall from a steady 5–7% to 1, 2, 0, 0 across Jan–Apr 1948, none after 23
  February. Already in §09 of the history document, and load-bearing for §13.

## 4. Three query traps — the methodological result

Measured, not assumed, after asking whether five mentions in sixteen years
could really be all. Each silently turns a real corpus into an apparent
absence.

- **Hyphenation splits German compounds and the index does not rejoin them.**
  `Regierungskrankenhaus` = 109 documents; the adjacency phrase
  `"Regierungs Krankenhaus"` finds **44 more the single token cannot see**
  (`"Kranken haus"` = 1,321). One of those 44 is a contemporaneous Mendelsohn
  attribution, June I 1938, p.8 (page 12724706) — **but its siting is wrong**
  ("auf der Höhe des Carmel"; Bat Galim is at sea level). Recorded as a lead,
  not a fact: it bears on how firmly the Mendelsohn attribution should be
  stated, and it is the kind of conflation later sources could have inherited.
- **Display type is largely unread by this OCR.** `"Haifaer Notizen"`, a
  running column head, indexes in exactly one issue. Items are findable only
  through body text.
- **Umlaut is not folded to `ae`.** `Borromäerinnen` = 1, `Borromaeerinnen` =
  10. Inflection *is* stemmed (`Krankenhauses` ≡ `Krankenhaus`). Query both.

**The conclusion these support:** no Haifa hospital is much named in this
corpus — not the Rothschild, not Elisha, not Bnai Zion. Against that baseline
five or six mentions of the Government Hospital is not an anomaly to explain
away; it is the corpus's normal rate, and more than the Rothschild gets. The
one institution mentioned often (42 issues) is Kupath Cholim — the sick fund,
the thing readers actually dealt with. All counts are **floors**, for the OCR
reasons above.

## 5. Still open

- **The 187 Mandate-era `Krankenhaus`×`Haifa` issues in
  `cm_kh_and_haifa.tsv` (1,023 rows), plus 54 in `cm_haifa_spital.tsv`, are
  unread page by page.** Only the phrase-level and `Regierungskrankenhaus`×
  `Haifa` subsets were read. The hospital may well be discussed there without
  being named. The hit lists already name the pages to fetch, so this is
  mechanical.
- **Compact Memory serves page images openly but no text** — stage 2 is reading
  images. If Yiftach's diasporic-memory access carries **OCR text**, it is
  still worth having for that reason alone. The old hold pending that access no
  longer blocks anything.
- ***Jedioth Chadashoth*, *Blumenthal's Neueste Nachrichten*, *Orient*** (Haifa,
  1942–43) remain unlocated in any archive.

## 6. Two housekeeping notes

- **"Session E" is used three times** in `data/newspapers/README.md` for three
  different workstreams: the Palestine Post 1941–48 (line ~757), the
  Mitteilungsblatt (line ~819), and the Hebrew JPress work that session `-96`
  calls its own. Worth renaming before any of these labels get cited.
- **Five hospital-registers sessions were live on this repo** on 2026-08-26.
  `pipeline/year_audit.py`, the `app/` changes and `pipeline/build.py` are
  other sessions' uncommitted work and were deliberately **left out** of
  `a40fadb`; it was staged by explicit path, never `git add -A`.
