"""Transcribe the nominal infectious-disease returns for Haifa, 1942-44 (ISA 000zbri).

ISA file 000zbri, "Monthly Returns - Infectious Diseases, Haifa", January 1942 -
October 1944, 388 pages, image-only. The file is built of repeating PAIRS:

  (a) a printed DAILY RETURN OF INFECTIOUS DISEASES - a tally by town/village
      and disease: Existing | New cases | Cured | Died (In / Out of Hospital) |
      Remaining. No names.
  (b) its verso, REPORT ON CASES AND DEATHS - a NOMINAL list, one row per
      named case. That is what this script extracts.

The file runs BACKWARDS in time: late 1944 at the front, 1942 at the back.

The nominal form changes across the file. The later (1944, typed) form ends
  ... | Where Treated | When Inoculated or Vaccinated | Date of Onset | Remarks
the earlier (1942-43, handwritten) form inserts an ADMITTED TO HOSPITAL column
and replaces Remarks with a wider
  ... | Date of Onset | Admitted to H. | Bacteriological Exam, Results.
      Disposal of Case & Precautions taken.
Both are captured; `admitted_to_h` is simply empty on the later form.

The KEY COLUMN for this project is `where_treated`. Its values distinguish
"Govt. Hosp." and "Isolation Haifa" from home treatment, and so separate the
cases our admission register can see from the ones it never could.

Design follows pipeline/isa_ledger.py and pipeline/second_look.py, whose
lessons were paid for:
  * temperature 0, low thinking, a response schema, resumable output;
  * the model transcribes what is on the page and flags doubt in `uncertain`
    rather than tidying the record.

ROTATION. Pages are scanned sideways and the direction VARIES page to page -
p.21 is upright at +90, p.20 and p.200 at -90. Tesseract OSD fails on these
sparse forms and a word-count heuristic at 150dpi is a coin-flip. So each page
is sent in BOTH rotations and the model is told to read whichever one is
upright and ignore the other. This costs a second image and removes the silent
failure mode entirely.

NAMES. Unlike the admission registers, names here are NOT redacted - this is a
Mandate government return opened to the public by the ISA. They are
transcribed. The ISA publishing the file is a separate decision from us
republishing it, so the output goes to data/private/, NOT data/public/.

Run:
  python3 pipeline/isa_returns.py --pages 21,25      # named pages
  python3 pipeline/isa_returns.py --limit 20         # first 20 unread
  python3 pipeline/isa_returns.py --all

Needs GOOGLE_API_KEY, and page images rendered beforehand:
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
OUT = os.path.join(ROOT, "data", "private", "isa-1942-44-cases.tsv")
OUT_PAGES = os.path.join(ROOT, "data", "private", "isa-1942-44-pages.tsv")

API = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-3.1-pro-preview"
IMG_WIDTH = 2200
THINKING_LEVEL = "low"
MAX_OUTPUT_TOKENS = 65536

FIELDS = ["disease", "case_ref", "name", "age", "sex", "nationality_religion",
          "residence_period", "source_of_infection", "where_treated",
          "when_inoculated", "date_onset", "admitted_to_h", "remarks",
          "uncertain"]

# Page-level fields: which return this nominal list backs, and what kind of
# page it is at all - most pages in the file are NOT nominal lists.
PAGE_FIELDS = ["page_kind", "return_date", "serial_no", "district", "page_note"]

SCHEMA = {
    "type": "object",
    "properties": {
        "page_kind": {"type": "string"},
        "return_date": {"type": "string"},
        "serial_no": {"type": "string"},
        "district": {"type": "string"},
        "page_note": {"type": "string"},
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {f: {"type": "string"} for f in FIELDS},
            },
        },
    },
    "required": ["page_kind", "rows"],
}

PROMPT = """You are reading one page from a Mandate Department of Health file,
"Monthly Returns - Infectious Diseases, Haifa", January 1942 to October 1944,
and transcribing it.

THE PAGE IS GIVEN TWICE, in two rotations. Exactly ONE of them is upright and
readable. Read that one. Ignore the other completely - do not try to combine
them, and do not report the same row twice.

FIRST, decide what kind of page this is, and put it in `page_kind`:

  "nominal"  - a REPORT ON CASES AND DEATHS: a table with a Name column, one
               row per named person. THIS IS THE ONE THAT MATTERS.
  "daily"    - a DAILY RETURN OF INFECTIOUS DISEASES: a printed tally form with
               columns Town or Village | Diseases | Existing | New cases |
               Cured | Died (In Hospital / Out of Hospital) | Remaining.
               It has NO names. Return `rows` EMPTY for these.
  "blank"    - an empty form, or a blank or near-blank page.
  "other"    - a letter, a monthly summary, a cover, anything else. Say what it
               is in `page_note`.

If `page_kind` is anything but "nominal", return `rows` as an empty list. Do
not invent rows and do not transcribe the daily tally as if it were people.

FOR A NOMINAL PAGE, transcribe EVERY named row. The columns, left to right:

  Disease | Case Reference | Name | Age | Sex | Nationality and Religion |
  Period of Residence in Palestine | Source of Infection | Where Treated |
  When Inoculated or Vaccinated | Date of Onset of Disease | Remarks

THE FORM COMES IN TWO LAYOUTS AND YOU MUST DECIDE WHICH ONE YOU ARE LOOKING AT
BEFORE YOU READ A SINGLE ROW. Count the columns in the printed header.

  LATER form (1944, usually typed) - TWELVE columns, ending:
      ... Where Treated | When Inoculated or Vaccinated | Date of Onset of
      Disease | Remarks.
      Here `admitted_to_h` IS ALWAYS EMPTY.

  EARLIER form (1942-43, usually handwritten) - THIRTEEN columns. It has an
  EXTRA narrow column, and its last column is wider:
      ... Where Treated | When Inoculated or Vaccinated | Date of Onset |
      ADMITTED TO H. | Bacteriological Exam, Results. Disposal of Case &
      Precautions taken. In case of deaths give reference to original report.
      Here `admitted_to_h` holds the admission date and `remarks` holds that
      long last column.

GETTING THIS WRONG SHIFTS EVERY FIELD BY ONE and is the main way this task
fails. The tell is that `where_treated` comes back holding a value that
obviously belongs to Source of Infection, such as "Local" or "Native", while
`source_of_infection` holds a place of treatment such as "Isolation".
If you see that in your own output, you have mis-registered the columns: go
back to the printed header, count again, and re-read the rows.

Read each row by ITS OWN CELL POSITION against the printed header above it, not
by counting non-empty values across - the middle columns are frequently blank
or hold only a dash, and a dash is a value, not a missing cell.

TRANSCRIBE WHAT IS ON THE PAGE. Do not correct it, complete it, or make it
consistent. If a cell is empty, leave it empty. If you cannot read something,
put your best reading in the field and say so in `uncertain`.

Things these returns do, learned from reading them:

* `where_treated` IS THE MOST IMPORTANT COLUMN. Its values include
  "Govt. Hosp.", "Isolation Haifa", "Isolation", "Home", "At home", a private
  hospital's name, or a village. Transcribe it EXACTLY as written, including
  abbreviations - never expand "Govt. Hosp." and never normalise "Isolation
  Haifa" to "Isolation". If it is blank, leave it blank; blank is a fact.
* DITTO MARKS are everywhere - " or -do- or a repeated quote sign, meaning
  "same as the row above". EXPAND them: write the value they stand for, taken
  from the nearest row above that has a value in that column. This matters most
  in `disease`, `where_treated`, `source_of_infection` and `case_ref`.
  If you expanded a ditto and are not sure what it referred to, say so in
  `uncertain`.
* `case_ref` looks like "Rep.A.1", "A.2", "R.A", "R.B" - a letter keying the
  case to the daily return this page is the verso of, plus a number. Keep it.
* `disease` is a notifiable disease: typhoid, paratyphoid, bubonic plague,
  smallpox, murine typhus, undulant fever, erysipelas, dysentery, measles,
  scarlet fever, C.S.M. (cerebro-spinal meningitis), anthrax, poliomyelitis,
  whooping cough, cerebro-spinal fever. Keep any qualifier in brackets.
* `nationality_religion` is one cell holding both, e.g. "Palest.Jew",
  "Moslem Native", "Pal. Moslem", "Christian", "British". Transcribe the whole
  cell as one string, as written.
* `age` is written like "45y", "10m", "35". Keep the unit letter if it is there.
* `remarks` carries the bacteriology and the outcome, e.g. "B. Pestis +",
  "patient died", "Widal +", "Patient cured", "-do-". This is where a DEATH is
  usually recorded. Transcribe it in full and expand any ditto.
* Dates are written 9.8.44, 6.8.44, 11/2, 30/1. Transcribe the form used; do
  not convert it and do not add a year that is not written.

For the page as a whole, also record from the form's own printed heading, if
present: `return_date`, `serial_no` and `district`. `return_date` must be A
DATE AND NOTHING ELSE, copied as written ("15.8.44", "11 VIII 44"); if the page
carries no date in its heading, LEAVE IT EMPTY - never put a title, a
description or a sentence there. `serial_no` is the bare Serial No. of the
return. `district` is usually Haifa. These headings are usually on the DAILY
RETURN recto rather than on the nominal verso, so on a nominal page they are
often simply absent - leave them empty rather than guessing.

Use `page_note` for anything true of the page as a whole - a heading, a change
of year, a torn or stained area, a marginal annotation, a column left blank
throughout, or a page you could not orient.

Keep `uncertain` SHORT - a few words, only when a reading is genuinely in
doubt. Leave it empty otherwise. Do not restate the row in it."""


def rotations(path: str) -> list[bytes]:
    """Return the page rotated +90 and -90, as JPEGs.

    The scans are sideways and the direction is not consistent across the file.
    Tesseract OSD refuses these pages ("Too few characters") and an OCR
    word-count heuristic at readable dpi does not separate them reliably, so
    both rotations go to the model and it picks.
    """
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
    parts.append({"text": "Now classify the page and return its rows."})

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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", default=os.path.join(
        ROOT, "paper", "sources", "isa", "pages", "000zbri"),
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
              f"  pdftoppm -r 200 -png paper/sources/isa/000zbri.pdf "
              f"{args.images}/p", file=sys.stderr)
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
    w = csv.DictWriter(
        fout, fieldnames=["page", "return_date", "serial_no"] + FIELDS,
        delimiter="\t", extrasaction="ignore")
    wp = csv.DictWriter(
        fpag, fieldnames=["page", "rows"] + PAGE_FIELDS + ["error"],
        delimiter="\t", extrasaction="ignore")
    if new_out:
        w.writeheader()
    if new_pages:
        wp.writeheader()

    def work(path: str):
        pg = pageno(path)
        try:
            got = read_page(rotations(path), args.model, key)
        except Exception as e:
            with lock:
                wp.writerow({"page": pg, "rows": 0, "page_kind": "",
                             "error": str(e)[:200]})
                fpag.flush()
            print(f"  page {pg}: FAILED {str(e)[:90]}", file=sys.stderr)
            return
        rows = got.get("rows", [])
        kind = (got.get("page_kind") or "").strip()
        with lock:
            for r in rows:
                rec = {"page": pg,
                       "return_date": (got.get("return_date") or "").strip(),
                       "serial_no": (got.get("serial_no") or "").strip()}
                rec.update({f: (r.get(f) or "").strip() for f in FIELDS})
                w.writerow(rec)
            prow = {"page": pg, "rows": len(rows), "error": ""}
            for f in PAGE_FIELDS:
                prow[f] = (got.get(f) or "").strip()[:300]
            wp.writerow(prow)
            fout.flush()
            fpag.flush()
        print(f"  page {pg}: {kind}, {len(rows)} rows", file=sys.stderr)

    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(work, todo))

    fout.close()
    fpag.close()
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
