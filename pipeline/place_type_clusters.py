"""Find bursts of same-type admissions from one place within a few days.

The Afikim typhoid outbreak (28-31 July 1938) and the Haifa market bombings
(6 and 25 July 1938) share a shape: many admissions of one kind, from one
place, inside a day or two. This scans the whole register for that shape.

For every (place, type) pair it slides a WINDOW-day window over admission
dates and compares the count inside it with what that place usually sends
of that type: the same pair's admissions in the surrounding +/-BASE_DAYS,
excluding the window itself, scaled to the window length. The tail
probability under a Poisson model scores the surprise.

"Type" is read at two grains, because an event does not always share one
code - a bombing spreads over fractures, burns and wounds, an outbreak over
typhoid, "fever" and "observation for typhoid":
  - ICD-9 category (3 digits), e.g. 002 typhoid, 084 malaria
  - ICD-9 chapter for infectious (001-139) and injury (800-999 + E codes)
Overlapping hits for the same place are merged into one event.

"Place" is the City column, keyed on its Wikidata (else Kima) id so that
"Affikim" and "Kibutz Affikim" count as one place. Notebook 25 (Atlit camp) is excluded.

Writes data/public/place-type-clusters.tsv, one row per event, strongest
first, tiered "strong" (p < 1e-6) or "candidate" (p < --p). These are leads to read on the page and in the press, not findings:
a clerk who copied one address down a column can make a cluster too.

Run: python3 pipeline/place_type_clusters.py [--window 3] [--min-n 5] [--p 1e-6]
"""

from __future__ import annotations

import argparse
import bisect
import csv
import datetime as dt
import math
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "app", "public", "data", "hospital-registers.tsv")
OUT = os.path.join(ROOT, "data", "public", "place-type-clusters.tsv")

CHAPTER_GROUPS = {
    "001-139": "infectious (chapter)",
    "800-999": "injury (chapter)",
    "E800-E999": "injury (chapter)",
}


def parse_date(s):
    try:
        return dt.date.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def log10_poisson_sf(n: int, mu: float) -> float:
    """log10 P(X >= n) for X ~ Poisson(mu), summed in log space so the
    strongest events do not all underflow to the same floor."""
    terms = [k * math.log(mu) - mu - math.lgamma(k + 1) for k in range(n, n + 400)]
    top = max(terms)
    return (top + math.log(sum(math.exp(t - top) for t in terms))) / math.log(10)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=3, help="days, inclusive")
    ap.add_argument("--base-days", type=int, default=365)
    ap.add_argument("--min-n", type=int, default=5)
    ap.add_argument("--p", type=float, default=1e-4,
                    help="keep events below this; under 1e-6 they are tiered 'strong'")
    args = ap.parse_args()

    rows = []
    covered = set()  # days the surviving register has any admission at all
    names: dict[str, Counter] = defaultdict(Counter)
    with open(REG, newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r.get("Notebook_Number") == "25":
                continue
            d = parse_date(r.get("Admission Date"))
            if d:
                covered.add(d.toordinal())
            city = (r.get("City") or "").split("|")[0].strip()
            # spelling variants of one place share a Wikidata/Kima id
            place = r.get("City Wikidata") or r.get("City Kima ID") or city
            if d and place:
                r["_d"], r["_place"] = d, place
                names[place][city] += 1
                rows.append(r)

    cov = sorted(covered)

    def covered_days(a: int, b: int) -> int:
        return bisect.bisect_right(cov, b) - bisect.bisect_left(cov, a)

    # (place, type) -> rows; each type also belongs to a family, and only
    # hits of one family merge (a bombing must not absorb a typhoid case)
    keyed: dict[tuple, list] = defaultdict(list)
    family: dict[str, str] = {}
    for r in rows:
        cat = (r.get("ICD-9 Category") or "").strip()
        chap = (r.get("ICD-9 Chapter") or "").split(" ")[0]
        fam = CHAPTER_GROUPS.get(chap, "").split(" ")[0] or "cat:" + cat
        if cat:
            keyed[(r["_place"], "cat:" + cat)].append(r)
            family["cat:" + cat] = fam
        if chap in CHAPTER_GROUPS:
            key = "chap:" + CHAPTER_GROUPS[chap]
            keyed[(r["_place"], key)].append(r)
            family[key] = fam

    W, B = args.window, args.base_days
    hits = []  # (place, key, start, end, n, mu, p, rows)
    for (place, key), rs in keyed.items():
        if len(rs) < args.min_n:
            continue
        rs.sort(key=lambda r: r["_d"])
        ds = [r["_d"].toordinal() for r in rs]
        for i, start in enumerate(ds):
            j = bisect.bisect_right(ds, start + W - 1)
            n = j - i
            if n < args.min_n:
                continue
            lo = bisect.bisect_left(ds, start - B)
            hi = bisect.bisect_right(ds, start + W - 1 + B)
            if key == "chap:infectious (chapter)":
                # a chapter-level outbreak must still be mostly one disease;
                # otherwise it is a busy week of unrelated infections
                top = Counter(r.get("ICD-9 Category") for r in rs[i:j]).most_common(1)[0][1]
                if top < 0.5 * n:
                    continue
            # the rate per day the register survives, not per calendar day:
            # the lost 1942-43 notebooks must not deflate the baseline
            days = (covered_days(start - B, start - 1)
                    + covered_days(start + W, start + W - 1 + B))
            mu = (hi - lo - n) / max(days, 1) * W
            mu = max(mu, W / max(days, 1))  # never below one case in the baseline
            p = log10_poisson_sf(n, mu)
            if p < math.log10(args.p):
                hits.append((place, key, ds[i], ds[j - 1], n, mu, p, rs[i:j]))

    # merge overlapping hits per place and family into events
    hits.sort(key=lambda h: (h[0], family[h[1]], h[2]))
    events = []
    for h in hits:
        place, key, s, e, n, mu, p, rs = h
        ev = events[-1] if events else None
        if (ev and ev["place"] == place and ev["family"] == family[key]
                and s <= ev["end"] + 1):
            ev["end"] = max(ev["end"], e)
            ev["rows"].update(id(r) for r in rs)
            ev["objs"].update({id(r): r for r in rs})
            if p < ev["p"]:
                ev.update(p=p, n=n, mu=mu, key=key)
        else:
            events.append(dict(place=place, family=family[key], key=key, start=s, end=e, n=n,
                               mu=mu, p=p, rows={id(r) for r in rs},
                               objs={id(r): r for r in rs}))

    out = []
    for ev in events:
        rs = sorted(ev["objs"].values(), key=lambda r: r["_d"])
        diag = Counter((r.get("Diagnosis") or r.get("Diagnosis as standardized") or "?").strip() for r in rs)
        rel = Counter(r.get("Religion") or "?" for r in rs)
        sex = Counter(r.get("Sex") or "?" for r in rs)
        died = sum(1 for r in rs if (r.get("Result") or "").lower().startswith("died"))
        pages = sorted({r.get("Notebook-page") or f"NB{r.get('Notebook_Number')}" for r in rs})
        days = Counter(r["_d"].isoformat() for r in rs)
        ages = [float(r["Age"]) for r in rs if (r.get("Age") or "").replace(".", "", 1).isdigit()
                and (r.get("Age Unit") or "y").lower().startswith("y")]
        out.append({
            "tier": "strong" if ev["p"] < -6 else "candidate",
            "start": dt.date.fromordinal(ev["start"]).isoformat(),
            "end": dt.date.fromordinal(ev["end"]).isoformat(),
            "place": names[ev["place"]].most_common(1)[0][0],
            "type": ev["key"].split(":", 1)[1],
            "n_records": len(rs),
            "peak_window_n": ev["n"],
            "expected": round(ev["mu"], 2),
            "log10_p": round(ev["p"], 1),
            "died": died,
            "by_day": "; ".join(f"{k}:{v}" for k, v in sorted(days.items())),
            "diagnoses": "; ".join(f"{k} ({v})" for k, v in diag.most_common(6)),
            "religion": "; ".join(f"{k} {v}" for k, v in rel.most_common()),
            "sex": "; ".join(f"{k} {v}" for k, v in sex.most_common()),
            "age_range": f"{min(ages):g}-{max(ages):g}" if ages else "",
            "pages": " ".join(pages),
        })
    out.sort(key=lambda o: o["log10_p"])

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]), delimiter="\t")
        w.writeheader()
        w.writerows(out)
    print(f"{len(out)} events -> {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
