#!/usr/bin/env python3
"""Harvest ISA search result rows (signature, title, source, dates, access) via shared Chrome."""
import json, urllib.request, urllib.parse, websocket, time, sys, re

BASE='https://www.archives.gov.il/'+urllib.parse.quote('חיפוש/חיפוש/')

def cdp():
    tabs=json.load(urllib.request.urlopen("http://127.0.0.1:9222/json"))
    t=next(x for x in tabs if x["type"]=="page")
    return websocket.create_connection(t["webSocketDebuggerUrl"],timeout=300,
                                       max_size=300*1024*1024,suppress_origin=True)
_id=[0]
def send(ws,m,p=None):
    _id[0]+=1;mid=_id[0];ws.send(json.dumps({"id":mid,"method":m,"params":p or {}}))
    while True:
        r=json.loads(ws.recv())
        if r.get("id")==mid: return r

TXT="document.body.innerText"

def parse(text):
    """Rows are newline blocks; pull signature + the lines around it."""
    rows=[]
    blocks=re.split(r'\n(?=\d+\n)', text)
    for b in blocks:
        m=re.search(r'מזהה לציטוט:\s*\n?\s*([0-9a-z]{6,8})', b)
        if not m: continue
        sig=m.group(1)
        lines=[l.strip() for l in b.split('\n') if l.strip()]
        # title = first line that is not boilerplate
        skip={'גישה מקוונת','טקסטואלי','גלוי','רמה:','תיק','מיכל','פריט זה ללא תיאור','מוגבל'}
        title=' '.join([l for l in lines[1:6] if l not in skip and not l.startswith(('מקור','תקופת','מזהה','רמה'))])[:200]
        src=re.search(r'מקור החומר:\s*\n?\s*(.+)', b)
        per=re.search(r'תקופת החומר:\s*\n?\s*(.+)', b)
        phys=re.search(r'מזהה פיזי:\s*\n?\s*(.+)', b)
        lvl=re.search(r'רמה:\s*\n?\s*(.+)', b)
        rows.append({'sig':sig,'title':title.strip(),
                     'source':(src.group(1).strip() if src else ''),
                     'period':(per.group(1).strip() if per else ''),
                     'phys':(phys.group(1).strip() if phys else ''),
                     'level':(lvl.group(1).strip() if lvl else ''),
                     'online':('גישה מקוונת' in b)})
    return rows

def harvest(ws,query,decades='',pages=6,pagesize=50):
    allrows={}
    total=None
    for pg in range(1,pages+1):
        q={'searchType':'ArchiveSimple','query':query,'searchMethod':'allTerms',
           'currentPage':pg,'pageSize':pagesize,'sortBy':'score'}
        url=BASE+'?'+urllib.parse.urlencode(q)
        if decades: url+='&decades='+urllib.parse.quote(decades)
        send(ws,"Page.navigate",{"url":url}); time.sleep(20)
        r=send(ws,"Runtime.evaluate",{"expression":TXT,"returnByValue":True})
        txt=(r.get('result',{}).get('result',{}) or {}).get('value') or ''
        if total is None:
            m=re.search(r'מתוך\s*([\d,]+)\s*תוצאות',txt)
            total=m.group(1) if m else '?'
        rows=parse(txt)
        if not rows: break
        for x in rows: allrows[x['sig']]=x
        if len(rows)<int(pagesize*0.6): break
    return total,list(allrows.values())

if __name__=="__main__":
    ws=cdp(); send(ws,"Page.enable"); send(ws,"Runtime.enable")
    out={}
    for q in sys.argv[1:]:
        total,rows=harvest(ws,q)
        out[q]={'total':total,'rows':rows}
        print(f"### {q}  total={total}  harvested={len(rows)}",flush=True)
    json.dump(out,open('isa_search_results.json','w'),ensure_ascii=False,indent=1)
    ws.close()
