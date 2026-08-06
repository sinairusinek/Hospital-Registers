"""Second classification pass over the diagnoses the first one never reached.

The bulk of the corpus was coded by the prompt in
pipeline/prompts/diagnoses-icd9-v1.md. Some records came back with no code —
not because the diagnosis was hard, but because the classifier never saw it:
the original pass ran on GPT-4o and hit a rate limit, and on five records its
429 error text was written into the diagnosis field instead of a diagnosis.

This sends the same prompt over the distinct diagnosis strings that still carry
no ICD-9 code, so the column keeps one provenance rather than two.

What it does *not* do is write into the artifact. It writes

  data/public/diagnosis-classification.tsv

which is committed, reviewable, and read by build.py. So the artifact stays
reproducible without an API key, every code the second pass proposed can be
read next to the string it came from, and a code that is wrong can be struck
out by editing one line rather than by re-running anything.

Run: GOOGLE_API_KEY=... python3 pipeline/classify_diagnoses.py [--limit N]
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "data" / "public" / "hospital-registers-normalized.tsv"
PROMPT = ROOT / "pipeline" / "prompts" / "diagnoses-icd9-v1.md"
OUTPUT = ROOT / "data" / "public" / "diagnosis-classification.tsv"

MODEL = "gemini-2.5-pro"

# Small enough that a truncated or malformed reply costs one batch, not the run,
# and that each batch stays well inside the model's output limit.
BATCH = 40

COLUMNS = [
    "Original-Diagnosis",
    "Primary-ICD9",
    "Primary-ICD9-Name",
    "Primary-Confidence",
    "Additional-ICD9",
    "Additional-ICD9-Name",
    "Additional-Confidence",
    "Frequency",
]

# Strings that are not diagnoses at all and must never be sent for coding: an
# outcome that landed in the wrong column, the classifier's own error text, a
# stray header. build.py flags each of these separately; sending them would
# invite the model to invent a code for "Cured".
NOT_A_DIAGNOSIS = re.compile(
    r"^(cured|died|recovered|improved|relieved|unimproved|discharged|transferred"
    r"|dead|not improved|escaped)\W*$"
    r"|validation error|error code:|^diagnosis$|^[-?.\s]*$",
    re.IGNORECASE,
)


def uncoded_diagnoses() -> Counter[str]:
    """Distinct diagnosis strings in the artifact that carry no ICD-9 code."""
    counts: Counter[str] = Counter()
    with ARTIFACT.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE):
            if (row.get("ICD-9 Code") or "").strip():
                continue
            written = (row.get("Diagnosis as written") or "").strip()
            if not written or NOT_A_DIAGNOSIS.search(written):
                continue
            counts[written] += 1
    return counts


def load_existing() -> dict[str, dict[str, str]]:
    """Rows already in the output file, so a re-run only fills what is missing."""
    if not OUTPUT.exists():
        return {}
    with OUTPUT.open(newline="", encoding="utf-8") as handle:
        return {
            (row["Original-Diagnosis"] or "").strip(): row
            for row in csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)
            if (row.get("Original-Diagnosis") or "").strip()
        }


def parse_reply(text: str, expected: set[str]) -> list[dict[str, str]]:
    """Pull TSV rows out of the reply, keeping only diagnoses we asked about.

    The model is asked for TSV and generally gives it, sometimes wrapped in a
    fence and sometimes with the header repeated. Rather than trust the shape,
    every line is matched back to a string that was actually sent — anything
    else is a hallucinated row and is dropped.
    """
    rows = []
    for line in text.splitlines():
        line = line.strip().strip("`")
        if not line or line.lower().startswith("index\t"):
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        # The prompt puts a sequential index first; the diagnosis follows it.
        diagnosis = parts[1].strip()
        if diagnosis not in expected:
            continue
        record = dict(zip(COLUMNS, [p.strip() for p in parts[1:]]))
        rows.append(record)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="only the N commonest, for a trial run")
    args = parser.parse_args()

    if not os.environ.get("GOOGLE_API_KEY"):
        print("GOOGLE_API_KEY is not set.", file=sys.stderr)
        return 1
    if not ARTIFACT.exists():
        print(f"Artifact not found: {ARTIFACT}\nRun: python3 pipeline/build.py", file=sys.stderr)
        return 1

    from google import genai

    # Anything already answered stays answered. Without this the file would be
    # rewritten from scratch each run, and since build.py applies its codes to
    # the artifact, a string classified last time is no longer uncoded this time
    # and would silently drop out of the very file that supplies its code.
    existing = load_existing()
    counts = uncoded_diagnoses()
    pending = Counter({d: n for d, n in counts.items() if d not in existing})
    items = pending.most_common(args.limit or None)
    if existing:
        print(f"{len(existing)} already in {OUTPUT.name}, left as they are")
    print(f"{len(items)} distinct diagnoses to classify, {sum(n for _, n in items):,} records")

    prompt = PROMPT.read_text(encoding="utf-8").split("---", 1)[1].strip()
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    results: dict[str, dict[str, str]] = {}
    for start in range(0, len(items), BATCH):
        batch = items[start : start + BATCH]
        expected = {d for d, _ in batch}
        payload = "\n".join(f"{i + 1},{d},{n}" for i, (d, n) in enumerate(batch))
        try:
            reply = client.models.generate_content(
                model=MODEL,
                contents=f"{prompt}\n\n{payload}",
            )
            rows = parse_reply(reply.text or "", expected)
        except Exception as error:  # noqa: BLE001 — one bad batch must not end the run
            print(f"  batch {start // BATCH + 1}: {type(error).__name__}: {error}", file=sys.stderr)
            continue
        for row in rows:
            results[row["Original-Diagnosis"]] = row
        print(f"  batch {start // BATCH + 1}/{(len(items) + BATCH - 1) // BATCH}: "
              f"{len(rows)}/{len(batch)} classified")

    coded = sum(1 for r in results.values() if r.get("Primary-ICD9"))
    # Written by hand, like the artifact: the registers carry bare double quotes
    # (inches, gershayim) and quoting them here would make this file the one
    # place in the pipeline that escapes them.
    def cell(value: object) -> str:
        return re.sub(r"[\t\r\n]+", " ", str(value or "")).strip()

    merged = dict(existing)
    for diagnosis, _ in items:
        row = results.get(diagnosis)
        merged[diagnosis] = (row if row
                             else dict(zip(COLUMNS, [diagnosis, "", "", "", "", "", "", counts[diagnosis]])))

    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\t".join(COLUMNS) + "\n")
        for diagnosis in sorted(merged):
            handle.write("\t".join(cell(merged[diagnosis].get(c, "")) for c in COLUMNS) + "\n")

    print(f"\n{len(results)} of {len(items)} strings answered, {coded} carry a code")
    print(f"wrote {OUTPUT.relative_to(ROOT)} — review it before rebuilding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
