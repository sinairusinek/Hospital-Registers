#!/usr/bin/env python3
"""Put page numbers on the archival citations.

"ISA 0005xx0" points at 1,569 pages; that is a file reference, not a citation.
The readings in `data/archives/` record the page for nearly every claim, so
this script rewrites each button's label to carry it — "ISA 0005xx0 pp.
727–729" — leaving the `data-src` key alone so the source panel still resolves.

Each entry below is keyed by the *claim*, not by the file, because the same
file is cited eleven times for eleven different things. The anchor text is a
distinctive phrase from the sentence the citation closes; if the prose is
reworded the anchor stops matching and the script says so rather than guessing.

Idempotent: a label that already carries pages is left alone.

    python3 pipeline/history_archival_pages.py [--check]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "paper" / "hospital-history.html"

# (anchor phrase just before the button, source key, page string)
# The anchor is matched against the plain text preceding the citation.
CITATIONS = [
    # §01 source base — whole-file references, no page
    ("The central file is", "isa-0005xx0", None),
    ("the infectious-disease returns are", "isa-000zbri", None),
    # §04 Mountain Road
    ("for the whole pre-Bat Galim period", "isa-0010qhu", None),
    ("Infectious Diseases Annex at the Municipal Hospital in 1927", "isa-00079mb", None),
    # §06 capacity
    ("the 220 that actually opened", "isa-0005xx0", "pp. 323–331"),
    # §07 Bat Galim
    ("the closest thing to a room list the building has left", "isa-0005xx0",
     "pp. 276–289, 323–331"),
    ("with cadastral plans at 1:2500", "isa-000b0ms", None),
    ("the roads proposed to serve it", "isa-000ucac", None),
    ("its environs at 1:1250", "isa-000w8jb", None),
    ("not answerable from this source", "isa-0005xx0", "pp. 18, 727–729"),
    ("(ISA pp. 1236–1237, 1 April 1941)", "isa-0005xx0", "pp. 1236–1237"),
    # §08 lazaret and plague unit
    ("deferred for want of provision in the Estimates", "isa-000nxlg", "pp. 4–6"),
    ("at £P.277.5 per dunum", "isa-000b33x", None),
    ('"Plague Unit" and "Plague Service Station"', "isa-0005xx0",
     "pp. 1301–1421"),
    # §15 what remains open
    ("one adjoining project in 1928 and deferred", "isa-000nxlg", "pp. 4–6"),
    ("plague unit was built on the hospital site itself", "isa-0005xx0",
     "pp. 1301–1421"),
    ("the admission registers do not reach", "isa-000i5yq", None),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    html = HISTORY.read_text(encoding="utf-8")

    # Every archival button, in document order, with its position.
    buttons = list(
        re.finditer(
            r'<button type="button" class="src" data-src="(isa-[^"]+)" '
            r'aria-expanded="false">([^<]*)</button>',
            html,
        )
    )
    if len(buttons) != len(CITATIONS):
        print(
            f"! {len(buttons)} archival buttons in the document but "
            f"{len(CITATIONS)} listed here — the prose has changed shape.",
            file=sys.stderr,
        )
        return 1

    edits: list[tuple[int, int, str]] = []
    problems: list[str] = []
    added = skipped = 0

    for btn, (anchor, key, pages) in zip(buttons, CITATIONS):
        if btn.group(1) != key:
            problems.append(
                f"expected {key} at {anchor!r} but found {btn.group(1)}"
            )
            continue
        before = re.sub(r"<[^>]+>", "", html[max(0, btn.start() - 400):btn.start()])
        if anchor not in before:
            problems.append(f"anchor not found before {key}: {anchor!r}")
            continue
        if pages is None:
            skipped += 1
            continue
        label = btn.group(2)
        if "p." in label:  # already carries pages
            skipped += 1
            continue
        edits.append((btn.start(2), btn.end(2), f"{label} {pages}"))
        added += 1

    if problems:
        for p in problems:
            print(f"! {p}", file=sys.stderr)
        return 1

    for start, end, new in reversed(edits):
        html = html[:start] + new + html[end:]

    print(f"page numbers added: {added}; left as whole-file refs: {skipped}")

    if args.check:
        print("(--check: nothing written)")
        return 0
    if not edits:
        print("no change")
        return 0

    HISTORY.write_text(html, encoding="utf-8")
    print(f"wrote {HISTORY.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
