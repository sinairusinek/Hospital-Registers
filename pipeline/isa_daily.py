"""Transcribe the DAILY RETURN tallies of ISA 000zbri (Haifa, 1942-44).

Companion to pipeline/isa_returns.py, which read the 180 NOMINAL versos ("Report
on Cases and Deaths", one row per named person). This reads the other side of
the pair: the 178 printed DAILY RETURN OF INFECTIOUS DISEASES rectos, which
carry no names but do carry the aggregate daily state:

  Town or Village | Diseases | Existing | New Cases | DIED (In Hospital /
  Out of Hospital) | Remaining | Reference to report on back of form, or to
  previous Serial No.

WHY THIS IS WORTH DOING SEPARATELY. The nominal lists gave a per-case
`where_treated`, from which 72% of notified cases were treated at the
Government Hospital or Isolation and 23% at home. The daily returns record
deaths already split **In Hospital / Out of Hospital** by the clerks
themselves. That is an INDEPENDENT check on the hospital/home division, made by
the same office but through a different column, and it is the reason
data/archives/isa_1942-44_linkage.md left this job open.

The pages are already classified: pipeline/isa_returns.py wrote page_kind,
return_date, serial_no and district for all 388 pages to
data/private/isa-1942-44-pages.tsv. This script reads only the 178 marked
`daily`, and takes the date and serial from that file rather than re-reading
them.

THINGS THESE FORMS DO, learned from looking at them:

  * The grid is often EMPTY. A return was sent "only when a change in the daily
    state has occurred", and multi-sheet returns exist - p.332 is headed
    "Sheet III", signed, and carries no tally rows at all. An empty grid is a
    fact about the return, not a failed read, so `rows` may legitimately be 0
    and the page is still recorded.
  * Consecutive pages sometimes share a date AND serial number (337/339,
    341/343). Those are the sheets of one multi-sheet return, not duplicates.
    The serial is therefore NOT a unique key; (serial, page) is.
  * `Town or Village` runs down the column in ditto marks under the first
    named place, usually Haifa but not always - outlying villages appear.
  * A DASH means zero and a BLANK means not stated. They are different and
    both are kept as written; do not silently turn either into 0.
  * The reference column chains returns together ("Ref. Return No.29 of
    28.7.44 Rep.C cases Nos 1 & 7"), which is what lets a case be followed
    across returns. It is transcribed verbatim.

Rotation is handled as in isa_returns.py: the scans are sideways and the
direction varies page to page, so both rotations are sent and the model reads
whichever is upright.

Run:
  python3 pipeline/isa_daily.py --pages 6,20     # named pages
  python3 pipeline/isa_daily.py --limit 10
  python3 pipeline/isa_daily.py --all

Needs GOOGLE_API_KEY and the page images rendered by isa_returns.py's
instructions:
  pdftoppm -r 200 -png paper/sources/isa/000zbri.pdf <dir>/p
"""

from __future__ import annotations

import argparse
import base64
import csv
import glob
import io
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = os.path.join(ROOT, "data", "private", "isa-1942-44-pages.tsv")
OUT = os.path.join(ROOT, "data", "private", "isa-1942-44-daily.tsv")
OUT_PAGES = os.path.join(ROOT, "data", "private", "isa-1942-44-daily-pages.tsv")

API = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-3.1-pro-preview"
IMG_WIDTH = 2200
THINKING_LEVEL = "low"
MAX_OUTPUT_TOKENS = 65536

FIELDS = ["town", "disease", "existing", "new_cases", "died_in_hospital",
          "died_out_of_hospital", "cured", "remaining", "reference",
          "uncertain"]

SCHEMA = {
    "type": "object",
    "properties": {
        "is_daily_return": {"type": "boolean"},
        "sheet": {"type": "string"},
        "date": {"type": "string"},
        "serial_no": {"type": "string"},
        "district": {"type": "string"},
        "grid_empty": {"type": "boolean"},
        "page_note": {"type": "string"},
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {f: {"type": "string"} for f in FIELDS},
            },
        },
    },
    "required": ["is_daily_return", "rows"],
}

PROMPT = """You are reading one page from a Mandate Department of Health file,
"Monthly Returns - Infectious Diseases, Haifa", 1942-1944. This page should be a
printed form headed DAILY RETURN OF INFECTIOUS DISEASES.

THE PAGE IS GIVEN TWICE, in two rotations. Exactly ONE of them is upright and
readable. Read that one. Ignore the other completely - do not try to combine
them, and do not report the same row twice.

Set `is_daily_return` true if this is that printed tally form. If the page is
instead a nominal "REPORT ON CASES AND DEATHS" (a table with a NAME column and
one row per named person), a letter, or anything else, set `is_daily_return`
false, return `rows` empty, and say what it is in `page_note`. Do NOT transcribe
names on this pass.

THE COLUMNS of the tally grid, left to right:

  Town or Village | Diseases | Existing | New Cases | DIED (split into two
  sub-columns: In Hospital | Out of Hospital) | Remaining | Reference to report
  on back of form, or to previous Serial No.

Some printings of the form also carry a CURED column between New Cases and
DIED. If it is present, put it in `cured`; if the form has no such column,
leave `cured` empty. Look at the printed header and see which layout you have
before reading any row - the DIED sub-columns are narrow and easy to slip.

TRANSCRIBE WHAT IS ON THE PAGE.

* **An empty grid is normal and is not an error.** The form says a return is to
  be sent "only when a change in the daily state has occurred", and some sheets
  of a multi-sheet return carry a heading and a signature but no tally rows at
  all. If the grid has no data rows, set `grid_empty` true and return `rows`
  empty. Never invent a row to fill the page.
* **A DASH means zero. A BLANK means not stated.** They are different. Write a
  dash as "-" and leave a blank empty. Do not convert either into "0".
* **Ditto marks in Town or Village** (" or -do-) mean the same place as the row
  above. EXPAND them: write the place name they stand for. Most rows are Haifa,
  but outlying villages do appear and must not be silently turned into Haifa.
* **Disease names** run: typhoid, paratyphoid, plague (bubonic), smallpox,
  murine typhus, undulant fever, erysipelas, dysentery, measles, scarlet fever,
  C.S.M., anthrax, poliomyelitis, whooping cough, diphtheria. Keep any
  qualifier, e.g. "Plague Bubonic".
* **The reference column** chains returns together, e.g. "Rep.A. (a) Ref.
  Return No.29 of 28.7.44 Rep.C cases Nos 1 & 7". Transcribe it in full and as
  written - it is what lets a case be followed from one return to the next.
* **Corrections on the page.** Figures were sometimes struck through and
  rewritten, often in a different colour by a later hand - "92" crossed out and
  "96" written beside it. When that happens, put the FINAL (corrected) value in
  the field and record the correction in `uncertain` as e.g. "92 corrected to
  96". Do not concatenate the two numbers into one cell, and do not silently
  drop either: which figure Jerusalem ended up with is the point.
* The CURED column, where the form has one, is often NARROW and squeezed
  between New Cases and the DIED pair, sometimes with its heading printed
  sideways. Do not mistake a cured figure for a death. If a number sits left of
  the "In Hospital" rule it is Cured; only what sits under DIED is a death.

Also record, from the form's own printed heading:
`date` (as written, e.g. "30.8.44."), `serial_no` (the bare Serial No.),
`district` (usually Haifa), and `sheet` if the page is marked as a sheet of a
multi-sheet return, e.g. "Sheet III".

Use `page_note` for anything true of the page as a whole - a stamp, a marginal
annotation, a tear, a note added by Jerusalem.

Keep `uncertain` SHORT - a few words, only when a reading is genuinely in
doubt. Leave it empty otherwise. Do not restate the row in it."""


def rotations(path: str) -> list[bytes]:
    """Both rotations of a sideways scan; the model picks the upright one."""
    from PIL import Image
    im = Image.open(path)
    if im.mode != "RGB":
        im = im.convert("RGB")
    out = []
    for rot in (90, -90):
        part = im.rotate(rot, expand=True)
        if part.width > IMG_WIDTH:
            part = part.resize(
                (IMG_WIDTH, int(part.height * IMG_WIDTH / part.width)),
                Image.LANCZOS)
        buf = io.BytesIO()
        part.save(buf, format="JPEG", quality=90)
        out.append(buf.getvalue())
    return out


def read_page(images: list[bytes], model: str, key: str) -> dict:
    labels = ["The page rotated one way:",
              "The SAME page rotated the other way - only one of these two is "
              "upright, read that one and ignore the other:"]
    parts: list[dict] = [{"text": PROMPT}]
    for label, image in zip(labels, images):
        parts.append({"text": label})
        parts.append({"inline_data": {
            "mime_type": "image/jpeg",
            "data": base64.b64encode(image).decode("ascii")}})
    parts.append({"text": "Now return the heading and every tally row."})

    body = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
            "temperature": 0,
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
            "thinkingConfig": {"thinkingLevel": THINKING_LEVEL},
        },
    }).encode("utf-8")

    url = f"{API}/models/{model}:generateContent?key={key}"
    for attempt in range(5):
        try:
            req = urllib.request.Request(
                url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=900) as r:
                payload = json.load(r)
            cand = payload["candidates"][0]
            if cand.get("finishReason") not in (None, "STOP"):
                raise RuntimeError(f"model stopped early: {cand['finishReason']}")
            return json.loads(cand["content"]["parts"][0]["text"])
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:
                raise
            if attempt == 4:
                raise
            time.sleep(min(60, 4 * 2 ** attempt))
        except Exception:
            if attempt == 4:
                raise
            time.sleep(min(60, 4 * 2 ** attempt))
    raise RuntimeError("unreachable")


def done_pages(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["page"] for r in csv.DictReader(fh, delimiter="\t")
                if not r.get("error")}


def daily_pages() -> dict[str, dict]:
    """The pages isa_returns.py classified as daily returns, with their headings."""
    if not os.path.exists(PAGES):
        return {}
    out = {}
    with open(PAGES, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if r.get("page_kind") == "daily":
                out[r["page"]] = r
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", default=os.path.join(
        ROOT, "paper", "sources", "isa", "pages", "000zbri"))
    ap.add_argument("--pages", help="comma-separated page numbers")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("GOOGLE_API_KEY not set", file=sys.stderr)
        return 2

    known = daily_pages()
    if not known:
        print(f"no daily pages listed in {PAGES} - run pipeline/isa_returns.py "
              f"first", file=sys.stderr)
        return 2

    files = sorted(glob.glob(os.path.join(args.images, "*.png")))

    def pageno(p: str) -> str:
        m = re.search(r"(\d+)\.png$", p)
        return str(int(m.group(1))) if m else os.path.basename(p)

    files = [f for f in files if pageno(f) in known]
    if not files:
        print(f"no page images for the daily pages in {args.images}",
              file=sys.stderr)
        return 2

    already = done_pages(OUT_PAGES)
    todo = [f for f in files if pageno(f) not in already]
    if args.pages:
        want = {p.strip() for p in args.pages.split(",")}
        todo = [f for f in files if pageno(f) in want]
    elif args.limit:
        todo = todo[:args.limit]
    elif not args.all:
        todo = todo[:1]

    print(f"{len(files)} daily pages, {len(already)} already read, "
          f"{len(todo)} to do", file=sys.stderr)

    lock = threading.Lock()
    new_out = not os.path.exists(args.out)
    new_pages = not os.path.exists(OUT_PAGES)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fout = open(args.out, "a", newline="", encoding="utf-8")
    fpag = open(OUT_PAGES, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(
        fout, fieldnames=["page", "date", "serial_no", "sheet"] + FIELDS,
        delimiter="\t", extrasaction="ignore")
    wp = csv.DictWriter(
        fpag,
        fieldnames=["page", "rows", "is_daily_return", "grid_empty", "date",
                    "serial_no", "district", "sheet", "page_note", "error"],
        delimiter="\t", extrasaction="ignore")
    if new_out:
        w.writeheader()
    if new_pages:
        wp.writeheader()

    def work(path: str):
        pg = pageno(path)
        prior = known.get(pg, {})
        try:
            got = read_page(rotations(path), args.model, key)
        except Exception as e:
            with lock:
                wp.writerow({"page": pg, "rows": 0, "error": str(e)[:200]})
                fpag.flush()
            print(f"  page {pg}: FAILED {str(e)[:90]}", file=sys.stderr)
            return
        rows = got.get("rows", [])
        # The heading was already read on the classification pass; prefer that
        # value and fall back to this read, so the two passes cannot disagree
        # silently.
        date = (prior.get("return_date") or got.get("date") or "").strip()
        serial = (prior.get("serial_no") or got.get("serial_no") or "").strip()
        sheet = (got.get("sheet") or "").strip()
        with lock:
            for r in rows:
                rec = {"page": pg, "date": date, "serial_no": serial,
                       "sheet": sheet}
                rec.update({f: (r.get(f) or "").strip() for f in FIELDS})
                w.writerow(rec)
            wp.writerow({
                "page": pg, "rows": len(rows),
                "is_daily_return": got.get("is_daily_return"),
                "grid_empty": got.get("grid_empty"),
                "date": date, "serial_no": serial,
                "district": (prior.get("district")
                             or got.get("district") or "").strip(),
                "sheet": sheet,
                "page_note": (got.get("page_note") or "")[:300], "error": ""})
            fout.flush()
            fpag.flush()
        flag = "" if got.get("is_daily_return") else "  NOT-A-DAILY"
        print(f"  page {pg}: {len(rows)} rows{flag}", file=sys.stderr)

    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(work, todo))

    fout.close()
    fpag.close()
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
