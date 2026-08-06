#!/usr/bin/env python3
"""Extract the distinct-City matching queue for kimatch.

Reads the normalized register TSV, keeps Jewish patients with a non-empty City,
and writes one row per distinct City value with record counts. Values carrying a
`|` alternation (two preserved readings) are split into name1/name2 so the
matcher tries both spellings.

Usage: python3 kimatch/extract_queue.py
"""
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "public" / "hospital-registers-normalized.tsv"
QUEUE = ROOT / "kimatch" / "city-queue.tsv"


def main() -> None:
    counts: Counter[str] = Counter()
    with SOURCE.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row.get("Religion") != "Jewish":
                continue
            city = (row.get("City") or "").strip()
            if city:
                counts[city] += 1

    with QUEUE.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["city", "name1", "name2", "n_records"])
        for city, n in counts.most_common():
            name1, _, name2 = city.partition("|")
            w.writerow([city, name1.strip(), name2.strip(), n])

    print(f"{QUEUE.name}: {len(counts)} distinct City values, "
          f"{sum(counts.values())} records")


if __name__ == "__main__":
    main()
