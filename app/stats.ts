// Representation arithmetic: how a selection's composition differs from the
// registry's own.
//
// The pies answer "who is in this selection". They cannot answer the question
// that a claim about, say, typhoid actually rests on: whether the Jewish share
// of typhoid admissions is larger than the Jewish share of admissions at large.
// That is a ratio of two shares, and it needs a denominator the pies never draw.
//
// Everything here is a ratio of an observed count to an expected one, so a
// single definition and a single confidence interval cover both the crude and
// the standardized figure.
import { RegistryRecord } from './types';
import { facetValue } from './facets';

export interface LiftRow {
  name: string;
  /** Records of this value inside the selection. */
  observed: number;
  /** Records of this value in the whole registry. */
  registryN: number;
  /** Share of the selection that this value accounts for. */
  selectionShare: number;
  /** Share of the registry that this value accounts for. */
  registryShare: number;
  /** Selection size × registry share: the count a neutral selection would hold. */
  expected: number;
  /** observed / expected. 1 means the selection mirrors the registry. */
  lift: number;
  lo: number;
  hi: number;
  /** The same ratio with admission year held constant; null if no year is usable. */
  expectedStd: number | null;
  liftStd: number | null;
  loStd: number | null;
  hiStd: number | null;
}

export interface LiftResult {
  rows: LiftRow[];
  selectionTotal: number;
  registryTotal: number;
  /** Records dropped from the standardized column for want of an admission year. */
  undatedSelection: number;
}

// Byar's approximation to the exact Poisson interval on observed/expected. It
// is the standard interval for an indirectly standardized ratio, and unlike the
// normal approximation it stays honest when a cell holds only a handful of
// records — which, for a single diagnosis in a single community, it usually does.
//
// It conditions on the expected count, so it describes the sampling error in the
// numerator only. When a selection is a large fraction of the registry the two
// are not independent and the interval is a little narrower than it should be.
const byar = (observed: number, expected: number): [number, number] => {
  if (expected <= 0) return [0, 0];
  const upper =
    ((observed + 1) *
      Math.pow(1 - 1 / (9 * (observed + 1)) + 1.96 / (3 * Math.sqrt(observed + 1)), 3)) /
    expected;
  if (observed === 0) return [0, upper];
  const lower =
    (observed * Math.pow(1 - 1 / (9 * observed) - 1.96 / (3 * Math.sqrt(observed)), 3)) /
    expected;
  return [Math.max(0, lower), upper];
};

const yearOf = (row: RegistryRecord, dateKey: string | undefined): string | null => {
  if (!dateKey) return null;
  const raw = String(row[dateKey] ?? '');
  return /^\d{4}/.test(raw) ? raw.slice(0, 4) : null;
};

/**
 * Compare the composition of `selection` against that of `registry` along one
 * column.
 *
 * The standardized figure is an indirect standardization on admission year:
 * each year contributes its own selection rate, so a value is credited only
 * with the records the years it actually appears in would predict. Without it a
 * ratio can be produced entirely by one epidemic year coinciding with one
 * year's admission mix — the registry spans 1930–48, over which the communities'
 * shares of admissions move a great deal, so this is not a hypothetical.
 *
 * `selection` must be a subset of `registry`; the caller passes the filtered and
 * unfiltered arrays it already holds.
 */
export const computeLift = (
  registry: RegistryRecord[],
  selection: RegistryRecord[],
  key: string | undefined,
  dateKey: string | undefined
): LiftResult => {
  const registryTotal = registry.length;
  const selectionTotal = selection.length;

  const registryCounts = new Map<string, number>();
  const selectionCounts = new Map<string, number>();
  // value → year → count, for the standardized column.
  const registryByYear = new Map<string, Map<string, number>>();
  const registryYearTotals = new Map<string, number>();
  const selectionYearTotals = new Map<string, number>();

  registry.forEach(row => {
    const v = facetValue(key && row[key]);
    registryCounts.set(v, (registryCounts.get(v) || 0) + 1);
    const y = yearOf(row, dateKey);
    if (y) {
      registryYearTotals.set(y, (registryYearTotals.get(y) || 0) + 1);
      let byYear = registryByYear.get(v);
      if (!byYear) registryByYear.set(v, (byYear = new Map()));
      byYear.set(y, (byYear.get(y) || 0) + 1);
    }
  });

  let undatedSelection = 0;
  selection.forEach(row => {
    const v = facetValue(key && row[key]);
    selectionCounts.set(v, (selectionCounts.get(v) || 0) + 1);
    const y = yearOf(row, dateKey);
    if (y) selectionYearTotals.set(y, (selectionYearTotals.get(y) || 0) + 1);
    else undatedSelection++;
  });

  // The probability that a registry record from year y ends up in the selection.
  const selectionRate = new Map<string, number>();
  registryYearTotals.forEach((total, y) => {
    selectionRate.set(y, total > 0 ? (selectionYearTotals.get(y) || 0) / total : 0);
  });

  const rows: LiftRow[] = [];
  registryCounts.forEach((registryN, name) => {
    const observed = selectionCounts.get(name) || 0;
    const registryShare = registryTotal > 0 ? registryN / registryTotal : 0;
    const expected = selectionTotal * registryShare;
    const [lo, hi] = byar(observed, expected);

    let expectedStd: number | null = null;
    const byYear = registryByYear.get(name);
    if (byYear && dateKey) {
      let acc = 0;
      byYear.forEach((n, y) => {
        acc += n * (selectionRate.get(y) || 0);
      });
      expectedStd = acc;
    }
    const [loStd, hiStd] =
      expectedStd && expectedStd > 0 ? byar(observed, expectedStd) : [null, null];

    rows.push({
      name,
      observed,
      registryN,
      selectionShare: selectionTotal > 0 ? observed / selectionTotal : 0,
      registryShare,
      expected,
      lift: expected > 0 ? observed / expected : 0,
      lo,
      hi,
      expectedStd,
      liftStd: expectedStd && expectedStd > 0 ? observed / expectedStd : null,
      loStd,
      hiStd
    });
  });

  rows.sort((a, b) => b.registryN - a.registryN || a.name.localeCompare(b.name));
  return { rows, selectionTotal, registryTotal, undatedSelection };
};

/**
 * A ratio is a multiplicative quantity, so it is plotted on a log axis: ×2 and
 * ×0.5 are the same distance from parity, in opposite directions. On a linear
 * axis over-representation gets the whole right-hand side and under-
 * representation is crushed into the strip between 0 and 1.
 */
export const log2 = (v: number): number => (v > 0 ? Math.log2(v) : 0);

// ---------------------------------------------------------------- over time

/**
 * One dimension's composition over time, as both shares and counts.
 *
 * The share series is what answers a question like "did the Jewish share of
 * admissions fall?", because the register's total intake swings by a factor of
 * six across these years and a count series mostly draws that swing. The counts
 * are carried alongside because a share computed over 30 admissions and a share
 * computed over 3,000 are not the same evidence, and only the counts show which
 * one a reader is looking at.
 *
 * A period with no surviving register yields null, never zero: zero would claim
 * the hospital admitted nobody. Recharts breaks a line on null, which is the
 * shape of the claim. A period that exists but holds none of a given value is a
 * true 0 and is drawn as one.
 */
export interface CompositionPeriod {
  /** '1937' or '1937-04'. */
  period: string;
  /** Total admissions in the period, across the requested values. null if absent. */
  total: number | null;
  /** value -> share of that period, 0..1. Empty when the period is absent. */
  shares: Record<string, number>;
  /** value -> count in that period. Empty when the period is absent. */
  counts: Record<string, number>;
  absent: boolean;
}

const yearSpan = (from: string, to: string): string[] => {
  const out: string[] = [];
  for (let y = Number(from); y <= Number(to); y++) out.push(String(y));
  return out;
};

const monthSpan = (from: string, to: string): string[] => {
  const out: string[] = [];
  let [y, m] = from.split('-').map(Number);
  const [ey, em] = to.split('-').map(Number);
  while (y < ey || (y === ey && m <= em)) {
    out.push(`${y}-${String(m).padStart(2, '0')}`);
    if (++m > 12) { m = 1; y++; }
  }
  return out;
};

/**
 * Periods between the first and last that carry data, with the empty ones
 * present and flagged. `granularity` 'year' slices the ISO date to 4 characters
 * and 'month' to 7.
 */
export const composeOverTime = (
  rows: RegistryRecord[],
  key: string | undefined,
  dateKey: string | undefined,
  granularity: 'year' | 'month',
  values: string[]
): CompositionPeriod[] => {
  if (!key || !dateKey) return [];
  const width = granularity === 'year' ? 4 : 7;
  const wanted = new Set(values);

  const counts = new Map<string, Map<string, number>>();
  rows.forEach(row => {
    const iso = String(row[dateKey] ?? '');
    if (iso.length < width) return;
    const period = iso.slice(0, width);
    // A month is 'YYYY-MM' and a year 'YYYY'; anything else is a misparse.
    if (!/^\d{4}(-\d{2})?$/.test(period)) return;
    const value = facetValue(row[key]);
    if (!wanted.has(value)) return;
    if (!counts.has(period)) counts.set(period, new Map());
    const bucket = counts.get(period)!;
    bucket.set(value, (bucket.get(value) || 0) + 1);
  });
  if (counts.size === 0) return [];

  const present = [...counts.keys()].sort();
  const span = granularity === 'year'
    ? yearSpan(present[0], present[present.length - 1])
    : monthSpan(present[0], present[present.length - 1]);

  return span.map(period => {
    const bucket = counts.get(period);
    if (!bucket) return { period, total: null, shares: {}, counts: {}, absent: true };
    const total = [...bucket.values()].reduce((a, b) => a + b, 0);
    const shares: Record<string, number> = {};
    const out: Record<string, number> = {};
    values.forEach(v => {
      const n = bucket.get(v) || 0;
      out[v] = n;
      shares[v] = total > 0 ? n / total : 0;
    });
    return { period, total, shares, counts: out, absent: false };
  });
};

// ---------------------------------------------------------------- heatmap

/**
 * Two dimensions crossed, each cell carrying its observed count and how that
 * count compares with the one independence would predict.
 *
 * Raw counts across a contingency table mostly draw the marginals: the Surgical
 * ward's Muslim cell is the largest in the table because Muslims are the largest
 * group and Surgical the largest ward, which is arithmetic rather than a
 * finding. Expected = rowTotal x colTotal / grandTotal, and the ratio of
 * observed to expected is what shows structure — where the two dimensions are
 * not independent.
 *
 * Cells below `minN` observed keep their count but carry ratio null: a ratio
 * over a handful of records is noise, and drawing it in a strong colour would
 * make the sparsest corner of the table the loudest thing in it.
 */
export interface HeatCell {
  row: string;
  col: string;
  observed: number;
  expected: number;
  /** observed / expected; null when observed < minN. */
  ratio: number | null;
  /** Share of the row, 0..1 — what this row's records were. */
  rowShare: number;
}

export interface HeatResult {
  rows: string[];
  cols: string[];
  cells: HeatCell[];
  rowTotals: Record<string, number>;
  colTotals: Record<string, number>;
  total: number;
  /** Records dropped because either dimension fell outside the requested values. */
  skipped: number;
}

export const crossTabulate = (
  data: RegistryRecord[],
  rowKey: string | undefined,
  colKey: string | undefined,
  rowValues: string[],
  colValues: string[],
  minN = 20
): HeatResult => {
  const empty: HeatResult = {
    rows: [], cols: [], cells: [], rowTotals: {}, colTotals: {}, total: 0, skipped: 0
  };
  if (!rowKey || !colKey) return empty;

  const wantRow = new Set(rowValues);
  const wantCol = new Set(colValues);
  const cellCounts = new Map<string, number>();
  const rowTotals: Record<string, number> = {};
  const colTotals: Record<string, number> = {};
  let total = 0;
  let skipped = 0;

  data.forEach(record => {
    const r = facetValue(record[rowKey]);
    const c = facetValue(record[colKey]);
    if (!wantRow.has(r) || !wantCol.has(c)) { skipped++; return; }
    // Tab-joined: a value may contain spaces, but never a tab.
    cellCounts.set(`${r}\t${c}`, (cellCounts.get(`${r}\t${c}`) || 0) + 1);
    rowTotals[r] = (rowTotals[r] || 0) + 1;
    colTotals[c] = (colTotals[c] || 0) + 1;
    total++;
  });

  // Only values the selection actually contains, in the order they were asked
  // for, so an empty row does not open a blank band across the table.
  const rows = rowValues.filter(v => rowTotals[v]);
  const cols = colValues.filter(v => colTotals[v]);

  const cells: HeatCell[] = [];
  rows.forEach(r => {
    cols.forEach(c => {
      const observed = cellCounts.get(`${r}\t${c}`) || 0;
      const expected = total > 0 ? (rowTotals[r] * colTotals[c]) / total : 0;
      cells.push({
        row: r,
        col: c,
        observed,
        expected,
        ratio: observed >= minN && expected > 0 ? observed / expected : null,
        rowShare: rowTotals[r] > 0 ? observed / rowTotals[r] : 0
      });
    });
  });

  return { rows, cols, cells, rowTotals, colTotals, total, skipped };
};
