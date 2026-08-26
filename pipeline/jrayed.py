"""Client for the Veridian XML API behind jrayed.org (NLI Arabic newspapers).

The NLI newspaper sites run on Veridian with the XML interface enabled:
appending `f=XML` to ordinary site URLs returns machine-readable XML for
every browse, search and content request (spec: Veridian's published XML
interface documentation; field names below verified against live responses
2026-08-25).

Cloudflare gates the site, and its clearance is bound to the browser's TLS
fingerprint - a copied cf_clearance cookie does NOT work from curl/curl_cffi
(tried; every impersonation was challenged). What does work is making the
requests from inside a real Chrome: this client launches a dedicated Chrome
instance (separate profile, so your own browsing is untouched), lets it
solve the challenge invisibly, and issues every API call as an in-page
fetch() over the Chrome DevTools Protocol. The Chrome window must stay open
while harvesting; it is reused across runs.

Request forms (relative to https://jrayed.org/en/newspapers/):

  GetPublications          ?a=cl&cl=CL1&f=XML
  GetPublicationDocuments  ?a=cl&cl=CL1&sp=<PUB>&f=XML
  GetDates                 ?a=cl&cl=CL2&f=XML[&sp=<PUB>]
  GetDocument/Page/Section ?a=d&d=<ID>&f=XML
  SearchDocuments          ?a=q&leq=Document&f=XML[&puq=&yeq=&r=&o=]
  SearchLogicalSections    ?a=q&leq=Logical&txq=<TEXT>&f=XML[&...]
  SearchPages              ?a=q&leq=Page&txq=<TEXT>&f=XML[&...]
  article image            ?a=is&oid=<SECTID>&type=blockimage&area=1&width=W
  page tile                ?a=is&oid=<PAGEID>&type=pagetileimage&width=W&crop=x,y,w,h

Identifiers nest: document `elcarmel19320907-01`, page `...-01.1.4`,
article `...-01.2.7`. Searches page in blocks of at most 100 (`r` = first
result, 1-based; `o` = block size). Date filters: dafyq/datyq (+ dafmq/
dafdq etc.) bound the range.

Image access, established empirically: `type=staticpdf` and
`type=pageimage` are login-gated (the site's Download flow, NLI account +
reCAPTCHA). `type=blockimage` (whole logical sections/articles) is open at
any width. `type=pagetileimage` (the viewer's OpenSeadragon tiles) is open
but caps the output width of each request at 256px - so `page` below
reassembles a full-resolution page from a grid of crop requests (~100 per
page at 2000px; budget accordingly).

What the collection holds (as of 2026-08-25): 108 Arabic titles, 17 of
them printed in Haifa. Full-text search only covers the titles with OCR,
and the OCR follows the microfilm generations: Filastin and al-Difa' are
searchable across the Mandate decades (thousands of hospital mentions in
the 1930s-40s), while al-Ittihad's OCR is concentrated post-1960s and the
other Haifa titles (El-Carmel, al-Yarmuk, al-Nafir ...) are image-only -
reachable by date browsing, with pages harvestable through `page` for a
run through our own Gemini reading pipeline. Issues are barely segmented
for the image-only titles (El-Carmel 1932 sample: 8 pages, 3 sections).

Requests are throttled to one per second by default (--delay). Keep it
polite: this is a library service, not a bulk-download endpoint.

Examples:

  python3 pipeline/jrayed.py publications
  python3 pipeline/jrayed.py issues elcarmel
  python3 pipeline/jrayed.py dates --pub falastin
  python3 pipeline/jrayed.py search 'مستشفى حيفا' --pub alittihad \
      --from-year 1944 --to-year 1948 --out data/private/jrayed_hits.tsv
  python3 pipeline/jrayed.py text falastin19331026-01.1.5
  python3 pipeline/jrayed.py article falastin19331026-01.2.28 --width 2000
  python3 pipeline/jrayed.py page elcarmel19320917-01.1.1 --width 2000
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

try:
    import websocket
except ImportError:
    sys.exit("websocket-client is required:  python3 -m pip install --user websocket-client")

# The same Veridian instance serves two front doors. jrayed.org carries the
# Arabic collection (108 titles); www.nli.org.il carries everything else
# (2,356 titles, the English and Hebrew press among them). The API is
# identical; only the host differs. Requests are same-origin fetches from the
# Chrome tab, so the tab must be on the host being queried - switching sites
# means renavigating, which `site()` below handles.
SITES = {
    "jrayed": "https://jrayed.org/en/newspapers/",
    "nli": "https://www.nli.org.il/en/newspapers/",
}
BASE = SITES["jrayed"]
CDP = "http://127.0.0.1:9222"
PROFILE = os.path.expanduser("~/Library/Caches/jrayed-chrome")


def site(name: str) -> None:
    """Point every subsequent request at one of the two front doors."""
    global BASE
    BASE = SITES[name]


class Client:
    """Runs Veridian requests as fetch() calls inside a dedicated Chrome."""

    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self._last = 0.0
        self._mid = 0
        self.ws = self._connect()

    def _connect(self) -> websocket.WebSocket:
        tab = self._find_tab() or self._launch()
        ws = websocket.create_connection(
            tab["webSocketDebuggerUrl"], timeout=120, suppress_origin=True)
        self.ws = ws
        for _ in range(45):  # wait out the invisible Cloudflare challenge
            title = self._eval("document.title") or ""
            if "moment" not in title.lower():
                return ws
            time.sleep(2)
        sys.exit("Chrome is stuck on the Cloudflare challenge - check the window.")

    def _host(self) -> str:
        return urllib.parse.urlsplit(BASE).netloc

    def _find_tab(self) -> dict | None:
        """A tab already on the active host, or any tab we can renavigate."""
        try:
            tabs = json.load(urllib.request.urlopen(f"{CDP}/json", timeout=3))
        except (urllib.error.URLError, OSError):
            return None
        pages = [t for t in tabs if t["type"] == "page"]
        onsite = next((t for t in pages if self._host() in t.get("url", "")), None)
        if onsite or not pages:
            return onsite
        # Chrome is up but pointed elsewhere. Requests are same-origin fetches,
        # so take the tab over rather than opening a second window.
        self.ws = websocket.create_connection(
            pages[0]["webSocketDebuggerUrl"], timeout=120, suppress_origin=True)
        self._resolve_challenge()
        return pages[0]

    def _launch(self) -> dict:
        print("launching dedicated Chrome (leave its window open) ...", file=sys.stderr)
        subprocess.run([
            "open", "-na", "Google Chrome", "--args",
            "--remote-debugging-port=9222", f"--user-data-dir={PROFILE}",
            "--no-first-run", "--no-default-browser-check",
            BASE.rstrip("/") + "/home",
        ], check=True)
        for _ in range(30):
            time.sleep(2)
            tab = self._find_tab()
            if tab:
                return tab
        sys.exit("Chrome did not come up on port 9222. If another Chrome instance "
                 "owns the port, close it and retry.")

    def _call(self, method: str, params: dict) -> dict:
        self._mid += 1
        self.ws.send(json.dumps({"id": self._mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self._mid:
                return msg.get("result", {})

    def _eval(self, expression: str, await_promise: bool = False):
        result = self._call("Runtime.evaluate", {
            "expression": expression, "awaitPromise": await_promise,
            "returnByValue": True})
        if result.get("exceptionDetails"):
            raise RuntimeError(result["exceptionDetails"]
                               .get("exception", {}).get("description", "JS error"))
        return result.get("result", {}).get("value")

    def _resolve_challenge(self) -> None:
        """fetch() cannot pass a Cloudflare challenge; a navigation can.
        Reload the site and wait for the invisible challenge to clear."""
        print("Cloudflare clearance expired - renavigating ...", file=sys.stderr)
        self._call("Page.navigate", {"url": BASE.rstrip("/") + "/home"})
        for _ in range(45):
            time.sleep(2)
            try:
                title = self._eval("document.title") or ""
            except RuntimeError:  # context mid-navigation
                continue
            if title and "moment" not in title.lower():
                return
        sys.exit("Chrome is stuck on the Cloudflare challenge - check the window.")

    def _url(self, params: dict) -> str:
        return BASE + "?" + urllib.parse.urlencode(params)

    def _throttle(self) -> None:
        wait = self._last + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def raw(self, params: dict) -> str:
        """The response body as text, with challenge auto-recovery."""
        for attempt in (1, 2, 3):
            self._throttle()
            body = self._eval(
                f"fetch({json.dumps(self._url(params))},"
                "{credentials:'include'}).then(r=>r.text())", True)
            if body is None:
                # CDP occasionally returns no value for a large body; the
                # request itself is fine, so simply ask again.
                print("  empty CDP result - retrying", file=sys.stderr)
                time.sleep(2)
                continue
            if not is_challenge(body):
                return body
            self._resolve_challenge()
        raise RuntimeError("still challenged after renavigation")

    def xml(self, params: dict) -> ET.Element:
        body = self.raw({**params, "f": "XML"})
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            # Veridian emits OCR snippets with bare &, HTML-only named
            # entities (&nbsp; and friends, undefined in XML) and control
            # characters. Escape every & that does not open one of XML's own
            # five entities or a numeric reference, then strip the controls.
            body = re.sub(
                r"&(?!(?:#\d+|#x[0-9a-fA-F]+|amp|lt|gt|quot|apos);)",
                "&amp;", body)
            body = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", body)
            root = ET.fromstring(body)
        err = root.findtext(".//Error")
        if err:
            raise RuntimeError(f"Veridian error: {err}")
        return root

    def binary(self, params: dict, out: str) -> None:
        for _ in (1, 2, 3):
            self._throttle()
            b64 = self._eval(
                f"fetch({json.dumps(self._url(params))},{{credentials:'include'}})"
                ".then(r=>r.blob()).then(b=>new Promise(res=>{const fr=new FileReader();"
                "fr.onload=()=>res(fr.result.split(',')[1]);fr.readAsDataURL(b)}))", True)
            data = base64.b64decode(b64)
            if data[:1] in (b"\xff", b"\x89", b"%"):  # JPEG/PNG/PDF
                break
            if b"challenges.cloudflare.com" in data[:3000]:
                self._resolve_challenge()
                continue
            raise RuntimeError(f"got non-image response: {data[:120]!r}")
        else:
            raise RuntimeError("still challenged after renavigation")
        if hasattr(out, "write"):
            out.write(data)
            out.seek(0)
        else:
            with open(out, "wb") as f:
                f.write(data)


def is_challenge(body: str) -> bool:
    """Is this response a Cloudflare interstitial rather than our content?

    Cloudflare serves at least two forms here. The scripted one embeds
    challenges.cloudflare.com; the other is a bare holding page titled
    "Checking your browser..." with a meta refresh and no such script. Only
    testing for the first let the second reach the XML parser, where it
    surfaced as a mismatched-tag ParseError several hundred results into a
    harvest - a confusing way to be told the clearance had simply expired.
    """
    head = body[:3000].lower()
    return any(m in head for m in (
        "challenges.cloudflare.com", "checking your browser", "just a moment"))


def text(el: ET.Element | None, tag: str) -> str:
    return (el.findtext(tag) or "").strip() if el is not None else ""


def cmd_publications(c: Client, args) -> None:
    root = c.xml({"a": "cl", "cl": "CL1"})
    w = csv.writer(sys.stdout, delimiter="\t")
    w.writerow(["id", "title", "city", "language", "region"])
    for pub in root.iter("PublicationMetadata"):
        w.writerow([
            text(pub, "PublicationID"), text(pub, "PublicationTitle"),
            text(pub, "City"), text(pub, "Language"), text(pub, "Region"),
        ])


def cmd_issues(c: Client, args) -> None:
    root = c.xml({"a": "cl", "cl": "CL1", "sp": args.pub})
    w = csv.writer(sys.stdout, delimiter="\t")
    w.writerow(["document_id", "date", "type"])
    for doc in root.iter("DocumentMetadata"):
        w.writerow([text(doc, "DocumentID"), text(doc, "DocumentDate"),
                    text(doc, "DocumentType")])


def cmd_dates(c: Client, args) -> None:
    params = {"a": "cl", "cl": "CL2"}
    if args.pub:
        params["sp"] = args.pub
    for d in c.xml(params).iter("Date"):
        print(f"{d.text}\t{d.get('n', '')}")


def cmd_search(c: Client, args) -> None:
    params = {"a": "q", "leq": args.level, "txq": args.text, "ssnip": "txt"}
    if args.pub:
        params["puq"] = args.pub
    if args.from_year:
        params["dafyq"] = str(args.from_year)
    if args.to_year:
        params["datyq"] = str(args.to_year)
    if args.any:
        params["t"] = "1"

    out = open(args.out, "w", newline="") if args.out else sys.stdout
    w = csv.writer(out, delimiter="\t")
    w.writerow(["n", "id", "date", "publication", "title", "snippet"])
    hit_tag = "LogicalSection" if args.level == "Logical" else args.level

    got, total, r = 0, None, 1
    while total is None or (got < total and got < args.max):
        # A few blocks in the larger Hebrew harvests make the server hang up
        # ("Failed to fetch"). The results are fine either side of them, so
        # step the block size down rather than losing the run.
        want = min(100, args.max - got)
        for size in (want, want // 2, want // 4, 10):
            if size < 1:
                continue
            try:
                block = c.xml({**params, "r": str(r), "o": str(size)})
                break
            except RuntimeError as exc:
                print(f"  block r={r} o={size} failed ({exc}); backing off",
                      file=sys.stderr)
        else:
            raise RuntimeError(f"block r={r} unrecoverable")
        total = int(block.findtext(".//TotalNumberOfSearchResults") or 0)
        hits = list(block.iter(hit_tag))
        if not hits:
            break
        for hit in hits:
            meta = hit.find(f"{hit_tag}Metadata")
            docmeta = hit.find("DocumentMetadata")
            snippet = " ".join((hit.findtext("SearchResultSnippetHTML") or "").split())
            w.writerow([
                text(hit, "SearchResultNumber"),
                text(meta, f"{hit_tag}ID") or text(docmeta, "DocumentID"),
                text(docmeta, "DocumentDate") or text(meta, "DocumentDate"),
                text(hit.find("PublicationMetadata"), "PublicationID"),
                text(meta, f"{hit_tag}Title"),
                snippet,
            ])
        got += len(hits)
        r += len(hits)
        print(f"  {got}/{total}", file=sys.stderr)

    if args.out:
        out.close()
        print(f"wrote {got} of {total or 0} hits -> {args.out}", file=sys.stderr)

    facets = [(text(f, "SearchFacetValue"), int(text(f, "SearchFacetCount") or 0))
              for f in (block.iter("SearchFacet") if total else [])
              if "(PU)" in text(f, "SearchFacetField")]
    if facets and not args.pub:
        print("hits by publication:", file=sys.stderr)
        for v, n in sorted(facets, key=lambda x: -x[1])[:15]:
            print(f"  {n:6d}  {v}", file=sys.stderr)


def cmd_doc(c: Client, args) -> None:
    ET.indent(root := c.xml({"a": "d", "d": args.id}))
    sys.stdout.write(ET.tostring(root, encoding="unicode"))


def cmd_text(c: Client, args) -> None:
    root = c.xml({"a": "d", "d": args.id})
    body = (root.findtext(".//LogicalSectionTextHTML")
            or root.findtext(".//PageTextHTML") or "")
    print(body)


def cmd_article(c: Client, args) -> None:
    out = args.out or f"{args.id}.jpg"
    c.binary({"a": "is", "oid": args.id, "type": "blockimage", "area": "1",
              "width": str(args.width)}, out)
    print(f"wrote {out}", file=sys.stderr)


def cmd_page(c: Client, args) -> None:
    """Reassemble a full page from 256px-wide viewer tiles."""
    from io import BytesIO
    from PIL import Image

    root = c.xml({"a": "d", "d": args.id})
    pages = list(root.iter("PageMetadata"))
    page = next((p for p in pages if text(p, "PageID") == args.id),
                pages[0] if pages else None)
    if page is None:
        sys.exit(f"no PageMetadata for {args.id}")
    full_w = int(text(page, "PageImageWidth"))
    full_h = int(text(page, "PageImageHeight"))

    scale = min(1.0, args.width / full_w)
    out_w, out_h = round(full_w * scale), round(full_h * scale)
    step = round(256 / scale)  # source pixels per 256px output tile
    canvas = Image.new("L", (out_w, out_h), 255)
    cols = range(0, full_w, step)
    rows = range(0, full_h, step)
    n, todo = 0, len(cols) * len(rows)
    for y in rows:
        for x in cols:
            w, h = min(step, full_w - x), min(step, full_h - y)
            buf = BytesIO()
            c.binary({"a": "is", "type": "pagetileimage", "oid": args.id,
                      "width": str(round(w * scale)),
                      "crop": f"{x},{y},{w},{h}"}, buf)
            canvas.paste(Image.open(buf).convert("L"),
                         (round(x * scale), round(y * scale)))
            n += 1
            if n % 20 == 0:
                print(f"  tile {n}/{todo}", file=sys.stderr)
    out = args.out or f"{args.id}.jpg"
    canvas.save(out, quality=90)
    print(f"wrote {out} ({out_w}x{out_h}, {n} tiles)", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--site", choices=sorted(SITES), default="jrayed",
                    help="jrayed = the Arabic collection; nli = everything else "
                         "(English and Hebrew press, 2,356 titles)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("publications", help="list all titles in the collection")

    p = sub.add_parser("issues", help="list every issue of one title")
    p.add_argument("pub", help="publication id, e.g. elcarmel")

    p = sub.add_parser("dates", help="date coverage, optionally per title")
    p.add_argument("--pub")

    p = sub.add_parser("search", help="full-text search, paged to TSV")
    p.add_argument("text")
    p.add_argument("--pub")
    p.add_argument("--from-year", type=int)
    p.add_argument("--to-year", type=int)
    p.add_argument("--level", choices=["Logical", "Page", "Document"], default="Page")
    p.add_argument("--any", action="store_true", help="match any keyword, not all")
    p.add_argument("--max", type=int, default=1000)
    p.add_argument("--out")

    p = sub.add_parser("doc", help="raw XML for a document/page/section id")
    p.add_argument("id")

    p = sub.add_parser("text", help="OCR text of a page or article id")
    p.add_argument("id")

    p = sub.add_parser("article", help="download an article (section) image")
    p.add_argument("id", help="section id, e.g. falastin19331026-01.2.28")
    p.add_argument("--width", type=int, default=2000)
    p.add_argument("--out")

    p = sub.add_parser("page", help="download a full page, stitched from tiles")
    p.add_argument("id", help="page id, e.g. elcarmel19320917-01.1.1")
    p.add_argument("--width", type=int, default=2000)
    p.add_argument("--out")

    args = ap.parse_args()
    site(args.site)
    c = Client(delay=args.delay)
    {
        "publications": cmd_publications,
        "issues": cmd_issues,
        "dates": cmd_dates,
        "search": cmd_search,
        "doc": cmd_doc,
        "text": cmd_text,
        "article": cmd_article,
        "page": cmd_page,
    }[args.cmd](c, args)


if __name__ == "__main__":
    main()
