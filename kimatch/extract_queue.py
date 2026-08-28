#!/usr/bin/env python3
"""Extract the distinct-City matching queue for kimatch.

Reads the normalized register TSV and writes one row per distinct City value
with record counts. Values carrying a `|` alternation (two preserved readings)
are split into name1/name2 so the matcher tries both spellings.

The first round (2026-08-06) scoped the queue to Jewish patients' cities, and
because the build-time join is religion-blind those matches carried every
community's records for the places the communities shared. What they could not
carry is the places they did not share: the Galilee and Carmel villages no
Jewish patient came from — Tarshiha, Kafr Yasif, Igzim, Yarka, Umm al-Fahm —
which stayed unreviewed and so stayed off the map. That absence is systematic,
not random, and it skews Muslim and Christian.

So the default scope is now every City value in the register. `--religion` is
kept for reproducing the original round.

Below `--min-records` the tail is mostly transcription debris: 81% of the
never-reviewed values occur exactly once. The threshold is a triage order, not
a judgement — a singleton is not junk, it is merely unevidenced by repetition,
and a later round can lower the bar.

Usage:
    python3 kimatch/extract_queue.py                    # every value, all of them
    python3 kimatch/extract_queue.py --min-records 3    # the repeat villages
    python3 kimatch/extract_queue.py --religion Jewish  # the original round
"""
import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "public" / "hospital-registers-normalized.tsv"
QUEUE = ROOT / "kimatch" / "city-queue.tsv"
DECISIONS = ROOT / "kimatch" / "city-kima-decisions.tsv"


def already_decided() -> set[str]:
    """City values a previous round already ruled on."""
    if not DECISIONS.exists():
        return set()
    with DECISIONS.open(encoding="utf-8", newline="") as fh:
        return {row["city"] for row in csv.DictReader(fh, delimiter="\t")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--religion", default=None,
                    help="restrict to one Religion value (default: every record)")
    ap.add_argument("--min-records", type=int, default=1,
                    help="drop values seen fewer than this many times")
    ap.add_argument("--new-only", action="store_true",
                    help="omit values city-kima-decisions.tsv already rules on")
    args = ap.parse_args()

    counts: Counter[str] = Counter()
    religions: dict[str, Counter[str]] = defaultdict(Counter)
    with SOURCE.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if args.religion and row.get("Religion") != args.religion:
                continue
            city = (row.get("City") or "").strip()
            if city and city not in ("null", "undefined"):
                counts[city] += 1
                religions[city][(row.get("Religion") or "").strip() or "Not recorded"] += 1

    decided = already_decided() if args.new_only else set()
    kept = [(c, n) for c, n in counts.most_common()
            if n >= args.min_records and c not in decided]

    with QUEUE.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["city", "name1", "name2", "n_records"])
        for city, n in kept:
            name1, _, name2 = city.partition("|")
            w.writerow([city, name1.strip(), name2.strip(), n])

    records = sum(n for _, n in kept)
    print(f"{QUEUE.name}: {len(kept):,} distinct City values, {records:,} records")
    if decided:
        print(f"  ({len(decided):,} values already in the decisions file, omitted)")
    if args.min_records > 1:
        dropped = [(c, n) for c, n in counts.items()
                   if n < args.min_records and c not in decided]
        print(f"  below the {args.min_records}-record threshold: "
              f"{len(dropped):,} values / {sum(n for _, n in dropped):,} records, held for a later round")

    # Which communities the new queue speaks for — the reason it exists.
    tally: Counter[str] = Counter()
    for city, _ in kept:
        tally.update(religions[city])
    if tally:
        print("  records by religion: "
              + ", ".join(f"{k} {v:,}" for k, v in tally.most_common(5)))


if __name__ == "__main__":
    main()
