#!/usr/bin/env python3
"""Assemble the data behind the site's Timeline view.

Four layers on one axis, plus the sources that make them clickable:

  1. external    — what was happening around the hospital. Hand-authored in
                   data/public/external-events.tsv, because nothing in this
                   repo knows about the Revolt or the Fifth Aliyah. Every row
                   carries a source.
  2. institution — what the hospital itself did, taken from the press read.
                   Seeded from the flags in pipeline/history_timeline.py and
                   expanded here; each event names a source id.
  3. intake      — monthly admissions from the register. The Atlit camp book
                   (Notebook 25) is kept as a SEPARATE series and never folded
                   into the general count: see the standing ruling in memory.
  4. notebooks   — which physical ledger covers which months, so the band can
                   be read back to the scan it came from.

  gaps           — the months with no surviving register. Drawn explicitly,
                   because an intake band with unmarked holes says the hospital
                   emptied in 1941, which is false.

  sources        — the drawer payload: masthead, date, place, language, the
                   passage and its translation. Read from the public
                   data/public/sources-registry.json, which source_registry.py
                   builds complete at 278 entries: 243 generated from the
                   Hebrew readings plus 35 hand-authored Arabic, German and
                   English rows kept in sources/press/.

Output: data/public/timeline.json, staged into the app by scripts/copy-data.mjs.
"""
import csv
import json
import pathlib
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTER = ROOT / "data" / "public" / "hospital-registers-normalized.tsv"
EXTERNAL = ROOT / "data" / "public" / "external-events.tsv"
REGISTRY = ROOT / "data" / "public" / "sources-registry.json"
OUT = ROOT / "data" / "public" / "timeline.json"

# The Atlit camp register. 965 admissions in 1940, 962 of them Jewish, every
# one at Athlit — it is not the Haifa hospital's general intake and is excluded
# from every general-register statistic.
ATLIT_NOTEBOOK = "25"

FIRST, LAST = "1930-01", "1948-04"


# ---------------------------------------------------------------- helpers

def months(lo, hi):
    """Every YYYY-MM from lo to hi inclusive."""
    y, m = int(lo[:4]), int(lo[5:7])
    out = []
    while f"{y:04d}-{m:02d}" <= hi:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def runs(seq):
    """Collapse a sorted list of months into contiguous [start, end] runs."""
    out = []
    prev = None
    for m in seq:
        n = int(m[:4]) * 12 + int(m[5:7])
        if prev is not None and n - prev == 1:
            out[-1][1] = m
        else:
            out.append([m, m])
        prev = n
    return out


# ---------------------------------------------------------------- register

def read_register():
    """Monthly counts, and the month span of each notebook.

    csv.QUOTE_NONE is not optional: the dataset contains bare quote characters
    in free-text fields, and Python's default quoting silently swallows rows
    across them — that is how an earlier count lost 153 records.
    """
    if not REGISTER.exists():
        sys.exit(
            f"{REGISTER.relative_to(ROOT)} not found.\n"
            "Run: python3 pipeline/build.py"
        )

    general = Counter()
    atlit = Counter()
    nb_months = defaultdict(set)
    nb_first_page = {}
    undated = 0
    total = 0

    with REGISTER.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            total += 1
            date = (row.get("Admission Date") or "").strip()
            if len(date) < 7 or not date[:4].isdigit():
                undated += 1
                continue
            month = date[:7]
            notebook = (row.get("Notebook_Number") or "").strip()

            if notebook == ATLIT_NOTEBOOK:
                atlit[month] += 1
            else:
                general[month] += 1

            if notebook:
                nb_months[notebook].add(month)
                page = (row.get("Page_Number") or "").strip()
                if page.isdigit():
                    cur = nb_first_page.get(notebook)
                    if cur is None or int(page) < cur:
                        nb_first_page[notebook] = int(page)

    notebooks = []
    for nb, ms in nb_months.items():
        ms = sorted(ms)
        notebooks.append({
            "notebook": nb,
            "start": ms[0],
            "end": ms[-1],
            "months": len(ms),
            "records": sum(
                (atlit if nb == ATLIT_NOTEBOOK else general)[m] for m in ms
            ),
            "firstPage": nb_first_page.get(nb),
            "atlit": nb == ATLIT_NOTEBOOK,
        })
    notebooks.sort(key=lambda n: (n["start"], int(n["notebook"])))

    return general, atlit, notebooks, total, undated


# ---------------------------------------------------------------- sources

def read_sources():
    """The drawer payload: the public registry, complete at 278 entries.

    source_registry.py merges the 243 generated Hebrew entries with the 35
    hand-authored Arabic, German and English ones, so the full set no longer
    depends on the private paper/ folder — CI and a fresh clone build the
    same payload this does.

    The registry is preferred over paper/hospital-history.html even when
    that file is present. Both carry the same passages, but the registry is
    generated: it escapes its own markup and resolves the [[memory]]
    cross-references that the history document leaves raw. Reading the HTML
    instead would republish those artefacts to the site.
    """
    if REGISTRY.exists():
        raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
        return (
            {k: {"id": k, **v} for k, v in raw.items()},
            "sources-registry.json",
        )

    return {}, None


# ---------------------------------------------------------------- events

# The hospital's own chronology. The first thirteen are the flags already
# drawn in pipeline/history_timeline.py for the printed figure; the rest come
# from the same press read and are added here because a zoomable axis has room
# for them where a fixed-width figure did not. `src` is a key into the source
# payload and is what makes the flag clickable.
INSTITUTIONAL = [
    ("1929-03", "St. Luke's mission hospital closes", "plb19290311-01.2.7",
     "The Church Missionary Society hospital on Mountain Road shuts. Its "
     "premises are the ones the Government later rents."),
    ("1930-02", "The register opens", None,
     "The first surviving admission is entered in Notebook 1."),
    ("1932-10", "The Government takes the building", None,
     "The rented Mountain Road premises pass into direct Government use."),
    ("1933-07", "Enlargement deferred", "haretz19330703-01.2.12",
     "Haaretz reports that because the enlargement was deferred, "
     "\"the position there became difficult in the intestinal-disease "
     "season.\""),
    ("1935-09", "A new hospital announced, 260 beds", "dhy19350912-01.2.71",
     "Doar HaYom, citing al-Muqattam: 180 surgical beds and 80 for other "
     "diseases, work to begin shortly and take two years."),
    ("1937-06", "Contracted to Solel Boneh, ~£90,000", "haolam19370617-01.2.10",
     "With a clause requiring 50 per cent Jewish and 50 per cent Arab "
     "labour."),
    ("1937-06", "Ground broken at Bat Galim", "dav19370618-01.2.93",
     "Some 80 Jewish and Arab workers clearing and excavating."),
    ("1937-09", "The Arab workers on the site strike", "dav19370905-01.2.129",
     "Their daily wage 27-32 grush against 60-75 for the Jewish carpenters; "
     "the Deputy District Commissioner promises to equalise them."),
    ("1938-01", "Standing complete on the plain",
     "palestinereview19380107-01.2.8",
     "\"The Government Hospital at Bat Galim stands sheer, complete in "
     "architectural severity.\""),
    ("1938-09", "Construction completed", "haretz19381223-01.2.5",
     "Mendelsohn's assistant Dr Kampinsky, at the ceremony, dates completion "
     "to September."),
    ("1938-10", "The wards are occupied — NB20 to NB21", "pls19381108-01.2.31",
     "Some 150 patients transferred from Mountain Road. The register's own "
     "notebook seam falls here."),
    ("1938-12", "Opened at 225 beds", "dav19381223-01.2.66",
     "\"I declare the hospital officially open, and I wish that it may "
     "remain empty.\""),
    ("1938-12", "A language incident at the opening", "dav19381227-01.2.16",
     "The Va'ad Leumi protests to the Chief Secretary that the speeches "
     "were not translated into Hebrew."),
    ("1939-06", "An Emergency Aid Post at the old premises",
     "pls19390605-01.2.66",
     "The Mountain Road building continues in use under its own name."),
    ("1940-03", "A death inside the gap", "mb19400308",
     "The Mitteilungsblatt records a death at the hospital in months for "
     "which no register survives."),
    ("1942-06", "A plague department is built", "haretz19450710-01.2.24",
     "Built beside the hospital by the Public Works Department."),
    ("1943-06", "Dr Naif Amin Hamzeh honoured", "pls19430602-01.1.1",
     "Medical Officer at the Government Hospital, Haifa, made Hon. M.B.E."),
    ("1944-06", "The plague outbreak begins", "haretz19441117-01.2.59",
     "64 cases and 18 dead by November 1944."),
    ("1945-08", "An Isolation Section", None,
     "The hospital still has an Isolation Section in 1945 — so the ward "
     "value's disappearance from the register after Feb 1940 was a clerical "
     "change, not the work leaving."),
    ("1947-07", "The Exodus deportees are landed", "hzh19470720-01.2.2",
     "The wounded from the intercepted ship come ashore at Haifa."),
    ("1947-12", "The Jewish staff walk out", "hmf19480126-01.2.34",
     "Reported alongside the removal of Jewish patients."),
    ("1948-01", "Jewish patients are removed", None,
     "Corroborated by the register itself: the Jewish share of admissions "
     "falls away in the last notebook."),
    ("1948-05", "To the municipality", "haretz19480503-01.2.39",
     "The hospital passes out of Government hands on 2 May 1948."),
]


def read_external():
    if not EXTERNAL.exists():
        return []
    rows = []
    with EXTERNAL.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            date = (row.get("date") or "").strip()
            if not date:
                continue
            rows.append({
                "date": date,
                "end": (row.get("end") or "").strip() or None,
                "kind": (row.get("kind") or "other").strip(),
                "label": (row.get("label") or "").strip(),
                "scope": (row.get("scope") or "").strip(),
                "note": (row.get("note") or "").strip(),
                "source": (row.get("source") or "").strip(),
            })
    rows.sort(key=lambda r: r["date"])
    return rows


# ---------------------------------------------------------------- build

def build():
    general, atlit, notebooks, total, undated = read_register()
    sources, source_origin = read_sources()

    span = months(FIRST, LAST)
    intake = [
        {"month": m, "general": general.get(m, 0), "atlit": atlit.get(m, 0)}
        for m in span
    ]

    # A gap is a month in which the register records nothing at all. The Atlit
    # book counts here: a month it covers is a month we can read.
    missing = [m for m in span if not general.get(m) and not atlit.get(m)]
    gaps = [
        {
            "start": a,
            "end": b,
            "months": len(months(a, b)),
            # Every one of these is an archival absence, not a closure: the
            # press has the hospital working throughout. Kept as a field so a
            # later ruling can mark one differently without touching the view.
            "reason": "no surviving register",
        }
        for a, b in runs(missing)
    ]

    institutional = [
        {
            "date": when,
            "label": label,
            "src": src,
            "note": note,
            "hasSource": bool(src and src in sources),
        }
        for when, label, src, note in INSTITUTIONAL
    ]

    # Only the sources an event actually points at are shipped; the full 278
    # belong to the history document, not to this view.
    used = {e["src"] for e in institutional if e["hasSource"]}
    payload = {k: sources[k] for k in sorted(used)}

    dangling = sorted(
        e["src"] for e in institutional if e["src"] and e["src"] not in sources
    )
    if dangling:
        print(f"  warning: {len(dangling)} event source id(s) not in the "
              f"payload: {', '.join(dangling)}", file=sys.stderr)

    return {
        "meta": {
            "first": FIRST,
            "last": LAST,
            "records": total,
            "dated": total - undated,
            "undated": undated,
            "generalRecords": sum(general.values()),
            "atlitRecords": sum(atlit.values()),
            "atlitNotebook": ATLIT_NOTEBOOK,
            "sourceOrigin": source_origin,
        },
        "intake": intake,
        "gaps": gaps,
        "notebooks": notebooks,
        "institutional": institutional,
        "external": read_external(),
        "sources": payload,
    }


if __name__ == "__main__":
    data = build()

    # The registry is public now, so CI finds its sources. This guard stays as
    # a backstop: if the registry is ever missing or empty, refuse to
    # republish the timeline with all its passages silently stripped.
    if not data["sources"] and OUT.exists():
        existing = json.loads(OUT.read_text(encoding="utf-8"))
        if existing.get("sources"):
            sys.exit(
                f"Refusing to overwrite {OUT.relative_to(ROOT)}: it carries "
                f"{len(existing['sources'])} sources and this run found none "
                "(data/public/sources-registry.json is missing or empty). "
                "Run python3 pipeline/source_registry.py first, or delete "
                "the file if a sourceless rebuild is really intended."
            )

    OUT.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    m = data["meta"]
    print(f"timeline -> {OUT.relative_to(ROOT)}")
    print(f"  {m['generalRecords']:,} general + {m['atlitRecords']:,} Atlit "
          f"admissions across {len(data['intake'])} months")
    print(f"  {len(data['gaps'])} gap runs, {len(data['notebooks'])} notebooks")
    print(f"  {len(data['external'])} external + "
          f"{len(data['institutional'])} institutional events, "
          f"{len(data['sources'])} sources ({m['sourceOrigin']})")
