# Hebrew query plan: raising the recall floor

**Status:** written offline, not executed. Every command below is meant to be
run **unmodified** by whichever session owns the dedicated Chrome instance.
Nothing here touches `app/` or `pipeline/build.py`.

## Why this plan exists

The Hebrew figure we currently hold — **702 hits for `"בית החולים הממשלתי"`,
1930–48, across 30 titles** — is a floor, not a measurement. Three things were
never probed:

1. **The abbreviation.** Hebrew press of the Mandate decades writes the
   hospital far more often as `ביה"ח` / `בי"ח` than in full. A query for the
   spelled-out phrase cannot see any of them.
2. **Gershayim and maqaf.** The abbreviation mark is `״` (U+05F4) in properly
   typeset text, a plain ASCII `"` in most digitised text, and frequently
   nothing at all in Optical Character Recognition (OCR) output. The compound
   noun is written `בית־החולים` with a maqaf (`־`, U+05BE) at least as often as
   `בית החולים` with a space.
3. **Phrase degradation.** Veridian phrase queries of four or more tokens
   silently stop behaving as phrases and become an AND of the tokens.

Point 3 is not a suspicion — it is visible in a file already in this
directory. `heb_newhosp.tsv` (106 rows) was harvested with a long phrase, and
its snippets show the highlighter landing on scattered single tokens:

```
"...אירעו <b>בחיפה</b> כמה מקרים של טיפוס הבטן..."          ← only בחיפה matched
"...ליד <b>בית</b> שאן־עוד שוטר ערבי נפצע קשה"              ← only בית matched (Beit She'an!)
"...חגגה חיפה את חג חנוכת בנין <b>בית</b> <b>החולים</b> ""הדסה""..."  ← Hadassah, not the Government Hospital
```

A phrase query cannot return Beit She'an for a hospital phrase. The query
degraded. So a four-token phrase is not a broken precision query — it is a
**recall harvest wearing a precision query's clothes**, and it must be labelled
and used as such.

## Method inherited from the Arabic side

`data/newspapers/README.md` records the decisions taken for Filastin and
al-Difa', and this plan deliberately mirrors them so the two languages are
comparable:

| Arabic decision | Hebrew equivalent here |
|---|---|
| Stage 1 is server-side and **page-level** (`--level Page`), phrase + AND | same; every harvest below is page-level |
| Precision comes from a **local pass over harvested text**, not from the query | same; stage 2 is not optional |
| Definite article indexed **attached** (`ال`/`و` are part of the token) | Hebrew `ה`/`ב`/`ל`/`מ`/`ו` are likewise part of the token, so each prefixed form is a separate index term and must be enumerated |
| The adjectival form `المستشفى الحكومي` harvested **separately** (`*_adj.tsv`) | the abbreviated forms `ביה"ח` / `בי"ח` harvested separately (`heb_abbrev_*.tsv`) |
| Unqualified "the Government Hospital" may be Jaffa, Hebron or Jerusalem — check the dateline | identical hazard: `בית החולים הממשלתי` unqualified may be Jaffa, Jerusalem, Safed, Tiberias or Acre |
| No regular expressions; `*` truncation only | same engine, same limit — and `*` truncates on the **right** only, which is exactly the wrong end for Hebrew prefixes |

That last row is the structural constraint of the whole plan. Because
truncation cannot reach a prefix, `ממשלתי` and `הממשלתי` and `בחיפה` and `חיפה`
must each be asked for by name.

## Operational preconditions

- **`--site nli`** on every command. The Hebrew press lives behind the
  `www.nli.org.il` front door, not `jrayed.org`. Switching sites renavigates
  the Chrome tab (`site()` → `_find_tab()` → `_resolve_challenge()`), so run
  this whole batch in one sitting rather than interleaving it with Jrayed work.
- **Date filters are year-granular only.** `pipeline/jrayed.py` wires
  `--from-year`/`--to-year` to `dafyq`/`datyq`; the month and day parameters
  (`dafmq`, `dafdq`) exist in the API but are **not exposed** by the search
  subcommand. Any Mountain-Road-vs-Bat-Galim split (the seam is October 1938)
  must be made locally on the `date` column, not in the query.
- **`--max` must be raised.** The default is 1000 and the baseline alone is
  702; the recall harvests will exceed it. Every harvest below sets
  `--max 5000`.
- **Shell quoting.** `txq` is sent verbatim. A Veridian phrase needs literal
  double quotes *inside* the argument, so the outer shell quotes must be
  single: `'"בית החולים הממשלתי"'`. This collides head-on with the ASCII-quote
  abbreviation form — see the trap on D6.
- **The title census is free.** `cmd_search` prints a per-publication facet to
  stderr only when `--pub` is absent, and only the top 15. Do not rely on it
  for the 30-title list. Take the complete list from the harvest file itself:
  `cut -f4 heb_recall_full.tsv | sort | uniq -c | sort -rn`.
- **No `--pub` on any query below.** We do not yet have a trustworthy list of
  the 30 Hebrew publication ids; constraining by `--pub` now would re-impose
  the floor we are trying to lift. The ids confirmed from `heb_newhosp.tsv` so
  far are `dav`, `haretz`, `haolam`, `hbkr`, `hzh`, `hmf`, `ytlv`, `hashaah`,
  `kolisraeljlm`. Treat that as a fragment, and let step A produce the rest.

---

# Stage D — diagnostics (13 requests, ~13 seconds)

These settle *how the engine tokenises Hebrew* before any bulk harvesting is
committed. Each uses `--max 1`, which issues exactly **one** request and prints
`1/<TOTAL>` to stderr — the total is the whole point, the row is discarded.
Record every total in the results table at the foot of this file.

```sh
cd /Users/sinairusinek/Documents/GitHub/Hospital-Registers
J="python3 pipeline/jrayed.py --site nli search"
Y="--from-year 1930 --to-year 1948 --max 1"
```

| # | command | what it decides | expected trap |
|---|---|---|---|
| D1 | `$J '"בית החולים הממשלתי"' $Y` | reproduces the 702 baseline at page level | if this is **not** 702, the baseline was taken at a different `--level` or a different date range; stop and pin that down before continuing |
| D2 | `$J '"בית החולים הממשלתי"' $Y --level Logical` | the same baseline at article level | pins which of the two numbers "702" actually was. The Arabic corpus is page-level, so **page** is the comparable figure; record both |
| D3 | `$J 'בית החולים הממשלתי' $Y` | the same three tokens **unquoted** (AND) | D3 ≫ D1 means phrase matching is genuinely active at three tokens. D3 ≈ D1 means quoting is being ignored altogether and the 702 was never a phrase result |
| D4 | `$J '"בית החולים הממשלתי בחיפה"' $Y` | the four-token phrase | **the degradation test.** A true phrase must return ≤ D1. If it returns *more* than D1, degradation is confirmed and this string is a recall harvest, not a precision query |
| D5 | `$J 'בית־החולים' $Y` | is the maqaf a token separator? | if this ≈ D6 below, the maqaf splits and `בית־החולים` is already covered by the spaced phrase. If it returns its own large population, the maqaf binds into a **single distinct token** that the 702 never saw |
| D6 | `$J '"בית החולים"' $Y` | spaced-compound population | a very large number; it is a denominator, not a finding |
| D7 | `$J 'ביה״ח' $Y` | the gershayim abbreviation (U+05F4) | the single most likely source of missed recall |
| D8 | `$J 'ביה"ח' $Y` | the ASCII-quote abbreviation | **quoting trap.** Veridian may read that bare `"` as opening an unterminated phrase, returning 0 or an error rather than a token match. If it does, the ASCII form is not directly queryable and D9 becomes the only route to it |
| D9 | `$J 'ביה' $Y` | does `״` split tokens? | if D9 is large and roughly ≥ D7, the abbreviation mark is a separator and `ביה` alone reaches **every** punctuation variant at once — the ASCII form, the gershayim form and the OCR-dropped form together. This is the key result of the whole diagnostic stage |
| D10 | `$J 'ביהח' $Y` | mark dropped entirely by OCR | expect small but non-zero; unreachable from any other query |
| D11 | `$J 'בי״ח' $Y` and `$J 'ביח' $Y` | the shorter abbreviation | `ביח` will also collide with ordinary words; treat as harvest-grade only |
| D12 | `$J 'הממשלתי' $Y` then `$J 'ממשלתי' $Y` | the definiteness axis | two separate populations, not one. The indefinite `בית חולים ממשלתי` construction is common in early-1930s copy and is entirely absent from the 702 |
| D13 | `$J 'בחיפה' $Y` then `$J 'חיפה' $Y` | the locative axis | likewise two populations. Note also that the highlighter in `heb_newhosp.tsv` spans `בחיפה.` and `בחיפה,` including the punctuation, which indicates trailing punctuation is stripped at index time — so no separate comma/full-stop variants are needed |

**Decision rule out of stage D.** If D9 shows that the abbreviation mark
separates tokens, run harvest H3 and skip H4/H5. If it does not, H3 is useless
and H4/H5 must each be run in full.

---

# Stage H — harvests

Page level throughout, to match Arabic stage 1. Each writes a TSV alongside the
existing files.

```sh
J="python3 pipeline/jrayed.py --site nli search"
Y="--from-year 1930 --to-year 1948 --max 5000"
D="data/newspapers"
```

### H1 — baseline, kept for comparison

```sh
$J '"בית החולים הממשלתי"' $Y --out $D/heb_govhosp_phrase.tsv
```

Three tokens, below the degradation threshold: **a genuine phrase query, precision-grade.**
This is the 702, written down properly this time. Not a harvest — the control.

### H2 — phrase plus detached locative

```sh
$J '"בית החולים הממשלתי" בחיפה' $Y --out $D/heb_govhosp_haifa.tsv
```

The correct way to add the town. A three-token phrase **AND** a separate token
stays inside the phrase limit, so this does **not** degrade — where D4's
four-token phrase does. This pair is the direct structural analogue of the
Arabic `مستشفى الحكومة` + `حيفا` stage-1 query, and is the number to quote
beside 2,322 and 1,593.

**Trap:** it will still miss any article that names Haifa only in the dateline
and never in the body. Do not read a low count as absence.

### H3 — abbreviation via the split-token route *(run only if D9 says the mark separates)*

```sh
$J 'ביה הממשלתי' $Y --out $D/heb_abbrev_split.tsv
$J 'ביה חיפה'    $Y --out $D/heb_abbrev_split_haifa.tsv
```

**Recall harvest, not precision.** `ביה` as a bare token also matches the
opening of `ביהדות`, `ביהודה`, `ביהודים` — and if `ביה` is a token in its own
right, `בית` truncated by bad OCR lands there too. Filtering is stage 2's job.
The AND term is what keeps the yield usable.

### H4 — abbreviation, gershayim form

```sh
$J 'ביה״ח' $Y --out $D/heb_abbrev_gershayim.tsv
$J 'בי״ח'  $Y --out $D/heb_abbrev_short_gershayim.tsv
```

One or two tokens; no degradation possible. **Precision-grade** — every hit is
genuinely an abbreviated hospital reference, though not necessarily *this*
hospital. Expect heavy contamination from Hadassah, Rothschild and Elisha, all
of which were Haifa hospitals in these years and all of which are written the
same way.

### H5 — abbreviation, ASCII-quote and bare forms

```sh
$J 'ביה"ח' $Y --out $D/heb_abbrev_ascii.tsv     # see D8: may return 0 or error
$J 'ביהח'  $Y --out $D/heb_abbrev_bare.tsv
```

The second is small and unreachable any other way. Run it regardless of what
D9 said; it costs one request.

### H6 — indefinite and adjectival constructions

```sh
$J '"בית חולים ממשלתי"' $Y --out $D/heb_indef.tsv
$J 'ממשלתי חיפה חולים'  $Y --out $D/heb_indef_and.tsv
```

The first is a clean three-token phrase. The second is three bare tokens
ANDed — **harvest-grade**, deliberately, to catch every word-order and
punctuation variant the phrase forms cannot express. `ממשלתי` alone also picks
up government *schools*, *offices* and *land*; that is expected and is stage
2's problem.

### H7 — maqaf form *(run only if D5 showed a distinct population)*

```sh
$J 'בית־החולים הממשלתי' $Y --out $D/heb_maqaf.tsv
```

### H8 — the deliberate recall ceiling

```sh
$J 'ביה בית חולים החולים ממשלתי הממשלתי חיפה בחיפה' $Y --any \
   --out $D/heb_recall_full.tsv
```

`--any` sets `t=1`, turning the query into an **OR** of every token this plan
has identified. This is not a query anyone should read the results of — it is
the measurement of how much room lies above 702, and the source of the
complete 30-title publication list (`cut -f4 … | sort | uniq -c`).

**Trap:** at `--max 5000` this may still truncate. If the stderr progress shows
`5000/<something larger>`, the ceiling was not reached and the number to report
is a lower bound on a lower bound. Say so explicitly if it happens.

### H9 — premises follow-up, for comparability with session C *(optional)*

```sh
$J 'דרך ההר חיפה חולים'      $Y --out $D/heb_mountainroad.tsv
$J '"בבת גלים" חולים ממשלתי' $Y --out $D/heb_batgalim.tsv
```

The Hebrew counterpart to `mountainroad.tsv` and `govhosp_batgalim.tsv`. Note
`בת גלים` also appears as `בת־גלים` — the same maqaf question as D5, so run H9
after D5 has been read.

---

# Stage 2 is not optional

Exactly as the Arabic README concludes: **search snippets are useless for
filtering.** They centre on whichever token the engine chose, which under
degradation is an arbitrary token. Every harvest above must go through the
full-text harvester and a local regular-expression pass before any count is
reported as a finding.

The Hebrew local pass needs, at minimum, to separate:

- **Other towns' government hospitals** — Jaffa, Jerusalem, Safed, Tiberias,
  Acre. Same hazard the Arabic README flags; check the dateline.
- **Haifa's other hospitals** — הדסה (Hadassah), רוטשילד (Rothschild),
  אליישע (Elisha). These share the abbreviation `ביה"ח` completely, so H4 and
  H5 cannot be reported without this filter.
- **Beit She'an** — `בית שאן`, which under degradation matches on `בית`.
- **OCR damage.** The snippets already show `נית־החולים`, `בי־תהחולע` and
  `בית־החולם`. A local pass should be tolerant (character-class or edit
  distance), which is precisely the tolerance the engine will not give us.

---

# Results table — to be filled in by the executing session

| probe | query | level | total | notes |
|---|---|---|---|---|
| D1 | `"בית החולים הממשלתי"` | Page | | expected 702 |
| D2 | `"בית החולים הממשלתי"` | Logical | | |
| D3 | `בית החולים הממשלתי` (AND) | Page | | |
| D4 | `"בית החולים הממשלתי בחיפה"` | Page | | > D1 ⇒ degraded |
| D5 | `בית־החולים` | Page | | |
| D6 | `"בית החולים"` | Page | | denominator |
| D7 | `ביה״ח` | Page | | |
| D8 | `ביה"ח` | Page | | 0/error ⇒ unqueryable |
| D9 | `ביה` | Page | | ≥ D7 ⇒ mark separates |
| D10 | `ביהח` | Page | | |
| D11 | `בי״ח` / `ביח` | Page | | |
| D12 | `הממשלתי` / `ממשלתי` | Page | | |
| D13 | `בחיפה` / `חיפה` | Page | | |

And the headline number this plan exists to produce:

> **702** (spelled-out phrase) → **____** (phrase + locative, H2) →
> **____** (union of all precision-grade forms, H1 ∪ H2 ∪ H4 ∪ H5 ∪ H6, deduplicated
> on the `id` column) → **____** (recall ceiling, H8).

Report the third figure as the Hebrew count comparable to the Arabic 2,322 and
1,593. Report the fourth only as a ceiling, never as a count of references.
