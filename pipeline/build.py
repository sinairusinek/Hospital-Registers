"""Build the published artifact from the consolidated TSV.

Reads data/public/hospital-registers-<date>.tsv and writes

  data/public/hospital-registers-normalized.tsv   the artifact the site loads
  data/public/normalization-report.tsv            every change, with counts

The source file is never modified: it stays the record of what the registers
say. Everything here is a second pass over the `standardized *` columns, which
the extraction produced but did not fully reconcile.

Two principles govern the rules below:

  * Merge only orthographic variants of the same term — Moslem/Muslim,
    Poland/Polish, Mat./Maternity. Compound designations that carry meaning
    ("Palestinian British", "Palestinian Syrian") stay distinct.
  * Never guess. Values that are ambiguous, illegible, or plainly stray
    ("Byzage", "Lincoln", "Police 12291") pass through untouched and are
    listed in the report as unresolved.

Run: python3 pipeline/build.py
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "public" / "hospital-registers-2025-08-10.tsv"
OUTPUT = ROOT / "data" / "public" / "hospital-registers-normalized.tsv"
REPORT = ROOT / "data" / "public" / "normalization-report.tsv"

# Column 45 lost its header in the source spreadsheets. By position (between
# origPrimICD9Name and Additional-ICD9) and content (ICD-9 labels, filled for
# 28,107 records against origPrimICD9Name's 18,971) it is the standardized
# ICD-9 name for the primary diagnosis.
HEADER_FIXES = {"<info@doctorsonly.co.i": "standardPrimaryICD9Name"}

# Where a field exists twice — once as the clerk wrote it, once cleaned — the
# plain name goes to the cleaned column and the verbatim one is marked "as
# written". Applied when writing, so the rules above keep their source names.
COLUMN_RENAMES = {
    "Days in Hospital (Rep)": "Days in Hospital as written",
    "Days in Hospital (Calc)": "Days in Hospital",
    "Admission Date (Orig)": "Admission Date as written",
    "Admission Date [ISO]": "Admission Date",
    "Discharge Date (Orig)": "Discharge Date as written",
    "Discharge Date (ISO)": "Discharge Date",
    "Religion": "Religion as written",
    "standardized Religion": "Religion",
    "Nationality": "Nationality as written",
    "StandardNationality": "Nationality",
    "Ward": "Ward as written",
    "standardized ward": "Ward",
    "Class": "Class as written",
    "Class standard": "Class",
    "Rate": "Rate as written",
    "rateStandard": "Rate",
    "Original Result": "Result as written",
    "Standardized Result": "Result",
    # Diagnosis is a three-column case. `Standardized Diagnosis` is not in fact
    # a normalization — 13,992 distinct values against the original's 13,851 —
    # so the plain name goes to the ICD-9 label, which is the column that
    # actually groups (3,860 distinct).
    "Original Diagnosis": "Diagnosis as written",
    "Standardized Diagnosis": "Diagnosis as standardized",
    "standardPrimaryICD9Name": "Diagnosis",
    "origPrimICD9Name": "Diagnosis as written (ICD-9 name)",
    "Primary-ICD9": "ICD-9 Code",
    "StandardICDInteger": "ICD-9 Category",
}

# ---------------------------------------------------------------- rules

SEX = {
    "male": "Male",
    "female": "Female",
    "m": "Male",
    "f": "Female",
}
# Sex is the one closed vocabulary here, so it is also the one column where a
# value that resolves to neither term is cleared rather than passed through.
# In the 2025-08-10 source that is "B", "W" and "C", one record each: single
# letters that are not abbreviations of Male or Female in any reading we can
# support, and read as debris from a neighbouring column. Clearing them puts
# those records in the same unrecorded bucket as the 186 blanks instead of
# inventing three one-member categories. Every clearance is listed in the
# report, and the source file still holds the letter.
CLOSED_VOCABULARIES = {"Sex": {"Male", "Female"}}

RELIGION = {
    "moslem": "Muslim",
    "muh.": "Muslim",  # Muhammadan, the register's own usage
}

NATIONALITY = {
    # Palestinian, abbreviated by clerks in a dozen ways. The trailing tokens on
    # some of these ("R", "R.C.", record numbers) are dropped here but survive
    # in the untouched raw Nationality column.
    "palst.": "Palestinian",
    "pales.": "Palestinian",
    "pale.": "Palestinian",
    "palent.": "Palestinian",
    "palist.": "Palestinian",
    "pals.": "Palestinian",
    "palest'n": "Palestinian",
    "palestinian | palestinian": "Palestinian",
    'palest. "r"': "Palestinian",
    'palest. "es"': "Palestinian",
    'pal. "r"': "Palestinian",
    "palest. a 351": "Palestinian",
    "palest. p": "Palestinian",
    "palest. r.c.": "Palestinian",
    "palest. c.r.l.": "Palestinian",
    "pal (l)": "Palestinian",
    # Country name given where the demonym is used elsewhere.
    "poland": "Polish",
    "greece": "Greek",
    "syria": "Syrian",
    "lebanon": "Lebanese",
    "transjordan": "Transjordanian",
    "leban.": "Lebanese",
    "libanian": "Lebanese",
    "t.j.": "Transjordanian",
    "t/jordanian": "Transjordanian",
    "cheko": "Czechoslovakian",
    "czech": "Czechoslovakian",
    "latevian": "Latvian",
    # British, with clerk shorthand and stray record numbers.
    "brit.": "British",
    "british subj.": "British",
    "british 2234": "British",
    "british 3332": "British",
    "british c/e": "British",
    # Compound designations: separator normalized, both terms kept.
    "palestinian-syrian": "Palestinian Syrian",
    "palestinian / lebanese": "Palestinian Lebanese",
    "palestinian (t. jordan)": "Palestinian Transjordanian",
    "palestinian t.j.": "Palestinian Transjordanian",
    "palest. transj.": "Palestinian Transjordanian",
    "palestinian | transjordanian": "Palestinian Transjordanian",
    "palest. egyptian": "Palestinian Egyptian",
    "t.j. muslem": "Transjordanian",
    "syrian / egyptian": "Syrian Egyptian",
}

WARD = {
    "mat": "Maternity",
    "mat.": "Maternity",
    "infectious": "Infectious Diseases",
    "infectious section": "Infectious Diseases",
    "infectious diseases section": "Infectious Diseases",
    "childrens": "Children's",
}

CLASS = {
    "1st": "1",
    "2nd": "2",
    "3rd": "3",
    "1st class": "1",
    "2nd class": "2",
    "3rd class": "3",
    "i": "1",
    "ii": "2",
    "iii": "3",
}
# Values carrying a question mark ("3rd?", "2nd?") keep their uncertainty rather
# than being flattened into a clean class.

RULES = {
    "Sex": SEX,
    "standardized Religion": RELIGION,
    "StandardNationality": NATIONALITY,
    "standardized ward": WARD,
    "Class standard": CLASS,
}

# A value left standing on fewer than this many records is reported as tail:
# not an error, but the place to look when a rule is missing.
TAIL_THRESHOLD = 20

# Wards are recorded as combinations when a patient moved between them.
WARD_SPLIT = re.compile(r"\s*[|/]\s*")

# ------------------------------------------------------- address policy

# The PII policy keeps the street or neighbourhood and drops the house number.
HOUSE_NUMBER = re.compile(
    r"""(?:
          \bp\.?\s*o\.?\s*b\.?\s*\d+\b     # "P.O.B. 623"
        | \bno\.?\s*[A-Z]?\d+\b\.?         # "No. 38", "no 1029", "No. H307"
        | \b\d+\b                          # a bare number anywhere
    )""",
    re.IGNORECASE | re.VERBOSE,
)


def coarsen_address(value: str) -> str:
    """Strip house and box numbers, keep the street or neighbourhood."""
    if not value or not any(ch.isdigit() for ch in value):
        return value
    out = HOUSE_NUMBER.sub("", value)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.])", r"\1", out)   # " ." left where a number stood
    out = re.sub(r"([,.])\1+", r"\1", out)
    # Trailing full stops belong to abbreviations — "Carmel St.", "Hfa." — so
    # only spaces, commas and dashes left dangling by the removal are trimmed.
    return out.strip(" ,-")


# ----------------------------------------------------------- normalize


def normalize(column: str, value: str) -> str:
    rules = RULES.get(column)
    if not rules or not value:
        return value
    stripped = value.strip()
    if column == "standardized ward" and WARD_SPLIT.search(stripped):
        parts = [rules.get(p.strip().lower(), p.strip()) for p in WARD_SPLIT.split(stripped) if p.strip()]
        seen: list[str] = []
        for part in parts:
            if part not in seen:
                seen.append(part)
        return " | ".join(seen)
    resolved = rules.get(stripped.lower(), stripped)
    permitted = CLOSED_VOCABULARIES.get(column)
    if permitted is not None and resolved not in permitted:
        return ""
    return resolved


def is_repeated_header(row: dict[str, str]) -> bool:
    """The source spreadsheets carry one header line inside the data.

    Legitimate records hold Ward = "Ward" and Rate = "Rate", so a single
    self-matching field is not enough to judge by.
    """
    return sum(1 for key, value in row.items() if value == key) >= 5


def main() -> int:
    if not SOURCE.exists():
        print(f"Source not found: {SOURCE}", file=sys.stderr)
        return 1

    with SOURCE.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)
        fieldnames = [HEADER_FIXES.get(name, name) for name in (reader.fieldnames or [])]
        rows = [
            {HEADER_FIXES.get(k, k): v for k, v in row.items() if k is not None}
            for row in reader
        ]

    changes: Counter[tuple[str, str, str]] = Counter()
    final_values: dict[str, Counter[str]] = {col: Counter() for col in RULES}
    dropped = 0
    coarsened = 0
    out_rows = []

    for row in rows:
        if is_repeated_header(row):
            dropped += 1
            continue

        for column in RULES:
            if column not in row:
                continue
            before = (row[column] or "").strip()
            after = normalize(column, before)
            if after != before:
                changes[(column, before, after)] += 1
            row[column] = after
            if after:
                final_values[column][after] += 1

        if "Address" in row:
            before = row["Address"] or ""
            after = coarsen_address(before)
            if after != before:
                coarsened += 1
            row["Address"] = after

        out_rows.append(row)

    # Written by hand rather than through csv.writer: the registers contain bare
    # double quotes (inches, gershayim) and any escaping of them would have to be
    # undone by every consumer. Tabs and newlines inside a value are the only
    # things that could break the format, so those are the only things touched.
    def cell(value: str) -> str:
        return re.sub(r"[\t\r\n]+", " ", value or "").strip()

    published = [COLUMN_RENAMES.get(name, name) for name in fieldnames]
    clashes = {name for name in published if published.count(name) > 1}
    if clashes:
        print(f"Renames collide on: {', '.join(sorted(clashes))}", file=sys.stderr)
        return 1

    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\t".join(published) + "\n")
        for row in out_rows:
            handle.write("\t".join(cell(row.get(name, "")) for name in fieldnames) + "\n")

    with REPORT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["kind", "column", "from", "to", "records"])
        for (column, before, after), count in changes.most_common():
            writer.writerow(["cleared" if not after else "merged", column, before, after, count])
        for column, counts in final_values.items():
            for value, count in counts.most_common():
                if count < TAIL_THRESHOLD:
                    writer.writerow(["tail", column, value, "", count])

    print(f"read       {len(rows):,} rows")
    print(f"dropped    {dropped} repeated header row(s)")
    print(f"wrote      {len(out_rows):,} rows -> {OUTPUT.relative_to(ROOT)}")
    cleared = sum(n for (_, _, after), n in changes.items() if not after)
    print(f"merged     {sum(changes.values()) - cleared:,} values across {len(changes)} rules")
    print(f"cleared    {cleared} value(s) outside a closed vocabulary")
    print(f"coarsened  {coarsened:,} addresses")
    tail = {
        (col, val): n
        for col, counts in final_values.items()
        for val, n in counts.items()
        if n < TAIL_THRESHOLD
    }
    print(f"tail       {len(tail)} value(s) left standing on fewer than {TAIL_THRESHOLD} records")
    print(f"report     {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
