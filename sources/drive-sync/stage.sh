#!/bin/zsh
# Build the local staging tree that mirrors the Drive folder
#   מאמר לקתדרה/מקורות ראשוניים
# Copies (not symlinks) so rclone sees real files.
set -e
REPO="$(cd "$(dirname "$0")/../.." && pwd)"   # repo root, two levels up
S="${HR_DRIVE_WORKDIR:-$(cd "$(dirname "$0")" && pwd)}"
ST=$S/stage
cd $REPO

rm -rf $ST
mkdir -p $ST

# --- 01 הפנקסים ------------------------------------------------------------
A="$ST/01 הפנקסים"
mkdir -p "$A/דוגמאות עמודים" "$A/שיטת החילוץ" "$A/נתונים נגזרים" "$A/ביקורת תאריכים"
cp data/public/iiif-pages.tsv "$A/קישורים לסריקות (iiif-pages).tsv"
cp data/private/page-cache/*.jpg "$A/דוגמאות עמודים/"
cp pipeline/prompts/gemini-v1.md "$A/שיטת החילוץ/"
cp pipeline/prompts/diagnoses-icd9-v1.md "$A/שיטת החילוץ/"
cp data/public/diagnosis-classification.tsv \
   data/public/normalization-report.tsv \
   data/public/address-corrections.tsv \
   data/public/place-coords.tsv \
   data/public/external-events.tsv "$A/נתונים נגזרים/"
cp kimatch/city-kima-decisions.tsv kimatch/review-workbook.tsv kimatch/README.md \
   "$A/נתונים נגזרים/"
cp data/eval/*.tsv "$A/ביקורת תאריכים/"

# --- 02 ארכיון המדינה -------------------------------------------------------
B="$ST/02 ארכיון המדינה"
mkdir -p "$B/קריאות" "$B/איורים" "$B/חילוצים (שמות — לא להפצה)"
cp data/archives/*.md "$B/קריאות/"
cp paper/sources/isa/figures/*.png "$B/איורים/"
cp data/private/isa-*.tsv data/private/isa-*.txt "$B/חילוצים (שמות — לא להפצה)/"

# --- 03 דוחות רשמיים --------------------------------------------------------
C="$ST/03 דוחות רשמיים"
mkdir -p "$C/דוחות המנדט" "$C/מחלקת הבריאות 1921"
cp sources/archives/mandate-reports/*.txt "$C/דוחות המנדט/"
cp paper/sources/doh/DOH_annual_report_1921.pdf "$C/מחלקת הבריאות 1921/"
cp sources/archives/doh/DOH_annual_report_1921.txt "$C/מחלקת הבריאות 1921/"
cp sources/archives/meca-jem-catalogue.txt "$C/"

# --- 04 עיתונות -------------------------------------------------------------
E="$ST/04 עיתונות"
mkdir -p "$E/קריאות" "$E/ציטוטים" "$E/איורים"
cp data/newspapers/README.md "$E/קריאות/newspapers_README.md"
cp data/newspapers/heb_article_readings.md \
   data/newspapers/hebrew_query_plan.md \
   data/newspapers/MB_HANDOFF.md "$E/קריאות/"
cp data/newspapers/TODO.md "$E/קריאות/newspapers_TODO.md"
cp paper/press-register-cases.md "$E/קריאות/"
cp sources/press/hand-authored-sources.json "$E/ציטוטים/"
cp data/public/sources-registry.json "$E/ציטוטים/"
cp data/newspapers/figures/* "$E/איורים/"

# --- 06 סינתזה --------------------------------------------------------------
G="$ST/06 סינתזה"
mkdir -p "$G/איורים למאמר"
cp paper/hospital-history.html "$G/הסיפור המוסדי — hospital-history.html"
cp paper/timeline.svg.html "$G/"
cp paper/two-buildings-workplan.md "$G/"
cp paper/figures/* "$G/איורים למאמר/" 2>/dev/null || true

find $ST -name '.DS_Store' -delete
echo "staged:"
du -sh $ST
find $ST -type f | wc -l
