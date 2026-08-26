"""Build the deduplicated Hebrew qualified-union hit list.

Stage 1 asked for the Haifa Government Hospital under every name the Mandate
Hebrew press used for it - spelled out, abbreviated, with a maqaf, and
indefinite - which produced one hit list per form. They overlap only slightly
(see data/newspapers/hebrew_query_plan.md), so the union is what stage 2 has
to read.

"Qualified" means the page calls the hospital *governmental*: ממשלתי or
הממשלתי. The unqualified sweep (heb_unqualified*.tsv, heb_abbrev_haifa_broad
.tsv) is deliberately excluded - it is 8,587 pages that are mostly Haifa's
other hospitals, and it is a separate decision whether to mine it at all.

Writes data/newspapers/heb_qualified_union.tsv in the same shape as the
jrayed.py search output, so jrayed_text_harvest.py can read it directly:

  python3 pipeline/heb_union.py
  python3 pipeline/jrayed_text_harvest.py --site nli \
      --glob heb_qualified_union.tsv --out heb_page_texts.jsonl
"""

from __future__ import annotations

import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HITS = os.path.join(ROOT, "data", "newspapers")
OUT = os.path.join(HITS, "heb_qualified_union.tsv")

# form label -> hit list. The _haifa files are subsets of their parents, but
# including them costs nothing and keeps the provenance column honest about
# every query a page answered.
SOURCES = [
    ("spelled",     "heb_govhosp_phrase.tsv"),
    ("spelled",     "heb_govhosp_haifa.tsv"),
    ("spelled",     "heb_govhosp_haifa_phrase.tsv"),
    ("abbreviated", "heb_abbrev_phrase.tsv"),
    ("abbreviated", "heb_abbrev_haifa.tsv"),
    ("abbrev_short", "heb_abbrev_short.tsv"),
    ("maqaf",       "heb_maqaf.tsv"),
    ("maqaf",       "heb_maqaf_haifa.tsv"),
    ("indefinite",  "heb_indef.tsv"),
]


def main() -> None:
    rows: dict[str, dict] = {}
    forms: dict[str, set] = {}
    for form, name in SOURCES:
        path = os.path.join(HITS, name)
        if not os.path.exists(path):
            print(f"  missing, skipped: {name}")
            continue
        n = 0
        with open(path, newline="") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                if not row.get("id"):
                    continue
                n += 1
                rows.setdefault(row["id"], row)
                forms.setdefault(row["id"], set()).add(form)
        print(f"  {name:32s} {n:5,d}")

    with open(OUT, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["n", "id", "date", "publication", "title", "snippet", "forms"])
        for i, (pid, row) in enumerate(sorted(rows.items()), 1):
            w.writerow([i, pid, row.get("date", ""), row.get("publication", ""),
                        row.get("title", ""), row.get("snippet", ""),
                        ",".join(sorted(forms[pid]))])

    print(f"\nunion: {len(rows):,d} pages -> {os.path.relpath(OUT, ROOT)}")
    tally: dict[str, int] = {}
    for s in forms.values():
        tally[",".join(sorted(s))] = tally.get(",".join(sorted(s)), 0) + 1
    print("pages by which form(s) found them:")
    for k, v in sorted(tally.items(), key=lambda x: -x[1]):
        print(f"  {v:5,d}  {k}")


if __name__ == "__main__":
    main()
