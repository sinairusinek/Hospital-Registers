#!/usr/bin/env python3
"""Personnel strip data: who the sources place at the hospital, and when.

Source is MidEastMed (Liat Kozma's ERC project), institution entity 60387 —
"Government Hospital, Haifa". Scrape and provenance: data/mideastmed/README.md.

We publish a NAME, a ROLE, DATES and a LINK BACK, and nothing else. The
biographies stay unpublished: birthplace, religion, year of birth and the
rest of each career are in data/mideastmed/ for our own reading, and the
person page on mideastmed.org is where a reader who wants them should go.
That is also why every row carries its MidEastMed URL — the strip cites its
source per person rather than asserting a life.

The one thing this file must get right is that the dates come in two shapes,
and drawing them alike would be a lie:

  span        both years present, e.g. 1935-1948. The source gives a period.
  attestation a single year. Someone was recorded here THEN — an Official
              Gazette issue, an index entry. It is a sighting, not a tenure.

Several people have more than one attestation (Zakia Chabishian: 1930, 1935,
1940). The presence between two sightings is a reasonable inference but not
a documented fact, so those are emitted as `points` on one row with an
`inferred` bridge the view draws differently from a real span. Never promote
a first-and-last attestation into a span here.
"""
import csv
import json
import re
import pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "mideastmed" / "mem_haifa_govhosp_staff.tsv"
ADMIN = ROOT / "data" / "personnel" / "administrative.tsv"
OUT = ROOT / "data" / "public" / "personnel.json"

# The hospital's own years, so the strip shares the Timeline's axis.
CLAMP_LO, CLAMP_HI = 1918, 1950


def read_admin() -> list:
    """The senior staff, hand-read from the press and archives.

    A different kind of record from the MidEastMed rows and kept visibly so:
    these are posts, each with the source that names the person in it, and
    several are `inferred` — deduced across readings rather than stated. The
    view draws them in their own group and carries the certainty through, so
    a deduced directorship never reads as a printed one.
    """
    if not ADMIN.exists():
        return []
    rows = [r for r in ADMIN.open(encoding="utf-8")
            if not r.startswith("#") and r.strip()]
    out = []
    for r in csv.DictReader(rows, delimiter="\t"):
        a, b = r["from"].strip(), r["to"].strip()
        ya = int(a) if a.isdigit() else None
        yb = int(b) if b.isdigit() else None
        if ya and yb and yb > ya:
            spans = [{"from": ya, "to": yb, "kind": "Post"}]
            points = []
        else:
            spans = []
            y = ya or yb
            points = [{"year": y, "kind": "Post"}] if y else []
        years = [y for s in spans for y in (s["from"], s["to"])]
        years += [q["year"] for q in points]
        if not years:
            continue
        out.append({
            "id": "adm-" + re.sub(r"[^a-z0-9]+", "-", r["name"].lower()).strip("-"),
            "name": r["name"],
            "nameAr": r["name_ar"],
            "role": r["post"],
            "url": "",
            "kinds": ["Post" if r["kind"] == "post" else "Staff"],
            "spans": spans,
            "points": points,
            "first": min(years),
            "last": max(years),
            "origin": "press",
            "certainty": r["certainty"],
            "source": r["source"],
            "note": r["note"],
            "sameAs": r.get("same_as", "").strip(),
        })
    return out


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC.relative_to(ROOT)} — see data/mideastmed/README.md")

    rows = list(csv.DictReader(SRC.open(encoding="utf-8"), delimiter="\t"))
    people = defaultdict(lambda: {"spans": [], "points": [], "kinds": set()})

    for r in rows:
        node = r["person_node"]
        p = people[node]
        p["name"] = r["name"]
        p["name_ar"] = r["name_arabic"]
        p["role"] = r["profession"]
        p["url"] = r["url"]
        p["kinds"].add(r["activity_kind"])
        a, b = r["year_from"].strip(), r["year_to"].strip()
        ya = int(a) if a.isdigit() else None
        yb = int(b) if b.isdigit() else None
        if ya and yb and yb > ya:
            p["spans"].append([ya, yb, r["activity_kind"]])
        elif ya or yb:
            p["points"].append([ya or yb, r["activity_kind"]])

    out = []
    for node, p in people.items():
        pts = sorted({tuple(x) for x in p["points"]})
        spans = sorted(p["spans"])
        years = [y for y, _ in pts] + [y for s in spans for y in s[:2]]
        years = [y for y in years if CLAMP_LO <= y <= CLAMP_HI]
        if not years:
            continue  # 3 undated activities: no honest place on an axis
        out.append({
            "id": node,
            "name": p["name"],
            "nameAr": p["name_ar"],
            "role": p["role"],
            "url": p["url"],
            # Studied here, worked here, or both — the school and the staff
            # are different relationships to the same building.
            "kinds": sorted(p["kinds"]),
            "spans": [{"from": s[0], "to": s[1], "kind": s[2]} for s in spans],
            "points": [{"year": y, "kind": k} for y, k in pts],
            "first": min(years),
            "last": max(years),
        })

    for p in out:
        p["origin"] = "mideastmed"

    # Merge the press rows that name a person MidEastMed already has. One
    # person, one line: drawn once, but carrying both evidence marks, and the
    # press reading supplies the post the prosopography does not record.
    by_node = {p["id"]: p for p in out}
    for a in read_admin():
        target = by_node.get(a.pop("sameAs", "") or None)
        if target is None:
            out.append(a)
            continue
        target["origin"] = "both"
        target["post"] = a["role"]
        target["certainty"] = a["certainty"]
        target["source"] = a["source"]
        target["note"] = a["note"]
        # The press span is the documented tenure; keep whichever reaches
        # further, since the two readings rest on different evidence.
        for s2 in a["spans"]:
            if s2 not in target["spans"]:
                target["spans"].append(s2)
        target["first"] = min(target["first"], a["first"])
        target["last"] = max(target["last"], a["last"])

    out.sort(key=lambda d: (d["first"], d["last"], d["name"]))

    undated = sum(1 for r in rows if not r["year_from"].strip() and not r["year_to"].strip())
    data = {
        "meta": {
            # Credit in full, as the project asks on its own About page. The
            # grant line is theirs verbatim.
            "source": "MidEastMed (ERC), institution 60387 — Government Hospital, Haifa",
            "sourceUrl": "https://www.mideastmed.org/entity/60387/institution",
            "sourceHome": "https://www.mideastmed.org/",
            "project": "MidEastMed \u2014 A Regional History of Medicine "
                       "in the Middle East",
            "pi": "Prof. Liat Kozma",
            "institution": "The Hebrew University of Jerusalem",
            "grant": "ERC-2016-CoG \u2013 723718_Mideast Med",
            "grantKind": "European Research Council Consolidator Grant",
            "licence": "CC-BY 4.0",
            "people": len(out),
            "fromPress": sum(1 for p in out if p["origin"] in ("press", "both")),
            "merged": sum(1 for p in out if p["origin"] == "both"),
            "activities": len(rows),
            "undated": undated,
            "spans": sum(len(p["spans"]) for p in out),
            "points": sum(len(p["points"]) for p in out),
            "first": min(p["first"] for p in out),
            "last": max(p["last"] for p in out),
        },
        "people": out,
    }

    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    m = data["meta"]
    print(f"personnel -> {OUT.relative_to(ROOT)}")
    print(f"  {m['people']} people ({m['people'] - m['fromPress']} MidEastMed only, "
          f"{m['fromPress']} named in the press, {m['merged']} in both), "
          f"{m['spans']} spans, "
          f"{m['points']} attestations, {m['undated']} undated dropped")
    print(f"  {m['first']}-{m['last']}")


if __name__ == "__main__":
    main()
