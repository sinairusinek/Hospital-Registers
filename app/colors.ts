// Colour follows the value, never its rank in the current selection.
//
// The charts double as filters, so a slice's colour has to survive the click
// that filters on it: if colours were handed out by position in the sorted
// distribution — as they were — then filtering to Muslim patients would repaint
// Christian orange and the two views could not be read against each other.
// Every scale here is therefore built once from the *unfiltered* data.
import { RegistryRecord } from './types';
import { facetValue, UNKNOWN } from './facets';

// Eight categorical hues in a fixed order, validated for colour-vision
// deficiency on a white surface (worst adjacent pair ΔE 9.1 protan, 19.6
// normal). The order is the safety mechanism, not decoration — do not shuffle
// it without re-validating. Three of the eight sit below 3:1 contrast against
// white, which is why every pie keeps its labelled legend.
export const SERIES = [
  '#2a78d6', // blue
  '#eb6834', // orange
  '#1baf7a', // green
  '#eda100', // yellow
  '#e87ba4', // magenta
  '#008300', // deep green
  '#4a3aa7', // violet
  '#e34948'  // red
];

// A blank is an absence, not a category: it gets a neutral grey everywhere, and
// the residue slice a lighter one so the two never read as the same thing.
export const NEUTRAL = '#898781';
export const RESIDUE = '#dcdbd5';
export const OTHERS = 'Others';

// Whether a diagnosis was recorded at all is a statement about the register,
// not about a patient, so it takes no categorical hue. The classified majority
// is the pale residue grey — it is the ground the other two are read against —
// and the absence keeps the neutral grey a blank has everywhere else. Only the
// middle state, a diagnosis the clerk wrote and the coding never reached, is
// coloured, because it is the one that names work still to do.
export const RECORDING: Record<string, string> = {
  'Classified': RESIDUE,
  'Recorded, not classified': SERIES[3], // yellow
  'Not recorded': NEUTRAL
};

// One measure with a meaningful midpoint — a representation ratio, where 1 is
// parity — is a diverging scale, not a categorical one: two hues from a neutral
// centre. Deliberately darker and more saturated than anything in SERIES, since
// these bars carry no category identity and must not be read as one. Worst
// adjacent pair ΔE 21.1 protan, 28.7 normal; both clear 3:1 against white.
export const DIVERGING = {
  above: '#b2182b', // over-represented in the selection
  below: '#2166ac', // under-represented
  muted: '#c9c8c2'  // too few records to say
};

// Values whose colour is fixed by what they mean rather than by how common they
// happen to be, so that the same group is the same colour in every chart, in
// every screenshot, and in anything written about them.
const SEMANTIC: Record<string, Record<string, string>> = {
  Religion: {
    Muslim: SERIES[2],    // green
    Christian: SERIES[1], // orange
    Jewish: SERIES[0]     // blue
  }
};

export type ColorScale = (name: string) => string;

export const buildColorScale = (
  rows: RegistryRecord[],
  key: string | undefined,
  displayName: string
): ColorScale => {
  const semantic = SEMANTIC[displayName] || {};

  const counts = new Map<string, number>();
  rows.forEach(row => {
    const v = facetValue(key && row[key]);
    counts.set(v, (counts.get(v) || 0) + 1);
  });

  // Ties broken by name so the ranking is fully determined by the data and not
  // by the order rows happen to arrive in.
  const ranked = [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([name]) => name);

  const reserved = new Set(Object.values(semantic));
  const pool = SERIES.filter(c => !reserved.has(c));

  const assigned = new Map<string, string>();
  let next = 0;
  ranked.forEach(name => {
    if (name === UNKNOWN) {
      assigned.set(name, NEUTRAL);
    } else if (semantic[name]) {
      assigned.set(name, semantic[name]);
    } else {
      // Past the eighth-commonest value the pool wraps. Those values live in
      // the Others residue unless a filter lifts one into the top eight, so a
      // repeat is possible but rare — and it is still stable, which is the
      // property that matters here.
      assigned.set(name, pool[next % pool.length]);
      next++;
    }
  });

  return (name: string) =>
    name === OTHERS ? RESIDUE : (assigned.get(name) ?? NEUTRAL);
};
