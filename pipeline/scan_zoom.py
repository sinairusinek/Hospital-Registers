"""Zoom on one record's address: serial column + address column, about two
rows around the serial, placed by its rank among the page's serials.

    python3 pipeline/scan_zoom.py NB PAGE SERIAL OUT.jpg

Library notebooks only (not NB6-9); see pipeline/scan_crop.py for those.
"""
import csv,sys,io,urllib.request,collections
from PIL import Image
nb,pg,serial,out=sys.argv[1:5]; serial=int(serial)
R=csv.DictReader(open('/Users/sinairusinek/Documents/GitHub/Hospital-Registers/data/public/hospital-registers-normalized.tsv'),delimiter='\t',quoting=csv.QUOTE_NONE)
ser=sorted({int(r['Notebook Record ID']) for r in R if r['Notebook_Number']==nb and r['Page_Number']==pg and r['Notebook Record ID'].isdigit()})
idx=ser.index(serial) if serial in ser else len([x for x in ser if x<serial]); n=max(len(ser),1)
y0=max(0,5+95*(idx-0.8)/n); y1=min(100,5+95*(idx+1.8)/n)
svc=next(r['image_service'] for r in csv.DictReader(open('/Users/sinairusinek/Documents/GitHub/Hospital-Registers/data/public/iiif-pages.tsv'),delimiter='\t') if r['Notebook_Number']==nb and r['Page_Number']==pg)
parts=[]
for x,w in [(2,4),(31,18)]:
    u=f"{svc}/pct:{x},{y0:.1f},{w},{y1-y0:.1f}/,700/0/default.jpg"
    parts.append(Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"HR/1.0 (sinai.rusinek@gmail.com)"}),timeout=120).read())))
c=Image.new('RGB',(sum(p.width for p in parts),700),'white');x=0
for p in parts: c.paste(p,(x,0)); x+=p.width
c.save(out); print(out,c.size)
