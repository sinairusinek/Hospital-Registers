#!/usr/bin/env python3
"""Fold Yoni Furas's place identifications into city-kima-decisions.tsv.

Yoni Furas (University of Haifa) annotated the 2024 list of unique patient
addresses (data/public/furas-unique-addresses-2024.tsv): a reading, a place
type, the town, and for many villages a Wikidata QID. The historian ruled on
2026-10-18 that his identifications stand wherever he gave one.

kimatch/furas-rulings.tsv is the reviewed bridge between his sheet and the
City column: one row per `City as written` value, matched to his row exactly
or by a close spelling, with the Kima id and QID his reading resolves to.
Rows he marked "check", and rows naming a place without saying which
namesake, are kept as `held` and change nothing here.

Each matched ruling updates the decision row for its normalized `city`, or
appends one. Rerunning is idempotent.

Usage: python3 kimatch/apply_furas.py
"""
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULINGS = ROOT / "kimatch" / "furas-rulings.tsv"
DECISIONS = ROOT / "kimatch" / "city-kima-decisions.tsv"
KIMA_DUMP = Path("/Users/sinairusinek/Documents/GitHub/Kimatch/20250126KimaPlacesCSVx.csv")
DATE = "2026-10-18"


def main() -> None:
    with KIMA_DUMP.open(encoding="utf-8-sig", newline="") as fh:
        places = {r["id"]: r for r in csv.DictReader(fh)}
    with DECISIONS.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        fields = reader.fieldnames
        decisions = list(reader)
    by_city = {r["city"]: r for r in decisions}

    rulings = defaultdict(list)
    with RULINGS.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if r["decision"] == "matched":
                rulings[r["city"]].append(r)

    updated = added = 0
    for city, group in rulings.items():
        targets = {(r["kima_id"], r["wikidata_qid"]) for r in group}
        if len(targets) > 1:
            raise SystemExit(f"{city!r}: spellings resolve to different places {targets}")
        kima_id, qid = targets.pop()
        first = group[0]
        name = places[kima_id]["primary_rom_full"] if kima_id else ""
        source = "furas" if first["decided_by"] == "furas" else "human"
        row = by_city.get(city)
        if row is None:
            row = {f: "" for f in fields}
            row.update(city=city, spelling=city, grade="furas",
                       n_records=str(sum(int(r["n_records"]) for r in group)))
            decisions.append(row)
            by_city[city] = row
            added += 1
        else:
            updated += 1
        row.update(kima_id=kima_id, kima_name_rom=name, wikidata_qid=qid, qid_source=source,
                   decision="matched", decided_by=first["decided_by"], note=first["note"], date=DATE)

    decisions.sort(key=lambda r: (-int(r["n_records"] or 0), r["city"]))
    with DECISIONS.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(decisions)
    print(f"{DECISIONS.name}: {updated} rows re-ruled, {added} added, {len(decisions)} in all")


if __name__ == "__main__":
    main()
