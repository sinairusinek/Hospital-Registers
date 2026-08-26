"""Fetch whole articles, with their headlines, for the casualty days.

The concordance works on page text and returns character windows, which cut
reports off mid-sentence and carry no headline. But Filastin and al-Difa' are
segmented into logical sections in the archive, each with its own title, so a
report can be retrieved as the article it actually was.

For every day in casualty_spikes.tsv this searches the following days'
issues for sections mentioning the hospital, then fetches each section's
headline and full text.

Writes data/newspapers/articles.jsonl:
  {spike, id, date, pub, title, type, words, text}

Run: python3 pipeline/jrayed_articles.py [--days 4]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jrayed import Client, text as tx  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPIKES = os.path.join(ROOT, "data", "newspapers", "casualty_spikes.tsv")
OUT = os.path.join(ROOT, "data", "newspapers", "articles.jsonl")

HOSPITAL = "مستشفى"


def clean(raw: str) -> str:
    t = html.unescape(html.unescape(raw or ""))
    t = re.sub(r"<[^>]+>", " ", t)
    return " ".join(t.split())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=4,
                    help="days after the spike to search")
    args = ap.parse_args()

    spikes = [r["date"] for r in
              csv.DictReader(open(SPIKES, newline=""), delimiter="\t")]
    c = Client(delay=1.0)
    seen = set()
    n = 0
    with open(OUT, "w") as out:
        for s in spikes:
            d0 = dt.date.fromisoformat(s)
            for pub in ("falastin", "difaa"):
                for k in range(0, args.days + 1):
                    d = d0 + dt.timedelta(days=k)
                    params = {
                        "a": "q", "leq": "Logical", "txq": HOSPITAL,
                        "puq": pub, "ssnip": "", "o": "100", "r": "1",
                        "dafdq": str(d.day), "dafmq": str(d.month),
                        "dafyq": str(d.year), "datdq": str(d.day),
                        "datmq": str(d.month), "datyq": str(d.year),
                    }
                    try:
                        block = c.xml(params)
                    except Exception as e:
                        print(f"  {d} {pub}: {e}", file=sys.stderr)
                        continue
                    for hit in block.iter("LogicalSection"):
                        meta = hit.find("LogicalSectionMetadata")
                        sid = tx(meta, "LogicalSectionID")
                        if not sid or sid in seen:
                            continue
                        seen.add(sid)
                        try:
                            body = c.raw({"a": "d", "d": sid, "f": "XML"})
                        except Exception as e:
                            print(f"  {sid}: {e}", file=sys.stderr)
                            continue
                        m = re.search(
                            r"<LogicalSectionTextHTML>(.*?)</LogicalSectionTextHTML>",
                            body, re.S)
                        article = clean(m.group(1)) if m else ""
                        if HOSPITAL not in article:
                            continue
                        rec = {
                            "spike": s, "id": sid, "date": d.isoformat(),
                            "pub": pub, "title": tx(meta, "LogicalSectionTitle"),
                            "type": tx(meta, "LogicalSectionType"),
                            "words": len(article.split()), "text": article,
                        }
                        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        out.flush()
                        n += 1
            print(f"{s}: {n} articles so far", flush=True)
    print(f"{n} articles -> {OUT}")


if __name__ == "__main__":
    main()
