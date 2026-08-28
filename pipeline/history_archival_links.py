#!/usr/bin/env python3
"""Make the archival citations in the institutional history clickable.

The history already opens a source panel for every press citation: a
`<button class="src" data-src="…">` looked up in the `src-data` JSON blob. The
archival references — the Mandate reports, the MECA catalogue, the Israel State
Archives files — were inert `<span class="sig">` text, so a reader could see
that a claim rested on an archive but could not reach it.

This script merges `paper/archival-sources.json` into that same blob and
rewrites the inert spans as buttons, so archives and press behave alike. It is
idempotent: running it twice changes nothing the second time.

    python3 pipeline/history_archival_links.py [--check]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "paper" / "hospital-history.html"
ARCHIVAL = ROOT / "sources" / "archival-sources.json"

# Inert citations that become buttons. The key is the source id in the merged
# blob; the pattern matches the <span class="sig">…</span> as it stands in the
# document. Only citations that point at something a reader can open are
# rewritten — file paths and code identifiers stay as plain text, because a
# panel for `csv.QUOTE_NONE` would be noise.
SIG_TO_SOURCE = {
    "mr-reports": re.compile(r'<span class="sig">(MR-19\d\d(?:\s*&sect;\s*[\w.]+| §[\w.]+)?)</span>'),
    "jem-cat": re.compile(r'<span class="sig">(JEM-cat)</span>'),
}


def load_blob(html: str) -> tuple[dict, int, int]:
    """Return the parsed src-data blob and the span it occupies."""
    m = re.search(
        r'(<script id="src-data" type="application/json">)(.*?)(</script>)',
        html,
        re.S,
    )
    if not m:
        raise SystemExit("src-data blob not found — has the history changed shape?")
    return json.loads(m.group(2)), m.start(2), m.end(2)


def merge(html: str, archival: dict) -> tuple[str, int]:
    data, start, end = load_blob(html)
    added = 0
    for key, entry in archival.items():
        if key not in data:
            added += 1
        data[key] = entry
    blob = json.dumps(data, ensure_ascii=False, indent=0, sort_keys=True)
    return html[:start] + blob + html[end:], added


def linkify(html: str) -> tuple[str, int]:
    """Turn the inert sig spans into source buttons."""
    total = 0
    for key, pattern in SIG_TO_SOURCE.items():
        def repl(m: re.Match) -> str:
            label = m.group(1)
            return (
                f'<button type="button" class="src" data-src="{key}" '
                f'aria-expanded="false">{label}</button>'
            )

        html, n = pattern.subn(repl, html)
        total += n
    return html, total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--check",
        action="store_true",
        help="report what would change without writing",
    )
    args = ap.parse_args()

    html = HISTORY.read_text(encoding="utf-8")
    archival = json.loads(ARCHIVAL.read_text(encoding="utf-8"))

    merged, added = merge(html, archival)
    merged, linked = linkify(merged)

    data, _, _ = load_blob(merged)
    archives = sum(1 for v in data.values() if v.get("kind") == "archive")
    print(f"archival entries in blob: {archives} ({added} newly added)")
    print(f"inert citations linkified: {linked}")
    print(f"total sources: {len(data)}")

    if args.check:
        print("(--check: nothing written)")
        return 0

    if merged == html:
        print("no change")
        return 0

    HISTORY.write_text(merged, encoding="utf-8")
    print(f"wrote {HISTORY.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
