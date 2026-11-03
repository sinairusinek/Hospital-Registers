import React, { useMemo, useState } from 'react';
import { Clock, AlertTriangle } from 'lucide-react';
import { RegistryRecord } from '../types';
import { UNKNOWN } from '../facets';
import { ColorScale, DIVERGING, NEUTRAL } from '../colors';
import { compareStays, StayStandard, StayRow } from '../stats';
import { GROUP_DIM, dimensionLabel } from '../groups';

/*
 * Length of stay by group. A pooled comparison mostly redraws the diagnosis
 * mix — typhoid kept patients for weeks, a delivery for days — so the default
 * holds the ICD-9 chapter constant and asks whether a group stayed longer than
 * its own illnesses would predict. The boxes beside the ratio are the raw
 * stays, so the reader can always see what the ratio was computed from.
 */

const MIN_N = 20;
const MAX_ROWS = 10;
const DIMENSIONS = [GROUP_DIM, 'Religion', 'Nationality', 'Class', 'Ward', 'Sex'] as const;
type Dimension = typeof DIMENSIONS[number];
// Notebook 25 is the Atlit camp register: its stays are a camp's, not a ward's.
const ATLIT_NOTEBOOK = '25';

const STANDARDS: { key: StayStandard; label: string }[] = [
  { key: 'chapter', label: 'Hold diagnosis chapter constant' },
  { key: 'chapterYear', label: 'Hold chapter and year constant' },
  { key: 'crude', label: 'Crude (no adjustment)' }
];

// The box axis is log(1 + days), so a week and a month both have room.
const AXIS_MAX = 365;
const TICKS = [0, 1, 3, 7, 14, 30, 90, 365];
const BOX_W = 300;
const sx = (d: number) => (Math.log1p(Math.min(d, AXIS_MAX)) / Math.log1p(AXIS_MAX)) * BOX_W;

// The ratio axis runs ×½ to ×2 on a log scale; a whisker beyond is clipped.
const RATIO_W = 160;
const rx = (v: number) => ((Math.max(-1, Math.min(1, Math.log2(v))) + 1) / 2) * RATIO_W;

const fmt = (d: number) => (Number.isInteger(d) ? String(d) : d.toFixed(1));

interface Props {
  data: RegistryRecord[];
  actualKeys: Record<string, string>;
  colorScales: Record<string, ColorScale>;
}

const StayPanel: React.FC<Props> = ({ data, actualKeys, colorScales }) => {
  const [dimension, setDimension] = useState<Dimension>(GROUP_DIM);
  const [standard, setStandard] = useState<StayStandard>('chapter');
  const [dropDeaths, setDropDeaths] = useState(false);

  const stayKey = actualKeys['Stay'];
  const groupKey = actualKeys[dimension];
  const notebookKey = actualKeys['Notebook'];
  const resultKey = actualKeys['Result'];

  const { rows, atlit, deaths } = useMemo(() => {
    let atlit = 0, deaths = 0;
    const rows = data.filter(row => {
      if (notebookKey && String(row[notebookKey] ?? '') === ATLIT_NOTEBOOK) { atlit++; return false; }
      if (dropDeaths && resultKey && String(row[resultKey] ?? '') === 'Died') { deaths++; return false; }
      return true;
    });
    return { rows, atlit, deaths };
  }, [data, notebookKey, resultKey, dropDeaths]);

  const result = useMemo(
    () => (stayKey && groupKey
      ? compareStays(rows, groupKey, stayKey, actualKeys['Chapter'], actualKeys['Admission Date'], standard)
      : null),
    [rows, groupKey, stayKey, actualKeys, standard]
  );

  if (!stayKey || !result) return null;

  const shown = result.rows.slice(0, MAX_ROWS);
  const hidden = result.rows.length - shown.length;
  const noStay = rows.length - result.total;
  const color = colorScales[dimension];
  const dimLabel = dimensionLabel(dimension);
  const against = standard === 'crude'
    ? 'the typical stay of the whole comparison'
    : standard === 'chapter'
      ? 'what its own diagnoses predict'
      : 'what its own diagnoses, in their years, predict';

  const ratioText = (r: StayRow) => (r.ratio === null ? '—'
    : <>×{r.ratio.toFixed(2)}<span className="font-medium text-slate-400"> ({r.lo!.toFixed(2)}–{r.hi!.toFixed(2)})</span></>);

  return (
    <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="font-bold text-slate-800 flex items-center gap-2">
            <Clock size={20} className="text-slate-600" /> Length of stay by {dimLabel.toLowerCase()}
          </h3>
          <p className="text-xs text-slate-500 mt-1">
            Each group's stays, and its typical stay set against {against}. Parity is ×1.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <select value={dimension} onChange={e => setDimension(e.target.value as Dimension)}
                  className="text-xs font-bold text-slate-700 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 outline-none">
            {DIMENSIONS.filter(d => actualKeys[d]).map(d => <option key={d} value={d}>{dimensionLabel(d)}</option>)}
          </select>
          <select value={standard} onChange={e => setStandard(e.target.value as StayStandard)}
                  className="text-xs font-bold text-slate-700 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 outline-none">
            {STANDARDS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
          <label className="flex items-center gap-2 text-xs font-bold text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 cursor-pointer">
            <input type="checkbox" checked={dropDeaths} onChange={e => setDropDeaths(e.target.checked)}
                   className="accent-slate-700" />
            Leave out deaths
          </label>
        </div>
      </div>

      {standard === 'crude' && (
        <div className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-xl p-3">
          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          <span>
            A crude comparison mostly measures which illnesses each group arrived with. Pooled,
            the communities' median stays differ by a day or two; within a single chapter they can
            differ by half. Hold the chapter constant before reading a difference as treatment.
          </span>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-widest text-slate-400 border-b border-slate-200">
              <th className="py-2 pr-4 font-bold">{dimLabel}</th>
              <th className="py-2 pr-4 font-bold text-right">Stays</th>
              <th className="py-2 pr-4 font-bold text-right">Median (IQR)</th>
              <th className="py-2 pr-4 font-bold" style={{ width: BOX_W + 8 }}>Days, middle 80% and middle half</th>
              <th className="py-2 pr-4 font-bold" style={{ width: RATIO_W + 8 }}>Typical stay, ×½ – ×2</th>
              <th className="py-2 font-bold text-right">Ratio (95% CI)</th>
            </tr>
          </thead>
          <tbody>
            {shown.map(r => {
              const weak = r.n < MIN_N;
              const fill = weak ? DIVERGING.muted : r.name === UNKNOWN ? NEUTRAL : (color ? color(r.name) : NEUTRAL);
              const ratioColor = weak || r.ratio === null ? DIVERGING.muted
                : (r.lo! > 1 ? DIVERGING.above : r.hi! < 1 ? DIVERGING.below : '#475569');
              return (
                <tr key={r.name} className={`border-b border-slate-50 ${weak ? 'text-slate-400' : 'text-slate-700'}`}>
                  <td className="py-2 pr-4 font-bold">{r.name}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">{r.n.toLocaleString()}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    {fmt(r.median)} <span className="text-slate-400">({fmt(r.q1)}–{fmt(r.q3)})</span>
                  </td>
                  <td className="py-2 pr-4">
                    <svg width={BOX_W + 8} height={18} className="overflow-visible">
                      <g transform="translate(4,0)">
                        {TICKS.map(t => <line key={t} x1={sx(t)} x2={sx(t)} y1={0} y2={18} stroke="#f1f5f9" />)}
                        <line x1={sx(r.p10)} x2={sx(r.p90)} y1={9} y2={9} stroke="#94a3b8" strokeWidth={1.5} />
                        <rect x={sx(r.q1)} y={3} width={Math.max(2, sx(r.q3) - sx(r.q1))} height={12} rx={3}
                              fill={fill} fillOpacity={0.85} />
                        <line x1={sx(r.median)} x2={sx(r.median)} y1={1} y2={17} stroke="#0f172a" strokeWidth={2} />
                      </g>
                    </svg>
                  </td>
                  <td className="py-2 pr-4">
                    <svg width={RATIO_W + 8} height={18} className="overflow-visible">
                      <g transform="translate(4,0)">
                        <line x1={rx(1)} x2={rx(1)} y1={0} y2={18} stroke="#64748b" strokeWidth={1.5} />
                        {r.ratio !== null && <>
                          <line x1={rx(r.lo!)} x2={rx(r.hi!)} y1={9} y2={9} stroke={ratioColor} strokeWidth={2} />
                          <circle cx={rx(r.ratio)} cy={9} r={4.5} fill={ratioColor} />
                        </>}
                      </g>
                    </svg>
                  </td>
                  <td className="py-2 text-right tabular-nums font-bold whitespace-nowrap">{ratioText(r)}</td>
                </tr>
              );
            })}
            <tr>
              <td colSpan={3} />
              <td className="pt-1 pr-4">
                <svg width={BOX_W + 8} height={12} className="overflow-visible">
                  <g transform="translate(4,0)">
                    {TICKS.map(t => (
                      <text key={t} x={sx(t)} y={10} fontSize={9} fill="#94a3b8" textAnchor="middle">
                        {t === AXIS_MAX ? '365+' : t}
                      </text>
                    ))}
                  </g>
                </svg>
              </td>
              <td className="pt-1 pr-4">
                <svg width={RATIO_W + 8} height={12} className="overflow-visible">
                  <g transform="translate(4,0)">
                    {[0.5, 1, 2].map(v => (
                      <text key={v} x={rx(v)} y={10} fontSize={9} fill="#94a3b8" textAnchor="middle">
                        {v === 0.5 ? '×½' : `×${v}`}
                      </text>
                    ))}
                  </g>
                </svg>
              </td>
              <td />
            </tr>
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[10px] font-medium text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full" style={{ background: DIVERGING.above }} /> stays longer, interval clear of ×1
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full" style={{ background: DIVERGING.below }} /> stays shorter, interval clear of ×1
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full" style={{ background: '#475569' }} /> consistent with parity
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full" style={{ background: DIVERGING.muted }} /> fewer than {MIN_N} stays
        </span>
      </div>

      <p className="text-[10px] text-slate-400 leading-relaxed">
        The typical stay is the geometric mean of one plus the days, so a few year-long stays
        cannot outweigh hundreds of short ones; ×1.25 means a stay about a quarter longer.
        {standard !== 'crude' && <> Each stay is measured against the mean of the stays sharing its
          ICD-9 chapter{standard === 'chapterYear' ? ' and admission year' : ''} in the current selection, and a group's
          ratio averages those departures, so a group that stays longer only because it brought
          longer illnesses sits at ×1.
          {result.unstratified > 0 && <> {result.unstratified.toLocaleString()} stays have no
            chapter{standard === 'chapterYear' ? ' or year' : ''}, or are alone in their stratum, and
            enter the boxes but not the ratio.</>}</>}
        {' '}{result.total.toLocaleString()} stays are compared.
        {noStay > 0 && <> {noStay.toLocaleString()} selected records carry no usable length of stay and are left out.</>}
        {atlit > 0 && <> The {atlit.toLocaleString()} Atlit camp records (notebook 25) are left out: their stays are a detention camp's, not a ward's.</>}
        {deaths > 0 && <> {deaths.toLocaleString()} deaths are left out.</>}
        {hidden > 0 && <> {hidden} smaller {hidden === 1 ? 'group is' : 'groups are'} not shown.</>}
        {' '}Stays still differ by ward, class and outcome; the selectors above and the filters on
        the left are the way to hold those fixed too. A ratio here is a lead to read the pages
        behind, not a finding about care.
      </p>
    </div>
  );
};

export default StayPanel;
