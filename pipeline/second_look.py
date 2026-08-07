"""Read the register pages again, and say where the dataset departs from them.

The extraction read each page once. This reads them a second time, from the
IIIF scans (see pipeline/iiif_pages.py), and writes

  data/public/second-look.tsv        one row per disagreement, for a human
  data/public/second-look-pages.tsv  one row per page: rows found vs rows held

Nothing is corrected here and the dataset is never written to. The output is
evidence — a claim about what the page says, with the scan URL to check it
against. Accepting a claim is a separate, deliberate act.

Two decisions govern the design, both taken from the pilot of 2026-08-06
(10 pages read by hand; see the notes in PROMPT below):

  * The model transcribes **blind**. It is never shown the dataset's values
    for the page it is reading, because a model shown an answer tends to
    confirm it. The comparison is done here, in code, where it is auditable.

  * It reads **every row of the page**, not the flagged cells. The pilot's
    worst finding — a whole ward column misread — carried no flag at all,
    and two diagnosis misreadings on a single page were both unflagged. A
    pass restricted to the review queues would have found none of it.

Run:
  python3 pipeline/second_look.py --list-models
  python3 pipeline/second_look.py --pages 11:34,1:3          # named pages
  python3 pipeline/second_look.py --flagged --limit 50       # flag-dense first
  python3 pipeline/second_look.py --all                      # all 2,547 pages

Needs GOOGLE_API_KEY in the environment. Resumable: pages already in the
output are skipped, so an interrupted run continues where it stopped.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = os.path.join(ROOT, "data", "public", "iiif-pages.tsv")
DATASET = os.path.join(ROOT, "data", "public", "hospital-registers-normalized.tsv")
OUT = os.path.join(ROOT, "data", "public", "second-look.tsv")
OUT_PAGES = os.path.join(ROOT, "data", "public", "second-look-pages.tsv")
CACHE = os.path.join(ROOT, "data", "private", "page-cache")

API = "https://generativelanguage.googleapis.com/v1beta"
# The pilot's task is adjudication, not bulk OCR: deciding between two readings
# of a date on the strength of the clerk's own day-count is reasoning work, so
# the default is a Pro model. --model swaps it; --benchmark scores one against
# pages that have been read by hand.
DEFAULT_MODEL = "gemini-3.1-pro-preview"

# Resolution is what decides whether this works at all, and the failures are
# quiet ones - not garbled text but missing rows and empty columns.
#
# The spread photographed whole is ~10,000px of two pages side by side. Sent as
# one image it is downsampled past reading: at 1500px the model returned two of
# notebook 11's eleven rows, and at 3000px it read notebook 1 page 3's register
# numbers and ages correctly while returning the entire right-hand page empty -
# that notebook's plate is wider, so the same output width buys less of it.
#
# So each half is sent as its own image. The model gets twice the pixels per
# page, the halves carry a small overlap so a row straddling the gutter is
# whole in both, and it is told they are the same rows in the same order.
HALF_WIDTH = 2000
GUTTER_OVERLAP = 0.02

# Reading a page is transcription, not deduction, and unbounded thinking eats
# the whole budget: 62,912 thinking tokens on one page, MAX_TOKENS, no rows.
# At "low" the same page returns all eleven rows and still checks the clerk's
# day-count against the dates, which is the only reasoning this task needs.
THINKING_LEVEL = "low"
# Generous, because the cost of being wrong here is a page abandoned after five
# attempts: notebook 1 page 32 hit MAX_TOKENS on every one of them at 32k.
MAX_OUTPUT_TOKENS = 65536


PROMPT = """You are reading one page of a hospital admission register from the
Government Hospital in Haifa, 1930-1948, and transcribing every row on it.

The page is a two-page spread photographed as one image. A single patient's
record runs across both halves: the register number, age, sex, religion and
nationality, occupation, address and next of kin on the left; the ward, class
and rate, dates, days in hospital, diagnosis, result, bill number and remarks
on the right. Read each row straight across.

TRANSCRIBE WHAT IS ON THE PAGE. Do not correct it, complete it, or make it
consistent. If the clerk wrote a date that cannot be right, write down what
the clerk wrote. If a cell is empty, leave it empty. If you cannot read
something, put your best reading in the field and say so in `uncertain`.

THE NAME COLUMN IS REDACTED and must stay that way. It is covered by a solid
orange or black band. Never transcribe a patient's name, and never guess one
from the next-of-kin column. If a name is visible through an incomplete
redaction, leave the field empty and note it in `uncertain`.

Things this register does, learned from reading it:

* The ward is abbreviated: `Is.` isolation, `Surg.` surgical, `Med.` medical,
  `Mat.` maternity, `Br.` British section, `Gen.` general, `C.` children's.
  `Gen.` is GENERAL. This hospital had no gynaecology ward, and an earlier
  pass misread thousands of these. If you believe you see a gynaecological
  ward, look again and say what letters are actually there.
* Months are sometimes lowercase roman numerals: `1.iv.30` is 1 April 1930,
  not "1.V.30". Read `iv`, `vi`, `ix`, `xi` carefully - they are easily
  confused with each other and with digits.
* The days-in-hospital column is the clerk's own count of the stay, and it is
  the best check you have on the two dates. When your reading of the dates
  does not produce the number in that column, look at all three again. Say in
  `uncertain` when they still disagree after a second look - the clerk did
  sometimes miscount, and that is a fact about the register worth recording.
* Register numbers run in sequence down the page. Transcribe the number that
  is actually printed on each row. NEVER renumber a row to fit the run: if the
  page jumps from 3308 to 3319, write 3319. A misread number is exactly what
  this pass is looking for.
* Results include `I.S.Q.` (in statu quo - unchanged), `Refused treatment`,
  and transfers such as `Transferred to Sarafand Military Hospital`. These are
  outcomes; record them in `result`, not in the remarks.
* Some rows are not ordinary admissions - a cross-reference (`See Entry No.
  4445`), a patient who refused to stay, a death on admission. They are still
  rows of the register. Transcribe them, with whatever they carry, and
  describe them in `uncertain`.

The spread is given as TWO images. The first is the left-hand page - register
number, age, sex, religion and nationality, occupation, address, next of kin.
The second is the right-hand page - ward, class and rate, the two dates, days
in hospital, diagnosis, result, bill number, remarks. They hold the SAME rows
in the SAME order: the first row of the first image is the first row of the
second. Join them into one row each. The halves overlap slightly, so a column
appearing at the edge of both is one column, not two. Not every notebook has
every column - the earliest have no ward at all - and a column the form does
not have is simply empty.

Return every row on the page, in the order they appear, top to bottom."""


SCHEMA = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "serial": {"type": "string", "description": "Register number exactly as printed"},
                    "age": {"type": "string"},
                    "age_unit": {"type": "string", "description": "years, months, weeks or days"},
                    "sex": {"type": "string"},
                    "religion": {"type": "string"},
                    "nationality": {"type": "string"},
                    "occupation": {"type": "string"},
                    "address": {"type": "string"},
                    "next_of_kin": {"type": "string"},
                    "ward": {"type": "string"},
                    "klass": {"type": "string", "description": "Class: 1st, 2nd, 3rd"},
                    "rate": {"type": "string", "description": "Rate or Gratis/Free"},
                    "admission": {"type": "string", "description": "As written, e.g. 16.3.35"},
                    "discharge": {"type": "string"},
                    "days": {"type": "string"},
                    "diagnosis": {"type": "string"},
                    "result": {"type": "string"},
                    "bill": {"type": "string"},
                    "remarks": {"type": "string"},
                    "uncertain": {
                        "type": "string",
                        "description": "What was hard to read, what disagrees with what, "
                                       "what kind of row this is. Empty if the row is plain.",
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "How legible this row was overall",
                    },
                },
                "required": ["serial", "confidence"],
            },
        },
        "page_note": {
            "type": "string",
            "description": "Anything about the page as a whole: damage, a column "
                           "shifted, a heading, rows crossed out.",
        },
    },
    "required": ["rows"],
}


# The dataset column each transcribed field is checked against. Fields with no
# entry here are reported only when the dataset holds nothing and the page does.
FIELD_MAP = {
    "age": "Age",
    "sex": "Sex",
    "religion": "Religion as written",
    "nationality": "Nationality as written",
    "occupation": "Occupation",
    "address": "Address",
    "ward": "Ward as written",
    "klass": "Class as written",
    "rate": "Rate as written",
    "admission": "Admission Date as written",
    "discharge": "Discharge Date as written",
    "days": "Days in Hospital as written",
    "diagnosis": "Diagnosis as written",
    "result": "Result as written",
}

# Fields where a difference is worth a person's time. Address and occupation
# vary in wording constantly and would drown the file; they are reported only
# when the dataset is empty and the page is not.
SUBSTANTIVE = {"age", "sex", "religion", "nationality", "ward", "klass",
               "admission", "discharge", "days", "diagnosis", "result"}

WARD_FORMS = {
    "is": "isolation", "isol": "isolation",
    "surg": "surgical",
    "med": "medical",
    "mat": "maternity",
    "br": "british section",
    "gen": "general",
    "c": "children's",
}

WARD_CANONICAL = ["british section", "infectious diseases", "venereal diseases",
                  "isolation", "surgical", "medical", "maternity", "general",
                  "children's"]


def ward_key(value: str) -> str:
    """The ward a value names, however much else it carries.

    The model sometimes returns the whole right-hand row in this field -
    "Gen. 3rd Gratis 22.1.38 ..." - which is a reading of the ward that is
    perfectly correct and would otherwise be reported as a disagreement with
    the dataset's "General". Only the ward at the front is compared.
    """
    v = norm(value)
    if not v:
        return ""
    for name in WARD_CANONICAL:
        if v.startswith(name):
            return name
    head = v.split()[0]
    return WARD_FORMS.get(head, v)


def norm(value: str) -> str:
    """Compare on substance: case, punctuation and spacing are not differences."""
    v = (value or "").strip().lower()
    v = v.replace("&", "and")
    v = re.sub(r"[.,;:()\[\]'\"]+", " ", v)
    v = re.sub(r"\s+", " ", v).strip()
    return v


def norm_field(field: str, value: str) -> str:
    if field == "ward":
        return ward_key(value)
    v = norm(value)
    if field == "sex":
        if v.startswith("m"):
            return "male"
        if v.startswith("f"):
            return "female"
    elif field in ("admission", "discharge"):
        # 16.3.35, 16/3/35 and 1935-03-16 are the same date differently written.
        iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", v)
        if iso:
            y, m, d = iso.groups()
            return f"{int(d)}.{int(m)}.{int(y) % 100}"
        parts = re.split(r"[./\-]", v)
        if len(parts) == 3 and all(p.strip().isdigit() for p in parts):
            d, m, y = (int(p) for p in parts)
            return f"{d}.{m}.{y % 100}"
    elif field in ("age", "days", "klass"):
        digits = re.sub(r"\D", "", v)
        return digits or v
    return v


def load_pages() -> dict[tuple[str, str], dict]:
    with open(PAGES, encoding="utf-8") as fh:
        return {(r["Notebook_Number"], r["Page_Number"]): r
                for r in csv.DictReader(fh, delimiter="\t")}


def load_dataset() -> dict[tuple[str, str], list[dict]]:
    rows: dict[tuple[str, str], list[dict]] = {}
    with open(DATASET, encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            key = ((r.get("Notebook_Number") or "").strip(),
                   (r.get("Page_Number") or "").strip())
            if key[0] and key[1]:
                rows.setdefault(key, []).append(r)
    return rows


def fetch_halves(meta: dict, notebook: str, page: str) -> list[bytes]:
    """The two pages of the spread, each at its own resolution."""
    os.makedirs(CACHE, exist_ok=True)
    width, height = int(meta["width"]), int(meta["height"])
    half = width // 2
    over = int(width * GUTTER_OVERLAP)
    regions = [(0, 0, half + over, height),
               (half - over, 0, width - half + over, height)]

    out = []
    for side, (x, y, w, h) in enumerate(regions):
        # Keyed by width and side: a cache filled at one size or layout must
        # not be served for another.
        path = os.path.join(
            CACHE, f"nb{int(notebook):02d}_p{int(page):03d}_{HALF_WIDTH}_{side}.jpg")
        if os.path.exists(path) and os.path.getsize(path) > 20000:
            with open(path, "rb") as fh:
                out.append(fh.read())
            continue
        url = f"{meta['image_service']}/{x},{y},{w},{h}/{HALF_WIDTH},/0/default.jpg"
        for attempt in range(4):
            try:
                with urllib.request.urlopen(url, timeout=180) as r:
                    data = r.read()
                with open(path, "wb") as fh:
                    fh.write(data)
                out.append(data)
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2 * (attempt + 1))
    return out


def read_page(halves: list[bytes], model: str, key: str) -> dict:
    # Each image is labelled in its own right. With both following a single
    # block of text the model bound only the first, and returned page after
    # page of register numbers and ages with the right-hand page blank.
    labels = ["LEFT-HAND PAGE (register number, age, sex, religion and "
              "nationality, occupation, address, next of kin):",
              "RIGHT-HAND PAGE (ward, class and rate, date of admission, date "
              "of discharge, days in hospital, diagnosis, result, bill, "
              "remarks) - the SAME rows, in the SAME order:"]
    parts: list[dict] = [{"text": PROMPT}]
    for label, image in zip(labels, halves):
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
            candidate = payload["candidates"][0]
            # A page that ran out of budget comes back with no rows and no
            # error. Say so rather than recording it as an empty page, which
            # would read as "the register holds nothing here".
            if candidate.get("finishReason") not in (None, "STOP"):
                raise RuntimeError(f"model stopped early: {candidate['finishReason']}")
            text = candidate["content"]["parts"][0]["text"]
            return json.loads(text)
        except urllib.error.HTTPError as e:
            # 429 and 5xx are worth waiting out; a 400 will not improve.
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


def compare(notebook: str, page: str, seen: dict, held: list[dict],
            image_url: str) -> tuple[list[dict], dict]:
    """Diff one page's reading against the dataset. Returns (findings, summary)."""
    findings: list[dict] = []
    rows = seen.get("rows") or []
    by_serial = {norm(r.get("serial", "")): r for r in rows if r.get("serial")}
    held_by_serial = {norm((h.get("Notebook Record ID") or "")): h for h in held}

    def finding(serial, field, was, now, verdict, note, confidence=""):
        findings.append({
            "Notebook_Number": notebook, "Page_Number": page,
            "serial": serial, "field": field,
            "dataset_value": was, "page_value": now,
            "verdict": verdict, "confidence": confidence,
            "note": note, "scan": image_url,
        })

    # Rows the page carries and the dataset does not, and the reverse. The page
    # is the authority on which rows exist; a serial only in the dataset is
    # usually a misreading of one that is on the page.
    for serial in by_serial.keys() - held_by_serial.keys():
        r = by_serial[serial]
        finding(r.get("serial", ""), "(row)", "", r.get("diagnosis", ""),
                "row-missing-from-dataset",
                f"On the page, absent from the dataset. {r.get('uncertain','')}".strip(),
                r.get("confidence", ""))
    for serial in held_by_serial.keys() - by_serial.keys():
        h = held_by_serial[serial]
        finding(h.get("Notebook Record ID", ""), "(row)",
                (h.get("Diagnosis as written") or ""), "",
                "row-not-on-page",
                "In the dataset, no such register number on the page - "
                "check whether its number was misread.")

    for serial in by_serial.keys() & held_by_serial.keys():
        r, h = by_serial[serial], held_by_serial[serial]
        for field, column in FIELD_MAP.items():
            was = (h.get(column) or "").strip()
            now = (r.get(field) or "").strip()
            if not was and not now:
                continue
            if norm_field(field, was) == norm_field(field, now):
                continue
            if not was:
                # The dataset holds nothing and the page does: a recovery,
                # and worth reporting for every column including the free-text
                # ones, where whole occupations and addresses went missing.
                verdict = "dataset-empty"
            elif field not in SUBSTANTIVE:
                # Wording drift, and blanks the model simply did not fill,
                # are not evidence of anything in the free-text columns.
                continue
            elif not now:
                verdict = "page-empty"
            else:
                verdict = "differs"
            finding(r.get("serial", ""), column, was, now, verdict,
                    r.get("uncertain", ""), r.get("confidence", ""))

    summary = {
        "Notebook_Number": notebook, "Page_Number": page, "status": "read",
        "rows_on_page": len(rows), "rows_in_dataset": len(held),
        "findings": len(findings),
        "low_confidence_rows": sum(1 for r in rows if r.get("confidence") == "low"),
        "page_note": (seen.get("page_note") or "").replace("\t", " "),
        "scan": image_url,
    }
    return findings, summary


FINDING_COLUMNS = ["Notebook_Number", "Page_Number", "serial", "field",
                   "dataset_value", "page_value", "verdict", "confidence",
                   "note", "scan"]
SUMMARY_COLUMNS = ["Notebook_Number", "Page_Number", "status", "rows_on_page",
                   "rows_in_dataset", "findings", "low_confidence_rows",
                   "page_note", "scan"]

# A read that comes back thin has not found an emptier register - it has
# failed, and quietly. Two shapes of this, both seen in testing:
#
#   too few rows      notebook 32 page 7 returned one row of twelve, which the
#                     comparison would have published as eleven records that
#                     are not on the page: eleven confident falsehoods.
#   rows with no page notebook 18 page 65 returned all eleven rows with the
#                     right-hand page blank - correct register numbers and
#                     ages, then nothing - and that would have been published
#                     as eighty-six columns the register supposedly leaves
#                     empty.
#
# Neither is a finding about the register. Below these ratios the page is
# recorded as unread and nothing is taken from it.
COMPLETE_ENOUGH = 0.6
FILLED_ENOUGH = 0.6


def already_done(summary_path: str) -> set[tuple[str, str]]:
    """Pages that have been read.

    Read from the page summary rather than the findings, so that a page which
    genuinely disagrees with nothing still counts as done - and so that a page
    left unread on a thin read does not. Running the command again therefore
    converges on the pages the model has been failing to read.
    """
    if not os.path.exists(summary_path):
        return set()
    with open(summary_path, encoding="utf-8") as fh:
        return {(r["Notebook_Number"], r["Page_Number"])
                for r in csv.DictReader(fh, delimiter="\t")
                if r.get("status") == "read"}


def select(args, pages, dataset) -> list[tuple[str, str]]:
    if args.pages:
        wanted = []
        for token in args.pages.split(","):
            nb, _, pg = token.partition(":")
            key = (nb.strip(), pg.strip())
            if key not in pages:
                print(f"no scan for notebook {key[0]} page {key[1]}", file=sys.stderr)
            else:
                wanted.append(key)
        return wanted

    keys = [k for k in pages if k in dataset]
    if args.notebook:
        keys = [k for k in keys if k[0] == str(args.notebook)]
    if args.flagged:
        def flags(key):
            return sum(1 for r in dataset[key] if (r.get("Review Flags") or "").strip())
        keys = [k for k in keys if flags(k)]
        keys.sort(key=lambda k: (-flags(k), int(k[0]), int(k[1])))
    else:
        keys.sort(key=lambda k: (int(k[0]), int(k[1])))
    return keys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--pages", help="explicit list, e.g. 11:34,1:3")
    ap.add_argument("--notebook", type=int, help="every page of one notebook")
    ap.add_argument("--flagged", action="store_true",
                    help="only pages carrying review flags, densest first")
    ap.add_argument("--all", action="store_true", help="every page with a scan")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--list-models", action="store_true")
    args = ap.parse_args()

    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key:
        print("GOOGLE_API_KEY is not set", file=sys.stderr)
        return 2

    if args.list_models:
        with urllib.request.urlopen(f"{API}/models?key={key}&pageSize=200", timeout=60) as r:
            payload = json.load(r)
        for m in payload.get("models", []):
            if "generateContent" in m.get("supportedGenerationMethods", []):
                print(m["name"].split("/")[-1])
        return 0

    pages, dataset = load_pages(), load_dataset()
    keys = select(args, pages, dataset)
    summary_path = (args.out.replace(".tsv", "-pages.tsv")
                    if args.out != OUT else OUT_PAGES)
    done = already_done(summary_path)
    keys = [k for k in keys if k not in done]
    if not args.all and not args.pages:
        keys = keys[:args.limit]
    if not keys:
        print("nothing to do - every selected page is already in the output")
        return 0

    print(f"{len(keys)} page(s), model {args.model}, {args.workers} at a time")
    if done:
        print(f"({len(done)} already read, skipped)")

    lock = threading.Lock()
    counts = Counter()
    fresh = not os.path.exists(args.out)

    with open(args.out, "a", newline="", encoding="utf-8") as fh, \
         open(summary_path, "a", newline="", encoding="utf-8") as sfh:
        w = csv.DictWriter(fh, fieldnames=FINDING_COLUMNS, delimiter="\t",
                           lineterminator="\n", extrasaction="ignore")
        sw = csv.DictWriter(sfh, fieldnames=SUMMARY_COLUMNS, delimiter="\t",
                            lineterminator="\n", extrasaction="ignore")
        if fresh:
            w.writeheader()
        if os.path.getsize(summary_path) == 0:
            sw.writeheader()

        def work(k):
            notebook, page = k
            meta = pages[k]
            held = dataset.get(k, [])
            url = f"{meta['image_service']}/full/2000,/0/default.jpg"

            def thin(seen) -> bool:
                rows = seen.get("rows") or []
                if len(held) >= 4 and len(rows) < COMPLETE_ENOUGH * len(held):
                    return True
                if not rows:
                    return True
                # The right-hand page is where the register says what happened;
                # rows carrying none of it were not read, whatever their count.
                filled = sum(1 for r in rows if any(
                    (r.get(f) or "").strip()
                    for f in ("admission", "discharge", "days", "diagnosis", "result")))
                return filled < FILLED_ENOUGH * len(rows)

            try:
                halves = fetch_halves(meta, notebook, page)
                seen = read_page(halves, args.model, key)
                # More attempts when the read comes back thin: the failure is
                # intermittent, and a later pass usually lands.
                for _ in range(2):
                    if not thin(seen):
                        break
                    seen = read_page(halves, args.model, key)
            except Exception as e:
                with lock:
                    counts["failed"] += 1
                    print(f"  nb{notebook} p{page}: FAILED {type(e).__name__}: {e}",
                          file=sys.stderr)
                return

            rows_read = len(seen.get("rows") or [])
            if thin(seen):
                with lock:
                    counts["incomplete"] += 1
                    sw.writerow({
                        "Notebook_Number": notebook, "Page_Number": page,
                        "status": "incomplete", "rows_on_page": rows_read,
                        "rows_in_dataset": len(held), "findings": 0,
                        "low_confidence_rows": "",
                        "page_note": "the read came back thin - too few rows, or "
                                     "rows with the right-hand page blank; nothing "
                                     "taken from this page",
                        "scan": url,
                    })
                    sfh.flush()
                    print(f"  nb{notebook} p{page}: thin read ({rows_read} rows "
                          f"for {len(held)} records) - page left unread")
                return

            findings, summary = compare(notebook, page, seen, held, url)
            with lock:
                for row in findings:
                    w.writerow(row)
                sw.writerow(summary)
                fh.flush()
                sfh.flush()
                counts["pages"] += 1
                counts["findings"] += len(findings)
                for row in findings:
                    counts[row["verdict"]] += 1
                print(f"  nb{notebook} p{page}: {summary['rows_on_page']} rows read, "
                      f"{len(findings)} finding(s)")

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(work, keys))

    print(f"\n{counts['pages']} page(s) read, {counts['incomplete']} left unread, "
          f"{counts['failed']} failed")
    print(f"{counts['findings']} finding(s) -> {os.path.relpath(args.out, ROOT)}")
    for verdict in ("differs", "dataset-empty", "page-empty",
                    "row-missing-from-dataset", "row-not-on-page"):
        if counts[verdict]:
            print(f"  {counts[verdict]:6d}  {verdict}")
    print(f"page summaries    -> {os.path.relpath(summary_path, ROOT)}")
    print("\nNothing has been changed in the dataset. Every row above is a claim "
          "about the page, with the scan beside it to check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
