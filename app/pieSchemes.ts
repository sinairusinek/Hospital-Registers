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
import { useState } from 'react';
import { RegistryRecord } from './types';
import { UNKNOWN, facetValue } from './facets';
import { buildColorScale, semanticColor, RESIDUE } from './colors';
import { GROUP_COLUMN, GROUP_DIM, PALESTINIAN_ARAB, DRUZE, JEWISH, BRITISH_CHRISTIAN, OTHER } from './groups';

export type PieMode = 'community' | 'chapter';

export const PIE_MODES: { key: PieMode; label: string }[] = [
  { key: 'community', label: 'Community' },
  { key: 'chapter', label: 'Diagnosis (ICD-9 chapter)' }
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
    exportColumns: ['Diagnosis as written', 'ICD-9 Code', CHAPTER_COLUMN]
  };
};

/**
 * The cut the reader last chose, shared by both map tabs: switching to
 * diagnoses on the Map and then opening Haifa should not silently switch back.
 */
export const usePieMode = (): [PieMode, (m: PieMode) => void] => {
  const [mode, setMode] = useState<PieMode>(() => {
    try { return localStorage.getItem('map.pieMode') === 'chapter' ? 'chapter' : 'community'; }
    catch { return 'community'; }
  });
  const set = (m: PieMode) => {
    try { localStorage.setItem('map.pieMode', m); } catch { /* private window */ }
    setMode(m);
  };
  return [mode, set];
};
