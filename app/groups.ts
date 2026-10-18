// An alternative to the register's own two columns, not a replacement for them.
//
// The clerks recorded religion and nationality separately, as the Mandate's
// statistics did. Read singly, "Christian" pools British officials with
// Palestinian Arabs and so invents a population that did not exist (see the
// Shared Space view). This grouping crosses the two columns into the lines the
// hospital itself drew: Palestinian Arab, British Christian, Jewish, other.
//
// It is derived once at load time into its own column, so the sidebar facet,
// the pie and its time series treat it like any other dimension, and Religion
// and Nationality stay exactly as they were beside it.
import { RegistryRecord } from './types';
import { UNKNOWN } from './facets';

export const GROUP_COLUMN = 'Religion × nationality';

export const PALESTINIAN_ARAB = 'Palestinian Arab';
export const BRITISH_CHRISTIAN = 'British Christian';
export const JEWISH = 'Jewish';
// Singular on purpose: "Others" is the pies' residue slice, which is not
// clickable, and this is a real value that has to filter.
export const OTHER = 'Other';

// As in pipeline/shared_space_figures.py: "Palestinian British" is 27 rows but
// sits on the British side of the line the register draws.
const BRITISH_NAT = new Set(['British', 'Palestinian British']);
// Compound nationalities ("Palestinian Syrian") are not Palestinian here, again
// as in the pipeline; they fall to Other.
const PALESTINIAN_NAT = 'Palestinian';
// "Arab" is written in the religion column of eight admissions; with Palestinian
// nationality it is a Palestinian Arab by the register's own words.
const ARAB_RELIGIONS = new Set(['Muslim', 'Christian', 'Arab']);

export const groupOf = (religion: unknown, nationality: unknown): string => {
  const rel = String(religion ?? '').trim();
  const nat = String(nationality ?? '').trim();
  if (rel === '' || rel === 'null') return UNKNOWN;
  // Nationality does not change membership here: a Polish-born Jew and a
  // Palestinian-national one are both in the Jewish group.
  if (rel === 'Jewish') return JEWISH;
  if (rel === 'Christian' && BRITISH_NAT.has(nat)) return BRITISH_CHRISTIAN;
  if (ARAB_RELIGIONS.has(rel) && nat === PALESTINIAN_NAT) return PALESTINIAN_ARAB;
  // A Muslim or Christian with no nationality cannot be placed on either side
  // of the Palestinian/foreign line, so the gap is reported, not guessed.
  if ((rel === 'Muslim' || rel === 'Christian') && (nat === '' || nat === 'null')) return UNKNOWN;
  return OTHER;
};

// Plain names first, the consolidated TSV's after, as everywhere else.
const RELIGION_ALIASES = ['religion', 'standardized religion', 'standardized_religion'];
const NATIONALITY_ALIASES = ['nationality', 'standardnationality', 'standard_nationality'];

const findKey = (keys: string[], aliases: string[]) => {
  for (const alias of aliases) {
    const found = keys.find(k => k.toLowerCase().trim() === alias);
    if (found) return found;
  }
  return undefined;
};

/** Adds GROUP_COLUMN to every row in place. A file without both columns is left alone. */
export const addGroupColumn = (rows: RegistryRecord[], keys: string[]) => {
  const relKey = findKey(keys, RELIGION_ALIASES);
  const natKey = findKey(keys, NATIONALITY_ALIASES);
  if (!relKey || !natKey) return;
  rows.forEach(row => {
    const g = groupOf(row[relKey], row[natKey]);
    // Stored as null rather than the label, like any blank, so the facet,
    // the pie and the time series bucket it through facetValue as usual.
    row[GROUP_COLUMN] = g === UNKNOWN ? null : g;
  });
};
