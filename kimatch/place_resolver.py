#!/usr/bin/env python3
"""Resolve a place string against the places this project has already ruled on.

The decisions table links exact City values. A spelling it has not seen —
"Im El Fahem" when "Um el Fahm" is ruled — stays unlinked however obvious
the reading. This module reads any string (a City value, or a piece of an
Address) against every spelling already matched, in three tiers:

  exact     the loose key (case, punctuation, el-/al- articles, "village",
            "S/D" qualifiers stripped) equals a ruled spelling's key
  skeleton  the consonant skeleton (Arabic romanization folded: q/k, ou/u,
            vowels and h dropped, doublings collapsed) equals that of
            spellings of exactly ONE place, and the loose keys are close
  alternation  "A|B" or "A / B" whose parts resolve to one place, or to Haifa
            and one of its quarters (the finer reading wins, as in round 1)

A string resolving to two places is ambiguous and is never decided here.
Used by kimatch/variant_pass.py (City values) and pipeline/build.py (an empty
City read from the Address).
"""
from __future__ import annotations

import csv
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECISIONS = ROOT / "kimatch" / "city-kima-decisions.tsv"

ARTICLES = {"el", "al", "il", "es", "ed", "et", "ez", "esh", "en", "er", "ul", "ad", "as", "an", "ar", "at", "az"}
QUALIFIERS = re.compile(
    r"\b(village|vill|vil|s\s*/\s*d(ist)?|sub[\s.-]*dist(rict)?|dist(rict)?|qada|area|town)\b\.?", re.IGNORECASE)
UMM = {"um", "umm", "im", "om", "oum"}


def loose_key(text: str) -> str:
    s = (text or "").lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = QUALIFIERS.sub(" ", s)
    s = re.sub(r"[’'`ʻʼ]", "", s)
    s = re.sub(r"\b([a-z])\.(?=[a-z]\.)", r"\1", s)   # "p.m.f." -> "pmf."
    tokens = [t for t in re.split(r"[^a-z]+", s) if t]
    tokens = ["um" if t in UMM else t for t in tokens if t not in ARTICLES]
    return "".join(tokens)


def _folded(key: str) -> str:
    return key.replace("ou", "u").replace("ee", "i").replace("q", "k").replace("c", "k")


def skeleton(key: str) -> str:
    if not key:
        return ""
    s = key.replace("ou", "u").replace("ee", "i").replace("oo", "u")
    s = s.replace("q", "k").replace("c", "k").replace("ph", "f")
    head = "V" if s[0] in "aeiouy" else s[0]
    body = re.sub(r"[aeiouyh]", "", s[1:])
    body = re.sub(r"(.)\1+", r"\1", body)
    return head + body


@lru_cache(maxsize=1)
def known() -> dict:
    """Ruled spellings, by loose key and by skeleton, with their place."""
    by_key: dict[str, dict[tuple[str, str], str]] = {}
    by_skel: dict[str, dict[tuple[str, str], str]] = {}
    haifa_quarters: set[tuple[str, str]] = set()
    with DECISIONS.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if r["decision"] != "matched" or not (r["kima_id"] or r["wikidata_qid"]):
                continue
            place = (r["kima_id"], r["wikidata_qid"] if not r["kima_id"] else "")
            k = loose_key(r["city"])
            if len(k) < 3:
                continue
            by_key.setdefault(k, {})[place] = r["city"]
            by_skel.setdefault(skeleton(k), {})[place] = r["city"]
            if "(Haifa," in (r.get("kima_name_rom") or ""):
                haifa_quarters.add(place)
    return {"key": by_key, "skel": by_skel, "haifa_quarters": haifa_quarters}


HAIFA = ("791", "")


def resolve(text: str, allow_skeleton: bool = True) -> tuple[str, str, str]:
    """-> (ruled spelling it resolves to, tier, note); empty if unresolved."""
    text = (text or "").strip()
    if not text:
        return "", "", ""
    if SECOND_CAMP.search(text):
        return "", "", ""
    parts = [p for p in re.split(r"\s*(?:\||\s/\s)\s*", text) if p.strip()]
    if len(parts) > 1:
        hits = [resolve(p, allow_skeleton) for p in parts]
        found = [h[0] for h in hits if h[0]]
        # Every reading must resolve — "Rummaneh / Jenin" is not Jenin just
        # because the village is unknown. A part that only repeats a resolved
        # town inside an institution ("P.M.F. Jenin", "Dept. of Police,
        # Tiberias") is not a second reading; "near Nazareth" is.
        for part, hit in zip(parts, hits):
            if hit[0]:
                continue
            if re.search(r"\bnear\b", part, re.IGNORECASE) or not any(_only_noise(part, s) for s in found):
                return "", "", ""
        places = {_place_of(s) for s in found}
        if len(places) == 1:
            spelling = next(h[0] for h in hits if h[0])
            return spelling, "alternation", "all readings resolve to one place"
        if len(places) == 2 and HAIFA in places:
            other = (places - {HAIFA}).pop()
            if other in known()["haifa_quarters"]:
                spelling = next(h[0] for h in hits if h[0] and _place_of(h[0]) == other)
                return spelling, "alternation", "Haifa and one of its quarters: the finer reading"
        return "", "", ""
    # A parenthesis may hold the finer place ("Nazareth (Iksal village)"):
    # it is only dropped when it names a known place itself or says nothing.
    paren = re.findall(r"\(([^)]*)\)", text)
    for inner in paren:
        bare = re.sub(r"\b(vicinity|\?)\b|\?", "", inner).strip()
        if bare and not resolve(bare, allow_skeleton)[0]:
            return "", "", ""
    k = loose_key(text)
    if len(k) < 3:
        return "", "", ""
    exact = known()["key"].get(k)
    if exact:
        if len(exact) == 1:
            return next(iter(exact.values())), "exact", ""
        return "", "", ""
    if not allow_skeleton:
        return "", "", ""
    sk = skeleton(k)
    cands = known()["skel"].get(sk)
    if not cands or len(cands) != 1:
        return "", "", ""
    spelling = next(iter(cands.values()))
    # Short skeletons have namesakes, so the shorter the skeleton the closer
    # the spellings must be: Arrabeh/Arraba passes, Bireh/Bineh would not.
    need = 0.7 if len(sk) >= 4 else 0.8 if len(sk) == 3 else 1.0
    if SequenceMatcher(None, _folded(k), _folded(loose_key(spelling))).ratio() < need:
        return "", "", ""
    return spelling, "skeleton", f"same consonant skeleton as {spelling!r}"


# Words that add an office, a qualifier or a camp number to a town without
# naming another place.
NOISE = {"police", "pp", "p", "dept", "department", "of", "survey", "camp", "prison", "co", "c", "o",
         "dho", "d", "h", "cmf", "pmf", "bsp", "s", "ol", "sfo", "pb", "nfd", "n", "no", "i", "ii",
         "trans", "jordan", "transjordan", "haifa", "sd", "dist", "district", "sub", "g", "deri", "station"}
# The second Bassa camp is the open Bassa/Shelomi question, not al-Bassa.
SECOND_CAMP = re.compile(r"\bno\.?\s*2\b|\bn\s*[:=.]?\s*2\b|\bII\b", re.IGNORECASE)


def _only_noise(part: str, spelling: str) -> bool:
    """True if `part` is `spelling` plus nothing but office words and qualifiers."""
    town = set(re.findall(r"[a-z]+", spelling.lower()))
    tokens = re.findall(r"[a-z]+", re.sub(r"\b([a-z])\.(?=[a-z]\.)", r"\1", part.lower()))
    if not town & set(tokens):
        return False
    rest = [t for t in tokens if t not in town and t not in NOISE and t not in ARTICLES]
    return not rest


@lru_cache(maxsize=None)
def _place_of(spelling: str) -> tuple[str, str]:
    for places in known()["key"].values():
        for place, s in places.items():
            if s == spelling:
                return place
    return ("", "")


STREETISH = re.compile(r"\b(st|str|street|rd|road|ave|avenue|lane|square|sq)\b\.?", re.IGNORECASE)
SEGMENTS = re.compile(r"\s*(?:[,;|/()]|\s[-–]\s|\.\s)\s*")


def place_in_address(address: str) -> tuple[str, str]:
    """The one ruled place an Address names, for a record with no City.

    Exact readings only (no skeleton guesses on what may be a person's name),
    never a street named for a town ("Nazareth St."), and nothing when the
    address names two places that do not nest. -> (ruled spelling, the piece
    of the address it was read from)."""
    found: dict[tuple[str, str], tuple[str, str]] = {}
    for seg in [address] + SEGMENTS.split(address or ""):
        seg = seg.strip(" .-")
        if len(seg) < 3 or STREETISH.search(seg):
            continue
        spelling, tier, _ = resolve(seg, allow_skeleton=False)
        if spelling:
            found.setdefault(_place_of(spelling), (spelling, seg))
    place = None
    if len(found) == 1:
        place = next(iter(found))
    elif len(found) == 2 and HAIFA in found:
        other = (set(found) - {HAIFA}).pop()
        if other in known()["haifa_quarters"]:
            place = other
    if place is None:
        return "", ""
    return canonical()[place], found[place][1]


@lru_cache(maxsize=1)
def canonical() -> dict[tuple[str, str], str]:
    """Place -> its commonest ruled spelling, the City an empty record is given."""
    best: dict[tuple[str, str], tuple[tuple, str]] = {}
    with DECISIONS.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if r["decision"] != "matched" or not (r["kima_id"] or r["wikidata_qid"]):
                continue
            place = (r["kima_id"], r["wikidata_qid"] if not r["kima_id"] else "")
            # A plain spelling over a compound one ("Jenin", not "Jenin|P.M.F.
            # Jenin"), then the commonest — round 1 counted Jewish records only,
            # so the count alone is not a fair vote.
            plain = not re.search(r"[|/()\[\]]|\bS/D", r["city"])
            gazetteer = re.sub(r"\s*\(.*\)$", "", r.get("kima_name_rom") or "")
            near = round(SequenceMatcher(None, loose_key(r["city"]), loose_key(gazetteer)).ratio(), 1) if gazetteer else 0
            rank = (plain, near, int(r["n_records"] or 0), -len(r["city"]))
            if place not in best or rank > best[place][0]:
                best[place] = (rank, r["city"])
    out = {p: c for p, (_, c) in best.items()}
    # Kima names al-Tira for its successor; the register's own word wins.
    out.update(CANONICAL_OVERRIDE)
    return out


CANONICAL_OVERRIDE = {("756", ""): "Tireh"}
