"""Trace TRAINING_VALIDATION_SET / 'Copy of HTR Train Set' page provenance.

For each GT page in a training/validation doc, dumps the imgFileName and tries
to match it against pages in the original source documents in the collection.
Image filenames in Transkribus typically retain the source name, so a string
match on imgFileName usually resolves provenance.

Writes data/eval/gt_provenance.tsv with one row per GT page.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .client import TrpClient
from .inventory import _transcript_status, _latest_gt_url

DEFAULT_COL = 150024

TRAINING_DOC_NAME_PATTERNS = (
    "TRAINING_VALIDATION_SET",
    "Copy of HTR Train Set",
)


def _is_training_doc(title: str) -> bool:
    return any(p in title for p in TRAINING_DOC_NAME_PATTERNS)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collection", type=int, default=DEFAULT_COL)
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("data/eval/gt_provenance.tsv"),
    )
    args = ap.parse_args(argv)

    c = TrpClient.from_env()
    docs = c.list_docs(args.collection)

    training_docs = [d for d in docs if _is_training_doc(d.get("title", ""))]
    source_docs = [d for d in docs if not _is_training_doc(d.get("title", ""))]
    print(
        f"{len(training_docs)} training/validation docs, "
        f"{len(source_docs)} candidate source docs",
        file=sys.stderr,
    )

    source_index: dict[str, tuple[int, str, int]] = {}
    for d in source_docs:
        try:
            fd = c.fulldoc(args.collection, int(d["docId"]))
        except Exception as e:
            print(f"  skip source {d['docId']}: {e}", file=sys.stderr)
            continue
        for p in fd.get("pageList", {}).get("pages", []) or []:
            ifn = p.get("imgFileName")
            if ifn:
                source_index[ifn] = (int(d["docId"]), d.get("title", ""), int(p["pageNr"]))
    print(f"Indexed {len(source_index)} source page filenames", file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow([
            "train_doc_id", "train_doc_title", "train_page_nr",
            "img_file_name", "source_doc_id", "source_doc_title",
            "source_page_nr", "gt_url",
        ])
        for d in training_docs:
            doc_id = int(d["docId"])
            title = d.get("title", "")
            try:
                fd = c.fulldoc(args.collection, doc_id)
            except Exception as e:
                print(f"  skip train {doc_id}: {e}", file=sys.stderr)
                continue
            pages = fd.get("pageList", {}).get("pages", []) or []
            matched = 0
            for p in pages:
                if _transcript_status(p) != "GT":
                    continue
                ifn = p.get("imgFileName", "")
                src = source_index.get(ifn)
                w.writerow([
                    doc_id, title, p.get("pageNr"),
                    ifn,
                    src[0] if src else "",
                    src[1] if src else "",
                    src[2] if src else "",
                    _latest_gt_url(p) or "",
                ])
                if src:
                    matched += 1
            print(f"  {title}: {matched}/{sum(1 for p in pages if _transcript_status(p) == 'GT')} GT pages traced", file=sys.stderr)

    print(f"\nWrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
