import re, html, json, glob, os

def txt(s):
    return html.unescape(re.sub(r'(?s)<[^>]+>', ' ', s)).replace('\xa0', ' ').strip()

def sq(s):
    return re.sub(r'\s+', ' ', txt(s))

def block(h, cls):
    """Return the substring starting at a view class, up to the next view div."""
    i = h.find(cls)
    if i < 0: return ''
    j = h.find('view view-', i + len(cls))
    return h[i:j if j > 0 else len(h)]

def caption_fields(seg):
    out = {}
    for m in re.finditer(r'(?is)<div class="div-caption[^"]*">(.*?)</div>\s*<div class="div-value">(.*?)</div>', seg):
        out[sq(m.group(1)).rstrip(':').strip()] = sq(m.group(2))
    return out

def refs(seg):
    out = []
    for m in re.finditer(r'(?is)<div class="scholarship-references[^"]*"[^>]*>(.*?)</div>', seg):
        c = m.group(1)
        t = re.search(r'(?is)title="Source"[^>]*>(.*?)</span>', c)
        n = re.search(r'(?is)title="Note"[^>]*>(.*?)</span>', c)
        nid = re.search(r'href="/node/(\d+)', c)
        out.append({'source': sq(t.group(1)) if t else '',
                    'source_node': nid.group(1) if nid else '',
                    'note': sq(n.group(1)).lstrip(', ') if n else ''})
    return out

def activities(h):
    seg = block(h, 'view-person-activities')
    out = []
    for c in re.findall(r'(?is)<li class="row">(.*?)</li>', seg):
        y = dict(re.findall(r'(?is)class="year([12])"[^>]*>(.*?)</span>', c))
        def g(t):
            m = re.search(r'(?is)<span[^>]*title="%s"[^>]*>(.*?)</span>' % t, c)
            return sq(m.group(1)) if m else ''
        inst_n = re.search(r'(?is)href="/node/(\d+)\s*"[^>]*>\s*<span title="Institution"', c)
        city_n = re.search(r'(?is)href="/node/(\d+)\s*"[^>]*>\s*<span title="City"', c)
        out.append({
            'year_from': sq(y.get('1', '')), 'year_to': sq(y.get('2', '')),
            'kind': g('Activity kind'), 'study_level': g('Study level'),
            'profession': g('Profession').lstrip('| ').strip(),
            'institution': g('Institution'), 'institution_node': inst_n.group(1) if inst_n else '',
            'city': g('City'), 'city_node': city_n.group(1) if city_n else '',
            'refs': refs(c),
        })
    return out

people = []
for f in sorted(glob.glob('people/*.html')):
    node = os.path.basename(f)[:-5]
    h = open(f, encoding='utf-8').read()
    ident = block(h, 'view-person-identity')
    name = re.search(r'(?is)<div class="clearfix title-identity"><div class="div-value">(.*?)</div>', ident)
    rtl = re.search(r'(?is)<div class="clearfix rtl-fullname[^"]*"><div class="div-value">(.*?)</div>', ident)
    fld = caption_fields(ident)
    cb = re.search(r'(?is)City of birth:\s*</div><div class="div-value"><a href="/node/(\d+)', ident)
    photo = re.search(r'(?is)field-content"><a href="(https://www\.mideastmed\.org/sites/default/files/field/photo/[^"]+)"', h)
    people.append({
        'node': node,
        'url': 'https://www.mideastmed.org/node/' + node,
        'name': sq(name.group(1)) if name else '',
        'name_rtl': sq(rtl.group(1)) if rtl else '',
        'year_of_birth': fld.get('Year of birth', ''),
        'year_of_death': fld.get('Year of death', ''),
        'profession': fld.get('Profession', ''),
        'city_of_birth': fld.get('City of birth', ''),
        'city_of_birth_node': cb.group(1) if cb else '',
        'religion': fld.get('Religion', ''),
        'gender': fld.get('Gender', ''),
        'photo_url': photo.group(1) if photo else '',
        'bibliographic_references': refs(block(h, 'view-any-further-info')),
        'activities': activities(h),
    })

json.dump(people, open('mideastmed_haifa_govhosp.json', 'w'), ensure_ascii=False, indent=1)
print('people:', len(people))
print('with rtl name:', sum(1 for p in people if p['name_rtl']))
print('with photo:', sum(1 for p in people if p['photo_url']))
print('total activities:', sum(len(p['activities']) for p in people))
print('total bib refs:', sum(len(p['bibliographic_references']) for p in people))
