"""The hospital among institutions: transfers in and out, for the buildings
dossier (§10). Imported by buildings_figures.py, which injects the figures.

PROVISIONAL. The register has no "transferred from" column, and the Result
and Remarks columns are being re-read off the scans (paper/prompt-full-reread.md).
Until then the counts below come from what the extraction transcribed, plus
the 68 "Transferred, no destination" rows read off the scans on 24 Oct 2026
(paper/inter-institutional/transferred-68-read.tsv). Rerun after the re-read
is applied; the to-do is paper/prompt-inter-institutional.md.

Every record is scanned for:
  out    - a destination in Result (as written, or the extraction's discarded
           values, where most destinations ended up);
  in     - custody or residence at another institution (prison, the Athlit
           clearance camp, the lazaret, the reformatory, a military unit), or
           "sent by"/"sent for observation";
  notify - "M.L. case sent to Central Police Station" (1938 only).
"""
from __future__ import annotations

import ast
import csv
import html
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "data/public/hospital-registers-normalized.tsv"
SOURCE = ROOT / "data/public/hospital-registers-2025-08-10.tsv"
READ68 = ROOT / "paper/inter-institutional/transferred-68-read.tsv"
PAGES = ROOT / "data/public/iiif-pages.tsv"
ATLIT = "25"
YEARS = list(range(1930, 1949))
MISSING_YEARS = {1941, 1942, 1943, 1945}
csv.field_size_limit(sys.maxsize)

# Destinations, most specific first: (node, label, regex on the lower-cased text)
OUT_RULES = [
    ("sarafand", "Sarafand Military Hospital", r"sarafand"),
    ("military", "42 General Hospital", r"42 ?gen"),
    ("military", "Military Reception Station", r"recep.{0,4}tion st|recep\?tion"),
    ("military", "military hospital, not named", r"mil(itary|\.)? ?hosp|military hosptl|for convalesc"),
    ("jerusalem", "Government Hospital / St John Ophthalmic, Jerusalem",
     r"jerusalem|j'?lm|\bjl\?|j'r\b|govt hosp j|j\.l\. hosp|ophthalmic hosp|oph\. hosp|j'a\b"),
    ("acre", "Government Hospital, Acre", r"acre hosp"),
    ("acre", "Acre prison hospital", r"prison hosp"),
    ("acre", "civil prison", r"civil prison"),
    ("jaffa", "Government Hospital, Jaffa", r"jaffa hosp"),
    ("safad", "Hadassah, Safad", r"hadass?a.*safad"),
    ("safad", "Safad (hospital not named)", r"\bsafad\b"),
    ("hadassah", "Hadassah (town not written)", r"hadd?ass?ah?"),
    ("hadassah", "Rothschild Hospital", r"rothsch"),
    ("afula", "Kupat Holim hospital, Afula", r"kupat|affuleh|afula"),
    ("nazareth", "C.M.S. Hospital, Nazareth", r"c\.m\.s"),
    ("nazareth", "French Hospital, Nazareth", r"french hosp"),
    ("german", "German Hospital", r"german hosp"),
    ("beisan", "Medical Officer's clinic, Beisan", r"beisan m\.?o"),
    ("unplaced", "private hospital", r"private hosp"),
    ("unplaced", "nuns' institute", r"nuns"),
    ("unplaced", "Public Health Department", r"p\.h\.d"),
    ("unplaced", "another hospital, not named", r"another hosp"),
    ("unplaced", "specialist surgeon, not named", r"specialist"),
    ("abroad", "Lebanon", r"lebanon"),
    ("abroad", "England", r"england|u\.k\b|oronsay|orousay"),
    ("abroad", "Alexandria, Egypt", r"alex"),
    ("police", "arrested or deported", r"arrest|^deported"),
    ("lazaret", "quarantine / lazaret", r"sent to quarantine|sufficiently to quarantine|quarantined|to lazar"),
]
INTERNAL = re.compile(r"out ?pat|o\.p\.d|clinic|v\. ?d\b|dental|psychiatr|dr\b|\bm\.s\b|new hosp|surgical ward|isolation", re.I)
HOME = re.compile(r"(removed|transferred|sent|advised) (to )?(his|her|the)? ?(home|house)|removed home|sent home", re.I)
NOTIFY = re.compile(r"case sent to|sent to .{0,15}police|sent to rural division", re.I)
TRANSF = re.compile(r"\btransf|\bremov(e|')d (to|b\.o)|\breferr?e?d\b|\bsent\b|arrest|deport|quarant|left for|shipped|transported", re.I)
NOISE = re.compile(r"trans-?\.? ?jord|transverse|transien|transit|transp\.?$|dept\. of trans|sent by|sent (in )?for ob", re.I)

# The map: node -> (label, x, y, kind). x/y in a 1000 x 640 viewBox.
NODES = {
    "gh":        ("Government Hospital, Haifa", 430, 310, "self"),
    "lazaret":   ("Quarantine & lazaret", 290, 240, "haifa"),
    "military":  ("Military hospitals, Haifa", 330, 430, "haifa"),
    "german":    ("German & Italian hospitals", 440, 200, "haifa"),
    "hadassah":  ("Hadassah · Rothschild", 590, 255, "haifa"),
    "hprison":   ("Haifa prison", 545, 385, "haifa"),
    "police":    ("Police", 480, 440, "haifa"),
    "acre":      ("Acre", 560, 85, "town"),
    "safad":     ("Safad", 800, 70, "town"),
    "tiberias":  ("Tiberias", 905, 175, "town"),
    "nazareth":  ("Nazareth", 755, 250, "town"),
    "afula":     ("Afula", 790, 345, "town"),
    "beisan":    ("Beisan", 920, 340, "town"),
    "atlit":     ("Atlit", 290, 540, "town"),
    "jaffa":     ("Jaffa", 380, 600, "town"),
    "sarafand":  ("Sarafand", 510, 600, "town"),
    "jerusalem": ("Jerusalem", 680, 600, "town"),
    "abroad":    ("Abroad", 40, 70, "edge"),
    "forces":    ("British forces (units)", 40, 250, "edge"),
    "prison?":   ("Prison, not named", 40, 350, "edge"),
    "unplaced":  ("Other, not placed", 40, 520, "edge"),
}
# Relations attested only outside the register (press, Mandate reports).
PRESS_ONLY = {
    ("tiberias", "in"): "Mandate report 1931: an ambulance service brings Tiberias and Acre cases to Haifa",
    ("acre", "in"): "Mandate report 1931; Acre Government Hospital closed 1933",
    ("german", "out"): "6 July 1938: 6 wounded to the German, 12 to the Italian hospital (Filastin)",
    ("hadassah", "in"): "from Hadassah 1930, 1935; from Rothschild with measles 1944 (press)",
    ("lazaret", "in"): "immigrant ships 1939: the sick to the hospital, the rest to the quarantine station",
    ("atlit", "out"): "1946–47: immigrants examined at the hospital, then sent on to the Atlit camp",
    ("afula", "in"): "1947: plague patients transferred from Afula (Haaretz)",
    ("sarafand", "in"): None,
}


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE))


def segments(r: dict, raw: dict) -> list[str]:
    x = raw.get(r["Index"], {})
    try:
        dv = [str(d) for d in ast.literal_eval(x.get("discarded_values") or "[]")]
    except (ValueError, SyntaxError):
        dv = [x.get("discarded_values", "")]
    dx = [r["Diagnosis as written"]] if re.search(r"sent to|transferr?ed to", r["Diagnosis as written"], re.I) else []
    return [s for s in [r["Result as written"], x.get("Original Result", "")] + dv + dx if s]


def destination(text: str):
    low = text.lower()
    for node, label, rx in OUT_RULES:
        if re.search(rx, low):
            return node, label
    return None


def inbound(r: dict, txt: str) -> list[tuple[str, str, str]]:
    """(lane, node, label) for custody or residence at another institution."""
    a, o = r["Address"].lower(), r["Occupation"].lower()
    w = (r["Ward"] + " " + r["Ward as written"]).lower()
    low = txt.lower()
    out = []
    if r["Address institution"] == "Prison" or "prisoner" in o or "prison" in w or "prisoner" in low:
        if "acre" in a or "acre" in low:
            out.append(("prison", "acre", "Acre Central Prison"))
        elif "athlit" in a or "atlit" in a:
            out.append(("prison", "atlit", "Athlit prison"))
        elif "haifa" in a:
            out.append(("prison", "hprison", "Haifa prison"))
        else:
            out.append(("prison", "prison?", "prison, not named"))
    if re.search(r"clearance camp|camp a?th?lit|athlit camp|transit camp", a + " " + low):
        out.append(("camp", "atlit", "Athlit clearance camp"))
    elif re.search(r"^(quarantine )?lazaret|quarantine lazaret|^quarantine haifa$", a.strip(" .")):
        out.append(("quarantine", "lazaret", "quarantine / lazaret"))
    if re.search(r"reformatory|soolahyeh|isslahyeh|islahiy", a + " " + low):
        out.append(("reformatory", "acre", "Reformatory School, Acre"))
    if r["Address institution"] in ("British Army", "Royal Navy", "Royal Air Force", "Transjordan Frontier Force"):
        out.append(("forces", "forces", r["Address institution"]))
    if re.search(r"sent (in )?for ob", low):
        out.append(("observation", "unplaced", "sent for observation"))
    if re.search(r"sent by hadassah", low):
        out.append(("sentby", "hadassah", "sent by Hadassah"))
    if re.search(r"d\.h\.o|sent by g\. office|sent by municipality", low):
        out.append(("sentby", "unplaced", "sent by a health office or the municipality"))
    return out


def compute() -> dict:
    rows = [r for r in read_tsv(REGISTER)
            if r["Notebook_Number"].strip() != ATLIT and "not-an-admission" not in (r["Review Flags"] or "")]
    raw = {r["Index"]: r for r in read_tsv(SOURCE)} if SOURCE.exists() else {}
    read68 = {r["Index"]: r for r in read_tsv(READ68)} if READ68.exists() else {}
    links = []          # dicts: dir, lane, node, label, year, nb, page, serial, evidence
    unknown = []        # "Transferred" with no destination anywhere
    read_fixed = Counter()
    for r in rows:
        segs = segments(r, raw)
        txt = " ¦ ".join(segs)
        year = r["Admission Date"][:4]
        base = {"year": int(year) if year.isdigit() else None, "nb": r["Notebook_Number"],
                "page": r["Page_Number"], "serial": r["Notebook Record ID"], "Index": r["Index"]}
        got = set()
        for s in segs:
            low = s.lower()
            if not TRANSF.search(low) or NOISE.search(low):
                continue
            if NOTIFY.search(low):
                got.add(("notify", "notify", "police", "police notified")); continue
            if HOME.search(low):
                continue
            d = destination(s)
            if d:
                got.add(("out", "out", *d))
        if r["Index"] in read68:
            # the scan reading replaces the extraction's Result for this row
            rd = read68[r["Index"]]
            got = {g for g in got if g[0] != "out"}
            text = " ".join([rd["destination"], rd["result_as_written"], rd["remarks_as_written"]])
            d = destination(rd["destination"] or text)
            if d:
                got.add(("out", "out", *d)); read_fixed["destination"] += 1
            elif rd["confidence"] == "notfound":
                read_fixed["notfound"] += 1
                unknown.append(base)
            else:
                read_fixed["not a transfer out"] += 1
        elif ("Transferred" in r["Result"] and not any(g[0] == "out" for g in got)
              and not any(INTERNAL.search(x) or HOME.search(x) for x in segs)):
            unknown.append(base)
        for lane, node, label in inbound(r, txt):
            got.add(("in", lane, node, label))
        for d, lane, node, label in got:
            links.append({**base, "dir": d, "lane": lane, "node": node, "label": label,
                          "evidence": txt[:160]})
    return {"links": links, "unknown": unknown, "read68": dict(read_fixed),
            "pages": {(p["Notebook_Number"], p["Page_Number"]): p["image_service"] for p in read_tsv(PAGES)}}


# Lanes of the yearly chart: (key, label, predicate on a link)
OUT_LANE = {
    "sarafand": "military", "military": "military",
    "jerusalem": "govhosp", "acre": "govhosp", "jaffa": "govhosp", "beisan": "govhosp",
    "safad": "jewish", "hadassah": "jewish", "afula": "jewish",
    "nazareth": "mission", "german": "mission", "unplaced": "mission",
    "abroad": "abroad", "police": "custody", "lazaret": "custody",
}
LANES = [
    ("in", "prison", "Prisoners (Acre, Haifa, Athlit prisons)"),
    ("in", "forces", "Soldiers, sailors, airmen (units)"),
    ("in", "camp", "Athlit clearance camp"),
    ("in", "quarantine", "Quarantine / lazaret"),
    ("in", "reformatory", "Reformatory School, Acre"),
    ("in", "observation", "“Sent for observation”"),
    ("out", "military", "→ military hospitals"),
    ("out", "govhosp", "→ other government hospitals & clinics"),
    ("out", "jewish", "→ Hadassah, Rothschild, Kupat Holim"),
    ("out", "mission", "→ mission, German & private hospitals"),
    ("out", "abroad", "→ abroad"),
    ("out", "custody", "→ police custody, deportation, quarantine"),
    ("notify", "notify", "Police notified of a wound"),
]


def lane_of(l: dict) -> tuple[str, str]:
    if l["dir"] == "out":
        return "out", OUT_LANE.get(l["node"], "mission")
    return l["dir"], l["lane"]


def summarise(fig: dict) -> dict:
    links = fig["links"]
    by_lane = defaultdict(Counter)
    for l in links:
        if l["year"]:
            by_lane[lane_of(l)][l["year"]] += 1
    edges = defaultdict(lambda: {"n": 0, "labels": Counter()})
    for l in links:
        if l["dir"] in ("in", "out") and l["lane"] not in ("observation", "sentby"):
            e = edges[(l["node"], l["dir"])]
            e["n"] += 1
            e["labels"][l["label"]] += 1
    out_tab = defaultdict(list)
    for l in links:
        if l["dir"] == "out":
            out_tab[l["label"]].append(l)
    return {"by_lane": by_lane, "edges": edges, "out_tab": out_tab,
            "records": len({l["Index"] for l in links}),
            "unknown": len(fig["unknown"]),
            "n_out": sum(1 for l in links if l["dir"] == "out"),
            "n_in": sum(1 for l in links if l["dir"] == "in"),
            "n_notify": sum(1 for l in links if l["dir"] == "notify"),
            "n_prison": sum(1 for l in links if l["lane"] == "prison"),
            "n_forces": sum(1 for l in links if l["lane"] == "forces"),
            "n_camp": sum(1 for l in links if l["lane"] == "camp"),
            "n_military_out": sum(1 for l in links if l["dir"] == "out" and OUT_LANE.get(l["node"]) == "military"),
            "n_jewish_out": sum(1 for l in links if l["dir"] == "out" and OUT_LANE.get(l["node"]) == "jewish"),
            "read68": fig["read68"]}


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def svg_map(s: dict) -> str:
    edges = s["edges"]
    gx, gy = NODES["gh"][1], NODES["gh"][2]
    out = ['<svg viewBox="0 0 1000 650" role="img" aria-label="Schematic map of patient movements between the Government Hospital and other institutions, 1930 to 1948. Arrow width is the number of register records.">',
           '<defs><marker id="ah-out" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" class="ia-out-h"/></marker>'
           '<marker id="ah-in" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" class="ia-in-h"/></marker></defs>',
           '<rect x="210" y="150" width="420" height="330" rx="18" class="ia-haifa"/>',
           '<text x="222" y="170" class="axis">HAIFA</text>',
           '<text x="20" y="24" class="axis">NOT PLACED</text>',
           '<line x1="20" y1="32" x2="20" y2="560" class="grid"/>']
    width = lambda n: 1.2 + 3 * math.log10(1 + n)
    for node, (label, x, y, kind) in NODES.items():
        if node == "gh":
            continue
        dx, dy = gx - x, gy - y
        L = math.hypot(dx, dy) or 1
        ux, uy = dx / L, dy / L
        px, py = -uy, ux
        r0, r1 = 14, 46          # gap at the node, gap at the hospital
        for d, off in (("in", 4.5), ("out", -4.5)):
            e = edges.get((node, d))
            press = PRESS_ONLY.get((node, d))
            if not e and not press:
                continue
            ax, ay = x + ux * r0 + px * off, y + uy * r0 + py * off
            bx, by = gx - ux * r1 + px * off, gy - uy * r1 + py * off
            if d == "out":
                ax, ay, bx, by = bx, by, ax, ay
            if e:
                parts = "|".join(f"{k}: {v}" for k, v in e["labels"].most_common())
                head = (f"{label} → Government Hospital" if d == "in" else f"Government Hospital → {label}")
                tip = f"{head} · {e['n']} records|{parts}" + (f"|press also: {press}" if press else "")
                out.append(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" class="ia-{d}" '
                           f'stroke-width="{width(e["n"]):.1f}" marker-end="url(#ah-{d})" data-t="{esc(tip)}"/>')
                lx, ly = (x + ux * 30 + px * off * 2.6, y + uy * 30 + py * off * 2.6)
                out.append(f'<text x="{lx:.1f}" y="{ly + 3:.1f}" class="ia-n ia-n-{d}" text-anchor="middle">{e["n"]}</text>')
            else:
                head = (f"{label} → Government Hospital" if d == "in" else f"Government Hospital → {label}")
                out.append(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" class="ia-{d} ia-press" '
                           f'marker-end="url(#ah-{d})" data-t="{esc(head + " · press / reports only|" + press)}"/>')
    for node, (label, x, y, kind) in NODES.items():
        if node == "gh":
            out.append(f'<rect x="{x - 78}" y="{y - 22}" width="156" height="44" rx="4" class="ia-self"/>'
                       f'<text x="{x}" y="{y - 3}" class="ia-sl" text-anchor="middle">Government</text>'
                       f'<text x="{x}" y="{y + 12}" class="ia-sl" text-anchor="middle">Hospital</text>')
            continue
        tot = [edges.get((node, d), {"n": 0})["n"] for d in ("in", "out")]
        inst = Counter()
        for d in ("in", "out"):
            if (node, d) in edges:
                for k, v in edges[(node, d)]["labels"].items():
                    inst[f"{'from' if d == 'in' else 'to'} {k}"] += v
        tip = f"{label}|" + "|".join(f"{k}: {v}" for k, v in inst.most_common()) if inst else f"{label}|press / reports only"
        cls = "ia-node" + (" ia-edge" if kind == "edge" else "")
        out.append(f'<g data-t="{esc(tip)}"><circle cx="{x}" cy="{y}" r="7" class="{cls}"/>')
        anchor, tx = ("start", x + 12) if kind == "edge" or x < gx - 150 else (("end", x - 12) if x < gx else ("start", x + 12))
        if kind == "haifa":
            ty = y + 21 if y > gy else y - 13
            out.append(f'<text x="{x}" y="{ty}" class="ia-l" text-anchor="middle">{esc(label)}</text></g>')
        elif kind == "edge":
            out.append(f'<text x="{x - 8}" y="{y - 13}" class="ia-l" text-anchor="start">{esc(label)}</text></g>')
        else:
            out.append(f'<text x="{tx}" y="{y + 4}" class="ia-l" text-anchor="{anchor}">{esc(label)}</text></g>')
    out.append('</svg>')
    return "\n".join(out)


def svg_lanes(s: dict) -> str:
    by = s["by_lane"]
    X0, X1, top, rowh = 300, 985, 92, 22
    span = YEARS[-1] + 1 - YEARS[0]
    X = lambda y: X0 + (y - YEARS[0]) / span * (X1 - X0)
    H = top + rowh * len(LANES) + 26
    vmax = max((v for c in by.values() for v in c.values()), default=1)
    out = [f'<svg viewBox="0 0 1000 {H}" role="img" aria-label="Relations with other institutions by year, 1930 to 1948: one lane per kind of relation, circle area proportional to the number of records.">']
    for y in MISSING_YEARS:
        out.append(f'<rect class="gapband" x="{X(y):.1f}" y="{top - 8}" width="{X(y + 1) - X(y):.1f}" height="{rowh * len(LANES) + 4}"/>')
    out.append(f'<rect class="ia-old" x="{X0}" y="{top - 8}" width="{X(1938.83) - X0:.1f}" height="4"/>'
               f'<text x="{X0}" y="{top - 13}" class="absent">MOUNTAIN ROAD</text>'
               f'<text x="{X(1938.9):.1f}" y="{top - 13}" class="absent">BAT GALIM</text>')
    events = [(1938.51, "6 Jul 1938 overflow"), (1939.28, "Apr 1939 scarlet fever"), (1940.08, "Jan–Feb 1940 Atlit"),
              (1947.74, "Sep 1947 bomb"), (1947.99, "Dec 1947 Jewish patients out"), (1948.34, "May 1948 boat to Acre")]
    for i, (t, lab) in enumerate(events):
        x = X(t)
        ly = 16 + (i if i < 3 else (2, 0, 1)[i - 3]) * 14
        anchor, tx = ("end", x - 3) if t > 1946 else ("start", x + 3)
        out.append(f'<line class="ev" x1="{x:.1f}" y1="{ly + 3}" x2="{x:.1f}" y2="{top + rowh * len(LANES) - 6}"/>'
                   f'<text class="evt" x="{tx:.1f}" y="{ly}" text-anchor="{anchor}">{esc(lab)}</text>')
    prev = None
    for i, (d, key, label) in enumerate(LANES):
        cy = top + i * rowh + rowh / 2 - 4
        if prev and prev != d:
            out.append(f'<line class="grid" x1="8" x2="{X1}" y1="{cy - rowh / 2:.1f}" y2="{cy - rowh / 2:.1f}"/>')
        prev = d
        c = by.get((d, key), Counter())
        out.append(f'<text x="290" y="{cy + 4:.1f}" class="hl" text-anchor="end">{esc(label)}</text>'
                   f'<text x="8" y="{cy + 4:.1f}" class="axis">{"IN" if d == "in" else ("OUT" if d == "out" else "")}</text>')
        out.append(f'<line class="hrule" x1="{X0}" x2="{X1}" y1="{cy:.1f}" y2="{cy:.1f}"/>')
        for y, n in sorted(c.items()):
            r = 1.6 + 8.4 * math.sqrt(n / vmax)
            out.append(f'<circle cx="{X(y + .5):.1f}" cy="{cy:.1f}" r="{r:.1f}" class="ia-dot ia-dot-{d}" '
                       f'data-t="{esc(label)} · {y}|{n} records"/>')
        out.append(f'<text x="{X1 + 2}" y="{cy + 4:.1f}" class="axis" text-anchor="end"></text>')
    yb = top + rowh * len(LANES) + 8
    for y in YEARS:
        if y % 2 == 0:
            out.append(f'<text x="{X(y + .5):.1f}" y="{yb + 8}" class="axis" text-anchor="middle">{y}</text>')
    out.append('</svg>')
    return "\n".join(out)


def table_out(fig: dict, s: dict) -> str:
    pages = fig["pages"]
    h = ['<div class="tw"><table><caption>Sent elsewhere, destination written · records</caption>'
         '<thead><tr><th>destination</th><th class="n">records</th><th>years</th><th>pages (scan)</th></tr></thead><tbody>']
    for label, ls in sorted(s["out_tab"].items(), key=lambda kv: -len(kv[1])):
        years = sorted({l["year"] for l in ls if l["year"]})
        yr = ", ".join(str(y) for y in years)
        links = []
        for l in sorted(ls, key=lambda l: (l["year"] or 0))[:4]:
            svc = pages.get((l["nb"], l["page"]))
            t = f"NB{l['nb']} p{l['page']}"
            links.append(f'<a href="{esc(svc)}/full/2000,/0/default.jpg" target="_blank" rel="noopener">{t}</a>' if svc else t)
        more = f" +{len(ls) - 4}" if len(ls) > 4 else ""
        h.append(f'<tr><td>{esc(label)}</td><td class="n">{len(ls)}</td><td class="nb">{yr}</td>'
                 f'<td class="nb">{", ".join(links)}{more}</td></tr>')
    h.append(f'<tr><td colspan="4" class="fn">Plus {s["unknown"]} written “Transferred” whose scan could not be fetched '
             f'(the library has no image for those pages). Of the 68 rows the extraction called “Transferred” without a destination, '
             f'the scans named one for {s["read68"].get("destination", 0)}; '
             f'{s["read68"].get("not a transfer out", 0)} were not transfers out at all (“In Plaster”, “I.S.Q.”, a referral inside the hospital).</td></tr>')
    h.append('</tbody></table></div>')
    return "".join(h)


def figures() -> tuple[dict, dict]:
    fig = compute()
    s = summarise(fig)
    parts = {"inst-map": svg_map(s), "inst-lanes": svg_lanes(s), "inst-out": table_out(fig, s)}
    nums = {"ia-records": f'{s["records"]:,}', "ia-prison": f'{s["n_prison"]:,}', "ia-forces": str(s["n_forces"]),
            "ia-camp": str(s["n_camp"]), "ia-out": str(s["n_out"]), "ia-military-out": str(s["n_military_out"]),
            "ia-jewish-out": str(s["n_jewish_out"]), "ia-notify": str(s["n_notify"]),
            "ia-read-dest": str(s["read68"].get("destination", 0)),
            "ia-read-not": str(s["read68"].get("not a transfer out", 0))}
    return parts, nums


if __name__ == "__main__":
    parts, nums = figures()
    print(nums)


# Sources the section cites that neither the dossier nor the history already
# carries. Items the history cites are looked up in its src-data block.
NLI = "https://www.nli.org.il/en/newspapers/?a=d&d="
SOURCES = {
    "mr-1931-ambulance": {
        "pub": "Report on the Administration of Palestine and Trans-Jordan, 1931 — Health",
        "place": "London", "date": "1931-12-31", "lang": "English", "kind": "archive",
        "id": "Mandate annual report 1931 · paper/sources/mandate-reports/t1931.txt",
        "orig": "There will be an increase of 50 in the bed-strength of the Haifa Hospital. Acre Hospital will then be closed down. An ambulance service will take to Haifa cases requiring hospital treatment from Tiberias and Acre.",
        "note": "<p>The plan that made Haifa the referral hospital of the Northern District. Acre's hospital is reported closed in the 1933 report.</p>"},
    "mr-1933-missions": {
        "pub": "Report on the Administration of Palestine and Trans-Jordan, 1933 — Health",
        "place": "London", "date": "1933-12-31", "lang": "English", "kind": "archive",
        "id": "Mandate annual report 1933 · paper/sources/mandate-reports/t1933.txt",
        "orig": "… the Edinburgh Mission Hospital at Nazareth fulfilled their functions admirably and dealt with the sick of those districts in which no Government hospitals exist. In the larger towns the Church Missionary Society, French, German and Italian hospitals, dealt with a considerable …",
        "note": "<p>The division of labour the government relied on: mission hospitals stood in for government ones where there were none.</p>"},
    "mr-1936-detention": {
        "pub": "Report on the Administration of Palestine and Trans-Jordan, 1936 — Health",
        "place": "London", "date": "1936-12-31", "lang": "English", "kind": "archive",
        "id": "Mandate annual report 1936 · paper/sources/mandate-reports/t1936.txt",
        "orig": "Sick-bays in these detention camps were equipped and staffed for the nursing and treatment of minor or chronic ailments. Cases of acute or serious illness were transferred to Government hospitals.",
        "note": "<p>The rule behind the register's prisoners: the camps and prisons kept minor cases and sent serious ones to the government hospital.</p>"},
    "falastin19380707-p1": {
        "pub": "Filastin", "place": "Jaffa", "date": "1938-07-07", "lang": "Arabic",
        "id": "Filastin, 7 July 1938, p. 1 · read in paper/press-register-cases.md",
        "url": NLI + "falastin19380707-01",
        "trans": "The wounded are put at seventy. A large part of them were placed in the Government Hospital, and when the hospital could no longer take them, six were sent to the German Hospital and twelve to the Italian.",
        "note": "<p>The day after the Haifa market bombing of 6 July 1938, the largest admission day in the register. The overflow went to the German and Italian hospitals; the register records only those it kept.</p>"},
    "pls19380726-01.2.9": {
        "pub": "The Palestine Post", "place": "Jerusalem", "date": "1938-07-26", "lang": "English",
        "url": NLI + "pls19380726-01.2.9",
        "orig": "The Government Hospital as well as the Italian and German Hospitals were soon crowded and were unable to admit all the injured.",
        "note": "<p>The second market explosion, 25 July 1938: the same three hospitals share the casualties.</p>"},
    "pls19380822-01.2.19": {
        "pub": "The Palestine Post", "place": "Jerusalem", "date": "1938-08-22", "lang": "English",
        "url": NLI + "pls19380822-01.2.19",
        "orig": "… continued to command his column although severely wounded, until taken to the Government Hospital at Haifa. He has since been transferred to the Military Hospital at Sarafand …",
        "note": "<p>A wounded British officer: first aid and first beds at the Government Hospital, then the military hospital. The register's soldiers follow the same path.</p>"},
    "pls19390608-01.2.1": {
        "pub": "The Palestine Post", "place": "Jerusalem", "date": "1939-06-08", "lang": "English",
        "url": NLI + "pls19390608-01.2.1",
        "orig": "All the refugees were transferred to the quarantine station at Haifa with the exception of one woman who was taken to Government Hospital.",
        "note": "<p>An immigrant schooner brought in at Nahariya: the sick to the hospital, the rest to the quarantine station. The sorting of ma'apilim (clandestine Jewish immigrants) between the two begins by 1939, not 1946.</p>"},
    "dav19381226-01.2.11": {
        "pub": "Davar", "place": "Tel Aviv", "date": "1938-12-26", "lang": "Hebrew",
        "url": NLI + "dav19381226-01.2.11", "id": "dav19381226-01.2.11 (OCR corrected)",
        "orig": "מכונית צבאית העבירה את הפצועים לבית החולים הממשלתי בבת גלים ומשם העבירום להדסה",
        "trans": "A military car took the wounded to the Government Hospital in Bat Galim, and from there they were moved to Hadassah.",
        "note": "<p>First treatment at the Government Hospital, then on to a Jewish hospital: the pattern behind the register's “Transferred to Hadassah”.</p>"},
    "hmf19460820-01.2.75": {
        "pub": "HaMashkif", "place": "Tel Aviv", "date": "1946-08-20", "lang": "Hebrew",
        "url": NLI + "hmf19460820-01.2.75",
        "orig": "הועבר אתמול מביה\"ח הממשלתי בחיפה לבית החולים שבבית הסוהר בעכו",
        "trans": "… was moved yesterday from the Government Hospital in Haifa to the hospital in the prison at Acre.",
        "note": "<p>A prisoner wounded in the attack on the railway workshops, moved to the Acre prison hospital once fit; the Palestine Post of 20 June 1946 has the reverse journey, Acre to Haifa.</p>"},
    "falastin19461205-01.1.2": {
        "pub": "Filastin", "place": "Jaffa", "date": "1946-12-05", "lang": "Arabic",
        "url": NLI + "falastin19461205-01.1.2",
        "orig": "الحكومة قد تستعمل المستشفى الالماني وتحوله لخدمة المدنيين بعد ان استعملته مدة الحرب وذلك لعدم استيعاب مستشفى الحكومة للمرضى من الجمهور وينتظر أن يبقى مستشفى الحكومة للحوادث والاصابات الطارئة وان يكون المستشفى الالمانى للأمراض الأخرى",
        "trans": "The Government may take over the German Hospital, used during the war, and turn it to civilian service, because the Government Hospital cannot absorb the patients of the public; the Government Hospital would be kept for accidents and emergencies and the German Hospital would take the other diseases.",
        "note": "<p>A planned division of labour between two Haifa hospitals. Whether it happened has not been checked.</p>"},
    "difaa19470418-01.1.1": {
        "pub": "al-Difaʿ", "place": "Jaffa", "date": "1947-04-18", "lang": "Arabic",
        "url": NLI + "difaa19470418-01.1.1",
        "orig": "وقد بلغ عدد المهربين الذين تم نقلهم الى قبرص ٢٥٥٢ مهربا وبقي ٦٤ مهربا في مستشفى عتليت و ۲۲ في مستشفى الحكومة بحيفا",
        "trans": "The number of smuggled immigrants transferred to Cyprus reached 2,552; 64 remained in the Atlit hospital and 22 in the Government Hospital in Haifa.",
        "note": "<p>The immigrant ship Guardian: the sorting of one ship's people between deportation, the camp hospital at Atlit and the Government Hospital, in numbers.</p>"},
}
