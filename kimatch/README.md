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
