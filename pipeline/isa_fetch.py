#!/usr/bin/env python3
"""Fetch Israel State Archives file PDFs by signature (e.g. 000zbri).

ISA loads scans into a pdf.js iframe from a presigned S3 URL that expires in
~1h and 403s outside the browser session. So we drive the shared Chrome
(port 9222, see reference_shared_chrome_protocol), let pdf.js load the file,
then pull the bytes out of PDFViewerApplication.pdfDocument.getData().
"""
import json, urllib.request, websocket, time, sys, os, base64

def cdp():
    tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json"))
    tab = next(t for t in tabs if t["type"] == "page")
    return websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=300,
                                       max_size=600*1024*1024, suppress_origin=True)

GETDATA = """(async()=>{try{
const app=window.PDFViewerApplication;
if(!app||!app.pdfDocument) return 'NOAPP';
const d=await app.pdfDocument.getData();
let s='';for(let i=0;i<d.length;i+=8192)s+=String.fromCharCode.apply(null,d.subarray(i,i+8192));
return 'OK'+btoa(s);}catch(e){return 'EXC '+e.message}})()"""

class ISA:
    def __init__(self):
        self.ws = cdp(); self.ctxs = {}; self._id = 0
        self.send("Runtime.enable"); self.send("Page.enable")

    def send(self, method, params=None):
        self._id += 1; mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            r = json.loads(self.ws.recv())
            if r.get("method") == "Runtime.executionContextCreated":
                c = r["params"]["context"]; self.ctxs[c["id"]] = c.get("origin", "")
            if r.get("method") == "Runtime.executionContextDestroyed":
                self.ctxs.pop(r["params"].get("executionContextId"), None)
            if r.get("id") == mid: return r

    def fetch(self, sig, outdir="isa_files", wait=420):
        """Navigate, then poll every JS context until pdf.js reports the doc loaded.

        Large files (some are 100+ MB) take minutes to stream from S3, so we poll
        rather than sleeping a fixed interval."""
        os.makedirs(outdir, exist_ok=True)
        out = os.path.join(outdir, f"{sig}.pdf")
        if os.path.exists(out) and open(out, "rb").read(5) == b"%PDF-":
            return out, os.path.getsize(out), "cached"
        # Blank the tab first: pdf.js keeps the PREVIOUS document alive for a while after
        # navigation, so without this a slow-loading file silently yields the last one's bytes.
        self.send("Page.navigate", {"url": "about:blank"})
        time.sleep(4)
        self.ctxs.clear()
        self.send("Page.navigate", {"url": f"https://www.archives.gov.il/details/{sig}"})
        t0 = time.time(); saw_frame = False
        while time.time() - t0 < wait:
            time.sleep(5)
            for cid in sorted(self.ctxs, reverse=True):
                try:
                    r = self.send("Runtime.evaluate", {"expression": GETDATA,
                        "awaitPromise": True, "returnByValue": True,
                        "contextId": cid, "timeout": 240000})
                except Exception:
                    continue
                v = (r.get("result", {}).get("result", {}) or {}).get("value")
                if isinstance(v, str) and v.startswith("OK"):
                    d = base64.b64decode(v[2:]); open(out, "wb").write(d)
                    return out, len(d), "ok"
                if v == "NOAPP":
                    saw_frame = True
        return None, 0, ("viewer never finished loading" if saw_frame
                         else "no scan / restricted")

    def close(self):
        try: self.ws.close()
        except Exception: pass

if __name__ == "__main__":
    isa = ISA()
    try:
        for sig in sys.argv[1:]:
            p, n, st = isa.fetch(sig)
            print(f"{sig}: {st}  {p or ''} {n:,}" if p else f"{sig}: FAILED — {st}")
    finally:
        isa.close()
