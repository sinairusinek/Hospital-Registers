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
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "public" / "hospital-registers-2025-08-10.tsv"
OUTPUT = ROOT / "data" / "public" / "hospital-registers-normalized.tsv"
REPORT = ROOT / "data" / "public" / "normalization-report.tsv"

# A second classification pass over the diagnoses the first one never reached,
# produced by pipeline/classify_diagnoses.py with the same prompt. Kept as its
# own reviewable file rather than folded into the source: every code it proposed
# can be read beside the string it came from, a wrong one is struck out by
# editing a line, and the build stays reproducible without an API key. Optional —
# absent, the build simply leaves those diagnoses uncoded.
CLASSIFICATION = ROOT / "data" / "public" / "diagnosis-classification.tsv"

# Below this the prompt's own scale calls the code a speculative guess from
# partial text. Those are written in like the rest, but flagged, so a reader can
# exclude them and a reviewer knows where to look first.
LOW_CONFIDENCE = 0.4
KIMA_DECISIONS = ROOT / "kimatch" / "city-kima-decisions.tsv"


def load_kima_decisions() -> dict[str, tuple[str, str]]:
    """City value -> (Kima place id, Wikidata QID) for human-confirmed matches.

    The decisions file is the reviewed City-to-gazetteer mapping produced by the
    kimatch workflow (see kimatch/README.md). Only rows whose decision is
    `matched` link; the build tolerates the file's absence so the pipeline can
    run on a fresh checkout.
    """
    links: dict[str, tuple[str, str]] = {}
    if not KIMA_DECISIONS.exists():
        return links
    with KIMA_DECISIONS.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row.get("decision") == "matched" and (row.get("kima_id") or row.get("wikidata_qid")):
                links[row["city"]] = (row.get("kima_id", ""), row.get("wikidata_qid", ""))
    return links

# Column 45 lost its header in the source spreadsheets. By position (between
# origPrimICD9Name and Additional-ICD9) and content (ICD-9 labels, filled for
# 28,107 records against origPrimICD9Name's 18,971) it is the standardized
# ICD-9 name for the primary diagnosis.
HEADER_FIXES = {"<info@doctorsonly.co.i": "standardPrimaryICD9Name"}

# Withheld from the published artifact. `Next of Kin` holds 2,379 personal names
# of third parties — people who never were the subject of the record — which the
# PII policy's redaction of patient names did not cover. The column stays in the
# consolidated TSV and in data/private/.
#
# `discarded_values` and `splitDiscValues` go with it: they are extraction
# debris that echo the raw cells of a record verbatim, next-of-kin names
# included, so withholding the column alone would not have withheld the names.
DROP_COLUMNS = {"Next of Kin", "discarded_values", "splitDiscValues"}

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
    "byzage": "Druze",  # a transcription failure, read against the page
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

# Cities were never normalized upstream: 2,623 spellings over 24,561 records,
# most of them one clerk's transliteration of the same place. Only spellings of
# the same name are merged here, and the canonical form is the register's own
# most frequent one — except Hadera, where the modern standard was asked for
# over the commoner "Hedera".
#
# What is deliberately *not* merged: names from different naming traditions for
# the same place — Acre and Akka, Balad al-Sheikh and Nesher. Which name a clerk
# reached for is evidence, and collapsing it is an editorial act rather than a
# spelling fix. The verbatim spelling survives in `City as written` regardless.
#
# Generated by clustering the spellings and then read by hand: the clustering
# alone proposed Acre for Cairo, Ramallah for Ramleh and Abu Sinan for Beisan.
CITY = {
    "hedera": "Hadera", "khedera": "Hadera", "khadera": "Hadera",
    "khidera": "Hadera", "khdeira": "Hadera", "khedēra": "Hadera",
    "hadera (area)": "Hadera",
    "atlit": "Athlit", "athlith": "Athlit", "athleith": "Athlit", "atlith": "Athlit",
    "jeni": "Jenin", "jinin": "Jenin", "janin": "Jenin", "jene": "Jenin",
    "hayfa": "Haifa", "haffa": "Haifa", "hfa.": "Haifa",
    "shefa amr": "Shafa Amr", "shefa-'amr": "Shafa Amr", "shefa-amr": "Shafa Amr",
    "shafa 'amr": "Shafa Amr", "shafa-amr": "Shafa Amr", "shefa'amr": "Shafa Amr",
    "shafa'amr": "Shafa Amr", "shafa amer": "Shafa Amr", "shefa'amer": "Shafa Amr",
    "shefa'mer": "Shafa Amr", "shefa 'amr": "Shafa Amr", "shefa 'amer": "Shafa Amr",
    "shifa amr": "Shafa Amr", "shafa'mer": "Shafa Amr", "shafa'amer": "Shafa Amr",
    "shafa 'amer": "Shafa Amr", "shefamer": "Shafa Amr", "shafa 'mer": "Shafa Amr",
    "shifa amir": "Shafa Amr", "shafa'mr": "Shafa Amr", "shfa amr": "Shafa Amr",
    "shafe amr": "Shafa Amr", "shafaamer": "Shafa Amr",
    "beissan": "Beisan", "bisan": "Beisan", "bessan": "Beisan", "bissan": "Beisan",
    "baisan": "Beisan", "baissan": "Beisan",
    "abu sinan": "Abu Snan", "abou snan": "Abu Snan", "abo snan": "Abu Snan",
    "tirah": "Tireh", "tyreh": "Tireh", "tirreh": "Tireh", "tirih": "Tireh",
    "safed": "Safad", "sefad": "Safad",
    "tulkarm": "Tulkarem", "tul-karm": "Tulkarem", "tul karm": "Tulkarem",
    "tul-karem": "Tulkarem", "tul karem": "Tulkarem", "tul kerim": "Tulkarem",
    "toulkarem": "Tulkarem", "tulk-karm": "Tulkarem", "toul-karem": "Tulkarem",
    "neblus": "Nablus", "jerusalm": "Jerusalem",
    "kiriat haim": "Kiryat Haim", "kiryat hayim": "Kiryat Haim", "kiryat hayem": "Kiryat Haim",
    "bessa": "Bassa", "baasa": "Bassa",
    "balad al-shaykh": "Balad al-Sheikh", "balad el-sheikh": "Balad al-Sheikh",
    "belad el-sheikh": "Balad al-Sheikh", "balad el sheikh": "Balad al-Sheikh",
    "balad sheikh": "Balad al-Sheikh", "belad el sheikh": "Balad al-Sheikh",
    "balad esh chiekh": "Balad al-Sheikh", "balad el shaikh": "Balad al-Sheikh",
    "balad shekh": "Balad al-Sheikh",
    "hadar hacarmel": "Hadar Hacarmel",
    "yajur": "Yajour", "yagur": "Yajour", "yagour": "Yajour",
    "tarsheeha": "Tarshiha",
    "ara": "Arara", "ar'ara": "Arara", "arrara": "Arara", "ara'ra": "Arara",
    "arra": "Arara", "araara": "Arara", "a'ara": "Arara", "ara'ara": "Arara",
    # "Rameleh" looks like Ramleh but the one record carrying it says "of
    # Acre": it is Rameh (al-Rama) in the Galilee, as are Rami and the
    # unstripped "Rameh. Acre".
    "rameleh": "Rameh", "ramah": "Rameh", "arameh": "Rameh",
    "rami": "Rameh", "rameh. acre": "Rameh",
    "kufr yasif": "Kafr Yasif", "kfar yassif": "Kafr Yasif", "kufr yassif": "Kafr Yasif",
    "kafr yassif": "Kafr Yasif", "kufer yasif": "Kafr Yasif", "kufer yassif": "Kafr Yasif",
    "kafar yasif": "Kafr Yasif", "kafr-yasif": "Kafr Yasif", "kefar yasif": "Kafr Yasif",
    "kfar yassif": "Kafr Yasif", "kfar yusif": "Kafr Yasif", "kafr yousif": "Kafr Yasif",
    "kafr youssef": "Kafr Yasif", "kufar yassif": "Kafr Yasif", "kufr yasseef": "Kafr Yasif",
    "karkour": "Karkur", "kar kur": "Karkur",
    "zichron yakov": "Zichron Yaakov", "zikhron ya'akov": "Zichron Yaakov",
    "zikhron yaaqov": "Zichron Yaakov", "zikhron ya'aqov": "Zichron Yaakov",
    "zikhron yaakov": "Zichron Yaakov",
    "sachnin": "Sakhnin", "sakhneen": "Sakhnin", "sakhnien": "Sakhnin",
    "affula": "Afula", "affule": "Afula", "affuleh": "Afula", "affulah": "Afula",
    "afuleh": "Afula",
    "tantura": "Tantoura", "tantouria": "Tantoura",
    "ijzim": "Igzim", "iggzim": "Igzim", "igzem": "Igzim", "igzeim": "Igzim",
    "bath galim": "Bat Galim", "bat-galim": "Bat Galim",
    "irbid": "Irbed", "erbed": "Irbed", "erbid": "Irbed",
    "majdel krum": "Majd al-Krum", "majdel kroum": "Majd al-Krum",
    "majdal krum": "Majd al-Krum", "megdal el kroum": "Majd al-Krum",
    "magdel kouroum": "Majd al-Krum", "majdel kroom": "Majd al-Krum",
    "samach": "Samakh", "samekh": "Samakh",
    "kiryat bialek": "Kiryat Bialik",
    "wadi en nisnas": "Wadi Nisnas", "wad en nisnas": "Wadi Nisnas",
    "wadi el nisnas": "Wadi Nisnas", "wadi nisnass": "Wadi Nisnas",
    "yerka": "Yarka", "yirka": "Yarka",
    "ain ghazal": "Ein Ghazal",
    "tel-aviv": "Tel Aviv",
    "binyamina": "Benyamina",
    "akko": "Akka",
    "herzliya": "Herzlia", "herzelia": "Herzlia",
    "ard al-yahud": "Ardel Yahud", "ardel yahad": "Ardel Yahud",
    "wadi salub": "Wadi Salib", "wadi saleeb": "Wadi Salib", "wadi es salib": "Wadi Salib",
    "wadi el salib": "Wadi Salib", "wad el salib": "Wadi Salib", "wadi salieb": "Wadi Salib",
    "wady saleeb": "Wadi Salib", "wadi salab": "Wadi Salib",
    "maghar": "Mughar", "moghar": "Mughar", "mghar": "Mughar", "meghar": "Mughar",
    "mughrar": "Mughar", "imghar": "Mughar", "maughar": "Mughar",
    "carmel stn.": "Carmel Station", "carmel station": "Carmel Station",
    "kefar vitkin": "Kfar Vitkin", "kafar vitkeen": "Kfar Vitkin", "kafar vitkin": "Kfar Vitkin",
    "yammoun": "Yamoun", "yamun": "Yamoun",
    "jaba'a": "Jaba'", "jaba": "Jaba'", "jabaa": "Jaba'", "jab'a": "Jaba'",
    "arabeh": "Arrabeh", "arrabah": "Arrabeh", "arrabih": "Arrabeh",
    "afikim": "Affikim",
    "kiriat motzkin": "Kiryat Motzkin",
    "pardes hanna": "Pardess Hanna",
}

# Stripped before the lookup: a stray leading pipe from the extraction, the
# Arabic article, a trailing full stop, and the clerk's own question mark. The
# uncertainty it marks is preserved in `City as written`.
CITY_NOISE = re.compile(r"^\|+\s*|^(?:el|al|ed|es)[\s-]+|[.?]+$", re.IGNORECASE)


def normalize_city(value: str) -> str:
    if not value:
        return value
    cleaned = re.sub(r"\s{2,}", " ", CITY_NOISE.sub("", value.strip()).strip())
    return CITY.get(cleaned.lower(), cleaned)


# Haifa's arteries are named for the towns they lead to — Nazareth Road, Jaffa
# Road, Acre Street — and the upstream extraction sometimes read the street's
# namesake as the patient's city. When the address is such a street and the
# City column holds its namesake (or the street name itself), the record is a
# Haifa one: the many records writing "Nazareth Street, Haifa" in full carry
# the proof. A bare street with an empty City is left empty — the repair only
# corrects a wrong city, it never invents one.
STREET_NAMESAKE = re.compile(
    r"^\s*(?:Haifa[\s.,-]+)?(Nazareth|Naz\.?|Jaffa|Acre)\s*(?:St|Str|Street|Rd|Road)\b",
    re.IGNORECASE,
)


def city_from_street(address: str, city: str) -> bool:
    m = STREET_NAMESAKE.match(address or "")
    if not m:
        return False
    namesake = {"naz": "Nazareth", "naz.": "Nazareth"}.get(m.group(1).lower(), m.group(1).title())
    return city == namesake or city.lower() in (f"{namesake.lower()} road", f"{namesake.lower()} st.")


WARD = {
    "mat": "Maternity",
    "mat.": "Maternity",
    "infectious": "Infectious Diseases",
    "infectious section": "Infectious Diseases",
    "infectious diseases section": "Infectious Diseases",
    "childrens": "Children's",
}

# The wards of the hospital, as they read once standardized. An Occupation
# holding exactly one of these — a 7-year-old "Gynecology" among them — is the
# ward column's content misfiled by the extraction, not a trade.
WARD_NAMES = {
    "Surgical", "Medical", "British Section", "Isolation", "Gynecology",
    "General", "Maternity", "Infectious Diseases", "Venereal Diseases",
}

# The clerk's abbreviations, for reading the written ward on those records.
# "Gen." is General, not Gynecology: record 86 of notebook 11 reads "Gen."
# on the page beside a misfiled "Gynecology", confirmed against the scan.
WARD_WRITTEN = {name.lower(): name for name in WARD_NAMES} | WARD | {
    "surg": "Surgical",
    "surg.": "Surgical",
    "gen": "General",
    "gen.": "General",
}

# Record-level ward corrections, keyed (Notebook_Number, Notebook Record ID),
# for readings that survive only in a column the pipeline drops. Notebook 11
# record 86: the written ward reached the source file only as a discarded
# value, "Gen.", and the scan confirms General.
WARD_CORRECTIONS = {
    ("11", "86"): "General",
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

# A value repeating its record's next of kin is cleared only if it appears on
# fewer than this many records in its column — see the note in main().
KIN_RARITY = 5

# Fields with no controlled vocabulary, where a name can sit unnoticed.
FREE_TEXT_FIELDS = {"Address", "City", "Occupation"}

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


# --------------------------------------------------------- ICD-9 chapter
#
# The ICD-9 code column holds 2,514 distinct values and its three-digit
# category still holds 821 — too many for a facet list or a pie, where the top
# ten would leave most of the file in an "Others" residue. The chapter is the
# classification's own top level, seventeen headings plus the two supplementary
# series, and it is the level at which the registers can actually be read.
#
# Ranges are ICD-9-CM as published. The label is prefixed with its range so the
# facet sorts into classification order rather than alphabetically.
ICD9_CHAPTERS = [
    (1, 139, "Infectious and parasitic diseases"),
    (140, 239, "Neoplasms"),
    (240, 279, "Endocrine, nutritional and metabolic diseases"),
    (280, 289, "Diseases of the blood"),
    (290, 319, "Mental disorders"),
    (320, 389, "Nervous system and sense organs"),
    (390, 459, "Circulatory system"),
    (460, 519, "Respiratory system"),
    (520, 579, "Digestive system"),
    (580, 629, "Genitourinary system"),
    (630, 679, "Pregnancy, childbirth and the puerperium"),
    (680, 709, "Skin and subcutaneous tissue"),
    (710, 739, "Musculoskeletal system and connective tissue"),
    (740, 759, "Congenital anomalies"),
    (760, 779, "Conditions originating in the perinatal period"),
    (780, 799, "Symptoms, signs and ill-defined conditions"),
    (800, 999, "Injury and poisoning"),
]

# The first code in a pipe-separated list is the primary diagnosis.
ICD9_FIRST = re.compile(r"^\s*([EVev]?)(\d{1,3})")

# A one- or two-digit code has lost a leading zero somewhere in extraction, and
# zero-padding recovers it: "32.9" is diphtheria, "11.9" pulmonary tuberculosis,
# "84.9" malaria. That holds for 211 of the 231 records with a short code, every
# one confirmed by the ICD-9 name standing beside it in the row.
#
# It does not hold for these. They are ICD-9-CM *procedure* codes, or codes the
# accompanying name flatly contradicts, and padding them would file an operation
# under a disease — "72.1", a forceps delivery, landing among the infectious
# admissions next to the mumps cases that "72" and "72.9" correctly are. A
# procedure is not a diagnosis and has no diagnosis chapter, so these are left
# without one rather than placed in the wrong one. Each is listed with the name
# that identifies it.
#
# The last two are not ICD-9 at all: upstream coding reached for ICD-10 on a
# handful of rows, and those codes cannot match a chapter here whatever we do.
# Left alone they would have fallen out of the classification silently, refused
# by accident rather than by rule and carrying no flag to say so. Both name an
# operation in the row beside them — the thirty "O66.9" are every one of them a
# forceps delivery, the same admission as the "72.1" records above — so they
# are refused on the same ground and counted with the procedures.
ICD9_NOT_DIAGNOSES = {
    "72.1":  "Other specified forceps delivery",       # obstetric procedure
    "69.09": "",                                       # D&C; no name in the row
    "73.09": "",                                       # rupture of membranes
    "83.19": "Other tenotomy",                         # musculoskeletal procedure
    "43.0":  "Hydrocele, traumatic",                   # 043 is not a hydrocele
    "O66.9": "Forceps Delivery",                       # ICD-10; obstetric procedure
    "R29.89": "Sent in for Lumbar Puncture",           # ICD-10; procedure admission
}


def icd9_chapter(code: str, fallback: str) -> str:
    """The chapter a primary ICD-9 code belongs to, or "" if it cannot be read."""
    for candidate in (code, fallback):
        first = (candidate or "").split("|")[0].strip()
        if first in ICD9_NOT_DIAGNOSES:
            return ""
        if first.upper() in ICD10_CHAPTER:
            return ICD10_CHAPTER[first.upper()]
        match = ICD9_FIRST.match(first)
        if not match:
            continue
        prefix, digits = match.group(1).upper(), match.group(2)
        if prefix == "E":
            return "E800-E999 External causes of injury"
        if prefix == "V":
            return "V01-V82 Supplementary: factors influencing health status"
        # A handful of codes lost a leading zero in extraction — "32.9" for
        # diphtheria, "11.9" for pulmonary tuberculosis. Zero-padding recovers
        # the chapter for those; it also drags in about a dozen ICD-9 procedure
        # codes ("72.1", a forceps delivery), which is why the padded ones are
        # counted separately in the report.
        number = int(digits)
        for low, high, label in ICD9_CHAPTERS:
            if low <= number <= high:
                return f"{low:03d}-{high:03d} {label}"
    return ""


# --------------------------------------------------------- procedures
#
# 524 records name an operation in the diagnosis column. Most are not an error:
# "Normal Delivery" is ICD-9 650, a diagnosis code in its own right, and 476 of
# the 524 carry a chapter already. The distinction worth drawing is whether an
# operation stands *instead of* a diagnosis — a forceps delivery with the
# condition that called for it left unstated — or alongside one.
#
# This gets a column of its own rather than a value in the chapter column: the
# 476 are correctly chaptered and must stay so. As a facet it answers a question
# the chapter cannot, which is how often these clerks recorded the intervention
# rather than the illness.
PROCEDURE = re.compile(
    r"\b(forceps|caesar|cesar|curettage|curetage|craniotomy|tenotomy|circumcision"
    r"|version and extraction|laparotomy|append(?:ic)?ectomy|herniotomy|hysterectomy"
    r"|amputation|trephin\w*|nephrectomy|tonsillectomy|delivery"
    r"|\w+ectomy|\w+otomy|\w+ostomy|\w+plasty|\w+rraphy|\w+centesis)\b",
    re.IGNORECASE,
)

# ICD-10 codes that leaked into an ICD-9 column. Mapped at chapter level only,
# where the correspondence is not in doubt — an obstructed labour belongs to the
# obstetric chapter under either revision. No ICD-9 code is invented for them.
# O66.9 and R29.89 look like candidates for this table and are not: all 30 of
# the O66.9 records read "Forceps Delivery" in the register, and obstructed
# labour is the classifier's inference about why forceps were used rather than
# anything the clerk wrote. They belong in ICD9_NOT_DIAGNOSES above, with the
# other procedures. What is left is the one code whose record carries a symptom
# and no operation.
ICD10_CHAPTER = {
    "R50.9": "780-799 Symptoms, signs and ill-defined conditions",  # fever, unspecified
}

# Values from the Result column that ended up in a diagnosis or code field. They
# are a column misalignment, not a diagnosis, and are never classified — the
# record is flagged so the page can be checked.
RESULT_IN_WRONG_COLUMN = re.compile(
    r"^(cured|died|recovered|improved|relieved|unimproved|discharged|transferred"
    r"|dead|not improved|escaped)\W*$",
    re.IGNORECASE,
)

# The original classification pass ran on GPT-4o and hit a rate limit; on five
# records the error text was written into the diagnosis field instead of a
# diagnosis. Those, the stray header line and bare punctuation are debris.
CLASSIFIER_DEBRIS = re.compile(r"validation error|error code:|^diagnosis$|^[-?.\s]*$", re.IGNORECASE)


# ------------------------------------------------------------- review
#
# Everything the pipeline could not settle on its own, named so that the app can
# group by it and a person can work through it against the scans. A flag is not
# an error: it marks a record where the machine's reading is uncertain and the
# page is the only authority. Each is documented for the reviewer in the app.
#
# Order is the order they are worth working through: the smallest and most
# clearly wrong first, the large diffuse ones last.
REVIEW_FLAGS = [
    ("procedure-not-diagnosis", "An operation recorded where a diagnosis belongs"),
    ("impossible-stay", "Discharged before admitted; the stay has been cleared"),
    ("stay-over-by-a-year", "Discharge year corrected: the stay ran a year over the clerk's own count"),
    ("sex-cleared", "A single stray letter where a sex belongs"),
    ("date-out-of-span", "A date outside 1930-48 with nothing on the record to repair it from"),
    ("date-year-out-of-sequence", "Year corrected: the admission ran backwards against the register's order"),
    ("date-month-out-of-sequence", "Month corrected: the admission ran backwards against the register's order"),
    ("date-day-out-of-sequence", "Day corrected: one digit from what was read, and back in the register's order"),
    ("date-year-repaired", "A year outside 1930-48, taken from the other date on the record"),
    ("date-seated-by-order", "A date outside 1930-48, taken whole from identical dates either side of it"),
    ("date-unreadable", "A date the clerk's own writing could not be parsed from"),
    ("stay-disagrees", "Computed stay differs from the count written beside it"),
    ("serial-repaired", "Record number repaired: a digit slip against the register's own run"),
    ("serial-out-of-sequence", "Record number breaks the register's run and no safe repair exists"),
    ("icd9-low-confidence", "A second-pass code the classifier itself called speculative"),
    ("icd9-second-pass", "Coded by the second classification pass, not the first"),
    ("result-in-diagnosis", "A Result value standing in a diagnosis or code field"),
    ("classifier-debris", "Classifier error text where a diagnosis belongs"),
    ("procedure-only", "An operation named with no diagnosis behind it"),
    ("no-icd9-chapter", "No ICD-9 code the classification could place"),
]


# ------------------------------------------------------------- dates
#
# The source's ISO admission column cannot be trusted per record. Its values
# are shuffled among neighbouring rows: sample notebook 11 and every one of the
# 31 admission dates that disagrees with what the clerk wrote is some nearby
# row's correctly converted date. Usually the mix-up is a few days and shows up
# only as a wrong length of stay; occasionally a value travels far enough to
# produce a discharge years before admission, which is what made it visible.
#
# Two independent checks say the verbatim column is the one to keep. Where the
# two disagree and the clerk also wrote down a length of stay, the verbatim
# date reproduces his figure 1,978 times against the ISO column's 93. Across
# the whole file the verbatim dates agree with his stay 95.3% of the time
# against 88.2%.
#
# So the ISO dates are recomputed here from the verbatim ones, which are the
# register's own testimony. The source file keeps its columns untouched, and
# where a verbatim value cannot be read the upstream conversion is left in
# place rather than discarded — it is the only reading available for those.
DATE_WRITTEN = re.compile(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})")

# The registers cover 1930-48. A date outside that span is a misread digit in
# the year, not a real admission: "19.11.89" in notebook 23, discharged
# 25.11.39, is 1939 with the 3 read as an 8. Where the record's other date is
# in span it supplies the year — the two dates are days apart in every one of
# these cases — and where it does not, nothing is invented and the record is
# flagged for review instead.
REGISTER_YEARS = range(1930, 1949)

# A notebook needs enough dated records for its own order to mean anything, and
# a repaired date is allowed a few days either side of the backbone it rejoins:
# the register is kept in order, not to the day.
MIN_NOTEBOOK_RECORDS = 20
SEQUENCE_SLACK = timedelta(days=3)
# Beyond this a shift is not a misread digit but a different date.
MAX_YEAR_SHIFT = 10
# How many records either side of a run are asked what year it should be, and
# how many of them have to agree before the run is moved.
NEIGHBOURHOOD = 80
MIN_NEIGHBOURS = 20
# Passes over a notebook; misread pages in a row resolve from the outside in.
# What changing one record's year costs against the days of disorder it saves.
# The page-level witness: how many pages either side are asked, how many must
# agree, and how many pages a notebook needs before its pagination is trusted.
PAGE_NEIGHBOURHOOD = 8
MIN_PAGE_NEIGHBOURS = 4
MIN_PAGES = 10

# The registers run 1930-48. A two-digit year is read into that century; the
# cut-off only has to fall somewhere outside the range the registers cover.
YEAR_PIVOT = 25


def parse_written_date(value: str) -> str:
    """dd.mm.yy as the clerk wrote it -> ISO, or "" if it cannot be read."""
    match = DATE_WRITTEN.fullmatch((value or "").strip())
    if not match:
        return ""
    day, month, year = (int(g) for g in match.groups())
    if year < 100:
        year += 1900 if year >= YEAR_PIVOT else 2000
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def year_runs(values: list[date]) -> list[tuple[int, int, int]]:
    """Contiguous stretches of one year: (start, end exclusive, year).

    The misreadings come a page at a time — a year read once at the head of a
    page and carried down it — so a wrong year arrives as a block sitting
    between two blocks of the right one. Splitting the notebook into runs of a
    single year finds those blocks whatever their size, which a longest
    non-decreasing subsequence cannot: choosing notebook 24's 33 misread
    records or the 34 correct ones before them gives a subsequence of exactly
    the same length, so the tie breaks arbitrarily.
    """
    runs: list[tuple[int, int, int]] = []
    start = 0
    for i in range(1, len(values) + 1):
        if i == len(values) or values[i].year != values[start].year:
            runs.append((start, i, values[start].year))
            start = i
    return runs


def one_digit_apart(left: int, right: int) -> bool:
    """True if two small numbers differ in exactly one written digit.

    3 and 8, 13 and 18, 21 and 24 — the shapes a reader confuses. 16 and 22 are
    not, which is what keeps a late entry from being rewritten as an error.
    """
    a, b = f"{left:02d}", f"{right:02d}"
    return sum(1 for x, y in zip(a, b) if x != y) == 1


def repair_component(previous: date, value: date, following: date) -> tuple[date, str] | None:
    """A date out of order, mended by one component taken from its neighbours.

    Only the month and the day are tried here; the year is handled in blocks,
    where a whole page moves at once. A candidate has to seat the record back
    between its neighbours, and the day may only take a value one digit from
    the one written — otherwise a record entered late, which registers are full
    of, would be rewritten into tidy order and the lateness lost.
    """
    candidates: list[tuple[int, int, date, str]] = []
    for month in {previous.month, following.month}:
        try:
            candidates.append((0, abs(month - value.month), value.replace(month=month), "month"))
        except ValueError:
            continue
    for day in {previous.day, following.day}:
        if not one_digit_apart(day, value.day):
            continue
        try:
            candidates.append((1, abs(day - value.day), value.replace(day=day), "day"))
        except ValueError:
            continue

    seated = [
        candidate for candidate in candidates
        if previous - SEQUENCE_SLACK <= candidate[2] <= following + SEQUENCE_SLACK
    ]
    if not seated:
        return None
    _, _, mended, component = min(seated)
    return mended, component


def resolve_year_shifts(
    values: list[date],
    runs: list[tuple[int, int, int]],
    neighbourhood: int = NEIGHBOURHOOD,
    min_support: int = MIN_NEIGHBOURS,
) -> list[int]:
    """Per run of one year, the shift that puts it back in the notebook's order.

    Three things have to hold before a run of records moves.

    It has to be out of order to begin with — running backwards against the
    records above it, or past the records below. A run that sits in order where
    it is stays there however its neighbours read, which is what leaves a
    notebook's genuine turn of the year alone.

    The records on either side of the run, but not in it, have to agree on a
    year. Excluding the run from its own witness is the point: inside a misread
    page the wrong year is the local majority, so any window that includes the
    page agrees with the page. Once it is out of the vote a wide neighbourhood
    is safe and the block stands out however large it is.

    And the shift has to seat the run in order between the records above and
    below it. Anything that does not is left for a reader.

    Judging blocks one at a time, against the reading around them, is a
    deliberate choice over solving the notebook as a whole. A global optimum
    has to be told what to minimise, and every objective tried here — fewest
    records changed, fewest days out of order — buys one notebook's correctness
    with another's, because pulling a page of correct records back a year and
    pushing a misread page forward cost almost exactly the same. Local evidence
    is weaker but it is evidence, and where there is none this leaves the
    record alone and flags it.
    """
    shifts = [0] * len(runs)
    for index, (start, end, year) in enumerate(runs):
        before = values[start - 1] if start else None
        after = values[end] if end < len(values) else None
        jumps_back = before is not None and values[start] < before - SEQUENCE_SLACK
        jumps_forward = after is not None and values[end - 1] > after + SEQUENCE_SLACK
        if not (jumps_back or jumps_forward):
            continue

        witness = Counter(
            value.year for value in
            values[max(0, start - neighbourhood):start] + values[end:end + neighbourhood]
        )
        if not witness:
            continue
        expected, support = witness.most_common(1)[0]
        if expected == year or support < min_support:
            continue
        years = expected - year
        if abs(years) > MAX_YEAR_SHIFT:
            continue

        first = shift_years(values[start], years)
        last = shift_years(values[end - 1], years)
        if first is None or last is None or first.year not in REGISTER_YEARS:
            continue
        if before is not None and first + SEQUENCE_SLACK < before:
            continue
        if after is not None and last - SEQUENCE_SLACK > after:
            continue
        shifts[index] = years
    return shifts


def chronological_backbone(values: list[date]) -> set[int]:
    """Indices of the longest non-decreasing run through a notebook's dates.

    Used only to report how far a notebook departs from its own order; the
    repair works on year runs, for the reason given above.
    """
    tails: list[date] = []
    tail_index: list[int] = []
    previous = [-1] * len(values)
    for i, value in enumerate(values):
        lo, hi = 0, len(tails)
        while lo < hi:
            mid = (lo + hi) // 2
            if tails[mid] <= value:
                lo = mid + 1
            else:
                hi = mid
        if lo == len(tails):
            tails.append(value)
            tail_index.append(i)
        else:
            tails[lo] = value
            tail_index[lo] = i
        previous[i] = tail_index[lo - 1] if lo > 0 else -1

    keep: set[int] = set()
    i = tail_index[-1] if tail_index else -1
    while i != -1:
        keep.add(i)
        i = previous[i]
    return keep


def shift_years(value: date, years: int) -> date | None:
    try:
        return value.replace(year=value.year + years)
    except ValueError:  # 29 February
        return None


def to_date(value: str) -> date | None:
    try:
        return date.fromisoformat((value or "").strip()[:10])
    except ValueError:
        return None


def load_classification() -> dict[str, dict[str, str]]:
    """The second pass's codes, keyed by the diagnosis string as written."""
    if not CLASSIFICATION.exists():
        return {}
    with CLASSIFICATION.open(newline="", encoding="utf-8") as handle:
        return {
            (row["Original-Diagnosis"] or "").strip(): row
            for row in csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)
            if (row.get("Original-Diagnosis") or "").strip()
            and (row.get("Primary-ICD9") or "").strip()
        }


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
    kima_links = load_kima_decisions()
    kima_linked = 0
    street_reseated = 0
    final_values: dict[str, Counter[str]] = {col: Counter() for col in RULES}
    dropped = 0
    coarsened = 0
    kin_in_place: Counter[str] = Counter()
    kin_elsewhere: Counter[str] = Counter()
    column_values: dict[str, Counter[str]] = {}
    for row in rows:
        for field, value in row.items():
            if value:
                column_values.setdefault(field, Counter())[value.strip()] += 1
    # The City column is the registers' own gazetteer: a value that appears
    # there repeatedly is a place, whatever field it turns up in.
    place_vocabulary = column_values.get("City", Counter())

    # Names also turn up in a free-text field of a record whose own next-of-kin
    # cell is empty, which per-record matching cannot see. So the kin column is
    # read across the whole file as a list of names to remove: name-shaped
    # entries only (two or more words, no digits), minus anything the gazetteer
    # says is a place — "Arab el Turkman" is both a kin entry and a village.
    kin_names = {
        value.strip().lower()
        for value in column_values.get("Next of Kin", Counter())
        if len(value.split()) >= 2
        and not any(ch.isdigit() for ch in value)
        and place_vocabulary[value.strip()] < KIN_RARITY
    }
    ward_rehomed: Counter[tuple[str, str, str]] = Counter()
    ward_corrected = 0
    dates_rebuilt = Counter()
    stays_cleared = 0
    stays_over_a_year = 0
    chapters: Counter[str] = Counter()
    chapters_unresolved = 0
    recording: Counter[str] = Counter()
    icd9_padded = 0
    icd9_refused = 0
    review_counts: Counter[str] = Counter()
    classification = load_classification()
    second_pass = 0
    procedures: Counter[str] = Counter()
    out_rows = []

    for row in rows:
        if is_repeated_header(row):
            dropped += 1
            continue

        flags: list[str] = []

        for column in RULES:
            if column not in row:
                continue
            before = (row[column] or "").strip()
            after = normalize(column, before)
            if after != before:
                changes[(column, before, after)] += 1
                if column == "Sex" and before and not after:
                    flags.append("sex-cleared")
            row[column] = after
            if after:
                final_values[column][after] += 1

        # A hand correction first, so the pass below finds the ward in place.
        key = (
            (row.get("Notebook_Number") or "").strip(),
            (row.get("Notebook Record ID") or "").strip(),
        )
        corrected = WARD_CORRECTIONS.get(key)
        if corrected:
            previous = (row.get("standardized ward") or "").strip()
            if previous != corrected:
                row["standardized ward"] = corrected
                if previous:
                    final_values["standardized ward"][previous] -= 1
                final_values["standardized ward"][corrected] += 1
                ward_corrected += 1

        # The extraction sometimes filed the ward as the patient's occupation:
        # 49 records carry a bare ward name in Occupation, most of them beside
        # the very same value in the ward column. The name is taken out of
        # Occupation; where the ward column is empty it is completed, trusting
        # the clerk's own written ward over the misfiled value where the two
        # disagree.
        occupation = (row.get("Occupation") or "").strip()
        if occupation in WARD_NAMES:
            current = (row.get("standardized ward") or "").strip()
            written = (row.get("Ward") or "").strip()
            resolved = WARD_WRITTEN.get(written.lower(), "")
            if resolved and current in ("", occupation) and resolved != current:
                target, source = resolved, "written"
            elif current:
                target, source = current, "duplicate"
            else:
                target, source = occupation, "occupation"
            row["Occupation"] = ""
            if target != current:
                row["standardized ward"] = target
                if current:
                    final_values["standardized ward"][current] -= 1
                final_values["standardized ward"][target] += 1
            ward_rehomed[(occupation, target, source)] += 1

        # The derived chapter rides in a column of its own; the source's code
        # and three-digit category are both left exactly as they are.
        #
        # The second pass runs first, so a code it supplies is padded, refused
        # and chaptered by exactly the same rules as one from the original pass.
        # It fills only what the first left empty, and only for the exact string
        # it was asked about: it never overwrites a code.
        written_diag = (row.get("Original Diagnosis", "") or "").strip()
        if written_diag and not (row.get("Primary-ICD9") or "").strip():
            proposed = classification.get(written_diag)
            if proposed:
                row["Primary-ICD9"] = proposed.get("Primary-ICD9", "")
                row["standardPrimaryICD9Name"] = proposed.get("Primary-ICD9-Name", "")
                row["Primary-Confidence"] = proposed.get("Primary-Confidence", "")
                if not (row.get("Additional-ICD9") or "").strip():
                    row["Additional-ICD9"] = proposed.get("Additional-ICD9", "")
                second_pass += 1
                flags.append("icd9-second-pass")
                try:
                    if float(proposed.get("Primary-Confidence") or 0) < LOW_CONFIDENCE:
                        flags.append("icd9-low-confidence")
                except ValueError:
                    pass

        first_code = (row.get("Primary-ICD9", "") or "").split("|")[0].strip()
        if first_code in ICD9_NOT_DIAGNOSES:
            icd9_refused += 1
            flags.append("procedure-not-diagnosis")
        elif re.fullmatch(r"\d{1,2}(\.\d{1,2})?", first_code):
            icd9_padded += 1

        row["ICD-9 Chapter"] = icd9_chapter(
            row.get("Primary-ICD9", ""), row.get("StandardICDInteger", "")
        )
        if row["ICD-9 Chapter"]:
            chapters[row["ICD-9 Chapter"]] += 1
        else:
            chapters_unresolved += 1

        # Why a record has no chapter matters more than that it has none, and
        # the two reasons are not the same kind of fact. A record carrying
        # "Suppurative Adenitis Bursae" and no code is a coding job left undone:
        # the clerk wrote a diagnosis and the classification never reached it.
        # A record carrying nothing at all is the register itself falling
        # silent, and that silence is not evenly spread — it runs under 1% in
        # notebooks 1-9, 6.7% in notebook 32, 19.1% in notebook 33, and 66% of
        # the admissions of April 1948, alongside the same collapse in
        # the result and length-of-stay columns. What survives on those last
        # pages is the intake side of the record: date, age, sex, religion,
        # city. What is gone is everything a clerk fills in once a stay has
        # concluded. Pooled into a single "unrecorded" bucket the two read as
        # one gap in the data; kept apart, the second reads as evidence.
        row["Diagnosis Recording"] = (
            "Classified"
            if row["ICD-9 Chapter"]
            else "Recorded, not classified"
            if any(
                (row.get(col) or "").strip()
                for col in ("Original Diagnosis", "Standardized Diagnosis", "Primary-ICD9")
            )
            else "Not recorded"
        )
        recording[row["Diagnosis Recording"]] += 1

        # Dates before addresses: the stay is recomputed from whatever the two
        # date columns end up holding.
        for written_col, iso_col in (
            ("Admission Date (Orig)", "Admission Date [ISO]"),
            ("Discharge Date (Orig)", "Discharge Date (ISO)"),
        ):
            if written_col not in row or iso_col not in row:
                continue
            rebuilt = parse_written_date(row[written_col])
            if not rebuilt:
                dates_rebuilt[f"{iso_col}: verbatim unreadable, upstream kept"] += 1
                if "date-unreadable" not in flags:
                    flags.append("date-unreadable")
                continue
            if rebuilt != (row[iso_col] or "").strip()[:10]:
                dates_rebuilt[f"{iso_col}: replaced"] += 1
            row[iso_col] = rebuilt

        # A year outside the register's span, repaired from the other date on
        # the same record where that one is in span.
        for iso_col, other_col in (
            ("Admission Date [ISO]", "Discharge Date (ISO)"),
            ("Discharge Date (ISO)", "Admission Date [ISO]"),
        ):
            broken = to_date(row.get(iso_col, ""))
            if not broken or broken.year in REGISTER_YEARS:
                continue
            anchor = to_date(row.get(other_col, ""))
            if not anchor or anchor.year not in REGISTER_YEARS:
                dates_rebuilt[f"{iso_col}: year outside 1930-48, nothing to repair it from"] += 1
                if "date-out-of-span" not in flags:
                    flags.append("date-out-of-span")
                continue
            # An admission may fall in the year before its discharge, and a
            # discharge in the year after its admission.
            year = anchor.year
            if iso_col.startswith("Admission") and (broken.month, broken.day) > (anchor.month, anchor.day):
                year -= 1
            if iso_col.startswith("Discharge") and (broken.month, broken.day) < (anchor.month, anchor.day):
                year += 1
            try:
                row[iso_col] = broken.replace(year=year).isoformat()
            except ValueError:  # 29 February
                dates_rebuilt[f"{iso_col}: year outside 1930-48, nothing to repair it from"] += 1
                flags.append("date-out-of-span")
                continue
            dates_rebuilt[f"{iso_col}: year outside 1930-48, taken from the other date"] += 1
            flags.append("date-year-repaired")

        admitted = to_date(row.get("Admission Date [ISO]", ""))
        discharged = to_date(row.get("Discharge Date (ISO)", ""))
        if "Days in Hospital (Calc)" in row:
            if admitted and discharged:
                stay = (discharged - admitted).days
                # A discharge before an admission is not a short stay, it is a
                # broken record. 43 survive the repair — the clerk's own slips,
                # a wrong year written into the register itself. Publishing a
                # negative number invites it into a mean; publishing nothing
                # says what is actually known. The dates stay, so the record
                # can still be looked up and read.
                if stay < 0:
                    row["Days in Hospital (Calc)"] = ""
                    stays_cleared += 1
                    flags.append("impossible-stay")
                else:
                    row["Days in Hospital (Calc)"] = str(stay)
                    reported = row.get("Days in Hospital (Rep)", "").strip()
                    if stay > 365 and reported.isdigit() and stay - int(reported) in (365, 366):
                        # Handled after the sequence pass, where the discharge
                        # year is corrected against the clerk's own count.
                        pass
                    elif reported.isdigit() and stay != int(reported):
                        flags.append("stay-disagrees")
            else:
                row["Days in Hospital (Calc)"] = ""

        chapter = row.get("ICD-9 Chapter", "")
        if PROCEDURE.search(written_diag):
            row["Procedure"] = "Procedure and diagnosis" if chapter else "Procedure only"
            procedures[row["Procedure"]] += 1
            if not chapter:
                flags.append("procedure-only")
        else:
            row["Procedure"] = ""

        # A Result value or a classifier error in a diagnosis field is neither a
        # diagnosis nor a missing one: it is the wrong column's content, and
        # saying so is more use than filing it with the genuinely unrecorded.
        code_field = (row.get("Primary-ICD9", "") or "").strip()
        if RESULT_IN_WRONG_COLUMN.match(written_diag) or RESULT_IN_WRONG_COLUMN.match(code_field):
            flags.append("result-in-diagnosis")
        elif written_diag and CLASSIFIER_DEBRIS.search(written_diag):
            flags.append("classifier-debris")

        if not chapter:
            flags.append("no-icd9-chapter")

        # Written in the documented order, so the app can rank without knowing
        # anything about what the flags mean.
        order = [name for name, _ in REVIEW_FLAGS]
        row["Review Flags"] = "|".join(sorted(set(flags), key=order.index))
        for flag in set(flags):
            review_counts[flag] += 1

        # The extraction sometimes filed the next of kin's name into another
        # field. Withholding the column would leave those names in place, so any
        # field that simply repeats this record's next of kin is cleared.
        #
        # Two guards, because the confusion runs both ways — some records carry
        # "Isolation" or "Haifa" as next of kin, and clearing every field that
        # matched would destroy good data:
        #
        #   * in the free-text fields, a value is kept only if it works as a
        #     place elsewhere in the registers (Haifa stays, Abdel Yahud goes);
        #   * in the coded columns, a value is kept if it is an established
        #     value of its column (Isolation stays).
        kin = (row.get("Next of Kin") or "").strip().lower()
        if kin:
            for field, value in list(row.items()):
                if field == "Next of Kin" or not value:
                    continue
                stripped = value.strip()
                if stripped.lower() != kin:
                    continue
                common = (
                    place_vocabulary[stripped] if field in FREE_TEXT_FIELDS
                    else column_values[field][stripped]
                )
                if common < KIN_RARITY:
                    row[field] = ""
                    kin_in_place[field] += 1

        # Second pass: a known kin name sitting in a free-text field of any
        # record, whether or not that record names a next of kin itself.
        for field in FREE_TEXT_FIELDS:
            value = (row.get(field) or "").strip()
            if value and value.lower() in kin_names:
                row[field] = ""
                kin_elsewhere[field] += 1

        # City is the one field cleaned in place, since the source has no second
        # column for it. The clerk's spelling is preserved beside it.
        if "City" in row:
            written = (row["City"] or "").strip()
            row["City as written"] = written
            cleaned = normalize_city(written)
            if cleaned != written:
                changes[("City", written, cleaned)] += 1
            row["City"] = cleaned
            if city_from_street(coarsen_address(row.get("Address") or ""), cleaned):
                changes[("City", f"{cleaned} (the address is Haifa's {cleaned}-named street)", "Haifa")] += 1
                cleaned = "Haifa"
                row["City"] = cleaned
                street_reseated += 1
            # "Ramleh Village" is Rameh (al-Rama), not the town of Ramleh: the
            # village qualifier, or an Acre-district address, marks the Galilee
            # village whichever way the clerk spelled it.
            if cleaned == "Ramleh" and re.search(r"village|acre", row.get("Address") or "", re.IGNORECASE):
                changes[("City", "Ramleh (the address says village / Acre district)", "Rameh")] += 1
                cleaned = "Rameh"
                row["City"] = cleaned
            kima_id, qid = kima_links.get(cleaned, ("", ""))
            row["City Kima ID"] = kima_id
            row["City Wikidata"] = qid
            if kima_id:
                kima_linked += 1

        if "Address" in row:
            before = row["Address"] or ""
            after = coarsen_address(before)
            if after != before:
                coarsened += 1
            row["Address"] = after

        out_rows.append(row)

    # ------------------------------------------------- years out of sequence
    #
    # A register is written in order, so a stretch of records whose admissions
    # run backwards against what surrounds them is a misread year, not patients
    # admitted a year earlier. The misreadings arrive a page at a time — the
    # year read once at the head of a page and carried down it — so the notebook
    # is split into runs of a single year and a whole run is judged at once:
    # notebook 24 reads 1.12.39 for 34 records, then 33 records of "38", then
    # 5.12.39 onwards. The middle run is the page. Shifting it by a year seats
    # it exactly between the two runs around it, so the whole run moves.
    #
    # Both dates move together, by the same shift, so the length of stay the
    # clerk wrote beside each record is preserved — which is the corroboration
    # that the year, and only the year, was misread.
    sequence_repairs: Counter[int] = Counter()
    notebooks: dict[str, list[dict[str, str]]] = {}
    for row in out_rows:
        notebooks.setdefault(row.get("Notebook_Number", ""), []).append(row)

    # ------------------------------------- out of span, seated by the order
    #
    # Two records in notebook 8 read "17/5/63", fifteen years past the last
    # register, and neither carries a discharge for the pass above to take a
    # year from — so all it could do was flag them. The register's own order
    # answers instead: they sit between record 406 and record 408, and both of
    # those read 17.3.34. A date outside 1930-48 whose nearest in-span
    # neighbours on either side carry the same date is that date. The day
    # survives the misreading intact in both, which is the corroboration that
    # what went wrong was the rest of it.
    #
    # Nothing less than exact agreement on both sides will do. A date taken
    # from the order rather than from the page is a reconstruction, and it is
    # only worth making where the order leaves no room for a second answer;
    # anywhere else the flag, and a person with the scan, is the right outcome.
    span_seated = 0
    for items in notebooks.values():
        if len(items) < MIN_NOTEBOOK_RECORDS:
            continue
        values = [to_date(row.get("Admission Date [ISO]", "")) for row in items]
        in_span = [v if v and v.year in REGISTER_YEARS else None for v in values]

        for position, value in enumerate(values):
            if not value or in_span[position]:
                continue
            before = next((v for v in reversed(in_span[:position]) if v), None)
            after = next((v for v in in_span[position + 1:] if v), None)
            if before is None or before != after:
                continue

            row = items[position]
            row["Admission Date [ISO]"] = before.isoformat()
            in_span[position] = before
            span_seated += 1

            # The discharge, if there is one, is left exactly as it was: this
            # rule reads the admission column's order and has nothing to say
            # about the other date. Only the stay is recomputed, and only where
            # both ends are now readable.
            discharged = to_date(row.get("Discharge Date (ISO)", ""))
            if "Days in Hospital (Calc)" in row and discharged:
                stay = (discharged - before).days
                row["Days in Hospital (Calc)"] = str(stay) if stay >= 0 else ""

            flags = [f for f in (row.get("Review Flags") or "").split("|") if f]
            # The flag said there was nothing on the record to repair the date
            # from, and for the admission that is no longer true. It stays if
            # the discharge is the one out of span.
            if "date-out-of-span" in flags and not (discharged and discharged.year not in REGISTER_YEARS):
                flags.remove("date-out-of-span")
                review_counts["date-out-of-span"] -= 1
            if "date-seated-by-order" not in flags:
                flags.append("date-seated-by-order")
                review_counts["date-seated-by-order"] += 1
            order = [name for name, _ in REVIEW_FLAGS]
            row["Review Flags"] = "|".join(sorted(set(flags), key=order.index))

    for notebook, items in notebooks.items():
        dated = [(row, to_date(row.get("Admission Date [ISO]", ""))) for row in items]
        dated = [(row, value) for row, value in dated if value]
        if len(dated) < MIN_NOTEBOOK_RECORDS:
            continue

        values = [value for _, value in dated]
        shifts = [0] * len(values)
        runs = year_runs(values)
        for (start, end, _), years in zip(runs, resolve_year_shifts(values, runs)):
            for position in range(start, end):
                shifts[position] = years

        for (row, value), years in zip(dated, shifts):
            if years == 0:
                continue
            admitted = shift_years(value, years)
            if admitted is None:
                continue
            row["Admission Date [ISO]"] = admitted.isoformat()

            # The discharge does not always carry the same misreading: in
            # notebook 23 the clerk's "7.10.38" was read a year low while the
            # discharge beside it, "21.10.39", was read correctly. So the
            # discharge follows the admission only where that is what
            # reproduces the length of stay written beside the record.
            discharged = to_date(row.get("Discharge Date (ISO)", ""))
            if discharged:
                reported = (row.get("Days in Hospital (Rep)") or "").strip()
                options = [option for option in (shift_years(discharged, years), discharged) if option]
                if reported.isdigit():
                    options.sort(key=lambda option: abs((option - admitted).days - int(reported)))
                else:
                    options.sort(key=lambda option: (option - admitted).days < 0)
                if options:
                    row["Discharge Date (ISO)"] = options[0].isoformat()
                    stay = (options[0] - admitted).days
                    row["Days in Hospital (Calc)"] = str(stay) if stay >= 0 else ""
            sequence_repairs[years] += 1

            flags = [f for f in (row.get("Review Flags") or "").split("|") if f]
            if "date-year-out-of-sequence" not in flags:
                flags.append("date-year-out-of-sequence")
                review_counts["date-year-out-of-sequence"] += 1
            order = [name for name, _ in REVIEW_FLAGS]
            row["Review Flags"] = "|".join(sorted(set(flags), key=order.index))

    # ------------------------------------------------ months, and some days
    #
    # The same argument one component down. A record sitting between 9.7.33 and
    # 10.7.33 but reading 9.6.33 has a month misread, not a patient admitted a
    # month early, and taking the month from its neighbours seats it exactly.
    #
    # Days are held to a stricter test: only a day one written digit from the
    # one recorded is entertained. Registers are full of admissions entered a
    # few days late — a record reading 16.2 among 22.2 entries is a late entry,
    # and 16 is no misreading of 22 — so without that test the pass would tidy
    # the register's own working habits out of the record.
    component_repairs: Counter[str] = Counter()
    for notebook, items in notebooks.items():
        dated = [(row, to_date(row.get("Admission Date [ISO]", ""))) for row in items]
        dated = [(row, value) for row, value in dated if value]
        if len(dated) < MIN_NOTEBOOK_RECORDS:
            continue

        for position in range(1, len(dated) - 1):
            row, value = dated[position]
            previous = dated[position - 1][1]
            following = dated[position + 1][1]
            if previous - SEQUENCE_SLACK <= value <= following + SEQUENCE_SLACK:
                continue
            if previous > following:  # the neighbours disagree; no seat to take
                continue
            mended = repair_component(previous, value, following)
            if mended is None:
                continue
            admitted, component = mended

            # The clerk's own count decides. Ordering alone was not enough
            # here: on its own it produced repairs that seated the record
            # tidily and disagreed with the days he wrote beside it — a 16-day
            # stay turned into 10 — and agreement with his counts fell across
            # the file. A component only moves where his figure comes out
            # right, or, where he wrote none, where the stay stays possible.
            discharged = to_date(row.get("Discharge Date (ISO)", ""))
            reported = (row.get("Days in Hospital (Rep)") or "").strip()
            moved = discharged
            if discharged:
                try:
                    same = discharged.replace(**{component: getattr(admitted, component)})
                except ValueError:
                    same = discharged
                candidates = [discharged, same]
                if reported.isdigit():
                    moved = min(candidates, key=lambda option: abs((option - admitted).days - int(reported)))
                    if (moved - admitted).days != int(reported):
                        continue
                else:
                    moved = min(candidates, key=lambda option: (option - admitted).days < 0)
                    if (moved - admitted).days < 0 or component == "day":
                        continue
            elif component == "day":
                # Nothing at all to check a day against.
                continue

            row["Admission Date [ISO]"] = admitted.isoformat()
            if moved:
                row["Discharge Date (ISO)"] = moved.isoformat()
                row["Days in Hospital (Calc)"] = str((moved - admitted).days)

            dated[position] = (row, admitted)
            component_repairs[component] += 1

            # The record no longer discharges before it admits, so the flag
            # raised for that earlier no longer describes it.
            stale = [f for f in (row.get("Review Flags") or "").split("|") if f == "impossible-stay"]
            if stale and row.get("Days in Hospital (Calc)"):
                review_counts["impossible-stay"] -= 1
                stays_cleared -= 1
                row["Review Flags"] = "|".join(
                    f for f in row["Review Flags"].split("|") if f and f != "impossible-stay"
                )

            flag = f"date-{component}-out-of-sequence"
            flags = [f for f in (row.get("Review Flags") or "").split("|") if f]
            if flag not in flags:
                flags.append(flag)
                review_counts[flag] += 1
            order = [name for name, _ in REVIEW_FLAGS]
            row["Review Flags"] = "|".join(sorted(set(flags), key=order.index))

    # ------------------------------------------- discharge a year too high
    #
    # The other half of the same misreading, and the one that produced the
    # year-long hospitalizations: the admission is where its neighbours are, but
    # the discharge year is one above it — notebook 24's record 3990, admitted
    # 4.12.38 and discharged, as read, 4.1.40, for a stay of 396 days against
    # the 31 the clerk wrote beside it. The clerk's own count is the witness
    # here, so the correction is applied only where the stay falls to exactly
    # what he wrote once a year is taken off the discharge.
    for row in out_rows:
        admitted = to_date(row.get("Admission Date [ISO]", ""))
        discharged = to_date(row.get("Discharge Date (ISO)", ""))
        reported = (row.get("Days in Hospital (Rep)") or "").strip()
        if not admitted or not discharged or not reported.isdigit():
            continue
        stay = (discharged - admitted).days
        if stay <= 365 or stay - int(reported) not in (365, 366):
            continue
        moved = shift_years(discharged, -1)
        if not moved or (moved - admitted).days != int(reported):
            continue
        row["Discharge Date (ISO)"] = moved.isoformat()
        row["Days in Hospital (Calc)"] = str(int(reported))
        stays_over_a_year += 1

        flags = [f for f in (row.get("Review Flags") or "").split("|") if f]
        if "stay-over-by-a-year" not in flags:
            flags.append("stay-over-by-a-year")
            review_counts["stay-over-by-a-year"] += 1
        order = [name for name, _ in REVIEW_FLAGS]
        row["Review Flags"] = "|".join(sorted(set(flags), key=order.index))

    # --------------------------------------------- record numbers out of run
    #
    # The clerk's running serial is as ordered as his dates, and the same
    # argument applies: a block of numbers that leaves the run and hands back
    # to it afterwards is a misreading, not a renumbering. Notebook 11's page
    # 61 carries 645-649 read as 6445-6449 (one "4" doubled; 6447 = 647,
    # verified on the scan), page 14 carries 146-150 read with a leading "1".
    # A block is repaired only when one constant shift seats every member
    # strictly inside the gap AND the shift is mechanical - a whole number of
    # hundreds (a dropped or added prefix), or the same single digit slipped
    # into the same position in every member. Genuine restarts of the
    # numbering never hand back to the old run, so they are left alone;
    # blocks that hand back but fail the safety test (duplicated pages,
    # stray values from another column) are flagged, never guessed at.
    def one_digit_slip(raw: str, fixed: str) -> "tuple[int, str] | None":
        # fixed -> raw by inserting one digit; returns (position, digit).
        if len(raw) != len(fixed) + 1:
            return None
        for i in range(len(raw)):
            if raw[:i] + raw[i + 1:] == fixed:
                return (i, raw[i])
        return None

    serial_blocks: list[tuple[str, str, str, int, bool]] = []
    by_notebook: dict[str, list] = {}
    for row in out_rows:
        by_notebook.setdefault(row.get("Notebook_Number") or "", []).append(row)
    for notebook, items in by_notebook.items():
        seq = [(row, int(v)) for row in items
               if (v := (row.get("Notebook Record ID") or "").strip()).isdigit()]
        j = 0
        while j < len(seq) - 1:
            value = seq[j][1]
            if -2 <= seq[j + 1][1] - value <= 6:
                j += 1
                continue
            resume = next((k for k in range(j + 2, min(j + 18, len(seq)))
                           if 0 < seq[k][1] - value <= (k - j) + 6), None)
            if resume is None:
                j += 1
                continue
            block = seq[j + 1:resume]
            # The block's true position inside the gap is not known (a blank
            # id may hold one of the seats), so every placement is tried and a
            # repair is accepted only when exactly one of them is mechanical.
            workable = []
            for start in range(value + 1, seq[resume][1] - len(block) + 1):
                offset = block[0][1] - start
                shifted = [raw - offset for _, raw in block]
                if not (all(b > a for a, b in zip(shifted, shifted[1:]))
                        and shifted[0] > value and shifted[-1] < seq[resume][1]):
                    continue
                slips = {one_digit_slip(str(raw), str(raw - offset)) for _, raw in block}
                # Mechanical means a prefix dropped or added whole (the raw
                # and repaired numbers are suffixes of one another), or the
                # same single digit slipped into the same position throughout.
                prefix_slip = all(str(raw).endswith(str(raw - offset))
                                  or str(raw - offset).endswith(str(raw))
                                  for _, raw in block)
                if prefix_slip or (None not in slips and len(slips) == 1):
                    workable.append(offset)
            label = f"notebook {notebook}: {block[0][1]}-{block[-1][1]} between {value} and {seq[resume][1]}"
            if len(block) >= 2 and len(workable) == 1:
                offset = workable[0]
                for row, raw in block:
                    row["Notebook Record ID"] = str(raw - offset)
                    flags = [f for f in (row.get("Review Flags") or "").split("|") if f]
                    if "serial-repaired" not in flags:
                        flags.append("serial-repaired")
                        review_counts["serial-repaired"] += 1
                    order = [name for name, _ in REVIEW_FLAGS]
                    row["Review Flags"] = "|".join(sorted(set(flags), key=order.index))
                serial_blocks.append((label, str(block[0][1] - offset), str(block[-1][1] - offset), len(block), True))
            else:
                for row, _ in block:
                    flags = [f for f in (row.get("Review Flags") or "").split("|") if f]
                    if "serial-out-of-sequence" not in flags:
                        flags.append("serial-out-of-sequence")
                        review_counts["serial-out-of-sequence"] += 1
                    order = [name for name, _ in REVIEW_FLAGS]
                    row["Review Flags"] = "|".join(sorted(set(flags), key=order.index))
                serial_blocks.append((label, "", "", len(block), False))
            j = resume

    # Written by hand rather than through csv.writer: the registers contain bare
    # double quotes (inches, gershayim) and any escaping of them would have to be
    # undone by every consumer. Tabs and newlines inside a value are the only
    # things that could break the format, so those are the only things touched.
    def cell(value: str) -> str:
        return re.sub(r"[\t\r\n]+", " ", value or "").strip()

    if "Procedure" not in fieldnames:
        at = fieldnames.index("StandardICDInteger") + 1 if "StandardICDInteger" in fieldnames else len(fieldnames)
        fieldnames.insert(at, "Procedure")
    if "Review Flags" not in fieldnames:
        fieldnames.append("Review Flags")
    if "City as written" not in fieldnames and "City" in fieldnames:
        fieldnames.insert(fieldnames.index("City"), "City as written")
    if "City Kima ID" not in fieldnames and "City" in fieldnames:
        at = fieldnames.index("City") + 1
        fieldnames.insert(at, "City Kima ID")
        fieldnames.insert(at + 1, "City Wikidata")

    if "ICD-9 Chapter" not in fieldnames:
        at = fieldnames.index("StandardICDInteger") + 1 if "StandardICDInteger" in fieldnames else len(fieldnames)
        fieldnames.insert(at, "ICD-9 Chapter")

    if "Diagnosis Recording" not in fieldnames:
        at = fieldnames.index("ICD-9 Chapter") + 1
        fieldnames.insert(at, "Diagnosis Recording")

    fieldnames = [name for name in fieldnames if name not in DROP_COLUMNS]

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
        for (occupation, ward, source), count in sorted(ward_rehomed.items()):
            what = {
                "written": f"Ward: {ward}, read from the clerk's written ward",
                "occupation": f"Ward: {ward}",
                "duplicate": f"cleared; the ward column already carries {ward}",
            }[source]
            writer.writerow(["moved", "Occupation", occupation, what, count])
        if ward_corrected:
            writer.writerow(["corrected", "standardized ward", "Gynecology",
                             "General — the page reads Gen., notebook 11 record 86", ward_corrected])
        for value, count in procedures.most_common():
            writer.writerow(["derived", "Procedure", "operation named in the diagnosis column", value, count])
        for name, description in REVIEW_FLAGS:
            if review_counts[name]:
                writer.writerow(["review", "Review Flags", name, description, review_counts[name]])
        for name in sorted(DROP_COLUMNS):
            writer.writerow(["withheld", name, "", "", len(out_rows)])
        for field, count in sorted(kin_in_place.items()):
            writer.writerow(["withheld", field, "value repeated the next of kin", "", count])
        for field, count in sorted(kin_elsewhere.items()):
            writer.writerow(["withheld", field, "value is a name known from the kin column", "", count])
        if kima_linked:
            writer.writerow(["derived", "City Kima ID", "reviewed match in kimatch/city-kima-decisions.tsv",
                             "Kima place id and Wikidata QID attached", kima_linked])
        for label, count in chapters.most_common():
            writer.writerow(["derived", "ICD-9 Chapter", "", label, count])
        if icd9_padded:
            writer.writerow(["derived", "ICD-9 Chapter", "code missing a leading zero", "padded to three digits", icd9_padded])
        if icd9_refused:
            writer.writerow(["derived", "ICD-9 Chapter", "procedure code, not a diagnosis", "left without a chapter", icd9_refused])
        if chapters_unresolved:
            writer.writerow(["derived", "ICD-9 Chapter", "", "no readable code", chapters_unresolved])
        for label, count in recording.most_common():
            writer.writerow(["derived", "Diagnosis Recording", "", label, count])
        for name, count in sorted(component_repairs.items()):
            writer.writerow(["date", "Admission Date [ISO]", "ran backwards against the register's order",
                             f"{name} taken from the neighbouring records", count])
        for years, count in sorted(sequence_repairs.items()):
            writer.writerow(["date", "Admission Date [ISO]", "ran backwards against the register's order",
                             f"year shifted by {years:+d}", count])
        for label, first, last, count, repaired in serial_blocks:
            if repaired:
                writer.writerow(["serial", "Notebook Record ID", label, f"repaired to {first}-{last}", count])
            else:
                writer.writerow(["serial", "Notebook Record ID", label, "no safe repair; flagged for review", count])
        for label, count in dates_rebuilt.most_common():
            column, _, what = label.partition(": ")
            writer.writerow(["date", column, "upstream ISO", what, count])
        if stays_cleared:
            writer.writerow(
                ["date", "Days in Hospital (Calc)", "discharge before admission", "cleared", stays_cleared]
            )
        if span_seated:
            writer.writerow(
                ["date", "Admission Date [ISO]", "year outside 1930-48, nothing on the record to repair it from",
                 "taken whole from the identical dates either side of it in the register", span_seated]
            )
        if stays_over_a_year:
            writer.writerow(
                ["unresolved", "Discharge Date (ISO)", "stay exceeds the clerk's own count by a year",
                 "discharge year taken down one, to the clerk's own count", stays_over_a_year]
            )
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
    if ward_rehomed:
        seated = sum(c for (_, _, source), c in ward_rehomed.items() if source != "duplicate")
        print(f"wards      {sum(ward_rehomed.values())} ward name(s) taken out of Occupation, "
              f"{seated} seated in an empty ward column"
              + (f", {ward_corrected} corrected by hand against the scan" if ward_corrected else ""))
    print(f"withheld   {', '.join(sorted(DROP_COLUMNS))}")
    if kin_in_place:
        detail = ", ".join(f"{field} {count}" for field, count in sorted(kin_in_place.items()))
        print(f"           plus a next-of-kin name standing in another field: {detail}")
    if kin_elsewhere:
        detail = ", ".join(f"{field} {count}" for field, count in sorted(kin_elsewhere.items()))
        print(f"           and a name known from the kin column elsewhere: {detail}")
    replaced = sum(n for k, n in dates_rebuilt.items() if k.endswith("replaced"))
    kept = sum(n for k, n in dates_rebuilt.items() if k.endswith("upstream kept"))
    print(f"chapters   {sum(chapters.values()):,} records placed in {len(chapters)} ICD-9 chapters, {chapters_unresolved:,} without a readable code")
    print(f"           {icd9_padded} short code(s) padded, {icd9_refused} procedure code(s) refused a chapter")
    print(f"recording  of the unclassified: {recording['Recorded, not classified']:,} carry a diagnosis "
          f"the coding never reached, {recording['Not recorded']:,} carry none at all")
    if component_repairs:
        detail = ", ".join(f"{count} by {name}" for name, count in sorted(component_repairs.items()))
        print(f"component  {sum(component_repairs.values()):,} admission(s) mended one component: {detail}")
    if span_seated:
        print(f"out-of-span {span_seated} admission(s) outside 1930-48, seated on the register's own order")
    if sequence_repairs:
        detail = ", ".join(
            f"{count} by {years:+d} year" + ("s" if abs(years) > 1 else "")
            for years, count in sorted(sequence_repairs.items())
        )
        print(f"sequence   {sum(sequence_repairs.values()):,} admission(s) that ran backwards, year corrected: {detail}")
    print(f"dates      {replaced:,} ISO date(s) rebuilt from the verbatim column, {kept:,} left as upstream had them")
    print(f"stays      {stays_cleared} impossible length(s) of stay cleared, "
          f"{stays_over_a_year} discharge year(s) a year over the clerk's own count, corrected")
    tail = {
        (col, val): n
        for col, counts in final_values.items()
        for val, n in counts.items()
        if n < TAIL_THRESHOLD
    }
    print(f"tail       {len(tail)} value(s) left standing on fewer than {TAIL_THRESHOLD} records")
    if classification:
        print(f"secondpass {second_pass:,} record(s) coded from {len(classification)} reviewed strings "
              f"in {CLASSIFICATION.name}")
    print(f"procedures {sum(procedures.values()):,} record(s) name an operation: "
          + ", ".join(f"{n:,} {v.lower()}" for v, n in procedures.most_common()))
    flagged = sum(1 for row in out_rows if row.get("Review Flags"))
    print(f"review     {flagged:,} record(s) flagged for a human eye across {len(review_counts)} kinds")
    for name, _ in REVIEW_FLAGS:
        if review_counts[name]:
            print(f"           {review_counts[name]:>6,}  {name}")
    print(f"report     {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
