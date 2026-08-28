#!/usr/bin/env python3
"""Audit admission years against the library's catalogued year span per notebook.

The Haifa library's IIIF canvas labels carry the notebook's year span
(e.g. 0030_23_1939_030_d, 0001_24_1939-40_001_d). A record whose admission
year falls outside its notebook's span is a date-reading error, not a real
admission. Errors cluster by ledger page, because the year was read once per
page image and propagated down the eleven rows.

Writes a per-record report and a per-page summary; changes nothing.
"""
import csv
import re
import sys
import collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTERS = ROOT / "data/public/hospital-registers-2025-08-10.tsv"
IIIF = ROOT / "data/public/iiif-pages.tsv"
OUT_ROWS = ROOT / "data/eval/year_conflicts.tsv"
OUT_PAGES = ROOT / "data/eval/year_conflicts_by_page.tsv"

csv.field_size_limit(10 ** 9)


def cell(row, key):
    return (row.get(key) or "").strip()


def notebook_spans():
    """notebook -> set of years the library catalogued it under."""
    spans = collections.defaultdict(set)
    with IIIF.open(newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            label = row["canvas_label"]
            m = re.search(r"_(\d{4})(?:-(\d{2,4}))?_", label)
            if not m:
                continue
            start = int(m.group(1))
            # Notebooks 28 and 30-33 use "redacted_0001_0035" labels with no year;
            # only accept spans inside the register's real lifetime.
            if not 1925 <= start <= 1950:
                continue
            spans[row["Notebook_Number"]].add(start)
            if m.group(2):
                end = m.group(2)
                end = int(end) if len(end) == 4 else start - start % 100 + int(end)
                if 1925 <= end <= 1950:
                    spans[row["Notebook_Number"]].update(range(start, end + 1))
    return spans


def main():
    spans = notebook_spans()
    conflicts = []
    per_page = collections.defaultdict(collections.Counter)
    checked = 0

    with REGISTERS.open(newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            nb = cell(row, "Notebook_Number")
            span = spans.get(nb)
            iso = cell(row, "Admission Date [ISO]")
            if not span or len(iso) < 4 or not iso[:4].isdigit():
                continue
            checked += 1
            year = int(iso[:4])
            page = cell(row, "Page_Number")
            key = (nb, page)
            if year in span:
                per_page[key]["ok"] += 1
                continue
            per_page[key]["conflict"] += 1
            conflicts.append(
                {
                    "Notebook_Number": nb,
                    "Page_Number": page,
                    "Index": cell(row, "Index"),
                    "Notebook Record ID": cell(row, "Notebook Record ID"),
                    "admission_iso": iso,
                    "admission_orig": cell(row, "Admission Date (Orig)"),
                    "discharge_iso": cell(row, "Discharge Date (ISO)"),
                    "discharge_orig": cell(row, "Discharge Date (Orig)"),
                    "catalogued_years": ",".join(str(y) for y in sorted(span)),
                    "date_flag": cell(row, "final date quality flag"),
                }
            )

    OUT_ROWS.parent.mkdir(parents=True, exist_ok=True)
    with OUT_ROWS.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(conflicts[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(conflicts)

    with OUT_PAGES.open("w", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["Notebook_Number", "Page_Number", "conflict", "ok", "verdict"])
        for (nb, page), counts in sorted(
            per_page.items(), key=lambda kv: (-kv[1]["conflict"], kv[0])
        ):
            if not counts["conflict"]:
                continue
            verdict = "whole page" if not counts["ok"] else "partial"
            writer.writerow([nb, page, counts["conflict"], counts["ok"], verdict])

    by_nb = collections.Counter(c["Notebook_Number"] for c in conflicts)
    whole = sum(1 for c in per_page.values() if c["conflict"] and not c["ok"])
    print(f"checked {checked} dated records against {len(spans)} catalogued notebooks")
    print(f"{len(conflicts)} conflicts across {len(by_nb)} notebooks; {whole} whole pages")
    for nb, n in sorted(by_nb.items(), key=lambda kv: -kv[1]):
        span = ",".join(str(y) for y in sorted(spans[nb]))
        print(f"  NB{nb:>3}: {n:>4} conflicts  (catalogued {span})")
    print(f"wrote {OUT_ROWS.relative_to(ROOT)} and {OUT_PAGES.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
