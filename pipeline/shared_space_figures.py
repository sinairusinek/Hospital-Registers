#!/usr/bin/env python3
"""Build the Shared Space view's figures: data/public/shared-space.json.

The question this answers is whether the Government Hospital was a common space
for Arabs, Jews and Britons, and it is answered from two sides that disagree
productively. The 1936 Schedule of Accommodation (ISA 0005xx0) designed exactly
one group-specific unit — the 24-bed British Section — and divided everything
else by sex, function and *class*. The register then shows the medical wards
genuinely mixed. So the segregation that existed ran along nationality and
class, not confession, and that is what these figures are built to show.

    python3 pipeline/shared_space_figures.py            # write the JSON
    python3 pipeline/shared_space_figures.py --report   # tables to stdout

The method decisions follow pipeline/history_figures.py, which see for the long
form. The three that matter:

1. QUOTE_NONE. Free-text cells (Diagnosis as written, Address) carry unbalanced
   quote characters; csv's default quoting merges rows and loses 153 of them,
   149 in one contiguous stretch of Notebook 3. Never read this file with
   default quoting.

2. Religion percentages use an M+C+J denominator, not "any recorded value" —
   the 78 Bahai/Druze/Arab/unparseable rows leave both numerator and
   denominator. Class percentages use all rows with a recorded Class.

3. Notebook 25 (the Atlit camp register, 965 rows, 1940, 962 of them Jewish and
   all Athlit) is excluded throughout, as everywhere else in the project.

One extra decision is local to this script. The "mixed" grouping crosses
Religion with Nationality, because the undifferentiated Christian category is
an artefact: it pools British officials with Palestinian Arabs and so invents a
prosperous "Christian" population that does not exist. British nationality here
means Nationality of British or Palestinian British; the latter is only 27 rows
but belongs on the British side of the line the register itself draws.
"""

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TSV = ROOT / "data/public/hospital-registers-normalized.tsv"
OUT = ROOT / "data/public/shared-space.json"

ATLIT_NOTEBOOK = "25"
MCJ = ("Muslim", "Christian", "Jewish")
BRITISH_NAT = {"British", "Palestinian British"}

# The register's ward labels, in the order the 1936 schedule lists its units, so
# the chart reads as the building and not as a ranking. Compound labels ("A | B",
# 130 rows) are left out: a record in two wards cannot sit in one bar.
WARD_ORDER = [
    "Surgical", "Medical", "General", "Maternity",
    "Isolation", "Infectious Diseases", "Venereal Diseases",
    "British Section",
]

# The mixed grouping, in the order the charts use.
MIXED_ORDER = [
    "Muslim",
    "Christian, Palestinian nat.",
    "Christian, British nat.",
    "Jewish, Palestinian nat.",
    "Jewish, other/unrecorded nat.",
]

# Occupation substrings that mark a hospital worker. Deliberately narrow: these
# are the register's own words, and "ward" is excluded because "warder" is a
# prison officer, not a nurse.
STAFF_WORDS = ("nurse", "doctor", "dr.", "midwife", "matron", "orderly",
               "dresser", "probationer", "wardmaid", "ward maid")


def load():
    """Every non-Atlit register row, read the one way that does not lose 153."""
    with TSV.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE))
    return [r for r in rows if (r.get("Notebook_Number") or "").strip() != ATLIT_NOTEBOOK]


def g(row, col):
    return (row.get(col) or "").strip()


def year(row):
    d = g(row, "Admission Date")
    return d[:4] if len(d) >= 4 and d[:4].isdigit() else ""


def ward(row):
    """The ward as a single unit, or '' for blank and compound labels."""
    w = g(row, "Ward")
    return w if w in WARD_ORDER else ""


def klass(row):
    """Class as 1, 2 or 3. '2P', '3rd?' and '2S' all carry their digit."""
    c = g(row, "Class")
    for k in ("1", "2", "3"):
        if c.startswith(k):
            return k
    return ""


def mixed(row):
    """Religion crossed with nationality — see the module docstring."""
    rel, nat = g(row, "Religion"), g(row, "Nationality")
    if rel == "Christian":
        if nat in BRITISH_NAT:
            return "Christian, British nat."
        if nat == "Palestinian":
            return "Christian, Palestinian nat."
        return ""       # 684 rows, too heterogeneous to name
    if rel == "Muslim":
        return "Muslim"
    if rel == "Jewish":
        return "Jewish, Palestinian nat." if nat == "Palestinian" else "Jewish, other/unrecorded nat."
    return ""


def is_staff(row):
    occ = g(row, "Occupation").lower()
    return any(w in occ for w in STAFF_WORDS)


def died(row):
    return g(row, "Result") == "Died"


def pct(part, whole):
    return round(100 * part / whole, 1) if whole else None


def cfr(rows):
    """Case-fatality rate over rows with a recorded result."""
    seen = [r for r in rows if g(r, "Result")]
    if not seen:
        return None, 0
    return round(100 * sum(1 for r in seen if died(r)) / len(seen), 2), len(seen)


# --- the figures ------------------------------------------------------------

def fig_ward_mix(rows):
    """Ward composition by religion: the wards were mixed, one was not."""
    out = []
    for w in WARD_ORDER:
        sub = [r for r in rows if ward(r) == w and g(r, "Religion") in MCJ]
        if len(sub) < 20:
            continue
        c = Counter(g(r, "Religion") for r in sub)
        out.append({"ward": w, "n": len(sub),
                    **{m: pct(c[m], len(sub)) for m in MCJ}})
    allrel = [r for r in rows if g(r, "Religion") in MCJ]
    c = Counter(g(r, "Religion") for r in allrel)
    return {"wards": out,
            "baseline": {"ward": "All admissions", "n": len(allrel),
                         **{m: pct(c[m], len(allrel)) for m in MCJ}}}


def fig_page_mixing(rows):
    """Were the groups entered intermixed, or batched by group?

    Two tests. The ledger-page test asks how many religions share a page; the
    register was kept in admission order, so a page is a slice of real time. The
    adjacency test asks whether consecutive admissions to the same ward share a
    religion more often than the ward's own composition would produce by chance
    — the null is sum(p^2), and a ward that clusters sits well above it.
    """
    pages = defaultdict(list)
    for r in rows:
        if g(r, "Religion") in MCJ:
            pages[(g(r, "Notebook_Number"), g(r, "Page_Number"))].append(r)
    full = [p for p in pages.values() if len(p) >= 8]
    spread = Counter(len(set(g(r, "Religion") for r in p)) for p in full)

    adjacency = []
    for w in WARD_ORDER:
        sub = [r for r in rows if ward(r) == w and g(r, "Religion") in MCJ]
        if len(sub) < 200:
            continue
        sub.sort(key=lambda r: (g(r, "Admission Date"), g(r, "Notebook_Number"),
                                g(r, "Page_Number"), g(r, "Index")))
        same = sum(1 for a, b in zip(sub, sub[1:])
                   if g(a, "Religion") == g(b, "Religion"))
        c = Counter(g(r, "Religion") for r in sub)
        chance = sum((v / len(sub)) ** 2 for v in c.values())
        adjacency.append({
            "ward": w, "n": len(sub),
            "observed": round(100 * same / (len(sub) - 1), 1),
            "chance": round(100 * chance, 1),
            "excess": round(100 * same / (len(sub) - 1) - 100 * chance, 1),
        })
    return {
        "pages": {"n": len(full),
                  "allThree": spread[3], "allThreePct": pct(spread[3], len(full)),
                  "two": spread[2], "twoPct": pct(spread[2], len(full)),
                  "single": spread[1], "singlePct": pct(spread[1], len(full))},
        "adjacency": adjacency,
    }


def fig_british_section(rows):
    """Who was admitted to the one segregated unit, and how full was it?

    The 1936 schedule designs 24 beds — a 6-bed male ward plus 4 male single
    rooms, and 6 female single rooms. Occupancy is bed-days over 365, which
    understates the years the register covers only in part (1940, 1948); those
    are reported with their admission count so the reader can see why.
    """
    bs = [r for r in rows if g(r, "Ward").startswith("British Section")]
    by_rel = Counter(g(r, "Religion") for r in bs)
    by_nat = Counter(g(r, "Nationality") for r in bs)

    # The non-British admissions are the interesting ones: who got in?
    non_brit = [r for r in bs if g(r, "Nationality") not in BRITISH_NAT]
    occ = Counter(g(r, "Occupation") for r in non_brit if g(r, "Occupation"))

    occupancy = []
    for yr in sorted({year(r) for r in bs if year(r)}):
        sub = [r for r in bs if year(r) == yr]
        if len(sub) < 50:
            continue
        days = []
        for r in sub:
            try:
                d = float(g(r, "Days in Hospital").replace("+", ""))
            except ValueError:
                continue
            if 0 <= d < 400:
                days.append(d)
        if not days:
            continue
        occupancy.append({"year": yr, "admissions": len(sub),
                          "bedDays": round(sum(days)),
                          "meanBeds": round(sum(days) / 365, 1),
                          "pctOf24": round(100 * sum(days) / 365 / 24)})

    # Share of each group's ward-known admissions that went to the British Section.
    reach = []
    for k in MIXED_ORDER:
        sub = [r for r in rows if mixed(r) == k and g(r, "Ward")]
        if len(sub) < 30:
            continue
        b = sum(1 for r in sub if g(r, "Ward").startswith("British Section"))
        reach.append({"group": k, "n": len(sub), "pct": pct(b, len(sub))})

    return {
        "total": len(bs),
        "designedBeds": 24,
        "religion": [{"name": k, "n": v} for k, v in by_rel.most_common() if k],
        "nationality": [{"name": k, "n": v} for k, v in by_nat.most_common(8) if k],
        "nonBritish": {
            "n": len(non_brit),
            "byClass": {k: sum(1 for r in non_brit if klass(r) == k) for k in ("1", "2", "3")},
            "byReligion": {m: sum(1 for r in non_brit if g(r, "Religion") == m) for m in MCJ},
            "staff": sum(1 for r in non_brit if is_staff(r)),
            "topOccupations": [{"name": k, "n": v} for k, v in occ.most_common(8)],
        },
        "occupancy": occupancy,
        "reach": reach,
    }


def fig_mixed_groups(rows):
    """The mixed categorisation: class and mortality, with religion split by nationality.

    This is the figure that dissolves the 'Christian' category. Undifferentiated,
    Christians look like a prosperous middle class (45% second class). Split by
    nationality, the second class is 83.5% of the British and 21.6% of the
    Palestinians — the prosperity was the colonial officialdom, not the Arab
    Christian population.
    """
    out = []
    for k in MIXED_ORDER:
        sub = [r for r in rows if mixed(r) == k]
        with_class = [r for r in sub if klass(r)]
        c = Counter(klass(r) for r in with_class)
        rate, seen = cfr(sub)
        third = [r for r in sub if klass(r) == "3"]
        third_rate, third_seen = cfr(third)
        # British-national Christians barely appear in third class (49 records),
        # so their third-class rate is reported but must not be read as a rate.
        if third_seen < 100:
            third_rate = None
        out.append({
            "group": k, "n": len(sub),
            "classN": len(with_class),
            "class1": pct(c["1"], len(with_class)),
            "class2": pct(c["2"], len(with_class)),
            "class3": pct(c["3"], len(with_class)),
            "cfr": rate, "cfrN": seen,
            "cfrThirdClass": third_rate, "cfrThirdClassN": third_seen,
        })
    # The undifferentiated religions, for the comparison that makes the point.
    plain = []
    for m in MCJ:
        sub = [r for r in rows if g(r, "Religion") == m]
        with_class = [r for r in sub if klass(r)]
        c = Counter(klass(r) for r in with_class)
        rate, seen = cfr(sub)
        plain.append({"group": m, "n": len(sub), "classN": len(with_class),
                      "class1": pct(c["1"], len(with_class)),
                      "class2": pct(c["2"], len(with_class)),
                      "class3": pct(c["3"], len(with_class)),
                      "cfr": rate, "cfrN": seen})
    return {"mixed": out, "plain": plain}


def fig_withdrawal(rows):
    """Jewish share of admissions per year, and the 1948 months.

    The curve is the second headline: the shared institution was abandoned by
    one community from 1936, a decade before the war. Isolation and Infectious
    Diseases are carried alongside because notifiable-disease admission was
    compulsory — what collapsed was elective use, and those two wards show it.
    """
    series = []
    for yr in sorted({year(r) for r in rows if year(r)}):
        sub = [r for r in rows if year(r) == yr and g(r, "Religion") in MCJ]
        if len(sub) < 30:
            continue
        c = Counter(g(r, "Religion") for r in sub)
        iso = [r for r in sub if ward(r) in ("Isolation", "Infectious Diseases")]
        ic = Counter(g(r, "Religion") for r in iso)
        series.append({
            "year": yr, "n": len(sub),
            **{m: pct(c[m], len(sub)) for m in MCJ},
            "isolationN": len(iso),
            "jewishInIsolation": pct(ic["Jewish"], len(iso)) if len(iso) >= 30 else None,
        })
    months = []
    for r in rows:
        d = g(r, "Admission Date")
        if len(d) >= 7 and d[:4] in ("1947", "1948") and g(r, "Religion") in MCJ:
            months.append((d[:7], g(r, "Religion")))
    bym = defaultdict(Counter)
    for m, rel in months:
        bym[m][rel] += 1
    return {"years": series,
            "lateMonths": [{"month": m, **{k: bym[m][k] for k in MCJ},
                            "n": sum(bym[m].values())}
                           for m in sorted(bym)]}


def fig_staff(rows):
    """The hospital's own workers, as patients: who treated whom.

    243-odd admissions carry a medical occupation. Their confessional profile
    inverts the patient body's, which is the register's own evidence about the
    staff — a majority-Muslim patient population cared for by a nursing corps
    that was disproportionately Jewish and Christian. Read it against
    data/public/personnel.json, where MidEastMed's named establishment is
    overwhelmingly Arab and Armenian under British senior officers.
    """
    st = [r for r in rows if is_staff(r)]
    c = Counter(g(r, "Religion") for r in st if g(r, "Religion") in MCJ)
    allrel = [r for r in rows if g(r, "Religion") in MCJ]
    ca = Counter(g(r, "Religion") for r in allrel)
    return {
        "n": len(st),
        "female": sum(1 for r in st if g(r, "Sex") == "Female"),
        "comparison": [{"religion": m,
                        "staffPct": pct(c[m], sum(c.values())), "staffN": c[m],
                        "allPct": pct(ca[m], len(allrel))} for m in MCJ],
        "wards": [{"name": k or "Not recorded", "n": v}
                  for k, v in Counter(g(r, "Ward") for r in st).most_common(6)],
        "occupations": [{"name": k, "n": v} for k, v in
                        Counter(g(r, "Occupation") for r in st).most_common(10)],
        "inBritishSection": sum(1 for r in st if g(r, "Ward").startswith("British Section")),
    }


def fig_gaps(rows):
    """Where the record falls silent, and whether the silence is even-handed.

    It matters for every figure above that the gaps are temporal, not
    confessional: coverage collapses as the Mandate ends, in the same years for
    everyone. The one caution worth carrying is Ward, which goes missing far
    more often for Jewish patients in the late years — so the late-period ward
    shares are the weakest numbers in this view.
    """
    cols = ["Diagnosis as written", "Diagnosis as standardized", "ICD-9 Code",
            "ICD-9 Chapter", "Result", "Ward", "Class", "Age", "Procedure"]
    coverage = [{"column": c,
                 "filled": sum(1 for r in rows if g(r, c)),
                 "pct": pct(sum(1 for r in rows if g(r, c)), len(rows))}
                for c in cols]

    by_year = []
    for yr in sorted({year(r) for r in rows if year(r)}):
        sub = [r for r in rows if year(r) == yr]
        if len(sub) < 50:
            continue
        by_year.append({"year": yr, "n": len(sub),
                        "icd9Missing": pct(sum(1 for r in sub if not g(r, "ICD-9 Code")), len(sub)),
                        "wardMissing": pct(sum(1 for r in sub if not g(r, "Ward")), len(sub)),
                        "resultMissing": pct(sum(1 for r in sub if not g(r, "Result")), len(sub))})

    by_group = []
    for m in MCJ:
        sub = [r for r in rows if g(r, "Religion") == m]
        by_group.append({"group": m, "n": len(sub),
                         "icd9Missing": pct(sum(1 for r in sub if not g(r, "ICD-9 Code")), len(sub)),
                         "wardMissing": pct(sum(1 for r in sub if not g(r, "Ward")), len(sub)),
                         "resultMissing": pct(sum(1 for r in sub if not g(r, "Result")), len(sub))})

    # The ward-missing caution, year by year, for the three religions.
    ward_late = []
    for yr in ("1938", "1944", "1946", "1947", "1948"):
        row = {"year": yr}
        for m in MCJ:
            sub = [r for r in rows if year(r) == yr and g(r, "Religion") == m]
            row[m] = pct(sum(1 for r in sub if not g(r, "Ward")), len(sub)) if len(sub) >= 60 else None
        ward_late.append(row)

    # Is the ward-missing set different in kind from the ward-known set?
    known = [r for r in rows if g(r, "Ward")]
    missing = [r for r in rows if not g(r, "Ward")]
    def relmix(sub):
        s = [r for r in sub if g(r, "Religion") in MCJ]
        c = Counter(g(r, "Religion") for r in s)
        return {m: pct(c[m], len(s)) for m in MCJ}
    return {"coverage": coverage, "byYear": by_year, "byGroup": by_group,
            "wardMissingLate": ward_late,
            "wardBias": {
                "known": {"n": len(known), "cfr": cfr(known)[0], **relmix(known)},
                "missing": {"n": len(missing), "cfr": cfr(missing)[0], **relmix(missing)},
            }}


def fig_payment(rows):
    """Who was treated free, and who was charged.

    The Payment Status column is not a "recorded / not recorded" field, and
    reading it as one inverts the finding. It is a **gratis marker**: the clerk
    wrote Gratis when treatment was free and left it EMPTY when a fee was
    charged, entering the fee in the Rate column instead. Three things establish
    this and none of them is subtle. Rate is filled for 56.0% of the blank rows
    and 0.6% of the "Gratis" ones — the two columns are near-complementary. The
    blank tracks class the way a fee would: 99.0% of first class, 55.4% of
    second, 19.6% of third. And it is not a clerical era or a skipped page —
    88.6% of pages mix blank and filled rows, only 1.9% are wholly blank.

    So a blank here is evidence of payment, not of silence, and "gratis rate"
    below means marked-gratis over all admissions of that group. The residue
    matters and is reported: 13.2% of admissions are blank with no rate either,
    and those are the genuinely unknown ones.
    """
    def marked_gratis(row):
        return bool(g(row, "Payment Status"))

    def rate_mils(row):
        t = g(row, "Rate").replace("Mils", "").replace("mils", "").strip()
        try:
            return float(t)
        except ValueError:
            return None

    # The evidence for reading the blank as a charge, carried into the view so
    # the claim travels with the figure rather than living only in this comment.
    blank = [r for r in rows if not marked_gratis(r)]
    filled = [r for r in rows if marked_gratis(r)]
    pages = defaultdict(list)
    for r in rows:
        pages[(g(r, "Notebook_Number"), g(r, "Page_Number"))].append(r)
    full = [p for p in pages.values() if len(p) >= 8]
    all_blank = sum(1 for p in full if all(not marked_gratis(r) for r in p))
    none_blank = sum(1 for p in full if all(marked_gratis(r) for r in p))

    evidence = {
        "blankWithRatePct": pct(sum(1 for r in blank if g(r, "Rate")), len(blank)),
        "gratisWithRatePct": pct(sum(1 for r in filled if g(r, "Rate")), len(filled)),
        "blankByClass": {k: pct(sum(1 for r in rows if klass(r) == k and not marked_gratis(r)),
                                sum(1 for r in rows if klass(r) == k))
                         for k in ("1", "2", "3")},
        "pages": {"n": len(full),
                  "allBlankPct": pct(all_blank, len(full)),
                  "noneBlankPct": pct(none_blank, len(full)),
                  "mixedPct": pct(len(full) - all_blank - none_blank, len(full))},
        "split": {
            "gratis": len(filled),
            "chargedWithRate": sum(1 for r in blank if g(r, "Rate")),
            "unknown": sum(1 for r in blank if not g(r, "Rate")),
        },
    }

    by_group = []
    for m in MCJ:
        sub = [r for r in rows if g(r, "Religion") == m]
        third = [r for r in sub if klass(r) == "3"]
        rates = [x for x in (rate_mils(r) for r in sub if not marked_gratis(r)) if x]
        by_group.append({
            "group": m, "n": len(sub),
            "gratisPct": pct(sum(1 for r in sub if marked_gratis(r)), len(sub)),
            "gratisThirdClassPct": pct(sum(1 for r in third if marked_gratis(r)), len(third)),
            "thirdClassN": len(third),
            "medianRate": statistics.median(rates) if rates else None,
            "rateN": len(rates),
        })

    by_class = []
    for k in ("1", "2", "3"):
        row = {"class": k}
        for m in MCJ:
            sub = [r for r in rows if g(r, "Religion") == m and klass(r) == k]
            row[m] = pct(sum(1 for r in sub if marked_gratis(r)), len(sub)) if len(sub) >= 25 else None
        by_class.append(row)

    by_mixed = []
    for k in MIXED_ORDER:
        sub = [r for r in rows if mixed(r) == k]
        if len(sub) < 50:
            continue
        third = [r for r in sub if klass(r) == "3"]
        by_mixed.append({
            "group": k, "n": len(sub),
            "gratisPct": pct(sum(1 for r in sub if marked_gratis(r)), len(sub)),
            "gratisThirdClassPct": pct(sum(1 for r in third if marked_gratis(r)), len(third)),
            "thirdClassN": len(third),
        })

    return {"evidence": evidence, "byGroup": by_group,
            "byClass": by_class, "byMixed": by_mixed}


def build(rows):
    return {
        "meta": {
            "records": len(rows),
            "note": ("Notebook 25 (the Atlit camp register, 965 rows) excluded throughout. "
                     "Religion shares use an M+C+J denominator; blanks leave both "
                     "numerator and denominator."),
        },
        "wardMix": fig_ward_mix(rows),
        "mixing": fig_page_mixing(rows),
        "britishSection": fig_british_section(rows),
        "mixedGroups": fig_mixed_groups(rows),
        "withdrawal": fig_withdrawal(rows),
        "staff": fig_staff(rows),
        "gaps": fig_gaps(rows),
        "payment": fig_payment(rows),
    }


def report(data):
    m = data["wardMix"]
    print(f"=== WARD COMPOSITION (n={data['meta']['records']:,}) ===")
    for w in m["wards"] + [m["baseline"]]:
        print(f"  {w['ward']:22s} n={w['n']:6d}  " +
              "  ".join(f"{k[0]} {w[k]:5.1f}%" for k in MCJ))
    mx = data["mixing"]
    print(f"\n=== LEDGER PAGES (>=8 entries): {mx['pages']['n']} ===")
    print(f"  all three religions {mx['pages']['allThree']} ({mx['pages']['allThreePct']}%)"
          f"   single-religion {mx['pages']['single']} ({mx['pages']['singlePct']}%)")
    print("\n=== ADJACENCY (same-religion neighbour, same ward) ===")
    for a in mx["adjacency"]:
        print(f"  {a['ward']:22s} observed {a['observed']:5.1f}%  chance {a['chance']:5.1f}%  excess {a['excess']:+5.1f}")
    b = data["britishSection"]
    print(f"\n=== BRITISH SECTION: {b['total']} admissions, {b['designedBeds']} designed beds ===")
    print(f"  religion: {b['religion']}")
    print(f"  non-British nationals: {b['nonBritish']['n']}, of whom staff-titled {b['nonBritish']['staff']}")
    print(f"  by class: {b['nonBritish']['byClass']}")
    for o in b["occupancy"]:
        print(f"  {o['year']}  {o['admissions']:4d} adm  {o['meanBeds']:5.1f} beds mean  {o['pctOf24']:3d}% of 24")
    print("\n=== MIXED GROUPS ===")
    for r in data["mixedGroups"]["mixed"]:
        print(f"  {r['group']:32s} n={r['n']:6d}  cls1 {r['class1']:5.1f}% cls2 {r['class2']:5.1f}% "
              f"cls3 {r['class3']:5.1f}%  CFR {r['cfr']:5.2f}%  CFR(3rd) {r['cfrThirdClass']}")
    print("\n  undifferentiated, for comparison:")
    for r in data["mixedGroups"]["plain"]:
        print(f"  {r['group']:32s} n={r['n']:6d}  cls1 {r['class1']:5.1f}% cls2 {r['class2']:5.1f}% "
              f"cls3 {r['class3']:5.1f}%  CFR {r['cfr']:5.2f}%")
    s = data["staff"]
    print(f"\n=== STAFF AS PATIENTS: {s['n']} ({s['female']} female), {s['inBritishSection']} in the British Section ===")
    for c in s["comparison"]:
        print(f"  {c['religion']:10s} staff {c['staffPct']:5.1f}% (n={c['staffN']:3d})   all patients {c['allPct']:5.1f}%")
    print("\n=== JEWISH WITHDRAWAL ===")
    for y in data["withdrawal"]["years"]:
        iso = f"  isolation J {y['jewishInIsolation']}%" if y["jewishInIsolation"] else ""
        print(f"  {y['year']} n={y['n']:5d}  M {y['Muslim']:5.1f}%  C {y['Christian']:5.1f}%  J {y['Jewish']:5.1f}%{iso}")
    p = data["payment"]
    ev = p["evidence"]
    print("\n=== PAYMENT: the blank is a charge, not a silence ===")
    print(f"  Rate filled for {ev['blankWithRatePct']}% of blank rows vs {ev['gratisWithRatePct']}% of Gratis rows")
    print(f"  blank by class: {ev['blankByClass']}")
    print(f"  pages mixing blank and filled: {ev['pages']['mixedPct']}% (wholly blank {ev['pages']['allBlankPct']}%)")
    print(f"  split: {ev['split']}")
    print("\n  gratis share by group (blank counted as charged):")
    for r in p["byGroup"]:
        print(f"    {r['group']:10s} {r['gratisPct']:5.1f}%   3rd class {r['gratisThirdClassPct']:5.1f}%"
              f"   median fee {r['medianRate']} mils (n={r['rateN']})")
    print("\n  within class:")
    for r in p["byClass"]:
        print(f"    class {r['class']}: " + "  ".join(
            f"{m[0]} {r[m]}%" for m in MCJ if r[m] is not None))
    gp = data["gaps"]
    print("\n=== COVERAGE ===")
    for c in gp["coverage"]:
        print(f"  {c['column']:30s} {c['pct']:5.1f}%")
    print("\n=== WARD MISSING, late years, by religion (the caution) ===")
    for r in gp["wardMissingLate"]:
        print(f"  {r['year']}  " + "  ".join(f"{m[0]} {r[m]}%" for m in MCJ if r[m] is not None))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--report", action="store_true", help="print tables instead of writing JSON")
    args = ap.parse_args()

    data = build(load())
    if args.report:
        report(data)
    else:
        OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {OUT.relative_to(ROOT)}  ({data['meta']['records']:,} records)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
