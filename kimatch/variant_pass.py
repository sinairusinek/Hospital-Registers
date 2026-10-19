#!/usr/bin/env python3
"""Round 3: carry the places already ruled on to every spelling of them.

Rounds 1-2 and Yoni Furas's identifications rule on exact City values; the
registers spell a village a dozen ways, so most never-reviewed values are new
spellings of ruled places. This pass reads every City value with no decision
through kimatch/place_resolver.py and:

  * appends a `matched` decision (decided_by `variant`) where the value
    resolves to exactly one ruled place — the note names the spelling it
    follows and the tier (exact / skeleton / alternation);
  * writes kimatch/round3-workbook.tsv: the values it could not resolve, with
    their record counts, for the next review.

REJECT holds skeleton matches read and refused by eye (2026-10-19). Rerunning
is idempotent: values already decided are skipped.

    python3 kimatch/variant_pass.py           # dry run: counts only
    python3 kimatch/variant_pass.py --write
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from place_resolver import resolve  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DECISIONS = ROOT / "kimatch" / "city-kima-decisions.tsv"
DATA = ROOT / "data" / "public" / "hospital-registers-normalized.tsv"
WORKBOOK = ROOT / "kimatch" / "round3-workbook.tsv"
DATE = "2026-10-19"

# Same skeleton, different place — or too thin to call.
REJECT = {
    "Kafrin": "al-Kafrayn, not Kfar Inan",
    "Majadli": "probably al-Mujaydil, not Majdal/Migdal",
    "Keneret": "plain Kinneret stays ambiguous (standing ruling)",
    "Kafr Alam": "not safely Kafr Lam",
    "Migdaly": "not safely Migdal",
    "Ajjur": "Ajjur near Hebron, not Yagur",
    "Beit Hanna": "not Beit Anya",
    "Jalama": "three al-Jalamas; not safely the Haifa one",
    "Kallissa": "Halisa (Haifa) or al-Khalisa: either",
    "Mughayyir": "al-Mughayyir, not Mughar",
}


def main() -> None:
    write = "--write" in sys.argv
    csv.field_size_limit(10**9)
    with DECISIONS.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        fields = reader.fieldnames
        decisions = list(reader)
    by_city = {r["city"]: r for r in decisions}

    counts: Counter[str] = Counter()
    religion: dict[str, Counter[str]] = {}
    with DATA.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            if r["Notebook_Number"] == "25" or not r["City"] or r["City"] in by_city:
                continue
            counts[r["City"]] += 1
            religion.setdefault(r["City"], Counter())[r["Religion"] or "Not recorded"] += 1

    added, tiers, unresolved = [], Counter(), []
    for city, n in counts.most_common():
        spelling, tier, note = ("", "", "") if city in REJECT else resolve(city)
        if not spelling:
            unresolved.append((city, n))
            continue
        src = by_city[spelling]
        row = {f: "" for f in fields}
        row.update(city=city, spelling=city, n_records=str(n), kima_id=src["kima_id"],
                   kima_name_rom=src["kima_name_rom"], wikidata_qid=src["wikidata_qid"],
                   qid_source=src["qid_source"], decision="matched", grade=f"variant-{tier}",
                   decided_by="variant", date=DATE,
                   note=f"spelling of {spelling!r} ({tier}{': ' + note if note else ''})")
        added.append(row)
        tiers[tier] += n

    print(f"{len(counts)} undecided values, {sum(counts.values())} records")
    print(f"  resolved: {len(added)} values, {sum(int(r['n_records']) for r in added)} records {dict(tiers)}")
    print(f"  unresolved: {len(unresolved)} values, {sum(n for _, n in unresolved)} records")
    if not write:
        return
    decisions.extend(added)
    decisions.sort(key=lambda r: (-int(r["n_records"] or 0), r["city"]))
    with DECISIONS.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(decisions)
    with WORKBOOK.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["city", "n_records", "religion_mix", "rejected_because", "your_decision", "your_kima_id", "your_qid"])
        for city, n in unresolved:
            mix = ", ".join(f"{k} {v}" for k, v in religion[city].most_common())
            w.writerow([city, n, mix, REJECT.get(city, ""), "", "", ""])
    print(f"wrote {DECISIONS.name} (+{len(added)}) and {WORKBOOK.name}")


if __name__ == "__main__":
    main()
