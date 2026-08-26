"""Concordance of epidemic-disease mentions, datelined to Haifa, in the press corpus.

Generalises the single case that started this: al-Difa' of 21 October 1947
reported four children admitted to the Haifa Government Hospital with
diphtheria, calling the disease "returning" to the city. The register holds 27
diphtheria admissions between 10 September and 25 October 1947 and six child
deaths. The press noticed an epidemic that was already seven weeks old. The
question this script exists to answer is how often that holds — for which
diseases the press led the register, for which it lagged, and for which it said
nothing at all.

Reads data/newspapers/page_texts.jsonl (from jrayed_text_harvest.py) and writes
data/newspapers/epidemic_concordance.tsv, one row per disease mention window.

Three things distinguish it from jrayed_concordance.py:

  1. It matches a disease lexicon, not مستشف*. Each of the eleven diseases is
     given its period Arabic names with definite-article, orthographic and
     Optical Character Recognition (OCR) variants — الخناق as well as الدفتريا
     for diphtheria, البرداء as well as الملاريا for malaria, النزلة الوافدة as
     well as الانفلونزا for influenza.

  2. It keeps the paragraph structure the archive's markup carries, instead of
     flattening the page to one string. Both papers were published in Jaffa and
     ran their local news town by town, under a section heading (a paragraph
     reading just حيفا) and with each item carrying its own dateline
     (حيفا في ١٩ ايلول - لمراسل الدفاع الخاص). That is the only reliable way to
     tell a Haifa report from a Jaffa or Hebron one: unqualified
     المستشفى الحكومي belongs to whichever town the dateline names. Proximity
     alone cannot do it, so the Haifa evidence is graded and reported per row
     rather than used as a silent filter.

  3. The window is 150 characters each side, following the finding recorded in
     jrayed_concordance.py that wider windows report at a higher rate and
     tightening only loses evidence.

Corpus caveat, which governs how the negatives may be read: page_texts.jsonl is
not the run of the two papers. It is the 4,150 pages that already matched
مستشفى الحكومة (or المستشفى الحكومي) together with حيفا at the page level. A
disease absent from this concordance was absent from the pages that mention the
government hospital — not necessarily from the newspaper.

Run: python3 pipeline/epidemic_concordance.py [--context 150]
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "data", "newspapers", "page_texts.jsonl")
OUT = os.path.join(ROOT, "data", "newspapers", "epidemic_concordance.tsv")

MONTHS = {m: i + 1 for i, m in enumerate(
    "January February March April May June July August September October "
    "November December".split())}

AR = "ء-ي"          # Arabic letters, for the boundary lookarounds
DIACRITICS = re.compile(r"[ً-ْـٰ]")   # harakat + tatweel

# Attached prefixes. Veridian's own index keeps ال/و on the token, and the OCR
# reproduces whatever the compositor set, so every stem is matched with the
# clitics that can precede it rather than with a bare word boundary.
PREFIX = r"(?:و|ف|ب|ل|ك|بال|فال|وال|لل|كال|ال|)"

# disease -> alternation of stems. Stems are written against text that has
# already been normalised (alef forms folded to ا, ى to ي, ة to ه), so a stem
# ends in ه where the printed word ends in ة.
#
# Order matters only where two diseases share an OCR neighbourhood: تيفوئيد and
# تيفوس are one dropped letter apart, so typhoid's stems are written to require
# the ئيد/ويد/يه ending and typhus's to require the وس, and neither can swallow
# the other.
DISEASES: dict[str, str] = {
    "typhoid": r"(?:تيفوييد|تيفوئيد|تيفويد|تيفود|تيفيد|تيفوييم|تيفوييدي|"
               r"تيفويديه|براتيفوييد|باراتيفوييد|حمي\s+معويه)",
    "typhus": r"(?:تيفوس)",
    "malaria": r"(?:ملاريا|ملاريه|مالاريا|ملاري)",
    "smallpox": r"(?:جدري|جديري)",
    "cholera": r"(?:كوليرا|كولرا|كوليره)",
    "diphtheria": r"(?:دفتريا|دفتيريا|ديفتيريا|ديفثيريا|دفثيريا|دفتري|"
                  r"خناق|خوانيق)",
    "measles": r"(?:حصبه|حصب\b)",
    "dysentery": r"(?:زحار|زحاره|ديزنطاريا|دوسنطاريا|دوسنتاريا|دسنطاريا|"
                 r"ديسنطاريا|اسهال\s+دموي)",
    "trachoma": r"(?:تراخوما|تراكوما|رمد\s+(?:ال)?حبيبي)",
    "plague": r"(?:طاعون|طواعين)",
    "influenza": r"(?:انفلونزا|انفلونزه|انفلونز|نزله\s+وافده|زكام)",
}

# Lexical traps found by reading the first pass, each recorded here rather than
# fixed silently: they are facts about the corpus, not about the regex.
#
#   الكريب — "grippe" would be the obvious influenza term, and it is the
#     commonest string in the corpus that looks like one (382 windows). All but
#     a handful are كريب فروت, grapefruit, in the citrus shipping columns; the
#     rest are crêpe, the fabric, in auction notices. Dropped entirely.
#   البرداء — the classical word for malaria, but every hit was رداءة (poorness)
#     or the surname Brodetsky through the OCR. Dropped.
#   الجدري المائي — chickenpox, not smallpox.
#   طاعون الدجاج — fowl plague, an animal-quarantine story, not human plague.
#   الهيضة — classical cholera; the only hits were المهيضة. Dropped.
#   الرمد الحبيبي — trachoma, but حبيبي alone is "my beloved" (110 hits), so
#     the term is only matched with رمد attached.
#
# What survives the traps but stays ambiguous is flagged per row in soft_term
# rather than dropped, so a reader can weigh it:
#   الخناق is diphtheria in medical copy and "quarrel"/"throat" idiomatically
#   الزكام is a head cold as often as influenza
#   a plague window whose sentence is about طاعون الدجاج further off than the
#     exclusion reaches - the fowl-plague quarantines of 1940 and 1944 ran in
#     the same columns as the human ones
NOT_SMALLPOX = re.compile(r"جدري\s*(?:ال)?مايي|جدري\s*(?:ال)?مائي")
NOT_PLAGUE = re.compile(r"طاعون\s*(?:ال)?(?:دجاج|بقر|مواشي|حيوان|خنازير|"
                        r"طيور|ماشيه)")
SOFT_TERM = {"diphtheria": re.compile(r"خناق|خوانيق"),
             "influenza": re.compile(r"زكام")}

TOWNS = {
    "حيفا": "Haifa", "يافا": "Jaffa", "القدس": "Jerusalem", "الخليل": "Hebron",
    "نابلس": "Nablus", "غزه": "Gaza", "اللد": "Lydda", "الرمله": "Ramla",
    "طولكرم": "Tulkarm", "عكا": "Acre", "صفد": "Safad", "طبريا": "Tiberias",
    "الناصره": "Nazareth", "بيسان": "Beisan", "جنين": "Jenin",
    "بئر السبع": "Beersheba", "بيت لحم": "Bethlehem", "رام الله": "Ramallah",
    "يركا": "Yarka", "دمشق": "Damascus", "بيروت": "Beirut", "القاهره": "Cairo",
    "بغداد": "Baghdad", "عمان": "Amman",
}
TOWN_ALT = "|".join(sorted(map(re.escape, TOWNS), key=len, reverse=True))

# "حيفا في ١٩ ايلول" / "حيفا - ٣ نيسان" — the item's own dateline, at its head.
DATELINE = re.compile(rf"(?:^|[\s:،.-]){PREFIX}?({TOWN_ALT})\s*(?:في|فى)?\s*"
                      rf"[٠-٩۰-۹0-9]{{1,2}}\s*"
                      rf"(?:كانون|شباط|اذار|نيسان|ايار|حزيران|تموز|اب|ايلول|"
                      rf"تشرين|ك\s*[٠-٩1-2]|ت\s*[٠-٩1-2]|"
                      rf"يناير|فبراير|مارس|ابريل|مايو|يونيو|يوليو|اغسطس|"
                      rf"سبتمبر|اكتوبر|نوفمبر|ديسمبر)")
# "قال مراسلنا في حيفا" / "لمراسل الدفاع الخاص في حيفا"
CORRESPONDENT = re.compile(rf"مراسل\w*\s+(?:الدفاع\s+|فلسطين\s+)?(?:الخاص\s+)?"
                           rf"(?:في|فى)\s+({TOWN_ALT})")
HAIFA = re.compile(rf"(?<![{AR}])(?:و|ف|ب|ل|ك|)حيفا(?![{AR}])")
HOSPITAL = re.compile(rf"(?<![{AR}]){PREFIX}مستشف")
# words that mark the mention as an outbreak report rather than a passing use
EPIDEMIC = re.compile(r"وباء|وبائ|اوبئه|تفشي|انتشر|منتشر|حجر\s*صحي|"
                      r"اصابه|اصابات|مصاب|توفي|وفاه|وفيات|حاله|حالات|"
                      r"مستشف|عزل|تطعيم|تلقيح|لقاح")


def iso(date: str) -> str:
    m = re.match(r"(\d+) (\w+) (\d{4})", date or "")
    if not m:
        return date or ""
    return f"{m.group(3)}-{MONTHS.get(m.group(2), 0):02d}-{int(m.group(1)):02d}"


def normalise(raw: str) -> list[str]:
    """Page markup -> list of paragraphs, orthography folded for matching.

    Entities arrive double-escaped. The paragraph split has to happen before the
    tags are stripped, because <p> is the only record left of the column's
    typographic structure, and that structure is what carries the datelines.
    """
    t = html.unescape(html.unescape(raw))
    parts = re.split(r"</p\s*>|<br\s*/?>", t)
    out = []
    for p in parts:
        p = re.sub(r"<[^>]+>", " ", p)
        p = DIACRITICS.sub("", p)
        p = (p.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
              .replace("ى", "ي").replace("ة", "ه").replace("ؤ", "ء")
              .replace("ئ", "ي"))
        p = " ".join(p.split())
        if p:
            out.append(p)
    return out


def section_towns(paras: list[str]) -> list[str]:
    """Carry each local-news section heading down over the items beneath it.

    A heading is a paragraph that is nothing but a town name (sometimes with
    اخبار or a rule character around it). Everything after it belongs to that
    town until the next heading.
    """
    cur = ""
    out = []
    for p in paras:
        bare = re.sub(rf"^(?:اخبار|انباء|من)\s+", "", p).strip(" .:،-—_|")
        if len(bare) <= 12 and bare in TOWNS:
            cur = TOWNS[bare]
        out.append(cur)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context", type=int, default=150,
                    help="chars of context each side of the disease term. 150 "
                         "follows jrayed_concordance.py: wider windows report "
                         "at a higher rate and tightening only loses evidence")
    ap.add_argument("--lookback", type=int, default=2,
                    help="paragraphs to look back for a dateline when the "
                         "matched paragraph carries none")
    args = ap.parse_args()

    terms = {d: re.compile(rf"(?<![{AR}]){PREFIX}{stem}")
             for d, stem in DISEASES.items()}

    pages = rows = 0
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["date", "pub", "page_id", "disease", "term", "haifa",
                    "dateline", "hospital", "epidemic_words", "soft_term",
                    "window"])
        for line in open(IN):
            rec = json.loads(line)
            if not rec.get("text"):
                continue
            paras = normalise(rec["text"])
            sections = section_towns(paras)
            page_has_haifa = any(HAIFA.search(p) for p in paras)
            hit_this_page = False

            for i, para in enumerate(paras):
                # the item's dateline, or the nearest one above it
                town = ""
                for j in range(i, max(-1, i - args.lookback - 1), -1):
                    m = DATELINE.search(paras[j][:160]) or CORRESPONDENT.search(paras[j])
                    if m:
                        town = TOWNS.get(m.group(1).lstrip("وفبلك"), "")
                        if not town:
                            town = TOWNS.get(m.group(1), "")
                        break
                if not town:
                    town = sections[i]

                for disease, pat in terms.items():
                    spans = []
                    for m in pat.finditer(para):
                        near = para[max(0, m.start() - 8):m.end() + 24]
                        if disease == "smallpox" and NOT_SMALLPOX.search(near):
                            continue
                        if disease == "plague" and NOT_PLAGUE.search(near):
                            continue
                        a = max(0, m.start() - args.context)
                        b = min(len(para), m.end() + args.context)
                        if spans and a <= spans[-1][1]:
                            spans[-1] = (spans[-1][0], b, spans[-1][2])
                        else:
                            spans.append((a, b, m.group(0)))
                    for a, b, term in spans:
                        win = para[a:b]
                        if town == "Haifa":
                            haifa = "dateline"
                        elif town:
                            haifa = f"other:{town}"
                        elif HAIFA.search(win):
                            haifa = "window"
                        elif HAIFA.search(para):
                            haifa = "paragraph"
                        elif page_has_haifa:
                            haifa = "page"
                        else:
                            haifa = "none"
                        soft = SOFT_TERM.get(disease)
                        ambiguous = bool(soft and soft.search(term)) or (
                            disease == "plague" and bool(NOT_PLAGUE.search(win)))
                        w.writerow([
                            iso(rec["date"]), rec["pub"], rec["id"], disease,
                            term, haifa, town, "y" if HOSPITAL.search(win) else "",
                            "y" if EPIDEMIC.search(win) else "",
                            "y" if ambiguous else "",
                            "…" + win + "…",
                        ])
                        rows += 1
                        hit_this_page = True
            pages += 1 if hit_this_page else 0

    total = sum(1 for _ in open(IN))
    print(f"{total} pages scanned, {pages} matched, {rows} windows -> {OUT}")


if __name__ == "__main__":
    main()
