#!/usr/bin/env python3
"""Points for the Haifa view: the town quarters and the employing institutions.

Writes data/public/haifa-places.json, which the Haifa tab draws.

A point is a Wikidata item's own P625, fetched here. Where Wikidata has no
item, or its point is wrong for the period (a modern 20 km² district standing
for a 1930s hut quarter), POINT takes it instead from an OpenStreetMap feature,
also fetched (Nominatim lookup: the feature's centroid). Only as a last resort
is a coordinate typed by hand, and then the note must say where it comes from.
Each point carries how it relates to the register's name:

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
    ("Hawassa", "Q12407319", "identity", "Khwasa: the workers' settlement laid out from 1937 west of Balad al-Sheikh (Goren 2006), outside the municipality, for the families evacuated from Ard el-Ramel. It stood where the Ben Dor quarter of Nesher is today (hewiki), which is where its point falls."),
    ("Khamra Square", "Q3390256", "identity", "Hamra Square, today Paris Square."),
    ("Neve Sha'anan", "Q2919842", "identity", ""),
    ("Kiryat Eliyahu", "Q12029242", "identity", ""),
    ("Old City", "Q137399864", "identity", "Zahir al-Umar's walled town, between Hamra and Faisal Squares."),
    ("Harat al-Yahud", "Q16341015", "near", "The old town's Jewish quarter, built inside the Eastern Quarter; not Ard el-Yahud. Drawn at the al-Pasha compound on Hammam al-Pasha Street, which stood at its edge (hewiki) and housed its Talmud Torah until the quarter was evacuated on 18 Jul 1938."),
    ("Herzliya quarter", "Q12019571", "identity", "Herzlia, on the lower Carmel slope between Hadar and Wadi Nisnas."),
    ("Ahuza", "Q7060877", "near", "Ahuzat Shmuel, on the Carmel ridge (Q4159159, whose point lies 1.2 km south, in the later Ramot HaCarmel district). Drawn at Horev Square, \"in the heart of old Ahuza\" (hewiki), where its first streets, Sinai, Moriah and Horev, were laid in 1924."),
    ("Abbasiyya", "Q10374305", "identity", "The Abbas quarter, named for its streets, between the German Colony and Hadar."),
    ("Burj", "Q12404415", "near", "Drawn at Burj al-Salam, Zahir al-Umar's citadel above the old town, opposite today's City Hall; the road up to it was called al-Burj."),
    ("Ard el-Ramel", "Q12036875", "near", "The tin-hut quarter east of the Wadi Rushmiya estuary, by the Shemen factory (Goren 2006): 500 huts and 1,700 people in 1934-35, largely cleared from 1938. Wikidata gives it as an alias of the Haifa Bay quarter, whose point is 2.5 km east by the Check Post. Drawn instead at the Hof Shemen industrial zone (OpenStreetMap), on the beach that took the factory's name."),
    ("Harat al-Mukhallis", "", "near", "Harat al-Mukhallis, \"the Saviour's quarter\", named for the Church of the Saviour (\"near Kanisat el Mukhallis\"). It lay around the street of that name, renamed Y. L. Peretz Street after 1948. No item for the quarter or the church; drawn on Peretz Street (OpenStreetMap)."),
    ("Persian Colony", "", "near", "The Persian quarter, also written the Persian Colony: one place, around the street now called HaParsim (\"the Persians\"), on the lower slope above Wadi Nisnas. No item; drawn on HaParsim Street (OpenStreetMap)."),
    ("Harat al-Kishleh", "", "near", "The barracks quarter of the old town, named for the Ottoman kishla. The Kishle building stands at 24 Derech HaAtzmaut in the lower town (user, 2026-10-22). Neither Wikidata nor OpenStreetMap has the building or that house number, so the point is Google Maps' pin for the address, typed in."),
    # No item, and no landmark close enough to stand for them.
    ("Sharqiyya", "", "", "Al-Harat al-Sharqiyya, the old town's Eastern Quarter (54 dunams, mostly Muslim); no item of its own."),

    ("Ghazazwa", "", "", "Harat al-Ghazzawiyya, named for families from Gaza; no item. Not Khirbat al-Ghazazwa by Burayka."),
    ("Shawafna", "", "", "No item."),
]

# The Kima Historical Gazetteer's entry for each quarter, where it has one, and
# whether that entry IS the quarter or only stands near it. Read from the Kima
# dump (Kimatch/20250126KimaPlacesCSVx.csv), not looked up by name at run time.
KIMA = {
    "Wadi Salib": ("19522", "identity"), "Wadi Nisnas": ("85346", "identity"),
    "Hadar HaCarmel": ("21150", "identity"), "Halisa": ("83220", "identity"),
    "Bat Galim": ("21063", "identity"), "German Colony": ("21139", "identity"),
    "Neve Sha'anan": ("21497", "identity"), "Ahuza": ("21015", "identity"),
    "Mount Carmel": ("26805", "near"), "Wadi Rushmiya": ("86518", "near"),
    "Khamra Square": ("70144", "identity"), "Harat al-Kanais": ("70144", "near"),
    "Old City": ("26801", "near"),
}

# institution (as in the Address institution column), QID, relation, note,
# and the admission window it holds for, where the site changed.
INSTITUTIONS = [
    ("Palestine Railways", "Q7223486", "near", "Drawn at Haifa East, the railway's Haifa terminus.", None, None),
    ("Government Hospital", "Q2120867", "identity", "The seashore building at Bat Galim, today Rambam, from 31 Oct 1938.", "1938-10-31", None),
    ("Government Hospital", "", "near", "The old leased wards on Mountain Road (Tariq al-Jabal, today Sderot HaZiyonut), until 31 Oct 1938: \"the former hospital wards on Mountain Road\" (Palestine Post 8 Nov 1938). Which building is not known; drawn at St Luke's Church on that road (OpenStreetMap). Undated records are counted here.", None, "1938-10-30"),
    ("Harbour Works", "Q1376739", "near", "Drawn at the port.", None, None),
    ("Tilbury Contracting & Dredging", "Q1376739", "near", "The harbour contractors; drawn at the port.", None, None),
    ("Customs", "Q6635580", "near", "Drawn at the Custom House (by its railway halt).", None, None),
    ("Municipality", "Q6578210", "identity", "Haifa City Hall on Hassan Shukri Street, from 29 Jun 1942 (the inception date Wikidata gives).", "1942-06-29", None),
    ("Municipality", "Q3390256", "near", "The town hall at the corner of Allenby Road and Stanton Street (today Shivat Zion), from 1934: Palestine Post 18 Jun 1936; HaBoker 11 May 1939 (\"the municipality building on Allenby Street\"); HaBoker and Haaretz 4 Mar 1948 (\"the former municipality building\", bombed). Probably the old Italian Hospital building, which the municipality resolved in Dec 1933 to rent from 1934 (Filastin 7 Dec 1933). No item; drawn at Hamra (Paris) Square, from whose south-west corner Allenby Road leaves. The month of the move is not known.", "1934-01-01", "1942-06-28"),
    ("Municipality", "", "", "Before 1934: an earlier building on Allenby Street, \"the old municipality building\" (Filastin 11 Apr 1937). Its site is not fixed. Undated records are counted here.", None, "1933-12-31"),
    ("Nesher cement works", "Q18191988", "identity", "The Nesher cement factory below Yagur, outside the town; drawn where it stood.", None, None),
    ("Iraq Petroleum Company", "Q47466318", "near", "From 1939: the Haifa refinery (Q124285258, which has no coordinates) in Haifa Bay, completed in 1939 at the end of the Kirkuk pipeline. Drawn at its cooling towers, the Halebeniyot, in use from 1939.", "1939-01-01", None),
    ("Iraq Petroleum Company", "", "", "Before 1939: pipeline construction (from 1932) and the Haifa terminal, where the first oil arrived on 14 Oct 1934. The terminal has no item, so nothing is drawn. Undated records are counted here.", None, "1938-12-31"),
]

# Points taken from somewhere other than the item's P625: "osm:W123" (a way),
# "osm:N123" (a node) or "osm:R123" (a relation), fetched; or "geo:lat,lon",
# typed, whose source the note must give. Keyed by quarter name, or for an
# institution by (name, from, to). The label says where the point is.
POINT = {
    "Ard el-Ramel": ("osm:R2658680", "the Hof Shemen industrial zone"),
    "Harat al-Mukhallis": ("osm:W230743881", "Y. L. Peretz Street"),
    "Persian Colony": ("osm:W62075104", "HaParsim Street"),
    "Harat al-Kishleh": ("geo:32.816084,35.003165", "the Kishle, 24 Derech HaAtzmaut"),
    ("Government Hospital", None, "1938-10-30"): ("osm:W660034185", "St Luke's Church, Mountain Road"),
}

ICON = {  # a single glyph per institution for the map badge
    "Palestine Railways": "🚂", "Government Hospital": "✚", "Harbour Works": "⚓",
    "Tilbury Contracting & Dredging": "⚓", "Customs": "▣",
    "Municipality": "🏛", "Nesher cement works": "🏭", "Iraq Petroleum Company": "🛢",
}


# English names for anchors whose item has only a Hebrew or Arabic label, so
# the view can say where a quarter is drawn in the language it is written in.
ANCHOR_LABEL = {"Q12404415": "Burj al-Salam", "Q47466318": "the refinery cooling towers (Halebeniyot)"}


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
                out[q] = (round(v["latitude"], 6), round(v["longitude"], 6), ANCHOR_LABEL.get(q, label))
    return out


def osm(refs: list[str]) -> dict[str, tuple[float, float]]:
    ids = sorted({r.split(":", 1)[1] for r in refs if r.startswith("osm:")})
    if not ids:
        return {}
    url = "https://nominatim.openstreetmap.org/lookup?" + urllib.parse.urlencode(
        {"osm_ids": ",".join(ids), "format": "jsonv2"})
    data = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))
    return {"osm:" + r["osm_type"][0].upper() + str(r["osm_id"]): (round(float(r["lat"]), 6), round(float(r["lon"]), 6))
            for r in data}


def point(key, qid: str, pts: dict, osm_pts: dict) -> tuple[float | None, float | None, str, str]:
    """lat, lon, anchor label, and the OpenStreetMap ref the point came from."""
    if key in POINT:
        ref, label = POINT[key]
        if ref.startswith("geo:"):
            lat, lon = (float(x) for x in ref[4:].split(","))
            return lat, lon, label, ""
        lat, lon = osm_pts.get(ref, (None, None))
        return lat, lon, label, ref[4:]
    lat, lon, label = pts.get(qid, (None, None, ""))
    return lat, lon, label, ""


def main() -> int:
    pts = coords([q for _, q, *_ in QUARTERS] + [q for _, q, *_ in INSTITUTIONS])
    osm_pts = osm([ref for ref, _ in POINT.values()])
    quarters, institutions = [], []
    for name, qid, rel, note in QUARTERS:
        lat, lon, label, osm_ref = point(name, qid, pts, osm_pts)
        kima, kima_rel = KIMA.get(name, ("", ""))
        quarters.append({"name": name, "qid": qid, "relation": rel if lat is not None else "",
                         "anchor": label, "lat": lat, "lon": lon, "note": note, "osm": osm_ref,
                         "kima": kima, "kimaRelation": kima_rel})
    for name, qid, rel, note, start, end in INSTITUTIONS:
        lat, lon, label, osm_ref = point((name, start, end), qid, pts, osm_pts)
        institutions.append({"name": name, "qid": qid, "relation": rel if lat is not None else "",
                             "anchor": label, "lat": lat, "lon": lon, "note": note, "osm": osm_ref,
                             "from": start, "to": end, "icon": ICON.get(name, "")})
    missing = [q["name"] for q in quarters + institutions if (q["qid"] or q["osm"]) and q["lat"] is None]
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
