#!/usr/bin/env python3
"""Build the clickable-source registry for paper/hospital-history.html.

Every citation in the history document resolves to an entry here: the
publication in full, the date, the language, the passage as quoted in our
reading notes, an English rendering where the original is not English, and
the URL that opens the article at the National Library of Israel.

Inputs  data/newspapers/heb_article_readings.md   (the Hebrew read, session E)
        sources/press/hand-authored-sources.json  (the Arabic, German and
                                                   English entries, which have
                                                   no generator: they were read
                                                   and translated by hand)
Output  data/public/sources-registry.json

The Hebrew readings file is the system of record for the Hebrew corpus: its
entries are human reads, not OCR, so the passages quoted here are already
checked. Arabic and German entries are transcribed from the history document
itself, where they were quoted with their translations. Those 35 entries are
kept in the sidecar above so a checkout without the private paper/ folder —
CI, or a fresh clone — still builds the complete 278-entry registry.
"""
import json
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
READINGS = ROOT / "data" / "newspapers" / "heb_article_readings.md"
HAND = ROOT / "sources" / "press" / "hand-authored-sources.json"
OUT = ROOT / "data" / "public" / "sources-registry.json"

# Veridian front door. Every article id in the corpus resolves here; the
# request grammar is documented in pipeline/jrayed.py.
NLI = "https://www.nli.org.il/en/newspapers/?a=d&d="

# Masthead expansions. The corpus sigla are Veridian's publication codes.
PUBS = {
    "dav":             ("Davar",                    "Tel Aviv",  "he"),
    "haretz":          ("Haaretz",                  "Tel Aviv",  "he"),
    "hbkr":            ("HaBoker",                  "Tel Aviv",  "he"),
    "ahr":             ("Al HaMishmar",             "Tel Aviv",  "he"),
    "hmf":             ("HaMashkif",                "Tel Aviv",  "he"),
    "hzh":             ("HaZman",                   "Jerusalem", "he"),
    "hazmantlv":       ("HaZman",                   "Tel Aviv",  "he"),
    "hegeh":           ("HaGeh",                    "Tel Aviv",  "he"),
    "dhy":             ("Doar HaYom",               "Jerusalem", "he"),
    "khm":             ("Kol HaAm",                 "Tel Aviv",  "he"),
    "mar":             ("HaMashkif",                "Tel Aviv",  "he"),
    "haolam":          ("HaOlam",                   "Jerusalem", "he"),
    "tsohorayimhaifa": ("Tsohorayim",               "Haifa",     "he"),
    "ytlv":            ("Yediot Tel Aviv",          "Tel Aviv",  "he"),
    "kolisraeljlm":    ("Kol Israel",               "Jerusalem", "he"),
    "hayomjlm":        ("HaYom",                    "Jerusalem", "he"),
    "hashaah":         ("HaShaah",                  "Tel Aviv",  "he"),
    "hashaharerev":    ("HaShahar",                 "Tel Aviv",  "he"),
    "amudimaliya":     ("Amudim ba-Aliya",          "Tel Aviv",  "he"),
    "pls":             ("The Palestine Post",       "Jerusalem", "en"),
    "plb":             ("The Palestine Bulletin",   "Jerusalem", "en"),
    "palestinereview": ("Palestine Review",         "Jerusalem", "en"),
    "wartedestempels": ("Die Warte des Tempels",    "Jerusalem", "de"),
}

ID_RE = re.compile(r"([a-z]+)(\d{4})(\d{2})(\d{2})-01\.[\d.]+")

# The app displays `lang` verbatim and keys its right-to-left table on it
# (LANG_DIR in TimelineView.tsx), so the registry must carry display names,
# not the ISO codes the PUBS table is written in. A Hebrew entry emitted as
# "he" renders left-to-right and silently scrambles the passage.
LANG_NAMES = {"he": "Hebrew", "ar": "Arabic", "en": "English", "de": "German"}


def parse_id(aid):
    """Publication, ISO date and display date from a Veridian article id."""
    m = ID_RE.fullmatch(aid)
    if not m:
        return None
    code, y, mo, d = m.groups()
    name, place, lang = PUBS.get(code, (code, "", "he"))
    return {
        "pub": name,
        "place": place,
        "lang": LANG_NAMES.get(lang, lang),
        "date": f"{y}-{mo}-{d}",
        "url": NLI + aid,
    }


# The reading notes cross-reference our working memory files as
# [[project_haifa_lazaret]]. The slug means nothing to a site visitor, but it
# is usually the grammatical object of its sentence ("this bears directly on
# [[...]]"), so deleting it would leave a dangling clause. Each one is spelled
# out as the thing it actually names. An unlisted slug degrades to its own
# words rather than breaking the build.
WIKI_PHRASE = {
    "project_haifa_lazaret":
        "the question of Haifa's lazaret",
    "project_atlit_notebook_25":
        "the Atlit camp register, Notebook 25",
    "project_register_serial_annual_counter":
        "the register's annual serial count",
    "project_hospital_two_buildings":
        "the move between the hospital's two buildings",
    "project_press_epidemic_leadlag":
        "the lag between the register and the press on epidemics",
    "project_mb_press_findings":
        "what the Mitteilungsblatt records",
    "project_ard_harat_yahud":
        "the distinction between Ard al-Yahud and Harat al-Yahud",
    "project_cathedra_article":
        "the Cathedra article",
}


def to_html(md):
    """Render a reading note's Markdown as the HTML the drawer expects.

    The app injects `note` with dangerouslySetInnerHTML, so raw Markdown
    would show its own asterisks and backticks. The readings file uses a
    closed set of constructs — bold, emphasis, code spans, dash lists,
    blockquotes and blank-line paragraphs — so a full Markdown parser is
    not warranted, but escaping is: the notes quote the press, and a stray
    `<` must not become a tag. Escape first, then introduce markup.
    """
    def esc(s):
        return (s.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;"))

    md = re.sub(r"`*\[\[([^\]]+)\]\]`*",
                lambda m: WIKI_PHRASE.get(
                    m.group(1),
                    re.sub(r"^\w+?_", "", m.group(1)).replace("_", " ")),
                md)

    def inline(s):
        s = esc(s)
        # Double-backtick spans come first: they are how the readings file
        # quotes a string that itself contains a backtick.
        s = re.sub(r"``(.+?)``", r"<code>\1</code>", s, flags=re.S)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s, flags=re.S)
        s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>",
                   s, flags=re.S)
        return s

    out = []
    for para in re.split(r"\n\s*\n", md.strip()):
        lines = [ln.strip() for ln in para.strip().split("\n") if ln.strip()]
        if not lines:
            continue
        if all(ln.startswith(">") for ln in lines):
            body = " ".join(re.sub(r"^>\s?", "", ln) for ln in lines)
            out.append(f"<blockquote><p>{inline(body)}</p></blockquote>")
        elif all(re.match(r"^[-*]\s+", ln) for ln in lines):
            texts = [re.sub(r"^[-*]\s+", "", ln) for ln in lines]
            items = "".join(f"<li>{inline(t)}</li>" for t in texts)
            out.append(f"<ul>{items}</ul>")
        else:
            # A hard-wrapped paragraph is one paragraph; the line breaks are
            # an artefact of the readings file, not the passage.
            out.append(f"<p>{inline(' '.join(lines))}</p>")
    return "".join(out)


def passages(text):
    """Map each article id to the reading note that quotes it.

    The readings file records one block per article: a bold date, the paper,
    the id in backticks, an em-dash and then the read itself. A handful of
    articles appear only as rows of the plague table, whose last cell is the
    note. Where an id occurs in several blocks the longest note wins.
    """
    notes = {}
    lines = text.split("\n")
    start = re.compile(r"^\s*(?:-\s+)?\*\*(\d{4}-\d{2}-\d{2})")

    blocks, cur = [], None
    for line in lines:
        if start.match(line):
            if cur:
                blocks.append(cur)
            cur = [line]
        elif cur is not None:
            if line.startswith("#"):
                blocks.append(cur)
                cur = None
            else:
                cur.append(line)
    if cur:
        blocks.append(cur)

    def record(aid, note):
        note = re.sub(r"\n{3,}", "\n\n", note).strip()
        if note and len(note) > len(notes.get(aid, "")):
            notes[aid] = note

    for block in blocks:
        text_ = "\n".join(block)
        ids = re.findall(r"`([a-z]+\d{8}-01\.[\d.]+)`", text_)
        if not ids:
            continue
        # Drop the leading marker — the bold date and paper, the id, and the
        # em-dash that introduces the read — but only when the bold run that
        # opens the block is closed before the dash, so a heading like
        # "**1939-06-19/20 — the Haifa market bomb.**" is removed whole.
        head = re.match(
            r"\s*(?:-\s+)?\*\*(?:[^*]|\*(?!\*))*\*\*[^\n]*?—\s*", text_, re.S
        )
        note = text_[head.end():] if head else text_
        for aid in ids:
            record(aid, note)

    for line in lines:
        if not line.strip().startswith("|"):
            continue
        ids = re.findall(r"`([a-z]+\d{8}-01\.[\d.]+)`", line)
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        for aid in ids:
            record(aid, cells[-1] if cells else "")

    return notes


def main():
    text = READINGS.read_text(encoding="utf-8")
    notes = passages(text)
    reg = {}
    for aid in sorted(set(re.findall(r"`([a-z]+\d{8}-01\.[\d.]+)`", text))):
        meta = parse_id(aid)
        if meta:
            if aid in notes:
                meta["note"] = to_html(notes[aid])
            reg[aid] = meta

    # The hand-read Arabic, German and English citations. Generated entries
    # never collide with these, but let the sidecar win if one ever does: it
    # is the human read.
    hand = json.loads(HAND.read_text(encoding="utf-8")) if HAND.exists() else {}
    reg.update(hand)

    OUT.write_text(
        json.dumps(reg, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )
    print(f"{len(reg)} sources ({len(reg) - len(hand)} built + {len(hand)} "
          f"hand-authored) -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
