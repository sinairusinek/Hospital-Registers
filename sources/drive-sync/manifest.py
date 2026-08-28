#!/usr/bin/env python3
"""Rebuild the manifest from what is actually in Drive, not from the staging
tree — so the moved context/ folders and the ISA bulk are covered too."""
import csv
import os
import json
import subprocess
from pathlib import Path

# Working directory: beside these scripts by default, or $HR_DRIVE_WORKDIR.
S = Path(os.environ.get("HR_DRIVE_WORKDIR", Path(__file__).resolve().parent))
D = "jeckedrive:מאמר לקתדרה/מקורות ראשוניים"

out = subprocess.run(
    [str(S / "rc.sh"), "lsjson", D, "-R", "--files-only"],
    capture_output=True, text=True,
)
files = json.loads(out.stdout)

SECTION = {
    "00": "— מדריך / Guide",
    "01": "01 הפנקסים · Registers",
    "02": "02 ארכיון המדינה · Israel State Archives",
    "03": "03 דוחות רשמיים · Official reports",
    "04": "04 עיתונות · Press",
    "05": "05 מפקדים · Census",
    "06": "06 סינתזה · Synthesis",
    "07": "07 ספרות משנית · Secondary literature",
}

# Longest-prefix rules: folder path fragment -> (what it is, provenance, caution, repo path)
RULES = [
    ("01 הפנקסים/דוגמאות עמודים", (
        "סריקת עמוד פנקס, 2000 פיקסל", "ספריית אוניברסיטת חיפה", "",
        "data/private/page-cache/")),
    ("01 הפנקסים/שיטת החילוץ", (
        "ההנחיה שניתנה למודל — שיטת ההתקנה של המהדורה", "הפרויקט", "",
        "pipeline/prompts/")),
    ("01 הפנקסים/ביקורת תאריכים", (
        "עקבות תיקון השנים / מצאי עמודי אמת Transkribus", "pipeline/build.py",
        "מסמכי ביקורת, לא נתון סופי", "data/eval/")),
    ("01 הפנקסים/נתונים נגזרים", (
        "טבלה נגזרת מהקורפוס (סיווג אבחנות, נרמול, כתובות, מקומות, Kima)",
        "pipeline/build.py + kimatch", "", "data/public/, kimatch/")),
    ("02 ארכיון המדינה/תיקים PDF", (
        "תיק ארכיון המדינה במלואו, לפי סימן התיק", "ארכיון המדינה", "",
        "paper/sources/isa/")),
    ("02 ארכיון המדינה/עמודים", (
        "עמוד מרונדר מתיק 000zbri — החזרים חודשיים על מחלות מדבקות 1942–44",
        "ארכיון המדינה", "התיק סרוק כתמונה בלבד; אין שכבת טקסט",
        "paper/sources/isa/pages/")),
    ("02 ארכיון המדינה/איורים", (
        "תכנית/מפה שחולצה מתיקי הארכיון", "ארכיון המדינה", "",
        "paper/sources/isa/figures/")),
    ("02 ארכיון המדינה/קריאות", (
        "קריאה בתיקי הארכיון — מסמך Google Doc, ניתן להערות", "הפרויקט", "",
        "data/archives/")),
    ("02 ארכיון המדינה/חילוצים", (
        "חילוץ נקוב בשם מתיקי הארכיון", "ארכיון המדינה",
        "שמות פרטיים לצד מידע רפואי — לא להפצה", "data/private/")),
    ("03 דוחות רשמיים/דוחות המנדט", (
        "הדוח השנתי לממשלת הוד מלכותו, שכבת טקסט",
        "archive.org report-admin-palestine-*", "OCR פגום מקומית",
        "sources/archives/mandate-reports/")),
    ("03 דוחות רשמיים/מחלקת הבריאות", (
        "דוח מחלקת הבריאות 1921", "archive.org", "",
        "paper/sources/doh/, sources/archives/doh/")),
    ("03 דוחות רשמיים/רשימות מציאה", (
        "רשימת היטים גולמית (grep) מספרי הכחול ומדוחות מחלקת הבריאות",
        "grep מעל שכבת OCR",
        "פלט גולמי; מספרי השורות אינם ניתנים לפענוח — רמז, לא תמלול",
        "data/haifa_hospital_*.txt")),
    ("04 עיתונות/קריאות", (
        "קריאה בקורפוס העיתונות — מסמך Google Doc, ניתן להערות", "הפרויקט", "",
        "data/newspapers/, paper/")),
    ("04 עיתונות/ציטוטים", (
        "ציטוטי עיתונות מוכנים עם קישורי-קבע", "NLI Veridian + קריאה ידנית",
        "sources-registry נוצר אוטומטית — אל תערכו ידנית",
        "sources/press/, data/public/")),
    ("04 עיתונות/איורים", (
        "לוח איור לפרק העיתונות", "הפרויקט", "", "data/newspapers/figures/")),
    ("04 עיתונות/קורפוס", (
        "קורפוס העיתונות: טקסטים מלאים, רשימות היטים וקונקורדנציות",
        "Jrayed / JPress / Compact Memory",
        "התאמות עיתונות-פנקס הן רמזים, לא זיהויים", "data/newspapers/")),
    ("05 מפקדים", (
        "טבלת מפקד או סטטיסטיקת כפרים, תומללה מסריקות",
        "מפקד 1931 (מילס) / Village Statistics 1945",
        "VS-1945 מעוגל לעשרות; 1922 בגבולות 1931", "data/census/")),
    ("06 סינתזה", (
        "סינתזה / לוח הדפסה למאמר", "הפרויקט",
        "קובצי HTML הם דפים עצמאיים — הורידו ופתחו בדפדפן", "paper/")),
    ("01 הפנקסים/תמלולי פנקסים", (
        "תמלול פנקס יחיד, טבלאות מונַנמות (10 מתוך 33)",
        "חילוץ במודל מולטימודלי", "קיצור דרך אל 11-26data — לא עותק",
        "hospitals11-26/")),
    ("07 ספרות משנית/ביבליוגרפיה", (
        "ספרות משנית — פריט ביבליוגרפי",
        "נאסף לצורך המאמר; ראו גיליון 'סקירת ספרות'",
        "קיצור דרך אל תיקיית הביבליוגרפיה — לא עותק", "—")),
    ("01 הפנקסים", ("", "", "", "data/public/")),
]

TOPLEVEL = {
    "00 מדריך — קראו קודם": (
        "המדריך לאוסף: מה נמצא היכן, סדר קריאה, מפתח קיצורים ואזהרות",
        "נכתב לאוסף הזה", "התחילו כאן", "—"),
    "מפת הקבצים": (
        "המסמך הזה — שורה לכל קובץ באוסף", "נוצר מהאוסף עצמו", "", "—"),
}

NAMED = {
    "קישורים לסריקות (iiif-pages).tsv": (
        "2,547 שורות: פנקס/עמוד → כתובת IIIF וכתובת צפייה. הדרך לחזור מרשומה אל כתב היד",
        "ספריית אוניברסיטת חיפה, Alma 972HAI_MAIN", "", "data/public/iiif-pages.tsv"),
    "מאגר הנתונים המלא (xlsx).xlsx": (
        "קיצור דרך אל מאגר הנתונים המלא (לא מונַנם)", "הפרויקט",
        "שמות מלאים — לא להפצה", "—"),
    "מאגר הנתונים המלא (csv).csv": (
        "קיצור דרך אל אותו מאגר בפורמט csv", "הפרויקט",
        "ה-TSV/CSV נכתב בלי מרכאות — כבו את טיפול המרכאות", "—"),
    "רשימת התיקים של אליעזר.xlsx": (
        "קיצור דרך אל רשימת תיקי ארכיון המדינה של אליעזר באומגרטן",
        "אליעזר באומגרטן", "עמודת 'משימות' מחזיקה את מה שנותר לעשות", "—"),
}


def describe(path: str, name: str):
    if name in NAMED:
        return NAMED[name]
    stem = name.rsplit(".", 1)[0]
    if stem in TOPLEVEL:
        return TOPLEVEL[stem]
    if name.endswith("meca-jem-catalogue.txt"):
        return (
            "קטלוג ארכיון המזרח התיכון באוקספורד, אוסף Jerusalem & the East Mission GB165-0161",
            "MECA Oxford", "", "sources/archives/meca-jem-catalogue.txt")
    for frag, vals in RULES:
        if path.startswith(frag):
            return vals
    return ("", "", "", "")


rows = []
for f in files:
    path = f["Path"]
    name = f["Name"]
    top = path[:2] if path[:2].isdigit() else "00"
    desc, prov, caut, repo = describe(path, name)
    rows.append({
        "סעיף / Section": SECTION.get(top, ""),
        "נתיב ב-Drive / Path": path,
        "מה זה / What it is": desc,
        "מקור / Provenance": prov,
        "אזהרה / Caution": caut,
        "גודל / Size (KB)": round(f.get("Size", 0) / 1024, 1) if f.get("Size", 0) > 0 else "",
        "נתיב במאגר / Repo path": repo,
    })

rows.sort(key=lambda r: r["נתיב ב-Drive / Path"])
out_path = S / "manifest.csv"
with out_path.open("w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} rows")
undesc = sum(1 for r in rows if not r["מה זה / What it is"])
print(f"{undesc} rows without a description")
