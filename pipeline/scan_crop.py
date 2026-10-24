"""Crop a register page for reading a place: the serial column and the
age-to-address columns side by side, never the name column.

    python3 pipeline/scan_crop.py NB PAGE OUT.jpg [Y0 Y1]   (Y0/Y1: vertical band in %)

NB6-9 come from Transkribus (unredacted; needs TRANSKRIBUS_USER/PASS), the
rest from the Haifa library IIIF service via data/public/iiif-pages.tsv.
"""
import csv, io, os, sys, json, urllib.request
from PIL import Image
sys.path.insert(0, "/Users/sinairusinek/Documents/GitHub/Hospital-Registers/pipeline")
UA = {"User-Agent": "HospitalRegisters/1.0 (sinai.rusinek@gmail.com)"}
TK_DOCS = {"6": 1476910, "7": 1478219, "8": 1477097, "9": 1478257}
HERE = os.environ.get("TMPDIR", "/tmp")  # Transkribus page-list cache

def get(url):
    return Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180).read()))

def tk_image_id(nb, page):
    cache = os.path.join(HERE, f"tk_{nb}.json")
    if not os.path.exists(cache):
        from transkribus.client import TrpClient
        c = TrpClient.from_env()
        d = c.session.get(f"{c.base}/collections/150024/{TK_DOCS[nb]}/fulldoc", timeout=120).json()
        pages = {str(p["pageNr"]): p["url"].split("id=")[1].split("&")[0] for p in d["pageList"]["pages"]}
        json.dump(pages, open(cache, "w"))
    return json.load(open(cache))[page]

def main(nb, page, out, y0="0", y1="100"):
    y0, y1 = float(y0), float(y1); h = y1 - y0
    if nb in TK_DOCS:
        base = f"https://files.transkribus.eu/iiif/2/{tk_image_id(nb, page)}"
        parts = [get(f"{base}/pct:0,{y0},6,{h}/,{max(300,int(1800*h/100))}/0/default.jpg"), get(f"{base}/pct:20,{y0},26,{h}/,{max(300,int(1800*h/100))}/0/default.jpg")]
    else:
        svc = next(r["image_service"] for r in csv.DictReader(open("/Users/sinairusinek/Documents/GitHub/Hospital-Registers/data/public/iiif-pages.tsv"), delimiter="\t")
                   if r["Notebook_Number"] == nb and r["Page_Number"] == page)
        parts = [get(f"{svc}/pct:2,{y0},5,{h}/,{max(300,int(1800*h/100))}/0/default.jpg"), get(f"{svc}/pct:15,{y0},34,{h}/,{max(300,int(1800*h/100))}/0/default.jpg")]
    w = sum(p.width for p in parts); h = max(p.height for p in parts)
    canvas = Image.new("RGB", (w, h), "white"); x = 0
    for p in parts:
        canvas.paste(p, (x, 0)); x += p.width
    canvas.thumbnail((1400, 1400)); canvas.save(out, quality=85); print(out, canvas.size)

if __name__ == "__main__":
    main(*sys.argv[1:])
