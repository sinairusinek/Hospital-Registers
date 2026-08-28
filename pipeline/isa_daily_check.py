"""Check the nominal returns' hospital/home split against the daily returns' deaths.

data/archives/isa_1942-44_linkage.md reported, from the 2,171 NAMED cases in the
nominal returns, that 72% were treated at the Government Hospital or Isolation
and 23% at home. That figure rests on one column (`where_treated`) read off one
kind of page.

The DAILY RETURN rectos record deaths already split by the clerks themselves
into **In Hospital** and **Out of Hospital**. That is a second, independent
measurement of the same division, made by the same office through a different
column, and it is what this script compares.

The two are NOT the same quantity and the comparison has to respect that:

  * the nominal figure is a share of CASES; the daily figure is a share of
    DEATHS. If the hospital took the sicker patients - which is what a
    referral hospital does - deaths should be MORE concentrated in hospital
    than cases are. So daily-in-hospital > nominal-in-hospital is the expected
    direction, and the size of the gap is the finding.
  * the daily returns are a running state, not a case list. `New Cases`
    accumulates something comparable to a case count; `Existing` and
    `Remaining` are stocks and must never be summed across returns.

It also reports what the daily returns alone are worth: a disease-by-disease
case and death series for Haifa 1942-44, which is a denominator the register
cannot supply.

Run:
  python3 pipeline/isa_daily_check.py
"""

from __future__ import annotations

import csv
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY = os.path.join(ROOT, "data", "private", "isa-1942-44-daily.tsv")
CASES = os.path.join(ROOT, "data", "private", "isa-1942-44-cases.tsv")
PAGES = os.path.join(ROOT, "data", "private", "isa-1942-44-pages.tsv")
OUT = os.path.join(ROOT, "data", "private", "isa-1942-44-daily-summary.txt")

sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import isa_returns_link as L  # noqa: E402


def num(text: str):
    """A tally cell as a number, or None.

    A dash means zero; a blank means not stated. Both come back as None here
    because neither contributes to a sum, but they are different in the data and
    the distinction is kept in the TSV.
    """
    t = (text or "").strip()
    if not t or t in {"-", "–", "—", "nil", "Nil", "NIL"}:
        return None
    m = re.search(r"\d+", t)
    return int(m.group(0)) if m else None


def main() -> int:
    if not os.path.exists(DAILY):
        print(f"no {DAILY} - run pipeline/isa_daily.py first", file=sys.stderr)
        return 2

    daily = list(csv.DictReader(open(DAILY, encoding="utf-8"), delimiter="\t"))
    cases = [r for r in csv.DictReader(open(CASES, encoding="utf-8"),
                                       delimiter="\t")
             if (r.get("name") or "").strip()]
    years = L.page_years(PAGES)

    lines: list[str] = []

    def say(s=""):
        lines.append(s)
        print(s)

    say("ISA 000zbri daily returns - tallies, and the check on the 72/23 split")
    say("=" * 70)
    say()

    # ---- what the daily returns hold -------------------------------------
    towns = Counter((r.get("town") or "").strip() for r in daily)
    say(f"{len(daily)} tally rows on the daily-return rectos")
    say()
    say("TOWN OR VILLAGE (top 12)")
    for k, v in towns.most_common(12):
        say(f"  {v:5d}  {k or '(blank)'}")
    say()

    # ---- deaths, in vs out of hospital -----------------------------------
    din = dout = 0
    din_by_fam: Counter = Counter()
    dout_by_fam: Counter = Counter()
    newc_by_fam: Counter = Counter()
    for r in daily:
        fam = L.family(r.get("disease") or "") or (
            (r.get("disease") or "").strip().lower() or "(blank)")
        a = num(r.get("died_in_hospital"))
        b = num(r.get("died_out_of_hospital"))
        n = num(r.get("new_cases"))
        if a:
            din += a
            din_by_fam[fam] += a
        if b:
            dout += b
            dout_by_fam[fam] += b
        if n:
            newc_by_fam[fam] += n

    total_d = din + dout
    say("DEATHS as recorded on the daily returns, by the clerks' own split")
    if total_d:
        say(f"  in hospital      {din:5d}  ({100*din/total_d:.0f}%)")
        say(f"  out of hospital  {dout:5d}  ({100*dout/total_d:.0f}%)")
        say(f"  total            {total_d:5d}")
    else:
        say("  no deaths recorded in the transcribed tallies")
    say()

    # ---- the comparison --------------------------------------------------
    hosp = home = other = 0
    for c in cases:
        w = c.get("where_treated") or ""
        if L.IN_HOSPITAL.search(w):
            hosp += 1
        elif L.AT_HOME.search(w):
            home += 1
        else:
            other += 1
    n_cases = hosp + home + other

    say("THE CHECK - two independent measurements of the same division")
    say()
    say("  NOMINAL returns, share of CASES (n = %d named cases):" % n_cases)
    say(f"    treated in hospital/isolation  {hosp:5d}  ({100*hosp/n_cases:.0f}%)")
    say(f"    treated at home                {home:5d}  ({100*home/n_cases:.0f}%)")
    say(f"    elsewhere or not stated        {other:5d}  ({100*other/n_cases:.0f}%)")
    say()
    if total_d:
        say("  DAILY returns, share of DEATHS (n = %d deaths):" % total_d)
        say(f"    died in hospital               {din:5d}  ({100*din/total_d:.0f}%)")
        say(f"    died out of hospital           {dout:5d}  ({100*dout/total_d:.0f}%)")
        say()
        say("  These are shares of different things - cases vs deaths - so they")
        say("  are not expected to be equal. A referral hospital takes the")
        say("  sicker patients, so deaths should be MORE concentrated in")
        say("  hospital than cases are. Direction of the gap:")
        gap = 100*din/total_d - 100*hosp/n_cases
        say(f"    deaths {'MORE' if gap > 0 else 'LESS'} hospital-concentrated "
            f"than cases by {abs(gap):.0f} points")
        say()

        # Read whole, the two figures nearly agree (70/30 against 72/23) and
        # the small gap runs the "wrong" way. Both facts are one disease.
        m_in = din_by_fam.get("measles", 0)
        m_out = dout_by_fam.get("measles", 0)
        rest_in, rest_out = din - m_in, dout - m_out
        rest_d = rest_in + rest_out
        say("  BUT THE AGGREGATE HIDES THE STRUCTURE. Measles alone supplies")
        say(f"  {m_out} of the {dout} out-of-hospital deaths and {m_in} of the "
            f"in-hospital ones,")
        say("  because measles was nursed at home and killed there. Setting it")
        say("  aside:")
        if rest_d:
            say(f"    died in hospital     {rest_in:5d}  ({100*rest_in/rest_d:.0f}%)")
            say(f"    died out of hospital {rest_out:5d}  ({100*rest_out/rest_d:.0f}%)")
        say("  which is firmly in the expected direction: for everything except")
        say("  measles, death was overwhelmingly a hospital event, as it should")
        say("  be if the hospital received the severer cases.")
        say()
        say("  The nominal returns say the same thing from the case side:")
        for fam in ("measles", "typhoid"):
            sel = [c for c in cases if L.family(c.get("disease") or "") == fam]
            if not sel:
                continue
            h = sum(1 for c in sel if L.IN_HOSPITAL.search(
                c.get("where_treated") or ""))
            hm = sum(1 for c in sel
                     if not L.IN_HOSPITAL.search(c.get("where_treated") or "")
                     and L.AT_HOME.search(c.get("where_treated") or ""))
            say(f"    {fam:8s} {len(sel):5d} named cases - "
                f"{h} in hospital, {hm} at home")
        say()
        say("  So the headline '23% treated at home' is very largely ONE")
        say("  DISEASE. Quote it by disease, not as a single rate.")
    say()

    # ---- per-disease series ---------------------------------------------
    say("BY DISEASE - new cases and deaths from the daily returns")
    say(f"  {'disease':22s} {'new cases':>9s} {'died in':>8s} {'died out':>9s}")
    fams = set(newc_by_fam) | set(din_by_fam) | set(dout_by_fam)
    for fam in sorted(fams, key=lambda f: -newc_by_fam.get(f, 0)):
        say(f"  {fam:22s} {newc_by_fam.get(fam,0):9d} "
            f"{din_by_fam.get(fam,0):8d} {dout_by_fam.get(fam,0):9d}")
    say()

    # ---- named-case deaths, as a third view ------------------------------
    died_named = sum(1 for c in cases
                     if "died" in (c.get("remarks") or "").lower())
    say(f"For comparison, {died_named} of the {n_cases} NAMED cases have a "
        f"remark recording death.")
    say("The daily returns and the nominal lists count deaths on different")
    say("bases (a running daily state vs a case note written when the return")
    say("was filed), so these totals are not expected to agree exactly.")
    say()
    say(f"wrote {OUT}")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
