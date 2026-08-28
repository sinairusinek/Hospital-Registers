#!/usr/bin/env python3
"""Build the manifest CSV: one row per file in the Drive collection."""
import csv
import os
from pathlib import Path

S = Path(
    "/private/tmp/claude-501/-Users-sinairusinek-Documents-GitHub-Hospital-Registers"
    "/b7db0c0c-d15e-4325-89a1-2d25996b5d3b/scratchpad"
)
ST = S / "stage"
REPO = Path("/Users/sinairusinek/Documents/GitHub/Hospital-Registers")

# description | provenance | caution | repo path, keyed by staged filename
DESC = {
    "קישורים לסריקות (iiif-pages).tsv": (
        "2,547 שורות: פנקס/עמוד → כתובת IIIF וכתובת צפייה. הדרך לחזור מרשומה אל כתב היד",
        "ספריית אוניברסיטת חיפה, Alma/ExLibris 972HAI_MAIN",
        "",
        "data/public/iiif-pages.tsv",
    ),
    "diagnosis-classification.tsv": (
        "סיווג האבחנות ל-ICD-9",
        "מודל, לפי ההנחיה diagnoses-icd9-v1",
        "",
        "data/public/diagnosis-classification.tsv",
    ),
    "normalization-report.tsv": (
        "כל החלטת מיזוג בנרמול + 95 ערכים בזנב הנדיר (פחות מ-20 רשומות)",
        "pipeline/build.py",
        "מסמך לביקורת, לא נתון סופי",
        "data/public/normalization-report.tsv",
    ),
    "address-corrections.tsv": (
        "תיקוני כתובות",
        "עבודה ידנית",
        "",
        "data/public/address-corrections.tsv",
    ),
    "place-coords.tsv": (
        "קואורדינטות לכל מקום בגזטיר",
        "Kima + Wikidata",
        "שתי רשומות Kima ללא קואורדינטות",
        "data/public/place-coords.tsv",
    ),
    "external-events.tsv": (
        "כרונולוגיה חיצונית לציר הזמן",
        "אצור ביד",
        "טיוטה הממתינה לעריכתך",
        "data/public/external-events.tsv",
    ),
    "city-kima-decisions.tsv": (
        "החלטות זיהוי 437 ערכי City מול הגזטיר ההיסטורי Kima",
        "סשן אדם-בלולאה, 2026-08-06",
        "עמודת decided_by מבחינה בין auto / agent / human",
        "kimatch/city-kima-decisions.tsv",
    ),
    "review-workbook.tsv": (
        "בסיס הראיות שעליו נשענו החלטות Kima",
        "כנ\"ל",
        "",
        "kimatch/review-workbook.tsv",
    ),
    "hand-authored-sources.json": (
        "35 ציטוטים שנקראו ותורגמו ביד (29 אנגלית, 3 ערבית, 3 גרמנית)",
        "קריאה ידנית",
        "אין גנרטור שיבנה אותם מחדש — ערכו כאן",
        "sources/press/hand-authored-sources.json",
    ),
    "sources-registry.json": (
        "278 ציטוטי עיתונות עם קישורי-קבע ל-NLI Veridian והערת קריאה",
        "נוצר מהקריאות בעברית + הקובץ הידני",
        "נוצר אוטומטית — אל תערכו ידנית",
        "data/public/sources-registry.json",
    ),
    "meca-jem-catalogue.txt": (
        "קטלוג ארכיון המזרח התיכון באוקספורד, אוסף Jerusalem & the East Mission GB165-0161",
        "MECA Oxford",
        "",
        "sources/archives/meca-jem-catalogue.txt",
    ),
    "DOH_annual_report_1921.pdf": (
        "דוח מחלקת הבריאות 1921, המקור הסרוק",
        "archive.org",
        "",
        "paper/sources/doh/DOH_annual_report_1921.pdf",
    ),
    "DOH_annual_report_1921.txt": (
        "אותו דוח, שכבת טקסט",
        "OCR",
        "OCR פגום מקומית",
        "sources/archives/doh/DOH_annual_report_1921.txt",
    ),
}

SECTION = {
    "01": "01 הפנקסים · Registers",
    "02": "02 ארכיון המדינה · Israel State Archives",
    "03": "03 דוחות רשמיים · Official reports",
    "04": "04 עיתונות · Press",
    "05": "05 מפקדים · Census",
    "06": "06 סינתזה · Synthesis",
}


def describe(rel: Path, name: str):
    if name in DESC:
        return DESC[name]
    parts = rel.parts
    sub = parts[1] if len(parts) > 1 else ""
    if name.endswith(".html") and "קריאות" in sub:
        return ("קריאה — עולה ל-Drive כמסמך Google Doc, ניתן להערות", "המאגר", "", "")
    if "דוגמאות עמודים" in sub:
        return ("סריקת עמוד פנקס, 2000 פיקסל", "ספריית אוניברסיטת חיפה", "", "data/private/page-cache/")
    if "שיטת החילוץ" in sub:
        return ("ההנחיה שניתנה למודל — שיטת ההתקנה של המהדורה", "המאגר", "", "pipeline/prompts/")
    if "ביקורת תאריכים" in sub:
        return ("עקבות תיקון השנים / מצאי עמודי אמת Transkribus", "pipeline/build.py", "", "data/eval/")
    if "שמות" in sub:
        return (
            "חילוץ נקוב בשם מתיקי הארכיון",
            "ארכיון המדינה",
            "שמות פרטיים לצד מידע רפואי — לא להפצה",
            "data/private/",
        )
    if "איורים" in sub and parts[0].startswith("02"):
        return ("תכנית/מפה שחולצה מתיקי הארכיון", "ארכיון המדינה", "", "paper/sources/isa/figures/")
    if "דוחות המנדט" in sub:
        return (
            "הדוח השנתי לממשלת הוד מלכותו, שכבת טקסט",
            "archive.org report-admin-palestine-*",
            "OCR",
            "sources/archives/mandate-reports/",
        )
    if parts[0].startswith("06"):
        return ("סינתזה / לוח הדפסה", "הפרויקט", "", "paper/")
    if parts[0].startswith("04") and "איורים" in sub:
        return ("לוח איור לפרק העיתונות", "הפרויקט", "", "data/newspapers/figures/")
    return ("", "", "", "")


rows = []
for p in sorted(ST.rglob("*")):
    if p.is_dir() or p.name == ".DS_Store":
        continue
    rel = p.relative_to(ST)
    top = rel.parts[0][:2] if rel.parts[0][:2].isdigit() else ""
    desc, prov, caut, repo = describe(rel, p.name)
    rows.append(
        {
            "סעיף / Section": SECTION.get(top, "— מדריך / guide"),
            "נתיב ב-Drive / Path": str(rel),
            "מה זה / What it is": desc,
            "מקור / Provenance": prov,
            "אזהרה / Caution": caut,
            "גודל / Size (KB)": round(p.stat().st_size / 1024, 1),
            "נתיב במאגר / Repo path": repo,
        }
    )

out = S / "manifest.csv"
with out.open("w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} rows -> {out}")
