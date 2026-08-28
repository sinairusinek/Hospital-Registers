"""Transcribe the Haifa Infectious Diseases Record Book, 1921-1928 (ISA 000i5yq).

A bound Department of Health ledger, 393 pages, ~30 named cases a page, so on
the order of 7,200 records. Printed headings are trilingual (English / Arabic /
Hebrew); the entries are manuscript English. It is a NOTIFICATION register, not
an admissions register - see the caution in data/archives/isa_readings.md - and
it predates both hospital buildings.

Columns, left to right:
  Serial No. | Monthly No. | Date of receipt | Name of Patient | Address |
  Occupation (and if a child, name of school) | Age | Sex | Religion |
  Diagnosis | Date of commencement of illness | Attending Physician |
  Date cured | Date died

Design follows pipeline/second_look.py, whose lessons were paid for:
  * the page is sent in halves, because a whole spread downsamples past
    reading and the failure is silent - empty columns, not garbled text;
  * temperature 0, low thinking, a response schema, and a resumable output,
    so an interrupted run continues where it stopped;
  * the model transcribes what is on the page and flags doubt in `uncertain`
    rather than tidying the record.

UNLIKE the admission registers, names here are NOT redacted - this is a
government notification ledger of 1921-28, opened to the public by the ISA.
Names are transcribed.

PUBLICATION: cleared by the user on 2026-08-28 - this data MAY be published,
on the grounds that the ISA has already published the ledger openly and the
people recorded died long ago. The default output path below is still
data/private/ only because the extractor is not yet working; move it to
data/public/ when it is, and cite the source as ISA 000i5yq.

Run:
  python3 pipeline/isa_ledger.py --pages 4,5,6      # named pages
  python3 pipeline/isa_ledger.py --limit 20         # first 20 unread
  python3 pipeline/isa_ledger.py --all

Needs GOOGLE_API_KEY, and page images rendered beforehand:
  pdftoppm -r 200 -png paper/sources/isa/000i5yq.pdf <dir>/f
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
OUT = os.path.join(ROOT, "data", "private", "isa-infectious-ledger.tsv")
OUT_PAGES = os.path.join(ROOT, "data", "private", "isa-infectious-ledger-pages.tsv")

API = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-3.1-pro-preview"
HALF_WIDTH = 2200
GUTTER_OVERLAP = 0.08
THINKING_LEVEL = "low"
MAX_OUTPUT_TOKENS = 65536

FIELDS = ["serial", "monthly_no", "date_received", "name", "address",
          "occupation", "age", "sex", "religion", "diagnosis",
          "date_onset", "physician", "date_cured", "date_died", "uncertain"]

SCHEMA = {
    "type": "object",
    "properties": {
        "page_note": {"type": "string"},
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {f: {"type": "string"} for f in FIELDS},
                "required": ["serial"],
            },
        },
    },
    "required": ["rows"],
}

PROMPT = """You are reading one page of the INFECTIOUS DISEASES RECORD BOOK of
the Department of Health, Haifa, 1921-1928, and transcribing every row on it.

The printed headings are trilingual - English, Arabic and Hebrew. The entries
are handwritten in English. The columns, left to right, are:

  Serial No. | Monthly No. | Date of receipt | Name of Patient | Address |
  Occupation, and if a child, name of school | Age | Sex | Religion |
  Diagnosis | Date of commencement of illness | Attending Physician |
  Date cured | Date died

TRANSCRIBE WHAT IS ON THE PAGE. Do not correct it, complete it, or make it
consistent. If a cell is empty, leave it empty. If you cannot read something,
put your best reading in the field and say so in `uncertain`.

Things this ledger does, learned from reading it:

* The **Serial No.** is a CONTINUOUS counter running across the whole book
  (it reaches ~7,200 by the end of 1928). The **Monthly No.** restarts each
  month. Transcribe the number actually written on each row; NEVER renumber a
  row to fit the run. A jump in the sequence is a fact worth recording.
* **Addresses** are Haifa micro-topography and are the most valuable column
  after the name: Wadi Salib, Wadi Rushmia, Jaffa Road, Allenby Street, Hadar
  Carmel, German Colony, Mt. Carmel, Bat Galim, Ard el Yahud, Hai Salam. Some
  are keyed to a person or a landmark - "Selim Khoury's Quarter", "Aziz
  Mikati's Quarter", "near Dr Zurub's House", "near B.H.O. Offices",
  "house opposite Nassar's Hotel". Transcribe these in full, exactly as
  written. Places outside Haifa also appear (Zichron Yacob, Nahalal, Hadera,
  Meylia, Caesarea, Arara, Ein Taboun) - keep them.
* **Religion** is usually Moslem, Christian or Jew. Transcribe the word used.
* **Occupation** may be a trade, or "child", or a school name for a child, or
  an age in brackets. Transcribe what is there.
* **Diagnosis** is a notifiable or epidemic disease: pneumonia, influenza,
  varicella, measles, meningitis, whooping cough, puerperal fever, typhoid,
  smallpox, plague, dysentery, enteric. Some carry a qualifier in brackets,
  e.g. "Puerperal Fever (Gonorrhoeal)", "Pneumonia Left". Keep the qualifier.
* **Attending Physician** names recur - Dr Sternberg, Dr Hoffman, Dr Zurub,
  Dr Husseinham, Dr Kohen, Dr Khalil. Transcribe the name as written; do not
  normalise a spelling to match another row.
* **Date cured** and **Date died** are mutually exclusive in practice. A row
  with neither is an open case. Do not infer one from the other.
* Dates are written in several ways (5.3.22, 5.III.22, March 5th). Transcribe
  the form used; do not convert.

Some entries are officials or foreign residents (e.g. an Immigration Officer)
rather than townspeople. They are still rows of the register.

The page is given as TWO images: the LEFT part and the RIGHT part of the SAME
single ledger page, cut down the middle with a generous overlap, so some
columns appear in BOTH images. They hold the SAME rows in the SAME order - the
first row of the first image is the first row of the second. Read each row
straight across both images and return it as ONE record with every column
filled that you can see in either image.

Every row must carry its age, sex, religion, diagnosis, physician and dates if
they are written on the page. If a whole column comes back empty for the page,
you have mis-registered the two images against each other - look again.

Use `page_note` for anything true of the page as a whole - a heading, a change
of year, a torn or stained area, a column left blank throughout.

Keep `uncertain` SHORT - a few words, only when a reading is genuinely in
doubt. Leave it empty otherwise. Do not restate the row in it."""


def halves(path: str) -> list[bytes]:
    """Split one landscape ledger page into two overlapping vertical halves.

    Each PDF page is ONE page of the ledger (aspect ~1.5), not a two-page
    spread. A naive split at the midpoint cuts through the middle columns and
    the model returns serial/name/occupation but leaves age, religion,
    diagnosis, physician and the dates empty - a silent failure, exactly the
    kind second_look.py warns about. So the halves overlap generously and are
    cut past the midpoint, so every column is whole in at least one image.
    """
    from PIL import Image
    im = Image.open(path)
    if im.mode != "RGB":
        im = im.convert("RGB")
    w, h = im.size
    over = int(w * GUTTER_OVERLAP)
    boxes = [(0, 0, min(w, w // 2 + over), h),
             (max(0, w // 2 - over), 0, w, h)]
    out = []
    for box in boxes:
        part = im.crop(box)
        if part.width > HALF_WIDTH:
            part = part.resize(
                (HALF_WIDTH, int(part.height * HALF_WIDTH / part.width)),
                Image.LANCZOS)
        buf = io.BytesIO()
        part.save(buf, format="JPEG", quality=90)
        out.append(buf.getvalue())
    return out


def read_page(images: list[bytes], model: str, key: str) -> dict:
    labels = ["LEFT PART of the page (serial no., monthly no., date of "
              "receipt, name, address, occupation, and the start of age / "
              "sex / religion):",
              "RIGHT PART of the SAME page (age, sex, religion, diagnosis, "
              "date of commencement of illness, attending physician, date "
              "cured, date died) - the SAME rows, in the SAME order:"]
    parts: list[dict] = [{"text": PROMPT}]
    for label, image in zip(labels, images):
        parts.append({"text": label})
        parts.append({"inline_data": {
            "mime_type": "image/jpeg",
            "data": base64.b64encode(image).decode("ascii")}})
    parts.append({"text": "Now return every row, joining the two halves."})

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
        return {r["page"] for r in csv.DictReader(fh, delimiter="\t")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", default=os.path.join(
        ROOT, "paper", "sources", "isa", "pages", "000i5yq"),
        help="directory of rendered page PNGs")
    ap.add_argument("--pages", help="comma-separated page numbers")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("GOOGLE_API_KEY not set", file=sys.stderr)
        return 2

    files = sorted(glob.glob(os.path.join(args.images, "*.png")))
    if not files:
        print(f"no page images in {args.images}\n"
              f"render them first:\n"
              f"  pdftoppm -r 200 -png paper/sources/isa/000i5yq.pdf "
              f"{args.images}/f", file=sys.stderr)
        return 2

    def pageno(p: str) -> str:
        m = re.search(r"(\d+)\.png$", p)
        return str(int(m.group(1))) if m else os.path.basename(p)

    already = done_pages(OUT_PAGES)
    todo = [f for f in files if pageno(f) not in already]
    if args.pages:
        want = {p.strip() for p in args.pages.split(",")}
        todo = [f for f in files if pageno(f) in want]
    elif args.limit:
        todo = todo[:args.limit]
    elif not args.all:
        todo = todo[:1]

    print(f"{len(files)} pages rendered, {len(already)} already read, "
          f"{len(todo)} to do", file=sys.stderr)

    lock = threading.Lock()
    new_out = not os.path.exists(args.out)
    new_pages = not os.path.exists(OUT_PAGES)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fout = open(args.out, "a", newline="", encoding="utf-8")
    fpag = open(OUT_PAGES, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(fout, fieldnames=["page"] + FIELDS,
                       delimiter="\t", extrasaction="ignore")
    wp = csv.DictWriter(fpag, fieldnames=["page", "rows", "note", "error"],
                        delimiter="\t")
    if new_out:
        w.writeheader()
    if new_pages:
        wp.writeheader()

    def work(path: str):
        pg = pageno(path)
        try:
            got = read_page(halves(path), args.model, key)
        except Exception as e:
            with lock:
                wp.writerow({"page": pg, "rows": 0, "note": "",
                             "error": str(e)[:200]})
                fpag.flush()
            print(f"  page {pg}: FAILED {str(e)[:90]}", file=sys.stderr)
            return
        rows = got.get("rows", [])
        with lock:
            for r in rows:
                rec = {"page": pg}
                rec.update({f: (r.get(f) or "").strip() for f in FIELDS})
                w.writerow(rec)
            wp.writerow({"page": pg, "rows": len(rows),
                         "note": (got.get("page_note") or "")[:300],
                         "error": ""})
            fout.flush()
            fpag.flush()
        print(f"  page {pg}: {len(rows)} rows", file=sys.stderr)

    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(work, todo))

    fout.close()
    fpag.close()
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
