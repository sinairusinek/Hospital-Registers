"""Stage 2: put the register's own diagnosis series beside each press report.

Reads data/newspapers/epidemic_concordance.tsv (stage 1) and rewrites it with
register columns appended, so the deliverable stays one file. It is idempotent:
only the stage-1 columns are read, any register columns already present are
discarded and recomputed.

The comparison is deliberately asymmetric. The press report is an event with a
date; the register is a continuous series. So for every Haifa-attributed press
mention the script asks three questions of the series:

  - had the register already seen cases of this disease in the 60 days before
    the paper spoke, and how many died?
  - did cases follow in the 60 days after?
  - if the report falls inside an outbreak the register defines on its own,
    how many days after that outbreak began was it printed?

The last is the measure that generalises the al-Difa' diphtheria case: the
register had been admitting diphtheria for six weeks before the paper called
the disease "returning" to Haifa.

Two constraints govern every number here and are carried into the output.

  1. The register is not continuous. It is missing 1940-04 to 1944-01 entirely,
     the whole of 1945, and several shorter stretches; see the coverage report
     the script prints. A press report in a month the register does not cover
     is marked `no-register-coverage` and is excluded from the aggregate,
     because "the register is silent" and "the register is absent" are not the
     same claim.
  2. Notebook 25 is the Atlit camp register and is excluded here as everywhere.

Diseases are matched to the register by ICD-9 code, not by diagnosis string:
the codes were assigned by pipeline/classify_diagnoses.py and are the column
that already carries one provenance. Observation codes (V71.0*, "Observation
for Typhoid Fever") are excluded from case counts — they record a suspicion the
hospital raised and then, in half the strings, explicitly negatived.

Run: python3 pipeline/epidemic_register_match.py [--window 60]
"""

from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONC = os.path.join(ROOT, "data", "newspapers", "epidemic_concordance.tsv")
REG = os.path.join(ROOT, "data", "public", "hospital-registers-normalized.tsv")

BASE_COLUMNS = ["date", "pub", "page_id", "disease", "term", "haifa",
                "dateline", "hospital", "epidemic_words", "soft_term", "window"]
REG_COLUMNS = ["reg_before", "reg_after", "reg_deaths_before", "reg_coverage",
               "surge", "days_after_surge", "lead_lag"]

# disease -> ICD-9 code prefixes (integer part, zero-padded)
GROUPS = {
    "typhoid": ("002",),      # includes paratyphoid A and B, 002.1 / 002.9
    "typhus": ("080", "081"),
    "malaria": ("084",),
    "smallpox": ("050",),
    "cholera": ("001",),
    "diphtheria": ("032",),
    "measles": ("055",),
    "dysentery": ("004", "006"),   # bacillary and amoebic
    "trachoma": ("076",),
    "plague": ("020",),
    "influenza": ("487",),
}

CODE = re.compile(r"^(\d{1,3})(?:\.\d+)?$")

# A month the register is open. Below this the month is a fragment - a notebook
# starting or ending mid-month - and its zeroes mean nothing.
OPEN_MONTH = 20


def codes(raw: str) -> list[str]:
    """Integer parts of the ICD-9 codes in a cell, zero-padded.

    The column carries alternatives separated by a pipe (081.9|080) and, on a
    few hundred rows, a code whose leading zero was lost somewhere upstream
    (32.9 for diphtheria, 87.9 for relapsing fever), so the integer part is
    padded rather than compared as written. V-codes fail the match and are
    thereby excluded, which is what we want.
    """
    out = []
    for part in (raw or "").split("|"):
        m = CODE.match(part.strip())
        if m:
            out.append(m.group(1).zfill(3))
    return out


def load_register():
    by_disease: dict[str, dict[dt.date, int]] = collections.defaultdict(
        lambda: collections.defaultdict(int))
    deaths: dict[str, dict[dt.date, int]] = collections.defaultdict(
        lambda: collections.defaultdict(int))
    month_total: collections.Counter[str] = collections.Counter()
    skipped = 0
    with open(REG, newline="") as f:
        for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if r["Notebook_Number"] == "25":     # Atlit camp register
                skipped += 1
                continue
            try:
                d = dt.date.fromisoformat(r["Admission Date"])
            except (ValueError, TypeError):
                continue
            month_total[d.strftime("%Y-%m")] += 1
            cs = codes(r["ICD-9 Code"])
            for g, prefixes in GROUPS.items():
                if any(c in prefixes for c in cs):
                    by_disease[g][d] += 1
                    if r["Result"] == "Died":
                        deaths[g][d] += 1
                    break
    open_months = {m for m, n in month_total.items() if n >= OPEN_MONTH}
    print(f"{skipped} Atlit rows excluded; register open in "
          f"{len(open_months)} of {len(month_total)} months with any data",
          file=sys.stderr)
    return by_disease, deaths, open_months


def surges(days: dict[dt.date, int], open_days: list[dt.date],
           trail: int, refractory: int, floor: int):
    """Dates on which the register's own series first reads as a surge.

    A wave defined by silence works for plague and fails for everything else:
    typhoid, malaria and dysentery were endemic in Haifa, admitted in ones and
    twos all year, so any gap rule merges four years into one "wave". The
    question the press comparison actually asks is not when a disease appeared
    but when it rose - so each disease is measured against its own baseline.

    For every day the register is open, count the admissions in the preceding
    `trail` days. The alarm threshold is that disease's 90th percentile of that
    trailing count, floored at `floor` so a rare disease cannot alarm on one
    case. The first day the count crosses is the surge date; a `refractory`
    period then has to pass before the same disease can raise another, so one
    epidemic yields one date rather than a hundred consecutive ones.

    Days outside the register's open months are skipped, so a surge is never
    dated to the day a surviving notebook happens to begin.
    """
    if not days:
        return []
    counts = []
    for d in open_days:
        lo = d - dt.timedelta(days=trail - 1)
        counts.append((d, sum(n for k, n in days.items() if lo <= k <= d)))
    ranked = sorted(c for _, c in counts)
    if not ranked:
        return []
    threshold = max(floor, ranked[int(len(ranked) * 0.90)])
    out, last = [], None
    for d, c in counts:
        if c < threshold:
            continue
        if last and (d - last).days <= refractory:
            continue
        peak = max(n for e, n in counts
                   if d <= e <= d + dt.timedelta(days=refractory))
        out.append({"date": d, "trailing": c, "peak": peak,
                    "threshold": threshold})
        last = d
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=60,
                    help="days each side of the press date to count admissions")
    ap.add_argument("--trail", type=int, default=30,
                    help="trailing days the surge detector counts over")
    ap.add_argument("--refractory", type=int, default=120,
                    help="days before the same disease can surge again")
    ap.add_argument("--floor", type=int, default=3,
                    help="trailing admissions a surge needs at minimum")
    args = ap.parse_args()

    by_disease, deaths, open_months = load_register()
    open_days = []
    for m in sorted(open_months):
        y, mo = int(m[:4]), int(m[5:])
        d = dt.date(y, mo, 1)
        while d.strftime("%Y-%m") == m:
            open_days.append(d)
            d += dt.timedelta(days=1)
    surge_by = {g: surges(by_disease.get(g, {}), open_days, args.trail,
                          args.refractory, args.floor) for g in GROUPS}

    with open(CONC, newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))

    out_rows = []
    for row in rows:
        r = {k: row.get(k, "") for k in BASE_COLUMNS}
        r.update({k: "" for k in REG_COLUMNS})
        g = r["disease"]
        try:
            d = dt.date.fromisoformat(r["date"])
        except (ValueError, TypeError):
            out_rows.append(r)
            continue
        # only rows the dateline, window or paragraph places in Haifa get a
        # register comparison; a page-level co-occurrence is not a Haifa report
        if r["haifa"] not in ("dateline", "window", "paragraph"):
            out_rows.append(r)
            continue

        series, died = by_disease.get(g, {}), deaths.get(g, {})
        lo = d - dt.timedelta(days=args.window)
        hi = d + dt.timedelta(days=args.window)
        before = sum(n for k, n in series.items() if lo <= k < d)
        after = sum(n for k, n in series.items() if d < k <= hi)
        dbefore = sum(n for k, n in died.items() if lo <= k < d)
        covered = d.strftime("%Y-%m") in open_months
        r["reg_before"], r["reg_after"] = before, after
        r["reg_deaths_before"] = dbefore
        r["reg_coverage"] = "open" if covered else "absent"

        near = [s for s in surge_by[g] if abs((d - s["date"]).days) <= 120]
        near.sort(key=lambda s: abs((d - s["date"]).days))
        if near:
            s0 = near[0]
            r["surge"] = f"{s0['date'].isoformat()}(peak {s0['peak']}/30d)"
            r["days_after_surge"] = (d - s0["date"]).days

        if not covered:
            r["lead_lag"] = "no-register-coverage"
        elif near and (d - near[0]["date"]).days > 0:
            r["lead_lag"] = f"lags {(d - near[0]['date']).days}d"
        elif near:
            r["lead_lag"] = f"leads {(near[0]['date'] - d).days}d"
        elif before == 0 and after == 0:
            r["lead_lag"] = "no register cases either side"
        else:
            r["lead_lag"] = "register admitting, no surge"
        out_rows.append(r)

    with open(CONC, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(BASE_COLUMNS + REG_COLUMNS)
        for r in out_rows:
            w.writerow([r[k] for k in BASE_COLUMNS + REG_COLUMNS])

    # ---- aggregate, printed only; the file carries the per-row detail ----
    # Computed on the strict set: Haifa evidence from the item's own dateline
    # or from inside the window, no soft term, register open. الخناق rows in
    # particular are mostly the political idiom ("tightening the noose") and
    # would otherwise supply half of diphtheria's apparent leads.
    def strict(r):
        return (r["haifa"] in ("dateline", "window") and not r["soft_term"]
                and r["reg_coverage"] == "open")

    print(f"\n{len(out_rows)} windows -> {CONC}\n")
    print(f"{'disease':11} {'reg':>5} {'died':>5} {'surge':>5} {'haifa':>6} "
          f"{'strict':>6} {'lead':>5} {'lag':>4} {'medlag':>7} {'nocase':>6} "
          f"{'reported':>9}")
    for g in GROUPS:
        reg = sum(by_disease.get(g, {}).values())
        dd = sum(deaths.get(g, {}).values())
        hr = [r for r in out_rows if r["disease"] == g and r["reg_coverage"]]
        st = [r for r in hr if strict(r)]
        lead = [r for r in st if str(r["lead_lag"]).startswith("leads")]
        lag = [r for r in st if str(r["lead_lag"]).startswith("lags")]
        none = [r for r in st if r["lead_lag"] == "no register cases either side"]
        lags = sorted(int(r["days_after_surge"]) for r in lag)
        med = lags[len(lags) // 2] if lags else ""
        reported = sum(
            1 for s in surge_by[g]
            if any(abs((dt.date.fromisoformat(r["date"]) - s["date"]).days)
                   <= args.window for r in st))
        print(f"{g:11} {reg:5d} {dd:5d} {len(surge_by[g]):5d} {len(hr):6d} "
              f"{len(st):6d} {len(lead):5d} {len(lag):4d} {str(med):>7} "
              f"{len(none):6d} {reported:4d}/{len(surge_by[g]):<4d}")

    print(f"\nregister surges (trailing {args.trail}d over its own 90th "
          f"percentile, floor {args.floor}, {args.refractory}d refractory):")
    for g in GROUPS:
        if surge_by[g]:
            print(f"  {g:11} threshold {surge_by[g][0]['threshold']:3d}  " +
                  ", ".join(f"{s['date']}({s['peak']})" for s in surge_by[g]))


if __name__ == "__main__":
    main()
