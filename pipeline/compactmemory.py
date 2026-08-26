"""Client for Compact Memory (Universitätsbibliothek Frankfurt) via SRU.

Compact Memory's HTML sits behind a browser-verification wall that curl and
WebFetch cannot pass, but the Visual Library server underneath exposes an
open, unauthenticated SRU endpoint that plain HTTP reaches:

  https://sammlungen.ub.uni-frankfurt.de/cm/sru?operation=explain
  https://sammlungen.ub.uni-frankfurt.de/cm/sru?operation=searchRetrieve
      &version=1.2&query=<CQL>&startRecord=N&maximumRecords=100

CORRECTION to an earlier note in this repo: the search is NOT metadata-only.
`explain` advertises a **fulltext** index, and it works - `vl.fulltext=Haifa`
returns 16,041 documents, phrase search (`vl.fulltext="Regierungskrankenhaus
in Haifa"`) works, and each hit carries the ids of the pages the term fell on.
The earlier "article/metadata level" reading came from the website's own
search form, not from this endpoint.

Query language is CQL. Useful indexes (from `explain`): anywhere, title,
corporation, personalName, printer-publisher, originPlace, date, subject,
identifier, domain, collection, **fulltext**, structures, genreCode.

  vl.fulltext=Krankenhaus                     one term
  vl.fulltext="Regierungskrankenhaus in Haifa"  phrase
  vl.fulltext=Krankenhaus and vl.fulltext=Haifa  both, in the same ISSUE

TRAP - the unit of a hit is the **issue**, not the page. An AND of two terms
means they occur somewhere in the same issue, possibly columns apart. Page
ids come back per hit (`<vl:pages><vl:page id=...>`), so precision has to be
recovered locally from page text, exactly as with Jrayed.

TRAP - German compounds break across narrow columns and the index does NOT
rejoin them. `Regierungskrankenhaus` matches 109 documents; the adjacency
phrase `"Regierungs Krankenhaus"` matches 44 more that the single-token query
cannot see (`"Kranken haus"` matches 1,321). Always query the split form too.
Two smaller ones in the same family: display type is largely unread, so a
running column head like "Haifaer Notizen" indexes in one issue only; and
umlaut is not folded to `ae` (Borromaeerinnen 10, Borromaeerinnen-with-umlaut
1), though inflection IS stemmed (Krankenhauses = Krankenhaus, Haifas = Haifa).
Read no zero as absence.

TRAP - there is no working server-side "search within this journal". The
`structures`, `collection` and `reference` indexes all return 0 for a journal
id. Filtering to a title is therefore done here, locally, on the host title
carried in each hit's MODS `relatedItem type="host"`. `--title` /
`--place` do that.

The Palestine-published titles (the reason we are here) are:

  Mitteilungsblatt der Hitachdut Olej Germania we Austria, Tel-Aviv 1940-42
  MB / Mitteilungsblatt des Irgun Olei Merkas Europa, Tel-Aviv 1943-52
  Jüdische Weltrundschau, Jerusalem 1939-40

Page text: `text <page-id>` fetches the OCR of one page through the same
open host (`/cm/download/pageocr/<id>` .. see PAGE_TEXT_URLS); if none of the
routes answer, the page is left empty rather than guessed at.

Requests are throttled to one per second by default. This is a library
service, not a bulk endpoint.

Examples:

  python3 pipeline/compactmemory.py explain
  python3 pipeline/compactmemory.py titles --place Tel-Aviv
  python3 pipeline/compactmemory.py search 'vl.fulltext="Regierungskrankenhaus in Haifa"'
  python3 pipeline/compactmemory.py search 'vl.fulltext=Krankenhaus and vl.fulltext=Haifa' \
      --title Mitteilungsblatt --title MB --out data/newspapers/cm_mb_krankenhaus.tsv
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://sammlungen.ub.uni-frankfurt.de/cm"
SRU = BASE + "/sru"
UA = "Hospital-Registers research harvester (contact: sinai.rusinek@gmail.com)"

# Candidate routes for one page's OCR text, tried in order.
PAGE_TEXT_URLS = [
    BASE + "/download/pageocr/{id}",
    BASE + "/download/webcache/0/{id}",
    BASE + "/urn/{id}/plain",
    BASE + "/api/fulltext/{id}",
]

FIELDS = [
    "issue_id", "host_title", "place", "date", "volume", "issue",
    "page_ids", "page_captions", "hits", "record_id",
]


def get(url: str, delay: float = 1.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as fh:
        body = fh.read().decode("utf-8", "replace")
    time.sleep(delay)
    return body


def sru(query: str, start: int = 1, count: int = 100, delay: float = 1.0) -> str:
    url = (f"{SRU}?operation=searchRetrieve&version=1.2&recordSchema=mods"
           f"&startRecord={start}&maximumRecords={count}"
           f"&query={urllib.parse.quote(query)}")
    return get(url, delay)


def _first(pattern: str, text: str) -> str:
    m = re.search(pattern, text, re.S)
    return html.unescape(m.group(1)).strip() if m else ""


def parse_records(xml: str) -> tuple[int, list[dict]]:
    total = int(_first(r"<srw:numberOfRecords>(\d+)", xml) or 0)
    out = []
    for rec in xml.split("<srw:record>")[1:]:
        data, _, extra = rec.partition("<srw:extraRecordData")
        host = _first(r'<relatedItem type="host">(.*?)</relatedItem>', data) or data
        pages = re.findall(r'<vl:page[^>]*caption="([^"]*)"[^>]*id="(\d+)"', extra)
        if not pages:  # attribute order is not guaranteed
            ids = re.findall(r'<vl:page[^>]*\bid="(\d+)"', extra)
            pages = [("", i) for i in ids]
        out.append({
            "issue_id": _first(r"<vl:id>(\d+)</vl:id>", extra),
            "host_title": _first(r"<title>(.*?)</title>", host),
            "place": _first(r'<placeTerm type="text">(.*?)</placeTerm>', host),
            "date": _first(r'<date encoding="w3cdtf">([\d-]+)</date>', data),
            "volume": _first(r'<detail type="volume"[^>]*>\s*<number>(.*?)</number>', data),
            "issue": _first(r'<detail type="issue"[^>]*>\s*<number>(.*?)</number>', data),
            "page_ids": ";".join(i for _, i in pages),
            "page_captions": ";".join(html.unescape(c) for c, _ in pages),
            "hits": _first(r'<vl:pages hits="(\d+)"', extra),
            "record_id": _first(r"<recordIdentifier[^>]*>(.*?)</recordIdentifier>", data),
        })
    return total, out


def search(query: str, limit: int, delay: float, titles: list[str],
           places: list[str], years: tuple[int, int] | None) -> tuple[int, list[dict]]:
    start, kept, total = 1, [], None
    while True:
        xml = sru(query, start, min(100, limit - len(kept) + 100), delay)
        n, recs = parse_records(xml)
        if total is None:
            total = n
        if not recs:
            break
        for r in recs:
            if titles and not any(t.lower() in r["host_title"].lower() for t in titles):
                continue
            if places and not any(p.lower() in r["place"].lower() for p in places):
                continue
            if years:
                y = int(r["date"][:4]) if r["date"][:4].isdigit() else None
                if y is None or not (years[0] <= y <= years[1]):
                    continue
            kept.append(r)
        start += len(recs)
        if start > n or start > limit:
            break
    return total, kept


def page_text(page_id: str, delay: float) -> str:
    for tmpl in PAGE_TEXT_URLS:
        try:
            body = get(tmpl.format(id=page_id), delay)
        except Exception:
            continue
        if body and "<html" not in body[:200].lower():
            return body
    return ""


def write_tsv(rows: list[dict], path: str | None) -> None:
    fh = open(path, "w", newline="", encoding="utf-8") if path else sys.stdout
    w = csv.DictWriter(fh, fieldnames=FIELDS, delimiter="\t", extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    if path:
        fh.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("explain", help="dump the SRU explain response (index list)")

    p = sub.add_parser("titles", help="list journal records, optionally by place")
    p.add_argument("--place")
    p.add_argument("--max", type=int, default=200)

    p = sub.add_parser("search", help="run a CQL query, one row per hit issue")
    p.add_argument("query")
    p.add_argument("--title", action="append", default=[],
                   help="keep only hits whose host title contains this (repeatable)")
    p.add_argument("--place", action="append", default=[])
    p.add_argument("--from-year", type=int)
    p.add_argument("--to-year", type=int)
    p.add_argument("--max", type=int, default=2000)
    p.add_argument("--out")

    p = sub.add_parser("text", help="fetch the OCR text of one page id")
    p.add_argument("page_id")

    a = ap.parse_args()

    if a.cmd == "explain":
        print(get(f"{SRU}?operation=explain", a.delay))
        return

    if a.cmd == "titles":
        q = 'vl.genreCode=periodical' if not a.place else f'vl.originPlace="{a.place}"'
        _, recs = parse_records(sru(q, 1, a.max, a.delay))
        seen = set()
        for r in recs:
            key = (r["host_title"], r["place"])
            if key in seen:
                continue
            seen.add(key)
            print(f'{r["issue_id"]}\t{r["host_title"]}\t{r["place"]}\t{r["date"]}')
        return

    if a.cmd == "search":
        years = None
        if a.from_year or a.to_year:
            years = (a.from_year or 0, a.to_year or 9999)
        total, rows = search(a.query, a.max, a.delay, a.title, a.place, years)
        print(f"# query: {a.query}", file=sys.stderr)
        print(f"# corpus-wide hits: {total}; kept after filters: {len(rows)}", file=sys.stderr)
        write_tsv(rows, a.out)
        return

    if a.cmd == "text":
        sys.stdout.write(page_text(a.page_id, a.delay))


if __name__ == "__main__":
    main()
