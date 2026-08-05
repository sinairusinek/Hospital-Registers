"""Inventory Transkribus collection 150024.

Lists all documents and counts pages, GT pages, structural tags, and any HTR
models trained on the collection. Writes a TSV summary to data/eval/.

Usage:
    python -m pipeline.transkribus.inventory [--collection 150024]
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from .client import TrpClient

DEFAULT_COL = 150024
PAGE_NS = "{http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15}"


def _transcript_status(p: dict) -> str:
    """Best transcript status for the page (GT/IN_PROGRESS/DONE/NEW/...)."""
    tsl = p.get("tsList", {}).get("transcripts", []) or []
    statuses = [t.get("status") for t in tsl if t.get("status")]
    for preferred in ("GT", "DONE", "FINAL", "IN_PROGRESS", "NEW"):
        if preferred in statuses:
            return preferred
    return statuses[0] if statuses else ""


def _latest_gt_url(p: dict) -> str | None:
    tsl = p.get("tsList", {}).get("transcripts", []) or []
    gts = [t for t in tsl if t.get("status") == "GT"]
    if not gts:
        return None
    gts.sort(key=lambda t: t.get("timestamp", 0), reverse=True)
    return gts[0].get("url")


def _structural_tags_from_pagexml(xml_text: str) -> set[str]:
    tags: set[str] = set()
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return tags
    for el in root.iter():
        local = el.tag.split("}", 1)[-1]
        if local in {"TableRegion", "TableCell", "TextRegion", "TextLine"}:
            tags.add(local)
        ct = el.get("custom") or ""
        for token in ("structure {type:", "readingOrder {index:"):
            if token in ct:
                tags.add(token.split(" ", 1)[0].strip("{"))
    return tags


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collection", type=int, default=DEFAULT_COL)
    ap.add_argument("--sample-gt-xml", type=int, default=3,
                    help="Fetch this many GT PAGE-XMLs per doc to detect structural tags")
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("data/eval/gt_inventory.tsv"),
    )
    args = ap.parse_args(argv)

    c = TrpClient.from_env()
    docs = c.list_docs(args.collection)
    print(f"Collection {args.collection}: {len(docs)} documents", file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow([
            "doc_id", "title", "n_pages", "n_gt_pages",
            "structural_tags", "first_gt_page_url",
        ])
        for d in docs:
            doc_id = int(d["docId"])
            title = d.get("title", "")
            try:
                fd = c.fulldoc(args.collection, doc_id)
            except Exception as e:
                print(f"  doc {doc_id} fulldoc failed: {e}", file=sys.stderr)
                continue
            pages = fd.get("pageList", {}).get("pages", []) or []
            gt_pages = [p for p in pages if _transcript_status(p) == "GT"]
            tags: set[str] = set()
            first_url = None
            for p in gt_pages[: args.sample_gt_xml]:
                url = _latest_gt_url(p)
                if not url:
                    continue
                first_url = first_url or url
                try:
                    xml = c.fetch_transcript(url)
                    tags |= _structural_tags_from_pagexml(xml)
                except Exception as e:
                    print(f"    page {p.get('pageNr')} fetch failed: {e}", file=sys.stderr)
            w.writerow([
                doc_id, title, len(pages), len(gt_pages),
                ",".join(sorted(tags)), first_url or "",
            ])
            print(
                f"  doc {doc_id} '{title}': {len(pages)} pages, {len(gt_pages)} GT, "
                f"tags={sorted(tags)}",
                file=sys.stderr,
            )

    print(f"\nWrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
