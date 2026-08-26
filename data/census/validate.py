#!/usr/bin/env python3
"""Arithmetic validation of the census transcriptions against the tables' own
marginal totals (row sums, column sums, cross-table identities).
Every failure prints a line; silence per section means all checks passed."""
import csv, sys
from pathlib import Path

HERE = Path(__file__).parent
fails = 0

def check(cond, msg):
    global fails
    if not cond:
        fails += 1
        print("FAIL:", msg)

def load(name):
    with open(HERE / name) as f:
        return list(csv.DictReader(f))

# ---------- age tables ----------
AGES = ["0-1","1-2","2-3","3-4","4-5"]
FIVE = ["0-5","5-10","10-15","15-20","20-25","25-30","30-35","35-40","40-45",
        "45-50","50-55","55-60","60-65","65-70","70-75","75+","not_recorded"]
BLOCKS = ["pop","unmarried","married","divorced","widowed"]

def check_age_table(name):
    rows = load(name)
    data = {}
    for r in rows:
        rec = {k: int(v) for k, v in r.items() if k not in ("religion","age_group")}
        data[(r["religion"], r["age_group"])] = rec
    religions = sorted({r for r, a in data})
    for (rel, age), rec in data.items():
        for b in BLOCKS:
            check(rec[f"{b}_persons"] == rec[f"{b}_males"] + rec[f"{b}_females"],
                  f"{name} {rel} {age}: {b} persons != m+f")
        for s in ("persons","males","females"):
            check(rec[f"pop_{s}"] == sum(rec[f"{b}_{s}"] for b in BLOCKS[1:]),
                  f"{name} {rel} {age}: {s} pop != unm+mar+div+wid")
    for rel in religions:
        for col in [f"{b}_{s}" for b in BLOCKS for s in ("persons","males","females")]:
            check(sum(data[(rel,a)][col] for a in AGES) == data[(rel,"0-5")][col],
                  f"{name} {rel}: {col} single years != 0-5")
            check(sum(data[(rel,a)][col] for a in FIVE) == data[(rel,"total")][col],
                  f"{name} {rel}: {col} age groups != total")
    return data, religions

sd, sd_rel = check_age_table("census-1931-haifa-subdistrict-age.csv")
town, town_rel = check_age_table("census-1931-haifa-town-age.csv")

# sub-district: printed all-religions panel == sum of the four religion panels, cell by cell
for age in AGES + FIVE + ["total"]:
    for col in [f"{b}_{s}" for b in BLOCKS for s in ("persons","males","females")]:
        s = sum(sd[(rel, age)][col] for rel in ("moslems","jews","christians","others"))
        check(s == sd[("all", age)][col],
              f"subdistrict-age {age} {col}: sum of religions {s} != all {sd[('all',age)][col]}")

# ---------- religion by sub-district (1931, total pop) ----------
rel31 = load("census-1931-religion-by-subdistrict.csv")
def key(r): return (r["district"], r["subdistrict"])
units = {}
for r in rel31:
    units.setdefault(key(r), {})[r["religion"]] = tuple(int(r[c]) for c in ("persons","males","females"))
for u, d in units.items():
    tot = tuple(sum(v[i] for rel, v in d.items() if rel != "all") for i in range(3))
    check(tot == d["all"], f"religion-by-subdistrict {u}: religions sum {tot} != all {d['all']}")
for dist in ("Southern","Jerusalem","Northern"):
    for i in range(3):
        for rel in ("all","moslems","jews","christians"):
            s = sum(v[rel][i] for u, v in units.items() if u[0] == dist and u[1] != "ALL" and rel in v)
            check(s == units[(dist,"ALL")][rel][i], f"{dist} {rel}[{i}]: SD sum {s} != district")
for rel in ("all","moslems","jews","christians"):
    for i in range(3):
        s = sum(units[(d,"ALL")][rel][i] for d in ("Southern","Jerusalem","Northern"))
        check(s == units[("Palestine","ALL")][rel][i], f"Palestine {rel}[{i}]: district sum != total")

# ---------- towns (1931) ----------
towns = load("census-1931-towns-religion.csv")
trows = {}
for r in towns:
    trows.setdefault((r["district"], r["town"]), {})[r["religion"]] = tuple(int(r[c]) for c in ("persons","males","females"))
for u, d in trows.items():
    tot = tuple(sum(v[i] for rel, v in d.items() if rel != "all") for i in range(3))
    check(tot == d["all"], f"towns {u}: religions sum != all")
for dist in ("Southern","Jerusalem","Northern"):
    for rel in ("all","moslems","jews","christians","others"):
        for i in range(3):
            s = sum(v[rel][i] for u, v in trows.items() if u[0] == dist and u[1] != "ALL")
            check(s == trows[(dist,"ALL")][rel][i], f"towns {dist} {rel}[{i}]: town sum != district")
for rel in ("all","moslems","jews","christians","others"):
    for i in range(3):
        s = sum(trows[(d,"ALL")][rel][i] for d in ("Southern","Jerusalem","Northern"))
        check(s == trows[("Palestine","ALL")][rel][i], f"towns Palestine {rel}[{i}]")

# town age table vs Table VI Haifa town row
for rel in ("moslems","jews","christians","others"):
    v = trows[("Northern","Haifa")][rel]
    t = town[(rel,"total")]
    check(v == (t["pop_persons"], t["pop_males"], t["pop_females"]),
          f"town-age {rel} total {t['pop_persons']} != Table VI {v}")
# sum of town panels == Table VI all row
for i, c in enumerate(("pop_persons","pop_males","pop_females")):
    s = sum(town[(rel,"total")][c] for rel in town_rel)
    check(s == trows[("Northern","Haifa")]["all"][i], f"town-age all[{i}] {s} != Table VI")

# SD age table vs Table VII Haifa SD row
hsd = units[("Northern","Haifa")]
for rel in ("moslems","jews","christians"):
    t = sd[(rel,"total")]
    check(hsd[rel] == (t["pop_persons"], t["pop_males"], t["pop_females"]), f"sd-age {rel} != Table VII")
oth = tuple(sum(hsd[r][i] for r in ("druzes","bahais","samaritans","no_religion")) for i in range(3))
t = sd[("others","total")]
check(oth == (t["pop_persons"], t["pop_males"], t["pop_females"]), f"sd-age others {oth} != Table VII minors")
t = sd[("all","total")]
check(hsd["all"] == (t["pop_persons"], t["pop_males"], t["pop_females"]), "sd-age all != Table VII")

# ---------- minor religions in towns ----------
minors = load("census-1931-towns-minor-religions.csv")
for r in minors:
    s = sum(int(r[c]) for c in ("druzes","bahais","samaritans","agnostics"))
    tw = next(v for (d, t), v in trows.items() if t == r["town"])
    check(s == tw["others"][0], f"minors {r['town']}: {s} != others {tw['others'][0]}")

# ---------- rural (1931) ----------
rural = load("census-1931-rural-religion.csv")
rrows = {}
for r in rural:
    rrows.setdefault((r["district"], r["subdistrict"]), {})[r["religion"]] = tuple(int(r[c]) for c in ("persons","males","females"))
for u, d in rrows.items():
    tot = tuple(sum(v[i] for rel, v in d.items() if rel != "all") for i in range(3))
    check(tot == d["all"], f"rural {u}: religions sum != all")
for dist in ("Southern","Jerusalem","Northern"):
    for rel in ("all","moslems","jews","christians","others"):
        for i in range(3):
            s = sum(v[rel][i] for u, v in rrows.items() if u[0] == dist and u[1] != "ALL")
            check(s == rrows[(dist,"ALL")][rel][i], f"rural {dist} {rel}[{i}]: SD sum != district")
# urban + rural == sub-district total (all religions column)
town_by_sd = {}
for (dist, twn), v in trows.items():
    if twn == "ALL": continue
    r = next(rr for rr in towns if rr["town"] == twn and rr["religion"] == "all")
    sdname = r["subdistrict"]
    town_by_sd[(dist, sdname)] = tuple(town_by_sd.get((dist, sdname), (0,0,0))[i] + v["all"][i] for i in range(3))
for (dist, sdname), v in rrows.items():
    if sdname == "ALL": continue
    urb = town_by_sd.get((dist, sdname), (0,0,0))
    tot = tuple(urb[i] + v["all"][i] for i in range(3))
    check(tot == units[(dist, sdname)]["all"], f"urban+rural {dist}/{sdname}: {tot} != SD total")

# ---------- christian churches ----------
ch = load("census-1931-christian-churches.csv")
crows = {}
for r in ch:
    crows.setdefault((r["district"], r["subdistrict"]), {})[r["church"]] = tuple(int(r[c]) for c in ("persons","males","females"))
for u, d in crows.items():
    tot = tuple(sum(v[i] for c, v in d.items() if c != "total_christians") for i in range(3))
    check(tot == d["total_christians"], f"churches {u}: denominations sum {tot} != total {d['total_christians']}")
    if u[1] != "ALL":
        check(d["total_christians"] == units[u]["christians"], f"churches {u}: total != Table VII christians")
for dist in ("Southern","Jerusalem","Northern"):
    for church in crows[(dist,"ALL")]:
        s = tuple(sum(v.get(church,(0,0,0))[i] for u, v in crows.items() if u[0]==dist and u[1]!="ALL") for i in range(3))
        check(s == crows[(dist,"ALL")][church], f"churches {dist} {church}: SD sum {s} != district")
for church in crows[("Palestine","ALL")]:
    s = tuple(sum(crows[(d,"ALL")].get(church,(0,0,0))[i] for d in ("Southern","Jerusalem","Northern")) for i in range(3))
    check(s == crows[("Palestine","ALL")][church], f"churches Palestine {church}: {s} != total")

# ---------- 1922 ----------
c22 = load("census-1922-religion.csv")
u22 = {}
for r in c22:
    u22.setdefault((r["scope"], r["district"], r["name"]), {})[r["religion"]] = tuple(int(r[c]) for c in ("persons","males","females"))
for u, d in u22.items():
    tot = tuple(sum(v[i] for rel, v in d.items() if rel != "all") for i in range(3))
    check(tot == d["all"], f"1922 {u}: religions sum != all")
    for rel, v in d.items():
        check(v[0] == v[1] + v[2], f"1922 {u} {rel}: persons != m+f")
for scope in ("urban","rural"):
    for dist in ("Southern","Jerusalem","Northern"):
        dk = (scope, dist, f"{dist} District")
        for rel in ("all","moslems","jews","christians","others"):
            for i in range(3):
                s = sum(v[rel][i] for u, v in u22.items() if u[0]==scope and u[1]==dist and u[2] != f"{dist} District")
                check(s == u22[dk][rel][i], f"1922 {scope} {dist} {rel}[{i}]: unit sum {s} != district {u22[dk][rel][i]}")
    for rel in ("all","moslems","jews","christians","others"):
        for i in range(3):
            s = sum(u22[(scope, d, f"{d} District")][rel][i] for d in ("Southern","Jerusalem","Northern"))
            check(s == u22[(scope,"Palestine","Palestine")][rel][i], f"1922 {scope} Palestine {rel}[{i}]")
for rel in ("all","moslems","jews","christians","others"):
    for i in range(3):
        s = u22[("urban","Palestine","Palestine")][rel][i] + u22[("rural","Palestine","Palestine")][rel][i]
        check(s == u22[("total","Palestine","Palestine")][rel][i], f"1922 urban+rural Palestine {rel}[{i}]")

# ---------- 1945 ----------
cols = ("moslems","jews","christians","others","total")

def vs1945_villages(sd):
    """Row and column checks on one sub-district sheet; returns its TOTAL row.

    Tribal units printed with no figures at all (counted inside another unit)
    have every numeric cell blank and take no part in the sums."""
    rows = load(f"vs1945-{sd.lower()}-subdistrict-villages.csv")
    tot = next(r for r in rows if r["village"] == "TOTAL")
    body = [r for r in rows if r["village"] != "TOTAL" and r["total"] != ""]
    for r in body:
        s = sum(int(r[c]) for c in cols[:4])
        check(s == int(r["total"]), f"vs1945 {sd} {r['village']}: M+J+C+O {s} != total {r['total']}")
    for c in cols:
        s = sum(int(r[c]) for r in body)
        check(s == int(tot[c]), f"vs1945 {sd} column {c}: sum {s} != printed total {tot[c]}")
    return tot

tot_row = vs1945_villages("Haifa")
acre_tot_row = vs1945_villages("Acre")

vss = load("vs1945-subdistrict-summary.csv")
for r in vss:
    s = sum(int(r[c]) for c in cols[:4])
    check(s == int(r["total"]), f"vs1945-summary {r['district']}/{r['subdistrict']}: row sum {s} != total")
for dist in ("Galilee","Samaria","Jerusalem","Lydda"):
    for c in cols + ("villages_and_tribal_units",):
        s = sum(int(r[c]) for r in vss if r["district"] == dist and r["subdistrict"] != "ALL")
        t = next(r for r in vss if r["district"] == dist and r["subdistrict"] == "ALL")
        check(s == int(t[c]), f"vs1945-summary {dist} {c}: SD sum {s} != district {t[c]}")
gt = next(r for r in vss if r["subdistrict"] == "ALL_EXCL_BEERSHEBA")
for c in cols + ("villages_and_tribal_units",):
    s = sum(int(next(r for r in vss if r["district"] == d and r["subdistrict"] == "ALL")[c]) for d in ("Galilee","Samaria","Jerusalem","Lydda"))
    s += int(next(r for r in vss if r["subdistrict"] == "Haifa")[c])
    s += int(next(r for r in vss if r["subdistrict"] == "Gaza")[c])
    check(s == int(gt[c]), f"vs1945-summary grand-excl-Beersheba {c}: {s} != {gt[c]}")
    full = int(gt[c]) + int(next(r for r in vss if r["subdistrict"] == "Beersheba")[c])
    check(full == int(next(r for r in vss if r["district"] == "Palestine" and r["subdistrict"] == "ALL")[c]),
          f"vs1945-summary grand total {c}")
for vs_sd, t in (("Haifa", tot_row), ("Acre", acre_tot_row)):
    row = next(r for r in vss if r["subdistrict"] == vs_sd)
    for c in cols:
        check(int(row[c]) == int(t[c]), f"vs1945 {vs_sd} summary {c} != villages TOTAL")

# ---------- infirmities ----------
INF = ["ins","b1","bl","df","dd"]
NOMADIC = {"Gaza":530,"Beersheba":47981,"Jaffa":4968,"Ramle":3786,
           "Hebron":2001,"Bethlehem":6944,"Jericho":127,"Nablus":216}

def inf_parse(r, keys):
    return {k: (None if r[k] == "" else int(r[k])) for k in keys}

def inf_row_check(rec, label):
    for base in ("pop","cases"):
        check(rec[f"{base}_p"] == rec[f"{base}_m"] + rec[f"{base}_f"], f"{label}: {base} p!=m+f")
    have_inf = all(rec[f"{i}_{c}"] is not None for i in INF for c in ("p","pb","m","mb","f","fb"))
    if have_inf:
        for i in INF:
            check(rec[f"{i}_p"] == rec[f"{i}_m"] + rec[f"{i}_f"], f"{label}: {i} p!=m+f")
            check(rec[f"{i}_pb"] == rec[f"{i}_mb"] + rec[f"{i}_fb"], f"{label}: {i} birth p!=m+f")
            check(rec[f"{i}_pb"] <= rec[f"{i}_p"], f"{label}: {i} birth > total")
        for s in ("p","m","f"):
            check(rec[f"cases_{s}"] == sum(rec[f"{i}_{s}"] for i in INF),
                  f"{label}: cases_{s} != sum of infirmities")
    return have_inf

with open(HERE / "census-1931-infirmities-by-subdistrict.csv") as f:
    inf_sd_rows = list(csv.DictReader(f))
inf_cols = [k for k in inf_sd_rows[0] if k not in ("religion","district","subdistrict","age_group")]
inf_sd = {}
for r in inf_sd_rows:
    rec = inf_parse(r, inf_cols)
    inf_sd[(r["religion"], r["district"], r["subdistrict"])] = rec
    inf_row_check(rec, f"inf-sd {r['religion']} {r['district']}/{r['subdistrict']}")
inf_totals = [c for c in inf_cols if not c.endswith("b")]
for rel in ("all","moslems","christians","jews","others"):
    for dist in ("Southern","Jerusalem","Northern"):
        for col in inf_totals:
            s = sum(v[col] for (rl,d,sdn), v in inf_sd.items() if rl==rel and d==dist and sdn!="ALL")
            check(s == inf_sd[(rel,dist,"ALL")][col], f"inf-sd {rel} {dist} {col}: SD sum {s} != district")
    for col in inf_totals:
        s = sum(inf_sd[(rel,d,"ALL")][col] for d in ("Southern","Jerusalem","Northern"))
        check(s == inf_sd[(rel,"Palestine","ALL")][col], f"inf-sd {rel} Palestine {col}")
for (rl,d,sdn), v in inf_sd.items():
    if rl != "all": continue
    for col in inf_totals:
        s = sum(inf_sd[(r2,d,sdn)][col] for r2 in ("moslems","christians","jews","others"))
        check(s == v[col], f"inf-sd {d}/{sdn} {col}: religions sum {s} != all {v[col]}")
# population dealt with = settled population (total minus nomads, all-Moslem)
for (dist, sdn), d in units.items():
    if sdn == "ALL": continue
    nom = NOMADIC.get(sdn, 0)
    check(inf_sd[("all",dist,sdn)]["pop_p"] == d["all"][0] - nom,
          f"inf-sd all {sdn}: pop {inf_sd[('all',dist,sdn)]['pop_p']} != settled {d['all'][0]-nom}")
    check(inf_sd[("moslems",dist,sdn)]["pop_p"] == d["moslems"][0] - nom,
          f"inf-sd moslems {sdn}: pop != settled moslems")

with open(HERE / "census-1931-infirmities-by-age.csv") as f:
    inf_age_rows = list(csv.DictReader(f))
inf_age = {}
for r in inf_age_rows:
    rec = inf_parse(r, inf_cols)
    inf_age[(r["religion"], r["age_group"])] = rec
    inf_row_check(rec, f"inf-age {r['religion']} {r['age_group']}")
AGE_YEARS = ["0-1","1-2","2-3","3-4","4-5"]
AGE_GROUPS = ["0-5","5-10","10-15","15-20","20-25","25-30","30-35","35-40","40-45",
              "45-50","50-55","55-60","60-65","65-70","70+","not_recorded"]
for rel in ("all","moslems","christians","jews","others"):
    cols = inf_cols if rel in ("all","moslems") else [c for c in inf_cols if c.split("_")[0] in ("pop","cases","ins")]
    for col in cols:
        check(sum(inf_age[(rel,a)][col] for a in AGE_YEARS) == inf_age[(rel,"0-5")][col],
              f"inf-age {rel} {col}: single years != 0-5")
        check(sum(inf_age[(rel,a)][col] for a in AGE_GROUPS) == inf_age[(rel,"total")][col],
              f"inf-age {rel} {col}: age groups != total")
    for col in cols:
        check(inf_age[(rel,"total")][col] == inf_sd[(rel,"Palestine","ALL")][col],
              f"inf-age {rel} total {col} != by-subdistrict Palestine")
for age in AGE_YEARS + AGE_GROUPS:
    for col in [c for c in inf_cols if c.split("_")[0] in ("pop","cases","ins") and not c.endswith("b")]:
        s = sum(inf_age[(r2,age)][col] for r2 in ("moslems","christians","jews","others"))
        check(s == inf_age[("all",age)][col], f"inf-age {age} {col}: religions sum {s} != all")


# ---------- literacy (Table IX A) ----------
LIT_AGES = ["0-7","7-14","14-21","21+","not_recorded"]
def lit_check_rows(rows, keyfn, label):
    data = {}
    for r in rows:
        rec = {k: int(v) for k, v in r.items() if k.split("_")[0] in ("total","literate","illiterate")}
        data[keyfn(r) + (r["age_group"],)] = rec
        lab = f"{label} {keyfn(r)} {r['age_group']}"
        for b in ("total","literate","illiterate"):
            check(rec[f"{b}_p"] == rec[f"{b}_m"] + rec[f"{b}_f"], f"{lab}: {b} p!=m+f")
        for s_ in ("p","m","f"):
            check(rec[f"total_{s_}"] == rec[f"literate_{s_}"] + rec[f"illiterate_{s_}"],
                  f"{lab}: lit+ill != total ({s_})")
    units_ = sorted({k[:-1] for k in data})
    for u in units_:
        for col in data[u + ("total",)]:
            check(sum(data[u + (a,)][col] for a in LIT_AGES) == data[u + ("total",)][col],
                  f"{label} {u} {col}: ages != total")
    return data

litd = lit_check_rows(load("census-1931-literacy-by-district.csv"),
                      lambda r: (r["district"], r["religion"]), "lit-district")
for dist in ("Palestine","Southern","Jerusalem","Northern"):
    for age in LIT_AGES + ["total"]:
        for col in litd[("Palestine","all","total")]:
            s_ = sum(litd[(dist, rel, age)][col] for rel in ("moslems","jews","christians","others"))
            check(s_ == litd[(dist,"all",age)][col], f"lit-district {dist} {age} {col}: religions sum != all")
for rel in ("all","moslems","jews","christians","others"):
    for age in LIT_AGES + ["total"]:
        for col in litd[("Palestine","all","total")]:
            s_ = sum(litd[(d, rel, age)][col] for d in ("Southern","Jerusalem","Northern"))
            check(s_ == litd[("Palestine",rel,age)][col], f"lit-district Palestine {rel} {age} {col}")
# settled-population basis agrees with infirmities table
for dist in ("Palestine","Southern","Jerusalem","Northern"):
    for rel in ("all","moslems","jews","christians","others"):
        k = ("Palestine","ALL") if dist == "Palestine" else (dist,"ALL")
        rel2 = {"jews":"jews"}.get(rel, rel)
        check(litd[(dist,rel,"total")]["total_p"] == inf_sd[(rel2,)+k]["pop_p"],
              f"lit-district {dist} {rel}: total != infirmities pop")

litt = lit_check_rows(load("census-1931-literacy-towns.csv"),
                      lambda r: (r["district"], r["town"], r["religion"]), "lit-towns")
for dist in ("Southern","Jerusalem","Northern"):
    for age in LIT_AGES + ["total"]:
        for col in litd[("Palestine","all","total")]:
            s_ = sum(v for k, v2 in litt.items() for c, v in [(0,0)] if False)
            if dist == "Jerusalem" and age in ("0-7","21+") and col in ("total_p","total_f","illiterate_p","illiterate_f"):
                continue  # printed district row disagrees with printed town rows by 10 (source misprint)
            s_ = sum(litt[k][col] for k in litt
                     if k[0] == dist and k[1] != "ALL" and k[2] == "all" and k[3] == age)
            check(s_ == litt[(dist,"ALL","all",age)][col], f"lit-towns {dist} {age} {col}: towns sum != district")
for town in ("Jaffa","Tel Aviv","Jerusalem","Haifa"):
    dist = {"Jaffa":"Southern","Tel Aviv":"Southern","Jerusalem":"Jerusalem","Haifa":"Northern"}[town]
    for age in LIT_AGES + ["total"]:
        for col in litd[("Palestine","all","total")]:
            if town == "Jaffa" and age in ("total","not_recorded") and col.split("_")[0] in ("literate","illiterate") and not col.endswith("m"):
                continue  # all-religions row disagrees with religion panels by 2 (source misprint)
            s_ = sum(litt[(dist,town,rel,age)][col] for rel in ("moslems","jews","christians","others"))
            check(s_ == litt[(dist,town,"all",age)][col], f"lit-towns {town} {age} {col}: religions sum != all")
# town totals match Table VI
for (d, t), v in trows.items():
    if t == "ALL": continue
    if (d, t, "all", "total") in litt:
        rec = litt[(d, t, "all", "total")]
        check((rec["total_p"], rec["total_m"], rec["total_f"]) == v["all"],
              f"lit-towns {t}: total != Table VI")


# ---------- age tables for all districts and sub-districts (Table VIII Parts I-II) ----------
SD_AGES = ["0-1","1-2","2-3","3-4","4-5"]
SD_GROUPS = ["0-5","5-10","10-15","15-20","20-25","25-30","30-35","35-40","40-45",
             "45-50","50-55","55-60","60-65","65-70","70-75","75+","not_recorded"]
sda = {}
for r in load("census-1931-subdistricts-age.csv"):
    u = r["unit"] + ("_D" if r["unit_type"] == "district" and r["unit"] == "Jerusalem" else "")
    sda[(u, r["religion"], r["age_group"])] = (int(r["persons"]), int(r["males"]), int(r["females"]))
# fold in Haifa from its own detailed file (population columns)
for (rel, age), rec in sd.items():
    sda[("Haifa", {"all":"all","moslems":"moslems","jews":"jews","christians":"christians","others":"others"}[rel], age)] = \
        (rec["pop_persons"], rec["pop_males"], rec["pop_females"])
SD_UNITS = {"Southern": ["Gaza","Beersheba","Jaffa","Ramle"],
            "Jerusalem_D": ["Hebron","Bethlehem","Jerusalem","Jericho","Ramallah"],
            "Northern": ["Tulkarm","Nablus","Jenin","Nazareth","Beisan","Tiberias","Haifa","Acre","Safad"]}
ALL_UNITS = ["Palestine","Southern","Jerusalem_D","Northern"] + sum(SD_UNITS.values(), [])
# source-level +-1 misprints (each panel's own columns verify; religions disagree with 'all' by one)
# Source-level inconsistencies in Table VIII: each printed panel's own row and
# column sums verify exactly, but different panels of the source contradict each
# other by the tolerance given (persons shifted between adjacent ages or between
# m/f). Values are kept as printed; see README "Transcription notes".
SDA_EXC = {("Hebron","40-45"): 1, ("Hebron","65-70"): 1,
           ("Jerusalem_D","40-45"): 1, ("Jerusalem_D","65-70"): 1,
           ("Northern","50-55"): 1, ("Northern","55-60"): 1, ("Northern","60-65"): 1,
           ("Northern","30-35"): 5, ("Northern","35-40"): 5,
           ("Northern","65-70"): 2, ("Northern","70-75"): 2,
           ("Palestine","40-45"): 1, ("Palestine","50-55"): 1, ("Palestine","55-60"): 1,
           ("Palestine","60-65"): 1, ("Palestine","65-70"): 1}
for u in ALL_UNITS:
    for rel in ("all","moslems","jews","christians","others"):
        for age in SD_AGES + SD_GROUPS + ["total"]:
            p, m, f = sda[(u, rel, age)]
            check(p == m + f, f"sd-age {u} {rel} {age}: p != m+f")
        for i in range(3):
            check(sum(sda[(u,rel,a)][i] for a in SD_AGES) == sda[(u,rel,"0-5")][i],
                  f"sd-age {u} {rel}[{i}]: single years != 0-5")
            check(sum(sda[(u,rel,a)][i] for a in SD_GROUPS) == sda[(u,rel,"total")][i],
                  f"sd-age {u} {rel}[{i}]: age groups != total")
    for age in SD_AGES + SD_GROUPS + ["total"]:
        for i in range(3):
            s2 = sum(sda[(u,rel,age)][i] for rel in ("moslems","jews","christians","others"))
            d2 = s2 - sda[(u,"all",age)][i]
            if d2 and not (abs(d2) <= SDA_EXC.get((u, age), 0)):
                check(False, f"sd-age {u} {age}[{i}]: religions sum {s2} != all {sda[(u,'all',age)][i]}")
for dist, sds in SD_UNITS.items():
    for rel in ("all","moslems","jews","christians","others"):
        for age in SD_AGES + SD_GROUPS + ["total"]:
            for i in range(3):
                s2 = sum(sda[(n,rel,age)][i] for n in sds)
                d2 = s2 - sda[(dist,rel,age)][i]
                if d2 and not (abs(d2) <= SDA_EXC.get((dist, age), 0)):
                    check(False, f"sd-age {dist} {rel} {age}[{i}]: SD sum {s2} != district {sda[(dist,rel,age)][i]}")
for rel in ("all","moslems","jews","christians","others"):
    for age in SD_AGES + SD_GROUPS + ["total"]:
        for i in range(3):
            s2 = sum(sda[(d,rel,age)][i] for d in ("Southern","Jerusalem_D","Northern"))
            d2 = s2 - sda[("Palestine",rel,age)][i]
            if d2 and not (abs(d2) <= SDA_EXC.get(("Palestine", age), 0)):
                check(False, f"sd-age Palestine {rel} {age}[{i}]: district sum {s2} != {sda[('Palestine',rel,age)][i]}")
# totals = settled population (Table VII minus nomads)
for (dist, sdn), dd in units.items():
    if sdn == "ALL":
        u2 = {"Palestine":"Palestine","Southern":"Southern","Jerusalem":"Jerusalem_D","Northern":"Northern"}[dist]
        nom_all = sum(NOMADIC.values()) if dist == "Palestine" else \
                  {"Southern": 530+47981+4968+3786, "Jerusalem": 2001+6944+127, "Northern": 216}[dist]
    else:
        u2, nom_all = sdn, NOMADIC.get(sdn, 0)
    check(sda[(u2,"all","total")][0] == dd["all"][0] - nom_all, f"sd-age {u2}: total != settled")
    check(sda[(u2,"moslems","total")][0] == dd["moslems"][0] - nom_all, f"sd-age {u2}: moslems != settled")
    check(sda[(u2,"jews","total")][0] == dd["jews"][0], f"sd-age {u2}: jews mismatch")
    check(sda[(u2,"christians","total")][0] == dd["christians"][0], f"sd-age {u2}: christians mismatch")

# ---------- occupations (Table XVI Part II(a)) ----------
OCC_COLS = ["total", "earners_males", "earners_females",
            "partly_agriculturists_males", "partly_agriculturists_females",
            "dependants_and_working_dependants"]
OCC_PARENTS = {
    "Southern District": ["Gaza", "Beersheba", "Jaffa", "Ramle"],
    "Jerusalem District": ["Hebron", "Bethlehem", "Jerusalem", "Jericho", "Ramallah"],
    "Northern District": ["Tulkarm", "Nablus", "Jenin", "Nazareth", "Beisan",
                          "Tiberias", "Haifa", "Acre", "Safad"],
    "Four Main Towns": ["Jaffa town", "Tel Aviv town", "Jerusalem town", "Haifa town"],
    "Palestine": ["Southern District", "Jerusalem District", "Northern District"],
}
occ = {}
for r in load("census-1931-occupations-by-unit.csv"):
    occ.setdefault(r["unit"], {})[r["order"]] = [int(r[c]) for c in OCC_COLS]
occ_units = list(occ)
# every order of every unit: total = male earners + female earners + dependants
for u, orders in occ.items():
    for o, v in orders.items():
        check(v[0] == v[1] + v[2] + v[5],
              f"occupations {u} order {o}: total {v[0]} != earners+dependants")
# the 58 orders (plus order 2(a)) sum to TOTAL ALL CLASSES; order 1's six
# sub-orders sum to order 1.  Both hold in all six columns.
TOPS = [o for o in occ["Palestine"] if o != "0" and not o[-1].isalpha()]
ONE_PARTS = ["1a", "1b", "1c", "1d", "1e", "1f"]
for u, orders in occ.items():
    for i in range(6):
        s = sum(orders[o][i] for o in TOPS)
        check(s == orders["0"][i],
              f"occupations {u} {OCC_COLS[i]}: orders sum {s} != all classes {orders['0'][i]}")
        s1 = sum(orders[o][i] for o in ONE_PARTS)
        check(s1 == orders["1"][i],
              f"occupations {u} {OCC_COLS[i]}: order 1 parts {s1} != order 1 {orders['1'][i]}")
# sub-districts sum to districts, districts to Palestine, towns to Four Main Towns
for parent, kids in OCC_PARENTS.items():
    for o in occ[parent]:
        for i in range(6):
            s = sum(occ[k][o][i] for k in kids)
            check(s == occ[parent][o][i],
                  f"occupations {parent} order {o} {OCC_COLS[i]}: parts {s} != {occ[parent][o][i]}")
# TOTAL ALL CLASSES == the settled population of the same unit in Tables VI/VII
for (dist, sdn), d in units.items():
    if sdn == "ALL" or sdn not in occ:
        continue
    check(occ[sdn]["0"][0] == d["all"][0] - NOMADIC.get(sdn, 0),
          f"occupations {sdn}: total all classes != settled population")
for twn in ("Jaffa", "Tel Aviv", "Jerusalem", "Haifa"):
    v = next(vv for (dd, tt), vv in trows.items() if tt == twn)
    check(occ[f"{twn} town"]["0"][0] == v["all"][0],
          f"occupations {twn} town: total all classes != Table VI town total")

# ---------- organized industry, Haifa town (Table XXI Part II) ----------
IND_BLOCKS = ["all religions", "moslems", "jews", "christians", "others"]
# three columns for the population engaged, then five staff categories of eleven
IND_STAFF = [5, 16, 27, 38, 49]
ind = {}
ind_rows = []
for r in load("census-1931-industry-haifa-town.csv"):
    ind[(r["religion"], int(r["column"]), r["industry"])] = int(r["value"])
    if r["industry"] not in ind_rows:
        ind_rows.append(r["industry"])
IND_COLS = sorted({c for _, c, _ in ind})
IND_TOTAL, IND_DETAIL = ind_rows[0], ind_rows[1:]
for b in IND_BLOCKS:
    for c in IND_COLS:
        s = sum(ind[(b, c, i)] for i in IND_DETAIL)
        check(s == ind[(b, c, IND_TOTAL)],
              f"industry {b} col {c}: industries {s} != town total {ind[(b, c, IND_TOTAL)]}")
    for i in ind_rows:
        # engaged persons = males + females, and = the five staff categories
        check(ind[(b, 2, i)] == ind[(b, 3, i)] + ind[(b, 4, i)],
              f"industry {b} {i}: engaged persons != m+f")
        s = sum(ind[(b, base, i)] for base in IND_STAFF)
        check(s == ind[(b, 2, i)],
              f"industry {b} {i}: staff categories {s} != engaged {ind[(b, 2, i)]}")
        for base in IND_STAFF:
            v = [ind[(b, base + k, i)] for k in range(11)]
            check(v[0] == v[1] + v[2], f"industry {b} {i} col {base}: total != m+f")
            check(v[1] == v[3] + v[5] + v[7] + v[9],
                  f"industry {b} {i} col {base}: males != Arabs+Jews+others+non-Palestinian")
            check(v[2] == v[4] + v[6] + v[8] + v[10],
                  f"industry {b} {i} col {base}: females != Arabs+Jews+others+non-Palestinian")
for c in IND_COLS:
    for i in ind_rows:
        s = sum(ind[(b, c, i)] for b in IND_BLOCKS[1:])
        check(s == ind[("all religions", c, i)],
              f"industry col {c} {i}: religions {s} != all {ind[('all religions', c, i)]}")

print(f"{fails} failures" if fails else "ALL CHECKS PASSED")
sys.exit(1 if fails else 0)
