#!/usr/bin/env python3
"""Give the institutional history a folding, tiered table of contents.

Sixteen sections and twenty subheadings is more than a reader can hold, and
§01 used to open the document with a thirteen-row reference table before a word
of history. This script:

  * gives every section and every subheading a stable id;
  * builds a **two-tier** contents rail — sections, each with its subheadings
    nested beneath, revealed when that section is the one being read or when
    the reader opens it;
  * lets the whole rail **fold away** to give the text the full width, with the
    choice remembered per reader;
  * moves the sigla table into a panel reachable from the rail, so §01 opens
    with prose.

On narrow screens the rail becomes a disclosure above the text, so nothing is
lost on a phone.

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
    r'<section id="(sec-\d\d)">\s*<div class="sec-head">'
    r'<div class="sec-no">([^<]*)</div><h2>(.*?)</h2>',
    re.S,
)

CSS = """
/* ---- contents rail ---------------------------------------------------- */
/* Wide screens get a rail beside the text that can be folded away; narrow
   ones get a disclosure above it, so the contents are reachable either way. */
.layout{display:block}
.toc{margin:0 0 28px;font-size:.92rem}
.toc summary{font-family:var(--mono);font-size:12px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--rubric);cursor:pointer;padding:10px 0}
.toc-inner{min-width:0}
.toc ol{list-style:none;margin:0;padding:0}
.toc > .toc-inner > ol > li + li{margin-top:1px}

/* tier 1 — sections */
.toc .row{display:flex;align-items:baseline;gap:.1em}
.toc .t1{display:flex;flex:1 1 auto;min-width:0;gap:.5em;align-items:baseline;text-decoration:none;
  color:var(--ink2);line-height:1.35;padding:5px 8px;border-radius:4px;
  border-left:2px solid transparent}
.toc .t1:hover{background:var(--raise);color:var(--ink)}
.toc .n{font-family:var(--mono);font-size:11px;color:var(--ink3);min-width:1.7em}
.toc li.on > .row > .t1{color:var(--rubric);border-left-color:var(--rubric);
  background:var(--raise)}
.toc li.on > .row > .t1 .n{color:var(--rubric)}

/* tier 2 — subheadings, revealed for the open/current section only */
.toc .t2s{max-height:0;overflow:hidden;opacity:0;
  transition:max-height .22s ease,opacity .18s ease}
.toc li.on > .t2s,.toc li.manual > .t2s{max-height:34em;opacity:1}
.toc .t2s li{margin:0}
.toc .t2{display:block;text-decoration:none;color:var(--ink3);
  font-size:.855rem;line-height:1.3;padding:4px 8px 4px 2.5em;
  border-left:2px solid transparent}
.toc .t2:hover{color:var(--ink);background:var(--raise)}
.toc .t2.on{color:var(--rubric);border-left-color:var(--hair)}

/* the twisty that opens a section's subheadings without navigating */
.toc .tw-btn{flex:0 0 auto;background:none;border:0;padding:0 0 0 .2em;margin:0;
  color:var(--ink3);cursor:pointer;font-size:10px;line-height:1;
  transition:transform .18s;align-self:center}
.toc li.on > .row > .tw-btn,.toc li.manual > .row > .tw-btn{transform:rotate(90deg)}
.toc .tw-btn:hover{color:var(--rubric)}

.toc-aside{margin-top:16px;padding-top:12px;border-top:1px solid var(--hair);
  display:flex;flex-direction:column;gap:2px;align-items:flex-start}
.toc-aside button{font:inherit;font-family:var(--mono);font-size:11px;
  letter-spacing:.04em;text-transform:uppercase;background:none;border:0;
  padding:5px 8px;color:var(--ink3);cursor:pointer;text-align:left}
.toc-aside button:hover{color:var(--rubric)}

/* the fold-away control, wide screens only */
.toc-fold{display:none}
.toc-show{display:none}

@media (min-width:1180px){
  .wrap{max-width:1340px}
  .layout{display:grid;grid-template-columns:250px minmax(0,1fr);gap:46px;
    align-items:start}
  .toc{position:sticky;top:24px;max-height:calc(100vh - 48px);overflow-y:auto;
    margin:0;padding-right:6px;scrollbar-width:thin}
  .toc > summary{display:none}
  .toc-fold{display:block}
  /* folded: the rail collapses to a slim strip and the text takes the width */
  .layout.folded{grid-template-columns:0 minmax(0,1fr);gap:0}
  .layout.folded .toc{opacity:0;pointer-events:none;overflow:hidden}
  .toc-show{display:block;position:fixed;left:12px;top:20px;z-index:40;
    font:inherit;font-family:var(--mono);font-size:11px;letter-spacing:.04em;
    text-transform:uppercase;background:var(--raise);color:var(--ink3);
    border:1px solid var(--hair);border-radius:4px;padding:7px 10px;
    cursor:pointer}
  .toc-show:hover{color:var(--rubric)}
  .layout:not(.folded) .toc-show{display:none}
}

@media print{.toc,.toc-show{display:none}.layout{display:block}}
"""

JS = """
<script>
/* Contents rail: track the section being read, reveal its subheadings, and
   remember whether the reader folded the rail away. Degrades to a plain
   nested link list without IntersectionObserver or localStorage. */
(function(){
  var toc=document.getElementById('toc');
  if(!toc) return;
  var layout=document.querySelector('.layout');
  var t1=[].slice.call(toc.querySelectorAll('a.t1'));
  var t2=[].slice.call(toc.querySelectorAll('a.t2'));
  if(!t1.length) return;

  var liById={};
  t1.forEach(function(a){ liById[a.getAttribute('data-sec')]=a.closest('li'); });
  var t2ById={};
  t2.forEach(function(a){ t2ById[a.getAttribute('data-sub')]=a; });

  function markSection(id){
    t1.forEach(function(a){ a.closest('li').classList.remove('on'); });
    var li=liById[id];
    if(li){
      li.classList.add('on');
      /* keep the current entry in view when the rail is long */
      if(toc.scrollHeight>toc.clientHeight){
        var r=li.getBoundingClientRect(), b=toc.getBoundingClientRect();
        if(r.top<b.top||r.bottom>b.bottom) li.scrollIntoView({block:'nearest'});
      }
    }
  }
  function markSub(id){
    t2.forEach(function(a){ a.classList.remove('on'); });
    if(id&&t2ById[id]) t2ById[id].classList.add('on');
  }

  /* The twisty opens a section's subheadings without jumping to it. */
  toc.addEventListener('click',function(e){
    var b=e.target.closest('.tw-btn');
    if(!b) return;
    e.preventDefault(); e.stopPropagation();
    var li=b.closest('li');
    li.classList.toggle('manual');
    b.setAttribute('aria-expanded',li.classList.contains('manual')?'true':'false');
  });

  if('IntersectionObserver' in window){
    var vis={};
    var io=new IntersectionObserver(function(es){
      es.forEach(function(e){ vis[e.target.id]=e.isIntersecting?e.intersectionRatio:0; });
      var best=null,bv=0;
      Object.keys(vis).forEach(function(k){ if(vis[k]>bv){bv=vis[k];best=k;} });
      if(best) markSection(best);
    },{rootMargin:'-70px 0px -60% 0px',threshold:[0,.2,.5,1]});
    document.querySelectorAll('section[id^="sec-"]').forEach(function(s){ io.observe(s); });

    /* Subheadings: whichever h3 last crossed the top of the viewport. */
    var subs=[].slice.call(document.querySelectorAll('h3[id^="sub-"]'));
    if(subs.length){
      var tick=function(){
        var cur=null;
        for(var i=0;i<subs.length;i++){
          if(subs[i].getBoundingClientRect().top<120) cur=subs[i].id; else break;
        }
        markSub(cur);
      };
      var queued=false;
      addEventListener('scroll',function(){
        if(queued) return; queued=true;
        requestAnimationFrame(function(){ queued=false; tick(); });
      },{passive:true});
      tick();
    }
  }

  /* Close the mobile disclosure after a jump so the text is visible. */
  toc.addEventListener('click',function(e){
    var a=e.target.closest('a.t1,a.t2');
    if(a&&toc.hasAttribute('open')&&matchMedia('(max-width:1179px)').matches){
      toc.removeAttribute('open');
    }
  });

  /* Fold the rail away; remember the choice. */
  var KEY='hist-toc-folded';
  var fold=document.querySelector('[data-toc-fold]');
  var show=document.querySelector('.toc-show');
  function setFolded(on){
    if(!layout) return;
    layout.classList.toggle('folded',on);
    if(fold) fold.setAttribute('aria-expanded',on?'false':'true');
    try{ localStorage.setItem(KEY,on?'1':'0'); }catch(e){}
  }
  try{ if(localStorage.getItem(KEY)==='1') setFolded(true); }catch(e){}
  if(fold) fold.addEventListener('click',function(){ setFolded(true); });
  if(show) show.addEventListener('click',function(){ setFolded(false); });

  /* Sigla, from the rail. */
  var sig=document.querySelector('[data-open-sigla]');
  if(sig) sig.addEventListener('click',function(){
    var s=document.getElementById('sigla');
    if(!s) return;
    s.setAttribute('open','');
    s.scrollIntoView({behavior:'smooth',block:'center'});
  });
})();
</script>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report without writing")
    args = ap.parse_args()

    html = HISTORY.read_text(encoding="utf-8")
    if MARKER in html:
        print("already injected — nothing to do")
        return 0

    # 1. Collect sections and the subheadings inside each.
    bounds = [(m.group(1), m.group(2).strip(), m.group(3), m.start())
              for m in SECTION_RE.finditer(html)]
    if not bounds:
        raise SystemExit("no sections found — has the history changed shape?")

    tree = []
    sub_n = 0
    for i, (sid, no, title, pos) in enumerate(bounds):
        stop = bounds[i + 1][3] if i + 1 < len(bounds) else len(html)
        subs = []
        for hm in re.finditer(r"<h3>(.*?)</h3>", html[pos:stop], re.S):
            sub_n += 1
            subs.append((f"sub-{sub_n:02d}", re.sub(r"<[^>]+>", "", hm.group(1)).strip()))
        tree.append((sid, no, re.sub(r"<[^>]+>", "", title).strip(), subs))

    # 2. Give the subheadings their ids, in document order.
    ids = iter([s[0] for _, _, _, subs in tree for s in subs])
    html = re.sub(r"<h3>", lambda m: f'<h3 id="{next(ids)}">', html)

    # 3. Lift the sigla table into a panel.
    tw = re.search(r'(<div class="tw"><table class="srcs">.*?</table></div>)', html, re.S)
    if not tw:
        raise SystemExit("sigla table not found")
    html = html.replace(
        tw.group(1),
        '<details class="sigla" id="sigla">'
        "<summary>Sigla — the sources cited throughout</summary>"
        f"{tw.group(1)}</details>",
        1,
    )

    # 4. Build the rail.
    items = []
    for sid, no, title, subs in tree:
        twisty = (
            '<button type="button" class="tw-btn" aria-expanded="false" '
            f'aria-label="Show sections within {title}">&#9656;</button>'
            if subs else ""
        )
        kids = "".join(
            f'<li><a class="t2" href="#{subid}" data-sub="{subid}">{subtitle}</a></li>'
            for subid, subtitle in subs
        )
        items.append(
            "<li><div class='row'>"
            f"<a class='t1' href='#{sid}' data-sec='{sid}'>"
            f"<span class='n'>{no.replace('§ ', '')}</span>"
            f"<span>{title}</span></a>{twisty}</div>"
            + (f"<ol class='t2s'>{kids}</ol>" if subs else "")
            + "</li>"
        )

    chron = (
        "<li><div class='row'><a class='t1' href='#chronology'>"
        "<span class='n'>&#9662;</span>"
        "<span>The chronology at a glance</span></a></div></li>"
    )

    nav = (
        f"{MARKER}\n"
        '<details class="toc" id="toc" open>'
        "<summary>Contents</summary>"
        '<div class="toc-inner">'
        f"<ol>{items[0]}{chron}{''.join(items[1:])}</ol>"
        '<div class="toc-aside">'
        '<button type="button" data-open-sigla>Sigla &amp; sources</button>'
        '<button type="button" class="toc-fold" data-toc-fold '
        'aria-expanded="true">&#9666; Hide contents</button>'
        "</div></div></details>"
        '\n<button type="button" class="toc-show">&#9656; Contents</button>'
    )
    html = html.replace("<main>", f'<div class="layout">\n{nav}\n<main>', 1)
    html = html.replace("</main>", "</main>\n</div>", 1)

    html = html.replace("</style>", CSS + "\n</style>", 1)
    html = html + JS

    n_sub = sum(len(s[3]) for s in tree)
    print(f"contents rail: {len(tree)} sections, {n_sub} subheadings, foldable")

    if args.check:
        print("(--check: nothing written)")
        return 0

    HISTORY.write_text(html, encoding="utf-8")
    print(f"wrote {HISTORY.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
