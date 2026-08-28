#!/usr/bin/env python3
"""Open the history with its chronology instead of a paragraph.

The standfirst was doing too much: it named the 1938 rented-mission finding,
the register test and four press corpora before the reader knew what the
institution was. The timeline says the same thing faster — two buildings, one
seam, the register's coverage under it — so it moves up into the header, where
it can be folded away, and the standfirst shrinks to a single orienting line.

Section 02 keeps its heading and its reading notes, and points at the header
figure rather than repeating it.

Idempotent.

    python3 pipeline/history_header_timeline.py [--check]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "paper" / "hospital-history.html"
MARKER = "<!-- header-timeline:injected -->"

# The new opening line. Short, and about the institution rather than about the
# findings — the findings are what the document is for, not how it should open.
STANDFIRST = (
    '<p class="standfirst">A government hospital in Haifa, from a rented '
    "mission building on Mountain Road to Erich Mendelsohn's block above the "
    "sea at Bat Galim — reconstructed from the Mandate's own files, four press "
    "corpora, and the admission register of some 29,000 patients. "
    "<strong>Every citation opens the source behind it.</strong></p>"
)

CSS = """
/* ---- header chronology ------------------------------------------------ */
.hero-tl{margin:22px 0 0;border-top:1px solid var(--hair);padding-top:6px}
.hero-tl summary{font-family:var(--mono);font-size:11px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--ink3);cursor:pointer;padding:8px 0;
  list-style:none}
.hero-tl summary::-webkit-details-marker{display:none}
.hero-tl summary::before{content:"\\25B8";display:inline-block;margin-right:.6em;
  transition:transform .15s}
.hero-tl[open] summary::before{transform:rotate(90deg)}
.hero-tl summary:hover{color:var(--rubric)}
.hero-tl figure{margin:4px 0 10px}
.hero-tl figcaption{font-size:.86rem;color:var(--ink3);margin-top:8px;
  max-width:78ch}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    html = HISTORY.read_text(encoding="utf-8")
    if MARKER in html:
        print("already injected — nothing to do")
        return 0

    # 1. Lift the whole <figure> out of section 02.
    start = html.find('<section id="sec-02">')
    end = html.find('<section id="sec-03">')
    if start < 0 or end < 0:
        raise SystemExit("sections 02/03 not found")
    block = html[start:end]

    fm = re.search(r"<figure>.*?</figure>", block, re.S)
    if not fm:
        raise SystemExit("timeline figure not found in section 02")
    figure = fm.group(0)

    block_without = block.replace(figure, "", 1)
    html = html[:start] + block_without + html[end:]

    # 2. Put it in the header, folded open by default so the first screen
    #    carries the shape of the story.
    hero = (
        f"{MARKER}\n"
        '<details class="hero-tl" id="chronology" open>'
        "<summary>The chronology at a glance</summary>"
        f"{figure}"
        "</details>"
    )
    html = html.replace("</header>", f"{hero}\n</header>", 1)

    # 3. Replace the standfirst.
    html = re.sub(
        r'<p class="standfirst">.*?</p>', STANDFIRST, html, count=1, flags=re.S
    )

    # 4. Point section 02 at the header figure.
    html = html.replace(
        "<strong>The flagged events are clickable</strong> — each opens the "
        "article that dates it.</p>",
        "<strong>The flagged events are clickable</strong> — each opens the "
        "article that dates it. The figure itself stands at the head of this "
        'document; <a href="#chronology">jump back to it</a>.</p>',
        1,
    )

    html = html.replace("</style>", CSS + "\n</style>", 1)

    print("timeline moved into the header (foldable, open by default)")
    print("standfirst replaced")

    if args.check:
        print("(--check: nothing written)")
        return 0

    HISTORY.write_text(html, encoding="utf-8")
    print(f"wrote {HISTORY.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
