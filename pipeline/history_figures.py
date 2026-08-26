#!/usr/bin/env python3
"""Recompute every register figure that appears in paper/hospital-history.html.

The paper is gitignored and local-only; this script is the committed record of
how its numbers were derived, so the next recompute is arithmetic and not
archaeology. It prints the tables and emits the two inline SVG charts (§12 bars,
§13 lines) with real coordinates, ready to paste over the ones in the HTML.

    python3 pipeline/history_figures.py            # tables to stdout
    python3 pipeline/history_figures.py --svg bars # just the §12 bar chart
    python3 pipeline/history_figures.py --svg line # just the §13 line chart

Three method decisions are baked in here deliberately. Change them only with a
reason, because they are what makes the output match the prose.

1. QUOTE_NONE. The TSV has unbalanced quote characters in free-text cells
   (Diagnosis as written, Address). csv's default quoting silently swallows the
   line breaks inside them and merges rows: 29,726 instead of 29,879. The 153
   lost rows are not spread thinly — 149 of them are one contiguous stretch of
   Notebook 3 covering Sep-Dec 1932, which is enough on its own to turn 1932
   from a dip into a level year. Never read this file with default quoting.

2. Religion percentages use an M+C+J denominator, not "any recorded value".
   The 78 rows recorded as Bahai, Druze, Arab or unparseable are excluded from
   both numerator and denominator. 1948 is the test case that settles it: it has
   19 such rows and no row-count change, and the paper's 70.0/29.6/0.4 is
   reproduced only on the M+C+J basis (any-recorded gives 68.2/28.9/0.4). 1947,
   1937, 1936, 1935, 1934 and 1930 all agree independently.

3. Third-class percentage uses ALL rows with a recorded Class, without the
   religion restriction. Restricting it to M+C+J rows moves 1947 to 65.2%
   against the paper's 67% and fits worse everywhere. The two denominators are
   genuinely different, which is not elegant but is what the paper does.

Blank cells are always excluded from denominators rather than counted as a
category. Notebook 25 (the Atlit camp register, 965 rows, 1940) is excluded
throughout, as it is everywhere else in the project.
"""

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

TSV = Path(__file__).resolve().parent.parent / "data/public/hospital-registers-normalized.tsv"

ATLIT_NOTEBOOK = "25"
FIRST_YEAR, LAST_YEAR = 1930, 1948
MCJ = ("Muslim", "Christian", "Jewish")

# Notebook lists as printed in the coverage table; the register's own notebook
# numbering, not derived, because "3, ?" records a real uncertainty.
NOTEBOOKS = {
    1930: "1", 1931: "2", 1932: "3, ?", 1933: "3, 4, 5, 6, 7",
    1934: "7, 8, 9, 10", 1935: "11, 12", 1936: "13, 14, 15",
    1937: "15, 16, 17, 18", 1938: "18, 19, 20, 21", 1939: "21, 22, 23, 24",
    1940: "24", 1944: "27, 28, 29", 1946: "26, 28, 30", 1947: "31, 32",
    1948: "33",
}
MISSING_YEARS = (1941, 1942, 1943, 1945)

# project chart colour convention (app/colors.ts): fixed hue per value, so the
# same group is the same colour in every chart and in the prose about it.
COLOURS = {"Muslim": "#2e7d55", "Christian": "#c85a26", "Jewish": "#2f6db5"}


def load():
    """Every non-Atlit register row, read the one way that does not lose 153."""
    with TSV.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE))
    return [r for r in rows if (r["Notebook_Number"] or "").strip() != ATLIT_NOTEBOOK]


def ym(row):
    """(year, 'YYYY-MM') for a row inside the register's span, else (None, None)."""
    d = (row["Admission Date"] or "").strip()
    if len(d) >= 7 and d[:4].isdigit():
        y = int(d[:4])
        if FIRST_YEAR <= y <= LAST_YEAR:
            return y, d[:7]
    return None, None


def profile(rows):
    """The four percentages the paper quotes, on the denominators it uses."""
    rel = Counter((r["Religion"] or "").strip() for r in rows)
    rden = sum(rel[k] for k in MCJ)
    cls = Counter((r["Class"] or "").strip() for r in rows)
    cden = sum(n for k, n in cls.items() if k)
    pct = lambda n, d: 100.0 * n / d if d else float("nan")
    return {
        "n": len(rows),
        "muslim": pct(rel["Muslim"], rden),
        "christian": pct(rel["Christian"], rden),
        "jewish": pct(rel["Jewish"], rden),
        "third": pct(cls["3"], cden),
        "counts": rel,
    }


def by_year(rows):
    years, months, undated = defaultdict(list), defaultdict(set), []
    for r in rows:
        y, m = ym(r)
        if y is None:
            undated.append(r)
        else:
            years[y].append(r)
            months[y].add(m)
    return years, months, undated


def window(rows, *prefixes):
    """Rows whose admission month starts with any given 'YYYY' or 'YYYY-MM'."""
    out = []
    for r in rows:
        _, m = ym(r)
        if m and m.startswith(prefixes):
            out.append(r)
    return out


def per_month(rows):
    months = {m for _, m in map(ym, rows) if m}
    rel = Counter((r["Religion"] or "").strip() for r in rows)
    n = len(months)
    return {
        "months": n,
        "all": len(rows) / n,
        "Muslim": rel["Muslim"] / n,
        "Christian": rel["Christian"] / n,
        "Jewish": rel["Jewish"] / n,
        "jewish_share": 100.0 * rel["Jewish"] / sum(rel[k] for k in MCJ),
    }


# ---------------------------------------------------------------- reporting

def report(rows):
    years, months, undated = by_year(rows)
    dated = sum(len(v) for v in years.values())

    print(f"corpus (excl. Notebook {ATLIT_NOTEBOOK})   {len(rows):,}")
    print(f"  dated within {FIRST_YEAR}-{LAST_YEAR}      {dated:,}")
    print(f"  no readable admission date  {len(undated):,}"
          f"  (notebooks {', '.join(sorted(set(r['Notebook_Number'] for r in undated), key=int))})")
    print("\nThe masthead figure is the corpus count. The undated rows are real\n"
          "admissions with an unread date cell, so they belong in the total but in\n"
          "no year — which is why the coverage table sums to the smaller number.\n")

    print("§12 coverage and §13 long run")
    print(f"{'year':>5} {'mo':>3} {'admissions':>11} {'per mo':>7} "
          f"{'Muslim':>7} {'Christ':>7} {'Jewish':>7} {'3rd cl':>7}")
    for y in sorted(years):
        p = profile(years[y])
        mo = len(months[y])
        print(f"{y:>5} {mo:>3} {p['n']:>11,} {p['n']/mo:>7.0f} "
              f"{p['muslim']:>6.1f}% {p['christian']:>6.1f}% {p['jewish']:>6.1f}% "
              f"{p['third']:>6.0f}%")

    print("\n§12 across the 1933 break, per covered month")
    windows = [
        ("1930-1932", ("1930", "1931", "1932")),
        ("1933 Jan-Apr", tuple(f"1933-0{m}" for m in (1, 2, 3, 4))),
        ("1933 May-Jun", ("1933-05", "1933-06")),
        ("1933 Jul-Dec", ("1933-07", "1933-08", "1933-09", "1933-10", "1933-11", "1933-12")),
        ("1934", ("1934",)),
        ("1935", ("1935",)),
    ]
    stats = {}
    for label, pre in windows:
        w = per_month(window(rows, *pre))
        stats[label] = w
        print(f"{label:>14} {w['months']:>3}mo  all {w['all']:>5.0f}  "
              f"M {w['Muslim']:>4.0f}  C {w['Christian']:>4.0f}  J {w['Jewish']:>4.0f}  "
              f"Jewish share {w['jewish_share']:>4.1f}%")

    a, b = stats["1933 Jan-Apr"], stats["1933 Jul-Dec"]
    print(f"\n  Jul-Dec : Jan-Apr ratios — all {b['all']/a['all']:.1f}x  "
          f"Muslim {b['Muslim']/a['Muslim']:.1f}x  "
          f"Christian {b['Christian']/a['Christian']:.1f}x  "
          f"Jewish {b['Jewish']/a['Jewish']:.1f}x")
    mshare = lambda w: 100 * w["Muslim"] / (w["Muslim"] + w["Christian"] + w["Jewish"])
    print(f"  Muslim share {mshare(a):.1f}% -> {mshare(b):.1f}%")


# -------------------------------------------------------------------- charts
# Both charts are emitted as one line of SVG with hard-coded coordinates, to be
# pasted straight into the HTML. Geometry, axis labels and every data-t tooltip
# come out of the same numbers as the tables above, so they cannot drift apart.

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def bar_chart(rows):
    """§12: admissions per covered month, one bar per year, gaps labelled."""
    years, months, _ = by_year(rows)
    W, H = 760, 300
    left, right, top, base = 52, 742, 18, 248
    ymax, step = 500, 100

    span = sorted(set(years) | set(MISSING_YEARS))
    slot = (right - left) / len(span)
    bw = min(22.5, slot * 0.62)
    y_of = lambda v: base - (base - 26.0) * v / ymax
    cx = lambda i: left + slot * (i + 0.5)

    out = []
    for v in range(0, ymax + 1, step):
        yy = y_of(v)
        out.append(f'<line class="grid" x1="{left}" x2="{right}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
        out.append(f'<text class="axis" x="{left-9}" y="{yy+4:.1f}" text-anchor="end">{v}</text>')

    for i, y in enumerate(span):
        if y in MISSING_YEARS:
            x = cx(i)
            out.append(f'<text class="absent" x="{x:.1f}" y="232.0" text-anchor="middle" '
                       f'transform="rotate(-90 {x:.1f} 232.0)">no notebooks</text>')
            continue
        n, mo = len(years[y]), len(months[y])
        rate = n / mo
        yy = y_of(rate)
        out.append(
            f'<rect class="bar" x="{cx(i)-bw/2:.1f}" y="{yy:.1f}" width="{bw:.1f}" '
            f'height="{base-yy:.1f}" rx="3" data-t="{y}|{rate:.0f} admissions per covered month|'
            f'{n:,} admissions over {mo} covered months|notebooks {esc(NOTEBOOKS[y])}"/>')

    for i, y in enumerate(span):
        if y in (1930, 1933, 1935, 1938, 1940, 1944, 1946, 1948):
            out.append(f'<text class="axis" x="{cx(i):.1f}" y="266" text-anchor="middle">{y}</text>')

    # event rules sit on the left edge of the year they mark
    for y, label, ty in ((1933, "1933 · +50 beds, St. Luke’s", 35),
                         (1938, "Oct 1938 · Bat Galim, 220 beds", 53)):
        x = cx(span.index(y)) - bw / 2 - 3
        out.append(f'<line class="ev" x1="{x:.1f}" x2="{x:.1f}" y1="{top}" y2="{base}"/>')
        out.append(f'<text class="evt" x="{x+4:.1f}" y="{ty}">{label}</text>')

    alt = ("Admissions per covered month by year, 1930 to 1948. The rate roughly "
           "doubles from 1932 to 1933 and again after 1944.")
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{alt}">'
            + "".join(out) + "</svg>")


def line_chart(rows):
    """§13: admissions per covered month, one line per religion.

    Absolute rates, not shares — the shares live in the §13 table. Plotting the
    rate is what lets the reader see that every community grew in 1933 while the
    Jewish line still falls away later; a share chart would hide the first half
    of that. The lines are broken, not bridged, across 1941–43 and 1945: there
    are no notebooks, and a connecting segment would draw a trend through a hole
    in the record. Colour comes from the .m/.c/.j classes in the page's own CSS
    so light and dark mode both stay on the project convention.
    """
    years, months, _ = by_year(rows)
    W, H = 760, 320
    left, right, base, headroom = 52, 674, 268.0, 26.0
    ymax, step = 300, 100

    span = sorted(years)
    slot = (right - left) / (len(span) - 1)
    y_of = lambda v: base - (base - headroom) * v / ymax
    cx = lambda i: left + slot * i

    out = []
    for v in range(0, ymax + 1, step):
        yy = y_of(v)
        out.append(f'<line class="grid" x1="{left}" x2="{right}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
        out.append(f'<text class="axis" x="{left-9}" y="{yy+4:.1f}" text-anchor="end">{v}</text>')

    for i, y in enumerate(span):
        if y in (1930, 1933, 1935, 1938, 1940, 1944, 1946, 1948):
            out.append(f'<text class="axis" x="{cx(i):.1f}" y="286" text-anchor="middle">{y}</text>')

    # contiguous runs of years, so the war gap breaks the path instead of
    # spanning it: 1930-1940, then 1944, then 1946-1948
    runs, cur = [], []
    for i, y in enumerate(span):
        if cur and y - span[i - 1] > 1:
            runs.append(cur)
            cur = []
        cur.append(i)
    runs.append(cur)

    cls = {"Muslim": "m", "Christian": "c", "Jewish": "j"}
    last = {}
    for name in MCJ:
        rate, count = {}, {}
        for i, y in enumerate(span):
            n = Counter((r["Religion"] or "").strip() for r in years[y])[name]
            count[i] = n
            rate[i] = n / len(months[y])

        for run in runs:
            if len(run) < 2:
                continue  # a lone year (1944) gets its dot, but no path
            d = "M" + " L".join(f"{cx(i):.1f},{y_of(rate[i]):.1f}" for i in run)
            out.append(f'<path class="ln {cls[name]}" d="{d}"/>')

        for i, y in enumerate(span):
            out.append(
                f'<circle class="pt {cls[name]}" cx="{cx(i):.1f}" cy="{y_of(rate[i]):.1f}" '
                f'r="4.5" data-t="{name} · {y}|{rate[i]:.0f} admissions per covered month|'
                f'{count[i]} admissions over {len(months[y])} months"/>')
        last[name] = y_of(rate[len(span) - 1])

    # direct labels at the right-hand end, nudged apart where lines converge
    for name in MCJ:
        out.append(f'<text class="dl {cls[name]}" x="{right+ 10 - 0.0:.1f}" '
                   f'y="{last[name] + 4:.1f}">{name}</text>')

    alt = ("Admissions per covered month by religion, 1930 to 1948. All three "
           "rise together in 1933; the Jewish line falls away from 1936 while "
           "Muslim and Christian continue upward.")
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{alt}">'
            + "".join(out) + "</svg>")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--svg", choices=("bars", "line"), help="emit one chart and nothing else")
    args = ap.parse_args()

    rows = load()
    if args.svg == "bars":
        print(bar_chart(rows))
    elif args.svg == "line":
        print(line_chart(rows))
    else:
        report(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
