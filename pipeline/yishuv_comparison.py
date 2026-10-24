#!/usr/bin/env python3
"""Old-yishuv Jews against immigrant Jews and against the other communities.

    python3 pipeline/yishuv_comparison.py              # all tables to stdout
    python3 pipeline/yishuv_comparison.py --tsv DIR    # also write profiles.tsv

Jewish patients are placed on two axes, deliberately kept apart:

1. Place tier, from data/public/yishuv-place-tiers.tsv (one ruling per place,
   keyed on City Wikidata, Haifa quarter, or an unlinked-spelling regex). The
   three old-yishuv tiers stay separate until a ruling merges them:
   old_core (holy cities), old_local (Haifa's Jewish quarters, Acre),
   early_moshava (First Aliyah / JCA, 1878-1914).
2. Nationality group. "Palestinian" in this column is a legal status, not an
   origin: its share among Jews runs ~0.7 in 1930-32, 0.2-0.5 in 1933-40 and
   ~0.8 in 1944-47, tracking naturalisation. It is never used as the old-yishuv
   proxy on its own; the validity table measures how far it follows place.

Staff (nurses and probationers admitted as patients), prisoners and police are
counted but kept out of the profiles: they reached the hospital by a route
that has nothing to do with where they lived. Notebook 25 and non-admissions
are excluded by load().
"""

import argparse
import csv
import re
import statistics
import sys
from collections import Counter, defaultdict
from math import sqrt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from history_figures import load  # noqa: E402  QUOTE_NONE + Atlit + non-admission rules

TIERS = Path(__file__).resolve().parent.parent / "data/public/yishuv-place-tiers.tsv"

JEWISH_TIERS = ("old_core", "old_local", "early_moshava", "later_moshava",
                "labour", "new_urban", "arab_or_mixed", "haifa_unplaced")
MIDEAST_BALKAN = {"Turkish", "Persian", "Yemeni", "Syrian", "Greek", "Bulgarian",
                  "Egyptian", "Iraqi", "Lebanese", "Yugoslavian", "Moroccan",
                  "Tunisian", "Algerian", "Kurdish", "Bukharan", "Afghan", "Indian"}
PERIODS = {"1930-32": (1930, 1932), "1933-40": (1933, 1940), "1944-48": (1944, 1948)}

STAFF = re.compile(r"nurse|prob|matron|sister|orderly|attendant|dresser|ward ?maid", re.I)
POLICE = re.compile(r"police|constable|\bB/C\b|gendarm", re.I)


def load_tiers():
    """Each ruling is (tier, basis). basis "nationality" marks a place tiered
    by its patients' nationality mix; those rows must stay out of the test of
    whether nationality follows place, or the test is circular."""
    by_qid, by_quarter, by_regex, by_address = {}, {}, [], []
    with TIERS.open(encoding="utf-8", newline="") as fh:
        for t in csv.DictReader(fh, delimiter="\t"):
            ruling = (t["tier"], t["basis"])
            if t["key_type"] == "wikidata":
                by_qid[t["key"]] = ruling
            elif t["key_type"] == "neighbourhood":
                by_quarter[t["key"]] = ruling
            elif t["key_type"] == "address_regex":
                by_address.append((re.compile(t["key"]), t["scope"], ruling))
            else:
                by_regex.append((re.compile(t["key"]), ruling))
    return by_qid, by_quarter, by_regex, by_address


def place_tier(r, tiers):
    """Address rules first (in file order): clerks wrote a town for its whole
    sub-district, so "Kinereth. Tiberias" is a kibbutz, not the old city. A
    rule with a scope applies only under that City Wikidata ID."""
    by_qid, by_quarter, by_regex, by_address = tiers
    q, n, c = (r["City Wikidata"] or "").strip(), (r["Neighbourhood"] or "").strip(), (r["City"] or "").strip()
    a = r["Address"] or ""
    for rx, scope, ruling in by_address:
        if (not scope or scope == q) and rx.search(a):
            return ruling
    if q == "Q41621" and n in by_quarter:
        return by_quarter[n]
    if q:
        return by_qid.get(q, ("unruled", ""))
    for rx, ruling in by_regex:
        if c and rx.search(c):
            return ruling
    return ("no_place", "") if not c else ("unruled", "")


def nat_group(r):
    nat = (r["Nationality"] or "").strip()
    if not nat:
        return "blank"
    if nat.startswith("Palestinian"):
        return "Palestinian"
    return "foreign_mideast" if nat in MIDEAST_BALKAN else "foreign_europe"


def route(r):
    """Why a patient's residence may not explain their admission."""
    occ, inst = r["Occupation"] or "", r["Address institution"] or ""
    if STAFF.search(occ) or inst == "Government Hospital":
        return "staff"
    if re.search(r"prisoner|detainee", occ, re.I) or inst == "Prison" or r["Ward"] == "Prison Ward":
        return "prisoner"
    if POLICE.search(occ) or re.search(r"warden|regiment|\bBat\b", occ) or inst in ("Police", "British Army"):
        return "police"
    return ""


def year(r):
    d = (r["Admission Date"] or "")[:4]
    return int(d) if d.isdigit() else None


def age_years(r):
    try:
        a = float(r["Age"])
    except ValueError:
        return None
    unit = (r["Age Unit"] or "").lower()
    if unit.startswith(("m", "d", "w")):
        return 0.0
    return a


def community(r):
    rel = r["Religion"]
    if rel == "Muslim":
        return "Muslim"
    if rel == "Druze":
        return "Druze"
    if rel == "Christian":
        nat = r["Nationality"] or ""
        if nat.startswith("Palestinian") and "British" not in nat:
            return "Christian, Palestinian"
        if nat == "British":
            return "Christian, British"
        return "Christian, other"
    return None


def annotate(rows):
    tiers = load_tiers()
    for r in rows:
        r["_year"] = year(r)
        r["_age"] = age_years(r)
        r["_route"] = route(r)
        if r["Religion"] == "Jewish":
            r["_tier"], r["_basis"] = place_tier(r, tiers)
            r["_nat"] = nat_group(r)
        else:
            r["_comm"] = community(r)
    return rows


def wilson(k, n, z=1.96):
    if not n:
        return (0, 0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * (c - h), 100 * (c + h))


def share(rows, test, base=lambda r: True):
    b = [r for r in rows if base(r)]
    k = sum(1 for r in b if test(r))
    return k, len(b)


def chapter(prefix):
    return lambda r: (r["ICD-9 Chapter"] or "").startswith(prefix)


MEASURES = [
    ("female %", lambda r: r["Sex"] == "Female", lambda r: r["Sex"] in ("Male", "Female")),
    ("age 0-14 %", lambda r: r["_age"] < 15, lambda r: r["_age"] is not None),
    ("age 50+ %", lambda r: r["_age"] >= 50, lambda r: r["_age"] is not None),
    ("1st/2nd class %", lambda r: r["Class"] in ("1", "2", "2P", "2S"), lambda r: r["Class"] in ("1", "2", "2P", "2S", "3")),
    ("infectious %", chapter("001"), lambda r: bool(r["ICD-9 Chapter"])),
    ("injury %", chapter("800"), lambda r: bool(r["ICD-9 Chapter"])),
    ("childbirth % of women", chapter("630"), lambda r: bool(r["ICD-9 Chapter"]) and r["Sex"] == "Female"),
    ("mental %", chapter("290"), lambda r: bool(r["ICD-9 Chapter"])),
    ("isolation ward %", lambda r: r["Ward"].startswith("Isolation"), lambda r: bool(r["Ward"])),
    ("died %", lambda r: r["Result"] == "Died", lambda r: bool(r["Result"])),
    ("left vs advice %", lambda r: r["Result"] == "Left Against Advice", lambda r: bool(r["Result"])),
]


def median_stay(rows):
    v = []
    for r in rows:
        try:
            d = float(r["Days in Hospital"])
        except ValueError:
            continue
        if 0 <= d < 1000:
            v.append(d)
    return (statistics.median(v), len(v)) if v else (None, 0)


def profile(rows):
    out = {"n": len(rows)}
    ages = [r["_age"] for r in rows if r["_age"] is not None]
    out["median age"] = f"{statistics.median(ages):.0f}" if ages else ""
    for name, test, base in MEASURES:
        k, n = share(rows, test, base)
        out[name] = f"{100 * k / n:.0f}" if n >= 10 else ("·" if n else "")
        if name == "died %" and n:
            lo, hi = wilson(k, n)
            out[name] += f" [{lo:.0f}-{hi:.0f}]"
    m, n = median_stay(rows)
    out["median stay (d)"] = f"{m:.0f}" if m is not None else ""
    return out


def table(title, groups, cols=None):
    profs = {g: profile(rs) for g, rs in groups.items() if rs}
    if not profs:
        return []
    cols = cols or list(next(iter(profs.values())).keys())
    print(f"\n### {title}\n")
    print("| group | " + " | ".join(cols) + " |")
    print("|---|" + "---|" * len(cols))
    for g, p in profs.items():
        print(f"| {g} | " + " | ".join(str(p.get(c, "")) for c in cols) + " |")
    return [{"table": title, "group": g, **p} for g, p in profs.items()]


def in_period(r, p):
    lo, hi = PERIODS[p]
    return r["_year"] is not None and lo <= r["_year"] <= hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tsv", help="directory to write profiles.tsv into")
    args = ap.parse_args()

    rows = annotate(load())
    jews = [r for r in rows if r["Religion"] == "Jewish"]

    print("## Cohort sizes\n")
    print(f"Jewish admissions: {len(jews)}; arrived by an institutional route: "
          + ", ".join(f"{k} {v}" for k, v in Counter(r['_route'] for r in jews if r['_route']).most_common()))
    unruled = Counter((r["City"], r["City Wikidata"]) for r in jews if r["_tier"] == "unruled")
    if unruled:
        print(f"UNRULED places ({sum(unruled.values())} records): {unruled.most_common(10)}")

    # --- validity: does nationality follow place? ---
    print("\n## Validity test: nationality group by place tier\n")
    print(f"(places tiered by nationality left out: {sum(1 for r in jews if r['_basis'] == 'nationality')} records)\n")
    tiers = [t for t in JEWISH_TIERS] + ["ambiguous", "institutional", "no_place"]
    nats = ("Palestinian", "foreign_europe", "foreign_mideast", "blank")
    print("| tier | n | " + " | ".join(nats) + " | Palestinian % 1930-32 | 1933-40 | 1944-48 |")
    print("|---|---|" + "---|" * (len(nats) + 3))
    for t in tiers:
        rs = [r for r in jews if r["_tier"] == t and r["_basis"] != "nationality"]
        c = Counter(r["_nat"] for r in rs)
        per = []
        for p in PERIODS:
            k, n = share(rs, lambda r: r["_nat"] == "Palestinian", lambda r, p=p: in_period(r, p) and r["_nat"] != "blank")
            per.append(f"{100 * k / n:.0f} (n={n})" if n >= 10 else (f"· (n={n})" if n else ""))
        print(f"| {t} | {len(rs)} | " + " | ".join(str(c[x]) for x in nats) + " | " + " | ".join(per) + " |")

    # --- profiles ---
    civil = [r for r in rows if not r["_route"]]
    cj = [r for r in civil if r["Religion"] == "Jewish"]
    out = []

    def comparison_groups(pool):
        g = {}
        for t in JEWISH_TIERS:
            g[f"J · {t}"] = [r for r in pool if r["Religion"] == "Jewish" and r["_tier"] == t]
        for nat in ("Palestinian", "foreign_europe", "foreign_mideast"):
            g[f"J · nat {nat}"] = [r for r in pool if r["Religion"] == "Jewish" and r["_nat"] == nat]
        g["J · old tiers & Palestinian"] = [r for r in pool if r["Religion"] == "Jewish"
                                            and r["_tier"] in ("old_core", "old_local") and r["_nat"] == "Palestinian"]
        g["J · new tiers & Palestinian, under 15"] = [r for r in pool if r["Religion"] == "Jewish"
                                                     and r["_tier"] in ("labour", "new_urban", "later_moshava")
                                                     and r["_nat"] == "Palestinian" and r["_age"] is not None and r["_age"] < 15]
        for c in ("Muslim", "Christian, Palestinian", "Christian, British", "Druze"):
            g[c] = [r for r in pool if r.get("_comm") == c]
        return g

    print("\n## Profiles (institutional routes excluded)")
    out += table("All years", comparison_groups(civil))
    for p in PERIODS:
        out += table(f"Period {p}", comparison_groups([r for r in civil if in_period(r, p)]))

    # --- neighbour design: same town, different community ---
    print("\n## Neighbour design: same town, by community")
    towns = {"Tiberias": "Q151920", "Acre": "Q126084", "Safed": "Q188336"}
    for town, q in towns.items():
        pool = [r for r in civil if r["City Wikidata"] == q]
        # Jews only where the address rules left them in the town itself
        g = {"Jewish": [r for r in pool if r["Religion"] == "Jewish" and r["_tier"] in ("old_core", "old_local")]}
        for c in ("Muslim", "Christian, Palestinian"):
            g[c] = [r for r in pool if r.get("_comm") == c]
        out += table(town, g)
    haifa_old = [r for r in cj if r["_tier"] == "old_local" and r["City Wikidata"] != "Q126084"]
    arab_q = [r for r in civil if r["City Wikidata"] == "Q41621" and r["Religion"] != "Jewish"
              and r["Neighbourhood"] in ("Haifa: Wadi Nisnas", "Haifa: Halisa", "Haifa: Burj", "Haifa: Wadi Salib",
                                         "Haifa: Harat al-Mukhallis", "Haifa: Harat al-Kanais", "Haifa: Acre Gate",
                                         "Haifa: Shawafna", "Haifa: Wadi Rushmiya")]
    out += table("Haifa: Jewish quarters vs downtown Arab quarters",
                 {"Jews, Ard/Harat al-Yahud": haifa_old,
                  "Muslims, Arab quarters": [r for r in arab_q if r.get("_comm") == "Muslim"],
                  "Christians, Arab quarters": [r for r in arab_q if (r.get("_comm") or "").startswith("Christian")]})

    if args.tsv:
        d = Path(args.tsv)
        d.mkdir(parents=True, exist_ok=True)
        keys = list(dict.fromkeys(k for o in out for k in o))
        with (d / "profiles.tsv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, keys, delimiter="\t", lineterminator="\n")
            w.writeheader()
            w.writerows(out)


if __name__ == "__main__":
    main()
