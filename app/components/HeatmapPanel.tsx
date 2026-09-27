import React, { useMemo, useState } from 'react';
import { Grid3x3, AlertTriangle } from 'lucide-react';
import { RegistryRecord, FilterState } from '../types';
import { facetValue, UNKNOWN } from '../facets';
import { DIVERGING, NEUTRAL } from '../colors';
import { crossTabulate, HeatCell } from '../stats';

/**
 * Two dimensions crossed, coloured by how far each cell departs from independence.
 *
 * The pies describe one dimension at a time and the representation panel compares
 * a selection with the registry. Neither answers the question a sentence like
 * "Jewish patients filled the isolation wards" rests on, which is about the joint
 * distribution: whether the Jewish share of Isolation is larger than the Jewish
 * share of admissions at large.
 *
 * Raw counts cannot show that, because a contingency table of counts mostly draws
 * its own marginals — the largest group in the largest ward makes the largest
 * cell whatever the structure is. So the default measure is observed / expected,
 * where expected is what independence would predict, and the scale is diverging
 * from a neutral midpoint at parity. Counts and row shares are available because
 * a ratio without its denominator is not checkable.
 *
 * Cells under MIN_N keep their count and lose their colour rather than being
 * blanked: a sparse cell is itself worth seeing, and colouring a ×4 computed over
 * six records would make the emptiest corner the loudest thing on screen.
 */

const MIN_N = 20;

// The dimensions worth crossing. Diagnosis is deliberately absent — 4,004
// distinct labels cannot be a heatmap axis; Chapter is its readable form.
const DIMENSIONS = ['Religion', 'Nationality', 'Ward', 'Class', 'Sex', 'Chapter', 'Result', 'City'] as const;
type Dimension = typeof DIMENSIONS[number];

// Past this many values an axis stops being readable, so the tail is dropped
// rather than squeezed; the caption says how much was left out.
const MAX_ROWS = 12;
const MAX_COLS = 10;

type Measure = 'ratio' | 'count' | 'rowShare';

interface Props {
  fullData: RegistryRecord[];
  data: RegistryRecord[];
  actualKeys: Record<string, string>;
  filterState: FilterState;
}

/**
 * Colour for a ratio, on a log scale so x2 and x0.5 sit equally far from parity.
 * Saturation is capped at x4 / x0.25 — beyond that the cell is already as loud as
 * the scale goes, and letting it run further would flatten everything else.
 */
const ratioColor = (ratio: number | null): string => {
  if (ratio === null) return DIVERGING.muted;
  const t = Math.min(1, Math.abs(Math.log2(ratio)) / 2);
  const hue = ratio >= 1 ? DIVERGING.above : DIVERGING.below;
  // Mixed toward the surface rather than varying alpha, so cells stay opaque and
  // the 2px gaps between them keep reading as gaps.
  return `color-mix(in oklab, ${hue} ${Math.round(18 + t * 82)}%, #ffffff)`;
};

const sequentialColor = (t: number): string =>
  `color-mix(in oklab, #2a78d6 ${Math.round(10 + Math.min(1, t) * 90)}%, #ffffff)`;

/** White text once the fill is dark enough to need it. */
const needsLightInk = (measure: Measure, cell: HeatCell, max: number): boolean => {
  if (measure === 'ratio') {
    return cell.ratio !== null && Math.abs(Math.log2(cell.ratio)) / 2 > 0.55;
  }
  const t = measure === 'count' ? cell.observed / (max || 1) : cell.rowShare;
  return t > 0.6;
};

const HeatmapPanel: React.FC<Props> = ({ fullData, data, actualKeys, filterState }) => {
  const [rowDim, setRowDim] = useState<Dimension>('Ward');
  const [colDim, setColDim] = useState<Dimension>('Religion');
  const [measure, setMeasure] = useState<Measure>('ratio');
  const [includeUnknown, setIncludeUnknown] = useState(false);

  const rowKey = actualKeys[rowDim];
  const colKey = actualKeys[colDim];

  // Values are ranked on the WHOLE registry, not the selection, so that filtering
  // cannot reorder or repaint the axes — the same guarantee the pies' colour
  // scales give. Ties broken by name so the order is fully determined.
  const rank = (key: string | undefined, limit: number): string[] => {
    if (!key) return [];
    const counts = new Map<string, number>();
    fullData.forEach(row => {
      const v = facetValue(row[key]);
      counts.set(v, (counts.get(v) || 0) + 1);
    });
    return [...counts.entries()]
      .filter(([name]) => includeUnknown || name !== UNKNOWN)
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, limit)
      .map(([name]) => name);
  };

  const rowValues = useMemo(() => rank(rowKey, MAX_ROWS), [fullData, rowKey, includeUnknown]);
  const colValues = useMemo(() => rank(colKey, MAX_COLS), [fullData, colKey, includeUnknown]);

  const result = useMemo(
    () => crossTabulate(data, rowKey, colKey, rowValues, colValues, MIN_N),
    [data, rowKey, colKey, rowValues, colValues]
  );

  const cellAt = useMemo(() => {
    const map = new Map<string, HeatCell>();
    result.cells.forEach(c => map.set(`${c.row}\t${c.col}`, c));
    return map;
  }, [result]);

  const maxCount = useMemo(
    () => result.cells.reduce((m, c) => Math.max(m, c.observed), 0),
    [result]
  );

  // Crossing a dimension with itself gives a diagonal and nothing else.
  const sameDim = rowDim === colDim;
  // Filtering on an axis makes that axis circular: the excluded values are absent
  // because the filter excluded them, not because of how the two dimensions relate.
  const axisFiltered = [rowKey, colKey]
    .filter(k => k && (filterState.facets[k] || []).length > 0).length > 0;

  const fill = (cell: HeatCell | undefined): string => {
    if (!cell || cell.observed === 0) return '#f8fafc';
    if (measure === 'ratio') return ratioColor(cell.ratio);
    if (measure === 'count') return sequentialColor(cell.observed / (maxCount || 1));
    return sequentialColor(cell.rowShare);
  };

  const label = (cell: HeatCell | undefined): string => {
    if (!cell || cell.observed === 0) return '';
    if (measure === 'ratio') return cell.ratio === null ? '·' : `${cell.ratio.toFixed(2)}`;
    if (measure === 'count') return cell.observed.toLocaleString();
    return `${(cell.rowShare * 100).toFixed(0)}%`;
  };

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
        <div>
          <h3 className="font-bold text-slate-800 flex items-center gap-2">
            <Grid3x3 size={18} className="text-violet-500" />
            Two dimensions crossed
          </h3>
          <p className="text-xs text-slate-500 mt-1 max-w-2xl leading-relaxed">
            Each cell compares the records it holds with the number independence
            would predict — <strong>rows × columns ÷ total</strong>. Red is
            over-represented, blue under, grey at parity or too sparse to say. A
            ratio is what shows structure; raw counts mostly redraw the marginals.
          </p>
        </div>
        <div className="flex gap-1 bg-slate-100 rounded-lg p-0.5 shrink-0" role="group"
             aria-label="Cell measure">
          {([
            ['ratio', 'Ratio'],
            ['count', 'Count'],
            ['rowShare', 'Row %']
          ] as const).map(([m, lab]) => (
            <button key={m} onClick={() => setMeasure(m)} aria-pressed={measure === m}
                    className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition-colors ${
                      measure === m ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                    }`}>
              {lab}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-4 mb-5">
        <label className="text-[11px] text-slate-500">
          <span className="block mb-1 font-medium">Rows</span>
          <select value={rowDim} onChange={e => setRowDim(e.target.value as Dimension)}
                  className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white
                             text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-100">
            {DIMENSIONS.filter(d => actualKeys[d]).map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </label>
        <label className="text-[11px] text-slate-500">
          <span className="block mb-1 font-medium">Columns</span>
          <select value={colDim} onChange={e => setColDim(e.target.value as Dimension)}
                  className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white
                             text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-100">
            {DIMENSIONS.filter(d => actualKeys[d]).map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-[11px] text-slate-500 pb-1 cursor-pointer">
          <input type="checkbox" checked={includeUnknown}
                 onChange={e => setIncludeUnknown(e.target.checked)}
                 className="rounded border-slate-300" />
          Include <em>{UNKNOWN}</em>
        </label>
      </div>

      {sameDim ? (
        <p className="text-xs text-slate-400 italic py-8 text-center">
          Pick two different dimensions — a dimension crossed with itself is a diagonal.
        </p>
      ) : result.total === 0 ? (
        <p className="text-xs text-slate-400 italic py-8 text-center">
          No records in this selection carry both {rowDim} and {colDim}.
        </p>
      ) : (
        <>
          {axisFiltered && (
            <p className="flex gap-2 text-[11px] text-amber-800 bg-amber-50 border border-amber-200
                          rounded-lg px-3 py-2 mb-4">
              <AlertTriangle size={13} className="shrink-0 mt-0.5" />
              <span>
                A filter is active on {rowDim} or {colDim}. The ratios are computed
                inside the selection, so the filtered axis compares its surviving
                values only — read it as a sub-table, not as the registry.
              </span>
            </p>
          )}

          <div className="overflow-x-auto">
            <table className="border-separate" style={{ borderSpacing: '2px' }}>
              <thead>
                <tr>
                  <th className="sticky left-0 bg-white z-10" />
                  {result.cols.map(c => (
                    <th key={c} className="px-1 pb-1 text-[10px] font-semibold text-slate-500
                                           align-bottom max-w-[5.5rem]">
                      <div className="truncate" title={c}>{c}</div>
                      <div className="text-slate-300 font-normal tabular-nums">
                        {(result.colTotals[c] || 0).toLocaleString()}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map(r => (
                  <tr key={r}>
                    <th className="sticky left-0 bg-white z-10 pr-2 text-right text-[10px]
                                   font-medium text-slate-600 whitespace-nowrap max-w-[9rem]">
                      <div className="truncate" title={r}>{r}</div>
                      <div className="text-slate-300 font-normal tabular-nums">
                        {(result.rowTotals[r] || 0).toLocaleString()}
                      </div>
                    </th>
                    {result.cols.map(c => {
                      const cell = cellAt.get(`${r}\t${c}`);
                      const light = cell ? needsLightInk(measure, cell, maxCount) : false;
                      return (
                        <td key={c} className="p-0">
                          <div
                            className="w-[4.5rem] h-10 rounded flex items-center justify-center
                                       text-[10px] font-semibold tabular-nums cursor-default
                                       transition-transform hover:scale-[1.06] hover:z-20 relative"
                            style={{ background: fill(cell), color: light ? '#ffffff' : '#475569' }}
                            title={cell && cell.observed > 0
                              ? `${r} × ${c}\n${cell.observed.toLocaleString()} records `
                                + `(${(cell.rowShare * 100).toFixed(1)}% of ${r})\n`
                                + `expected ${cell.expected.toFixed(1)} if independent\n`
                                + (cell.ratio === null
                                    ? `under ${MIN_N} records — no ratio shown`
                                    : `ratio ×${cell.ratio.toFixed(2)}`)
                              : `${r} × ${c}\nno records`}
                          >
                            {label(cell)}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 mt-4 text-[10px] text-slate-500">
            {measure === 'ratio' ? (
              <>
                <span className="flex items-center gap-1.5">
                  <span className="flex rounded overflow-hidden">
                    {[0.25, 0.5, 0.8, 1, 1.25, 2, 4].map(v => (
                      <span key={v} className="w-5 h-3" style={{ background: ratioColor(v) }} />
                    ))}
                  </span>
                  ×0.25 under-represented → ×1 parity → ×4 over
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded" style={{ background: DIVERGING.muted }} />
                  under {MIN_N} records — no ratio
                </span>
              </>
            ) : (
              <span className="flex items-center gap-1.5">
                <span className="flex rounded overflow-hidden">
                  {[0.1, 0.3, 0.5, 0.7, 0.9].map(v => (
                    <span key={v} className="w-5 h-3" style={{ background: sequentialColor(v) }} />
                  ))}
                </span>
                {measure === 'count' ? `0 → ${maxCount.toLocaleString()} records` : '0% → 100% of the row'}
              </span>
            )}
            <span className="text-slate-400">
              {result.total.toLocaleString()} records in the table
              {result.skipped > 0 && `; ${result.skipped.toLocaleString()} outside the values shown`}
            </span>
          </div>
          <p className="text-[10px] text-slate-400 mt-2 leading-relaxed">
            Row and column labels carry their totals beneath them. Axes show the
            largest {MAX_ROWS} and {MAX_COLS} values of the whole registry, ranked
            there rather than in the selection so a filter cannot reorder them.
          </p>
        </>
      )}
    </div>
  );
};

export default HeatmapPanel;
