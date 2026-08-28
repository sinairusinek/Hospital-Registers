#!/usr/bin/env python3
"""Repair the two defects Drive's HTML→Doc import introduces in the guide.

1. Literal ``\*\*`` inside table cells: the Markdown emphasis was escaped rather
   than rendered. Replace the escaped runs with real <strong> markup.
2. English gloss lines glued onto the Hebrew sentence: the blockquote inside a
   list item is flattened on import. Promote each such gloss to its own
   paragraph, visually set apart, so the two languages stay separate.
"""
import re
from pathlib import Path

# Working directory: beside these scripts by default, or $HR_DRIVE_WORKDIR.
S = Path(os.environ.get("HR_DRIVE_WORKDIR", Path(__file__).resolve().parent))
p = S / "stage" / "00 מדריך — קראו קודם.html"
html = p.read_text(encoding="utf-8")

# 1. \*\*text\*\* -> <strong>text</strong>, and stray \*text\* -> <em>
html = re.sub(r"\\\*\\\*(.+?)\\\*\\\*", r"<strong>\1</strong>", html)
html = re.sub(r"\\\*(.+?)\\\*", r"<em>\1</em>", html)

# 2. Blockquotes inside list items: lift the gloss out of the <li> so the
#    importer cannot glue it to the Hebrew sentence. Render as an italic
#    left-to-right paragraph after the item's own text.
def lift(m):
    inner = m.group(1).strip()
    inner = re.sub(r"</?p>", "", inner).strip()
    return (
        '<br /><span dir="ltr" style="font-style:italic;color:#555">'
        f"{inner}</span>"
    )

html = re.sub(r"<blockquote>(.*?)</blockquote>", lift, html, flags=re.S)

p.write_text(html, encoding="utf-8")
print("remaining escaped asterisks:", html.count(r"\*"))
print("remaining blockquotes:", html.count("<blockquote>"))
