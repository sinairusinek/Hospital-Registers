"""Resolve coordinates for every reviewed City value, for the map view.

Reads kimatch/city-kima-decisions.tsv and writes

  data/public/place-coords.tsv   city -> lat, lon, source, and the identifiers

Only rows the review decided were `matched` carry an identifier, so only those
can be placed. Everything else — ambiguous, no-Kima-entry, junk — is written
out with empty coordinates and its decision, so the map can say honestly how
many records it cannot put on the ground rather than silently dropping them.

Two authorities, in this order:

  * Kima, via data.geo-kima.org/api/places/<id>. The gazetteer the review was
    conducted against, so its point is the one the decision actually meant.
  * Wikidata P625, for the handful of matched rows that carry a QID but whose
    Kima entry has no coordinate.

The result is cached in place-coords.tsv itself: a row that already has a
coordinate is not re-fetched unless --refresh is passed. Run:

    python3 pipeline/place_coords.py [--refresh]
"""

from __future__ import annotations

import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECISIONS = ROOT / "kimatch" / "city-kima-decisions.tsv"
OUTPUT = ROOT / "data" / "public" / "place-coords.tsv"

KIMA_API = "https://data.geo-kima.org/api/places/{}"
WDQS = "https://query.wikidata.org/sparql"
UA = "HospitalRegisters/1.0 (https://github.com/sinaiRusinek; sinai.rusinek@gmail.com)"

FIELDS = ["city", "lat", "lon", "source", "kima_id", "kima_name_rom",
          "wikidata_qid", "decision", "decided_by", "n_records"]


def get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return fh.read()


def kima_point(place_id: str) -> tuple[float, float] | None:
    try:
        rec = json.loads(get(KIMA_API.format(place_id)))
    except Exception as exc:                       # network, 404, bad JSON
        print(f"  kima {place_id}: {exc}", file=sys.stderr)
        return None
    lat, lon = rec.get("lat"), rec.get("lon")
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


def wikidata_points(qids: list[str]) -> dict[str, tuple[float, float]]:
    """One batched SPARQL call for the QIDs Kima could not place."""
    if not qids:
        return {}
    values = " ".join(f"wd:{q}" for q in qids)
    query = (f"SELECT ?p ?lat ?lon WHERE {{ VALUES ?p {{ {values} }} "
             "?p p:P625/psv:P625 ?v. ?v wikibase:geoLatitude ?lat; "
             "wikibase:geoLongitude ?lon. }")
    url = WDQS + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    try:
        payload = json.loads(get(url, timeout=60))
    except Exception as exc:
        print(f"  wikidata batch: {exc}", file=sys.stderr)
        return {}
    out: dict[str, tuple[float, float]] = {}
    for row in payload["results"]["bindings"]:
        qid = row["p"]["value"].rsplit("/", 1)[-1]
        out[qid] = (float(row["lat"]["value"]), float(row["lon"]["value"]))
    return out


def load_cache() -> dict[str, dict[str, str]]:
    if not OUTPUT.exists():
        return {}
    with OUTPUT.open(encoding="utf-8") as fh:
        return {r["city"]: r for r in csv.DictReader(fh, delimiter="\t")}


def main() -> None:
    refresh = "--refresh" in sys.argv
    cache = {} if refresh else load_cache()

    with DECISIONS.open(encoding="utf-8") as fh:
        decisions = list(csv.DictReader(fh, delimiter="\t"))

    rows: list[dict[str, str]] = []
    needs_wikidata: list[dict[str, str]] = []

    for d in decisions:
        city = d["city"]
        row = {
            "city": city,
            "lat": "", "lon": "", "source": "",
            "kima_id": d.get("kima_id", ""),
            "kima_name_rom": d.get("kima_name_rom", ""),
            "wikidata_qid": d.get("wikidata_qid", ""),
            "decision": d.get("decision", ""),
            "decided_by": d.get("decided_by", ""),
            "n_records": d.get("n_records", ""),
        }

        cached = cache.get(city)
        if cached and cached.get("lat"):
            row["lat"], row["lon"] = cached["lat"], cached["lon"]
            row["source"] = cached.get("source", "")
            rows.append(row)
            continue

        # Only a confirmed match earns a point on the map.
        if row["decision"] != "matched":
            rows.append(row)
            continue

        if row["kima_id"]:
            point = kima_point(row["kima_id"])
            time.sleep(0.2)                        # civil to a small gazetteer
            if point:
                row["lat"], row["lon"] = f"{point[0]:.6f}", f"{point[1]:.6f}"
                row["source"] = "kima"
                rows.append(row)
                continue

        if row["wikidata_qid"]:
            needs_wikidata.append(row)
        rows.append(row)

    if needs_wikidata:
        print(f"Kima had no point for {len(needs_wikidata)}; asking Wikidata…")
        points = wikidata_points([r["wikidata_qid"] for r in needs_wikidata])
        for row in needs_wikidata:
            point = points.get(row["wikidata_qid"])
            if point:
                row["lat"], row["lon"] = f"{point[0]:.6f}", f"{point[1]:.6f}"
                row["source"] = "wikidata"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    placed = [r for r in rows if r["lat"]]
    records_placed = sum(int(r["n_records"] or 0) for r in placed)
    records_all = sum(int(r["n_records"] or 0) for r in rows)
    print(f"Wrote {OUTPUT}")
    print(f"  {len(placed)} of {len(rows)} reviewed City values placed")
    print(f"  {records_placed:,} of {records_all:,} records in the reviewed queue can be mapped")
    unplaced = [r for r in rows if not r["lat"] and r["decision"] == "matched"]
    if unplaced:
        print(f"  matched but unplaced: {', '.join(r['city'] for r in unplaced)}")


if __name__ == "__main__":
    main()
