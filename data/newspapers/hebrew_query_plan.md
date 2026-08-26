# Hebrew query plan: raising the recall floor

**Stage D (diagnostics) was executed on 2026-08-26 and its results are below.**
Stage H (harvests) has not been run. Every command here is meant to be run
unmodified. Nothing here touches `app/` or `pipeline/build.py`.

## The premise this plan started from was wrong

It was drafted on the understanding that *Veridian phrase queries of four or
more tokens silently degrade to an AND of their tokens*. **They do not.**
Measured at both page and article level:

| query | tokens | hits |
|---|---|---|
| `"בית החולים הממשלתי"` | 3 | 694 |
| `"בית החולים הממשלתי בחיפה"` | 4 | 65 |
| `"בית החולים הממשלתי החדש בחיפה"` | 5 | 2 |
| `"בית החולים הממשלתי בחיפה ירושלים תל אביב יפו"` | 8 | **0** |

The last line is decisive. Those eight tokens co-occur constantly in this
corpus — an AND would return thousands. It returned nothing, so the phrase held
as a phrase. The four-token query returns 65 at page level and 65 at article
level: identical, and far *below* the three-token phrase, which is what a
narrowing phrase does and the opposite of what degradation does.

**What misled the draft.** `heb_newhosp.tsv` shows the search highlighter
landing on scattered single tokens — on Beit She'an (`בית שאן`) for a hospital
query, on the Hadassah hospital, on `בחיפה` alone. That was read as a phrase
dissolving. The simpler explanation is the right one: **that query was never
quoted.** Bare tokens are ANDed, scattered highlighting is exactly what an AND
looks like, and its article-level ids are incidental. The engine behaved
correctly throughout; the inference did not.

The practical consequence is good news and it simplifies everything below.
Precision is available at any phrase length, so no query in this plan needs to
be labelled a "recall harvest wearing a precision query's clothes." That whole
category, and the branching it forced, is gone.

## What the diagnostics did establish

**1. The 702 was an article-level number.** The same phrase returns **694** at
page level. One page can carry several matching articles, hence the gap.

This is the one correction that changes a reported figure. The Arabic stage-1
counts (2,322 Filastin, 1,593 al-Difa') are page-level, so the Hebrew number
that belongs beside them is **694**. Quote 702 only when counting articles, and
say which is which.

**2. The abbreviation mark is stripped at index time.** All three spellings
return the identical total *and the identical per-title distribution*:

| query | hits |
|---|---|
| `ביה״ח` (gershayim, U+05F4) | 3,580 |
| `ביה"ח` (ASCII quote) | 3,580 |
| `ביהח` (no mark at all) | 3,580 |

They are one index term. **One query reaches every punctuation variant,
including whatever Optical Character Recognition (OCR) dropped.** The predicted
quoting trap — a bare `"` opening an unterminated phrase — did not materialise
either; the ASCII form queries cleanly.

**3. But the mark does not *split* the token.** `"ביה ח"` as a phrase returns
115, not 3,580. So `ביה` is not a route to the abbreviation: as a bare token it
returns 33,170, mostly from Yiddish titles (`frw`, `tjm`, `dertog`, `hajn`)
where it is simply a common sequence. The split-token harvest the draft
proposed is dead, and nothing is lost by killing it, because finding 2 makes it
unnecessary.

**4. The abbreviation is where the recall was hiding.** `ביה״ח` alone returns
3,580 pages against the spelled-out phrase's 694 — five times as many. Narrowed
to the hospital proper, `"ביה״ח הממשלתי"` returns **224** pages, a 32% addition
to the baseline before any deduplication.

**5. Hebrew prefixes are separate index terms, as the Arabic ال is.** The
plan's structural premise holds and enumeration is still required:

| pair | hits |
|---|---|
| `הממשלתי` / `ממשלתי` | 30,070 / 14,184 |
| `בחיפה` / `חיפה` | 74,727 / 118,173 |
| `בית־החולים` (maqaf) / `"בית החולים"` (spaced) | 2,731 / 9,956 |

The maqaf line matters most, and it works by the same mechanism as finding 2:
**the maqaf is stripped too.** `ביתהחולים`, written with no separator at all,
returns 2,731 — identical to `בית־החולים`, facets included. So the maqaf form
is a *single index token*, genuinely disjoint from the two-token sequence
`בית החולים`, and the spaced phrase cannot reach it. The maqaf harvest is
required rather than optional.

**6. The plan only sees the hospital when it is called governmental.** The
spaced phrase with the town but *without* the adjective —
`'"בית החולים" בחיפה'` — returns **5,796** pages, against 694 that also carry
`הממשלתי`. Most of that gap is Hadassah, Rothschild and Elisha. But some of it
is our hospital, named in passing as simply "the hospital in Haifa," and no
query in stage H can see those. See H9 and the note attached to it: this is a
deliberate boundary, not an oversight, and it is where the next increment of
recall lives.

## Method inherited from the Arabic side

`data/newspapers/README.md` records the decisions taken for Filastin and
al-Difa'. This plan mirrors them so the two languages are comparable:

| Arabic decision | Hebrew equivalent |
|---|---|
| Stage 1 is server-side and **page-level** | same — and finding 1 makes this load-bearing, not cosmetic |
| Precision comes from a **local pass over harvested text** | same; stage 2 is not optional |
| Definite article indexed **attached** | confirmed for Hebrew `ה`/`ב` by finding 5 |
| Adjectival form harvested separately (`*_adj.tsv`) | abbreviated form harvested separately (`heb_abbrev.tsv`) |
| No regular expressions; `*` truncates right only | same engine; Hebrew prefixes sit at the wrong end, hence enumeration |

## Operational notes

- **`--site nli`** on every command. Switching sites renavigates the shared
  Chrome tab, so run the batch in one sitting.
- **Date filters are year-granular.** `--from-year`/`--to-year` map to
  `dafyq`/`datyq`; the month and day parameters exist in the API but are not
  exposed by the search subcommand. Cut the October 1938 Mountain Road →
  Bat Galim seam locally on the `date` column.
- **Raise `--max`.** The default is 1000 and several harvests below exceed it.
- **Shell quoting.** `txq` is sent verbatim, so a phrase needs literal double
  quotes inside single shell quotes: `'"בית החולים הממשלתי"'`.
- **The facet caps at 15** and prints only without `--pub`. Take the full title
  list from the harvest file: `cut -f4 … | sort | uniq -c | sort -rn`.
- **No `--pub` on any query.** Constraining by title would re-impose the floor
  being lifted.

---

# Stage H — harvests

Page level throughout. `--max 5000` throughout.

```sh
J="python3 pipeline/jrayed.py --site nli search"
Y="--from-year 1930 --to-year 1948 --max 5000"
D="data/newspapers"
```

### H1 — baseline, spelled out

```sh
$J '"בית החולים הממשלתי"' $Y --out $D/heb_govhosp_phrase.tsv
```

Expect 694. The control.

### H2 — spelled out, with the town

```sh
$J '"בית החולים הממשלתי בחיפה"' $Y --out $D/heb_govhosp_haifa_phrase.tsv   # 65
$J '"בית החולים הממשלתי" בחיפה' $Y --out $D/heb_govhosp_haifa.tsv
```

Both are legitimate now that phrases hold at four tokens. The first is the
precise form (65 pages, the town named immediately after the hospital). The
second is broader — phrase AND a separate token, catching the town named
anywhere on the page — and is the direct analogue of the Arabic stage-1
`مستشفى الحكومة` + `حيفا`. Run both; the gap between them is itself informative.

**Trap:** both miss any report that names Haifa only in the dateline.

### H3 — the abbreviation *(the recall gain)*

```sh
$J '"ביה״ח הממשלתי"'        $Y --out $D/heb_abbrev_phrase.tsv        # 224
$J '"ביה״ח הממשלתי" בחיפה'  $Y --out $D/heb_abbrev_haifa.tsv
$J 'ביה״ח בחיפה'            $Y --out $D/heb_abbrev_haifa_broad.tsv
```

By finding 2, `ביה״ח` here also covers `ביה"ח` and `ביהח` — no separate runs
needed. All three are precision-grade.

**Trap:** the abbreviation is shared by every hospital. Haifa's Hadassah
(`הדסה`), Rothschild (`רוטשילד`) and Elisha (`אליישע`) are all `ביה״ח` too, and
that filtering belongs to stage 2, not to the query.

### H4 — the short abbreviation

```sh
$J '"בי״ח הממשלתי"' $Y --out $D/heb_abbrev_short.tsv
```

`בי״ח` alone returns 13,833, heavily Yiddish (`tjm`, `morgnfreiheit`,
`dertog`, `idisheshtime`). Bounded by the adjective it is usable; unbounded it
is not.

### H5 — the maqaf form *(required, per finding 5)*

```sh
$J '"בית־החולים הממשלתי"'       $Y --out $D/heb_maqaf.tsv
$J '"בית־החולים הממשלתי" בחיפה' $Y --out $D/heb_maqaf_haifa.tsv
```

2,731 pages carry the single token `ביתהחולים`, and the spaced phrase does not
reach any of them.

**Quote these.** An earlier draft left H5 unquoted, which would have made it an
AND of `ביתהחולים` with `הממשלתי` while H1 was a phrase — inflating the maqaf
count against the spaced one for reasons having nothing to do with the press.
The two harvests must be the same shape of query to be compared.

### H6 — indefinite construction

```sh
$J '"בית חולים ממשלתי"' $Y --out $D/heb_indef.tsv
```

Common in early-1930s copy and entirely absent from the 694.

### H7 — the recall ceiling

```sh
$J 'ביהח בית חולים החולים ממשלתי הממשלתי חיפה בחיפה' $Y --any \
   --out $D/heb_recall_full.tsv
```

`--any` sets `t=1`, an OR of every token identified. Not a query to read the
results of — it measures the room above 694 and yields the complete title list.

**Trap:** if stderr shows `5000/<larger>`, the ceiling was not reached; report
it as a lower bound and say so.

### H9 — the unqualified hospital *(the boundary of this plan)*

```sh
$J '"בית החולים" בחיפה'   $Y --out $D/heb_unqualified.tsv        # 5,796
$J 'ביתהחולים בחיפה'      $Y --out $D/heb_unqualified_maqaf.tsv
$J 'ביהח בחיפה'           $Y --out $D/heb_unqualified_abbrev.tsv
```

Everything above requires the word *governmental*. These three do not — they
ask only for a hospital and the town. The first alone is 5,796 pages against
the 694 baseline.

**This is the plan's real recall boundary, and it is a deliberate one.** Most
of those 5,796 are Haifa's other hospitals, and no query can tell them apart —
only stage 2 can. Two ways to treat it, and the choice is the historian's, not
the engine's:

- **Leave it out.** Report 694 + 224 + the maqaf increment as the count of
  press references to the *Government* Hospital, and say plainly that reports
  naming it without the adjective are excluded. Defensible, and comparable to
  the Arabic side, which was also built on a qualified phrase.
- **Harvest it and filter locally.** Run these three, take the full text, and
  have stage 2 keep only what a Government Hospital reading survives — a
  dateline, a named ward, a case that matches the register. Far more work, and
  the only route to the reports that call it simply "the hospital."

Do not report a number from H9 without saying which of the two was done.

**The mirror-image caution to the Arabic README's.** There, unqualified
*the Government Hospital* risked belonging to another town. Here, unqualified
*the hospital in Haifa* risks belonging to another hospital. Same failure,
opposite axis.

### H8 — premises follow-up *(optional, mirrors session C)*

```sh
$J 'דרך ההר חיפה חולים'        $Y --out $D/heb_mountainroad.tsv
$J '"בבת גלים" חולים ממשלתי'   $Y --out $D/heb_batgalim.tsv
$J '"בת־גלים" חולים ממשלתי'    $Y --out $D/heb_batgalim_maqaf.tsv
```

The maqaf variant is included because of finding 5.

---

# Stage 2 is not optional

As the Arabic README concludes: **search snippets are useless for filtering.**
Every harvest must go through the full-text harvester and a local regular
expression before any count is reported as a finding. The Hebrew pass must
separate:

- **Other towns' government hospitals** — Jaffa, Jerusalem, Safed, Tiberias,
  Acre. Same hazard the Arabic README flags; check the dateline.
- **Haifa's other hospitals** — `הדסה`, `רוטשילד`, `אליישע`. They share the
  abbreviation completely, so H3 and H4 cannot be reported without this.
- **Beit She'an** — `בית שאן`, which any unquoted `בית` query will match.
- **OCR damage.** The snippets show `נית־החולים`, `בי־תהחולע`, `בית־החולם`.
  The local pass should be tolerant in a way the engine will not be.

---

# Stage D results (run 2026-08-26, page level unless noted)

| probe | query | total | what it shows |
|---|---|---|---|
| D1 | `"בית החולים הממשלתי"` | **694** | the Arabic-comparable baseline |
| D2 | same, `--level Logical` | **702** | the figure previously quoted |
| D3 | `בית החולים הממשלתי` (unquoted) | 11,599 | phrase matching is real: 17× the quoted form |
| D4 | `"בית החולים הממשלתי בחיפה"` | 65 | 4-token phrase holds (65 at article level too) |
| — | 5-token phrase | 2 | holds |
| — | 8-token impossible phrase | **0** | holds — no degradation at any length tested |
| D5 | `בית־החולים` | 2,731 | distinct from the spaced form |
| — | `ביתהחולים` | 2,731 | identical to D5: the maqaf **is stripped**, one token |
| D6 | `"בית החולים"` | 9,956 | denominator |
| — | `"בית החולים" בחיפה` | **5,796** | the unqualified population H1–H6 cannot see (H9) |
| D7 | `ביה״ח` | 3,580 | |
| D8 | `ביה"ח` | 3,580 | identical to D7, facets included |
| D9 | `ביה` | 33,170 | a common token, not a route to the abbreviation |
| — | `"ביה ח"` | 115 | the mark does **not** split |
| D10 | `ביהח` | 3,580 | the mark **is stripped**; D7 = D8 = D10 |
| D11 | `בי״ח` | 13,833 | heavily Yiddish; `ביח` not run |
| D12 | `הממשלתי` / `ממשלתי` | 30,070 / 14,184 | prefix is part of the token |
| D13 | `בחיפה` / `חיפה` | 74,727 / 118,173 | same |
| — | `"ביה״ח הממשלתי"` | **224** | the recall gain, before deduplication |

**Publication ids** (D1 facet, page level; the 15 shown sum to 661 of 694, so
~33 hits sit in an unlisted tail):

`dav` 193 · `haretz` 147 · `hzh` 92 · `hbkr` 86 · `hmf` 45 · `ahr` 26 ·
`dhy` 14 · `hegeh` 13 · `itonmeyuhad` 8 · `yomyom` 7 · `ytlv` 7 ·
`hayomjlm` 6 · `hazmantlv` 6 · `mar` 6 · `haolam` 5

Eight were not recoverable from `heb_newhosp.tsv`: `ahr`, `dhy`, `hegeh`,
`itonmeyuhad`, `yomyom`, `hayomjlm`, `hazmantlv`, `mar`. Later probes surfaced
more, `tsohorayimhaifa` (a Haifa title) among them. The facet caps at 15, so the
full census still comes from H7.

---

# Stage H results (run 2026-08-26, page level, 1930–48)

| harvest | file | pages | new vs the 694 baseline |
|---|---|---:|---:|
| H1 spelled out `"בית החולים הממשלתי"` | `heb_govhosp_phrase.tsv` | 694 | — |
| H3a abbreviated `"ביה״ח הממשלתי"` | `heb_abbrev_phrase.tsv` | 224 | **216 of 224** |
| H5a maqaf `"בית־החולים הממשלתי"` | `heb_maqaf.tsv` | 220 | **209 of 220** |
| H6 indefinite `"בית חולים ממשלתי"` | `heb_indef.tsv` | 59 | **55 of 59** |
| H4 short `"בי״ח הממשלתי"` | `heb_abbrev_short.tsv` | 6 | 6 of 6 |
| **union, deduplicated on `id`** | | **1,175** | **+481 (+69%)** |

The three added forms are almost entirely *disjoint* from the spelled-out
phrase — 216 of 224, 209 of 220, 55 of 59 lie outside it. The floor was not a
rounding error: **481 pages, two in five of the total, were invisible to the
query that produced the 702.**

Restricted to pages that also name Haifa:

| harvest | file | pages |
|---|---|---:|
| H2b spelled out + `בחיפה` | `heb_govhosp_haifa.tsv` | 524 |
| H3b abbreviated + `בחיפה` | `heb_abbrev_haifa.tsv` | 194 |
| H5b maqaf + `בחיפה` | `heb_maqaf_haifa.tsv` | 176 |
| **union** | | **878** |
| H2a `"בית החולים הממשלתי בחיפה"` (town inside the phrase) | `heb_govhosp_haifa_phrase.tsv` | 65 |

And the unqualified sweep (H9), which requires no adjective:

| harvest | file | pages |
|---|---|---:|
| `"בית החולים" בחיפה` | `heb_unqualified.tsv` | 5,796 |
| `ביה״ח בחיפה` | `heb_abbrev_haifa_broad.tsv` | 2,258 |
| `ביתהחולים בחיפה` | `heb_unqualified_maqaf.tsv` | 1,461 |
| **union** | | **8,587** |

Of those, **7,692 are pages the qualified set never sees.** H7's ceiling, the
OR of every token, is **305,730** — a bound, not a count of anything.

## The headline number

> **878** — the union of the qualified forms restricted to pages naming Haifa —
> is the figure comparable to the Arabic **2,322** (Filastin) and **1,593**
> (al-Difa'). Those were built the same way: a qualified hospital phrase AND the
> town, at page level.
>
> **1,175** is the union without the Haifa restriction: the Government Hospital
> named anywhere, including the many pages that mean Haifa's without saying so.
>
> **694 / 702** was the floor — page and article level respectively.
>
> **8,587** and **305,730** are bounds. Never report either as a count of
> references to this hospital.

All three qualified-union figures are still **pre-stage-2**: no local pass has
yet removed other towns' government hospitals. Treat them as harvest sizes, not
as findings.
