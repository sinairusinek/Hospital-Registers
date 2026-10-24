#!/usr/bin/env python3
"""Do the places the clerks put in a district actually lie in it?

Many addresses name a sub-district after the village: "Zeeb - Acre S/D",
"Baka Village, Tul-Karm S/D", "Rosh Pina Safad s/o". Those words were written
in the 1930s and 40s, so they are tested against the MANDATE sub-districts
(user ruling 2026-10-24), not against today's districts or governorates.

The linked place's Mandate sub-district comes from, in this order:

  p131      Wikidata P131 pointing at a Mandate sub-district item
            (instances of Q15665395, "subdistrict of Mandatory Palestine")
  infobox   the enwiki article's infobox ("Subdistrict ... Tulkarm")
  vs1945-name  the name appears in exactly one sub-district's Village
            Statistics 1945 list (enwiki transcription of Hadawi's tables)
  nearest   inferred: majority of the 5 nearest reference points that carry
            one of the two above. A lead, weaker near a boundary.

Verdicts: ok; HOMONYM = the written sub-district's VS 1945 list holds a
village of this name, but the linked place lies elsewhere (the Baka case:
probably linked to a namesake); SOURCE-CONFLICT = only the written sub-
district's list holds the name, so our source for the place is likely the
one at fault; MISMATCH = no namesake there either.

Sub-district boundaries moved during the Mandate (Beisan, the Haifa/Acre/
Nazareth edges). A mismatch is a lead to read, not an error to fix.

Writes kimatch/district-check.tsv (one row per place x written district) and
caches fetched Wikidata/Wikipedia material in kimatch/district-cache.json.

    python3 kimatch/district_check.py [--refresh]
"""
from __future__ import annotations

import csv
import json
import math
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data" / "public" / "hospital-registers-normalized.tsv"
COORDS = ROOT.parent / "data" / "public" / "place-coords.tsv"
CACHE = ROOT / "district-cache.json"
OUT = ROOT / "district-check.tsv"
READINGS = ROOT / "district-check-readings.tsv"
UA = "HospitalRegisters/1.0 (https://github.com/sinaiRusinek; sinai.rusinek@gmail.com)"

MANDATE_SD_CLASS = "Q15665395"

# What the clerks wrote -> Mandate sub-district (or a Transjordan district).
ALIASES = {
    "Acre": ["acre", "acca", "akre", "akka", "acco"],
    "Haifa": ["haifa", "hfa"],
    "Jenin": ["jenin", "jennin", "jinin", "jenine"],
    "Safad": ["safad", "safed", "sfa", "zefat"],
    "Nablus": ["nablus", "nablous", "naplus"],
    "Nazareth": ["nazareth", "naz", "nazereth"],
    "Tiberias": ["tiberias", "tiberia", "tib"],
    "Tulkarm": ["tulkarem", "tulkarm", "tul-karm", "tul-karem", "toulkarem", "karm", "karem", "tul karm"],
    "Beisan": ["beisan", "beissan", "baisan", "bisan"],
    "Jaffa": ["jaffa"],
    "Gaza": ["gaza"],
    "Jerusalem": ["jerusalem", "j'lem", "jere", "jlem"],
    "Ramle": ["ramle", "ramleh"],
    "Hebron": ["hebron"],
    "Ramallah": ["ramallah"],
    "Irbid (TJ)": ["irbed", "irbid"],
    "Ajlun (TJ)": ["ajloun", "ajlun"],
}
ALIAS = {a: sd for sd, names in ALIASES.items() for a in names}

# "Haifa District" may name the district, not the sub-district: Haifa was the
# seat of the Northern District until 1939; from 1939 Nablus was the seat of
# Samaria and Nazareth of Galilee. A mismatch these cover is a weaker lead.
DISTRICT_SEATS = {
    "Haifa": {"Haifa", "Acre", "Safad", "Tiberias", "Nazareth", "Beisan", "Jenin", "Tulkarm", "Nablus"},
    "Nablus": {"Nablus", "Jenin", "Tulkarm"},
    "Nazareth": {"Nazareth", "Acre", "Safad", "Tiberias", "Beisan"},
    "Jaffa": {"Jaffa", "Ramle"},
}

# Names the clerks used for areas that were never Mandate sub-districts.
NOT_SUBDISTRICT = {"khudera": "Hadera", "khedera": "Hadera", "khedēra": "Hadera",
                   "benjamina": "Binyamina", "huleh": "Huleh", "salkhat": "Salkhad (Syria)"}
for k in ["akko", "jeni", "nez", "kaif", "neblus", "tulkerman"]:
    ALIAS.setdefault(k, {"akko": "Acre", "jeni": "Jenin", "nez": "Nazareth", "kaif": "Haifa",
                         "neblus": "Nablus", "tulkerman": "Tulkarm"}[k])

# A district counts only when a known name sits next to a marker, either side:
# "Zeeb - Acre S/D", "Acre's/d", "Arrabeh S/d Jenin", "Hfa St/Dist.".
MARKER = r"(?:s\s*[./]?\s*(?:d|o)\b|(?:s|st)\s*[./]\s*dist(?:rict)?\b|sub[-./ ]*dist(?:rict)?\b|dist(?:rict)?\b)"
NAMES = "|".join(sorted((re.escape(a) for a in list(ALIAS) + list(NOT_SUBDISTRICT)), key=len, reverse=True))
BEFORE = re.compile(r"(?<![A-Za-z])(" + NAMES + r")(?:'s)?[\s,.\-(/]{0,4}" + MARKER, re.I)
AFTER = re.compile(r"(?<![A-Za-z/])" + MARKER + r"[\s,.\-]{1,4}(" + NAMES + r")(?![A-Za-z])", re.I)


def get(url: str) -> dict:
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 + 3 * attempt)
    raise RuntimeError(url)


def sparql(query: str) -> list[dict]:
    url = "https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(query)
    return get(url)["results"]["bindings"]


def written_district(text: str) -> str | None:
    # "Sasa. Safad s/d Haifa. Wadi el Salib": a name before the marker is the
    # district; one after it is only read when nothing precedes a marker.
    found = [(m.start(), m.group(1)) for m in BEFORE.finditer(text)]
    found = found or [(m.start(), m.group(1)) for m in AFTER.finditer(text)]
    if not found:
        return None
    token = max(found)[1].lower()
    if token in NOT_SUBDISTRICT:
        return "~" + NOT_SUBDISTRICT[token]
    return ALIAS[token]


def sd_name(label: str) -> str:
    label = re.sub(r",? Mandatory Palestine", "", label)
    return label.replace(" Subdistrict", "").replace("Ramla", "Ramle")


def load_cache(refresh: bool, qids: set[str]) -> dict:
    cache = {} if refresh or not CACHE.exists() else json.loads(CACHE.read_text())
    if "subdistricts" not in cache:
        rows = sparql(f"SELECT ?sd ?sdLabel WHERE {{ ?sd wdt:P31 wd:{MANDATE_SD_CLASS} . "
                      'SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }')
        cache["subdistricts"] = {r["sd"]["value"].rsplit("/", 1)[1]: sd_name(r["sdLabel"]["value"]) for r in rows}
    if "reference" not in cache:
        sds = " ".join("wd:" + q for q in cache["subdistricts"])
        rows = sparql(f"SELECT ?v ?sd ?c WHERE {{ VALUES ?sd {{ {sds} }} ?v wdt:P131 ?sd ; wdt:P625 ?c . }}")
        cache["reference"] = [[r["v"]["value"].rsplit("/", 1)[1], r["sd"]["value"].rsplit("/", 1)[1], r["c"]["value"]] for r in rows]
    if "vs1945" not in cache:
        cache["vs1945"] = vs1945_tables()
    if "wiki_reference" not in cache:
        cache["wiki_reference"] = wiki_reference()
    items = cache.setdefault("items", {})
    todo = sorted(q for q in qids if q not in items)
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        d = get("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=claims|sitelinks|labels"
                "&languages=en&sitefilter=enwiki&ids=" + "|".join(batch))
        for q, e in d.get("entities", {}).items():
            claims = e.get("claims", {})
            p131 = [c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in claims.get("P131", [])]
            coord = None
            for c in claims.get("P625", []):
                v = c["mainsnak"].get("datavalue", {}).get("value")
                if v:
                    coord = [v["latitude"], v["longitude"]]
                    break
            items[q] = {"label": e.get("labels", {}).get("en", {}).get("value", ""),
                        "p131": [p for p in p131 if p],
                        "coord": coord,
                        "enwiki": e.get("sitelinks", {}).get("enwiki", {}).get("title")}
    titles = sorted({v["enwiki"] for v in items.values() if v.get("enwiki")} - set(cache.setdefault("infobox", {})))
    for i in range(0, len(titles), 40):
        batch = titles[i:i + 40]
        d = get("https://en.wikipedia.org/w/api.php?action=query&format=json&prop=revisions&rvprop=content"
                "&rvslots=main&redirects=1&titles=" + urllib.parse.quote("|".join(batch)))
        back = {t: t for t in batch}
        for n in d["query"].get("normalized", []) + d["query"].get("redirects", []):
            back[n["to"]] = back.get(n["from"], n["from"])
        for page in d["query"]["pages"].values():
            text = page.get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("*", "")
            cache["infobox"][back.get(page["title"], page["title"])] = infobox_subdistrict(text)
        for t in batch:
            cache["infobox"].setdefault(t, None)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
    return cache


def vs1945_tables() -> dict[str, list[str]]:
    """Village Statistics 1945, locality names per sub-district, as transcribed
    in the enwiki "<X> Subdistrict, Mandatory Palestine" tables (Hadawi)."""
    out = {}
    for sd in ALIASES:
        if "(TJ)" in sd:
            continue
        params = {"action": "parse", "page": f"{sd} Subdistrict, Mandatory Palestine", "prop": "wikitext",
                  "format": "json", "formatversion": 2, "redirects": 1}
        d = get("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params))
        text = d.get("parse", {}).get("wikitext", "")
        out[sd] = re.findall(r"^\|\s*([^|\n!{][^\n]*?)\s*\|\|", text, re.M)
        time.sleep(1.5)
    return out


def skeleton(name: str) -> str:
    """Consonant skeleton of a romanised Arabic/Hebrew place name."""
    name = unicodedata.normalize("NFKD", name.lower())
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = re.sub(r"[‘’'`ʿʻ]", "", name)
    name = re.sub(r"\b(?:el|al|er|ar|es|as|esh|ash|et|at|ed|ad|ez|az|en|an|edh|eth)\b[- ]?", "", name)
    name = re.sub(r"\b(?:urban|rural|village|kafr|kufr|kfar|kefar)\b", lambda m: "kfr" if m.group(0)[0] == "k" else "", name)
    name = name.replace("kh", "k").replace("q", "k").replace("gh", "g").replace("ou", "u").replace("sh", "s").replace("dh", "d")
    name = re.sub(r"[^a-z]", "", name)
    name = re.sub(r"[aeiouyhw]", "", name)
    return re.sub(r"(.)\1+", r"\1", name)


def vs_names(row: str) -> list[str]:
    """A VS row's own name plus every place it says it includes."""
    row = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", row)
    names = re.split(r" and |,", re.sub(r"\(.*?\)", "", row))
    for inner in re.findall(r"\((.*?)\)", row):
        if inner.lower().startswith("includ"):
            names += re.split(r",| and ", inner.split(" ", 1)[1] if " " in inner else "")
        elif len(inner) > 3:
            names.append(inner)
    return [n.strip() for n in names if n.strip()]


def wiki_reference() -> list[list]:
    """Every enwiki article whose infobox names a Mandate sub-district, with its
    coordinate. Wikidata P131 is too sparse for this (Jenin has 3 items); the
    village articles carry the Mandate sub-district in their infobox."""
    found: dict[str, list] = {}
    titles = [f"{sd} Subdistrict, Mandatory Palestine" for sd in ALIASES if "(TJ)" not in sd]
    for title in titles:
        cont: dict = {}
        while True:
            params = {"action": "query", "format": "json", "generator": "backlinks", "gbltitle": title,
                      "gblnamespace": 0, "gbllimit": 50, "gblredirect": 1, "prop": "coordinates|revisions",
                      "rvprop": "content", "rvslots": "main", "colimit": "max", **cont}
            d = get("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params))
            for page in d.get("query", {}).get("pages", {}).values():
                text = page.get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("*")
                co = page.get("coordinates")
                if text is None or not co:
                    continue
                sd = infobox_subdistrict(text)
                if sd:
                    found[page["title"]] = [page["title"], sd, co[0]["lat"], co[0]["lon"]]
            if "continue" not in d:
                break
            cont = d["continue"]
    return sorted(found.values())


def infobox_subdistrict(text: str) -> str | None:
    """The Mandate sub-district an infobox names, if it names one."""
    head = text[:6000]
    for m in re.finditer(r"\|\s*subdivision_name\d*\s*=\s*\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", head):
        target = m.group(1)
        if "Subdistrict" in target and "Israel" not in target and "Northern" not in target:
            name = sd_name(target)
            if name in ALIASES:
                return name
    return None


def dist(a, b) -> float:
    return math.hypot(a[0] - b[0], (a[1] - b[1]) * math.cos(math.radians(a[0])))


class Gazetteer:
    """A linked place's Mandate sub-district, from the cached sources."""

    def __init__(self, cache: dict):
        self.cache = cache
        self.sds = cache["subdistricts"]
        self.coords = {}
        for c in csv.DictReader(COORDS.open(), delimiter="\t"):
            if c["lat"]:
                self.coords[c["city"]] = (float(c["lat"]), float(c["lon"]))
        self.ref = []
        for _q, sd, c in cache["reference"]:
            m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", c)
            if m:
                self.ref.append(((float(m.group(2)), float(m.group(1))), self.sds[sd]))
        for _title, sd, lat, lon in cache["wiki_reference"]:
            self.ref.append(((lat, lon), sd))
        for q, it in cache["items"].items():
            sd, how = self.own_sd(q)
            if how == "infobox" and it.get("coord"):
                self.ref.append((tuple(it["coord"]), sd))
        self.vs_index: dict[str, set[str]] = defaultdict(set)
        for vsd, vrows in cache["vs1945"].items():
            for vrow in vrows:
                for n in vs_names(vrow):
                    sk = skeleton(n)
                    if len(sk) >= 2:
                        self.vs_index[sk].add(vsd)

    def own_sd(self, q: str) -> tuple[str, str]:
        it = self.cache["items"].get(q, {})
        for p in it.get("p131", []):
            if p in self.sds:
                return self.sds[p], "p131"
        ib = self.cache["infobox"].get(it.get("enwiki") or "")
        if ib:
            return ib, "infobox"
        return "", ""

    def vs_sds(self, city: str, place: str) -> set[str]:
        it = self.cache["items"].get(place, {})
        labels = {*city.split("|"), it.get("label", ""), (it.get("enwiki") or "").split(",")[0]}
        labels |= {re.sub(r"\s*\(.*\)", "", x) for x in labels}
        found: set[str] = set()
        for lab in labels:
            sk = skeleton(lab)
            if len(sk) >= 2:
                found |= self.vs_index.get(sk, set())
        return found

    def nearest(self, pt) -> tuple[str, str, str]:
        nn = sorted(self.ref, key=lambda x: dist(pt, x[0]))[:5]
        if dist(pt, nn[0][0]) * 111 > 20:      # a point outside Palestine has no neighbours to vote
            return "", "", f"{dist(pt, nn[0][0]) * 111:.0f} km"
        sd, n = Counter(s for _, s in nn).most_common(1)[0]
        return sd, f"nearest {n}/5", f"{dist(pt, nn[0][0]) * 111:.1f} km"

    def subdistrict(self, city: str, place: str) -> tuple[str, str, set[str], str]:
        """-> (sub-district, how it was found, VS 1945 lists holding the name, nearest-ref distance)"""
        sd, how = self.own_sd(place) if place.startswith("Q") else ("", "")
        in_vs = self.vs_sds(city, place)
        if not sd and len(in_vs) == 1:
            sd, how = next(iter(in_vs)), "vs1945-name"
        pt = self.coords.get(city) or tuple(self.cache["items"].get(place, {}).get("coord") or ()) or None
        near = ""
        if not sd and pt:
            sd, how, near = self.nearest(pt)
        return sd, how, in_vs, near


def main() -> int:
    rows = list(csv.DictReader(DATA.open(), delimiter="\t", quoting=csv.QUOTE_NONE))
    # Leads already read off the scans (kimatch/district-check-readings.tsv) are
    # set aside, so a rerun only shows what nobody has looked at.
    read = {(r["notebook"], r["serial"]) for r in csv.DictReader(READINGS.open(), delimiter="\t")} if READINGS.exists() else set()
    already_read = 0
    pairs: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    unlinked: Counter = Counter()
    for r in rows:
        if r.get("Notebook_Number") == "25":
            continue
        wd = written_district(r["Address"] + " | " + r.get("City as written", ""))
        if not wd:
            continue
        place = r["City Wikidata"] or (("kima:" + r["City Kima ID"]) if r["City Kima ID"] else "")
        if (r["Notebook_Number"], r["Notebook Record ID"]) in read:
            already_read += 1
            continue
        if not place:
            unlinked[(r["City"], wd)] += 1
            continue
        pairs[(r["City"], place, wd)].append(r)

    qids = {p for _, p, _ in pairs if p.startswith("Q")}
    gaz = Gazetteer(load_cache("--refresh" in sys.argv, qids))

    out = []
    for (city, place, wd), recs in sorted(pairs.items()):
        sd, how, in_vs, near = gaz.subdistrict(city, place)
        if wd.startswith("~"):
            verdict = "not-a-subdistrict"
        elif not sd and wd not in in_vs:
            verdict = "no-subdistrict-known"
        elif wd.endswith("(TJ)"):
            verdict = "transjordan"
        elif wd == sd:
            verdict = "ok"
        elif wd in in_vs and (how.startswith("nearest") or how == ""):
            verdict, how = "ok", (how + "; " if how else "") + "name in VS list"
        elif wd in in_vs and sd in in_vs and not how.startswith("nearest"):
            verdict = "HOMONYM"
        elif wd in in_vs:
            verdict = "SOURCE-CONFLICT"
        elif sd in DISTRICT_SEATS.get(wd, ()):
            verdict = "district-level?"
        else:
            verdict = "MISMATCH"
        refs = "; ".join(f"NB{r['Notebook_Number']}#{r['Notebook Record ID']} '{r['Address']}'" for r in recs[:4])
        out.append(dict(verdict=verdict, city=city, place=place, written_district=wd,
                        place_subdistrict=sd, source=how, vs1945_name_in=", ".join(sorted(in_vs)), nearest_ref=near, n_records=len(recs), examples=refs))
    order = {"HOMONYM": -2, "SOURCE-CONFLICT": -1, "MISMATCH": 0, "district-level?": 0.5, "not-a-subdistrict": 1, "no-subdistrict-known": 2, "transjordan": 3, "ok": 4}
    out.sort(key=lambda o: (order[o["verdict"]], -o["n_records"]))
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]), delimiter="\t")
        w.writeheader()
        w.writerows(out)
    tally = Counter()
    for o in out:
        tally[o["verdict"]] += o["n_records"]
    print(f"Wrote {OUT}: {len(out)} place x district pairs")
    for k in order:
        print(f"  {k:22} {sum(1 for o in out if o['verdict'] == k):4} pairs  {tally[k]:5} records")
    print(f"  already read off the scans (district-check-readings.tsv): {already_read} records")
    print(f"  unlinked City with a written district: {sum(unlinked.values())} records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
