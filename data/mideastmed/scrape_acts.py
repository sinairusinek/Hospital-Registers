import re, html, json
h = open('inst_all.html', encoding='utf-8').read()
lis = re.findall(r'(?is)<li class="row">(.*?)</li>', h)

def sp(chunk, title):
    m = re.search(r'(?is)<span[^>]*title="%s"[^>]*>(.*?)</span>' % title, chunk)
    return html.unescape(re.sub(r'(?s)<[^>]+>', '', m.group(1))).strip() if m else ''

def years(chunk):
    y = re.findall(r'(?is)class="year([12])"[^>]*>(.*?)</span>', chunk)
    d = {k: html.unescape(re.sub(r'(?s)<[^>]+>', '', v)).strip() for k, v in y}
    return d.get('1', ''), d.get('2', '')

out = []
for c in lis:
    m = re.search(r'href="/node/(\d+)\s*"[^>]*>\s*<span title="Person">(.*?)</span>', c, re.I | re.S)
    if not m:
        continue
    y1, y2 = years(c)
    out.append({
        'person_node': m.group(1),
        'name': html.unescape(re.sub(r'(?s)<[^>]+>', '', m.group(2))).strip(),
        'year_from': y1, 'year_to': y2,
        'birth_place': sp(c, 'Born in') and sp(c, 'Place of birth'),
        'birth_year': sp(c, 'Year of birth'),
        'profession': sp(c, 'Profession').lstrip('| ').strip(),
        'activity_kind': sp(c, 'Activity kind'),
        'study_level': sp(c, 'Study level'),
        'person_url': 'https://www.mideastmed.org/node/' + m.group(1),
    })
# birth place lives in an <a> inside par-in, grab separately
for c, rec in zip([c for c in lis if re.search(r'title="Person"', c)], out):
    bp = re.search(r'(?is)<span title="Born in">.*?</span>\s*(?:<a[^>]*>)?<span[^>]*title="(?:Place of birth|City)"[^>]*>(.*?)</span>', c)
    if not bp:
        bp = re.search(r'(?is)title="Born in">\s*b\.\s*</span>\s*<a[^>]*>(.*?)</a>', c)
    if bp:
        rec['birth_place'] = html.unescape(re.sub(r'(?s)<[^>]+>', '', bp.group(1))).strip()

json.dump(out, open('activities.json', 'w'), ensure_ascii=False, indent=1)
print(len(out), 'activities;', len({r['person_node'] for r in out}), 'unique people')
