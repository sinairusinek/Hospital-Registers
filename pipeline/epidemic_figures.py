"""Three figures from the press-versus-register comparison, as SVG.

Draws, from data/newspapers/epidemic_concordance.tsv and the register:

  A  fig-a-lag.svg          how late the press was, one dot per report-day,
                            faceted by disease
  B  fig-b-coverage.svg     every register surge, filled if the press reported
                            it - 6 of 60
  C  fig-c-diphtheria-1947.svg  the anchor case in full: the register's
                            September-October wave, the press ticks arriving in
                            the third week of October, and the months the
                            register does not cover

Each figure is written twice: an .svg plate for print, and its numbers as a
.tsv beside it so a reader can check the drawing against the data. The same
element markup is reused by the accompanying HTML page, which swaps the
stylesheet for theme tokens; this file is the single place the geometry lives.

Colour follows the project convention (see app/colors.ts): the categorical
slots are the validated default set, slot 1 blue #2a78d6 for the register,
slot 2 orange #eb6834 for the press, and grey #dcdbd5 for what is absent or
unreported - an absence never reads as a residue. The blue/orange pair was run
through the palette validator in both modes and passes every gate (CVD ΔE 24.7
light / 26.8 dark against an ≥8 target).

Figure A is faceted rather than coloured by disease deliberately. Six hues on a
dot plot would breach the all-pairs cap that scatter forms carry, and the row
labels carry identity better than a legend would.

Run: python3 pipeline/epidemic_figures.py
"""

from __future__ import annotations

import collections
import csv
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from epidemic_register_match import GROUPS, load_register, surges  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS = os.path.join(ROOT, "data", "newspapers")
CONC = os.path.join(NEWS, "epidemic_concordance.tsv")
FIGS = os.path.join(NEWS, "figures")

WINDOW = 60      # days each side, as in the match stage
TRAIL, REFRACTORY, FLOOR = 30, 120, 3

# The stylesheet for the standalone plates. The HTML page substitutes its own
# with the same class names, so nothing below needs to know which it is.
PLATE_CSS = """
  .fig { font-family: 'Iowan Old Style', Palatino, Georgia, serif; }
  .surface { fill: #fcfcfb; }
  .ink     { fill: #0b0b0b; }
  .ink-2   { fill: #52514e; }
  .ink-3   { fill: #898781; }
  .rule    { stroke: #d9d8d2; stroke-width: 1; fill: none; }
  .rule-0  { stroke: #898781; stroke-width: 1; fill: none; }
  .reg     { fill: #2a78d6; }
  .reg-s   { stroke: #2a78d6; fill: none; }
  .press   { fill: #eb6834; }
  .absent  { fill: #dcdbd5; }
  .ring    { stroke: #fcfcfb; stroke-width: 1.5; }
  .on-reg  { fill: #ffffff; }
  .press-s { stroke: #eb6834; stroke-width: 2.5; }
"""


def esc(t: str) -> str:
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def text(x, y, s, cls="ink", size=12, anchor="start", weight=None):
    w = f' font-weight="{weight}"' if weight else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" font-size="{size}" '
            f'text-anchor="{anchor}"{w}>{esc(s)}</text>')


def svg(width, height, body, title, desc):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}" class="fig" role="img" '
            f'aria-labelledby="t d">\n<title id="t">{esc(title)}</title>'
            f'<desc id="d">{esc(desc)}</desc>\n<style>{PLATE_CSS}</style>\n'
            f'<rect width="{width}" height="{height}" class="surface"/>\n'
            f'{body}\n</svg>\n')


def write(name, width, height, body, title, desc, rows, header):
    with open(os.path.join(FIGS, name + ".svg"), "w") as f:
        f.write(svg(width, height, body, title, desc))
    with open(os.path.join(FIGS, name + ".tsv"), "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(header)
        w.writerows(rows)
    return body


# --------------------------------------------------------------------------
def figure_a(points):
    """Dot strip per disease, x = days between the surge and the report."""
    order = sorted(points, key=lambda d: -len(points[d]))
    L, R, TOP = 128, 62, 104
    W, ROW = 840, 66
    H = TOP + ROW * len(order) + 64
    lo, hi = -125, 125
    def X(v):
        return L + (v - lo) / (hi - lo) * (W - L - R)

    bottom = TOP + ROW * len(order) - 20
    b = [text(38, 32, "Figure A \u00b7 How late the press was", size=15, weight="600"),
         text(38, 52, "One dot per Haifa press report-day, positioned against the day "
              "the register\u2019s own surge began.", cls="ink-2", size=11.5),
         text(38, 68, "Strict set only: Haifa established by the item\u2019s own dateline "
              "or inside the window, no ambiguous term, register open.",
              cls="ink-3", size=10.5)]
    for v in range(-120, 121, 30):
        b.append(f'<line x1="{X(v):.1f}" y1="{TOP - 6}" x2="{X(v):.1f}" '
                 f'y2="{bottom}" class="{"rule-0" if v == 0 else "rule"}"/>')
        b.append(text(X(v), TOP - 12, ("0" if v == 0 else f"{v:+d}"),
                      cls="ink-2" if v == 0 else "ink-3", size=10.5, anchor="middle"))
    b.append(text(X(0), bottom + 20, "the surge begins", cls="ink-2",
                  size=10.5, anchor="middle"))
    b.append(text(X(-62), bottom + 40, "\u25c0  press ahead of the register",
                  cls="ink-3", size=10.5, anchor="middle"))
    b.append(text(X(66), bottom + 40, "press behind the register  \u25b6",
                  cls="ink-3", size=10.5, anchor="middle"))

    for i, dis in enumerate(order):
        y = TOP + ROW * i + 14
        vals = sorted(points[dis])
        med = vals[len(vals) // 2]
        b.append(text(L - 14, y + 2, dis, cls="ink", size=12.5, anchor="end"))
        b.append(text(L - 14, y + 17, f"n={len(vals)} \u00b7 median {med:+d}d",
                      cls="ink-3", size=10, anchor="end"))
        # beeswarm: a point drops to the next level when it would sit within
        # 10px of one already placed there, so near-equal dates stack instead
        # of grinding into crescents
        levels = []
        for v in vals:
            x = X(v)
            for k, occupied in enumerate(levels):
                if all(abs(x - o) >= 10 for o in occupied):
                    occupied.append(x)
                    break
            else:
                levels.append([x])
                k = len(levels) - 1
            dy = (0, -10, 10, -20, 20, -30, 30)[k % 7]
            b.append(f'<circle cx="{x:.1f}" cy="{y + dy:.1f}" r="4" '
                     f'class="reg ring"/>')
        if dis == "diphtheria":
            b.append(f'<circle cx="{X(36):.1f}" cy="{y:.1f}" r="8.5" class="reg-s" '
                     f'stroke-width="1.5"/>')
            b.append(text(X(36) - 22, y + 3,
                          "al-Difa\u2019, 21 Oct 1947 \u2014 the report this began from",
                          cls="ink-2", size=10.5, anchor="end"))
        if dis == "plague":
            b.append(text(X(-111) + 2, y + 34,
                          "the 1944 plague scare \u2014 the one time the press was first",
                          cls="ink-2", size=10.5))
    return W, H, "\n".join(b), order


# --------------------------------------------------------------------------
def figure_b(cover):
    order = [g for g in GROUPS if cover.get(g)]
    L, TOP, W, ROW, GAP = 128, 96, 800, 42, 27
    H = TOP + ROW * len(order) + 64
    b = [text(38, 32, "Figure B · What the press never mentioned", size=15,
              weight="600"),
         text(38, 52, "Every surge the register defines on its own, 1930–1948, "
              "in chronological order.", cls="ink-2", size=11.5),
         text(38, 68, "Filled where a Haifa press report falls within 60 days. "
              "Marks are counted, not placed on a time axis; the reported ones "
              "carry their date.", cls="ink-3", size=10.5)]
    tot = sum(len(v) for v in cover.values())
    rep = sum(1 for v in cover.values() for _, f in v if f)
    pass  # the headline number is placed with the legend, below
    for i, g in enumerate(order):
        y = TOP + ROW * i
        b.append(text(L - 12, y + 4, g, cls="ink", size=12, anchor="end"))
        n = len(cover[g]); r = sum(1 for _, f in cover[g] if f)
        for j, (date, flag) in enumerate(cover[g]):
            x = L + 10 + j * GAP
            b.append(f'<circle cx="{x}" cy="{y}" r="7" '
                     f'class="{"reg ring" if flag else "absent ring"}"/>')
            if flag:
                b.append(text(x, y - 13, str(date)[:7], cls="ink-2", size=9,
                              anchor="middle"))
        b.append(text(L + 10 + n * GAP + 4, y + 4, f"{r}/{n}", cls="ink-3",
                      size=10.5))
    yy = TOP + ROW * len(order) + 16
    b.append(f'<circle cx="{L + 10}" cy="{yy}" r="7" class="reg ring"/>')
    b.append(text(L + 24, yy + 4, "reported", cls="ink-2", size=11))
    b.append(f'<circle cx="{L + 110}" cy="{yy}" r="7" class="absent ring"/>')
    b.append(text(L + 124, yy + 4, "not reported", cls="ink-2", size=11))
    b.append(text(W - 20, yy + 8, f"{rep} of {tot}", cls="ink", size=19,
                  anchor="end", weight="600"))
    b.append(text(W - 20, yy + 26, "surges reached the Haifa press",
                  cls="ink-2", size=10.5, anchor="end"))
    return W, H, "\n".join(b), order


# --------------------------------------------------------------------------
def figure_c(monthly, open_months, press_days, surge_date):
    months = [f"1947-{m:02d}" for m in range(1, 13)]
    L, R, TOP, W = 92, 34, 110, 800
    NAMES = ("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec").split()
    PLOT, TICKS = 190, 46
    H = TOP + PLOT + TICKS + 104
    cw = (W - L - R) / 12
    peak = max(monthly.values() or [1])
    def X(m):  # month index -> left edge
        return L + months.index(m) * cw
    def XD(d):  # a date -> x, positioned inside its month
        i = months.index(d.strftime("%Y-%m"))
        days = (dt.date(1947, 12, 31) if i == 11 else
                dt.date(1947, i + 2, 1) - dt.timedelta(days=1)).day
        return L + (i + (d.day - 0.5) / days) * cw

    b = [text(38, 32, "Figure C · Diphtheria in Haifa, 1947", size=15,
              weight="600"),
         text(38, 52, "The register’s admissions month by month, the press "
              "report-days beneath, and the months the register does not cover.",
              cls="ink-2", size=11.5),
         text(38, 68, "Press ticks include the weaker paragraph tier, so the months "
              "the register cannot cover are not left artificially empty.",
              cls="ink-3", size=10.5)]
    base = TOP + PLOT
    for m in months:
        x = X(m)
        if m not in open_months:
            b.append(f'<rect x="{x:.1f}" y="{TOP - 10}" width="{cw:.1f}" '
                     f'height="{PLOT + TICKS + 12}" class="absent" opacity="0.55"/>')
        b.append(text(x + cw / 2, base + 17, NAMES[months.index(m)], cls="ink-3",
                      size=10.5, anchor="middle"))
    b.append(f'<line x1="{L}" y1="{base}" x2="{W - R}" y2="{base}" class="rule-0"/>')
    sx = XD(surge_date)
    b.append(f'<line x1="{sx:.1f}" y1="{TOP - 18}" x2="{sx:.1f}" y2="{base}" '
             f'class="reg-s" stroke-width="1.5" stroke-dasharray="3 3"/>')
    b.append(text(sx - 10, TOP - 22, "the surge begins, 15 Sep", cls="ink-2",
                  size=10.5, anchor="end"))
    for m in months:
        n = monthly.get(m, 0)
        if not n:
            continue
        h = n / peak * (PLOT - 24)
        b.append(f'<rect x="{X(m) + 6:.1f}" y="{base - h:.1f}" '
                 f'width="{cw - 12:.1f}" height="{h:.1f}" class="reg" rx="4"/>')
        inside = h > 46
        b.append(text(X(m) + cw / 2, base - h + (20 if inside else -7), n,
                      cls="on-reg" if inside else "ink", size=11.5,
                      anchor="middle", weight="600" if inside else None))
    ty = base + 52
    for d in press_days:
        x = XD(d)
        b.append(f'<line x1="{x:.1f}" y1="{ty - 9}" x2="{x:.1f}" y2="{ty + 9}" '
                 f'class="press-s"/>')
    b.append(text(L - 10, ty + 4, "press", cls="press", size=11.5, anchor="end",
                  weight="600"))
    b.append(text(L - 10, TOP + 6, "register", cls="reg", size=11.5, anchor="end",
                  weight="600"))
    b.append(text(L, ty + 36,
                  "The paper speaks in October, five weeks in — and again in "
                  "August and November, where the register cannot answer.",
                  cls="ink-2", size=11))
    b.append(text(L, ty + 56, "Months shaded grey have no surviving register "
                  "pages; an empty month there is an absence of evidence, not of "
                  "disease.", cls="ink-3", size=10.5))
    return W, H, "\n".join(b), months


# --------------------------------------------------------------------------
def main() -> None:
    os.makedirs(FIGS, exist_ok=True)
    by, deaths, open_months = load_register()
    open_days = []
    for m in sorted(open_months):
        y, mo = int(m[:4]), int(m[5:])
        d = dt.date(y, mo, 1)
        while d.strftime("%Y-%m") == m:
            open_days.append(d)
            d += dt.timedelta(days=1)
    surge_by = {g: surges(by.get(g, {}), open_days, TRAIL, REFRACTORY, FLOOR)
                for g in GROUPS}

    rows = list(csv.DictReader(open(CONC, newline=""), delimiter="\t"))
    strict = [r for r in rows if r["haifa"] in ("dateline", "window")
              and not r["soft_term"] and r["reg_coverage"] == "open"]

    # A ------------------------------------------------------------------
    pts = {}
    for r in strict:
        if r["days_after_surge"] != "":
            pts[(r["disease"], r["date"])] = int(r["days_after_surge"])
    per = collections.defaultdict(list)
    for (dis, date), v in pts.items():
        per[dis].append(v)
    W, H, body, order = figure_a(per)
    write("fig-a-lag", W, H, body,
          "How late the press was",
          "Dot plot, one dot per Haifa press report-day, x is days between the "
          "register's surge onset and the report, faceted by disease.",
          sorted(((d, dd, v) for (d, dd), v in pts.items())),
          ["disease", "press_date", "days_after_surge"])

    # B ------------------------------------------------------------------
    cover = {}
    for g in GROUPS:
        if not surge_by[g]:
            continue
        cover[g] = [
            (s["date"], any(abs((dt.date.fromisoformat(r["date"]) - s["date"]).days)
                            <= WINDOW for r in strict if r["disease"] == g))
            for s in surge_by[g]]
    W, H, body, order = figure_b(cover)
    write("fig-b-coverage", W, H, body,
          "What the press never mentioned",
          "Dot matrix, one mark per register surge, filled where a Haifa press "
          "report falls within 60 days.",
          [(g, str(d), "reported" if f else "not reported")
           for g in cover for d, f in cover[g]],
          ["disease", "surge_onset", "press"])

    # C ------------------------------------------------------------------
    monthly = collections.Counter()
    for d, n in by["diphtheria"].items():
        if d.year == 1947:
            monthly[d.strftime("%Y-%m")] += n
    press_days = sorted({dt.date.fromisoformat(r["date"]) for r in rows
                         if r["disease"] == "diphtheria" and r["date"][:4] == "1947"
                         and r["haifa"] in ("dateline", "window", "paragraph")
                         and not r["soft_term"]})
    surge = next(s["date"] for s in surge_by["diphtheria"] if s["date"].year == 1947)
    W, H, body, months = figure_c(monthly, open_months, press_days, surge)
    write("fig-c-diphtheria-1947", W, H, body,
          "Diphtheria in Haifa, 1947",
          "Bar chart of monthly register admissions with press report-days as "
          "ticks beneath and uncovered months shaded.",
          [(m, monthly.get(m, 0), "open" if m in open_months else "absent",
            "|".join(str(d) for d in press_days if d.strftime("%Y-%m") == m))
           for m in months],
          ["month", "register_admissions", "register_coverage", "press_report_days"])

    print(f"3 figures + their data -> {FIGS}")
    for n in ("fig-a-lag", "fig-b-coverage", "fig-c-diphtheria-1947"):
        p = os.path.join(FIGS, n + ".svg")
        print(f"  {n}.svg  {os.path.getsize(p):,} bytes")


if __name__ == "__main__":
    main()
