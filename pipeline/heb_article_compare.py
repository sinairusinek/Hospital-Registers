"""Article-level against page-level: what changing the unit actually did.

Stage 2 filtered pages by proximity - a hospital mention within 150 characters
of the word Haifa - because a Mandate newspaper page carries a dozen unrelated
articles and page-level co-occurrence proves nothing. Stage 3 asked the same
questions at --level Logical, where the engine enforces the article boundary
itself, and this script measures the difference.

Two units are being compared, so nothing here is a correction to anything.
The page-level figures (694 / 878 / 475) stay the ones comparable to the
Arabic 2,322 and 1,593. These are a separate column.

The comparison is made at *issue* level (dav19380417-01), because a page id
and an article id share only that prefix - an article id carries no page
number, so the two sets cannot be joined any finer.

Three questions, in order:

  1. Does article scoping change what the single-phrase queries find?
     (No: a phrase never straddles an article boundary.)
  2. What does it discard from the two-term AND queries?
     (Two thirds of their issues - the cross-article contamination.)
  3. Where does it recover material page-level stage 2 lost, and where does
     it lose material page scoping caught?

For question 3 the adjudicator is *nearest town to a hospital mention*,
measured across the whole article rather than in a fixed window. The window
is what missed these articles in the first place, so re-using it to judge
them would only confirm its own verdict.

Run: python3 pipeline/heb_article_compare.py
"""

from __future__ import annotations

import csv
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS = os.path.join(ROOT, "data", "newspapers")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jrayed_concordance import TERMS  # noqa: E402
from heb_disambiguate import TOWN_RE  # noqa: E402

HOSP = re.compile(TERMS["he"][0])
HAIFA = re.compile(TERMS["he"][1])
GAP = 150  # the stage-2 window, repeated here so the two are comparable

# Each page-level harvest beside its --level Logical twin. The first three
# rows are single phrases; the last two are phrase-AND-token, which is where
# the article boundary can bite.
PAIRS = [
    ('"בית החולים הממשלתי"',   "heb_govhosp_phrase.tsv",     "heb_art_govhosp.tsv"),
    ('"ביה״ח הממשלתי"',        "heb_abbrev_phrase.tsv",      "heb_art_abbrev.tsv"),
    ('"בית־החולים הממשלתי"',   "heb_maqaf.tsv",              "heb_art_maqaf.tsv"),
    ('"בית חולים ממשלתי"',     "heb_indef.tsv",              "heb_art_indef.tsv"),
    ('"בי״ח הממשלתי"',         "heb_abbrev_short.tsv",       "heb_art_abbrev_short.tsv"),
    ("ביה״ח בחיפה",            "heb_abbrev_haifa_broad.tsv", "heb_art_abbrev_haifa.tsv"),
    ('"בית החולים" בחיפה',     "heb_unqualified.tsv",        "heb_art_unqualified.tsv"),
]


def rows(name: str) -> list[dict]:
    with open(os.path.join(NEWS, name), newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def ids(name: str) -> set[str]:
    return {r["id"] for r in rows(name) if r.get("id")}


def issues(s) -> set[str]:
    """dav19380417-01.2.7 and dav19380417-01.1.4 are one issue."""
    return {i.split(".")[0] for i in s}


def clean(raw: str) -> str:
    t = html.unescape(html.unescape(raw))
    return " ".join(re.sub(r"<[^>]+>", " ", t).split())


def main() -> None:
    print("=" * 72)
    print("1. the same query, both units (issue level)")
    print("=" * 72)
    print(f"{'query':26s} {'pages':>7s} {'arts':>7s} {'p-iss':>7s} {'a-iss':>7s} "
          f"{'page-only':>10s} {'art-only':>9s}")
    for q, pg, ar in PAIRS:
        P, A = ids(pg), ids(ar)
        pi, ai = issues(P), issues(A)
        print(f"{q:26s} {len(P):7d} {len(A):7d} {len(pi):7d} {len(ai):7d} "
              f"{len(pi - ai):10d} {len(ai - pi):9d}")

    texts = {}
    with open(os.path.join(NEWS, "heb_article_texts.jsonl")) as f:
        for line in f:
            rec = json.loads(line)
            texts[rec["id"]] = clean(rec.get("text") or "")

    qual = ids("heb_art_qualified_union.tsv")
    s2 = {r["page_id"] for r in rows("heb_concordance.tsv")}
    s2i = issues(s2)

    # An article naming both terms anywhere inside itself is the article-level
    # analogue of a page that survived the proximity filter: in both cases one
    # piece of writing has been shown to hold the hospital and the town.
    keep = {i for i in qual
            if HOSP.search(texts.get(i, "")) and HAIFA.search(texts.get(i, ""))}
    anykeep = {i for i, t in texts.items() if HOSP.search(t) and HAIFA.search(t)}
    K = issues(keep)

    print()
    print("=" * 72)
    print("2. the qualified union, page-filtered against article-scoped")
    print("=" * 72)
    print(f"  qualified union          {len(qual):5d} articles  {len(issues(qual)):5d} issues")
    print(f"    naming Haifa in-article{len(keep):5d} articles  {len(K):5d} issues")
    print(f"  page-level stage 2       {len(s2):5d} pages     {len(s2i):5d} issues")
    print(f"    in both                {len(K & s2i):5d} issues")
    print(f"    article-only (gained)  {len(K - s2i):5d} issues")
    print(f"    page-only (lost)       {len(s2i - K):5d} issues, of which "
          f"{len(s2i - issues(anykeep))} appear in no harvested article at all")

    print()
    print("=" * 72)
    print("3. how far apart the two terms sit, and who that leaves nearest")
    print("=" * 72)
    print("  Beyond the 150-character window the article boundary is the only")
    print("  evidence, so the nearest town is measured article-wide instead.")
    print()
    buckets: dict[tuple, dict] = {}
    for i in qual:
        t = texts.get(i, "")
        hosp = [m.start() for m in HOSP.finditer(t)]
        if not hosp:
            continue
        pos = {k: [m.start() for m in rx.finditer(t)] for k, rx in TOWN_RE.items()}
        if not pos.get("haifa"):
            continue
        gap = min(abs(a - b) for a in hosp for b in pos["haifa"])
        nearest = min(((abs(p - h), town)
                       for h in hosp for town, ps in pos.items() for p in ps),
                      key=lambda x: x[0])[1]
        key = ("within" if gap < GAP else "beyond",
               "new" if i.split(".")[0] not in s2i else "seen")
        buckets.setdefault(key, {}).setdefault(nearest, 0)
        buckets[key][nearest] += 1

    for key in sorted(buckets):
        tot = sum(buckets[key].values())
        top = sorted(buckets[key].items(), key=lambda x: -x[1])[:5]
        label = (f"{key[0]:>6s} {GAP} chars, "
                 f"{'new to stage 3' if key[1] == 'new' else 'page stage 2 had it'}")
        print(f"  {label:38s} n={tot:4d}  "
              + "  ".join(f"{t} {n}" for t, n in top))


if __name__ == "__main__":
    main()
