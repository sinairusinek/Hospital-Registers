#!/usr/bin/env python3
"""Give the institutional history a standing table of contents, and move the
sigla table out of the reading flow into a panel that opens on demand.

Sixteen sections is more than a reader can hold, and §01 opened the document
with a thirteen-row reference table before a word of history. This script:

  * gives every section a stable id and lifts the headings into a left rail
    that tracks the reader's position (sticky on wide screens, a disclosure at
    the top on narrow ones, so nothing is lost on a phone);
  * moves the sigla table into a `<details>` panel available from the rail and
    from §01, which now opens with prose instead.

Idempotent: running it twice changes nothing the second time.

    python3 pipeline/history_toc.py [--check]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "paper" / "hospital-history.html"

MARKER = "<!-- toc:injected -->"

SECTION_RE = re.compile(
    r'<section>\s*<div class="sec-head"><div class="sec-no">([^<]*)</div><h2>(.*?)</h2>',
    re.S,
)

CSS = """
/* ---- table of contents rail ------------------------------------------ */
/* Wide screens get a sticky rail beside the text; narrow ones get a
   disclosure above it, so the contents are reachable either way. */
.layout{display:block}
.toc-toggle{display:none}
.toc{margin:0 0 28px}
.toc summary{font-family:var(--mono);font-size:12px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--rubric);cursor:pointer;padding:10px 0}
.toc ol{list-style:none;margin:8px 0 0;padding:0}
.toc li{margin:0}
.toc a{display:flex;gap:.6em;text-decoration:none;color:var(--ink2);
  font-size:.92rem;line-height:1.35;padding:5px 8px;border-radius:4px;
  border-left:2px solid transparent}
.toc a:hover{background:var(--raise);color:var(--ink)}
.toc a .n{font-family:var(--mono);font-size:11px;color:var(--ink3);
  padding-top:.18em;min-width:1.6em}
.toc a.on{color:var(--rubric);border-left-color:var(--rubric);background:var(--raise)}
.toc a.on .n{color:var(--rubric)}
.toc-aside{margin-top:18px;padding-top:14px;border-top:1px solid var(--hair)}
.toc-aside button{font:inherit;font-family:var(--mono);font-size:11px;
  letter-spacing:.04em;text-transform:uppercase;background:none;border:0;
  padding:5px 8px;color:var(--ink3);cursor:pointer;text-align:left}
.toc-aside button:hover{color:var(--rubric)}

@media (min-width:1180px){
  .wrap{max-width:1320px}
  .layout{display:grid;grid-template-columns:232px minmax(0,1fr);gap:44px;
    align-items:start}
  .toc{position:sticky;top:24px;max-height:calc(100vh - 48px);overflow-y:auto;
    margin:0;padding-right:6px}
  .toc summary{display:none}
  .toc[open] > ol, .toc > ol{display:block}
}

/* ---- sigla panel ------------------------------------------------------ */
.sigla{margin:26px 0 0;border:1px solid var(--hair);border-radius:6px;
  background:var(--surface)}
.sigla summary{font-family:var(--mono);font-size:12px;letter-spacing:.05em;
  text-transform:uppercase;color:var(--rubric);cursor:pointer;
  padding:12px 16px;list-style:none}
.sigla summary::-webkit-details-marker{display:none}
.sigla summary::before{content:"\\25B8";display:inline-block;margin-right:.6em;
  transition:transform .15s}
.sigla[open] summary::before{transform:rotate(90deg)}
.sigla .tw{padding:0 16px 16px}
@media print{.toc{display:none}.sigla[open] .tw,.sigla .tw{display:block}}
"""

JS = """
<script>
/* Table of contents: mark the section the reader is in. Uses
   IntersectionObserver where available and degrades to a plain link list
   where it is not. */
(function(){
  var links=[].slice.call(document.querySelectorAll('.toc a[data-sec]'));
  if(!links.length) return;
  var byId={};
  links.forEach(function(a){ byId[a.getAttribute('data-sec')]=a; });

  function mark(id){
    links.forEach(function(a){ a.classList.remove('on'); });
    if(byId[id]) byId[id].classList.add('on');
  }

  if(!('IntersectionObserver' in window)) return;
  var seen={};
  var io=new IntersectionObserver(function(entries){
    entries.forEach(function(e){ seen[e.target.id]=e.isIntersecting?e.intersectionRatio:0; });
    var best=null,bestV=0;
    Object.keys(seen).forEach(function(k){ if(seen[k]>bestV){bestV=seen[k];best=k;} });
    if(best) mark(best);
  },{rootMargin:'-72px 0px -60% 0px',threshold:[0,.25,.5,1]});
  document.querySelectorAll('section[id]').forEach(function(s){ io.observe(s); });

  /* Close the mobile disclosure after a jump, so the text is visible. */
  var toc=document.querySelector('details.toc');
  links.forEach(function(a){
    a.addEventListener('click',function(){
      if(toc && toc.hasAttribute('open') && window.matchMedia('(max-width:1179px)').matches){
        toc.removeAttribute('open');
      }
    });
  });

  /* "Sigla" in the rail opens the panel wherever it sits and scrolls to it. */
  var open=document.querySelector('[data-open-sigla]');
  if(open){
    open.addEventListener('click',function(){
      var s=document.getElementById('sigla');
      if(!s) return;
      s.setAttribute('open','');
      s.scrollIntoView({behavior:'smooth',block:'center'});
    });
  }
})();
</script>
"""


def slug(sec_no: str) -> str:
    """'§ 07' -> 'sec-07'."""
    m = re.search(r"(\d+)", sec_no)
    return f"sec-{m.group(1)}" if m else "sec"


def build(html: str) -> str:
    sections = [
        (slug(m.group(1)), m.group(1).strip(), re.sub(r"<[^>]+>", "", m.group(2)).strip())
        for m in SECTION_RE.finditer(html)
    ]
    if not sections:
        raise SystemExit("no sections found — has the history changed shape?")

    # 1. Give each <section> its id, in document order.
    ids = iter(sections)

    def add_id(m: re.Match) -> str:
        sid, _, _ = next(ids)
        return m.group(0).replace("<section>", f'<section id="{sid}">', 1)

    html = SECTION_RE.sub(add_id, html)

    # 2. Lift the sigla table into a details panel.
    tw = re.search(
        r'(<div class="tw"><table class="srcs">.*?</table></div>)', html, re.S
    )
    if not tw:
        raise SystemExit("sigla table not found")
    table = tw.group(1)
    html = html.replace(
        table,
        '<details class="sigla" id="sigla">'
        "<summary>Sigla — the sources cited throughout</summary>"
        f"{table}"
        "</details>",
        1,
    )

    # 3. Build the rail and wrap <main>.
    items = "".join(
        f'<li><a href="#{sid}" data-sec="{sid}">'
        f'<span class="n">{no.replace("§ ", "")}</span>'
        f"<span>{title}</span></a></li>"
        for sid, no, title in sections
    )
    nav = (
        f"{MARKER}\n"
        '<details class="toc" id="toc">'
        "<summary>Contents</summary>"
        f"<ol>{items}</ol>"
        '<div class="toc-aside">'
        '<button type="button" data-open-sigla>Sigla &amp; sources</button>'
        "</div>"
        "</details>"
    )
    html = html.replace(
        "<main>", f'<div class="layout">\n{nav}\n<main>', 1
    )
    html = html.replace("</main>", "</main>\n</div>", 1)

    # 4. Styles and behaviour.
    html = html.replace("</style>", CSS + "\n</style>", 1)
    html = html.replace("</body>", JS + "\n</body>", 1) if "</body>" in html else html + JS
    return html


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report without writing")
    args = ap.parse_args()

    html = HISTORY.read_text(encoding="utf-8")
    if MARKER in html:
        print("already injected — nothing to do")
        return 0

    out = build(html)
    n = len(SECTION_RE.findall(html))
    print(f"table of contents: {n} sections")
    print("sigla table moved into a disclosure panel")

    if args.check:
        print("(--check: nothing written)")
        return 0

    HISTORY.write_text(out, encoding="utf-8")
    print(f"wrote {HISTORY.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
