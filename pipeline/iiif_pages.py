"""Resolve every register page to its IIIF image service.

Reads the 29 IIIF manifests the Haifa University Library serves for the
notebooks and writes

  data/public/iiif-pages.tsv    notebook + page -> canvas, image service URL

so that any record in the dataset can be pointed at the scan of its own page
without a single API call at runtime.

Two things this file establishes, both verified against the manifests rather
than assumed:

  * The dataset's `Page_Number` is the number carried in the canvas label, for
    every notebook including the `redacted_*` family. The offset is zero
    throughout. (The printed page in the ledger runs one behind the label in
    notebooks 27-33; that is a fact about the volumes, not about this mapping.)
  * Labels are not contiguous and not equal to position — notebook 12 holds
    101 canvases whose labels run to 126. So the canvas index is carried
    explicitly and never recomputed from the page number.

The Image API service needs no token: `<service>/full/1500,/0/default.jpg`
returns the page, and `<service>/{x,y,w,h}/{w},/0/default.jpg` returns a crop.
The viewer's own `?token=` is for its session, not for access.

Notebooks 6-9 have no representation and appear nowhere here: 6 is absent from
the library's viewer and 7, 8, 9 carry no tempLink in the dataset.

Run: python3 pipeline/iiif_pages.py [--manifest-dir DIR]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "public", "iiif-pages.tsv")

MANIFEST = (
    "https://haifa.userservices.exlibrisgroup.com/view/iiif/presentation"
    "/972HAI_MAIN/{rep}/manifest?iiifVersion=2"
)
VIEWER = (
    "https://haifa.userservices.exlibrisgroup.com/view/BookReaderViewer"
    "/972HAI_MAIN/{rep}"
)

# Notebook -> representation id, taken from the tempLink column of the
# consolidated TSV. Notebooks 6-9 are absent: they have no representation.
REPIDS = {
    1: "12309601280002791", 2: "12309730650002791", 3: "12309730090002791",
    4: "12309729550002791", 5: "12313400500002791", 10: "12313379520002791",
    11: "12336609400002791", 12: "12336608180002791", 13: "12336607160002791",
    14: "12336606170002791", 15: "12336605170002791", 16: "12336799300002791",
    17: "12336797410002791", 18: "12336796400002791", 19: "12337058660002791",
    20: "12337130730002791", 21: "12337785840002791", 22: "12337937890002791",
    23: "12337936870002791", 24: "12337935840002791", 25: "12337934760002791",
    26: "12338070740002791", 27: "12350967050002791", 28: "12350966060002791",
    29: "12350965120002791", 30: "12350964490002791", 31: "12351719160002791",
    32: "12351718120002791", 33: "12351717110002791",
}

COLUMNS = [
    "Notebook_Number",
    "Page_Number",
    "canvas_index",
    "canvas_label",
    "width",
    "height",
    "image_service",
    "viewer_url",
]


def page_from_label(label: str) -> int | None:
    """The page number a canvas label carries.

    Labels come in two families, both ending in the number:

        0034_11_1935_034_d          -> 34
        redacted_0001_0035          -> 35

    A trailing `_d` marks a derivative and is not part of the number.
    """
    parts = label.strip().split("_")
    while parts and not re.fullmatch(r"\d+", parts[-1]):
        parts.pop()
    return int(parts[-1]) if parts else None


def load_manifest(nb: int, rep: str, cache_dir: str | None) -> dict:
    path = os.path.join(cache_dir, f"nb{nb:02d}.json") if cache_dir else None
    if path and os.path.exists(path) and os.path.getsize(path) > 1000:
        with open(path, "rb") as fh:
            return json.load(fh)
    with urllib.request.urlopen(MANIFEST.format(rep=rep), timeout=90) as r:
        raw = r.read()
    manifest = json.loads(raw)
    if path:
        os.makedirs(cache_dir, exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(raw)
    return manifest


def rows_for(nb: int, rep: str, manifest: dict) -> list[dict]:
    out = []
    canvases = manifest["sequences"][0]["canvases"]
    for index, canvas in enumerate(canvases):
        label = canvas.get("label", "")
        page = page_from_label(label)
        if page is None:
            print(f"  nb{nb}: canvas {index} has no page in its label {label!r}",
                  file=sys.stderr)
            continue
        image = canvas["images"][0]["resource"]
        service = image.get("service", {}).get("@id", "")
        if not service:
            print(f"  nb{nb}: canvas {index} carries no image service",
                  file=sys.stderr)
            continue
        out.append({
            "Notebook_Number": nb,
            "Page_Number": page,
            "canvas_index": index,
            "canvas_label": label,
            # The canvas dimensions, not the resource's: they are what the
            # region syntax is expressed in.
            "width": canvas.get("width", image.get("width", "")),
            "height": canvas.get("height", image.get("height", "")),
            "image_service": service.rstrip("/"),
            "viewer_url": VIEWER.format(rep=rep),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest-dir", default=None,
                    help="cache directory for the fetched manifests")
    args = ap.parse_args()

    rows: list[dict] = []
    for nb, rep in sorted(REPIDS.items()):
        manifest = load_manifest(nb, rep, args.manifest_dir)
        got = rows_for(nb, rep, manifest)
        rows.extend(got)
        print(f"notebook {nb:2d}: {len(got):3d} pages")

    # A page number that repeats within a notebook would break the lookup the
    # site does. Report it rather than silently keeping the last one.
    seen: dict[tuple[int, int], int] = {}
    for r in rows:
        key = (r["Notebook_Number"], r["Page_Number"])
        if key in seen:
            print(f"  duplicate page: notebook {key[0]} page {key[1]} "
                  f"(canvases {seen[key]} and {r['canvas_index']})",
                  file=sys.stderr)
        seen[key] = r["canvas_index"]

    rows.sort(key=lambda r: (r["Notebook_Number"], r["Page_Number"]))
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, delimiter="\t",
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    print(f"\n{len(rows)} pages across {len(REPIDS)} notebooks -> "
          f"{os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
