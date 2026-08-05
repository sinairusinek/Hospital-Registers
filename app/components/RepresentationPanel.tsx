
import React, { useMemo, useState } from 'react';
import {
  BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ErrorBar, ResponsiveContainer
} from 'recharts';
import { Scale, AlertTriangle } from 'lucide-react';
import { RegistryRecord, FilterState } from '../types';
import { UNKNOWN } from '../facets';
import { DIVERGING, NEUTRAL } from '../colors';
import { computeLift, log2, LiftRow } from '../stats';

// Below this many records in the selection a ratio is arithmetic, not evidence.
// The row is still drawn — a small cell is itself worth seeing — but greyed, so
// nothing is silently dropped from a chart someone may cite.
const MIN_N = 20;

const DIMENSIONS = ['Religion', 'Nationality', 'Sex', 'Chapter', 'City', 'Result'] as const;
type Dimension = typeof DIMENSIONS[number];

interface Props {
  fullData: RegistryRecord[];
  data: RegistryRecord[];
  actualKeys: Record<string, string>;
  filterState: FilterState;
}

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const times = (v: number | null) => (v === null ? '—' : `×${v.toFixed(2)}`);

const RepresentationPanel: React.FC<Props> = ({ fullData, data, actualKeys, filterState }) => {
  const [dimension, setDimension] = useState<Dimension>('Religion');
  const [standardized, setStandardized] = useState(true);

  const key = actualKeys[dimension];
  const dateKey = actualKeys['Admission Date'];

  const result = useMemo(
    () => computeLift(fullData, data, key, dateKey),
    [fullData, data, key, dateKey]
  );

  const isFiltered = data.length > 0 && data.length < fullData.length;
  // Filtering on the very column being compared makes the comparison circular:
  // the excluded values read as ×0 because the filter excluded them, not
  // because the selection is composed differently.
  const selfFiltered = Boolean(key && (filterState.facets[key] || []).length > 0);

  const tableRows = useMemo(() => {
    return result.rows
      .filter(r => r.registryN > 0)
      .map(r => {
        const lift = standardized && r.liftStd !== null ? r.liftStd : r.lift;
        const lo = standardized && r.loStd !== null ? r.loStd : r.lo;
        const hi = standardized && r.hiStd !== null ? r.hiStd : r.hi;
        const value = log2(lift);
        return {
          ...r,
          shown: lift,
          shownLo: lo,
          shownHi: hi,
          value,
          // Recharts wants the whisker as a distance from the bar's end.
          error: [Math.max(0, value - log2(lo)), Math.max(0, log2(hi) - value)] as [number, number],
          weak: r.observed < MIN_N
        };
      })
      .slice(0, 12);
  }, [result, standardized]);

  // A value present in the registry but absent from the selection is ×0, which
  // has no place on a log axis. It stays in the table, where "absent" can be
  // read for what it is, rather than being drawn as a bar of some arbitrary
  // length.
  const chartData = useMemo(() => tableRows.filter(d => d.observed > 0), [tableRows]);
  const absent = useMemo(() => tableRows.filter(d => d.observed === 0), [tableRows]);

  // The axis is sized so that no bar is ever clipped: the extent covers every
  // ratio drawn, and only a whisker may run past the edge.
  const domain = useMemo(() => {
    const extent = chartData.reduce((m, d) => Math.max(m, Math.abs(d.value)), 0.8);
    return [-Math.ceil(extent), Math.ceil(extent)] as [number, number];
  }, [chartData]);

  const renderTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const d: LiftRow & { shown: number; shownLo: number; shownHi: number } = payload[0].payload;
    return (
      <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-3 text-xs space-y-1">
        <div className="font-bold text-slate-800">{d.name}</div>
        <div className="text-slate-500">
          {d.observed.toLocaleString()} of {result.selectionTotal.toLocaleString()} selected
          {' '}({pct(d.selectionShare)})
        </div>
        <div className="text-slate-500">
          {d.registryN.toLocaleString()} of {result.registryTotal.toLocaleString()} in the registry
          {' '}({pct(d.registryShare)})
        </div>
        <div className="pt-1 border-t border-slate-100 text-slate-700">
          expected {(standardized && d.expectedStd !== null ? d.expectedStd : d.expected).toFixed(1)}
          {' · '}
          <span className="font-bold">{times(d.shown)}</span>
          {' '}<span className="text-slate-400">(95% CI {d.shownLo.toFixed(2)}–{d.shownHi.toFixed(2)})</span>
        </div>
        {d.observed < MIN_N && (
          <div className="text-amber-600">Fewer than {MIN_N} records — read as a lead, not a finding.</div>
        )}
      </div>
    );
  };

  return (
    <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="font-bold text-slate-800 flex items-center gap-2">
            <Scale size={20} className="text-slate-600" /> Representation in the selection
          </h3>
          <p className="text-xs text-slate-500 mt-1">
            How each group's share of the selection compares with its share of the registry.
            Parity is ×1.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={dimension}
            onChange={e => setDimension(e.target.value as Dimension)}
            className="text-xs font-bold text-slate-700 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 outline-none"
          >
            {DIMENSIONS.filter(d => actualKeys[d]).map(d => (
              <option key={d} value={d}>{d === 'Chapter' ? 'Diagnosis (ICD-9 chapter)' : d}</option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-xs font-bold text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 cursor-pointer">
            <input
              type="checkbox"
              checked={standardized}
              onChange={e => setStandardized(e.target.checked)}
              className="accent-slate-700"
            />
            Hold admission year constant
          </label>
        </div>
      </div>

      {!isFiltered ? (
        <div className="text-sm text-slate-500 italic py-12 text-center">
          Nothing is filtered, so every group sits exactly at parity. Filter to a diagnosis, a
          ward or a period on the left — or click a pie slice — and this chart shows how that
          selection's composition departs from the registry's.
        </div>
      ) : (
        <>
          {selfFiltered && (
            <div className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-xl p-3">
              <AlertTriangle size={14} className="shrink-0 mt-0.5" />
              <span>
                A {dimension} filter is active, so this chart is comparing {dimension} against a
                selection defined by {dimension}. Clear that facet, or pick another dimension,
                before reading anything into it.
              </span>
            </div>
          )}

          <div style={{ height: Math.max(200, chartData.length * 38 + 40) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} layout="vertical" margin={{ top: 8, right: 56, left: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                <XAxis
                  type="number"
                  domain={domain}
                  ticks={[-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5].filter(t => t >= domain[0] && t <= domain[1])}
                  // Doublings and halvings, labelled as the ratios they are: on a
                  // log axis ×2 and ×½ sit the same distance either side of parity,
                  // which is the property that makes over- and under-representation
                  // comparable at a glance.
                  tickFormatter={(t: number) => (t === 0 ? '×1' : t > 0 ? `×${2 ** t}` : `×1/${2 ** -t}`)}
                  fontSize={10}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={110}
                  fontSize={10}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={renderTooltip} cursor={{ fill: '#f8fafc' }} />
                <ReferenceLine x={0} stroke="#64748b" strokeWidth={1.5} />
                <Bar dataKey="value" radius={[4, 4, 4, 4]} barSize={16} isAnimationActive={false}>
                  {chartData.map(d => (
                    <Cell
                      key={`lift-${d.name}`}
                      fill={
                        d.weak ? DIVERGING.muted
                          : d.name === UNKNOWN ? NEUTRAL
                          : d.value >= 0 ? DIVERGING.above : DIVERGING.below
                      }
                    />
                  ))}
                  <ErrorBar dataKey="error" direction="x" width={5} strokeWidth={1.5} stroke="#475569" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[10px] font-medium text-slate-500">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded" style={{ background: DIVERGING.above }} /> over-represented
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded" style={{ background: DIVERGING.below }} /> under-represented
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded" style={{ background: DIVERGING.muted }} /> fewer than {MIN_N} records
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded" style={{ background: NEUTRAL }} /> {UNKNOWN}
            </span>
            <span>whiskers are 95% confidence intervals; a whisker crossing ×1 is consistent with parity</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[10px] uppercase tracking-widest text-slate-400 border-b border-slate-200">
                  <th className="py-2 pr-4 font-bold">{dimension}</th>
                  <th className="py-2 pr-4 font-bold text-right">In selection</th>
                  <th className="py-2 pr-4 font-bold text-right">Share of selection</th>
                  <th className="py-2 pr-4 font-bold text-right">Share of registry</th>
                  <th className="py-2 pr-4 font-bold text-right">Expected</th>
                  <th className="py-2 pr-4 font-bold text-right">Ratio (95% CI)</th>
                </tr>
              </thead>
              <tbody>
                {tableRows.map(d => (
                  <tr key={`row-${d.name}`} className={`border-b border-slate-50 ${d.weak ? 'text-slate-400' : 'text-slate-700'}`}>
                    <td className="py-2 pr-4 font-bold">{d.name}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">{d.observed.toLocaleString()}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">{pct(d.selectionShare)}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">{pct(d.registryShare)}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      {(standardized && d.expectedStd !== null ? d.expectedStd : d.expected).toFixed(1)}
                    </td>
                    <td className="py-2 pr-4 text-right tabular-nums font-bold">
                      {d.observed === 0
                        ? <span className="font-medium italic text-slate-400">absent from the selection</span>
                        : <>
                            {times(d.shown)}
                            <span className="font-medium text-slate-400"> ({d.shownLo.toFixed(2)}–{d.shownHi.toFixed(2)})</span>
                          </>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-[10px] text-slate-400 leading-relaxed">
            {standardized
              ? `Expected counts are standardized on admission year: each year contributes its own selection rate, so a ratio cannot be produced by a single year's admission mix alone.`
              : `Expected counts are crude — the registry's overall composition applied to the selection. Over 1930–48 that composition shifts considerably; tick the box above to hold year constant.`}
            {result.undatedSelection > 0 && standardized &&
              ` ${result.undatedSelection.toLocaleString()} selected records carry no usable admission date and sit outside the standardization.`}
            {absent.length > 0 &&
              ` ${absent.length} value${absent.length === 1 ? '' : 's'} present in the registry are absent from this selection altogether; they are listed in the table but cannot be drawn on a ratio axis.`}
            {' '}These are shares of admissions to this hospital, not of Haifa's population: a ratio
            here describes who reached these wards, not who fell ill in the city.
          </p>
        </>
      )}
    </div>
  );
};

export default RepresentationPanel;
