#!/usr/bin/env python3
"""Link unlinked records through the sub-district their address names.

A spelling the gazetteer cannot settle on its own — "Kwekat", "Zbuba",
"Mielia" — often comes with the clerk's sub-district: "Zbuba, Jenin S/Dist.".
The district narrows the candidates to the places that actually lay there
(Mandate sub-districts, as in kimatch/district_check.py), and one candidate
left is a reading.

Two tiers, tried in order:

  ruled   the place word matches a place already ruled in
          city-kima-decisions.tsv (loose key, or consonant skeleton with close
          spellings), and exactly one such place lies in the written
          sub-district
  vs1945  no ruled place fits, but exactly one village of the written
          sub-district's Village Statistics 1945 list has the same skeleton,
          and a Wikidata item of that name lies in that sub-district

Everything else is written to the proposals file as unresolved, with its
candidates. Nothing here edits the decisions; --apply appends the resolved
records to record-readings.tsv and new places to city-kima-decisions.tsv.

    python3 kimatch/district_link.py [--apply]
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
import unicodedata
import urllib.parse
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import district_check as dc  # noqa: E402
import place_resolver as pr  # noqa: E402

OUT = ROOT / "district-link-proposals.tsv"
READINGS = ROOT / "record-readings.tsv"
DECISIONS = ROOT / "city-kima-decisions.tsv"
WD_CACHE = ROOT / "district-link-cache.json"

# West Bank villages carry only today's governorate. Inside the vs1945 tier —
# where the VS list already puts the name in the written sub-district — the
# governorate is enough to say the Wikidata item is in the right area. The
# edges differ from the Mandate's, so it is never used to judge a mismatch.
GOVERNORATE_SD = {
    "Q519311": "Jenin", "Q1093157": "Tulkarm", "Q1074443": "Tulkarm", "Q1074138": "Nablus",
    "Q948228": "Nablus", "Q926530": "Nablus", "Q1093166": "Ramallah", "Q264180": "Hebron",
    "Q247037": "Jerusalem", "Q658527": "Jerusalem", "Q941828": "Jerusalem",
}

# VS 1945 names whose place is already ruled under another spelling the
# skeleton test is too strict to join (Rama/Rameh, Lubiya/Lubieh).
SAME_AS_RULED = {"Rama (Acre)": "Rameh", "Lubiya (Tiberias)": "Lubieh"}

# Readings refused on review (2026-10-24): address fragment -> the wrong target.
REJECT = {
    ("Azara", "Al-Mazar (Haifa)"): "Azara is not al-Mazar",
    ("Kiryat Kharoshet", "Kiryat Ata"): "Kfar Kharoshet is Kiryat Kharoshet, not Kiryat Ata (standing ruling)",
    ("Kiriat El Naber", "Iqrith (Acre)"): "not Iqrith",
    ("Samma", "Sammu'i (Safad)"): "scan NB24 p2 reads 'Samma - Safad s/D' plainly; which village is open",
    ("Ein el Asad", "Deir el Asad"): "Ein al-Asad is its own village",
    ("Silwad", "Silwan (Jerusalem)"): "Silwad was a Ramallah village; Silwan is another place",
}

# First words that are a kind of place, not its name: "Kufr Rais" is not "Kufr".
GENERIC = {"kiryat", "kiriat", "qiryat", "kufr", "kafr", "kfar", "kefar", "kufer", "kafer", "kfr", "deir", "beit", "bet", "bait", "ein", "ain", "um",
           "khirbet", "khirbat", "tell", "tel", "arab", "jisr", "nahr", "wadi", "abu", "bir", "khan", "sheikh", "kh", "ard", "harat"}

DROP = re.compile(r"\b(c\s*/\s*o|own\s+house|house|village|vill|near|of|the|beit|bet|dar)\b\.?", re.I)


def fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c))


def place_words(r: dict) -> list[str]:
    """Candidate place strings: the City, and the address pieces that are not
    the district, a street or an addressee."""
    r = {k: fold(v) if k in ("Address", "City") else v for k, v in r.items()}
    text = r["Address"] or ""
    for rx in (dc.BEFORE, dc.AFTER):
        text = rx.sub(" | ", text)
    pieces = [r["City"]] if r["City"] and not dc.written_district(r["City"]) else []
    for seg in pr.SEGMENTS.split(text):
        seg = seg.strip(" .-–")
        if not seg or pr.STREETISH.search(seg) or re.match(r"^\s*c\s*/\s*o\b", seg, re.I):
            continue
        seg = re.sub(r"\s+", " ", DROP.sub(" ", seg)).strip(" .-")
        if len(pr.loose_key(seg)) >= 3:
            pieces.append(seg)
            words = seg.split()
            if len(words) > 1 and pr.loose_key(words[0]) not in GENERIC:   # "Zammoun village Nablus" -> "Zammoun"
                pieces.append(words[0])
    return list(dict.fromkeys(pieces))


def ruled_places() -> dict[tuple[str, str], dict]:
    """Every matched place, with its spellings."""
    out: dict[tuple[str, str], dict] = {}
    for r in csv.DictReader(DECISIONS.open(encoding="utf-8"), delimiter="\t"):
        if r["decision"] != "matched" or not (r["kima_id"] or r["wikidata_qid"]):
            continue
        place = (r["kima_id"], r["wikidata_qid"])
        out.setdefault(place, {"spellings": set(), "qid": r["wikidata_qid"], "kima": r["kima_id"]})
        out[place]["spellings"].add(r["city"])
    return out


def close(a: str, b: str) -> bool:
    ka, kb = pr.loose_key(a), pr.loose_key(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    sa, sb = pr.skeleton(ka), pr.skeleton(kb)
    if sa != sb or len(sa) < 2:
        return False
    # Short skeletons are only safe because the district has already narrowed
    # the field; they still need close spellings ("Rama"/"Rameh", "Milia"/"Mi'ilya").
    need = 0.7 if len(sa) >= 4 else 0.75
    return SequenceMatcher(None, pr._folded(ka), pr._folded(kb)).ratio() >= need


def name_match(a: str, b: str) -> bool:
    """Same place name, for two strings already known to share a sub-district:
    the district has narrowed the field, so short skeletons and the clerk's
    kh-for-h spellings ("Sukhmata"/"Suhmata") are allowed."""
    ka, kb = pr.loose_key(a), pr.loose_key(b)
    if len(ka) < 3 or len(kb) < 3:
        return False
    r = SequenceMatcher(None, pr._folded(ka), pr._folded(kb)).ratio()
    sa, sb = dc.skeleton(a), dc.skeleton(b)
    if sa == sb and len(sa) >= 2:
        return r >= (0.6 if len(sa) >= 3 else 0.65)
    return r >= 0.8 and min(len(ka), len(kb)) >= 5


def enwiki_qid(title: str, cache: dict) -> str:
    key = "enwiki:" + title
    if key not in cache:
        d = dc.get("https://en.wikipedia.org/w/api.php?action=query&format=json&prop=pageprops&redirects=1&titles="
                   + urllib.parse.quote(title))
        cache[key] = next(iter(d["query"]["pages"].values())).get("pageprops", {}).get("wikibase_item", "")
        time.sleep(0.3)
    return cache[key]


def wikidata_search(name: str, cache: dict) -> list[dict]:
    if name in cache:
        return cache[name]
    url = ("https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en&type=item&limit=10&search="
           + urllib.parse.quote(name))
    hits = dc.get(url).get("search", [])
    cache[name] = [{"id": h["id"], "label": h.get("label", ""), "description": h.get("description", "")} for h in hits]
    time.sleep(0.3)
    return cache[name]


def vs_clean(row: str) -> str:
    row = row.replace("‘", "'").replace("’", "'")
    row = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", row)
    row = re.sub(r"\((?:El|Er|Es|Et|Ed|Ez|Esh|Edh|En)\)", "", row)
    row = re.sub(r"\(.*?\)", "", row)
    return re.sub(r"\s+", " ", row).strip(" ,")


def main() -> int:
    rows = list(csv.DictReader(dc.DATA.open(), delimiter="\t", quoting=csv.QUOTE_NONE))
    todo = []
    for r in rows:
        if r.get("Notebook_Number") == "25" or r["City Wikidata"] or r["City Kima ID"]:
            continue
        wd = dc.written_district(r["Address"] + " | " + r.get("City as written", ""))
        if wd and not wd.startswith("~") and "(TJ)" not in wd:
            todo.append((r, wd))

    places = ruled_places()
    qids = {p["qid"] for p in places.values() if p["qid"]}
    gaz = dc.Gazetteer(dc.load_cache(False, qids))
    place_sd = {}
    for key, p in places.items():
        spelling = sorted(p["spellings"], key=len)[0]
        place_sd[key] = gaz.subdistrict(spelling, p["qid"] or ("kima:" + p["kima"]))[0]
    canon = pr.canonical()

    wcache = json.loads(WD_CACHE.read_text()) if WD_CACHE.exists() else {}
    vs_by_sd = {sd: [(vs_clean(v), v) for v in rows_] for sd, rows_ in gaz.cache["vs1945"].items()}

    def ruled_or_new(qid: str, new: str) -> str:
        ruled = next((k for k, p in places.items() if p["qid"] == qid), None)
        return (canon.get((ruled[0], ruled[1] if not ruled[0] else "")) if ruled else None) or SAME_AS_RULED.get(new, new)

    out = []
    for r, wd in todo:
        words = place_words(r)
        rec = dict(notebook=r["Notebook_Number"], serial=r["Notebook Record ID"], admission_date=r["Admission Date"],
                   city=r["City"], address=r["Address"], written_district=wd, words=" | ".join(words),
                   tier="", target_city="", qid="", candidates="")
        # tier 1: a ruled place in that sub-district
        hits = {key for w in words for key, p in places.items() if any(name_match(w, s) for s in p["spellings"])}
        here = {k for k in hits if place_sd.get(k) == wd}
        # The district's own town ("Dabburi - Nazareth S/D") is the district
        # talking, not the place, whenever another word is left over.
        town = {k for k in here if any(close(wd, sp) for sp in places[k]["spellings"])}
        if town and any(not any(close(w, sp) for k in town for sp in places[k]["spellings"]) for w in words):
            here -= town
        if len(here) == 1:
            key = here.pop()
            rec.update(tier="ruled", qid=places[key]["qid"],
                       target_city=canon.get((key[0], key[1] if not key[0] else ""), sorted(places[key]["spellings"])[0]))
            out.append(rec)
            continue
        rec["candidates"] = "; ".join(f"{sorted(places[k]['spellings'])[0]} ({place_sd.get(k) or '?'})" for k in hits)
        # tier 2: the written sub-district's own villages — enwiki articles whose
        # infobox puts them there, then the VS 1945 list and a Wikidata search
        vs = {(vs_clean(raw), raw) for w in words for raw in gaz.cache["vs1945"].get(wd, [])
              for n in dc.vs_names(raw) if name_match(w, n)}
        names = words + [c for c, _ in vs]
        wiki = {t for t, sd, _lat, _lon in gaz.cache["wiki_reference"] if sd == wd
                and any(name_match(n, re.sub(r"^(al|el|ar|as|ash|at|ad|az|an)-", "", t.split(",")[0], flags=re.I)) for n in names)}
        if vs:
            rec["candidates"] += " | VS 1945: " + "; ".join(sorted(r for _, r in vs))
        if wiki:
            rec["candidates"] += " | enwiki: " + "; ".join(sorted(wiki))
        if len(vs) == 1 and f"{next(iter(vs))[0]} ({wd})" in SAME_AS_RULED:
            rec.update(tier="vs1945", target_city=SAME_AS_RULED[f"{next(iter(vs))[0]} ({wd})"])
        elif len(wiki) == 1 and len(vs) <= 1:
            title = next(iter(wiki))
            qid = enwiki_qid(title, wcache)
            if qid:
                label = next(iter(vs))[0] if vs else title.split(",")[0]
                rec.update(tier="enwiki", qid=qid, target_city=ruled_or_new(qid, f"{label} ({wd})"))
        elif len(vs) == 1:
            clean, raw = next(iter(vs))
            found = []
            # The VS name first; the clerk's spelling only if it finds nothing,
            # so one village gets one item however it was spelt.
            search = [clean] if wikidata_search(clean, wcache) else [w for w in words if name_match(w, clean)]
            for name in dict.fromkeys(search):
                for h in wikidata_search(name, wcache):
                    if name_match(h["label"].split(",")[0], clean) and h["id"] not in {f[0] for f in found}:
                        found.append((h["id"], h["label"]))
            ok = []
            if found:
                gaz.cache = dc.load_cache(False, {f[0] for f in found})
                for qid, label in found:
                    item = gaz.cache["items"].get(qid, {})
                    if not item.get("coord"):
                        continue
                    # placed by something other than its name
                    sd, _ = gaz.own_sd(qid)
                    sd = sd or gaz.nearest(tuple(item["coord"]))[0]
                    gov = {GOVERNORATE_SD[g] for g in item.get("p131", []) if g in GOVERNORATE_SD}
                    if sd == wd or wd in gov:
                        ok.append((qid, label))
            rec["candidates"] += " | wikidata: " + ", ".join(f"{q} {l}" for q, l in found)
            if len(ok) == 1:
                rec.update(tier="vs1945", qid=ok[0][0], target_city=ruled_or_new(ok[0][0], f"{clean} ({wd})"))
        for (frag, target), why in REJECT.items():
            if rec["target_city"] == target and frag.lower() in (rec["address"] + " " + rec["city"]).lower():
                rec["candidates"] += f" | refused {target}: {why}"
                rec.update(tier="", target_city="", qid="")
        out.append(rec)
    WD_CACHE.write_text(json.dumps(wcache, ensure_ascii=False, indent=1))

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]), delimiter="\t")
        w.writeheader()
        w.writerows(sorted(out, key=lambda o: (o["tier"] == "", o["tier"], o["target_city"])))
    n = defaultdict(int)
    for o in out:
        n[o["tier"] or "unresolved"] += 1
    print(f"Wrote {OUT}: {len(out)} records — " + ", ".join(f"{k} {v}" for k, v in sorted(n.items())))

    if "--apply" in sys.argv:
        existing = {r["city"] for r in csv.DictReader(DECISIONS.open(encoding="utf-8"), delimiter="\t")}
        new_rows, readings = {}, []
        for o in out:
            # a reading is keyed by notebook and serial: without a serial it
            # would land on every serial-less row of that notebook and year
            if not o["tier"] or not o["serial"].strip():
                continue
            if o["tier"] in ("vs1945", "enwiki") and o["qid"] and o["target_city"] not in existing:
                new_rows[o["target_city"]] = (f"{o['target_city']}\t{o['target_city']}\t0\t\t\t{o['qid']}\thuman\t\tmatched\tdistrict-link\t\tagent\t"
                                              f"{'Village Statistics 1945' if o['tier'] == 'vs1945' else 'its enwiki infobox'} puts it in {o['written_district']} S/D, which the address names (kimatch/district_link.py)\t2026-10-24")
            readings.append("\t".join([o["notebook"], o["serial"], o["admission_date"], o["target_city"],
                                       f"address (district_link.py, {o['tier']}): \"{o['address']}\" names {o['written_district']} S/D"]))
        with DECISIONS.open("a", encoding="utf-8") as f:
            for row in new_rows.values():
                f.write(row + "\n")
        with READINGS.open("a", encoding="utf-8") as f:
            for row in readings:
                f.write(row + "\n")
        print(f"applied: {len(readings)} record readings, {len(new_rows)} new places")
    return 0


if __name__ == "__main__":
    sys.exit(main())
