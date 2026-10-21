#!/usr/bin/env python3
"""Two layers read out of the Address column: the institution it names, and
the town quarter.

The clerks often wrote a workplace or a custodian where a home address would
go: "c/o I.P.C.", "Palestine Railways", "Central Prison, Acre", "2nd Bn.
Lancashire Fusiliers". And inside Haifa (and Acre) the address names the
quarter: Wadi Salib, Hadar HaCarmel, Ard el-Yahud. Neither has a column of
its own in the ledger.

The vocabulary is Yoni Furas's. In his 2024 annotation of the patient
addresses (data/public/furas-unique-addresses-2024.tsv) every string carries
a place type — Neighborhood, Street, Government-Police, Iraq Petroleum
Company, Military unit… An address string he annotated takes his label
directly (`source` furas). Anything else is read with the patterns below,
which were drawn from his labelled strings and are scored against them by
`--eval` (`source` pattern).

What the institution column claims is only that the address names that
institution. A prison as address is usually an inmate, a hospital its staff
or a patient with nowhere else to give, a regiment a soldier. Read it as
"reached through", not "employed by".

Quarters are only read where the record's town allows it: Haifa's when the
City is Haifa, empty, or itself a Haifa quarter; Acre's when it is Acre.

    python3 pipeline/address_layers.py --eval
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FURAS = ROOT / "data" / "public" / "furas-unique-addresses-2024.tsv"

# ------------------------------------------------------------ institutions
# First match wins, so the order settles collisions: "The Iraq Pet. Coy." is
# the oil company, not an army company; "Police Prison, Nazareth" is the
# police lock-up. Karaman is the firm only with its partners' names — alone it
# is as often the family that owned the house ("Dar Zaher Karaman").
INSTITUTIONS: list[tuple[str, str, str]] = [
    ("Iraq Petroleum Company", "company", r"\bI\.?\s?P\.?\s?C\b|Ira[qg]\w*\.?\s+Pet"),
    ("Shell Company", "company", r"\bShell\b"),
    ("Nesher cement works", "company", r"Nesher|Nisher|Cement\s+Fact"),
    ("Karaman, Dick & Salti", "company", r"Karaman\W+(Dick|Dich|Sal)|Karaman\s+Quarr"),
    ("Tilbury Contracting & Dredging", "company", r"[TS]il+bury|Dredg"),
    ("Barclays Bank", "company", r"Bar[ce]l?ays"),
    ("Transjordan Frontier Force", "military", r"T\.?\s?J\.?\s?F\.?\s?F|Frontier\s+Force"),
    ("Royal Navy", "military", r"\bH\.\s?M\.\s?S\b"),
    ("Royal Air Force", "military", r"\bR\.\s?A\.\s?F\b|Air\s+Force"),
    ("British Army", "military",
     r"Regt|Regiment|Highlander|Fus[il]+i?[lz]ier|Royal\s+Scots|Gordons?\b|Seaforth|\bBn\b|Battalion|"
     r"R\.\s?A\.\s?M\.\s?C|R\.\s?A\.\s?S\.\s?C|Brigade|Hussars|Lancers|\bBuffs\b|Rifles|Signals|Artillery|"
     r"\bMilitary\b|\bJ\.\s?L\.\s?Coy|Labour\s+Coy|\bCoy\b"),
    ("Police", "government", r"Pol[il]ce|\bB\.\s?S\.\s?P\b|Constab|Gendarm|\bP\.\s?P\b\.?"),
    ("Prison", "government", r"Pri[sz]on|Ph[il]son|\bJail|\bGaol"),
    ("Palestine Railways", "government", r"Rail\s?way|\bP\.\s?R\b\.?|\bC\.\s?M\.\s?E\b|Loco\w*\s+Shed"),
    ("Posts & Telegraphs", "government", r"Posts?\s*(&|\+|and)?\s*Tel|Post[-\s]?Office|Telegra"),
    ("Harbour Works", "government", r"Harbo?u?rs?\s+(Works?|Dept)|Port\s+Works"),
    ("Customs", "government", r"Cust?o?ms?\b|Caustam|Custan"),
    ("Public Works Department", "government", r"P\.\s?W\.\s?D|Public\s+Works|Dist(rict|\.)?\s+Eng"),
    ("Municipality", "government", r"Munic[ia]p"),
    ("Government Hospital", "government", r"G[oa]v\w*\.?\s+Hosp"),
    ("Quarantine", "government", r"Quar[ae]?n?tine"),
    ("Department of Agriculture", "government", r"Agricult\w*\s+(Dept|Department|Station)"),
    ("Department of Health", "government", r"(Health|Medical)\s+(Dept|Department|Office)|Sanitary"),
    ("Hotel", "other", r"\bHotel\b"),
    ("School", "other", r"\bSchool\b|\bCollege\b"),
    ("Monastery or church", "other", r"Monaster|Convent|Carmelite|Mar\s+Elias|Stella\s+Maris"),
]
INSTITUTION_RE = [(name, kind, re.compile(p, re.IGNORECASE)) for name, kind, p in INSTITUTIONS]
KIND = {name: kind for name, kind, _ in INSTITUTIONS}

# Furas's own labels, mapped onto the names above. His broad labels
# ("Government Employee", "Company", "Factory", "Hospital") are refined by the
# patterns where the string says more, and otherwise kept as he gave them.
FURAS_INSTITUTION = {
    "government-police": "Police", "police": "Police",
    "prison": "Prison", "prisoner": "Prison",
    "iraq petroleum company": "Iraq Petroleum Company", "company ip": "Iraq Petroleum Company",
    "military unit": "British Army", "army unit": "British Army", "camp": "British Army",
    "government-post": "Posts & Telegraphs", "government post": "Posts & Telegraphs",
    "posts telegraph": "Posts & Telegraphs", "government-telegraph": "Posts & Telegraphs", "post": "Posts & Telegraphs",
    "government-railway": "Palestine Railways", "palestine railways": "Palestine Railways",
    "railways": "Palestine Railways", "railway station": "Palestine Railways",
    "government-harbour": "Harbour Works", "harbour works": "Harbour Works",
    "customs house": "Customs", "customs": "Customs",
    "municipality": "Municipality", "quarantine": "Quarantine",
    "public works department": "Public Works Department",
    "government-hospital": "Government Hospital",
    "bank": "Barclays Bank", "hotel": "Hotel", "school": "School", "monastery": "Monastery or church",
    "dredging co. ltd": "Tilbury Contracting & Dredging",
}
FURAS_BROAD = {"government employee": ("Government (other)", "government"),
               "health department": ("Department of Health", "government"),
               "government": ("Government (other)", "government"),
               "government laborator": ("Government (other)", "government"),
               "company": ("Company (other)", "company"),
               "factory": ("Company (other)", "company"),
               "quarry": ("Karaman, Dick & Salti", "company"),
               "hospital": ("Hospital (other)", "other"),
               "clinic": ("Hospital (other)", "other")}

# -------------------------------------------------------------- quarters
QUARTERS: dict[str, list[tuple[str, str]]] = {
    "Haifa": [
        # Ard and Harat al-Yahud are two places (Naor 2019); Judah Halevi St.
        # ran through Ard, so its garbled forms count there.
        ("Ard el-Yahud", r"\bar[dl]\W*(el|al|il)?\W*-?\s*yah|ardel\s*yah|y[ae]h?ou?dah?\s*(ha)?\s*le(vi|vin|ami|avy)"),
        ("Harat al-Yahud", r"\bh[ae]?r[ae]?t\W*(el|al|il)?\W*-?\s*yah|hartel\s*yah|jewish\s*q"),
        # The district outside the old town's eastern gate, not the town of
        # Acre (user ruling 2026-10-21). Furas's bare "Acre Gate" = Acre is
        # contradicted by his own "Haifa Acre gate" row, so read as a slip.
        ("Acre Gate", r"\bac(re|ri)'?s?\W*gate|\bgate\s+of\s+acre\b|\bakka\s+gate"),
        ("Hadar HaCarmel", r"\bhadar\b|\bhad\.\s*hac"),
        ("Wadi Salib", r"sal(i|ee|ea)b\b|\bwadi\s*sal[iu]b|\bsalile\b"),
        ("Wadi Nisnas", r"nis+na[sz]|nas+nas|nesnas"),
        ("Wadi Rushmiya", r"r[aou]u?sh?u?mi"),
        ("German Colony", r"german\s*colon|\bgerman\s*qu"),
        ("Bat Galim", r"\bba?e?t?h?[\s-]*galim\b"),
        ("Carmel Station", r"carmel\s+(station|stn)"),
        ("Mount Carmel", r"\bm(oun)?t\.?\s*carmel|har\s*hacarmel|central\s*carmel"),
        ("Neve Sha'anan", r"nev[eh]+\s*sha"),
        ("Herzliya quarter", r"\bherz?e?li?y?a\b|\bhezelia"),
        ("Halisa", r"\bk?h?al+[eiy]+s+[aeiy]?h?\b"),
        ("Harat al-Kanais", r"kana[iy]+s|churches?\s*(qr|qu|q\b|st)"),
        ("Harat al-Kishleh", r"kishl|kashl|barracks\s*q"),
        ("Sharqiyya", r"shar[kq]i"),
        ("Ard el-Ramel", r"\b(ard|arab)?\W*(el|al)?\W*ramel\b"),
        ("Kiryat Eliyahu", r"k[iy]r[iy]?y?at\s*eli"),
        ("Khamra Square", r"\bk?hamra\b"),
        ("Old City", r"haifa\s*el[\s-]*a?t[iy]k|old\s*(haifa|city)"),
        ("Ahuza", r"\bahuz"),
        ("Abbasiyya", r"abbas(ie|iy|i?a\b)"),
        ("Shkhunat Ovdim", r"ovdim|oadim"),
        ("Burj", r"\bbur[jg]\s*(qr|qu|sq|st)"),
        ("Ghazazwa", r"gha?zaz"),
        ("Shawafna", r"shawaf"),
        ("Harat al-Mukhallis", r"m[ui]?k?h?al+[ie]+s|\bn?a?kh?al+is\b|enukhallis"),
        ("Kibbutz Hashomer Hatzair", r"hashomer\s*ha\W?tza|kibb?utz\s*hashomer"),
    ],
    "Acre": [
        ("Mubalatta", r"mubal+at"),
        ("Rashadiyya", r"rash[ae]di"),
        ("Fakhura", r"fakh?ou?r"),
        ("Hammam al-Basha", r"hamm?am\s*(el|al)?\s*basha"),
    ],
}
# A quarter with a Wikidata item to stand for it. Acre Gate has none of its
# own: Faisal Square is where the gate stood, so it is a "located near"
# link, not an identity — the register's Acre Gate is the district around it.
QUARTER_WIKIDATA = {
    "Haifa: Acre Gate": "Q25488483",
}
QUARTER_RE = {town: [(q, re.compile(p, re.IGNORECASE)) for q, p in rules] for town, rules in QUARTERS.items()}


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


# A slip in one cell: plain "Benyamina" carries Government-Harbour, which none
# of his seven other Benyamina rows do. It is the settlement (user ruling
# 2026-10-19).
IGNORE_OTHER_CATEGORY = {"benyamina"}


@lru_cache(maxsize=1)
def furas_labels() -> dict[str, dict[str, str]]:
    """Address string (keyed loosely) -> Furas's row, for annotated strings."""
    out: dict[str, dict[str, str]] = {}
    if not FURAS.exists():
        return out
    with FURAS.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            if not (row.get("type of geographical place") or "").strip():
                continue
            if _key(row["orig address"]) in IGNORE_OTHER_CATEGORY:
                row["other category"] = ""

            for text in (row["orig address"], row["corrected name"]):
                k = _key(text)
                if len(k) >= 4:
                    out.setdefault(k, row)
    return out


# "Near Railway Station" uses the institution as a landmark, not a custodian.
LANDMARK = re.compile(r"\b(near|opposite|opp\.|behind|next\s+to|facing)\s+(the\s+)?$", re.IGNORECASE)
TOWN_SUFFIX = re.compile(r"[\s,.]*\b(haifa|hfa|acre)\b[\s,.]*$|[\s,.]+$", re.IGNORECASE)


def institution_by_pattern(text: str) -> tuple[str, str]:
    for name, kind, rx in INSTITUTION_RE:
        m = rx.search(text)
        if m and not LANDMARK.search(text[:m.start()]):
            return name, kind
    return "", ""


def quarter_by_pattern(text: str, town: str) -> str:
    for quarter, rx in QUARTER_RE.get(town, []):
        if rx.search(text):
            return quarter
    return ""


def town_of(city: str, haifa_family: bool) -> str:
    """Which town's quarters may be read for this record."""
    if not city or haifa_family:
        return "Haifa"
    if city in ("Acre", "Akka"):
        return "Acre"
    return ""


def classify(address: str, city: str, haifa_family: bool) -> dict[str, str]:
    """Institution and quarter named by one record's Address (and City)."""
    out = {"Address institution": "", "Address institution type": "",
           "Neighbourhood": "", "Neighbourhood Wikidata": "", "Address layer source": ""}
    town = town_of(city, haifa_family)
    furas = furas_labels().get(_key(address))
    # His own doubts ("check", "?") are not taken as labels.
    if furas and ("check" in (furas["disambiguate (fill in context)"] or "").lower()
                  or (furas["type of geographical place"] or "").strip() == "?"):
        furas = None
    if furas:
        label = (furas["type of geographical place"] or "").strip().lower()
        other = (furas["other category"] or "").strip().lower()
        reading = furas["Normalized PlaceName if different than corrected name"] or furas["corrected name"]
        for lab in (other, label):
            if lab in FURAS_INSTITUTION:
                name = FURAS_INSTITUTION[lab]
                out["Address institution"], out["Address institution type"] = name, KIND[name]
                break
            if lab in FURAS_BROAD:
                name, kind = institution_by_pattern(f"{reading} {address}")
                out["Address institution"], out["Address institution type"] = (name, kind) if name else FURAS_BROAD[lab]
                break
        if label == "neighborhood":
            ftown = (furas["city"] or "").strip() or town
            if ftown in ("Haifa", "Acre"):
                q = quarter_by_pattern(f"{reading} {address}", ftown)
                name = q or TOWN_SUFFIX.sub("", reading).strip()
                out["Neighbourhood"] = f"{ftown}: {name}"
        if out["Address institution"] or out["Neighbourhood"]:
            out["Address layer source"] = "furas"
    if not out["Address institution"]:
        name, kind = institution_by_pattern(address)
        if name:
            out["Address institution"], out["Address institution type"] = name, kind
            out["Address layer source"] = out["Address layer source"] or "pattern"
    if not out["Neighbourhood"] and town:
        q = quarter_by_pattern(f"{address} | {city}", town)
        if q:
            out["Neighbourhood"] = f"{town}: {q}"
            out["Address layer source"] = out["Address layer source"] or "pattern"
    out["Neighbourhood Wikidata"] = QUARTER_WIKIDATA.get(out["Neighbourhood"], "")
    return out


def evaluate(path: Path) -> None:
    """Score the patterns against Furas's labels on the strings he annotated."""
    csv.field_size_limit(10**9)
    inst, quart = Counter(), Counter()
    misses: Counter = Counter()
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            address, city = row.get("Address") or "", row.get("City") or ""
            if not furas_labels().get(_key(address)):
                continue
            haifa = row.get("City Kima ID") == "791" or not city
            truth = classify(address, city, haifa)
            name, _ = institution_by_pattern(address)
            if truth["Address institution"]:
                inst["furas"] += 1
                inst["agree" if name == truth["Address institution"] else "disagree"] += 1
                if name != truth["Address institution"]:
                    misses[("inst", truth["Address institution"], name or "-", address[:40])] += 1
            elif name:
                inst["pattern-only"] += 1
                misses[("extra", "-", name, address[:40])] += 1
            if truth["Neighbourhood"]:
                town = truth["Neighbourhood"].split(":")[0]
                q = quarter_by_pattern(f"{address} | {city}", town)
                quart["furas"] += 1
                quart["agree" if q and truth["Neighbourhood"].endswith(q) else "disagree"] += 1
    print("institution vs Furas:", dict(inst))
    print("quarter vs Furas:   ", dict(quart))
    for (kind, want, got, text), n in misses.most_common(25):
        print(f"  {n:4} {kind:5} furas={want!r} pattern={got!r}  {text}")


if __name__ == "__main__":
    if "--eval" in sys.argv:
        evaluate(ROOT / "data" / "public" / "hospital-registers-normalized.tsv")
    else:
        print(__doc__)
