// What the map pies are cut by. Both map tabs draw the same kind of pie — one
// place, sliced by a dimension of its admissions — and either dimension can be
// the cut: Community, as the maps first shipped, or the ICD-9 chapter, the
// diagnosis grouping the Statistics page uses.
//
// The slices of a pie on a map have to be few and fixed. Nineteen chapters are
// neither, so the chapter cut keeps the eight commonest in the whole registry —
// the same eight the Statistics pie shows before its Others slice — and folds
// the rest into one residue. The eight are ranked on the full dataset, never on
// the admissions a date range leaves, so a chapter does not change colour or
// fall into the residue as the range narrows.
//
// Two further cuts look inside one part of the registry rather than across all
// of it: the infectious diseases alone, cut by disease, and the Jewish patients
// alone, cut by the nationality the clerk wrote. A pie in either is sized by
// that part only, so a place with no such admissions drops off the map.
import { useState } from 'react';
import { RegistryRecord } from './types';
import { UNKNOWN, facetValue } from './facets';
import { buildColorScale, colorsForRanked, semanticColor, RESIDUE, NEUTRAL, SERIES } from './colors';
import { GROUP_COLUMN, GROUP_DIM, PALESTINIAN_ARAB, DRUZE, JEWISH, BRITISH_CHRISTIAN, OTHER } from './groups';

export type PieMode = 'community' | 'chapter' | 'infectious' | 'jewishNationality';

export const PIE_MODES: { key: PieMode; label: string }[] = [
  { key: 'community', label: 'Community' },
  { key: 'chapter', label: 'Diagnosis (ICD-9 chapter)' },
  { key: 'infectious', label: 'Infectious diseases only' },
  { key: 'jewishNationality', label: 'Jewish patients by nationality' }
];

export interface PieScheme {
  mode: PieMode;
  /** What a slice is, singular, for the help lines and the side panel. */
  noun: string;
  /** The slices, in a fixed order round the pie, the blank last. */
  keys: string[];
  color: (k: string) => string;
  /** The slice's name for a legend or a chip. */
  label: (k: string) => string;
  /** The slice a record falls in. */
  bucket: (row: RegistryRecord) => string;
  /** Columns the record export should carry for this cut. */
  exportColumns: string[];
  /** For a cut of one part of the registry: which records belong to it.
   *  Absent, every record counts. */
  include?: (row: RegistryRecord) => boolean;
  /** That part, as it reads before "records" in a count. */
  subset?: string;
  /** A long-named cut gets a single-column legend. */
  wideLegend?: boolean;
}

export const CHAPTER_COLUMN = 'ICD-9 Chapter';
const CHAPTER_TOP_N = 8;
export const OTHER_CHAPTERS = 'Other chapters';

export const communityScheme: PieScheme = {
  mode: 'community',
  noun: 'community',
  // Same order everywhere, so two pies can be read against each other at a
  // glance; the unrecorded last, in the neutral grey every chart gives a blank.
  keys: [PALESTINIAN_ARAB, DRUZE, JEWISH, BRITISH_CHRISTIAN, OTHER, UNKNOWN],
  color: k => semanticColor(GROUP_DIM, k),
  label: k => k,
  bucket: row => facetValue(row[GROUP_COLUMN]),
  exportColumns: [GROUP_COLUMN]
};

// "001-139 Infectious and parasitic diseases" → "Infectious and parasitic
// diseases": the code range is for the coder, and a legend has no room for it.
const chapterName = (k: string) => k.replace(/^[VE]?\d+-[VE]?\d+\s+/, '');

export const chapterScheme = (fullData: RegistryRecord[]): PieScheme => {
  const counts = new Map<string, number>();
  fullData.forEach(row => {
    const v = facetValue(row[CHAPTER_COLUMN]);
    if (v !== UNKNOWN) counts.set(v, (counts.get(v) || 0) + 1);
  });
  const top = [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, CHAPTER_TOP_N)
    .map(([k]) => k);
  const kept = new Set(top);
  // Built exactly as the Statistics page builds its chapter scale, so a
  // chapter is the same hue on the map as on the pie there.
  const scale = buildColorScale(fullData, CHAPTER_COLUMN, 'Chapter');
  return {
    mode: 'chapter',
    noun: 'chapter',
    keys: [...top, OTHER_CHAPTERS, UNKNOWN],
    color: k => (k === OTHER_CHAPTERS ? RESIDUE : scale(k)),
    label: k => (k === UNKNOWN ? 'No ICD-9 code' : chapterName(k)),
    bucket: row => {
      const v = facetValue(row[CHAPTER_COLUMN]);
      return v === UNKNOWN || kept.has(v) ? v : OTHER_CHAPTERS;
    },
    exportColumns: ['Diagnosis as written', 'ICD-9 Code', CHAPTER_COLUMN],
    wideLegend: true
  };
};

// The infectious diseases, cut by disease. A three-digit ICD-9 category is
// the disease; where ICD-9 itself groups several categories under one name —
// tuberculosis 010–018, the rickettsioses 080–083, the intestinal infections
// 001–009 — the group is the slice, so the 1936 typhus split across 080 and
// 081 shows as one, and typhoid (002) keeps its own slice out of 001–009.
// The groups are fixed here rather than ranked, but are the eight largest in
// the whole registry, in that order (typhoid 2,356 down to erysipelas 317; the
// helminths, next, are 198); everything else in the chapter pools. Typhoid is
// tested before 001–009, so it never falls into the intestinal slice.
const INFECTIOUS_PREFIX = '001-139';
const INFECTIOUS_GROUPS: { key: string; test: (cat: number) => boolean }[] = [
  { key: 'Typhoid and paratyphoid', test: c => c === 2 },
  { key: 'Malaria', test: c => c === 84 },
  { key: 'Other intestinal infections', test: c => c >= 1 && c <= 9 },
  { key: 'Tuberculosis', test: c => c >= 10 && c <= 18 },
  { key: 'Sandfly fever', test: c => c === 66 },
  { key: 'Typhus and other rickettsioses', test: c => c >= 80 && c <= 83 },
  { key: 'Diphtheria', test: c => c === 32 },
  { key: 'Erysipelas', test: c => c === 35 }
];
export const OTHER_INFECTIOUS = 'Other infectious diseases';

// The category from the code when the category column is blank: "32.9" and
// "032.9" are both 032, and a second code after "|" is the record's other one.
const categoryOf = (row: RegistryRecord): number | null => {
  const raw = facetValue(row['ICD-9 Category']) !== UNKNOWN ? row['ICD-9 Category'] : row['ICD-9 Code'];
  const m = String(raw ?? '').split('|')[0].trim().match(/^(\d+)/);
  return m ? Number(m[1]) : null;
};

export const infectiousScheme: PieScheme = {
  mode: 'infectious',
  noun: 'disease',
  keys: [...INFECTIOUS_GROUPS.map(g => g.key), OTHER_INFECTIOUS],
  color: k => (k === OTHER_INFECTIOUS ? RESIDUE : SERIES[INFECTIOUS_GROUPS.findIndex(g => g.key === k)] ?? NEUTRAL),
  label: k => k,
  bucket: row => {
    const c = categoryOf(row);
    return (c !== null && INFECTIOUS_GROUPS.find(g => g.test(c))?.key) || OTHER_INFECTIOUS;
  },
  exportColumns: ['Diagnosis as written', 'Diagnosis', 'ICD-9 Code', CHAPTER_COLUMN],
  include: row => String(row[CHAPTER_COLUMN] ?? '').startsWith(INFECTIOUS_PREFIX),
  subset: 'infectious-disease',
  wideLegend: true
};

// The Jewish patients, cut by the Nationality column — the state the clerk
// wrote, which before 1948 means citizenship: a Palestinian Jew is one
// naturalised under the Mandate, not one born in the country. The eight
// commonest among the Jewish records of the whole registry keep a slice; the
// rest pool. Their colours are ranked among the Jewish records too, not taken
// from the Statistics page's Nationality pie: there Austrian, Latvian and
// Czechoslovakian fall past the eighth hue and would wrap onto Polish and
// German. Atlit's register
// (notebook 25) wrote no nationality, so its pie is all grey.
const NATIONALITY_TOP_N = 8;
export const OTHER_NATIONALITIES = 'Other nationalities';

export const jewishNationalityScheme = (fullData: RegistryRecord[]): PieScheme => {
  const jewish = fullData.filter(r => facetValue(r['Religion']) === JEWISH);
  const counts = new Map<string, number>();
  jewish.forEach(row => {
    const v = facetValue(row['Nationality']);
    if (v !== UNKNOWN) counts.set(v, (counts.get(v) || 0) + 1);
  });
  const top = [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, NATIONALITY_TOP_N)
    .map(([k]) => k);
  const kept = new Set(top);
  const scale = colorsForRanked('Nationality', top);
  return {
    mode: 'jewishNationality',
    noun: 'nationality',
    keys: [...top, OTHER_NATIONALITIES, UNKNOWN],
    color: k => (k === OTHER_NATIONALITIES ? RESIDUE : scale(k)),
    label: k => (k === UNKNOWN ? 'No nationality written' : k),
    bucket: row => {
      const v = facetValue(row['Nationality']);
      return v === UNKNOWN || kept.has(v) ? v : OTHER_NATIONALITIES;
    },
    exportColumns: ['Religion', 'Nationality as written', 'Nationality'],
    include: row => facetValue(row['Religion']) === JEWISH,
    subset: 'Jewish'
  };
};

/** The scheme for a mode; the ranked cuts rank on the whole registry. */
export const schemeFor = (mode: PieMode, fullData: RegistryRecord[]): PieScheme =>
  mode === 'chapter' ? chapterScheme(fullData)
  : mode === 'infectious' ? infectiousScheme
  : mode === 'jewishNationality' ? jewishNationalityScheme(fullData)
  : communityScheme;

/**
 * The cut the reader last chose, shared by both map tabs: switching to
 * diagnoses on the Map and then opening Haifa should not silently switch back.
 */
export const usePieMode = (): [PieMode, (m: PieMode) => void] => {
  const [mode, setMode] = useState<PieMode>(() => {
    try {
      const saved = localStorage.getItem('map.pieMode');
      return PIE_MODES.some(m => m.key === saved) ? saved as PieMode : 'community';
    }
    catch { return 'community'; }
  });
  const set = (m: PieMode) => {
    try { localStorage.setItem('map.pieMode', m); } catch { /* private window */ }
    setMode(m);
  };
  return [mode, set];
};
