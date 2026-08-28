#!/usr/bin/env python3
"""Graphic chronology of the Haifa Government Hospital, 1929-1948.

Three registers of information, stacked on one time axis:

  * which building the institution occupied (the two bands at the foot);
  * how much of the admission register survives, year by year (the columns);
  * the dated events the press fixes, each one clickable through to the
    article that dates it (the flags above and below the axis).

Emits the <figure> block inserted into paper/hospital-history.html.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "paper" / "timeline.svg.html"

# Months of register surviving per year — the coverage table in §12.
COVERAGE = {
    1930: 7, 1931: 5, 1932: 4, 1933: 12, 1934: 12, 1935: 10, 1936: 11,
    1937: 12, 1938: 12, 1939: 10, 1940: 3, 1941: 0, 1942: 0, 1943: 0,
    1944: 10, 1945: 0, 1946: 5, 1947: 6, 1948: 4,
}

# (when, label, source key, above/below). The source key opens the drawer.
EVENTS = [
    ("1929-03", "St. Luke's closes", None, "up"),
    ("1932-10", "Government takes the building", None, "dn"),
    ("1935-09", "260 beds announced", "dhy19350912-01.2.71", "up"),
    ("1937-06", "Ground broken at Bat Galim", "dav19370618-01.2.93", "dn"),
    ("1938-09", "Construction completed", "haretz19381223-01.2.5", "up"),
    ("1938-10", "Wards occupied — NB20→NB21", "hbkr19381118-01.2.28", "dn"),
    ("1938-12", "Opened, 225 beds", "dav19381223-01.2.66", "up"),
    ("1940-03", "A death inside the gap", "mb19400308", "dn"),
    ("1942-06", "Plague department built", "haretz19450710-01.2.24", "up"),
    ("1944-06", "Plague outbreak begins", "haretz19441117-01.2.59", "dn"),
    ("1947-07", "Exodus deportees landed", "hzh19470720-01.2.2", "up"),
    ("1947-12", "Jewish staff walk out", "hmf19480126-01.2.34", "dn"),
    ("1948-05", "To the municipality", "haretz19480503-01.2.39", "up"),
]

Y0, Y1 = 1929, 1949
W = 1180
LEFT, RIGHT = 54, 22
PLOT = W - LEFT - RIGHT

CHAR = 6.35          # IBM Plex Mono advance at 10.5px, plus slack
LANE_UP, LANE_DN = 21, 20
BAR_MAX = 54

MOVE = 1938 + 9 / 12          # wards occupied, 31 October 1938
END = 1948 + 4 / 12           # handed over, 2 May 1948


def fyear(s):
    if "-" in s:
        y, m = s.split("-")
        return int(y) + (int(m) - 1) / 12
    return float(s)


def place(events, side):
    """Assign each flag a lane so no two labels on a lane overlap."""
    rows = []
    for when, label, src, _ in events:
        cx = LEFT + (fyear(when) - Y0) / (Y1 - Y0) * PLOT
        half = len(label) * CHAR / 2 + 10
        tx = min(max(cx, LEFT + half), W - RIGHT - half)
        lane = 0
        while any(
            lane == ln and not (tx + half < l or tx - half > r)
            for ln, l, r in rows
        ):
            lane += 1
        rows.append((lane, tx - half, tx + half))
        yield when, label, src, cx, tx, lane


def build():
    ups = [e for e in EVENTS if e[3] == "up"]
    dns = [e for e in EVENTS if e[3] == "dn"]
    up = list(place(ups, "up"))
    dn = list(place(dns, "dn"))

    n_up = max((l for *_, l in up), default=0) + 1
    n_dn = max((l for *_, l in dn), default=0) + 1

    top = 18 + n_up * LANE_UP          # baseline of the coverage columns
    axis = top + BAR_MAX
    yrs = axis + 17
    band_t = yrs + 12 + n_dn * LANE_DN
    band_b = band_t + 26
    height = band_b + 26

    def x(f):
        return LEFT + (f - Y0) / (Y1 - Y0) * PLOT

    o = ['<svg viewBox="0 0 %d %d" role="img" aria-label="Chronology of the '
         'Haifa Government Hospital, 1929 to 1948: the two buildings, the '
         'surviving register, and the dated events.">' % (W, height)]
    a = o.append

    # buildings
    a(f'<rect class="tl-band mr" x="{x(Y0):.1f}" y="{band_t}" '
      f'width="{x(MOVE)-x(Y0):.1f}" height="{band_b-band_t}" rx="2"/>')
    a(f'<rect class="tl-band bg" x="{x(MOVE):.1f}" y="{band_t}" '
      f'width="{x(END)-x(MOVE):.1f}" height="{band_b-band_t}" rx="2"/>')
    a(f'<text class="tl-cap" x="{(x(Y0)+x(MOVE))/2:.1f}" y="{band_b-9}" '
      f'text-anchor="middle">Mountain Road</text>')
    a(f'<text class="tl-cap" x="{(x(MOVE)+x(END))/2:.1f}" y="{band_b-9}" '
      f'text-anchor="middle">Bat Galim</text>')

    # coverage
    for y, m in COVERAGE.items():
        if not m:
            continue
        bh = m / 12 * BAR_MAX
        a(f'<rect class="tl-cov" x="{x(y)+1.2:.1f}" y="{axis-bh:.1f}" '
          f'width="{x(y+1)-x(y)-2.4:.1f}" height="{bh:.1f}" rx="1">'
          f'<title>{y}: {m} of 12 months survive</title></rect>')
    for lo, hi in ((1940 + 2 / 12, 1944), (1945, 1946)):
        a(f'<rect class="tl-gap" x="{x(lo):.1f}" y="{axis-BAR_MAX:.1f}" '
          f'width="{x(hi)-x(lo):.1f}" height="{BAR_MAX}" rx="1"/>')
    a(f'<text class="tl-lbl" x="{(x(1940+2/12)+x(1944))/2:.1f}" '
      f'y="{axis-BAR_MAX/2+4:.1f}" text-anchor="middle">no notebooks survive</text>')
    a(f'<line class="tl-gap-h" x1="{LEFT}" y1="{axis:.1f}" '
      f'x2="{W-RIGHT}" y2="{axis:.1f}"/>')

    # axis
    for y in range(Y0, Y1):
        a(f'<line class="tl-gap-h" x1="{x(y):.1f}" y1="{axis:.1f}" '
          f'x2="{x(y):.1f}" y2="{axis+5:.1f}" opacity=".3"/>')
        if y % 2 == 1:
            a(f'<text class="tl-yr" x="{x(y+.5):.1f}" y="{yrs:.1f}" '
              f'text-anchor="middle">{y}</text>')

    # flags
    for when, label, src, cx, tx, lane in up:
        ty = top - 12 - (n_up - 1 - lane) * LANE_UP
        attrs = f' data-src="{src}" tabindex="0" role="button"' if src else ''
        a(f'<g class="tl-ev"{attrs}>')
        if src:
            a(f'<title>{label} — open the source</title>')
        a(f'<line class="tl-stem" x1="{cx:.1f}" y1="{axis-BAR_MAX:.1f}" '
          f'x2="{cx:.1f}" y2="{ty+5:.1f}"/>')
        a(f'<circle cx="{cx:.1f}" cy="{axis-BAR_MAX:.1f}" r="3.4"/>')
        a(f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle">{label}</text>')
        a('</g>')

    for when, label, src, cx, tx, lane in dn:
        ty = yrs + 18 + lane * LANE_DN
        attrs = f' data-src="{src}" tabindex="0" role="button"' if src else ''
        a(f'<g class="tl-ev"{attrs}>')
        if src:
            a(f'<title>{label} — open the source</title>')
        a(f'<line class="tl-stem" x1="{cx:.1f}" y1="{axis:.1f}" '
          f'x2="{cx:.1f}" y2="{ty-10:.1f}"/>')
        a(f'<circle cx="{cx:.1f}" cy="{axis:.1f}" r="3.4"/>')
        a(f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle">{label}</text>')
        a('</g>')

    a(f'<text class="tl-cap" x="{LEFT}" y="{height-3:.1f}">'
      f'Columns: months of register surviving per year</text>')
    a('</svg>')
    return '\n'.join(o)


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"timeline -> {OUT.relative_to(ROOT)}")
