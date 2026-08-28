"""Link the ISA 1942-44 named infectious cases to the admission register.

Stage 2 of the job begun in pipeline/isa_returns.py. Reads

  data/private/isa-1942-44-cases.tsv          named cases from ISA 000zbri
  data/public/hospital-registers-normalized.tsv   the admission register

and writes

  data/private/isa-1942-44-candidates.tsv     one row per candidate pairing
  data/private/isa-1942-44-linkage-summary.txt  the counts, for the write-up

WHAT THIS CAN AND CANNOT DO. The register's patient names are redacted at the
image, so a name-to-name match is impossible and nothing here is an
identification. What is left is date + age + sex + religion + disease, which
in a town where a dozen people a week were notified with typhoid is not
discriminating enough to name anyone. So the output is CANDIDATES, and the
honest unit of analysis is the aggregate: how many notified cases could have
been in the hospital at all.

THE WINDOW IS NARROWER THAN THE FILE. The ISA returns run Jan 1942 - Oct 1944.
The digitised register does NOT: it jumps 1940 -> 1944 -> 1946, with no 1942 or
1943 admissions at all, and 1944 itself runs only Feb/Mar - Nov (notebooks 27,
28, 29). So only the 1944 part of the returns is linkable, and cases outside
that window are reported separately as OUT OF REGISTER WINDOW - they are not
evidence of anything, least of all of a patient not being admitted.

THE MATCHING RULE, stated so it can be argued with:
  * SEX must agree exactly.
  * AGE must agree within +/- 2 years (the returns and the register were
    written by different clerks from different informants).
  * RELIGION must agree, after mapping the returns' combined
    "nationality and religion" cell onto the register's Muslim / Christian /
    Jewish. A blank on either side does not match.
  * DISEASE must agree at the level of the disease family (typhoid,
    paratyphoid, plague, typhus, smallpox, dysentery, ...), compared through
    a synonym table rather than by string equality.
  * DATE: the register's Admission Date must fall within a window around the
    return's date of onset - by default onset-0 to onset+30 days, because a
    notified case was admitted after onset, not before, and the tail is long
    for typhoid. Where the return gives its own admission date
    (`admitted_to_h`, on the 1942-43 form) that is used instead, with a
    tolerance of +/- 3 days.

A case that satisfies all five is a candidate. A case with exactly one
candidate is reported as UNIQUE; with more than one, AMBIGUOUS; with none,
NO MATCH. UNIQUE does not mean identified - it means the register holds
exactly one admission that could be this person.

UNIQUENESS IS TWO-SIDED. Counting only "this case has one candidate row" is not
enough: two different named people cannot be the same admission, and on a first
pass seven register rows were each claimed by two or three different cases that
all called themselves UNIQUE. So after matching, any register row claimed by
more than one case demotes every claimant to CONTESTED. What survives as UNIQUE
is a one-to-one pairing in both directions.

Run:
  python3 pipeline/isa_returns_link.py
  python3 pipeline/isa_returns_link.py --onset-window 45
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(ROOT, "data", "private", "isa-1942-44-cases.tsv")
PAGES = os.path.join(ROOT, "data", "private", "isa-1942-44-pages.tsv")
REG = os.path.join(ROOT, "data", "public", "hospital-registers-normalized.tsv")
OUT = os.path.join(ROOT, "data", "private", "isa-1942-44-candidates.tsv")
SUMMARY = os.path.join(ROOT, "data", "private", "isa-1942-44-linkage-summary.txt")

# The register's own coverage. Anything outside this cannot be matched, and
# saying so is different from saying the patient was not admitted.
REG_MIN = dt.date(1944, 1, 1)
REG_MAX = dt.date(1944, 12, 31)

# Where the returns say a case was treated. The register can only ever see the
# first group; the second is the part of the epidemic it is blind to.
IN_HOSPITAL = re.compile(
    r"govt|gov\.?t|government|isol|hosp|g\.?h\.?\b", re.I)
AT_HOME = re.compile(r"\bhome\b|\bhouse\b|at home|residence", re.I)

DISEASE_FAMILIES = {
    "typhoid": ["typhoid", "enteric", "widal"],
    "paratyphoid": ["paratyphoid", "para typhoid", "para-typhoid"],
    "plague": ["plague", "pestis", "bubonic"],
    "typhus": ["typhus"],
    "smallpox": ["small pox", "smallpox", "variola"],
    "chickenpox": ["chicken pox", "chickenpox", "varicella"],
    "dysentery": ["dysent", "histolytica", "shiga", "flexner"],
    "measles": ["measles", "morbilli"],
    "scarlet fever": ["scarlet", "scarlatina"],
    "diphtheria": ["diphth"],
    "meningitis": ["meningitis", "c.s.m", "csm", "cerebro-spinal",
                   "cerebrospinal", "cerebro spinal"],
    "anthrax": ["anthrax"],
    "poliomyelitis": ["polio"],
    "whooping cough": ["whooping", "pertussis"],
    "undulant fever": ["undulant", "brucell", "malta fever"],
    "erysipelas": ["erysip"],
    "tetanus": ["tetanus"],
    "puerperal fever": ["puerperal"],
    "relapsing fever": ["relapsing"],
    "malaria": ["malaria"],
}


def family(text: str) -> str:
    t = (text or "").lower()
    for fam, keys in DISEASE_FAMILIES.items():
        if any(k in t for k in keys):
            return fam
    return ""


def religion(text: str) -> str:
    """Map either source's religion wording onto Muslim/Christian/Jewish.

    The returns write this as one cell combining nationality and religion, and
    they abbreviate hard: "Palest. Mosl.", "Palest Ch.", "Germ. Jew",
    "Pales.M.", "British C of E". An earlier version of this function matched
    only the spelled-out words and silently dropped 237 of 290 linkable cases -
    four fifths of the work - so the abbreviations are handled explicitly and
    the unmatched residue is reported rather than assumed empty.

    Two deliberate refusals:
      * "Arab" alone is a nationality, not a religion. Most Palestinian Arabs
        in these returns were Moslem, but some were Christian and the register
        records the difference, so guessing here would manufacture matches.
      * Druze and Mitwali are neither Muslim, Christian nor Jewish as the
        register uses those words. They get their own values and simply do not
        match, which is correct.
    """
    t = (text or "").strip().lower()
    if not t:
        return ""
    if re.search(r"\bdruz", t):
        return "Druze"
    if re.search(r"\bmitwali|\bmutawali|\bmetwali", t):
        return "Mitwali"
    # Moslem: moslem, muslim, mosl, mos., and a bare M as the last token
    if re.search(r"mosl|musl|\bmos\b|\bmos\.|\bm\.?$", t):
        return "Muslim"
    # Christian: christian, chr, ch., c of e, orthodox, latin, maronite
    # "Xian"/"Xtn" is the period's own shorthand for Christian.
    if re.search(r"christ|\bxian\b|\bxtn\b|\bchr\b|\bchr\.|\bch\b|\bch\.|"
                 r"c\s*of\s*e|orth|latin|maron|catholic|protest|\bc\.?$", t):
        return "Christian"
    if re.search(r"\bjew", t):
        return "Jewish"
    if re.search(r"\barab\b", t):
        return "Arab (religion not stated)"
    return ""


def age_years(value: str, unit: str = "") -> float | None:
    """Parse an age from either source. '45y' -> 45, '10m' -> 0.83."""
    t = (value or "").strip().lower()
    if not t:
        return None
    m = re.match(r"(\d+(?:\.\d+)?)\s*([a-z]*)", t)
    if not m:
        return None
    n = float(m.group(1))
    suffix = (m.group(2) or unit or "").lower()
    if suffix.startswith("m"):          # months
        return n / 12.0
    if suffix.startswith("d"):          # days
        return n / 365.0
    if suffix.startswith("w"):          # weeks
        return n / 52.0
    return n


def sex(text: str) -> str:
    t = (text or "").strip().lower().rstrip(".")
    if t.startswith("m"):
        return "M"
    if t.startswith("f"):
        return "F"
    return ""


def parse_return_date(text: str, default_year: int | None = None):
    """Parse the returns' dates: 9.8.44, 6.8.44., 1.VIII.44, 11/2, 30/1/42."""
    t = (text or "").strip().rstrip(".").replace(" ", "")
    if not t or t in {"-", "—", "–"}:
        return None
    roman = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7,
             "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12}
    parts = re.split(r"[./\-]", t)
    parts = [p for p in parts if p]
    if len(parts) < 2:
        return None
    try:
        day = int(parts[0])
    except ValueError:
        return None
    mon_raw = parts[1].lower()
    if mon_raw in roman:
        mon = roman[mon_raw]
    else:
        try:
            mon = int(mon_raw)
        except ValueError:
            return None
    if len(parts) >= 3:
        try:
            y = int(parts[2])
        except ValueError:
            return None
        year = 1900 + y if y < 100 else y
    elif default_year:
        year = default_year
    else:
        return None
    try:
        return dt.date(year, mon, day)
    except ValueError:
        return None


def parse_iso(text: str):
    t = (text or "").strip()
    if len(t) < 10:
        return None
    try:
        return dt.date(int(t[0:4]), int(t[5:7]), int(t[8:10]))
    except ValueError:
        return None



def page_years(pages_path: str) -> dict[int, int]:
    """Infer the year of every page from the dated daily-return rectos.

    The clerks usually wrote the onset as day-and-month only - "20/3", "15.6" -
    because the year was obvious from the return the sheet was attached to. Read
    literally that loses 990 of 2,171 named cases, so the year is recovered from
    the file itself.

    The DAILY RETURN rectos do carry a full date, and the file is in date order
    (running BACKWARDS: late 1944 at the front, 1942 at the back). So each dated
    recto is an anchor, and any page between two anchors that agree on a year
    takes that year. Where the neighbouring anchors disagree - the handful of
    pages that straddle a January - no year is assumed and the case keeps its
    NO DATE status rather than being placed in the wrong year.

    162 of the 388 pages carry a usable anchor, and they are monotonic to within
    4 inversions out of 161, so the interpolation is well constrained.
    """
    anchors: dict[int, dt.date] = {}
    if not os.path.exists(pages_path):
        return {}
    for r in csv.DictReader(open(pages_path, encoding="utf-8"), delimiter="\t"):
        d = parse_return_date(r.get("return_date") or "")
        if d and dt.date(1941, 12, 1) <= d <= dt.date(1944, 12, 31):
            try:
                anchors[int(r["page"])] = d
            except (ValueError, KeyError):
                pass
    if not anchors:
        return {}
    keys = sorted(anchors)
    out: dict[int, int] = {}
    for pg in range(1, max(keys) + 1):
        before = [k for k in keys if k <= pg]
        after = [k for k in keys if k >= pg]
        yb = anchors[before[-1]].year if before else None
        ya = anchors[after[0]].year if after else None
        if yb is not None and ya is not None:
            # Only commit where the two nearest anchors agree.
            if yb == ya:
                out[pg] = yb
        elif yb is not None:
            out[pg] = yb
        elif ya is not None:
            out[pg] = ya
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--onset-window", type=int, default=30,
                    help="days after onset within which an admission may fall")
    ap.add_argument("--age-tol", type=float, default=2.0)
    ap.add_argument("--admit-tol", type=int, default=3,
                    help="tolerance when the return gives its own admission date")
    args = ap.parse_args()

    if not os.path.exists(CASES):
        print(f"no {CASES} - run pipeline/isa_returns.py first", file=sys.stderr)
        return 2

    cases = list(csv.DictReader(open(CASES, encoding="utf-8"), delimiter="\t"))
    years = page_years(PAGES)
    reg = [r for r in csv.DictReader(open(REG, encoding="utf-8"), delimiter="\t")
           if (r.get("Admission Date") or "").startswith("1944")]

    # Index the register by (sex, religion, disease family) so each case only
    # compares against plausible rows.
    index = defaultdict(list)
    for r in reg:
        d = parse_iso(r.get("Admission Date"))
        if not d:
            continue
        fam = family(r.get("Diagnosis as standardized") or "") or \
            family(r.get("Diagnosis as written") or "")
        if not fam:
            continue
        rec = {
            "row": r,
            "date": d,
            "age": age_years(r.get("Age") or "", r.get("Age Unit") or ""),
            "sex": sex(r.get("Sex") or ""),
            "rel": religion(r.get("Religion") or ""),
            "fam": fam,
        }
        index[(rec["sex"], rec["rel"], fam)].append(rec)

    out_fields = ["case_page", "case_name", "case_disease", "case_where_treated",
                  "case_age", "case_sex", "case_religion", "case_onset",
                  "case_admitted", "status", "n_candidates",
                  "reg_index", "reg_admission_date", "reg_age", "reg_sex",
                  "reg_religion", "reg_diagnosis", "reg_ward", "reg_result",
                  "reg_notebook", "reg_page", "date_gap_days"]
    fout = open(OUT, "w", newline="", encoding="utf-8")
    w = csv.DictWriter(fout, fieldnames=out_fields, delimiter="\t",
                       extrasaction="ignore")
    w.writeheader()

    stats = Counter()
    emitted: list[dict] = []
    treated = Counter()
    fam_counts = Counter()
    fam_status = defaultdict(Counter)
    case_fam: dict[int, str] = {}

    for c in cases:
        if not (c.get("name") or "").strip():
            continue
        stats["named cases"] += 1

        where = (c.get("where_treated") or "").strip()
        in_hosp = bool(IN_HOSPITAL.search(where))
        at_home = bool(AT_HOME.search(where))
        if in_hosp:
            treated["hospital or isolation"] += 1
        elif at_home:
            treated["at home"] += 1
        elif where:
            treated[f"other: {where.lower()}"] += 1
        else:
            treated["not recorded"] += 1

        fam = family(c.get("disease") or "")
        fam_counts[fam or "(unrecognised)"] += 1

        try:
            default_year = years.get(int(c.get("page") or 0))
        except ValueError:
            default_year = None
        onset = parse_return_date(c.get("date_onset") or "", default_year)
        admitted = parse_return_date(c.get("admitted_to_h") or "", default_year)
        anchor = admitted or onset

        base = {
            "case_page": c.get("page", ""),
            "case_name": c.get("name", ""),
            "case_disease": c.get("disease", ""),
            "case_where_treated": where,
            "case_age": c.get("age", ""),
            "case_sex": c.get("sex", ""),
            "case_religion": c.get("nationality_religion", ""),
            "case_onset": c.get("date_onset", ""),
            "case_admitted": c.get("admitted_to_h", ""),
        }

        # Rule out the unlinkable BEFORE asking whether a match exists, so a
        # 1942 case is never reported as "not admitted".
        if not anchor:
            base.update(status="NO DATE", n_candidates=0)
            w.writerow(base)
            stats["no usable date"] += 1
            continue
        if not (REG_MIN <= anchor <= REG_MAX):
            base.update(status="OUT OF REGISTER WINDOW", n_candidates=0)
            w.writerow(base)
            stats["outside the register's years"] += 1
            continue
        if not in_hosp:
            base.update(status="NOT SENT TO HOSPITAL", n_candidates=0)
            w.writerow(base)
            stats["in window, treated outside hospital"] += 1
            continue

        stats["in window, marked hospital/isolation"] += 1

        s = sex(c.get("sex") or "")
        rel = religion(c.get("nationality_religion") or "")
        age = age_years(c.get("age") or "")

        cands = []
        if s and rel and fam and age is not None:
            for rec in index.get((s, rel, fam), []):
                if rec["age"] is None:
                    continue
                if abs(rec["age"] - age) > args.age_tol:
                    continue
                gap = (rec["date"] - anchor).days
                if admitted:
                    if abs(gap) > args.admit_tol:
                        continue
                else:
                    if gap < 0 or gap > args.onset_window:
                        continue
                cands.append((rec, gap))

        cands.sort(key=lambda x: abs(x[1]))
        if not cands:
            status = "NO MATCH"
        elif len(cands) == 1:
            status = "UNIQUE"
        else:
            status = "AMBIGUOUS"
        stats[status] += 1
        case_fam[len(emitted)] = fam or "(unrecognised)"
        fam_status[fam or "(unrecognised)"][status] += 1

        if not cands:
            base.update(status=status, n_candidates=0)
            emitted.append(base)
        else:
            for rec, gap in cands:
                r = rec["row"]
                row = dict(base)
                row.update(
                    status=status, n_candidates=len(cands),
                    reg_index=r.get("Index", ""),
                    reg_admission_date=r.get("Admission Date", ""),
                    reg_age=r.get("Age", ""), reg_sex=r.get("Sex", ""),
                    reg_religion=r.get("Religion", ""),
                    reg_diagnosis=r.get("Diagnosis as standardized")
                    or r.get("Diagnosis as written", ""),
                    reg_ward=r.get("Ward", ""), reg_result=r.get("Result", ""),
                    reg_notebook=r.get("Notebook_Number", ""),
                    reg_page=r.get("Page_Number", ""),
                    date_gap_days=gap)
                emitted.append(row)

    # Second pass: uniqueness has to hold in BOTH directions. A register row
    # claimed by more than one named case cannot be a one-to-one pairing, so
    # every claimant is demoted from UNIQUE to CONTESTED.
    claims = Counter(r["reg_index"] for r in emitted
                     if r.get("status") == "UNIQUE" and r.get("reg_index"))
    contested = {k for k, v in claims.items() if v > 1}
    for r in emitted:
        if r.get("status") == "UNIQUE" and r.get("reg_index") in contested:
            r["status"] = "CONTESTED"
    stats["UNIQUE"] -= sum(claims[k] for k in contested)
    stats["CONTESTED"] = sum(claims[k] for k in contested)
    seen_contested: set[str] = set()
    for r in emitted:
        if r.get("status") == "CONTESTED":
            key = r["case_page"] + "|" + r["case_name"]
            if key in seen_contested:
                continue
            seen_contested.add(key)
            f = family(r.get("case_disease") or "") or "(unrecognised)"
            fam_status[f]["UNIQUE"] -= 1
            fam_status[f]["CONTESTED"] += 1
    for r in emitted:
        w.writerow(r)
    fout.close()

    lines = []
    def say(s=""):
        lines.append(s)
        print(s)

    say("ISA 000zbri 1942-44 named infectious cases -> Haifa register linkage")
    say("=" * 68)
    say()
    say(f"matching rule: sex exact; age +/-{args.age_tol:g}y; religion exact "
        f"after mapping; disease family via synonym table;")
    say(f"date: admission within onset..onset+{args.onset_window}d, or "
        f"+/-{args.admit_tol}d of the return's own admission date.")
    say(f"year recovered for {len(years)} pages from the dated daily-return "
        f"rectos (the clerks wrote day-and-month only)")
    say(f"register window used: {REG_MIN} .. {REG_MAX} "
        f"({len(reg)} admissions, {sum(len(v) for v in index.values())} of them "
        f"with a recognised infectious diagnosis)")
    say()
    say("CASES")
    for k in ["named cases", "no usable date", "outside the register's years",
              "in window, treated outside hospital",
              "in window, marked hospital/isolation"]:
        say(f"  {stats[k]:5d}  {k}")
    say()
    say("WHERE TREATED, all named cases as written")
    for k, v in treated.most_common():
        say(f"  {v:5d}  {k}")
    say()
    say("OUTCOME for cases in window and marked hospital/isolation")
    for k in ["UNIQUE", "CONTESTED", "AMBIGUOUS", "NO MATCH"]:
        say(f"  {stats[k]:5d}  {k}")
    say("    UNIQUE    = one register admission could be this person, and no")
    say("                other named case claims that same admission.")
    say("    CONTESTED = one candidate each, but two or more named cases claim")
    say("                the same admission, so at most one of them is right.")
    say("    AMBIGUOUS = several register admissions fit this person.")
    say()
    say("DISEASE FAMILIES, all named cases")
    for k, v in fam_counts.most_common():
        st = fam_status.get(k)
        detail = ""
        if st:
            detail = "   (" + ", ".join(f"{a}={b}" for a, b in st.most_common()) + ")"
        say(f"  {v:5d}  {k}{detail}")
    say()
    say(f"wrote {OUT}")

    with open(SUMMARY, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
