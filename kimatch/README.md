# Kima matching for the City column

Links the normalized `City` values to the [Kima Historical Gazetteer](https://geo-kima.org)
and Wikidata. Produced with the kimatch engine
(`/Users/sinairusinek/Documents/GitHub/Kimatch`, run via its `.venv/bin/kimatch`)
in a human-in-the-loop session on 2026-08-06; scope was the distinct City values
of Jewish patients (437 values, 5,054 records), but the build-time join is
religion-blind, so shared city values link every community's records.

## Files

- `city-kima-decisions.tsv` — **the deliverable.** One row per distinct City
  value: `kima_id`, `wikidata_qid`, a `decision`
  (`matched` / `unmatched-no-kima-entry` / `unmatched-ambiguous` / `unmatched-junk`),
  and provenance (`decided_by`: `auto` = grade-A engine match that passed a
  geographic audit; `agent` = Claude adjudication; `human` = decided by the
  historian in the review session). `pipeline/build.py` joins the `matched`
  rows onto `City` at build time, emitting the `City Kima ID` and
  `City Wikidata` columns.
- `city-queue.tsv` — the matching queue (distinct values + record counts;
  `|` alternations split into two name fields). Rebuild: `python3 kimatch/extract_queue.py`.
- `hospital_registers_city.json` — the kimatch job config (Latin script,
  general Beider-Morse phonetics, no coordinates).
- `review-workbook.tsv` — the review queue with every candidate resolved
  against the Kima dump; the evidence base for the agent/human decisions.
- `build_decisions.py` — regenerates `city-kima-decisions.tsv` from
  `match-raw.csv` + the adjudication table encoded in the script.
  `--resolve` also queries Wikidata (type-verified) for matched places whose
  Kima record lacks a QID.

## Rerunning the match

```bash
cd /Users/sinairusinek/Documents/GitHub/Kimatch
.venv/bin/kimatch match -c <repo>/kimatch/hospital_registers_city.json \
  -o <repo>/kimatch/match-raw.csv --split-by-grade \
  --prior-resolutions <repo>/kimatch/city-kima-decisions.tsv
python3 <repo>/kimatch/build_decisions.py --resolve
python3 <repo>/pipeline/build.py
```

The decisions file doubles as `--prior-resolutions` input (its `spelling` +
`kima_id` columns), so confirmed answers survive engine reruns.

## Review conventions

- Only Israel/Palestine-plausible referents are accepted; matches outside the
  region (ancient cities, Europe, the Americas) are treated as engine false
  positives. Nearby-country locations (Transjordan, Lebanon, Syria, Egypt) are
  held as `unmatched-ambiguous` for human review rather than auto-linked.
- Haifa neighborhoods link only to their **own** Kima entries (Hadar Hakarmel,
  Bat Galim, Neve Sha'anan, Wadi Nisnas, Ahuza…), never rolled up to Haifa's
  city id; neighborhoods absent from Kima (Halisa, Ard el-Yahud, Kiryat
  Eliyahu, Shkhunat Ovdim) stay `unmatched-no-kima-entry` — they are donation
  candidates for a future round.
- Pipe alternations (`Haifa|Hadar Hacarmel`) resolve to the finer reading when
  both readings nest; alternations across different towns stay ambiguous.
- Distinct naming traditions (Acre/Akka, Balad al-Sheikh/Nesher) keep their
  distinct City values; linking to the same Kima place does not merge them.

## Round 2 — the villages the first round could not see (2026-08-28)

The first round scoped the queue to Jewish patients' cities. Because the
build-time join is religion-blind, those matches carried every community's
records for the places the communities *shared* — Acre, Nazareth, Jenin. What
they could not carry is the places they did not share: the Galilee and Carmel
villages no Jewish patient came from. Those stayed unreviewed and so stayed off
the map, and the absence is systematic rather than random — 3,570 records,
2,744 of them Muslim and 577 Christian.

`extract_queue.py` now takes every City value by default (`--religion` reproduces
the original round), with `--min-records` and `--new-only` for triage. Round 2
took the 209 values seen 3+ times that the first round never ruled on: 1,717
records, 1,290 Muslim and 267 Christian.

```bash
python3 kimatch/extract_queue.py --min-records 3 --new-only
cd ../Kimatch && .venv/bin/kimatch match \
  -c <repo>/kimatch/hospital_registers_city.json \
  -o <repo>/kimatch/match-round2.csv --split-by-grade \
  --prior-resolutions <repo>/kimatch/city-kima-decisions.tsv
```

- `round2-workbook.tsv` — **the review queue.** One row per value, with the
  engine's candidate, the Kima entry's coordinates, a geographic audit, and the
  religion mix of the records the ruling would speak for. Fill `your_decision`
  and `your_kima_id`; `proposed_decision` is pre-filled only where an A-grade
  match also passed the audit.

The audit is not decoration. Three A-grade matches land outside any plausible
catchment — Hebron to Hebron **Connecticut**, Zeitoun to Zeytun **Turkey**,
Cairo to a record labelled Cairo **Illinois** whose coordinates are in fact
Egypt's. The label lies and the point is right, which is exactly why these are
reviewed rather than autolinked. `_grade` alone is not a verdict.

Of the 209: 40 are A-grade and in-region (471 records) and could be taken as
read; 158 drew no candidate at all; 5 matched an entry Kima holds without
coordinates (Tarshiha the largest at 74 records), the same gap al-Bassa had.
