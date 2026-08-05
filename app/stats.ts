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
