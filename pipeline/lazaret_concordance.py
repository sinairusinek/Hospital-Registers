"""Concordance of the quarantine institutions that stood beside the hospital.

The epidemic concordance left one question open and could not close it. For the
quarantinable diseases — cholera, plague, smallpox — a press report with no
matching admission has three readings the corpus cannot separate: the case was
admitted somewhere these notebooks do not cover, or it is in them under
something the ICD-9 match does not reach, or there was no case. Haifa had a
lazaret, and suspected cases went to it.

This script assembles the evidence for the first reading so that the archival
document expected from the Israel State Archives lands on a prepared file. It
does not settle anything and is not meant to: it is a finding aid, and every
row is a lead.

It reads the Arabic corpus (page_texts.jsonl) and the English one
(govhosp_texts.jsonl, stluke_page_texts.jsonl, mountainroad_texts.jsonl) and
writes data/newspapers/lazaret_concordance.tsv.

Four institution kinds are distinguished, because the sources do:

  kerentina           الكرنتينا, the lazaret proper; English lazaret/karantina
  quarantine_station  المحجر الصحي, the quarantine station
  infectious_hospital مستشفى الأمراض المعدية / السارية; infectious diseases
                      hospital, section, pavilion
  isolation           مستشفى / دار / جناح / قسم العزل; isolation hospital, ward

The distinction matters. Filastin of 11 September 1941 has one medical officer
supervising مستشفى الحكومة ودوائر الصحة والكرنتينا as three separate things,
while al-Difa' of 22 August 1946 puts sick detainees
الى الكرنتينا في مستشفى الحكومة بحيفا — the Kerentina inside the Government
Hospital. Whether the lazaret was a department of the hospital or an
institution beside it is exactly what is unresolved, so the vocabulary is kept
apart rather than merged.

A `place` column captures the qualifier that follows the term, because most
hits are not Haifa's: محجر الطور is the Egyptian hajj quarantine at El-Tor,
الكرنتينا بيافا is Jaffa's, محجر عتليت is the Atlit detention camp. Haifa is
graded by dateline exactly as in epidemic_concordance.py, whose paragraph and
dateline machinery this imports rather than repeats.

Generic العزل is not matched. On its own the word is "separation" —
عزلة تامة, بمعزل عن — and only the institutional compounds are taken.

Run: python3 pipeline/lazaret_concordance.py [--context 150]
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from epidemic_concordance import (  # noqa: E402
    AR, CORRESPONDENT, DATELINE, DISEASES, HAIFA, PREFIX, TOWNS,
    iso, normalise, section_towns,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS = os.path.join(ROOT, "data", "newspapers")
OUT = os.path.join(NEWS, "lazaret_concordance.tsv")

ARABIC_SOURCES = ["page_texts.jsonl"]
ENGLISH_SOURCES = ["govhosp_texts.jsonl", "stluke_page_texts.jsonl",
                   "mountainroad_texts.jsonl"]

# kind -> stem alternation, matched against normalised Arabic
AR_KINDS = {
    "kerentina": r"(?:كرنتين\w*|كرانتين\w*|قرنطين\w*|قرنتين\w*|كوارنتين\w*)",
    # محجر is also "quarry", and the Shafa'amr land-sale notices, the Sadiq
    # quarry strike and the Suba quarry bus are all in this corpus. So the
    # station is matched only where the text qualifies it: صحي, or one of the
    # two stations the papers name outright — El-Tor, the Egyptian hajj
    # quarantine, and Atlit, where immigrants were held. Bare محجر is dropped.
    "quarantine_station": r"(?:محجر\s+(?:ال)?صحي|حجر\s+(?:ال)?صحي|"
                          r"محجر\s+(?:الطور|عتليت))",
    "infectious_hospital": r"مستشفي\s+(?:\S+\s+){0,2}?(?:ال)?امراض\s+"
                           r"(?:ال)?(?:معديه|ساريه)",
    "isolation": r"(?:مستشفي|دار|جناح|قسم|غرفه|مركز)\s+(?:ال)?عزل",
}
EN_KINDS = {
    "kerentina": r"lazaret\w*|kerentina|karantina|quarantine\s+station",
    "quarantine_station": r"quarantine",
    "infectious_hospital": r"infectious\s+diseases?\s+"
                           r"(?:hospital|section|pavill?ion|accommodation|ward)",
    "isolation": r"isolation\s+(?:hospital|section|ward|camp|block|pavill?ion)",
}

# what follows the term and tells you whose it is: بيافا, في حيفا, الطور, عتليت
AR_PLACE = re.compile(
    rf"\A\s*(?:في|ب|ال)?\s*({'|'.join(sorted(map(re.escape, TOWNS), key=len, reverse=True))}"
    rf"|الطور|عتليت|صوبا|الصادق)")
EN_PLACE = re.compile(r"\A\s*(?:at|in|of)\s+([A-Z][a-z]+)")

# a person being sent there, as against the institution merely named
AR_TRANSFER = re.compile(
    rf"(?:نقل\w*|ادخل\w*|ارسل\w*|حجز\w*|اودع\w*|سيق\w*|عزل\w*)"
    rf"[^.]{{0,60}}(?:الي|ل){PREFIX}?(?:كرنتين|محجر|مستشفي|عزل)")
EN_TRANSFER = re.compile(
    r"(?i)\b(?:removed|taken|transferred|sent|admitted|conveyed|detained|"
    r"isolated)\b[^.]{0,60}\b(?:to|in)\b[^.]{0,30}"
    r"(?:quarantine|lazaret|isolation|infectious)")

# generic Arabic isolation words that must not become institution hits
AR_NOT_PLACE = re.compile(r"\A\s*(?:تام|عن|من)")


def clean_english(raw: str) -> list[str]:
    t = html.unescape(html.unescape(raw))
    out = []
    for p in re.split(r"</p\s*>|<br\s*/?>", t):
        p = " ".join(re.sub(r"<[^>]+>", " ", p).split())
        if p:
            out.append(p)
    return out


def en_dateline(para: str) -> str:
    """Palestine Post datelines read HAIFA, Thursday. — town, then a weekday."""
    m = re.match(r"\s*([A-Z][A-Za-z' -]{2,20}?)\s*,\s*"
                 r"(?:Sun|Mon|Tues|Wednes|Thurs|Fri|Satur)day", para)
    if m:
        return m.group(1).strip().title()
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context", type=int, default=150,
                    help="chars of context each side, as in the epidemic pass")
    ap.add_argument("--lookback", type=int, default=2)
    args = ap.parse_args()

    ar_pats = {k: re.compile(rf"(?<![{AR}]){PREFIX}{stem}")
               for k, stem in AR_KINDS.items()}
    en_pats = {k: re.compile(rf"(?i)\b(?:{stem})\b") for k, stem in EN_KINDS.items()}
    ar_disease = {d: re.compile(rf"(?<![{AR}]){PREFIX}{stem}")
                  for d, stem in DISEASES.items()}
    en_disease = {
        "typhoid": r"typhoid|enteric", "typhus": r"typhus", "malaria": r"malaria",
        "smallpox": r"small.?pox|variola", "cholera": r"cholera",
        "diphtheria": r"diphther", "measles": r"measles",
        "dysentery": r"dysenter", "trachoma": r"trachoma", "plague": r"plague",
        "influenza": r"influenza|grippe",
    }
    en_disease = {d: re.compile(rf"(?i)\b(?:{p})", ) for d, p in en_disease.items()}

    rows = 0
    kinds: dict[str, int] = {}
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["date", "pub", "lang", "page_id", "kind", "term", "place",
                    "haifa", "dateline", "diseases", "transfer", "window"])

        for source, lang in ([(s, "ar") for s in ARABIC_SOURCES] +
                             [(s, "en") for s in ENGLISH_SOURCES]):
            path = os.path.join(NEWS, source)
            if not os.path.exists(path):
                print(f"  (missing, skipped) {source}", file=sys.stderr)
                continue
            pats = ar_pats if lang == "ar" else en_pats
            dis = ar_disease if lang == "ar" else en_disease
            transfer = AR_TRANSFER if lang == "ar" else EN_TRANSFER
            for line in open(path):
                rec = json.loads(line)
                if not rec.get("text"):
                    continue
                paras = (normalise(rec["text"]) if lang == "ar"
                         else clean_english(rec["text"]))
                sections = section_towns(paras) if lang == "ar" else [""] * len(paras)
                page_haifa = any(
                    (HAIFA.search(p) if lang == "ar" else "haifa" in p.lower())
                    for p in paras)

                for i, para in enumerate(paras):
                    town = ""
                    for j in range(i, max(-1, i - args.lookback - 1), -1):
                        if lang == "ar":
                            m = (DATELINE.search(paras[j][:160])
                                 or CORRESPONDENT.search(paras[j]))
                            if m:
                                key = m.group(1)
                                town = TOWNS.get(key) or TOWNS.get(key.lstrip("وفبلك"), "")
                                break
                        else:
                            t = en_dateline(paras[j])
                            if t:
                                town = t
                                break
                    if not town:
                        town = sections[i]

                    spans = []
                    for kind, pat in pats.items():
                        for m in pat.finditer(para):
                            spans.append((m.start(), m.end(), kind, m.group(0)))
                    if not spans:
                        continue
                    spans.sort()
                    # the more specific kind wins where two patterns overlap
                    # (quarantine_station's محجر sits inside nothing, but the
                    #  English "quarantine" is a substring of "quarantine
                    #  station", which is the lazaret)
                    kept = []
                    for s in spans:
                        if kept and s[0] < kept[-1][1]:
                            if (s[1] - s[0]) > (kept[-1][1] - kept[-1][0]):
                                kept[-1] = s
                            continue
                        kept.append(s)

                    for start, end, kind, term in kept:
                        tail = para[end:end + 30]
                        if lang == "ar" and AR_NOT_PLACE.match(tail):
                            continue
                        pm = (AR_PLACE.match(tail) if lang == "ar"
                              else EN_PLACE.match(tail))
                        place = pm.group(1) if pm else ""
                        if lang == "ar" and place:
                            place = TOWNS.get(place, place)
                        a = max(0, start - args.context)
                        b = min(len(para), end + args.context)
                        win = para[a:b]
                        if town == "Haifa":
                            haifa = "dateline"
                        elif town:
                            haifa = f"other:{town}"
                        elif (HAIFA.search(win) if lang == "ar"
                              else "haifa" in win.lower()):
                            haifa = "window"
                        elif (HAIFA.search(para) if lang == "ar"
                              else "haifa" in para.lower()):
                            haifa = "paragraph"
                        elif page_haifa:
                            haifa = "page"
                        else:
                            haifa = "none"
                        named = [d for d, p in dis.items() if p.search(win)]
                        w.writerow([
                            iso(rec["date"]), rec["pub"], lang, rec["id"], kind,
                            term, place, haifa, town, "|".join(sorted(named)),
                            "y" if transfer.search(win) else "",
                            "…" + win + "…",
                        ])
                        rows += 1
                        kinds[kind] = kinds.get(kind, 0) + 1

    print(f"{rows} windows -> {OUT}")
    for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print(f"  {k:20} {n}")


if __name__ == "__main__":
    main()
