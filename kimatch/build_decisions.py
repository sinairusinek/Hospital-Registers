#!/usr/bin/env python3
"""Build kimatch/city-kima-decisions.tsv from the raw match output.

Combines three provenance layers:
  auto  — grade-A engine matches that passed the Israel/Palestine geo audit
  agent — Claude's adjudication of review-grade rows (obvious variants, garbled
          spellings with a single plausible referent, junk, streets, Haifa
          neighborhoods absent from Kima)
  human — cases decided by the historian in the review session of 2026-08-06
          (Tel Amal split, Kinneret ambiguity, Bethania=Bitanya, pipe policy
          "prefer the finer reading", Bassa=al-Bassa with Haifa|Bassa held
          back, Ghedera held back, Beit Jann/Gan split, Kiryat Naim=Kiryat
          Haim, Degania=Alef, Sdedera/Emek ambiguous, Kishon unmatched)

Wikidata QIDs come from the Kima dump; --resolve additionally queries the
Wikidata API (type-verified via kimatch.data.wikidata.resolve_place) for
matched places whose Kima record lacks a QID.

Usage: python3 kimatch/build_decisions.py [--resolve]
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MATCH_RAW = ROOT / "kimatch" / "match-raw.csv"
DECISIONS = ROOT / "kimatch" / "city-kima-decisions.tsv"
KIMA_DUMP = Path("/Users/sinairusinek/Documents/GitHub/Kimatch/20250126KimaPlacesCSVx.csv")
DATE = "2026-08-06"

# Grade-A rows whose match failed the geo audit; they are re-decided below.
A_OVERRIDES = {"Tel Aviv", "Bethania", "Waldheim", "Carmel", "Bithania|Bethania"}

M, AMB, NKE, JUNK = "matched", "unmatched-ambiguous", "unmatched-no-kima-entry", "unmatched-junk"

# city value -> (decision, kima_id, decided_by, note)
MANUAL = {
    # --- major towns the engine graded C (ambiguous/fuzzy) ---
    "Haifa": (M, 791, "agent", "city, not the district entity"),
    "Hadera": (M, 858, "agent", ""),
    "Tiberias": (M, 807, "agent", ""),
    "Tiberias|Tiberia": (M, 807, "agent", ""),
    "Tiberias|P. & P. Tiberias": (M, 807, "agent", ""),
    "Acre": (M, 71, "agent", ""),
    "Akka": (M, 71, "agent", "Arabic naming tradition of Acre; value kept distinct"),
    "Jerusalem": (M, 691, "agent", "city entry, not sancak/East"),
    "Tel Aviv": (M, 272, "agent", "Tel Aviv-Yafo city, not the district entity"),
    "Jaffa": (M, 629, "agent", ""),
    "Rehovot": (M, 562, "agent", ""),
    "Rehovoth": (M, 562, "agent", ""),
    "Ramleh": (M, 456, "agent", ""),
    "Pardess Hanna": (M, 160, "agent", "Kima has only the merged Pardes Hanna-Karkur entity"),

    # --- Yagur ---
    "Yajour": (M, 771, "agent", "Yagur; Mandate romanization"),
    "Yajour|Yajur": (M, 771, "agent", ""),
    "Yajouj": (M, 771, "agent", "garbled Yajour"),
    "Meshek Yagur": (M, 771, "agent", ""),
    "Meshek Yagour": (M, 771, "agent", ""),

    # --- Zichron Yaakov family ---
    "Zichron Yaakov": (M, 8254, "agent", ""),
    "Zichron Jacob": (M, 8254, "agent", ""),
    "Zikhron Yacov": (M, 8254, "agent", ""),
    "Zicron": (M, 8254, "agent", ""),
    "Zichron Yaacob": (M, 8254, "agent", ""),
    "Zikron Yaacov": (M, 8254, "agent", ""),
    "Zikhron Yacob": (M, 8254, "agent", ""),
    "Zekra Yacov": (M, 8254, "agent", "garbled Zichron Yaakov"),
    "Zichron Yacov": (M, 8254, "agent", ""),
    "P. & P. Zichron Yacob": (M, 8254, "agent", ""),
    "Zichron Jacob|Zichron Yaakov": (M, 8254, "agent", ""),
    "Zichron Yakov|Zichron Yaakov": (M, 8254, "agent", ""),
    "Zichron Yaakov|Bat shlomo - Zichron Jacob": (M, 8254, "agent", "first reading"),

    # --- Afikim family ---
    "Affikim": (M, 554, "agent", ""),
    "Kibutz Affikim": (M, 554, "agent", ""),
    "Kibutz Affikim|Affikim": (M, 554, "agent", ""),
    "Kibutz Affiking|Kibutz Affikim": (M, 554, "agent", ""),
    "Kibbutz Affikim": (M, 554, "agent", ""),
    "Affikin": (M, 554, "agent", ""),
    "Kibutz Affiking": (M, 554, "agent", ""),

    # --- Kiryat Ata (Kfar Ata) family ---
    "Kfar Ata": (M, 477, "agent", "Kfar Ata = pre-1965 name of Kiryat Ata"),
    "Kfar Atta": (M, 477, "agent", ""),
    "Kufr Ata": (M, 477, "agent", ""),
    "Kufr 'Ata": (M, 477, "agent", ""),
    "Kufretta": (M, 477, "agent", ""),
    "Kafaratta": (M, 477, "agent", ""),
    "Kafata": (M, 477, "agent", "garbled Kfar Ata"),
    "Kiryat Ata": (M, 477, "agent", ""),
    "Ata village": (M, 477, "agent", ""),
    "Aten Village": (M, 477, "agent", "garbled Ata village"),

    # --- Kiryat Haim family ---
    "Kiryat Haim": (M, 479, "agent", ""),
    "Kirjat Hayim": (M, 479, "agent", ""),
    "Kiryat Haim|Kiryat-Haim Tribune Amal": (M, 479, "agent", ""),
    "Kiryat-Haim Tribune Amal": (M, 479, "agent", ""),
    "Churipat Hayim": (M, 479, "agent", "garbled Kiryat Haim"),
    "Kiryat Naim": (M, 479, "human", "read as Kiryat Haim (H/N misreading)"),

    # --- Haifa neighborhoods with own Kima entries ---
    "Hadar Hacarmel": (M, 21150, "agent", ""),
    "Had. Hac": (M, 21150, "agent", ""),
    "Had. Hac.|Hadar Hacarmel": (M, 21150, "agent", ""),
    "Hadar Hacarmel|Had. Hac": (M, 21150, "agent", ""),
    "Hadar HaCarmel (Haifa)": (M, 21150, "agent", ""),
    "Hadar Hacarmel (Haifa)": (M, 21150, "agent", ""),
    "Hadar Hacarmel / Haifa": (M, 21150, "agent", ""),
    "Hadar Hacarmel Haifa": (M, 21150, "agent", ""),
    "Hadar [Haifa]": (M, 21150, "agent", ""),
    "Haifa [Hadar HaCarmel]": (M, 21150, "agent", ""),
    "Haddar Carmel": (M, 21150, "agent", ""),
    "Had. Stac": (M, 21150, "agent", "read as Had. Hac. (Hadar Hacarmel)"),
    "Had Stae": (M, 21150, "agent", "read as Had. Hac. (Hadar Hacarmel)"),
    "Haifa|Hadar Hacarmel": (M, 21150, "human", "pipe policy: prefer the finer reading"),
    "Haifa|Hadar Hacarmel Haifa": (M, 21150, "human", "pipe policy: prefer the finer reading"),
    "Haifa|Had. Stac": (M, 21150, "human", "pipe policy; Had. Stac read as Hadar Hac."),
    "Beit Galim": (M, 21063, "agent", "Bat Galim"),
    "Bath Galim|Bath Galim K. H. Bldg": (M, 21063, "agent", ""),
    "Bar Galim": (M, 21063, "agent", "or Kfar Gallim; Bat Galim more likely"),
    "Bat Yalem": (M, 21063, "agent", "garbled Bat Galim"),
    "Coastal Watch Bath-Jalim": (M, 21063, "agent", "coastal-watch post at Bat Galim"),
    "Neveh Shaanan": (M, 21497, "agent", "Haifa's Neve Sha'anan (catchment)"),
    "Neve Shaanan": (M, 21497, "agent", ""),
    "Neve Sha'anan": (M, 21497, "agent", ""),
    "Nve Shaanan (Haifa)": (M, 21497, "agent", ""),
    "Brene Shaanan": (M, 21497, "agent", "garbled Neve Shaanan"),
    "Rumat Neshanan": (M, 21497, "agent", "read as Ramat/Neve Shaanan"),
    "Carmel Ahuza": (M, 21015, "agent", "Ahuza on the Carmel"),
    "W. el Nisnass": (M, 85346, "agent", "Wadi Nisnas"),
    "Wadi Nisnas": (M, 85346, "agent", ""),
    "German Colony": (M, 21139, "agent", "Haifa's German Colony (catchment)"),

    # --- Carmel ---
    "Mount Carmel": (AMB, None, "human", "held for human review: Mount Carmel entity; suggested #1156"),
    "Mt. Carmel": (AMB, None, "human", "held for human review: Mount Carmel entity; suggested #1156"),
    "Hacarmel": (AMB, None, "human", "held for human review: Mount Carmel entity; suggested #1156"),
    "Carmel": (AMB, None, "human", "held for human review: Mount Carmel entity; suggested #1156"),
    "Haifa / Mount Carmel": (AMB, None, "human", "held for human review: Mount Carmel entity; suggested #1156"),
    "Haifa|Mt. Carmel": (AMB, None, "human", "held for human review: Mount Carmel entity; suggested #1156"),
    "Mt. Tabor": (AMB, None, "human", "held for human review: Mount Tabor entity; suggested #5765"),

    # --- settlements: clear variants ---
    "Kiryat Bialik": (M, 866, "agent", ""),
    "Kiryat Motzkin": (M, 481, "agent", ""),
    "Kiryat Yam": (M, 480, "agent", ""),
    "Nesher": (M, 20, "agent", ""),
    "Haifa (Nesher)": (M, 20, "agent", "parenthetical = finer reading"),
    "Benyamina": (M, 21551, "agent", ""),
    "Benjamina": (M, 21551, "agent", ""),
    "Benjamina|Benyamina": (M, 21551, "agent", ""),
    "Benjaminia": (M, 21551, "agent", ""),
    "Benyamina. & Beit-Sacaross": (M, 21551, "agent", "first reading Benyamina"),
    "Nahalal": (M, 38, "agent", ""),
    "Jarit Nahalal": (M, 38, "agent", "garbled; Nahalal"),
    "Kfar Vitkin": (M, 825, "agent", ""),
    "Tulkarem": (M, 73472, "agent", ""),
    "Jenin": (M, 79775, "agent", ""),
    "Ain Harod": (M, 12370, "agent", "generic En Harod; Ihud/Me'uhad split is post-1948"),
    "Ein Haron": (M, 12370, "agent", "garbled Ein Harod"),
    "Kfar Hassidim": (M, 830, "agent", ""),
    "Kfar Hasidim": (M, 830, "agent", ""),
    "Kfar Khassidim": (M, 830, "agent", ""),
    "Kfar Kasidim": (M, 830, "agent", ""),
    "Kfar Hasidim / Kfar Hanoar": (M, 830, "agent", "Kfar Hanoar is the youth village at Kfar Hasidim"),
    "Netanya": (M, 24, "agent", ""),
    "Nathania": (M, 24, "agent", ""),
    "Natania": (M, 24, "agent", ""),
    "Netanya|Nathania": (M, 24, "agent", ""),
    "Natamia": (M, 24, "agent", "garbled Natania"),
    "Naharia": (M, 39, "agent", ""),
    "Migdal": (M, 6904, "agent", "Galilee Migdal (catchment), not Ashkelon's"),
    "Mitzpa": (M, 21700, "agent", "Mitzpa near Tiberias"),
    "Mizpa": (M, 21700, "agent", ""),
    "Kefutz Mizra": (M, 224, "agent", "kibbutz Mizra"),
    "Mizra": (M, 224, "agent", ""),
    "Kiryat Kharoshet": (M, 21920, "agent", ""),
    "Kiriat Haroshet": (M, 21920, "agent", ""),
    "Kfar Kharoshet": (M, 21749, "agent", "Kefar Haroshet, distinct from Kiryat Haroshet"),
    "Kfar Horesh": (M, 820, "agent", "Kefar Hahoresh near Nazareth"),
    "Kfar Nacharish / Nazareth": (M, 820, "agent", "garbled Kfar Hahoresh"),
    "Kfar Nachanesh": (M, 820, "agent", "garbled Kfar Hahoresh"),
    "Ginjar": (M, 929, "agent", "Ginegar"),
    "Kfar Yehezkiel": (M, 832, "agent", ""),
    "Balfuria": (M, 20640, "agent", ""),
    "Ness Ziona": (M, 15, "agent", ""),
    "Degania B": (M, 893, "agent", "explicit Bet"),
    "Dejania": (M, 892, "human", "unqualified Degania read as Alef"),
    "Daganya": (M, 892, "human", ""),
    "Dejani": (M, 892, "human", ""),
    "Rosh Pinna": (M, 14873, "agent", ""),
    "Shafa Amr": (M, 261, "agent", "Shefa-Amr"),
    "Bat Shlomo": (M, 587, "agent", ""),
    "Bat Shlomo near Zammaren|Bat Shlomo": (M, 587, "agent", "Zammaren = Zummarin (Zichron)"),
    "Tantoura": (M, 21005, "agent", "Tantura on the Carmel coast"),
    "Nur El Shams|Nur Shams": (M, 76253, "agent", "Nur Shams detention camp"),
    "Nur Shams": (M, 76253, "agent", ""),
    "Nur El Shams": (M, 76253, "agent", ""),
    "Ekron": (M, 21515, "agent", "modern Ekron village"),
    "Gedera": (M, 341, "agent", ""),
    "Hadeira (Hadera)": (M, 858, "agent", ""),
    "Hadera|Hadera P. & P": (M, 858, "agent", ""),
    "Menahemia Colony": (M, 18297, "agent", "Menahemya"),
    "Sedjerah": (M, 733, "agent", "Sejera = Ilaniyya"),
    "Yavniel Colony": (M, 18477, "agent", ""),
    "Yavneel Colony": (M, 18477, "agent", ""),
    "Bersan|Dept. of Police, Bersan": (M, 613, "agent", "Bersan = Beisan (Bet She'an)"),
    "Vilhelma": (M, 26771, "agent", "Wilhelma Templer colony"),
    "Kafr Hittim": (M, 21908, "agent", ""),
    "Bet Alfa": (M, 563, "agent", ""),
    "Beit Alpha": (M, 563, "agent", ""),
    "Bet Alpha Huleh S/D.|Bet Alpha": (M, 563, "agent", ""),
    "Beit Alfa / Beisan": (M, 563, "agent", "Beit Alfa lies in the Beisan sub-district"),
    "Kfar Yeshua": (M, 19294, "agent", "Kfar Yehoshua"),
    "Kfar Jeshuah": (M, 19294, "agent", ""),
    "Kfar Joshua": (M, 19294, "agent", ""),
    "Kfar Yehoshoua": (M, 19294, "agent", ""),
    "Kefa Tabor": (M, 1666, "agent", "Kfar Tavor"),
    "Mes-hah": (M, 1666, "agent", "Mesha = old name of Kfar Tavor"),
    "Kfar Brandice": (M, 21588, "agent", "Kfar Brandeis"),
    "Beth Shearim": (M, 616, "agent", "the moshav (f. 1936)"),
    "Tel-Yusef": (M, 186, "agent", ""),
    "Tel Yousef": (M, 186, "agent", ""),
    "Tel Joseph": (M, 186, "agent", ""),
    "Sakhnin": (M, 95, "agent", ""),
    "Emek Zevouloun": (AMB, None, "human", "held for human review: Emek Zevulun region entity; suggested #86676"),
    "Emek Hayarden": (AMB, None, "human", "held for human review: Emek ha-Yarden regional entity; suggested #87167"),
    "Na'an": (M, 16, "agent", ""),
    "Defna": (M, 974, "agent", "Dafna"),
    "Hanita": (M, 799, "agent", ""),
    "Kibutz Dalia": (M, 886, "agent", ""),
    "Kibbutz Dalia": (M, 886, "agent", ""),
    "Givat Haim": (M, 910, "agent", "pre-split Giv'at Hayyim"),
    "Givat Adam": (M, 18292, "agent", "read as Giv'at Ada"),
    "Shavei Zion": (M, 21799, "agent", ""),
    "Ashadot Yakov": (M, 26521, "agent", "generic Ashdot Ya'akov; Ihud/Me'uhad split post-1948"),
    "Kfar Yadidia": (M, 831, "agent", "Kfar Yedidya"),
    "Kfar Yideyah": (M, 831, "agent", "garbled Kfar Yedidya"),
    "Beni Brak": (M, 594, "agent", ""),
    "Shar Amakim": (M, 258, "agent", "Sha'ar Ha'amakim"),
    "Ramat Gan": (M, 777, "agent", ""),
    "Maagan": (M, 189, "agent", ""),
    "P.T": (M, 426, "agent", "read as Petah Tikva"),
    "Heazelia": (M, 700, "agent", "garbled Herzlia"),
    "Joknan": (M, 18301, "agent", "garbled Yokneam"),
    "Naffuleh": (M, 18417, "agent", "garbled Affuleh (Afula)"),
    "Affula (Afula)": (M, 18417, "agent", ""),
    "Natseria": (M, 18, "agent", "read as Nazareth"),
    "Natsera (Nazareth)": (M, 18, "agent", ""),
    "Tell Addashume": (M, 280, "agent", "Tel Adashim"),
    "Beit-Zerah": (M, 599, "agent", "Bet Zera"),
    "Tel Chai": (M, 16154, "agent", "Tel Hai"),
    "Kfar Baroukh": (M, 815, "agent", ""),
    "Ein Shemer": (M, 69, "agent", ""),
    "Kfar Jeladim": (M, 21910, "agent", "Kfar Yeladim"),
    "Balad al-Sheikh": (M, 21670, "agent", "own entry; kept distinct from Nesher per project policy"),
    "Irbed": (AMB, None, "agent", "Irbid, Transjordan plausible; foreign location held for human review"),
    "Kafr Yasin": (M, 88951, "agent", "read as Kafr Yasif"),
    "Wadi el Hawareth": (AMB, None, "human", "held for human review: Hefer Valley region entity; suggested #4986"),
    "Galil": (AMB, None, "human", "held for human review: Galilee region entity; suggested #1475"),
    "Abu Shousheh": (AMB, None, "agent", "Kima's Abu Shusha is the Gezer one; the Mishmar Haemek village is absent"),

    # --- human-decided in review session ---
    "Tel Amal": (M, 7, "human", "kibbutz Tel Amal = Nir David (split from Kiryat Amal)"),
    "Kiryat Amal": (NKE, None, "human", "Kiryat Amal near Tivon; no Kima entry"),
    "Kiryat Kamal": (NKE, None, "human", "garbled Kiryat Amal (Tivon)"),
    "Bethania": (M, 16157, "human", "Bitanya above Lake Kinneret"),
    "Bithania|Bethania": (M, 16157, "human", ""),
    "Beit Anya": (M, 16157, "human", ""),
    "Kinneret": (AMB, None, "human", "Kevutsa vs Moshava undecidable"),
    "Kineret": (AMB, None, "human", ""),
    "Kinereth": (AMB, None, "human", ""),
    "Kineret|Kinneret": (AMB, None, "human", ""),
    "Kenereth": (AMB, None, "human", ""),
    "Kinnereth": (AMB, None, "human", ""),
    "Kvutzat Kinereth": (M, 1669, "agent", "explicit kevutsa"),
    "Kinneret (Kibbutz)": (M, 1669, "agent", "explicit kibbutz"),
    "Bassa": (M, 21539, "human", "al-Bassa, western Galilee"),
    "Bassa No 1|Bassa": (M, 21539, "human", "al-Bassa / Bassa Camp"),
    "Bassa I.|Bassa": (M, 21539, "human", ""),
    "Bassa N.1 N.F.D": (M, 21539, "human", ""),
    "Haifa|Bassa": (AMB, None, "human", "held for human review: Haifa's Bassa area vs al-Bassa"),
    "Ghedera": (AMB, None, "human", "held for human review: Hadera vs Gedera"),
    "Beit Jann": (M, 90226, "human", "Druze village, Upper Galilee"),
    "Beit Jan": (M, 90226, "human", ""),
    "Beit Gan": (NKE, None, "human", "Beit Gan by Yavne'el; no Kima entry"),
    "Bet Gan": (NKE, None, "human", ""),
    "Sdedera": (M, 858, "human", "user ruling: garbled Hadera"),
    "Sdedead": (M, 858, "human", "user ruling: garbled Hadera"),
    "Emek": (AMB, None, "human", "region nickname without clean referent"),
    "Emek R": (AMB, None, "human", ""),
    "Emek R.|Emek": (AMB, None, "human", ""),
    "Kishon": (NKE, None, "human", "Kishon harbour area; river entity rejected"),

    # --- pipe alternations across different towns: ambiguous ---
    "Haifa|Nesher": (M, 20, "human", "user ruling: Nesher"),
    "Haifa|Hedera": (AMB, None, "agent", "two different towns"),
    "Haifa|Ardel Jahud, Haifa": (NKE, None, "human", "finer reading Ard el-Yahud; no Kima entry"),
    "Haifa|Churches Ort": (AMB, None, "agent", "second reading unidentifiable"),
    "Haifa|Dar el Kadkany": (AMB, None, "agent", "second reading unidentifiable"),
    "Haifa|Bourj Billet": (AMB, None, "agent", "second reading unidentifiable"),
    "Haifa / Tel Amal": (AMB, None, "agent", "two different places"),
    "Tiberias / Kinneret": (AMB, None, "agent", ""),
    "Yavne'el / Tiberias": (AMB, None, "agent", ""),
    "Shavei Tzion / Nahariya": (AMB, None, "agent", ""),
    "Kiryat Haim / Kibbutz Amal": (AMB, None, "agent", ""),
    "Tiberias (Kibbutz Afikim?)": (AMB, None, "agent", "editor's guess in source"),

    # --- sub-district values: town link would be wrong granularity ---
    "Haifa s/d": (AMB, None, "agent", "sub-district, not the city"),
    "Haifa S/P": (AMB, None, "agent", ""),
    "Acre S/D": (AMB, None, "agent", ""),
    "Tiberias S/D": (AMB, None, "agent", ""),

    # --- Haifa localities absent from Kima ---
    "Ardel Yahud": (NKE, None, "agent", "Ard el-Yahud, Haifa's old Jewish quarter"),
    "Ardel Yahud|Ard al-Yahud": (NKE, None, "agent", ""),
    "Adel Yahud": (NKE, None, "agent", ""),
    "Hartel Yahud": (NKE, None, "agent", "Harat el-Yahud"),
    "Hart el Yahud": (NKE, None, "agent", ""),
    "Dantel Yahud": (NKE, None, "agent", "garbled Ard/Harat el-Yahud"),
    "Shatel Yahud": (NKE, None, "agent", ""),
    "Nahliel Yahud": (NKE, None, "agent", ""),
    "Kuryat el Yahu": (NKE, None, "agent", ""),
    "Hallissa": (NKE, None, "agent", "Halisa neighborhood"),
    "Hallesa": (NKE, None, "agent", ""),
    "Halisa": (NKE, None, "agent", ""),
    "Hallisa Qrt": (NKE, None, "agent", ""),
    "Kiryat Eliyahu": (NKE, None, "agent", "Haifa neighborhood"),
    "Kiryat Eliahu": (NKE, None, "agent", ""),
    "Sh.Khunat Oadim": (NKE, None, "agent", "Shkhunat Ovdim"),
    "Kurdaneh": (NKE, None, "agent", "Kurdani, by the Na'aman springs"),
    "Waldheim": (NKE, None, "agent", "Galilee Templer colony; Kima has only the Saxony Waldheim"),
    "Turaan": (NKE, None, "agent", "Tur'an village absent from Kima"),
    "Zeeb": (NKE, None, "agent", "al-Zib; only Tel Akhziv site in Kima"),
    "Wadi Kavara": (NKE, None, "agent", "Kabara marshes"),

    # --- streets (real, sub-gazetteer) ---
    "Tabor Street": (NKE, None, "agent", "street"),
    "Herzl Street": (NKE, None, "agent", "street"),
    "Ben Yehuda St": (NKE, None, "agent", "street"),
    "Ben Yehuda Street": (NKE, None, "agent", "street"),
    "Banks St": (NKE, None, "agent", "street"),
    "Doris St": (NKE, None, "agent", "street"),
    "Alya Street": (NKE, None, "agent", "street"),
    "Drachla Tabor St": (NKE, None, "agent", "street"),
    "Ben Yehuda": (AMB, None, "agent", "street vs Even Yehuda"),

    # --- institutions ---
    "Alliance Scool": (NKE, None, "agent", "institution"),
    "Beit Olim": (NKE, None, "agent", "immigrants' hostel"),
    "Bet Olim": (NKE, None, "agent", ""),
    "Beit tatikva": (NKE, None, "agent", "institution"),
    "Ahava": (AMB, None, "agent", "the Ahava children's home?"),

    # --- unresolved real-looking values ---
    "Bethlehem": (AMB, None, "agent", "likely Bethlehem of Galilee (absent from Kima)"),
    "Bathelim K.butz|Bathelim": (AMB, None, "agent", ""),
    "Nachla": (AMB, None, "agent", ""),
    "Nahla": (AMB, None, "agent", ""),
    "Nahlat Yacob": (AMB, None, "agent", ""),
    "Kibbutz Hashomer": (AMB, None, "agent", ""),
    "St. Hashomer": (AMB, None, "agent", ""),
    "Kiryat Gesher": (AMB, None, "agent", ""),
    "Gisr El Majami": (AMB, None, "agent", "Jisr al-Majami / Gesher area"),
    "Ras El Ein": (AMB, None, "agent", ""),
    "Kefar Bireim": (AMB, None, "agent", "Bir'im? kibbutz Bar'am is post-1948"),
    "Salem": (AMB, None, "agent", ""),
    "Tira": (M, 756, "human", "user ruling: Tira/Tireh in this dataset = al-Tira (Tirat Karmel)"),
    "Buriq": (AMB, None, "agent", ""),
    "Khamra": (AMB, None, "agent", ""),
    "Majamil": (AMB, None, "agent", ""),
    "Abu Khalil": (AMB, None, "agent", ""),
    "Dar Awwaj": (AMB, None, "agent", ""),
    "Sajour": (AMB, None, "agent", "Sajur vs Sejera"),
    "Mashmar Hyam": (AMB, None, "agent", "Mishmar HaYam vs Mishmar Haemek"),
    "Kfar Hasharon": (AMB, None, "agent", ""),
    "Kfar Secta": (AMB, None, "agent", ""),
    "Shunat Zarefin": (AMB, None, "agent", "Sarafand?"),
    "Benjamin": (AMB, None, "agent", "Benyamina? surname?"),
    "Tirch": (AMB, None, "agent", ""),
    "Nabi Sha'man Hagelil": (AMB, None, "agent", ""),
    "Carmel Station": (AMB, None, "agent", ""),
    "Kharwa": (AMB, None, "agent", ""),
    "Shezlia": (M, 700, "agent", "by analogy with the Shenglia ruling"),
    "Huleh": (AMB, None, "human", "held for human review: Hula Valley region entity; suggested #3327"),
    "Hammeh": (AMB, None, "human", "held for human review: el-Hamme spa, but Kima entity is the Hammat Gader archaeological site; suggested #4414"),
    "Mount Tabor": (AMB, None, "human", "held for human review: Mount Tabor entity; suggested #5765"),
    "Kafr Branch": (AMB, None, "agent", "Kfar Baruch? Kfar Brandeis?"),

    # --- junk ---
    "[ambiguous_city]": (JUNK, None, "agent", "pipeline marker"),
    "002.2": (JUNK, None, "agent", ""),
    "Is": (JUNK, None, "agent", ""),
    "Kibutz": (JUNK, None, "agent", "generic word"),
    "Shenglia": (M, 700, "human", "user ruling: Shenglia Qrt = Herzliya"),
    "Kiriat Kinzet": (JUNK, None, "agent", ""),
    "Smillel": (JUNK, None, "agent", ""),
    "Staerneck": (JUNK, None, "agent", ""),
    "Ayesdin": (JUNK, None, "agent", ""),
    "Blys": (JUNK, None, "agent", ""),
    "Fot Luq": (JUNK, None, "agent", ""),
    "Nebertz": (JUNK, None, "agent", ""),
    "Halershert": (JUNK, None, "agent", ""),
    "Port Mason": (JUNK, None, "agent", ""),
    "Roy": (M, None, "human", "El-Ro'i by Kiryat Haroshet; no Kima entry, Wikidata only"),
    "Kibbutz Hamarking": (JUNK, None, "agent", ""),
    "Geda": (JUNK, None, "agent", ""),
    "Ramatby": (JUNK, None, "agent", ""),
    "Haim": (JUNK, None, "agent", "fragment"),
}

# City values outside the Jewish-patient queue (they occur only among other
# communities' records) that the historian has ruled on. n_records here counts
# the whole dataset, not the Jewish subset.
# city value -> (decision, kima_id, decided_by, note, n_records_all)
EXTRA = {
    "Tireh": (M, 756, "human", "user ruling: Tira/Tireh in this dataset = al-Tira (Tirat Karmel)", 268),
    "Tire": (M, 756, "human", "user ruling: Tira/Tireh = al-Tira", 5),
    "Tirat Carmel": (M, 756, "human", "", 3),
    "Tireh (Acre Sub District)": (M, 756, "human", "linked per ruling; note the clerk's Acre Sub District qualifier", 2),
    "Tireh Village": (M, 756, "human", "", 1),
    "Tireh-Haifa": (M, 756, "human", "", 1),
    "Tireh, Haifa": (M, 756, "human", "", 1),
    "Haifa|Tireh": (M, 756, "human", "pipe policy: finer reading", 1),
    "Tires": (M, 756, "human", "garbled Tireh", 1),
    "Tires|Tireh": (M, 756, "human", "", 1),
    "Tirat Carmel / Haifa": (M, 756, "human", "", 1),
    "Tireh-Hayark": (M, 756, "human", "garbled suffix", 1),
    "Tireh/Athlit": (AMB, None, "agent", "alternation across two different places", 1),
    "Tirat Zvi": (M, 757, "agent", "kibbutz Tirat Zvi, Bet Shean valley - not al-Tira", 1),
    "Rameh": (M, 77979, "human", "user ruling: Rameh village (al-Rama, Galilee) is not Ramleh", 69),
}

WD_ONLY = {"Roy": "Q11878352"}

QID_RE = re.compile(r"^Q\d+$")


def load_dump():
    places = {}
    with KIMA_DUMP.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            places[r["id"]] = r
    return places


def main() -> None:
    resolve = "--resolve" in sys.argv
    places = load_dump()
    rows = list(csv.DictReader(MATCH_RAW.open(encoding="utf-8", newline="")))

    out_rows, missing = [], []
    for r in rows:
        city, n = r["city"], int(r["n_records"])
        if city in MANUAL:
            decision, kima_id, decided_by, note = MANUAL[city]
        elif r["_grade"] == "A_autolink" and city not in A_OVERRIDES:
            decision, kima_id, decided_by, note = M, int(r["_kima_id"]), "auto", ""
        else:
            missing.append(city)
            continue

        kima_name = qid = qid_source = ""
        if decision == M and kima_id:
            p = places.get(str(kima_id))
            if p is None:
                raise SystemExit(f"kima id {kima_id} for {city!r} not in dump")
            kima_name = p["primary_rom_full"]
            raw_qid = (p["WikiData_Id"] or "").strip()
            if QID_RE.match(raw_qid):
                qid, qid_source = raw_qid, "kima-dump"
        elif decision == M:
            qid, qid_source = WD_ONLY.get(city, ""), "human"
        out_rows.append({
            "city": city, "spelling": city, "n_records": n,
            "kima_id": kima_id if decision == M else "",
            "kima_name_rom": kima_name,
            "wikidata_qid": qid, "qid_source": qid_source, "wikidata_direct": "",
            "decision": decision, "grade": r["_grade"],
            "confidence": r["_confidence"] if decided_by == "auto" else "",
            "decided_by": decided_by, "note": note, "date": DATE,
        })

    for city, (decision, kima_id, decided_by, note, n_all) in EXTRA.items():
        kima_name = qid = qid_source = ""
        if decision == M:
            p = places.get(str(kima_id))
            if p is None:
                raise SystemExit(f"kima id {kima_id} for {city!r} not in dump")
            kima_name = p["primary_rom_full"]
            raw_qid = (p["WikiData_Id"] or "").strip()
            if QID_RE.match(raw_qid):
                qid, qid_source = raw_qid, "kima-dump"
        out_rows.append({
            "city": city, "spelling": city, "n_records": n_all,
            "kima_id": kima_id if decision == M else "",
            "kima_name_rom": kima_name,
            "wikidata_qid": qid, "qid_source": qid_source, "wikidata_direct": "",
            "decision": decision, "grade": "outside-queue",
            "confidence": "", "decided_by": decided_by, "note": note, "date": DATE,
        })

    if missing:
        raise SystemExit(f"{len(missing)} values lack a decision: {missing[:20]} …")

    if resolve:
        sys.path.insert(0, "/Users/sinairusinek/Documents/GitHub/Kimatch")
        from kimatch.data.wikidata import resolve_place
        pending = {}
        for row in out_rows:
            if row["decision"] == M and not row["wikidata_qid"]:
                pending.setdefault(row["kima_id"], []).append(row)
        for kid, group in pending.items():
            name = group[0]["kima_name_rom"]
            query = re.sub(r"\s*\(.*\)$", "", name)
            try:
                hit = resolve_place(query)
            except Exception as exc:
                print(f"  resolve failed for {name}: {exc}", file=sys.stderr)
                continue
            if hit:
                for row in group:
                    row["wikidata_qid"] = hit.qid
                    row["qid_source"] = "wikidata-reconciled"
                print(f"  {name} -> {hit.qid} ({hit.label}: {hit.description})", file=sys.stderr)

    # Independent Wikidata reconciliation of every City value, separate from
    # the QIDs Kima carries. Results are cached so reruns cost nothing; a
    # disagreement with the Kima-derived QID sends the value to review.
    if resolve or "--wikidata" in sys.argv:
        import json
        import time
        sys.path.insert(0, "/Users/sinairusinek/Documents/GitHub/Kimatch")
        from kimatch.data.wikidata import resolve_place
        cache_path = ROOT / "kimatch" / "wikidata-direct-cache.json"
        cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        pending = [r for r in out_rows if r["city"] not in cache]
        for i, row in enumerate(pending):
            query = row["city"].split("|")[0].strip()
            try:
                hit = resolve_place(query)
                cache[row["city"]] = hit.qid if hit else ""
            except Exception as exc:
                print(f"  direct lookup failed for {query}: {exc}", file=sys.stderr)
                continue
            time.sleep(0.15)
            if (i + 1) % 50 == 0:
                print(f"  direct wikidata: {i+1}/{len(pending)}", file=sys.stderr)
                cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0))
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0))
        conflicts = 0
        for row in out_rows:
            direct = cache.get(row["city"], "")
            row["wikidata_direct"] = direct
            if row["decision"] != M or not direct:
                continue
            if "|" in row["city"] or " / " in row["city"]:
                # The direct query used the first reading of an alternation; a
                # mismatch against the finer-reading match is an artifact.
                continue
            if row["wikidata_qid"] and direct != row["wikidata_qid"]:
                conflicts += 1
                flag = f"held for human review: QID conflict - {row['qid_source']} {row['wikidata_qid']} vs direct Wikidata {direct}"
                row["note"] = f"{row['note']}; {flag}" if row["note"] else flag
            elif not row["wikidata_qid"]:
                row["wikidata_qid"], row["qid_source"] = direct, "wikidata-direct"
        print(f"direct wikidata: {sum(1 for r in out_rows if r['wikidata_direct'])} values resolved, {conflicts} conflicts flagged for review")

    out_rows.sort(key=lambda r: (-r["n_records"], r["city"]))
    with DECISIONS.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()), delimiter="\t")
        w.writeheader()
        w.writerows(out_rows)

    matched = [r for r in out_rows if r["decision"] == M]
    rec_total = sum(r["n_records"] for r in out_rows)
    rec_matched = sum(r["n_records"] for r in matched)
    print(f"{DECISIONS.name}: {len(out_rows)} values "
          f"({len(matched)} matched, {len(out_rows)-len(matched)} unmatched); "
          f"records covered: {rec_matched}/{rec_total} ({100*rec_matched/rec_total:.1f}%)")
    with_qid = sum(1 for r in matched if r["wikidata_qid"])
    print(f"matched values with QID: {with_qid}/{len(matched)}")


if __name__ == "__main__":
    main()
