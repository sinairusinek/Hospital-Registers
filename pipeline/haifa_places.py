#!/usr/bin/env python3
"""Points for the Haifa view: the town quarters and the employing institutions.

Writes data/public/haifa-places.json, which the Haifa tab draws.

Every point is a Wikidata item's own P625, fetched here, never a coordinate
typed in by hand. Each carries how it relates to the register's name:

  identity  the item is the place the clerk wrote (Wadi Nisnas, Bat Galim)
  near      the item is a landmark in or beside it, because the place itself
            has no item (Acre Gate -> Faisal Square, where the gate stood)

A quarter or institution with neither — Harat al-Kanais' sister quarters in
the old town, the police, the I.P.C. — is written with no point and a note,
so the view can list it beside the map instead of dropping it.

Institutions are those of the Address layer (pipeline/address_layers.py):
what the address names, read as "reached through", not "employed by". Only
those with one site in Haifa are placed; a regiment or the police are many
places and stay off the map.

    python3 pipeline/haifa_places.py
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "public" / "haifa-places.json"
UA = {"User-Agent": "HospitalRegisters/0.1 (sinai.rusinek@gmail.com)"}

# quarter (as in the Neighbourhood column, after "Haifa: "), QID, relation, note
QUARTERS = [
    ("Hadar HaCarmel", "Q2630079", "identity", ""),
    ("Wadi Salib", "Q2910153", "identity", ""),
    ("Wadi Nisnas", "Q2920415", "identity", ""),
    ("Ard el-Yahud", "Q12404212", "identity", "Not Harat al-Yahud: two places (Naor 2019)."),
    ("Carmel Station", "Q12412037", "identity", "Tahanat HaCarmel, the quarter named for the station."),
    ("Halisa", "Q7212307", "identity", ""),
    ("Mount Carmel", "Q7217342", "near", "Drawn at Carmel Center; the register's \"Mount Carmel\" is the whole ridge."),
    ("Wadi Rushmiya", "Q4024328", "near", "Drawn on the wadi itself (Nahal Giborim); the quarter lay along it."),
    ("Bat Galim", "Q810685", "identity", ""),
    ("Harat al-Kanais", "Q3390256", "near", "The churches' quarter of the old town, drawn at Hamra (Paris) Square, the \"Churches District\"."),
    ("Acre Gate", "Q25488483", "near", "Drawn at Faisal Square, where the old town's eastern gate stood."),
    ("German Colony", "Q2413425", "identity", ""),
    ("Hawassa", "Q12407319", "identity", "Khwasa: the workers' settlement laid out from 1937 west of Balad al-Sheikh (Goren 2006). Outside the municipality."),
    ("Khamra Square", "Q3390256", "identity", "Hamra Square, today Paris Square."),
    ("Neve Sha'anan", "Q2919842", "identity", ""),
    ("Kiryat Eliyahu", "Q12029242", "identity", ""),
    ("Old City", "Q137399864", "identity", "Zahir al-Umar's walled town, between Hamra and Faisal Squares."),
    # No item, and no landmark close enough to stand for them.
    ("Harat al-Yahud", "", "", "The old town's Jewish quarter; no item, and not Ard el-Yahud."),
    ("Herzliya quarter", "", "", "No Wikidata item found."),
    ("Ard el-Ramel", "", "", "The tin-hut quarter east of the Wadi Rushmiya estuary, by the Shemen factory (Goren 2006); no item."),
    ("Harat al-Mukhallis", "", "", "No item."),
    ("Burj", "", "", "No item."),
    ("Sharqiyya", "", "", "The eastern quarter; no item."),
    ("Harat al-Kishleh", "", "", "The barracks quarter of the old town; no item."),
    ("Ghazazwa", "", "", "No item."),
    ("Shawafna", "", "", "No item."),
    ("Ahuza", "", "", "Has an item (Q104418538) but no coordinates."),
    ("Abbasiyya", "", "", "No item."),
]

# institution (as in the Address institution column), QID, relation, note,
# and the admission window it holds for, where the site changed.
INSTITUTIONS = [
    ("Palestine Railways", "Q7223486", "near", "Drawn at Haifa East, the railway's Haifa terminus.", None, None),
    ("Government Hospital", "Q2120867", "identity", "The seashore building at Bat Galim, today Rambam, from 31 Oct 1938.", "1938-10-31", None),
    ("Government Hospital", "", "", "The old leased wards on Mountain Road, until 31 Oct 1938. Exact site unsourced. Undated records are counted here.", None, "1938-10-30"),
    ("Harbour Works", "Q1376739", "near", "Drawn at the port.", None, None),
    ("Tilbury Contracting & Dredging", "Q1376739", "near", "The harbour contractors; drawn at the port.", None, None),
    ("Customs", "Q6635580", "near", "Drawn at the Custom House (by its railway halt).", None, None),
]

ICON = {  # a single glyph per institution for the map badge
    "Palestine Railways": "🚂", "Government Hospital": "✚", "Harbour Works": "⚓",
    "Tilbury Contracting & Dredging": "⚓", "Customs": "▣",
}


def coords(qids: list[str]) -> dict[str, tuple[float, float, str]]:
    out: dict[str, tuple[float, float, str]] = {}
    qids = sorted({q for q in qids if q})
    for i in range(0, len(qids), 40):
        url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({
            "action": "wbgetentities", "ids": "|".join(qids[i:i + 40]),
            "props": "claims|labels", "format": "json"})
        data = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))
        for q, e in data["entities"].items():
            claim = e.get("claims", {}).get("P625", [{}])[0]
            v = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            labels = e.get("labels", {})
            label = (labels.get("en") or labels.get("he") or next(iter(labels.values()), {})).get("value", q)
            if v:
                out[q] = (round(v["latitude"], 6), round(v["longitude"], 6), label)
    return out


def main() -> int:
    pts = coords([q for _, q, *_ in QUARTERS] + [q for _, q, *_ in INSTITUTIONS])
    quarters, institutions = [], []
    for name, qid, rel, note in QUARTERS:
        lat, lon, label = pts.get(qid, (None, None, ""))
        quarters.append({"name": name, "qid": qid, "relation": rel if lat is not None else "",
                         "anchor": label, "lat": lat, "lon": lon, "note": note})
    for name, qid, rel, note, start, end in INSTITUTIONS:
        lat, lon, label = pts.get(qid, (None, None, ""))
        institutions.append({"name": name, "qid": qid, "relation": rel if lat is not None else "",
                             "anchor": label, "lat": lat, "lon": lon, "note": note,
                             "from": start, "to": end, "icon": ICON.get(name, "")})
    missing = [q["name"] for q in quarters + institutions if q["qid"] and q["lat"] is None]
    if missing:
        print("no P625 for:", ", ".join(missing), file=sys.stderr)
    OUT.write_text(json.dumps({"quarters": quarters, "institutions": institutions},
                              ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    placed = sum(q["lat"] is not None for q in quarters)
    print(f"{OUT.relative_to(ROOT)}: {placed}/{len(quarters)} quarters, "
          f"{sum(i['lat'] is not None for i in institutions)}/{len(institutions)} institution sites placed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
