"""Find mass-casualty days in the register, and what the press says about them.

The press-to-register match works one report at a time, and for an ordinary
accident the link stays circumstantial. Mass-casualty days are different:
when a day's injury admissions jump far above the surrounding baseline, the
register itself is testifying to a single event, and the newspapers of the
following days usually name it.

This reads the register, scores each day against a trailing/leading
baseline, and joins the spikes to the concordance windows published in the
days after - so each spike arrives with its candidate press explanation.

Writes data/newspapers/casualty_spikes.tsv:

  date, admissions, injuries, died, baseline, ratio, religions, sexes,
  age_range, diagnoses (the distinct injury wordings, truncated),
  press (dated snippets from the following days, ' || '-joined)

Notebook 25 (Atlit camp) is excluded throughout.

Run: python3 pipeline/casualty_spikes.py [--min-injuries 8] [--ratio 3.0]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "data", "public", "hospital-registers-normalized.tsv")
CONC = os.path.join(ROOT, "data", "newspapers", "hospital_haifa_concordance.tsv")
OUT = os.path.join(ROOT, "data", "newspapers", "casualty_spikes.tsv")

INJURY = ("800-999", "E800-E999")


def parse_date(s: str):
    try:
        return dt.date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-injuries", type=int, default=8,
                    help="a day needs at least this many injury admissions")
    ap.add_argument("--ratio", type=float, default=3.0,
                    help="times the surrounding baseline")
    ap.add_argument("--baseline-days", type=int, default=14)
    ap.add_argument("--press-days", type=int, default=4,
                    help="days after the spike to search the press")
    args = ap.parse_args()

    by_day: dict[dt.date, list[dict]] = defaultdict(list)
    with open(REG, newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["Notebook_Number"] == "25":
                continue
            d = parse_date(r["Admission Date"])
            if d:
                by_day[d].append(r)

    def injuries(day):
        return [r for r in by_day.get(day, [])
                if r["ICD-9 Chapter"].startswith(INJURY)]

    days = sorted(by_day)
    # only judge days inside a covered stretch: the registers have gaps, and
    # a lone day after a gap would look like a spike against empty neighbours
    covered = {d for d in days
               if sum(1 for k in range(-args.baseline_days, args.baseline_days + 1)
                      if d + dt.timedelta(days=k) in by_day) >= args.baseline_days // 2}

    press = defaultdict(list)
    if os.path.exists(CONC):
        with open(CONC, newline="") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                d = parse_date(row["date"])
                if d:
                    press[d].append(row)

    spikes = []
    for d in days:
        if d not in covered:
            continue
        inj = injuries(d)
        if len(inj) < args.min_injuries:
            continue
        neigh = [len(injuries(d + dt.timedelta(days=k)))
                 for k in range(-args.baseline_days, args.baseline_days + 1) if k]
        base = sum(neigh) / len(neigh) if neigh else 0
        if len(inj) < args.ratio * max(base, 0.5):
            continue
        spikes.append((d, inj, base))

    with open(OUT, "w", newline="") as g:
        w = csv.writer(g, delimiter="\t")
        w.writerow(["date", "admissions", "injuries", "died", "baseline", "ratio",
                    "religions", "sexes", "age_range", "diagnoses", "press"])
        for d, inj, base in spikes:
            died = sum(1 for r in inj if r["Result"] == "Died")
            ages = sorted(int(r["Age"]) for r in inj if r["Age"].isdigit())
            diags = Counter((r["Diagnosis as standardized"] or
                             r["Diagnosis as written"] or "?")[:60] for r in inj)
            snips = []
            for k in range(0, args.press_days + 1):
                for row in press.get(d + dt.timedelta(days=k), []):
                    snips.append(f"[{row['date']} {row['pub']}] "
                                 + re.sub(r"\s+", " ", row["window"])[:200])
            w.writerow([
                d.isoformat(), len(by_day[d]), len(inj), died, f"{base:.1f}",
                f"{len(inj)/max(base, 0.5):.1f}",
                ", ".join(f"{k or '?'}:{n}" for k, n in
                          Counter(r["Religion"] for r in inj).most_common()),
                ", ".join(f"{k or '?'}:{n}" for k, n in
                          Counter(r["Sex"] for r in inj).most_common()),
                f"{ages[0]}-{ages[-1]}" if ages else "",
                " | ".join(f"{k}×{n}" if n > 1 else k for k, n in diags.most_common(8)),
                " || ".join(snips[:4]),
            ])

    print(f"{len(spikes)} casualty spikes -> {OUT}")
    for d, inj, base in spikes:
        died = sum(1 for r in inj if r["Result"] == "Died")
        has = "press" if any(press.get(d + dt.timedelta(days=k))
                             for k in range(args.press_days + 1)) else "-"
        print(f"  {d}  {len(inj):3d} injuries ({died} died), baseline {base:.1f}  {has}")


if __name__ == "__main__":
    main()
