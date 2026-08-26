"""Match press reports of Haifa hospital admissions to register rows.

Takes the concordance windows (jrayed_concordance.py) and asks, for each
window that actually reports someone being taken to hospital, whether the
register holds an admission that could be the same event.

The link is necessarily circumstantial - the registers carry no names in
the public dataset, and the press rarely gives an admission date - so this
produces *candidates*, not identifications. What makes a candidate worth a
historian's eye is the conjunction: an injury admission, in the right few
days, of the right sex, with an outcome consistent with what the paper
reported.

Method:

  1. Keep only windows whose text reports a transfer to hospital
     (نقل/ادخل/اسعف الى المستشفى ...) rather than a mention in passing
     (a hospital's budget, an appointment, an advertisement).
  2. Read what the report says about the case: cause (traffic, gunfire,
     stabbing, drowning, fall, burn, explosion), whether the victim died,
     and sex where the wording gives it away.
  3. Date the event. The issue date is the upper bound; Arabic time adverbs
     ("امس" yesterday, "امس الاول" the day before) shift it back, otherwise
     a 4-day window absorbs the reporting lag.
  4. Search the register for admissions in that window whose diagnosis is
     in the injury/poisoning chapter (800-999, or E800-E999), and score
     each by sex agreement, outcome agreement, and cause-specific
     diagnosis keywords (fracture, wound, burn, drowning ...).

Notebook 25 is the Atlit camp register and is excluded, as everywhere else.

Writes data/newspapers/press_register_candidates.tsv, one row per
(report, candidate admission) pair, best first within each report:

  press_date, pub, page_id, cause, died, sex_hint, report
  adm_date, notebook, page, age, sex, religion, city, diagnosis, result,
  score, why

Run: python3 pipeline/press_register_match.py [--window 4] [--min-score 2]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONC = os.path.join(ROOT, "data", "newspapers", "hospital_haifa_concordance.tsv")
REG = os.path.join(ROOT, "data", "public", "hospital-registers-normalized.tsv")
OUT = os.path.join(ROOT, "data", "newspapers", "press_register_candidates.tsv")

# A report of someone being taken to hospital, not a passing mention.
ADMITTED = re.compile(
    r"(نقل\w*|أ?ادخل\w*|اسعف\w*|أ?سعف\w*|حمل\w*|أ?رسل\w*)"
    r"[^.]{0,40}(الى|إلى)\s+(ال)?مستشف")

# cause -> (press keywords, register diagnosis keywords)
CAUSES = {
    "traffic": (r"(سيارة|السيارة|سيارات|شاحنة|دهس|صدم|اصطدم|انقلب|قطار|دراجة)",
                r"(fracture|contusion|wound|injur|crush|concussion|laceration)"),
    "gunfire": (r"(رصاص|اطلاق النار|إطلاق النار|بندقية|مسدس|اطلق عليه|أطلق عليه)",
                r"(gunshot|bullet|wound|fracture|penetrat)"),
    "stabbing": (r"(طعن|سكين|خنجر|موسى|جرح\w* بآلة)",
                 r"(stab|wound|incis|laceration|cut)"),
    "drowning": (r"(غرق|الغرق|البحر|النهر)", r"(drown|asphyx|submers)"),
    "fall": (r"(سقط|وقع من|هوى من|انهار)",
             r"(fracture|contusion|concussion|fall|injur|dislocat)"),
    "burn": (r"(حريق|احترق|النار|لهب|كاز)", r"(burn|scald)"),
    "explosion": (r"(قنبلة|انفجار|لغم|متفجر)",
                  r"(blast|explos|wound|fracture|burn|injur)"),
    "assault": (r"(اعتدى|ضرب\w*|مشاجرة|عراك|هجم)",
                r"(contusion|wound|fracture|injur)"),
}
DIED = re.compile(r"(توفي|توفى|مات\b|وفاة|قتل\b|قتيل|الجثة|الجنة|فارق الحياة|نفسه الاخير)")
FEMALE = re.compile(r"(امرأة|إمرأة|سيدة|فتاة|زوجة|والدتها|ابنتها|طفلة|السيدة|الفتاة)")
MALE = re.compile(r"(رجل|شاب|فتى|السيد|الشيخ|طفل\b|ولد\b|سائق|عامل|شرطي|بوليس)")
YESTERDAY = re.compile(r"امس الاول|أمس الأول|امس اﻻول")
TODAY_YEST = re.compile(r"\bامس\b|\bأمس\b")

INJURY_CH = ("800-999", "E800-E999")


def parse_date(s: str):
    try:
        return dt.date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=4,
                    help="days before the issue date to search")
    ap.add_argument("--min-score", type=int, default=2)
    ap.add_argument("--max-candidates", type=int, default=5,
                    help="candidates kept per report")
    args = ap.parse_args()

    # register: injury admissions only, indexed by date
    by_date: dict[dt.date, list[dict]] = {}
    kept = 0
    with open(REG, newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["Notebook_Number"] == "25":  # Atlit camp register
                continue
            if not any(r["ICD-9 Chapter"].startswith(c) for c in INJURY_CH):
                continue
            d = parse_date(r["Admission Date"])
            if d is None:
                continue
            by_date.setdefault(d, []).append(r)
            kept += 1
    print(f"{kept} injury admissions indexed "
          f"({min(by_date)} .. {max(by_date)})", file=sys.stderr)

    reports = pairs = 0
    with open(CONC, newline="") as f, open(OUT, "w", newline="") as g:
        w = csv.writer(g, delimiter="\t")
        w.writerow(["press_date", "pub", "page_id", "cause", "died", "sex_hint",
                    "report", "adm_date", "notebook", "page", "age", "sex",
                    "religion", "city", "diagnosis", "result", "score", "why"])

        for row in csv.DictReader(f, delimiter="\t"):
            win = row["window"]
            if not ADMITTED.search(win):
                continue
            press_date = parse_date(row["date"])
            if press_date is None:
                continue

            causes = [c for c, (kw, _) in CAUSES.items() if re.search(kw, win)]
            died = bool(DIED.search(win))
            sex_hint = ("F" if FEMALE.search(win) else
                        "M" if MALE.search(win) else "")

            # date span: adverbs pin it, otherwise absorb the reporting lag
            if YESTERDAY.search(win):
                lo = hi = press_date - dt.timedelta(days=2)
            elif TODAY_YEST.search(win):
                lo, hi = press_date - dt.timedelta(days=2), press_date - dt.timedelta(days=1)
            else:
                lo, hi = press_date - dt.timedelta(days=args.window), press_date
            lo -= dt.timedelta(days=1)  # admission may precede the event date
            hi += dt.timedelta(days=1)

            scored = []
            d = lo
            while d <= hi:
                for r in by_date.get(d, []):
                    score, why = 0, []
                    diag = (r["Diagnosis as standardized"] or
                            r["Diagnosis as written"] or "").lower()
                    for c in causes:
                        if re.search(CAUSES[c][1], diag):
                            score += 2
                            why.append(f"diagnosis fits {c}")
                            break
                    if sex_hint and r["Sex"]:
                        if r["Sex"].upper().startswith(sex_hint):
                            score += 1
                            why.append("sex agrees")
                        else:
                            score -= 2
                            why.append("sex conflicts")
                    if died:
                        if r["Result"] == "Died":
                            score += 3
                            why.append("died, as reported")
                        elif r["Result"]:
                            score -= 2
                            why.append("survived, but report says died")
                    if (r["City"] or "").strip() in ("Haifa", "חיפה", "حيفا"):
                        score += 1
                        why.append("Haifa resident")
                    if d == press_date or d == press_date - dt.timedelta(days=1):
                        score += 1
                        why.append("admitted on/just before publication")
                    scored.append((score, r, d, "; ".join(why)))
                d += dt.timedelta(days=1)

            scored = [s for s in scored if s[0] >= args.min_score]
            scored.sort(key=lambda s: -s[0])
            if not scored:
                continue
            reports += 1
            for score, r, d, why in scored[:args.max_candidates]:
                w.writerow([
                    row["date"], row["pub"], row["page_id"],
                    "/".join(causes), "yes" if died else "", sex_hint,
                    win[:300], d.isoformat(), r["Notebook_Number"],
                    r["Page_Number"], r["Age"], r["Sex"], r["Religion"],
                    r["City"], r["Diagnosis as standardized"] or r["Diagnosis as written"],
                    r["Result"], score, why,
                ])
                pairs += 1

    print(f"{reports} reports with candidates, {pairs} pairs -> {OUT}")


if __name__ == "__main__":
    main()
