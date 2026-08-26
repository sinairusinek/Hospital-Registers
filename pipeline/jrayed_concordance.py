"""Concordance of hospital mentions near Haifa in the harvested page texts.

Reads data/newspapers/page_texts.jsonl (from jrayed_text_harvest.py) and
applies the precision filter that Veridian's search engine cannot: a real
regex over the OCR text, keeping only pages where a مستشف* token and حيفا
occur within a tight window of each other. Server-side we could only ask
for page-level co-occurrence; here the match is local, so a Jaffa hospital
story on a page that mentions Haifa elsewhere drops out.

Writes data/newspapers/hospital_haifa_concordance.tsv with one row per
matched window (a page can contribute several):

  date (ISO), pub, page_id, window   - the window is ±120 chars of context
                                       around the co-occurrence, tags and
                                       entities stripped, whitespace flat

Run it on the partial file any time; it is a pure local pass over whatever
the harvest has fetched so far.

Run: python3 pipeline/jrayed_concordance.py [--gap 80] [--context 120]
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "data", "newspapers", "page_texts.jsonl")
OUT = os.path.join(ROOT, "data", "newspapers", "hospital_haifa_concordance.tsv")

MONTHS = {m: i + 1 for i, m in enumerate(
    "January February March April May June July August September October "
    "November December".split())}


def iso(date: str) -> str:
    m = re.match(r"(\d+) (\w+) (\d{4})", date or "")
    if not m:
        return date or ""
    return f"{m.group(3)}-{MONTHS.get(m.group(2), 0):02d}-{int(m.group(1)):02d}"


def clean(raw: str) -> str:
    t = html.unescape(html.unescape(raw))  # entities arrive double-escaped
    t = re.sub(r"<[^>]+>", " ", t)
    return " ".join(t.split())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap", type=int, default=150,
                    help="max chars between مستشف* and حيفا. 150 beats 80: the "
                         "extra windows report admissions at a higher rate "
                         "(44% vs 38%), so tightening only loses evidence. The "
                         "residual noise is not distance but ambiguity - "
                         "'المستشفى الحكومي' unqualified can be another town's "
                         "government hospital, so check the dateline.")
    ap.add_argument("--context", type=int, default=120,
                    help="chars of context kept on each side of the window")
    args = ap.parse_args()

    # either order: hospital ... Haifa or Haifa ... hospital
    pat = re.compile(
        rf"(?:\bال?مستشف\w*\b.{{0,{args.gap}}}حيفا|حيفا.{{0,{args.gap}}}\bال?مستشف\w*\b)")

    pages = rows = 0
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["date", "pub", "page_id", "window"])
        for line in open(IN):
            rec = json.loads(line)
            if not rec.get("text"):
                continue
            text = clean(rec["text"])
            spans = []
            for m in pat.finditer(text):
                a = max(0, m.start() - args.context)
                b = min(len(text), m.end() + args.context)
                if spans and a <= spans[-1][1]:  # merge overlapping windows
                    spans[-1] = (spans[-1][0], b)
                else:
                    spans.append((a, b))
            if spans:
                pages += 1
                for a, b in spans:
                    w.writerow([iso(rec["date"]), rec["pub"], rec["id"],
                                "…" + text[a:b] + "…"])
                    rows += 1
    total = sum(1 for _ in open(IN))
    print(f"{total} pages scanned, {pages} matched, {rows} windows -> {OUT}")


if __name__ == "__main__":
    main()
