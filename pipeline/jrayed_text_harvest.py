"""Fetch the OCR text of every page in the Jrayed hit lists.

Reads the data/newspapers/*_gov_hospital_haifa*.tsv hit lists produced by
`jrayed.py search`, dedupes the page ids, and fetches each page's OCR text
through the same Chrome/CDP transport (see jrayed.py's docstring), appending

  data/newspapers/page_texts.jsonl    {"id", "date", "pub", "text"} per line

Incremental and resumable: ids already present in the output file are
skipped, so the script can be re-run after any interruption and only does
the remainder. Pages whose fetch fails are recorded with "error" instead of
"text" and retried on the next run.

Run: python3 pipeline/jrayed_text_harvest.py [--delay 1.0]
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jrayed import Client, site, text  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HITS = os.path.join(ROOT, "data", "newspapers")
OUT = os.path.join(HITS, "page_texts.jsonl")


def main() -> None:
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--glob", default="*_gov_hospital_haifa*.tsv",
                    help="hit-list TSVs to read, relative to data/newspapers/")
    ap.add_argument("--site", default="jrayed", choices=["jrayed", "nli"],
                    help="which Veridian front door the hit-list ids belong to")
    ap.add_argument("--out", default=OUT,
                    help="output jsonl (default data/newspapers/page_texts.jsonl)")
    args = ap.parse_args()
    site(args.site)
    OUT = args.out if os.path.isabs(args.out) else os.path.join(HITS, args.out)

    todo: dict[str, dict] = {}
    for path in sorted(glob.glob(os.path.join(HITS, args.glob))):
        with open(path, newline="") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                if row.get("id"):
                    todo[row["id"]] = {"date": row["date"], "pub": row["publication"]}

    done = set()
    if os.path.exists(OUT):
        with open(OUT) as f:
            for line in f:
                rec = json.loads(line)
                if "text" in rec:
                    done.add(rec["id"])
        # errors get retried: rewrite the file without them
        with open(OUT) as f:
            keep = [l for l in f if "error" not in json.loads(l)]
        with open(OUT, "w") as f:
            f.writelines(keep)

    ids = [i for i in sorted(todo) if i not in done]
    print(f"{len(todo)} unique pages, {len(done)} already fetched, {len(ids)} to go",
          flush=True)
    if not ids:
        return

    c = Client(delay=args.delay)
    t0 = time.monotonic()
    with open(OUT, "a") as out:
        for n, pid in enumerate(ids, 1):
            rec = {"id": pid, **todo[pid]}
            try:
                # regex, not an XML parse: Veridian serves the OCR text with
                # unescaped characters that break well-formedness
                body = c.raw({"a": "d", "d": pid, "f": "XML"})
                m = re.search(r"<(?:Page|LogicalSection)TextHTML>(.*?)"
                              r"</(?:Page|LogicalSection)TextHTML>", body, re.S)
                if m is None and "<Error>" in body:
                    raise RuntimeError(re.search(r"<Error>(.*?)</Error>", body, re.S).group(1))
                rec["text"] = m.group(1) if m else ""
            except Exception as e:  # keep going; recorded errors retry next run
                rec["error"] = str(e)[:200]
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            if n % 100 == 0:
                rate = n / (time.monotonic() - t0)
                print(f"{n}/{len(ids)}  ({rate:.1f}/s, ~{(len(ids)-n)/rate/60:.0f} min left)",
                      flush=True)
    errs = sum(1 for line in open(OUT) if "error" in json.loads(line))
    print(f"done: {len(todo) - errs} texts, {errs} errors (re-run to retry)", flush=True)


if __name__ == "__main__":
    main()
