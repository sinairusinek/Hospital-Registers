"""Draw a random sample of the unqualified sweep, to price the full mine.

The unqualified pages (heb_unqualified*.tsv, heb_abbrev_haifa_broad.tsv) name a
hospital and Haifa but never the word governmental. There are 7,692 of them the
qualified set never sees, and harvesting all their text is ~2h20m on the shared
browser. Before spending that, measure what fraction survives the same stage-2
filter the qualified set went through.

Writes data/newspapers/heb_unqualified_sample.tsv in jrayed.py search shape, so
jrayed_text_harvest.py reads it directly.

Run: python3 pipeline/heb_sample_unqualified.py [--n 150] [--seed 20260826]
"""

from __future__ import annotations

import argparse
import csv
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS = os.path.join(ROOT, "data", "newspapers")
SOURCES = ["heb_unqualified.tsv", "heb_unqualified_maqaf.tsv",
           "heb_abbrev_haifa_broad.tsv"]
QUALIFIED = "heb_qualified_union.tsv"
OUT = os.path.join(NEWS, "heb_unqualified_sample.tsv")


def rows(name):
    with open(os.path.join(NEWS, name), newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--seed", type=int, default=20260826,
                    help="fixed so the sample is reproducible and the estimate "
                         "can be checked later against the full mine")
    args = ap.parse_args()

    qualified = {r["id"] for r in rows(QUALIFIED)}
    pool: dict[str, dict] = {}
    for name in SOURCES:
        for r in rows(name):
            if r.get("id") and r["id"] not in qualified:
                pool.setdefault(r["id"], r)

    ids = sorted(pool)
    rng = random.Random(args.seed)
    pick = rng.sample(ids, min(args.n, len(ids)))

    with open(OUT, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["n", "id", "date", "publication", "title", "snippet"])
        for i, pid in enumerate(sorted(pick), 1):
            r = pool[pid]
            w.writerow([i, pid, r.get("date", ""), r.get("publication", ""),
                        r.get("title", ""), r.get("snippet", "")])

    print(f"pool: {len(ids):,d} unqualified pages not in the qualified union")
    print(f"sample: {len(pick):,d} (seed {args.seed}) -> "
          f"{os.path.relpath(OUT, ROOT)}")
    print(f"margin of error at 95% on a 40% rate, n={len(pick)}: "
          f"±{196 * (0.4 * 0.6 / len(pick)) ** 0.5:.0f} percentage points")


if __name__ == "__main__":
    main()
