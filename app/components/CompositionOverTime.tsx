import React, { useMemo, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceArea
} from 'recharts';
import { RegistryRecord } from '../types';
import { UNKNOWN } from '../facets';
import { ColorScale } from '../colors';
import { composeOverTime, CompositionPeriod } from '../stats';

/**
 * A pie says who was in the selection; this says when.
 *
 * The two charts are deliberately side by side rather than one toggling into the
 * other. A share series alone can rise because a group grew or because everyone
 * else shrank, and over these years the register's total intake moves by a factor
 * of six — so the counts are not an alternative view of the same fact, they are
 * the denominator the shares are computed over. Reading the Jewish line falling
 * from 1936 means nothing until the count chart shows the other two rising.
 *
 * Absent periods are null, never zero, and recharts breaks each line across them;
 * the shaded bands name them so a gap in the register cannot read as a collapse
 * in admissions. That distinction is load-bearing here: the register is missing
 * 1941-43 and 1945 entirely.
 */

// recharts types ReferenceArea's SVG props off RectangleProps, which does not
// declare fill; the props do reach the rect at runtime. Declared once and cast,
// matching StatisticsView's handling of the same problem.
const GAP_SHADING = {
  fill: '#94a3b8',
  fillOpacity: 0.09,
  strokeOpacity: 0
} as React.ComponentProps<typeof ReferenceArea>;

// At most this many lines. Past a handful of series a line chart becomes a
// thicket, and the pie beside it already carries the long tail as Others.
const MAX_SERIES = 6;

// A share computed over very few admissions is arithmetic rather than evidence,
// so the count chart is where the reader checks it; this is only the floor for
// anchoring the axis, matching StatisticsView's SPAN_FLOOR.
const SPAN_FLOOR = 5;

interface Props {
  /** The current selection — the same rows the pie beside this is drawn from. */
  data: RegistryRecord[];
  /** Column holding the dimension, already resolved from the header aliases. */
  valueKey: string | undefined;
  dateKey: string | undefined;
  /** Values to draw, in the pie's own order, so the two charts agree. */
  values: string[];
  colorScale: ColorScale | undefined;
  displayName: string;
  /** Column holding the notebook number, for the Atlit caution below. */
  notebookKey?: string | undefined;
}

const contiguousAbsent = (periods: CompositionPeriod[]): [string, string][] => {
  const runs: [string, string][] = [];
  let start: string | null = null;
  periods.forEach((p, i) => {
    if (p.absent) {
      if (start === null) start = p.period;
      if (i === periods.length - 1) runs.push([start, p.period]);
    } else if (start !== null) {
      runs.push([start, periods[i - 1].period]);
      start = null;
    }
  });
  return runs;
};

// Notebook 25 is the Atlit detention-camp register — 965 admissions in 1940,
// 962 of them Jewish, screened at a different institution. Every figure in the
// project excludes it, but the site ships the whole dataset, so a Religion series
// drawn over all notebooks shows 1940 jumping to 67.7% Jewish against 19.8%
// without it. That is not a change in the hospital's patients, and a line chart
// is exactly where someone would misread it as one.
const ATLIT_NOTEBOOK = '25';

const CompositionOverTime: React.FC<Props> = ({
  data, valueKey, dateKey, values, colorScale, displayName, notebookKey
}) => {
  const [granularity, setGranularity] = useState<'year' | 'month'>('year');

  // Unrecorded is dropped from the lines: it is an absence, not a trend, and at
  // this scale it would often be the largest series and say nothing.
  const series = useMemo(
    () => values.filter(v => v !== UNKNOWN).slice(0, MAX_SERIES),
    [values]
  );

  const periods = useMemo(
    () => composeOverTime(data, valueKey, dateKey, granularity, series),
    [data, valueKey, dateKey, granularity, series]
  );

  // Trim leading and trailing periods too thin to anchor an axis: two records
  // carry a misread 1963 admission date, and without this they stretch the axis
  // fifteen years past the last register.
  const trimmed = useMemo(() => {
    const solid = periods.filter(p => !p.absent && (p.total ?? 0) >= SPAN_FLOOR);
    if (solid.length === 0) return [];
    const first = solid[0].period;
    const last = solid[solid.length - 1].period;
    return periods.filter(p => p.period >= first && p.period <= last);
  }, [periods]);

  const chartData = useMemo(() => trimmed.map(p => {
    const row: Record<string, string | number | null> = { period: p.period, total: p.total };
    series.forEach(v => {
      row[`${v} share`] = p.absent ? null : (p.shares[v] ?? 0) * 100;
      row[`${v} count`] = p.absent ? null : (p.counts[v] ?? 0);
    });
    return row;
  }), [trimmed, series]);

  const gaps = useMemo(() => contiguousAbsent(trimmed), [trimmed]);
  const absentCount = trimmed.filter(p => p.absent).length;

  const atlitInSelection = useMemo(() => {
    if (!notebookKey) return 0;
    return data.reduce(
      (n, row) => n + (String(row[notebookKey] ?? '').trim() === ATLIT_NOTEBOOK ? 1 : 0), 0
    );
  }, [data, notebookKey]);

  if (chartData.length === 0 || series.length === 0) {
    return (
      <div className="h-32 flex items-center justify-center text-slate-400 text-xs italic">
        No dated records in this selection
      </div>
    );
  }

  const tooltip = (mode: 'share' | 'count') => ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    const total = payload[0]?.payload?.total;
    return (
      <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-3 text-[11px]">
        <div className="font-bold text-slate-800 mb-1">{label}</div>
        {total === null || total === undefined ? (
          <div className="text-slate-500 italic">No surviving register</div>
        ) : (
          <>
            {payload.map((p: any) => (
              <div key={p.name} className="flex items-center gap-1.5 text-slate-600">
                <span className="w-2 h-2 rounded-full shrink-0" style={{ background: p.stroke }} />
                {p.name.replace(/ (share|count)$/, '')}:{' '}
                <strong>{mode === 'share' ? `${Number(p.value).toFixed(1)}%` : Number(p.value).toLocaleString()}</strong>
              </div>
            ))}
            <div className="text-slate-400 pt-1 mt-1 border-t border-slate-100">
              {total.toLocaleString()} admissions in this {granularity}
            </div>
          </>
        )}
      </div>
    );
  };

  const axes = (
    <>
      <CartesianGrid stroke="#f1f5f9" vertical={false} />
      <XAxis dataKey="period" tick={{ fontSize: 9, fill: '#94a3b8' }}
             stroke="#e2e8f0" interval="preserveStartEnd" minTickGap={14} />
    </>
  );

  const gapBands = gaps.map(([from, to]) => (
    <ReferenceArea key={`gap-${from}`} x1={from} x2={to} {...GAP_SHADING} />
  ));

  return (
    <div>
      <div className="flex items-center justify-between mb-2 gap-3">
        <p className="text-[11px] text-slate-500 leading-snug">
          Share answers whether the mix changed; counts show how many records each
          share rests on. Read them together — a share can move because one group
          left or because the others arrived.
        </p>
        <div className="flex bg-slate-100 rounded-md p-0.5 shrink-0" role="group"
             aria-label="Time granularity">
          {(['year', 'month'] as const).map(g => (
            <button key={g} onClick={() => setGranularity(g)}
                    aria-pressed={granularity === g}
                    className={`px-2 py-0.5 text-[10px] font-medium rounded transition-colors ${
                      granularity === g ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                    }`}>
              {g === 'year' ? 'Year' : 'Month'}
            </button>
          ))}
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <h5 className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
            Share of admissions
          </h5>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                {axes}
                <YAxis tick={{ fontSize: 9, fill: '#94a3b8' }} stroke="#e2e8f0"
                       domain={[0, 100]} tickFormatter={v => `${v}%`} />
                {gapBands}
                <Tooltip content={tooltip('share')} />
                {series.map(v => (
                  <Line key={v} type="monotone" dataKey={`${v} share`} name={v}
                        stroke={colorScale ? colorScale(v) : '#94a3b8'} strokeWidth={2}
                        dot={false} activeDot={{ r: 4 }} connectNulls={false}
                        animationDuration={600} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div>
          <h5 className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
            Admissions
          </h5>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                {axes}
                <YAxis tick={{ fontSize: 9, fill: '#94a3b8' }} stroke="#e2e8f0" allowDecimals={false} />
                {gapBands}
                <Tooltip content={tooltip('count')} />
                {series.map(v => (
                  <Line key={v} type="monotone" dataKey={`${v} count`} name={v}
                        stroke={colorScale ? colorScale(v) : '#94a3b8'} strokeWidth={2}
                        dot={false} activeDot={{ r: 4 }} connectNulls={false}
                        animationDuration={600} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <ul className="flex flex-wrap gap-x-3 gap-y-1 mt-3">
        {series.map(v => (
          <li key={v} className="flex items-center gap-1 text-[10px] text-slate-600">
            <span className="w-2.5 h-0.5 rounded-full shrink-0"
                  style={{ background: colorScale ? colorScale(v) : '#94a3b8' }} />
            {v}
          </li>
        ))}
        {absentCount > 0 && (
          <li className="flex items-center gap-1 text-[10px] text-slate-400 italic">
            <span className="w-2.5 h-2 rounded-sm shrink-0" style={{ background: '#94a3b8', opacity: 0.18 }} />
            {absentCount} {granularity === 'year' ? 'years' : 'months'} with no surviving register
          </li>
        )}
        {values.length > series.length && (
          <li className="text-[10px] text-slate-400 italic">
            showing the {series.length} largest
            {values.includes(UNKNOWN) ? '; unrecorded omitted' : ''}
          </li>
        )}
      </ul>

      {atlitInSelection > 0 && (
        <p className="text-[10px] text-amber-800 bg-amber-50 border border-amber-200 rounded-md
                      px-2.5 py-1.5 mt-2 leading-relaxed">
          <strong>1940 includes the Atlit camp register.</strong> Notebook 25 contributes{' '}
          {atlitInSelection.toLocaleString()} admissions to this selection — screening at a
          detention camp, not the Haifa hospital, and 962 of its 965 records are Jewish. It lifts
          1940 sharply and every figure in the project excludes it. Filter Notebook 25 out to read
          the hospital's own intake.
        </p>
      )}
    </div>
  );
};

export default CompositionOverTime;
