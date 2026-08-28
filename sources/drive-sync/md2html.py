#!/usr/bin/env python3
"""Convert a Markdown file to HTML suitable for import as a Google Doc.

Google Docs' HTML import honours dir="rtl" on block elements, so a document
whose body is mostly Hebrew gets rtl paragraphs. Detection is by character
count, not by filename.
"""
import re
import sys
from pathlib import Path

import markdown

HEB = re.compile(r"[֐-׿]")
LAT = re.compile(r"[A-Za-z]")


def is_rtl(text: str) -> bool:
    return len(HEB.findall(text)) > len(LAT.findall(text))


def convert(src: Path, dst: Path, title=None) -> bool:
    text = src.read_text(encoding="utf-8")
    body = markdown.markdown(
        text, extensions=["tables", "fenced_code", "sane_lists", "attr_list"]
    )
    rtl = is_rtl(text)
    d = ' dir="rtl"' if rtl else ""
    head_title = title or src.stem
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{head_title}</title></head>"
        f"<body{d}>{body}</body></html>"
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(html, encoding="utf-8")
    return rtl


if __name__ == "__main__":
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    print("rtl" if convert(src, dst) else "ltr", dst)
