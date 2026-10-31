#!/usr/bin/env python3
"""Figures for the buildings and wards dossier (paper/buildings-dossier.html).

The dossier is the evidence file behind the History tab's account of where the
hospital stood and how it was laid out. Its prose is written by hand; every
register figure in it is computed here and injected, so a change to the build
reaches the dossier by rerunning this script rather than by retyping numbers.

    python3 pipeline/buildings_figures.py            # tables to stdout + data/public/buildings-figures.json
    python3 pipeline/buildings_figures.py --inject   # also rewrite the marked regions of the dossier

--inject replaces everything between `<!-- fig:NAME -->` and `<!-- /fig:NAME -->`
in paper/buildings-dossier.html, and the `src-data` script block, and leaves
the rest of the file alone. Running it twice gives the same file.

Method decisions, fixed here so the next rerun matches the prose:

1. QUOTE_NONE, and notebook 25 (the Atlit camp register) excluded throughout,
   as in pipeline/history_figures.py.

2. The daily in-patient census is a MIDNIGHT census: a patient counts on every
   night from the admission date up to, not including, the discharge date. That
   is the rule that reproduces the figures already quoted in
   paper/historical-leads-2026-10.md (Aug-Oct 1944 means 189 / 184 / 194, peak
   238 on 3 June 1946). Records without a discharge date, or with a stay that
   is negative or over 400 days, are left out, so the census is a FLOOR.

3. The census is only shown where the register can support it. Admission
   dates are split into runs wherever ten or more days pass with no admission
   (a lost notebook, not a quiet week). A day counts only inside a run and at
   least 21 days after the run begins (three median stays), so that patients admitted in a missing
   notebook are not silently missing from the count. A month is drawn when at
   least 20 of its days count.

4. Scan reads are only compared against, never merged. The notebook 24
   pavilion letters and the "no bed" disposals reached the build in commit
   763fc05; the whole-notebook scan read (paper/rereads-2026-10-22/out_F*.tsv)
   and the 1944 Remarks read (remarks-1944/) are kept here as a check on how
   much of each the build now carries. Both live in the gitignored paper/
   folder; without it the check is skipped.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import html
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import institutions_figures as institutions

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "data/public/hospital-registers-normalized.tsv"
SOURCE = ROOT / "data/public/hospital-registers-2025-08-10.tsv"
REREADS = ROOT / "paper/rereads-2026-10-22"
DOSSIER = ROOT / "paper/buildings-dossier.html"
JSON_OUT = ROOT / "data/public/buildings-figures.json"
REGISTRY = ROOT / "data/public/sources-registry.json"
ARCHIVAL = ROOT / "sources/archival-sources.json"
HISTORY = ROOT / "paper/hospital-history.html"

ATLIT = "25"
MOVE = dt.date(1938, 10, 31)        # the NB20 -> NB21 seam
YEARS = list(range(1930, 1949))
BURN_IN = 21                         # days into a run of notebooks before the census counts
MISSING_YEARS = {1941, 1942, 1943, 1945}
csv.field_size_limit(sys.maxsize)


# --------------------------------------------------------------------------- data

def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE))


def load() -> list[dict]:
    # Neither the Atlit camp register nor the ledger's refused, duplicate and
    # cancelled entries (not-an-admission) count as admissions here.
    return [r for r in read_tsv(REGISTER) if (r["Notebook_Number"] or "").strip() != ATLIT
            and "not-an-admission" not in (r.get("Review Flags") or "")]


def day(s: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat((s or "").strip()[:10])
    except ValueError:
        return None


def is_male(r: dict) -> bool:
    return (r.get("Sex") or "").strip().lower().startswith("m")


def is_child(age: str, unit: str = "") -> bool | None:
    """Under 13, the cut the October write-up used. None when unreadable."""
    text = f"{age} {unit}".lower()
    if re.search(r"\b(mo|mos|mth|mths|month|months|day|days|wk|wks|week|weeks)\b", text):
        return True
    m = re.search(r"\d+(?:\.\d+)?", age or "")
    if not m:
        return None
    return float(m.group()) < 13


# Diagnosis families, for describing what a pavilion held. Deliberately crude:
# the same regexes run over the clerk's words in the data and in the scan read,
# so the two periods are described alike. Order matters (first match wins).
FAMILIES = [
    ("plague", r"plague|\bpest\b|\bbubo"),
    ("lymphadenitis", r"adenitis|lymphaden|glands?\b"),
    ("typhoid", r"typhoid|enteric|paratyph"),
    ("typhus", r"typhus"),
    ("relapsing fever", r"relapsing"),
    ("malaria", r"malaria|\bm\.?\s?t\.?\b|\bb\.?\s?t\.?\b|tertian|quartan"),
    ("tuberculosis", r"tuberc|\bt\.?\s?b\.?\s?c?\b|phthisis|koch"),
    ("diphtheria", r"diphth"),
    ("measles", r"measles|morbill"),
    ("rubella", r"rubella|german measles"),
    ("scarlet fever", r"scarlet"),
    ("chickenpox", r"chicken|varicella"),
    ("smallpox", r"smallpox|small pox|variola"),
    ("pneumonia", r"pneumon|labor pneu"),
    ("dysentery", r"dysent|shigell"),
    ("meningitis", r"mening"),
    ("erysipelas", r"erysip"),
    ("puerperal fever", r"puerper"),
    ("tonsillitis", r"tonsil"),
    ("sandfly fever", r"sand ?fly|phlebot|papatac"),
    ("pyrexia", r"pyrexia|\bp\.?u\.?o|fever"),
    ("gunshot / wounds", r"gun|shot|bullet|bomb|shrapnel|wound|\bw\.\s?s\b|fract|punc"),
    ("pleurisy", r"pleur"),
]
FAMILY_RE = [(name, re.compile(pat, re.I)) for name, pat in FAMILIES]


def family(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    for name, rx in FAMILY_RE:
        if rx.search(t):
            return name
    return "other"


def top(counter: Counter, n: int = 3, skip=("", "other")) -> list[tuple[str, int]]:
    return [(k, v) for k, v in counter.most_common() if k not in skip][:n]


# ------------------------------------------------------------------ ward families

def written_part(w: str) -> str:
    """The clerk's form from the extraction's 'raw|expanded' cells."""
    parts = [p.strip() for p in (w or "").split("|")]
    for p in parts:
        if p and p != "-":
            return p
    return ""


def written_family(w: str, when: dt.date | None) -> str:
    s = written_part(w)
    l = s.lower()
    if not l:
        return "(blank)"
    if "hut" in l:
        return "Hut"
    if "laz" in l:
        return "Q. Laz. / Laz."
    if re.search(r"p\.?\s?m\.?\s?f", l):
        return "P.M.F."
    if re.search(r"^(g|c|s)\.?m\.?(w|f|h|p)\.?$", l):
        return "G.M.W. / G.M.F."
    if re.search(r"p\.?\s?/?w\b|prison", l):
        return "P.W."
    if re.search(r"^(s|g)/s", l):
        return "S/S · G/S"
    if re.search(r"^(isol?|isl|is)\.?\s*\"?[a-f]\b", l):
        return "Is. / Isol. + letter"
    if re.fullmatch(r'"?[a-f]"?\.?', l):
        if l.strip('".') == "g":
            return "G"
        if l.strip('".') == "b" and when and when < MOVE:
            return "B. (before the move)"
        return "Bare letter A–E"
    if re.search(r"^br\b|^br\.|b/s|british", l):
        return "Br. · B/S · British Section"
    if "infect" in l or re.fullmatch(r"i\.d\.?s?\.?", l):
        return "Infectious …"
    if re.search(r"^is\b|^is\.|^isol|^i\.s\.?$|^i\.$", l):
        return "Is. · Isol. · Isolation"
    if l.startswith("gen"):
        return "Gen. · General"
    if l.startswith("med"):
        return "Med. · Medical"
    if l.startswith("surg"):
        return "Surg. · Surgical"
    if l.startswith("mat"):
        return "Mat. · Maternity"
    if "child" in l:
        return "Children's"
    return "other"


WRITTEN_ORDER = [
    "Gen. · General", "Med. · Medical", "Surg. · Surgical", "Mat. · Maternity",
    "Children's", "Br. · B/S · British Section", "B. (before the move)",
    "Is. · Isol. · Isolation", "Infectious …", "Is. / Isol. + letter",
    "Bare letter A–E", "G", "Hut", "Q. Laz. / Laz.", "P.W.", "P.M.F.",
    "G.M.W. / G.M.F.", "S/S · G/S", "other", "(blank)",
]


def heat_row(r: dict) -> str:
    """One row of the ward heatmap per admission, as standardized, with the
    clerk's special marks pulled out where the build folds them elsewhere."""
    when = day(r["Admission Date"])
    fam = written_family(r["Ward as written"], when)
    if fam in ("Hut", "Q. Laz. / Laz.", "P.M.F.", "G.M.W. / G.M.F."):
        return fam
    std = (r["Ward"] or "").strip()
    if fam == "P.W." or std == "Prison Ward":
        return "Prisoners' ward (P.W.)"
    if std.startswith("Isolation-pavilion-"):
        return "Pavilion " + std[-1]
    if "|" in std:
        return "Two wards written"
    if not std:
        return "No ward"
    if std in ("General", "Medical", "Surgical", "Maternity", "Children's",
               "British Section", "Isolation"):
        return std
    return "Other"


HEAT_ORDER = [
    ("General", "General"), ("Medical", "Medical"), ("Surgical", "Surgical"),
    ("Maternity", "Maternity"), ("Children's", "Children's"),
    ("British Section", "British Section"), ("P.M.F.", "P.M.F. (as written)"),
    ("G.M.W. / G.M.F.", "G.M.W./G.M.F. (as written)"),
    ("Prisoners' ward (P.W.)", "Prisoners' ward (P.W.)"),
    ("Isolation", "Isolation"),
    ("Pavilion A", "Pavilion A"), ("Pavilion B", "Pavilion B"),
    ("Pavilion C", "Pavilion C"), ("Pavilion D", "Pavilion D"),
    ("Pavilion E", "Pavilion E"),
    ("Hut", "Hut (as written)"), ("Q. Laz. / Laz.", "Q. Laz. (as written)"),
    ("Two wards written", "Two wards written"), ("Other", "Other"),
    ("No ward", "No ward"),
]


# ------------------------------------------------------------------- the census

def runs_of(dates: list[dt.date], gap: int = 10) -> list[tuple[dt.date, dt.date]]:
    ds = sorted(set(dates))
    out, start, prev = [], ds[0], ds[0]
    for d in ds[1:]:
        if (d - prev).days >= gap:
            out.append((start, prev))
            start = d
        prev = d
    out.append((start, prev))
    return out


def census(rows: list[dict], keep=lambda r: True):
    """Midnight census by day, the set of days it is valid on, and counts of
    what was left out."""
    occ: Counter = Counter()
    no_dis = bad = 0
    for r in rows:
        if not keep(r):
            continue
        a, b = day(r["Admission Date"]), day(r["Discharge Date"])
        if not a:
            continue
        if not b:
            no_dis += 1
            continue
        if b < a or (b - a).days > 400:
            bad += 1
            continue
        for i in range((b - a).days):
            occ[a + dt.timedelta(i)] += 1
    return occ, no_dis, bad


def valid_days(rows: list[dict]) -> tuple[set, list]:
    adm = [d for d in (day(r["Admission Date"]) for r in rows) if d and 1930 <= d.year <= 1948]
    runs = runs_of(adm)
    ok = set()
    for s, e in runs:
        d = s + dt.timedelta(BURN_IN)
        while d <= e:
            ok.add(d)
            d += dt.timedelta(1)
    return ok, runs


def month_days(y: int, m: int):
    d = dt.date(y, m, 1)
    while d.month == m:
        yield d
        d += dt.timedelta(1)


# --------------------------------------------------------- what the sources say

# Bed strength, every figure the project holds, by KIND. The kinds are not
# interchangeable: an announcement, a design, an establishment, a count of beds
# in use on a day, and an average of beds occupied are five different things.
BEDS = [
    # (date, beds, kind, what, source id)
    ("1930-06-30", 30, "reported", "“30 beds for general cases”", "mr-reports", "MR-1930 §15"),
    ("1933-03-01", None, "works", "+50 beds in the St. Luke's building, “early in 1933”", "mr-reports", "MR-1933 §7"),
    ("1935-09-01", 130, "reported", "130, of which 40 fever and isolation", "isa-0005xx0", "ISA 0005xx0 p. 323"),
    ("1935-09-01", 150, "approved", "to 150 by “a temporary hut designed to accommodate 20 cases”", "isa-0005xx0", "ISA 0005xx0 p. 323"),
    ("1935-09-12", 260, "announced", "180 surgical + 80 other, “will take two years”", "dhy19350912-01.2.71", "Doar HaYom 12 Sep 1935"),
    ("1935-10-01", 277, "designed", "189 general + 88 fever, “the total bedstrength of the whole Hospital”", "isa-0005xx0", "ISA 0005xx0 pp. 327–329"),
    ("1936-01-02", 208, "designed (our sum)", "beds named room by room in the Schedule of Accommodation; it states no total", "isa-0005xx0", "ISA 0005xx0 pp. 276–289"),
    ("1936-06-30", 171, "establishment", "General 74 · Isolation 70 · British 9 · Maternity 18", "bb-1936", "Blue Book 1936"),
    ("1937-06-30", 171, "establishment", "General 74 · Isolation 70 · British 9 · Maternity 18", "bb-1937", "Blue Book 1937"),
    ("1938-06-30", 220, "establishment", "General 88 · Isolation 76 · British 30 · Maternity 26", "bb-1938", "Blue Book 1938"),
    ("1938-10-15", 220, "reported", "“the new hospital … comprising 220 beds was opened in October, 1938”", "mr-reports", "MR-1938 §15"),
    ("1938-11-18", 230, "reported", "“for the present 230 beds, among them 90 for infectious diseases”", "hbkr19381118-01.2.28", "HaBoker 18 Nov 1938"),
    ("1938-12-22", 225, "reported", "the High Commissioner's speech; 200 planned + 24 “for the military”", "dav19381223-01.2.66", "Davar 23 Dec 1938"),
    ("1940-06-30", 220, "establishment", "General 88 · Isolation 76 · British 30 · Maternity 26", "isa-000v2ig", "DoH 1940 Table (a), ISA 000v2ig p. 248"),
    ("1941-06-30", 237, "establishment", "General 94 · Isolation 98 · British 28 · Maternity 17", "isa-000v2ig", "DoH 1941 Table (a), ISA 000v2ig p. 223"),
    ("1944-06-30", 261, "establishment", "General 117 · Isolation 98 · British 28 · Maternity 18", "isa-000v2ig", "DoH 1944 Table (a), ISA 000v2ig pp. 95–96"),
    ("1945-07-10", None, "works", "“a pavilion of 20 beds was added” during the war", "haretz19450710-01.2.24", "Haaretz 10 Jul 1945"),
    ("1948-05-02", 288, "reported", "at the handover to the municipality", "haretz19480503-01.2.39", "Haaretz 3 May 1948"),
]

# The official "daily average number of beds occupied": the realised figure,
# the one the register's census can be set against.
OCCUPIED = [
    (1936, 117.4, "bb-1936", "Blue Book 1936"),
    (1938, 133.5, "bb-1938", "Blue Book 1938"),
    (1940, 171.0, "isa-000v2ig", "DoH 1940, ISA 000v2ig p. 248"),
    (1941, 176.5, "isa-000v2ig", "DoH 1941, ISA 000v2ig p. 223"),
    (1944, 210.8, "isa-000v2ig", "DoH 1944, ISA 000v2ig pp. 95–96"),
]


# -------------------------------------------------------------- the computations

def compute(rows: list[dict]) -> dict:
    out: dict = {"register_rows": len(rows)}
    by_month: Counter = Counter()
    for r in rows:
        d = day(r["Admission Date"])
        if d and 1930 <= d.year <= 1948:
            by_month[(d.year, d.month)] += 1

    # census, whole house
    occ, no_dis, bad = census(rows)
    ok, runs = valid_days(rows)
    months = []
    for y in YEARS:
        for m in range(1, 13):
            ds = [d for d in month_days(y, m) if d in ok]
            if len(ds) >= 20:
                v = [occ[d] for d in ds]
                months.append({"m": f"{y}-{m:02d}", "mean": round(sum(v) / len(v), 1),
                               "max": max(v), "days": len(ds)})
    peak_day = max((d for d in ok), key=lambda d: occ[d])
    yearly = {}
    for y in YEARS:
        ds = [d for d in ok if d.year == y]
        if ds:
            yearly[y] = {"mean": round(sum(occ[d] for d in ds) / len(ds), 1), "days": len(ds)}
    out["census"] = {
        "months": months, "yearly": yearly,
        "peak": {"day": peak_day.isoformat(), "n": occ[peak_day]},
        "left_out_no_discharge": no_dis, "left_out_bad_stay": bad,
        "runs": [(s.isoformat(), e.isoformat()) for s, e in runs],
        "valid_days": len(ok),
    }

    # ward heatmap by month
    heat: dict = defaultdict(Counter)
    for r in rows:
        d = day(r["Admission Date"])
        if d and 1930 <= d.year <= 1948:
            heat[heat_row(r)][f"{d.year}-{d.month:02d}"] += 1
    out["heat"] = {k: dict(v) for k, v in heat.items()}
    out["month_totals"] = {f"{y}-{m:02d}": n for (y, m), n in by_month.items()}

    # the clerk's forms by year
    written: dict = defaultdict(Counter)
    for r in rows:
        d = day(r["Admission Date"])
        if d and 1930 <= d.year <= 1948:
            written[written_family(r["Ward as written"], d)][d.year] += 1
    out["written"] = {k: dict(v) for k, v in written.items()}

    # Isolation section, word + pavilions
    iso: Counter = Counter()
    for r in rows:
        d = day(r["Admission Date"])
        w = (r["Ward"] or "").strip()
        if d and (w == "Isolation" or w.startswith("Isolation-pavilion-")):
            iso[d.year] += 1
    out["isolation_section"] = dict(iso)
    out["isolation_word_only"] = sum(1 for r in rows if (r["Ward"] or "").strip() == "Isolation")
    out["pavilion_total"] = sum(1 for r in rows if (r["Ward"] or "").startswith("Isolation-pavilion-"))
    out["british_section"] = sum(1 for r in rows if (r["Ward"] or "").strip() == "British Section")

    # Gen. gives way to Med. as the wards move: the last General before the
    # move and the first Medical of the autumn, by admission date.
    gen = [d for d in (day(r["Admission Date"]) for r in rows if (r["Ward"] or "") == "General") if d and d.year == 1938]
    med = [d for d in (day(r["Admission Date"]) for r in rows if (r["Ward"] or "") == "Medical")
           if d and dt.date(1938, 9, 1) <= d <= dt.date(1938, 12, 31)]
    out["gen_med_switch"] = {"last_general": max(gen).isoformat(), "first_medical": min(med).isoformat(),
                             "general_after": sum(1 for r in rows if (r["Ward"] or "") == "General"
                                                  and "1938-11" <= (r["Admission Date"] or "")[:7] <= "1940-12")}
    out["corrections"] = corrections(rows)
    out["pavilions"] = pavilions(rows)
    out["hut"] = hut(rows, occ, ok)
    out["special"] = special(rows, occ)
    out["qlaz"] = qlaz(rows)
    out["nobed"] = nobed(rows)
    out["isol_letters"] = isol_letters(rows)
    return out


def corrections(rows: list[dict]) -> dict:
    """The four corrections to the ward column, counted by year, by setting the
    source the extraction delivered beside the build that ships."""
    if not SOURCE.exists():
        return {}
    src = {r["Index"]: r for r in read_tsv(SOURCE)}
    gyn = re.compile(r"\bgyn", re.I)
    out = {k: Counter() for k in ("gyn", "ven", "inf", "bs_total", "bs_kept", "bs_iso", "bs_pav",
                                    "bs_surg", "bs_other", "pav")}
    for r in rows:
        d = day(r["Admission Date"])
        if not d:
            continue
        y = d.year
        s = src.get(r["Index"])
        now = (r["Ward"] or "").strip()
        if "ward-pavilion-isolation" in (r["Review Flags"] or ""):
            out["pav"][y] += 1
        if not s:
            continue
        sstd, sraw = (s.get("standardized ward") or "").strip(), (s.get("Ward") or "").strip()
        if gyn.search(sstd) or gyn.search(sraw):
            out["gyn"][y] += 1
        if "venereal" in sstd.lower():
            out["ven"][y] += 1
        if "infect" in (sstd + " " + sraw).lower():
            out["inf"][y] += 1
        if sstd == "British Section":
            out["bs_total"][y] += 1
            if now == "British Section":
                out["bs_kept"][y] += 1
            elif now == "Isolation":
                out["bs_iso"][y] += 1
            elif now.startswith("Isolation-pavilion-") or not now:
                out["bs_pav"][y] += 1
            elif now == "Surgical":
                out["bs_surg"][y] += 1
            else:
                out["bs_other"][y] += 1
    return {k: dict(v) for k, v in out.items()}


PAV_LETTER = re.compile(r"(?:isol?|isl|is)\.?\s*\"?([a-e])\b", re.I)


def read_nb24() -> list[dict]:
    rows = []
    for p in sorted(glob.glob(str(REREADS / "out_F*.tsv"))):
        rows += [r for r in read_tsv(Path(p)) if r["notebook"] == "24" and r["serial"] != "NONE"]
    return rows


def describe(group: list[tuple[bool | None, bool | None, str]]) -> dict:
    n = len(group)
    males = sum(1 for m, _, _ in group if m)
    kids = [c for _, c, _ in group if c is not None]
    fam = Counter(f for _, _, f in group)
    return {"n": n, "male_pct": round(100 * males / n) if n else None,
            "child_pct": round(100 * sum(kids) / len(kids)) if kids else None,
            "top": top(fam)}


def pavilions(rows: list[dict]) -> dict:
    out: dict = {}
    nb24 = read_nb24()
    if nb24:
        g = defaultdict(list)
        for r in nb24:
            m = PAV_LETTER.search(r["ward_as_written"] or "")
            if m:
                g[m.group(1).upper()].append(((r["sex"] or "").strip().lower().startswith("m"),
                                              is_child(r["age"]), family(r["diagnosis_as_written"])))
        out["1939–40 scan"] = {k: describe(v) for k, v in sorted(g.items())}
    periods = {"1939–40 data": (1939, 1940), "1944": (1944, 1944), "1946": (1946, 1946),
               "1947": (1947, 1947), "1948": (1948, 1948)}
    for label, (a, b) in periods.items():
        g = defaultdict(list)
        for r in rows:
            d = day(r["Admission Date"])
            w = (r["Ward"] or "")
            if d and a <= d.year <= b and w.startswith("Isolation-pavilion-"):
                g[w[-1]].append((is_male(r), is_child(r["Age"], r["Age Unit"]),
                                 family(r["Diagnosis as written"])))
        out[label] = {k: describe(v) for k, v in sorted(g.items())}
    # plague's route into E, 1944
    route = Counter()
    for r in rows:
        d = day(r["Admission Date"])
        if d and d.year == 1944 and family(r["Diagnosis as written"]) == "plague":
            w = (r["Ward"] or "").replace("Isolation-pavilion-", "") or "(none)"
            route[("before 14 Aug" if d < dt.date(1944, 8, 14) else "from 14 Aug", w)] += 1
    out["plague_route_1944"] = {f"{k[0]}|{k[1]}": v for k, v in route.items()}
    return out


def isol_letters(rows: list[dict]) -> dict:
    """NB24: lettered isolation rows on the scan against the data."""
    nb24 = read_nb24()
    data = sum(1 for r in rows if r["Notebook_Number"] == "24"
               and (r["Ward"] or "").startswith("Isolation-pavilion-"))
    flat = sum(1 for r in rows if r["Notebook_Number"] == "24" and (r["Ward"] or "") == "Isolation")
    scan = sum(1 for r in nb24 if PAV_LETTER.search(r["ward_as_written"] or ""))
    return {"scan_lettered": scan, "data_lettered": data, "data_plain_isolation": flat}


def hut(rows: list[dict], _occ, _ok) -> dict:
    keep = lambda r: "hut" in (r["Ward as written"] or "").lower()
    hr = [r for r in rows if keep(r)]
    occ, no_dis, bad = census(rows, keep)
    days = {}
    d, end = dt.date(1937, 5, 1), dt.date(1938, 10, 31)
    while d <= end:
        days[d.isoformat()] = occ[d]
        d += dt.timedelta(1)
    dates = sorted(d for d in (day(r["Admission Date"]) for r in hr) if d)
    monthly = Counter(f"{d.year}-{d.month:02d}" for d in dates)
    rel = Counter((r["Religion"] or "").strip() or "not recorded" for r in hr)
    fam = Counter(family(r["Diagnosis as written"]) for r in hr)
    died = sum(1 for r in hr if "died" in (r["Result"] or "").lower() or "death" in (r["Result"] or "").lower())
    vals = [v for k, v in days.items() if "1937-08-01" <= k <= "1938-09-17"]
    return {"n": len(hr), "first": dates[0].isoformat(), "last": dates[-1].isoformat(),
            "first_after_stray": next(d for d in dates if d.year == 1937).isoformat(),
            "strays": [d.isoformat() for d in dates if d < dt.date(1937, 6, 1)],
            "male": sum(1 for r in hr if is_male(r)),
            "female": sum(1 for r in hr if (r["Sex"] or "").lower().startswith("f")),
            "religion": dict(rel), "top": top(fam, 8), "died": died,
            "census_days": days, "monthly": dict(monthly),
            "census_median_aug37_sep38": sorted(vals)[len(vals) // 2] if vals else None,
            "census_max": max(days.values()),
            "census_max_day": max(days, key=days.get),
            "left_out": no_dis + bad}


def special(rows: list[dict], _occ) -> dict:
    out: dict = defaultdict(Counter)
    detail: dict = defaultdict(lambda: defaultdict(Counter))
    for r in rows:
        d = day(r["Admission Date"])
        if not d:
            continue
        row = heat_row(r)
        if row in ("Prisoners' ward (P.W.)", "P.M.F.", "G.M.W. / G.M.F.", "Hut", "Q. Laz. / Laz.",
                   "Children's"):
            out[row][d.year] += 1
            detail[row]["religion"][(r["Religion"] or "").strip() or "not recorded"] += 1
            detail[row]["nationality"][(r["Nationality"] or "").strip() or "not recorded"] += 1
            detail[row]["sex"]["M" if is_male(r) else "F/other"] += 1
    # prisoners' ward occupancy, nights with anyone in it
    occ, _, _ = census(rows, lambda r: heat_row(r) == "Prisoners' ward (P.W.)")
    nights = [v for v in occ.values() if v]
    return {"by_year": {k: dict(v) for k, v in out.items()},
            "detail": {k: {kk: dict(vv) for kk, vv in v.items()} for k, v in detail.items()},
            "pw_nights_occupied": len(nights),
            "pw_median_when_occupied": sorted(nights)[len(nights) // 2] if nights else None,
            "pw_max": max(nights) if nights else None}


def qlaz(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        if "laz" in (r["Ward as written"] or "").lower():
            a, b = day(r["Admission Date"]), day(r["Discharge Date"])
            out.append({"adm": a.isoformat() if a else "", "ward": r["Ward as written"],
                        "religion": r["Religion"], "dx": r["Diagnosis as written"],
                        "class": r["Class"], "stay": (b - a).days if a and b else None,
                        "nb": r["Notebook_Number"], "page": r["Page_Number"]})
    return sorted(out, key=lambda x: x["adm"])


def nobed(rows: list[dict]) -> dict:
    """'No bed' entries: the 1944 scan read, and what the data itself carries."""
    scan = []
    for p in sorted(glob.glob(str(REREADS / "remarks-1944/remarks_*.tsv"))):
        for r in read_tsv(Path(p)):
            blob = " ".join([r.get("diagnosis") or "", r.get("result") or "", r.get("remarks") or ""])
            if re.search(r"no\s+beds?\s+(is\s+)?avail", blob, re.I):
                scan.append({"nb": r["notebook"], "page": r["page"], "row": r["row"],
                             "adm": r["adm"], "ward": r["ward"],
                             "note": re.sub(r"\s+", " ", blob).strip()})
    data = []
    for r in rows:
        blob = " ".join([r["Diagnosis as written"] or "", r["Result as written"] or ""])
        if re.search(r"no\s+beds?\b", blob, re.I):
            data.append({"adm": r["Admission Date"][:10], "ward": r["Ward as written"],
                         "nb": r["Notebook_Number"], "serial": r["Notebook Record ID"],
                         "note": re.sub(r"\s+", " ", blob).strip()})
    return {"scan_1944": scan, "data": sorted(data, key=lambda x: x["adm"])}


# ---------------------------------------------------------------- SVG and HTML

def esc(s) -> str:
    return html.escape(str(s), quote=True)


def mx(y: int, m: int, x0: float, w: float, d: int = 15) -> float:
    """x for a day of a month on the 1930-01 .. 1949-01 axis."""
    total = 19 * 12
    return x0 + w * (((y - 1930) * 12 + (m - 1)) + (d - 1) / 30.4) / total


def svg_census(fig: dict) -> str:
    W, H = 1000, 330
    L, R, T, B = 44, 12, 18, 34
    pw, ph = W - L - R, H - T - B
    ymax = 300

    def Y(v):
        return T + ph - ph * v / ymax

    def X(iso):
        d = dt.date.fromisoformat(iso)
        return mx(d.year, d.month, L, pw, d.day)

    p = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Daily in-patient census from the register, '
         f'1930 to 1948, against the bed strengths and average occupancy the sources report.">']
    for v in range(0, ymax + 1, 50):
        p.append(f'<line class="grid" x1="{L}" y1="{Y(v):.1f}" x2="{W - R}" y2="{Y(v):.1f}"/>')
        p.append(f'<text class="axis" x="{L - 6}" y="{Y(v) + 3.5:.1f}" text-anchor="end">{v}</text>')
    for y in YEARS:
        x = mx(y, 1, L, pw, 1)
        p.append(f'<line class="grid" x1="{x:.1f}" y1="{T + ph}" x2="{x:.1f}" y2="{T + ph + 4}"/>')
        if y % 2 == 0:
            p.append(f'<text class="axis" x="{mx(y, 7, L, pw, 1):.1f}" y="{T + ph + 17}" text-anchor="middle">{y}</text>')
    # months with no surviving notebook
    tot = fig["month_totals"]
    run = None
    spans = []
    for y in YEARS:
        for m in range(1, 13):
            empty = tot.get(f"{y}-{m:02d}", 0) == 0
            if empty and run is None:
                run = (y, m)
            if not empty and run is not None:
                spans.append((run, (y, m)))
                run = None
    if run:
        spans.append((run, (1949, 1)))
    for (y0, m0), (y1, m1) in spans:
        x0, x1 = mx(y0, m0, L, pw, 1), mx(y1, m1, L, pw, 1)
        if x1 - x0 > 6:
            p.append(f'<rect class="gapband" x="{x0:.1f}" y="{T}" width="{x1 - x0:.1f}" height="{ph}"/>')
    x0 = mx(1941, 1, L, pw, 1)
    p.append(f'<text class="absent" x="{(x0 + mx(1943, 12, L, pw, 31)) / 2:.1f}" y="{T + 14}" text-anchor="middle">NO NOTEBOOKS SURVIVE</text>')
    # the move
    xm = X(MOVE.isoformat())
    p.append(f'<line class="ev" x1="{xm:.1f}" y1="{T}" x2="{xm:.1f}" y2="{T + ph}"/>')
    p.append(f'<text class="evt" x="{xm - 4:.1f}" y="{T + ph - 6}" text-anchor="end">Mountain Road</text>')
    p.append(f'<text class="evt" x="{xm + 4:.1f}" y="{T + ph - 6}">Bat Galim</text>')
    # census: max (faint) then mean
    ms = fig["census"]["months"]

    def segs(key):
        out, cur, prev = [], [], None
        for m in ms:
            y, mo = map(int, m["m"].split("-"))
            idx = y * 12 + mo
            if prev is not None and idx != prev + 1:
                out.append(cur)
                cur = []
            cur.append((mx(y, mo, L, pw, 15), Y(m[key]), m))
            prev = idx
        if cur:
            out.append(cur)
        return out

    for s in segs("max"):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in s)
        p.append(f'<polyline class="cmax" points="{pts}"/>')
    for s in segs("mean"):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in s)
        p.append(f'<polyline class="cmean" points="{pts}"/>')
        for x, y, m in s:
            yy, mo = m["m"].split("-")
            label = dt.date(int(yy), int(mo), 1).strftime("%b %Y")
            p.append(f'<circle class="chit" cx="{x:.1f}" cy="{y:.1f}" r="3.2" '
                     f'data-t="{esc(label)}|census mean {m["mean"]} · max {m["max"]}|{m["days"]} days counted"/>')
    # establishment steps
    for d, beds, kind, what, sid, cite in BEDS:
        if kind == "establishment":
            yy = int(d[:4])
            xa, xb = mx(yy, 1, L, pw, 1), mx(yy + 1, 1, L, pw, 1)
            p.append(f'<g data-src="{sid}" tabindex="0" role="button" class="bedmark">'
                     f'<line class="estab" x1="{xa:.1f}" y1="{Y(beds):.1f}" x2="{xb:.1f}" y2="{Y(beds):.1f}"/>'
                     f'<rect x="{xa:.1f}" y="{Y(beds) - 6:.1f}" width="{xb - xa:.1f}" height="12" fill="transparent" '
                     f'data-t="{esc(cite)}|{beds} beds, nominal establishment|{esc(what)}"/></g>')
    # other figures as markers
    shapes = {"reported": "rep", "designed": "des", "designed (our sum)": "des", "announced": "ann",
              "approved": "ann"}
    labelled = {277: (8, -3), 260: (-8, 4), 130: (-8, 4), 150: (-8, 4), 30: (0, -8),
                288: (-4, -9), 230: (-2, -9), 225: (14, 4), 208: (0, 15), 220: (0, 0)}
    for d, beds, kind, what, sid, cite in BEDS:
        if beds is None or kind == "establishment":
            continue
        x, y = X(d), Y(beds)
        cls = shapes.get(kind, "rep")
        if cls == "des":
            mark = f'<rect class="bm des" x="{x - 4:.1f}" y="{y - 4:.1f}" width="8" height="8" transform="rotate(45 {x:.1f} {y:.1f})"/>'
        elif cls == "ann":
            mark = f'<circle class="bm ann" cx="{x:.1f}" cy="{y:.1f}" r="4.2"/>'
        else:
            mark = f'<circle class="bm rep" cx="{x:.1f}" cy="{y:.1f}" r="4.2"/>'
        dx, dy = labelled.get(beds, (0, -9))
        lab = "" if beds == 220 else (f'<text class="bml" x="{x + dx:.1f}" y="{y + dy:.1f}" '
                                       f'text-anchor="{"start" if dx > 6 else ("end" if dx < -3 else "middle")}">{beds}</text>')
        p.append(f'<g data-src="{sid}" tabindex="0" role="button" class="bedmark" '
                 f'data-t="{esc(cite)}|{beds} beds — {esc(kind)}|{esc(what)}">{mark}{lab}</g>')
    for yr, v, sid, cite in OCCUPIED:
        x, y = mx(yr, 7, L, pw, 1), Y(v)
        p.append(f'<g data-src="{sid}" tabindex="0" role="button" class="bedmark" '
                 f'data-t="{esc(cite)}|{v} beds occupied on an average day|the official realised figure">'
                 f'<rect class="occ" x="{x - 4.5:.1f}" y="{y - 4.5:.1f}" width="9" height="9"/></g>')
    p.append("</svg>")
    return "\n".join(p)


def svg_hut(h: dict) -> str:
    W, H = 1000, 230
    L, R, T, B = 40, 12, 14, 30
    pw, ph = W - L - R, H - T - B
    days = sorted(h["census_days"].items())
    d0 = dt.date.fromisoformat(days[0][0])
    n = len(days)
    ymax = 30

    def X(i):
        return L + pw * i / (n - 1)

    def Y(v):
        return T + ph - ph * v / ymax

    p = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Patients in the Hut each night, May 1937 to October 1938, against its design of 20 beds.">']
    for v in range(0, ymax + 1, 10):
        p.append(f'<line class="grid" x1="{L}" y1="{Y(v):.1f}" x2="{W - R}" y2="{Y(v):.1f}"/>')
        p.append(f'<text class="axis" x="{L - 6}" y="{Y(v) + 3.5:.1f}" text-anchor="end">{v}</text>')
    for i, (k, _) in enumerate(days):
        d = dt.date.fromisoformat(k)
        if d.day == 1:
            p.append(f'<line class="grid" x1="{X(i):.1f}" y1="{T + ph}" x2="{X(i):.1f}" y2="{T + ph + 4}"/>')
            lab = d.strftime("%b") + (f" {d.year}" if d.month in (1, 5) or i == 0 else "")
            p.append(f'<text class="axis" x="{X(i) + 2:.1f}" y="{T + ph + 16}">{lab}</text>')
    p.append(f'<line class="design" x1="{L}" y1="{Y(20):.1f}" x2="{W - R}" y2="{Y(20):.1f}"/>')
    p.append(f'<text class="evt" x="{L + 6}" y="{Y(20) - 5:.1f}">designed for 20 cases (ISA 0005xx0 p. 323)</text>')
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, (_, v) in enumerate(days))
    area = f"{X(0):.1f},{Y(0):.1f} {pts} {X(n - 1):.1f},{Y(0):.1f}"
    p.append(f'<polygon class="harea" points="{area}"/>')
    p.append(f'<polyline class="hline" points="{pts}"/>')
    # hover targets, one per week
    for i in range(0, n, 7):
        k, v = days[i]
        d = dt.date.fromisoformat(k)
        p.append(f'<rect x="{X(i) - 2:.1f}" y="{T}" width="{pw * 7 / n:.1f}" height="{ph}" fill="transparent" '
                 f'data-t="week of {d.strftime("%-d %b %Y")}|{max(x[1] for x in days[i:i + 7])} in the Hut at most"/>')
    xm = X((MOVE - d0).days)
    p.append(f'<line class="ev" x1="{xm:.1f}" y1="{T}" x2="{xm:.1f}" y2="{T + ph}"/>')
    p.append(f'<text class="evt" x="{xm - 4:.1f}" y="{T + 12}" text-anchor="end">the move, 31 Oct</text>')
    p.append("</svg>")
    return "\n".join(p)


def svg_heat(fig: dict) -> str:
    rows = [(k, lab) for k, lab in HEAT_ORDER if fig["heat"].get(k)]
    W = 1000
    LAB, R, T, B = 178, 8, 34, 26
    rh = 15
    H = T + rh * len(rows) + B
    pw = W - LAB - R
    tot = fig["month_totals"]

    def X(y, m, d=1):
        return mx(y, m, LAB, pw, d)

    p = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Wards by month, 1930 to 1948: the share of each month\'s admissions written to each ward, as standardized.">']
    # gaps
    for y in YEARS:
        for m in range(1, 13):
            if not tot.get(f"{y}-{m:02d}"):
                p.append(f'<rect class="hgap" x="{X(y, m):.2f}" y="{T}" width="{pw / 228:.2f}" height="{rh * len(rows)}"/>')
    for i, (k, lab) in enumerate(rows):
        y0 = T + i * rh
        p.append(f'<text class="hl" x="{LAB - 8}" y="{y0 + rh * 0.72:.1f}" text-anchor="end">{esc(lab)}</text>')
        p.append(f'<line class="hrule" x1="{LAB}" y1="{y0 + rh:.1f}" x2="{W - R}" y2="{y0 + rh:.1f}"/>')
        for mk, n in sorted(fig["heat"][k].items()):
            yy, mm = map(int, mk.split("-"))
            share = n / tot[mk]
            op = min(1.0, 0.16 + 0.84 * math.sqrt(share / 0.5))
            label = dt.date(yy, mm, 1).strftime("%b %Y")
            p.append(f'<rect class="hc" x="{X(yy, mm):.2f}" y="{y0 + 1.5:.1f}" width="{pw / 228 + 0.25:.2f}" '
                     f'height="{rh - 3}" style="fill-opacity:{op:.2f}" '
                     f'data-t="{esc(label)} · {esc(lab.rstrip(" ¹²³⁴"))}|{n} of {tot[mk]} admissions ({100 * share:.0f}%)"/>')
    for y in YEARS:
        x = X(y, 1)
        p.append(f'<line class="grid" x1="{x:.1f}" y1="{T - 3}" x2="{x:.1f}" y2="{T + rh * len(rows) + 3}" opacity=".55"/>')
        p.append(f'<text class="axis" x="{X(y, 7):.1f}" y="{T + rh * len(rows) + 16}" text-anchor="middle">{str(y)[2:] if y % 2 else y}</text>')
    # annotations
    xm = X(1938, 10, 31)
    xd = X(1939, 12, 1)
    xg0, xg1 = X(1940, 3, 1), X(1944, 2, 8)
    xl = X(1944, 3, 13)
    ann = [
        (xm, "the move · 31 Oct 1938", "end", 11),
        (xd, "“Is. A–E” · 1 Dec 1939", "start", 22),
        (xl, "first bare letter · 13 Mar 1944", "start", 11),
    ]
    for x, t, anchor, dy in ann:
        p.append(f'<line class="ev" x1="{x:.1f}" y1="{T - dy + 4}" x2="{x:.1f}" y2="{T + rh * len(rows)}"/>')
        p.append(f'<text class="evt" x="{x + (-4 if anchor == "end" else 4):.1f}" y="{T - dy + 1}" text-anchor="{anchor}">{t}</text>')
    p.append(f'<text class="absent" x="{(xg0 + xg1) / 2:.1f}" y="{T + rh * len(rows) / 2:.1f}" text-anchor="middle">NO NOTEBOOKS</text>')
    p.append("</svg>")
    return "\n".join(p)


def shade(v: int, rowmax: int) -> str:
    if not v:
        return ""
    pct = 6 + 34 * math.sqrt(v / rowmax)
    return f' style="background:color-mix(in srgb,var(--ink) {pct:.0f}%,transparent);color:{"var(--paper)" if pct > 28 else "inherit"}"'


def table_written(fig: dict) -> str:
    years = [y for y in YEARS if y not in MISSING_YEARS]
    w = fig["written"]
    h = ['<div class="tw"><table class="wtab"><caption>The clerk\'s marks, by year · admissions</caption><thead><tr><th>written as</th>']
    h += [f'<th class="n">{y}</th>' for y in years] + ['<th class="n">all</th></tr></thead><tbody>']
    for fam in WRITTEN_ORDER:
        c = w.get(fam, {})
        if not c:
            continue
        rowmax = max(c.values())
        h.append(f'<tr><td class="wf">{esc(fam)}</td>')
        for y in years:
            v = c.get(str(y), c.get(y, 0))
            h.append(f'<td class="n"{shade(v, rowmax)}>{v or ""}</td>')
        h.append(f'<td class="n strong">{sum(c.values()):,}</td></tr>')
    h.append('</tbody></table></div>')
    return "".join(h)


def table_corrections(fig: dict) -> str:
    c = fig["corrections"]
    if not c:
        return "<p><em>Source TSV not found; corrections not counted.</em></p>"
    years = [y for y in YEARS if y not in MISSING_YEARS]

    def g(k, y):
        return c.get(k, {}).get(str(y), c.get(k, {}).get(y, 0))

    lines = [
        ("1", "“Gynecology” read back as General", "gyn", "the clerk's Gen., in either of the extraction's ward columns; 7 Aug 2026"),
        ("2a", "“Infectious …” merged into Isolation", "inf", "one Fever Section, two clerical names, either column; 27 Sep 2026"),
        ("2b", "“Venereal Diseases” cleared", "ven", "never written by a clerk; no venereal diagnosis; 27 Sep 2026"),
        ("3", "“British Section” re-read off the scans, and moved", None, "21–22 Oct 2026"),
        ("4", "Lettered pavilions ruled part of Isolation", "pav", "after the move only; 21 Oct 2026"),
    ]
    h = ['<div class="tw"><table class="wtab"><caption>The corrections to the ward column, by year · admissions affected</caption>'
         '<thead><tr><th></th><th>correction</th>']
    h += [f'<th class="n">{y}</th>' for y in years] + ['<th class="n">all</th></tr></thead><tbody>']
    for no, label, key, note in lines:
        if key:
            vals = [g(key, y) for y in years]
        else:
            vals = [g("bs_total", y) - g("bs_kept", y) for y in years]
        h.append(f'<tr><td class="nb">{no}</td><td>{esc(label)}<br><span class="fn">{esc(note)}</span></td>')
        h += [f'<td class="n">{v or ""}</td>' for v in vals]
        h.append(f'<td class="n strong">{sum(vals):,}</td></tr>')
    bs_moved = {k: sum(c.get(k, {}).values()) for k in ("bs_iso", "bs_pav", "bs_surg", "bs_other")}
    h.append(f'<tr><td></td><td colspan="{len(years) + 2}" class="fn">Of the {sum(c.get("bs_total", {}).values()):,} '
             f'records the extraction called British Section, {sum(c.get("bs_kept", {}).values()):,} stay; '
             f'{bs_moved["bs_iso"]:,} are Isolation (“Is.”), {bs_moved["bs_pav"]:,} a bare pavilion letter or no ward, '
             f'{bs_moved["bs_surg"]:,} Surgical (S/S), {bs_moved["bs_other"]:,} other wards.</td></tr>')
    h.append('</tbody></table></div>')
    return "".join(h)


def table_pavilions(fig: dict) -> str:
    pv = fig["pavilions"]
    periods = [k for k in ("1939–40 data", "1944", "1946", "1947", "1948") if k in pv]
    head = {"1939–40 data": "1939–40"}
    h = ['<div class="tw"><table class="ptab"><caption>The pavilions by period · admissions, % male, % under 13, leading diagnoses</caption><thead><tr><th>pavilion</th>']
    h += [f'<th>{head.get(p, p)}</th>' for p in periods] + ['</tr></thead><tbody>']
    for L in "ABCDE":
        h.append(f'<tr><td class="pl">{L}</td>')
        for p in periods:
            d = pv[p].get(L)
            if not d:
                h.append('<td class="fn">—</td>')
                continue
            tops = ", ".join(f"{esc(k)} {v}" for k, v in d["top"])
            h.append(f'<td><b>{d["n"]}</b> · {d["male_pct"]}% m · {d["child_pct"] if d["child_pct"] is not None else "–"}% &lt;13'
                     f'<br><span class="fn">{tops}</span></td>')
        h.append('</tr>')
    h.append('</tbody></table></div>')
    return "".join(h)


def table_special(fig: dict) -> str:
    s = fig["special"]["by_year"]
    years = [y for y in YEARS if y not in MISSING_YEARS]
    order = ["Prisoners' ward (P.W.)", "P.M.F.", "G.M.W. / G.M.F.", "Children's", "Hut", "Q. Laz. / Laz."]
    h = ['<div class="tw"><table class="wtab"><caption>Wards named for who was in them, by year · admissions</caption><thead><tr><th>ward</th>']
    h += [f'<th class="n">{y}</th>' for y in years] + ['<th class="n">all</th></tr></thead><tbody>']
    for k in order:
        c = s.get(k, {})
        if not c:
            continue
        h.append(f'<tr><td class="wf">{esc(k)}</td>')
        h += [f'<td class="n">{c.get(str(y), c.get(y, "")) or ""}</td>' for y in years]
        h.append(f'<td class="n strong">{sum(c.values())}</td></tr>')
    h.append('</tbody></table></div>')
    return "".join(h)


def table_nobed(fig: dict) -> str:
    rows = fig["nobed"]["data"]
    h = ['<div class="tw"><table><caption>“No bed”: patients registered and turned away · in the data since 22 Oct 2026</caption>'
         '<thead><tr><th>admitted</th><th>NB · serial</th><th>ward as written</th><th>diagnosis and result as written</th></tr></thead><tbody>']
    for r in sorted(rows, key=lambda r: (r["adm"] or "9", int(r["nb"]), r["serial"])):
        h.append(f'<tr><td class="nb">{esc(r["adm"] or "—")}</td><td class="nb">{esc(r["nb"])} · {esc(r["serial"])}</td>'
                 f'<td>{esc(written_part(r["ward"]))}</td><td>{esc(r["note"])}</td></tr>')
    h.append('</tbody></table></div>')
    return "".join(h)


def table_census_check(fig: dict) -> str:
    yr = fig["census"]["yearly"]
    h = ['<div class="tw"><table><caption>The register\'s census against the official average · beds occupied</caption>'
         '<thead><tr><th>year</th><th class="n">official daily average</th><th class="n">register census, mean</th>'
         '<th class="n">days counted</th><th class="n">register ÷ official</th><th>source</th></tr></thead><tbody>']
    for y, v, sid, cite in OCCUPIED:
        c = yr.get(y) or yr.get(str(y))
        if c:
            h.append(f'<tr><td class="nb">{y}</td><td class="n">{v}</td><td class="n">{c["mean"]}</td><td class="n">{c["days"]}</td>'
                     f'<td class="n">{100 * c["mean"] / v:.0f}%</td><td><button class="src" data-src="{sid}">{esc(cite)}</button></td></tr>')
        else:
            h.append(f'<tr><td class="nb">{y}</td><td class="n">{v}</td><td class="n">—</td><td class="n">0</td><td class="n">—</td>'
                     f'<td><button class="src" data-src="{sid}">{esc(cite)}</button></td></tr>')
    h.append('</tbody></table></div>')
    return "".join(h)


def table_beds() -> str:
    h = ['<div class="tw"><table class="beds"><caption>Every bed figure, with its kind</caption><thead><tr>'
         '<th>date</th><th class="n">beds</th><th>kind</th><th>what the source says</th><th>source</th></tr></thead><tbody>']
    for d, beds, kind, what, sid, cite in BEDS:
        h.append(f'<tr><td class="nb">{esc(d[:7] if d.endswith("-06-30") else d)}</td><td class="n strong">{beds if beds else "+"}</td>'
                 f'<td><span class="kind k-{esc(kind.split()[0])}">{esc(kind)}</span></td><td>{esc(what)}</td>'
                 f'<td><button class="src" data-src="{sid}">{esc(cite)}</button></td></tr>')
    for y, v, sid, cite in OCCUPIED:
        h.append(f'<tr><td class="nb">{y}</td><td class="n strong">{v}</td><td><span class="kind k-occupied">occupied, daily average</span></td>'
                 f'<td>average number of beds occupied each day</td><td><button class="src" data-src="{sid}">{esc(cite)}</button></td></tr>')
    h.append('</tbody></table></div>')
    return "".join(h)


def table_qlaz(fig: dict) -> str:
    h = ['<div class="tw"><table><caption>“Q. Laz.” and “Laz.” as a ward, 1935</caption><thead><tr><th>admitted</th>'
         '<th>written</th><th>religion</th><th>diagnosis as written</th><th>class</th><th class="n">days</th><th>NB · p.</th></tr></thead><tbody>']
    for r in fig["qlaz"]:
        h.append(f'<tr><td class="nb">{esc(r["adm"])}</td><td>{esc(r["ward"])}</td><td>{esc(r["religion"])}</td>'
                 f'<td>{esc(r["dx"])}</td><td>{esc(r["class"])}</td><td class="n">{r["stay"] if r["stay"] is not None else "—"}</td>'
                 f'<td class="nb">{esc(r["nb"])} · {esc(r["page"])}</td></tr>')
    h.append('</tbody></table></div>')
    return "".join(h)


# Register pages shown in the dossier. Only the right-hand block is ever
# fetched (ward, class, dates, days, diagnosis, result: 50-87% of the spread's
# width), never the name column. Each was looked at before it was listed.
IIIF_PAGES = ROOT / "data/public/iiif-pages.tsv"
RIGHT_BLOCK = "pct:50,0,37,100"
SCANS = [
    ("12", "76", "19 Jul 1935", "“Q. Laz.” as a ward: the first row, T.B.C. lungs, 52 days."),
    ("19", "99", "6 Jul 1938", "Bomb casualties written to “Mat”, every row the same hand and date."),
    ("20", "63", "17 Sep 1938", "The last “Hut” admission, burns and pyrexia."),
    ("20", "72", "27–29 Sep 1938", "“Gen.” on 27 September, “Med” from 28 September: the vocabulary of the new ward blocks."),
    ("20", "77", "3 Oct 1938", "The day the main blocks were taken over: the last “Gen” rows, surgical cases, beside “Surg”."),
    ("20", "99", "30–31 Oct 1938", "The last page at Mountain Road: Surg, Isol, Mat."),
    ("21", "1", "31 Oct 1938", "The first page of notebook 21, the same day, with no heading."),
    ("24", "13", "11 Dec 1939", "“Isol B”, “Isol C”, “Isol D”, “Isol E”: the letters the extraction kept as plain Isolation."),
    ("27", "68", "19 Aug 1944", "A plague death: “B/S” struck through and “E.” written."),
    ("28", "10", "11 Sep 1944", "“NO BEDS AVAILABLE” across two Maternity rows; and a patient “left against advice”."),
    ("31", "33", "5 May 1947", "Pavilion E, all rows: the Acre prison wounded."),
    ("32", "47", "29 Sep 1947", "P.M.F. rows, bomb explosion; on the last, “Br.” struck and P.M.F. written."),
]


def scans_html() -> str:
    svc = {}
    if IIIF_PAGES.exists():
        for r in read_tsv(IIIF_PAGES):
            svc.setdefault((r["Notebook_Number"], r["Page_Number"]), r["image_service"])
    h = ['<div class="scans">']
    for nb, pg, when, what in SCANS:
        s = svc.get((nb, pg))
        if not s:
            print(f"scans: no IIIF service for NB{nb} p{pg}", file=sys.stderr)
            continue
        big, small = f"{s}/{RIGHT_BLOCK}/1600,/0/default.jpg", f"{s}/{RIGHT_BLOCK}/420,/0/default.jpg"
        h.append(f'<figure class="scan"><a href="{esc(big)}" target="_blank" rel="noopener">'
                 f'<img src="{esc(small)}" loading="lazy" alt="Notebook {nb}, page {pg}, ward to result columns"></a>'
                 f'<figcaption><b>NB{nb} p. {pg}</b> · {esc(when)}<br>{esc(what)}</figcaption></figure>')
    h.append("</div>")
    return "".join(h)


# ---------------------------------------------------------------------- sources

NLI = "https://www.nli.org.il/en/newspapers/?a=d&d="

# Sources the dossier cites that neither the press registry nor
# sources/archival-sources.json carries. Kept here, not in the shared files,
# so the History tab's committed registry is untouched.
LOCAL_SOURCES = {
    "bb-1936": {
        "pub": "Palestine Blue Book 1936 — Government hospitals table",
        "place": "Government of Palestine", "date": "1936-12-31", "lang": "English", "kind": "archive",
        "url": "https://archive.org/details/palestine-blue-book-1936",
        "id": "Blue Book 1936 · hospital table · data/haifa_hospital_bluebook_tables_extracted.txt",
        "note": "<p>Haifa Government Hospital, nominal bed strength: <strong>General 74, Isolation 70, British 9, Maternity 18 = 171</strong>. Admissions 3,119 (Moslems 1,586, Christians 805, Jews 605, others 123); deaths 180; discharges 2,914; <strong>daily average in hospital 117.4</strong>. Read off an OCR text layer and checked by row arithmetic: the 70 prints as “Jo”.</p>",
    },
    "bb-1937": {
        "pub": "Palestine Blue Book 1937 — Government hospitals table",
        "place": "Government of Palestine", "date": "1937-12-31", "lang": "English", "kind": "archive",
        "url": "https://archive.org/details/palestine-blue-book-1937",
        "id": "Blue Book 1937 · hospital table",
        "note": "<p>Haifa: <strong>74 / 70 / 9 / 18 = 171</strong>, unchanged from 1936 (the OCR reads “14 7o”). Admissions 1,836 / 847 / 541 / 67 = 3,291. The daily-average column was not captured in the text layer.</p>",
    },
    "bb-1938": {
        "pub": "Palestine Blue Book 1938 — Government hospitals table",
        "place": "Government of Palestine", "date": "1938-12-31", "lang": "English", "kind": "archive",
        "url": "https://archive.org/details/palestine-blue-book-1938",
        "id": "Blue Book 1938 · hospital table",
        "note": "<p>Haifa: <strong>General 88, Isolation 76, British 30, Maternity 26 = 220</strong> — the same 220 the Mandate report gives for the new building. Admissions 3,175; deaths 188; discharges 3,028; <strong>daily average 133.5</strong>. 1938 straddles the move: nine and a half months on Mountain Road, two and a half at Bat Galim.</p>",
    },
    "isa-000v2ig": {
        "pub": "ISA 000v2ig — Department of Health annual reports, 1941–47 (with printed reports enclosed)",
        "place": "Israel State Archives", "date": "1941-01-01", "lang": "English", "kind": "archive",
        "url": "https://www.archives.gov.il/details/000v2ig",
        "id": "ISA 000v2ig · M/20/41 · 282 pp",
        "note": "<p>The Chief Secretary's file on the Department of Health's annual reports, with printed reports enclosed for some years. Table (a), “Government and Municipal Hospitals”, gives Haifa per year: <strong>nominal bed strength</strong> by General / Isolation / British / Maternity, admissions by religion, deaths and the daily average of beds occupied.</p><p>1940: 88 / 76 / 30 / 26 = <strong>220</strong>, occupied 171.0 (p. 248). 1941: 94 / 98 / 28 / 17 = <strong>237</strong>, occupied 176.5 (p. 223). 1944: 117 / 98 / 28 / 18 = <strong>261</strong>, occupied 210.8 (pp. 95–96). No Haifa row has been found for 1942, 1943 or 1945–47.</p>",
        "pages": "pp. 95–96 (1944) · 223 (1941) · 248–249 (1940)",
    },
    "isa-0005xx0-memo": {
        "pub": "ISA 0005xx0 pp. 323–331 — the founding memorandum, Sept/Oct 1935",
        "place": "Israel State Archives", "date": "1935-10-01", "lang": "English", "kind": "archive",
        "url": "https://www.archives.gov.il/details/0005xx0",
        "id": "ISA 0005xx0 · DMS to Chief Secretary, ref. 108/107, answering M/47/34 of 4 Sept 1935",
        "note": "<p>“The bedstrength of the Government Hospital, Haifa, at present is <strong>130 of which 40 beds are for fever and isolation cases</strong> … the Secretary of State has recently approved of the increase of the bedstrength to 150 by the construction of a <strong>temporary hut designed to accommodate 20 cases</strong>.” (p. 323)</p><p>“…the present <strong>leased premises of St. Luke's Mission Hospital</strong> must be vacated by the end of December, 1938.” (p. 323)</p><p>“…beds which should be allotted to general medical and surgical cases, have to be given up for the accommodation of cases of Typhoid Fever. This situation now arises annually.” (p. 325)</p><p>Allocation by section (p. 327) and “the total bedstrength of the whole Hospital will consequently be <strong>277 beds</strong>” (p. 329). The Fever Section “will not provide for such highly infectious cases as Plague, Cholera, Yellow Fever, Smallpox and Typhus”.</p>",
        "pages": "pp. 323 (old hospital, lease, hut) · 325 (typhoid) · 327–329 (allocation, 277)",
    },
    "isa-0005xx0-schedule": {
        "pub": "ISA 0005xx0 pp. 276–289 — Schedule of Accommodation, “Proposed General Hospital, Haifa”",
        "place": "Israel State Archives", "date": "1936-01-02", "lang": "English", "kind": "archive",
        "url": "https://www.archives.gov.il/details/0005xx0",
        "id": "ISA 0005xx0 · DMS to Director of Public Works, PWD stamp 2 JAN 1936 · 8 pp lettered A–V",
        "note": "<p>“I forward herewith a revised schedule of accommodation required in the proposed Haifa Hospital.” Room by room: ward blocks C–F (Male Medical, Female Medical, Male Surgical, Female Surgical), <strong>26 beds each</strong>, each 2 × 10-bed wards, 1 × 2-bed, 2 × 1-bed; British Section (male 6-bed ward + 4 single rooms; female 6 single rooms); Maternity (8 third-class, 2 second, 2 first, nursery for 18 cots); Maternity Isolation (2 single rooms); Fever Section V: a double-storey pavilion of <strong>44</strong>, a double-storey pavilion of <strong>16</strong> single rooms, a single-storey pavilion of <strong>14</strong> “capable of having second storey added in future”.</p><p>Also the Main Kitchen <strong>(Kosher)</strong>, a Mortuary with P.M. room, laundry with two disinfecting rooms and a separate foul wash, and staff quarters and dining rooms segregated British / Palestinian and male / female.</p>",
        "pages": "pp. 276 (covering letter) · 277–289 (schedule, versos blank)",
    },
    "isa-0005xx0-handover": {
        "pub": "ISA 0005xx0 pp. 510, 532, 537, 1055 — occupation and taking over, 1938–40",
        "place": "Israel State Archives", "date": "1939-01-06", "lang": "English", "kind": "archive",
        "url": "https://www.archives.gov.il/details/0005xx0",
        "id": "ISA 0005xx0 · DMS to Director of Public Works, refs 108/107 R and 123/61",
        "note": "<p>p. 537, stamped 6 JAN 1939: “The official taking over took place for the main blocks and Pavilions A, B, C, D <strong>October 3rd, 1938</strong>. For Pavilions E and F <strong>December 21st, 1938</strong>.”</p><p>p. 532, stamped 11 JAN 1939: “Occupation of the Hospital buildings started in the <strong>second half of September, 1938</strong>.”</p><p>p. 510, 28 Feb 1939: water “for the old Hospital at Haifa … up to the time it was evacuated”.</p><p>p. 1055, 6 March 1940: “Pavilions ‘E’ and ‘F’ taking over” — a snagging list signed by the Steward, Pettitt.</p>",
        "pages": "pp. 510 · 532 · 537 · 1055",
    },
    "isa-0005xx0-plague": {
        "pub": "ISA 0005xx0 pp. 1301–1421 — the Plague Unit, Dec 1941 – Apr 1942",
        "place": "Israel State Archives", "date": "1942-03-16", "lang": "English", "kind": "archive",
        "url": "https://www.archives.gov.il/details/0005xx0",
        "id": "ISA 0005xx0 · PWD minutes and estimates HA/204, drawing B/1641",
        "note": "<p>“Haifa Hosp. Plague Unit” (p. 1301, Dec 1941); a sketch plan handed to Dr Macqueen on 22 Jan 1942 (p. 1347); estimate HA/204 (p. 1380); “Plague Service Station Haifa Hosp.”, about <strong>£P.2,700</strong> (p. 1388); and the siting, p. 1411, 16 March 1942: “to facilitate the difficulties of foundations and expansion joint of <strong>the adjacent existing verandah</strong> the new building may be moved 90 cms away from the edge of verandah and 30 cms or so to the south”. Drawing <strong>B/1641</strong> (p. 1412).</p>",
        "pages": "pp. 1301 · 1347 · 1380 · 1388 · 1411 · 1412 · 1421",
    },
    "isa-0005xx0-drawings": {
        "pub": "ISA 0005xx0 p. 1223 — PWD Drawing E/524, Schedule of Received Record Drawings, 18 Mar 1941",
        "place": "Israel State Archives", "date": "1941-03-18", "lang": "English", "kind": "archive",
        "url": "https://www.archives.gov.il/details/0005xx0",
        "id": "ISA 0005xx0 p. 1223 · Drawing E/524",
        "note": "<p>About 65 as-built drawings, E/R 224–286: a main block of six storeys (basement to fifth floor) with numbered units 1–24 across the floors; <strong>Pavilions A, B, C, D, E, F</strong>, each with its own sheet; Block 9 (garage and workshop below, attendants' quarters above). The last entry is <strong>E/R 286 “KEY PLAN”</strong>, the sheet that would say which unit was which. It is not in this file. The drawings were “forwarded to DEHAF”, the Department's Haifa office.</p>",
    },
    "isa-0005xx0-airraid": {
        "pub": "ISA 0005xx0 pp. 1121, 1130 — the casualty entrance after the 1940 air raid",
        "place": "Israel State Archives", "date": "1940-08-13", "lang": "English", "kind": "archive",
        "url": "https://www.archives.gov.il/details/0005xx0",
        "id": "ISA 0005xx0 · District Engineer to DPW, sketch HA/4171",
        "note": "<p>“During the last air raid on Haifa the Government Hospital was called upon to deal with a large number of casualties in a short time. It was found that with the existing approach road to the casualty entrance, serious congestion occurred, as it was not possible for an ambulance to leave the courtyard whilst casualties were being dealt with at the entrance.” A second emergency approach was asked for; £P.26 of A.R.P. funds opened a gate.</p>",
    },
    "pls19470507-01.1.3": {
        "pub": "Palestine Post", "place": "Jerusalem", "date": "1947-05-07", "lang": "English",
        "url": NLI + "pls19470507-01.1.3", "id": "pls19470507-01.1.3",
        "note": "<p>“Prison death toll rises”: “Of the <strong>14 prisoners</strong> known to have been wounded during the Acre prison break, <strong>one has died</strong>, and six are still reported to be in a serious condition.” An unidentified man “brought dead to the Government Hospital on the night of the attack” was buried in the Jewish cemetery.</p>",
    },
    "pls19470511-01.1.3": {
        "pub": "Palestine Post", "place": "Jerusalem", "date": "1947-05-11", "lang": "English",
        "url": NLI + "pls19470511-01.1.3", "id": "pls19470511-01.1.3",
        "note": "<p>Two of the Acre wounded “were transferred from Haifa Government Hospital to Acre Prison today” (Saturday 10 May 1947).</p>",
    },
    "hbkr19390814-01.2.45": {
        "pub": "HaBoker", "place": "Tel Aviv", "date": "1939-08-14", "lang": "Hebrew",
        "url": NLI + "hbkr19390814-01.2.45", "id": "hbkr19390814-01.2.45",
        "note": "<p>Haifa's air-defence casualty stations include “<strong>the new and old Government Hospital</strong>” — both buildings standing and distinguishable a year after the move.</p>",
    },
    "dav19361015-01.2.116": {
        "pub": "Davar", "place": "Tel Aviv", "date": "1936-10-15", "lang": "Hebrew",
        "url": NLI + "dav19361015-01.2.116", "id": "dav19361015-01.2.116",
        "note": "<p>Kupat Holim health column: typhus “appeared this summer in many places … its carrier is the rat flea”.</p>",
    },
}


def history_sources() -> dict:
    """The history document's own source entries, for items both cite."""
    if not HISTORY.exists():
        return {}
    m = re.search(r'<script id="src-data" type="application/json">(.*?)</script>',
                  HISTORY.read_text(encoding="utf-8"), re.S)
    return json.loads(m.group(1).replace("<\\/", "</")) if m else {}


def build_sources(page: str) -> dict:
    ids = sorted(set(re.findall(r'data-src="([^"]+)"', page)))
    reg = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {}
    reg = {**history_sources(), **reg, **institutions.SOURCES}
    arc = json.loads(ARCHIVAL.read_text(encoding="utf-8")) if ARCHIVAL.exists() else {}
    out, missing = {}, []
    for k in ids:
        if k in LOCAL_SOURCES:
            out[k] = LOCAL_SOURCES[k]
        elif k in arc:
            out[k] = arc[k]
        elif k in reg:
            out[k] = reg[k]
        else:
            missing.append(k)
    if missing:
        print(f"sources: {len(missing)} cited ids have no entry: {', '.join(missing)}", file=sys.stderr)
    return out


# ------------------------------------------------------------------------ inject

def inject(fig: dict) -> None:
    page = DOSSIER.read_text(encoding="utf-8")
    inst_parts, inst_nums = institutions.figures()
    parts = {
        "census": svg_census(fig),
        "census-check": table_census_check(fig),
        "beds": table_beds(),
        "heat": svg_heat(fig),
        "written": table_written(fig),
        "pavilions": table_pavilions(fig),
        "hut": svg_hut(fig["hut"]),
        "special": table_special(fig),
        "qlaz": table_qlaz(fig),
        "nobed": table_nobed(fig),
        "scans": scans_html(),
        **inst_parts,
    }
    for name, body in parts.items():
        rx = re.compile(rf"(<!-- fig:{re.escape(name)} -->).*?(<!-- /fig:{re.escape(name)} -->)", re.S)
        if not rx.search(page):
            print(f"inject: no region for {name}", file=sys.stderr)
            continue
        page = rx.sub(lambda m: m.group(1) + "\n" + body + "\n" + m.group(2), page)
    # numbers quoted in prose: <span data-n="key">…</span>
    nums = {**numbers(fig), **inst_nums}
    page = re.sub(r'(<span data-n="([a-z0-9_-]+)">)(.*?)(</span>)',
                  lambda m: m.group(1) + nums.get(m.group(2), m.group(3)) + m.group(4), page)
    for k in set(re.findall(r'data-n="([a-z0-9_-]+)"', page)) - set(nums):
        print(f"inject: no number for data-n={k}", file=sys.stderr)
    srcs = build_sources(page)
    blob = json.dumps(srcs, ensure_ascii=False, indent=0, sort_keys=True).replace("</", "<\\/")
    page = re.sub(r'(<script id="src-data" type="application/json">).*?(</script>)',
                  lambda m: m.group(1) + blob + m.group(2), page, flags=re.S)
    DOSSIER.write_text(page, encoding="utf-8")
    print(f"injected {len(parts)} figures, {len(nums)} numbers, {len(srcs)} sources → {DOSSIER}")


def numbers(fig: dict) -> dict:
    """Every register number the prose quotes, by key."""
    c, h, s = fig["census"], fig["hut"], fig["special"]
    ms = defaultdict(lambda: {"mean": float("nan"), "max": 0}, {m["m"]: m for m in c["months"]})
    corr = fig["corrections"]
    tot = lambda k: sum(corr.get(k, {}).values())
    pv = fig["pavilions"]
    route = fig["pavilions"]["plague_route_1944"]
    iso = fig["isolation_section"]
    n = {
        "rows": f'{fig["register_rows"]:,}',
        "census-peak": str(c["peak"]["n"]),
        "census-peak-day": dt.date.fromisoformat(c["peak"]["day"]).strftime("%-d %B %Y"),
        "census-nodis": f'{c["left_out_no_discharge"]:,}',
        "census-bad": str(c["left_out_bad_stay"]),
        "c-1944-08": str(round(ms["1944-08"]["mean"])), "c-1944-09": str(round(ms["1944-09"]["mean"])),
        "c-1944-10": str(round(ms["1944-10"]["mean"])),
        "c-1944-max": str(max(ms[k]["max"] for k in ("1944-08", "1944-09", "1944-10"))),
        "c-1946-05": str(round(ms["1946-05"]["mean"])), "c-1946-06": str(round(ms["1946-06"]["mean"])),
        "c-1939-max": str(max(m["max"] for k, m in ms.items() if k.startswith("1939"))),
        "c-1937-mean": str(round(c["yearly"][1937]["mean"])) if 1937 in c["yearly"] else "—",
        "hut-n": str(h["n"]), "hut-first": dt.date.fromisoformat(h["first_after_stray"]).strftime("%-d %B %Y"),
        "hut-last": dt.date.fromisoformat(h["last"]).strftime("%-d %B %Y"),
        "hut-max": str(h["census_max"]), "hut-median": str(h["census_median_aug37_sep38"]),
        "hut-male": str(h["male"]), "hut-female": str(h["female"]), "hut-died": str(h["died"]),
        "hut-strays": ", ".join(dt.date.fromisoformat(d).strftime("%-d %b %Y") for d in h["strays"]) or "none",
        "gyn": f'{tot("gyn"):,}', "inf": f'{tot("inf"):,}', "ven": f'{tot("ven"):,}', "pav": f'{tot("pav"):,}',
        "bs-src": f'{tot("bs_total"):,}', "bs-now": f'{fig["british_section"]:,}',
        "iso-word": f'{fig["isolation_word_only"]:,}', "iso-pav": f'{fig["pavilion_total"]:,}',
        "iso-all": f'{fig["isolation_word_only"] + fig["pavilion_total"]:,}',
        "iso-1939": f'{iso.get(1939, 0):,}',
        "nb24-scan": str(fig["isol_letters"]["scan_lettered"]),
        "nb24-data": str(fig["isol_letters"]["data_lettered"]),
        "nb24-flat": str(fig["isol_letters"]["data_plain_isolation"]),
        "plague-e-after": str(route.get("from 14 Aug|E", 0)),
        "plague-all": str(sum(route.values())),
        "pw-all": str(sum(s["by_year"].get("Prisoners' ward (P.W.)", {}).values())),
        "pw-median": str(s["pw_median_when_occupied"]), "pw-max": str(s["pw_max"]),
        "pmf-all": str(sum(s["by_year"].get("P.M.F.", {}).values())),
        "gmw-all": str(sum(s["by_year"].get("G.M.W. / G.M.F.", {}).values())),
        "nobed-scan": str(len(fig["nobed"]["scan_1944"])),
        "gen-last": dt.date.fromisoformat(fig["gen_med_switch"]["last_general"]).strftime("%-d %B %Y"),
        "med-first": dt.date.fromisoformat(fig["gen_med_switch"]["first_medical"]).strftime("%-d %B %Y"),
        "nobed-data": str(len(fig["nobed"]["data"])),
        "nobed-1944": str(sum(1 for r in fig["nobed"]["data"] if not r["adm"] or r["adm"].startswith("1944"))),
    }
    for p in ("1944", "1946", "1947"):
        for L in "ABCDE":
            d = pv.get(p, {}).get(L)
            if d:
                n[f"pv-{p}-{L.lower()}"] = str(d["n"])
    return n


# -------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--inject", action="store_true", help="rewrite the marked regions of the dossier")
    args = ap.parse_args()
    rows = load()
    fig = compute(rows)
    JSON_OUT.write_text(json.dumps(fig, ensure_ascii=False, indent=1, sort_keys=True, default=str) + "\n",
                        encoding="utf-8")
    c = fig["census"]
    print(f"register rows (no Atlit): {fig['register_rows']:,}")
    print(f"census: peak {c['peak']}, left out {c['left_out_no_discharge']} without discharge, "
          f"{c['left_out_bad_stay']} with an impossible stay; {c['valid_days']} valid days")
    print("census yearly:", {y: v["mean"] for y, v in c["yearly"].items()})
    print(f"Isolation word {fig['isolation_word_only']:,} + pavilions {fig['pavilion_total']:,}; "
          f"by year {dict(sorted(fig['isolation_section'].items()))}")
    print(f"British Section {fig['british_section']:,}")
    print("NB24 letters:", fig["isol_letters"])
    print("hut:", {k: v for k, v in fig["hut"].items() if k not in ("census_days", "monthly")})
    print("corrections:", {k: sum(v.values()) for k, v in fig["corrections"].items()})
    print("plague route 1944:", fig["pavilions"]["plague_route_1944"])
    for p, d in fig["pavilions"].items():
        if p != "plague_route_1944":
            print(p, {k: (v["n"], v["male_pct"], v["child_pct"], v["top"]) for k, v in d.items()})
    print("special:", fig["special"]["by_year"], "PW median/max", fig["special"]["pw_median_when_occupied"],
          fig["special"]["pw_max"])
    print("no bed (scan):", len(fig["nobed"]["scan_1944"]), " (data):", len(fig["nobed"]["data"]))
    print(f"→ {JSON_OUT}")
    if args.inject:
        if not DOSSIER.exists():
            print(f"no dossier at {DOSSIER}", file=sys.stderr)
            return 1
        inject(fig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
