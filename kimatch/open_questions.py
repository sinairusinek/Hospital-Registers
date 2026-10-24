#!/usr/bin/env python3
"""The place questions still open, written for Yoni Furas.

Each question names the City values (or town quarters) whose records it
concerns, what the project currently reads, and what we need from him. The
app's Review view shows them with the records and their scan pages
(app/public/data/place-questions.json, staged by copy-data.mjs).

The last two groups are generated: every round-3 value still unidentified
with two or more records, and the gazetteer's technical QID conflicts.

    python3 kimatch/open_questions.py
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data" / "public" / "hospital-registers-normalized.tsv"
DECISIONS = ROOT / "city-kima-decisions.tsv"
WORKBOOK = ROOT / "round3-workbook.tsv"
OUT = ROOT / "open-questions.json"

G1 = "1 · Your own open notes"
G2 = "2 · Places named, but which one?"
G3 = "3 · Where your sheet and the records part ways"
G4 = "4 · Our new readings — please check"
G5 = "5 · Still unidentified"
G6 = "6 · Technical (project team, not for Yoni)"

QUESTIONS = [
    # --- his "check" marks
    dict(id="sarafand", group=G1, title="Sarafand — the camp or the village?",
         question="Your sheet marks Sarafand 'check specifically: can refer to the camp or the village'. Seven Muslim and three Christian patients. Which Sarafand — the British camp at Sarafand al-Amar, either Ramle village, or Sarafand in Lebanon?",
         reading="Held: not on the map.", cities=["Sarafand"]),
    dict(id="jisr-majami", group=G1, title="Jisr el-Majami — village, station or bridge?",
         question="You marked it 'village and station' and gave the bridge's Wikidata item (Q20384748). Several records are police or IPC postings there. One place, or should the station/police post be kept apart from the village?",
         reading="Held.", cities=["Jisr el Majami", "Jisr el Majamie", "Jisr el-Majami", "Gisr El Majami"]),
    dict(id="beit-gan", group=G1, title="Beit Gan — your Q2900552, marked 'check'",
         question="You identified Beit Gan (by Yavne'el, Q2900552) but marked it to check. Is that the settlement these patients came from?",
         reading="On the map at your Q2900552 (Sinai confirmed it, 24 Oct 2026, and added two 'Bet Jan' records from 1937); Beit Gan has no Kima entry (a donation candidate).", cities=["Beit Gan"]),
    dict(id="jabata", group=G1, title="Jabata — which village?",
         question="You read 'Jabata' as Jebata and marked it to check. Is this Jibta, or another village?",
         reading="Held.", cities=["Jabata"]),
    dict(id="raman", group=G1, title="Raman — Rameh?",
         question="You read Raman as Rameh, with 'check'. Our standing ruling is that Rameh is al-Rama in the Galilee, not Ramleh. Same here?",
         reading="Held.", cities=["Raman"]),
    dict(id="tel-shamman", group=G1, title="Tel Shamman — Tel Amal (Nir David)?",
         question="You read it as Tel Amal, with 'check'. Tel Amal was founded 1936 and became Nir David. Is that right for this record?",
         reading="Held.", cities=["Tel Shamman"]),
    dict(id="tabor", group=G1, title="Tabor — Kfar Tavor, or Mount Tabor?",
         question="You read 'Tabor' as Kfar Tavor, with 'check'. Two further records say 'Mount Tabor' / 'Mt. Tabor' (Kadoorie school is there). Village or mountain?",
         reading="Held.", cities=["Tabor", "Mount Tabor", "Mt. Tabor"]),
    dict(id="beit-lahim", group=G1, title="Beit Lahim — Bat Galim, or Bethlehem of Galilee?",
         question="Your sheet: 'Bat Galim or Beit Lehem?', check. Two more records say 'Bethlehem'. We lean to Bethlehem of Galilee (the German Templer colony) for those. And Beit Lahim?",
         reading="Held.", cities=["Beit Lahim", "Beit Lahm", "Bethlehem"]),
    dict(id="hashomer", group=G1, title="Kibbutz Hashomer (Hatzair) — a Haifa group?",
         question="You typed it as a Haifa neighbourhood (and 'Hedera Kibutz' with check). Was this the Hashomer Hatzair urban group in Haifa, or a kibbutz elsewhere (Hadera)?",
         reading="Held.", cities=["Kibbutz Hashomer", "Kibutz"]),
    dict(id="hadar", group=G1, title="Hadar — Hadera, or Hadar HaCarmel?",
         question="You read 'Hadar' as Hedera, with 'check'. These four records say 'Retsof street Hadar', 'Hadar Police Billet', 'Beit Dr … Hadar'. We read them as Hadar HaCarmel. Agree?",
         reading="Hadar HaCarmel (on the map).", cities=["Hadar"]),
    # --- named, not resolved
    dict(id="kinneret", group=G2, title="Kineret — the moshava or the kvutza?",
         question="Kinneret (moshava, 1909) and Kvutzat Kinneret (1913) are a kilometre apart. Is there any way to tell them apart in these records?",
         reading="Sinai's ruling (24 Oct 2026): a bare Kinneret is the moshava (Q2891213); the 9 records whose address says kibbutz / kvutza (or Hashomer Hatzair) go to the kvutza. No record names the moshava outright: tell us if you know otherwise.", cities=["Kineret", "Kinereth", "Kinneret", "Kineret|Kinneret"]),
    dict(id="zarka", group=G2, title="Zarka",
         question="Jisr al-Zarqa, or another Zarqa?", reading="Held.", cities=["Zarka"]),
    dict(id="jdeideh", group=G2, title="Jdeideh / Gdeideh",
         question="al-Judayda by Acre (Jdeideh-Makr), or another Judayda?", reading="Held.", cities=["Jdeideh", "Gdeideh"]),
    dict(id="kurdaneh", group=G2, title="Kurdaneh — Kurdani by Na'aman spring?",
         question="Kurdani has no Kima entry. Is it the Kurdani by the Na'aman spring, near Acre?",
         reading="Held; a Kima donation candidate.", cities=["Kurdaneh", "Kurdani"]),
    dict(id="turkman", group=G2, title="Arab el-Turkman",
         question="Which Turkman group or encampment (Marj ibn Amer / Megiddo area)?", reading="Held.", cities=["Arab Turkman", "Arab el Turkman"]),
    dict(id="nahlat-yacob", group=G2, title="Nahlat Yacob",
         question="Nahalat Ya'akov — where? (Not to be confused with Nahalat Yehuda, which the scans showed is a third toponym near Ard el-Yahud.)",
         reading="Held.", cities=["Nahlat Yacob"]),
    # --- conflicts
    dict(id="rihanieh", group=G3, title="Rihanieh — Haifa sub-district or Safad?",
         question="You identified 'Rihanieh' as al-Rihaniyya in the Haifa sub-district (Q2152846). But records spelled 'Rihaniya' read 'Rihanieh. Safad s/o' — the Circassian Rihaniyya in Upper Galilee. Your four Rihanieh records give no district. Are they Haifa's, or Safad's too?",
         reading="Rihanieh → Haifa's (your ruling); Rihaniya → Safad's (from the address).", cities=["Rihanieh", "Rihaniya"]),
    dict(id="harat-yahud", group=G3, title="Harat al-Yahud and Ard el-Yahud — two places?",
         question="Your sheet gives the Harat al-Yahud rows the Wikidata item of Ard el-Yahud (Q12404212). Following Naor (2019) we keep them apart: Harat al-Yahud inside the old city, evacuated July 1938; Ard el-Yahud outside the walls, founded 1891. Agree?",
         reading="Two places; Harat al-Yahud drawn at Haifa.", neighbourhoods=["Haifa: Harat al-Yahud"]),
    dict(id="kantara", group=G3, title="Kantara — El Qantara East?",
         question="Your sheet types Kantara as a village without a location. The records are mostly Egyptian railway labourers: 'Kantara East', 'P. Railway Kantara', 'Engineering Kantara'. We read El Qantara East, the Suez Canal end of Palestine Railways. Agree?",
         reading="El Qantara East (listed beyond the map's edge).", cities=["Kantara"]),
    # --- our readings
    dict(id="jaba", group=G4, title="Jaba' — the Haifa village",
         question="Addresses read 'Jaba' Haifa s/o', 'Jaba' Hfa S/Dist.' — so we took Jaba' of the Haifa sub-district (Q4118648), not the Jenin one, for all thirty. Right?",
         reading="Jaba' (Haifa).", cities=["Jaba'"]),
    dict(id="ijzim", group=G4, title="Eggim, Eggem, Iggim — Ijzim?",
         question="Twenty Muslim patients from 'Eggim/Eggem/Iggim'; one reads 'Eggem - Haifa'. We read Ijzim, with g for j. Right?",
         reading="Ijzim.", cities=["Eggim", "Eggem", "Iggim"]),
    dict(id="sileh", group=G4, title="Sileh — Silat al-Harithiya?",
         question="Addresses read 'Sileh village, Jenin Sub Dist.', 'Near Affuleh', one 'Nablus Sub District'. We took Silat al-Harithiya. Could some be Silat al-Dhahr?",
         reading="Silat al-Harithiya.", cities=["Sileh", "Silet el Hartieh", "Sileh el Hartieh"]),
    dict(id="hawassa", group=G4, title="Hawassa — the Haifa quarter",
         question="Twenty-eight Muslim patients from 'Hawassa'. We read Harat al-Hawassa, the shack quarter east of Haifa. Right?",
         reading="Haifa (quarter).", cities=["Hawassa"]),
    dict(id="jalameh", group=G4, title="Jalameh — al-Jalama of Haifa?",
         question="'Haifa District Jalameh', 'Jalameh Police Station'. We took al-Jalama of the Haifa sub-district (Q4704113). Right?",
         reading="al-Jalama (Haifa).", cities=["Jalameh"]),
    dict(id="mukhallis", group=G4, title="Harat al-Mukhallis — a quarter of its own",
         question="Forty-three Haifa addresses name Mukhallis ('Mukhallis Street', 'Hartel Mukhalis', 'Beit El Mukhalis'). We treat it as its own quarter around Deir al-Mukhallis, not Halisa. Right?",
         reading="Haifa: Harat al-Mukhallis.", neighbourhoods=["Haifa: Harat al-Mukhallis"]),
    dict(id="khalisa", group=G4, title="Khalsa — the Huleh village; Hallisa — the Haifa quarter",
         question="Of 151 lines spelled Halisa/Hallissa/Khalisa, 146 are clearly the Haifa quarter. Three, spelled 'Khalsa' (1936–38), we read as al-Khalisa in the Huleh. Right? (And one 'Halleesa, Bureen - Nablus' we left alone.)",
         reading="Khalsa → al-Khalisa (Huleh).", cities=["Khalsa"]),
    dict(id="villages", group=G4, title="Mandate villages, not their successors",
         question="Where Kima's entry is the later settlement, we linked the Mandate village: al-Kabri (not Kibbutz Kabri), Sa'sa' (not Kibbutz Sasa), al-Birwa, al-Tira (not Tirat Carmel), Tarshiha (not Ma'alot). Right?",
         reading="Mandate villages.", cities=["Kabri", "Sasa", "Birweh", "Tireh", "Tarshiha"]),
    dict(id="transjordan", group=G4, title="Transjordan — drawn at Salt",
         question="You placed 'Transjordan' at Salt; we did the same for 'Transj', 'T. Jordan'. A country label on a town's point: keep, or leave off the map?",
         reading="Salt.", cities=["Trans-Jordan", "Transjordan", "Trans Jordan", "TransJordanian", "Transj", "T. Jordan"]),
    # --- unresolved
    dict(id="kafr-yashan", group=G5, title="'Kafr Yashan' — which place?",
         question="One Polish Jewish patient, August 1937 (NB17 p11, register no. 1708): the address reads 'Kafr yashan'. The extraction matched it to Kafr Yasif, which we doubt for a Polish Jew. Do you recognise it — a Jewish settlement (Kfar Yehoshua? Kfar Hasidim?) or something else?",
         reading="Held: not on the map.", cities=["Kafr Yashan"]),
    dict(id="arrabeh", group=G5, title="Arrabeh with no district",
         question="Two Arrabas: Arraba of Jenin and Arrabat al-Battuf. Where the address or the page names a district we split them: 21 Jenin, 13 al-Battuf, and four that the scan shows are Ar'ara. These 24 name neither, on the record or the page — we read the scans. Those that name a district run Jenin in 1934–39 and al-Battuf in 1944–47. Is that a pattern you would trust, or is there another way to tell?",
         reading="Held.", cities=["Arrabeh"]),
    dict(id="bassa", group=G5, title="Bassa No. 2 — al-Bassa or Shelomi?",
         question="al-Bassa (Q2915875) and 'Bassa No 2' / Shelomi sit ~1 km apart; the register also has 'Bassa No 1', 'Bassa II. N.F.D.', 'Haifa|Bassa'. Were the numbered Bassas camps? Which records belong to the village?",
         reading="Held (the open Bassa/Shelomi question).", cities=["Bassa No 2", "Haifa|Bassa"]),
    dict(id="features", group=G5, title="Mountains, valleys, regions",
         question="Mount Carmel, the Emek, the Huleh, the Galilee, el-Hamme. Should a patient 'from the Emek' go on the map at all, and where?",
         reading="Held (never auto-linked).", cities=["Mount Carmel", "Carmel", "Hacarmel", "Huleh", "Emek", "Emek Hayarden", "Emek Zevouloun", "Galil", "Hammeh", "Haifa / Mount Carmel", "Haifa|Mt. Carmel"]),
]


def main() -> None:
    csv.field_size_limit(10**9)
    counts: Counter[str] = Counter()
    with DATA.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            if r["Notebook_Number"] != "25":
                counts[r["City"]] += 1
    taken = {c for q in QUESTIONS for c in q.get("cities", [])}
    questions = list(QUESTIONS)

    # Round 3's leftovers: every unidentified value with two or more records.
    rest = []
    if WORKBOOK.exists():
        with WORKBOOK.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                if r["city"] not in taken and counts.get(r["city"], 0) >= 2:
                    rest.append(r["city"])
    if rest:
        questions.append(dict(id="tail", group=G5, title=f"{len(rest)} other unidentified spellings (2+ records each)",
                              question="Spellings no round has resolved. Many are misreadings; the scan link beside each record shows what the clerk wrote. Any you recognise, a word is enough.",
                              reading="Not on the map.", cities=rest))

    # Technical: the gazetteer's QID conflicts. For the project team.
    conflicts = []
    with DECISIONS.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if "QID conflict" in r["note"]:
                conflicts.append(r["city"])
    if conflicts:
        questions.append(dict(id="qid-conflicts", group=G6, title=f"{len(conflicts)} Wikidata conflicts",
                              question="Kima's QID and an independent Wikidata lookup disagree. The independent lookup has been wrong before (Tireh → a village in Iran). Housekeeping for us.",
                              reading="Linked on Kima's QID.", cities=conflicts))

    for q in questions:
        q.setdefault("cities", [])
        q.setdefault("neighbourhoods", [])
    OUT.write_text(json.dumps({"for": "Yoni Furas", "questions": questions}, ensure_ascii=False, indent=1))
    print(f"{OUT.name}: {len(questions)} questions")


if __name__ == "__main__":
    main()
