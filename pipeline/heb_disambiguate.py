"""Which town's government hospital is each Hebrew page talking about?

Stage 1 could only ask for page-level co-occurrence, so heb_qualified_union
.tsv holds 1,175 pages that name *a* government hospital somewhere and may or
may not mean Haifa's. The Arabic README states the hazard plainly - Jaffa,
Hebron and Jerusalem all had one - and it applies identically in Hebrew.

This is the local pass the search engine cannot do. For every page it finds
each hospital mention, looks at the ±GAP characters around it, and asks which
town names appear in that window. A page is:

  haifa        every hospital mention that names a town names Haifa
  other        every such mention names some other town
  mixed        both occur - a digest page, or a comparison; needs a human
  untowned     hospital mentions carry no town in range at all

"untowned" is not noise to be discarded. A Haifa paper reporting its own
hospital has no reason to name the town, so this bucket holds both the local
coverage we most want and other towns' stories that happen to be qualified.
The publication's own city is the lead worth following there, not a verdict.

Writes data/newspapers/heb_town_disambiguation.tsv, one row per page.

Run: python3 pipeline/heb_disambiguate.py [--gap 150]
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS = os.path.join(ROOT, "data", "newspapers")
IN = os.path.join(NEWS, "heb_page_texts.jsonl")
UNION = os.path.join(NEWS, "heb_qualified_union.tsv")
OUT = os.path.join(NEWS, "heb_town_disambiguation.tsv")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jrayed_concordance import TERMS  # noqa: E402

# One definition of "a hospital in Hebrew", shared with the concordance. An
# earlier version of this file kept its own copy and the two drifted within the
# hour, which is exactly how a filter starts quietly disagreeing with itself.
HOSP = re.compile(TERMS["he"][0])

# Every Mandate town with a government hospital, plus the two big cities whose
# names crowd these pages. Prefixes attach, so none of these is anchored.
TOWNS = {
    "haifa":     r"ח[יו]פה",
    "jaffa":     r"יפו",
    "jerusalem": r"ירושל[יא]ם",
    "telaviv":   r"תל[\s־\-]?אביב",
    "safed":     r"צפת",
    "tiberias":  r"טבריה",
    "acre":      r"עכו",
    "nablus":    r"שכם",
    "gaza":      r"עזה",
    "hebron":    r"חברון",
    "nazareth":  r"נצרת",
    "ramleh":    r"רמלה",
}
TOWN_RE = {k: re.compile(v) for k, v in TOWNS.items()}

# Haifa's other hospitals. A page naming one of these is not disqualified -
# papers list several in a single notice - but it is flagged, because the
# abbreviation ביה"ח belongs to all of them equally.
RIVALS = {
    "hadassah":   r"הדסה",
    "rothschild": r"רוטשילד|רוטשלד",
    "elisha":     r"אליישע|אלישע",
    "english":    r"האנגלי",
}
RIVAL_RE = {k: re.compile(v) for k, v in RIVALS.items()}

MONTHS = {m: i + 1 for i, m in enumerate(
    "January February March April May June July August September October "
    "November December".split())}


def iso(date: str) -> str:
    m = re.match(r"(\d+) (\w+) (\d{4})", date or "")
    return (f"{m.group(3)}-{MONTHS.get(m.group(2), 0):02d}-{int(m.group(1)):02d}"
            if m else (date or ""))


def clean(raw: str) -> str:
    t = html.unescape(html.unescape(raw))
    t = re.sub(r"<[^>]+>", " ", t)
    return " ".join(t.split())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap", type=int, default=150,
                    help="chars each side of a hospital mention to search for "
                         "a town name (default 150, matching the Arabic pass)")
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--out", dest="dst", default=OUT)
    args = ap.parse_args()
    src = args.src if os.path.sep in args.src else os.path.join(NEWS, args.src)
    dst = args.dst if os.path.sep in args.dst else os.path.join(NEWS, args.dst)

    forms = {}
    if os.path.exists(UNION):
        with open(UNION, newline="") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                forms[row["id"]] = row.get("forms", "")

    verdicts: dict[str, int] = {}
    rows = []
    scanned = empty = 0
    for line in open(src):
        rec = json.loads(line)
        scanned += 1
        if not rec.get("text"):
            empty += 1
            continue
        text = clean(rec["text"])
        near: set[str] = set()
        mentions = 0
        page_rivals: set[str] = set()
        for m in HOSP.finditer(text):
            mentions += 1
            a, b = max(0, m.start() - args.gap), min(len(text), m.end() + args.gap)
            window = text[a:b]
            for town, rx in TOWN_RE.items():
                if rx.search(window):
                    near.add(town)
            # Rivals are judged in the same window as towns, never page-wide.
            # A Mandate newspaper page carries a dozen unrelated articles, so
            # "Hadassah appears somewhere on this page" is true of most of them
            # and means nothing; what matters is Hadassah appearing beside this
            # hospital mention.
            for rival, rx in RIVAL_RE.items():
                if rx.search(window):
                    page_rivals.add(rival)
        if not mentions:
            verdict = "no_hospital_term"
        elif not near:
            verdict = "untowned"
        elif near == {"haifa"}:
            verdict = "haifa"
        elif "haifa" in near:
            verdict = "mixed"
        else:
            verdict = "other"
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
        rows.append([iso(rec.get("date", "")), rec.get("pub", ""), rec["id"],
                     verdict, mentions, ",".join(sorted(near)),
                     ",".join(sorted(page_rivals)), forms.get(rec["id"], "")])

    rows.sort(key=lambda r: (r[0], r[2]))
    with open(dst, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["date", "pub", "page_id", "verdict", "hospital_mentions",
                    "towns_in_range", "other_haifa_hospitals", "found_by"])
        w.writerows(rows)

    print(f"{scanned:,d} pages scanned ({empty} with no text) -> {dst}")
    print("\nverdict:")
    for k, v in sorted(verdicts.items(), key=lambda x: -x[1]):
        print(f"  {v:5,d}  {k}")

    untowned_by_pub: dict[str, int] = {}
    for r in rows:
        if r[3] == "untowned":
            untowned_by_pub[r[1]] = untowned_by_pub.get(r[1], 0) + 1
    if untowned_by_pub:
        print("\nuntowned pages by publication (top 10) — the paper's own city "
              "is the lead:")
        for k, v in sorted(untowned_by_pub.items(), key=lambda x: -x[1])[:10]:
            print(f"  {v:5,d}  {k}")

    flagged = sum(1 for r in rows if r[6])
    print(f"\npages where another Haifa hospital sits inside a hospital "
          f"window: {flagged:,d}")

    # "mixed" is not a failure of the method, it is the shape of a newspaper
    # page: several unrelated articles, each with its own town. Report how many
    # of those pages carry a Haifa-only mention somewhere, since those are the
    # ones a human pass can still rescue.
    mixed = [r for r in rows if r[3] == "mixed"]
    if mixed:
        print(f"of {len(mixed):,d} mixed pages, {sum(1 for r in mixed if r[4] > 1):,d} "
              f"carry more than one hospital mention - i.e. the towns most "
              f"likely belong to different articles on the same page")


if __name__ == "__main__":
    main()
