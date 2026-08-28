import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ExternalLink } from 'lucide-react';

/**
 * The people the sources place inside the hospital, one line each.
 *
 * This strip shares the Timeline's axis and its discipline: it draws what a
 * source says and nothing more. The dates arrive in two shapes and the whole
 * design turns on keeping them apart —
 *
 *   a SPAN (1935–1948) is a period a source gives. Drawn solid.
 *   an ATTESTATION (1946) is a single sighting — an Official Gazette issue,
 *     an index entry. Drawn as a dot, because a bar from 1946 to 1946 would
 *     read as a tenure the source never claims.
 *
 * Where one person has several attestations, a dashed rule joins the first to
 * the last. That is an inference — they were here then, and here again later —
 * and it is drawn faintly so it cannot be mistaken for the solid case.
 *
 * We publish name, role, dates and a link back. The biographies stay
 * unpublished; the tooltip's link to mideastmed.org is where a reader who
 * wants a life should go. Data comes from pipeline/personnel_data.py.
 */

const DATA_URL = `${import.meta.env.BASE_URL}data/personnel.json`;

// ---------------------------------------------------------------- types

interface Span { from: number; to: number; kind: string; }
interface Point { year: number; kind: string; }
export interface Person {
  id: string; name: string; nameAr: string; role: string; url: string;
  kinds: string[]; spans: Span[]; points: Point[]; first: number; last: number;
}
interface PersonnelData {
  meta: {
    source: string; sourceUrl: string; licence: string;
    people: number; activities: number; undated: number;
    spans: number; points: number; first: number; last: number;
  };
  people: Person[];
}

// ---------------------------------------------------------------- palette

// Roles, not patient categories: these hues are deliberately outside the
// register's own scale in app/colors.ts so a nurse's line can never be read
// as a religion or a ward.
const ROLE_COLOR: Record<string, string> = {
  'Doctor': '#0f766e',
  'Doctor, Surgeon': '#0f766e',
  'Pharmacist': '#7c3aed',
  'Nurse': '#c2410c',
  'Midwife': '#a21caf'
};
const ROLE_FALLBACK = '#475569';
const roleColor = (r: string): string => ROLE_COLOR[r] || ROLE_FALLBACK;

// Study is a different relationship to the building than work: these are the
// hospital's own nursing and midwifery pupils, not its staff.
const isStudy = (k: string): boolean => k === 'Study';

// ---------------------------------------------------------------- layout

const M = { left: 8, right: 16, top: 8, bottom: 22 };
const ROW = 17;
const LABEL_W = 186;

const PersonnelStrip: React.FC<{
  /** Year window, shared with the Timeline so both read against one axis. */
  lo: number;
  hi: number;
}> = ({ lo, hi }) => {
  const [data, setData] = useState<PersonnelData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [roles, setRoles] = useState<Set<string> | null>(null);
  const [hover, setHover] = useState<{ p: Person; x: number; y: number } | null>(null);
  const [pinned, setPinned] = useState<Person | null>(null);

  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1100);

  useEffect(() => {
    let cancelled = false;
    fetch(DATA_URL)
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then((d: PersonnelData) => { if (!cancelled) setData(d); })
      .catch(() => {
        if (!cancelled) {
          setError('The personnel data could not be loaded. Run pipeline/personnel_data.py.');
        }
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(entries => {
      const w = entries[0]?.contentRect.width;
      if (w) setWidth(Math.max(680, Math.floor(w)));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Escape closes a pinned card, matching the Timeline's source drawer.
  useEffect(() => {
    if (!pinned) return undefined;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setPinned(null); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [pinned]);

  const allRoles = useMemo(() => {
    if (!data) return [];
    return Array.from(new Set(data.people.map(p => p.role))).sort();
  }, [data]);

  // Only people the current window can actually show. Filtering by role as
  // well keeps the strip's height honest: hidden rows leave no blank lanes.
  const shown = useMemo(() => {
    if (!data) return [];
    return data.people.filter(
      p => (!roles || roles.has(p.role)) && p.last >= lo && p.first <= hi
    );
  }, [data, roles, lo, hi]);

  // Dropped by the axis rather than by the role filter — the two are different
  // kinds of absence and the caption must not blur them.
  const offWindow = useMemo(() => {
    if (!data) return 0;
    return data.people.filter(
      p => (!roles || roles.has(p.role)) && !(p.last >= lo && p.first <= hi)
    ).length;
  }, [data, roles, lo, hi]);

  const plotL = M.left + LABEL_W;
  const plotR = width - M.right;
  const plotW = Math.max(80, plotR - plotL);
  // A year occupies a slot; its marker sits at the slot's middle, so a dot for
  // 1946 is not confusable with the rule that opens 1946.
  const slots = Math.max(hi - lo + 1, 1);
  const x = (year: number): number =>
    plotL + ((year - lo + 0.5) / slots) * plotW;
  const halfYear = plotW / slots / 2;

  const height = M.top + shown.length * ROW + M.bottom;

  const ticks = useMemo(() => {
    const out: number[] = [];
    const step = hi - lo > 40 ? 10 : hi - lo > 18 ? 5 : hi - lo > 8 ? 2 : 1;
    for (let y = Math.ceil(lo / step) * step; y <= hi; y += step) out.push(y);
    return out;
  }, [lo, hi]);

  if (error) {
    return (
      <div className="border border-amber-200 bg-amber-50 rounded-lg p-4 text-sm text-amber-800">
        {error}
      </div>
    );
  }
  if (!data) {
    return <div className="h-24 rounded-lg bg-slate-50 animate-pulse" />;
  }

  const card = pinned || hover?.p || null;

  return (
    <section className="mt-8" aria-label="Personnel">
      <header className="mb-3">
        <h3 className="text-base font-bold text-slate-900">Personnel</h3>
        <p className="mt-1 text-[13px] leading-relaxed text-slate-600 max-w-3xl">
          The {data.meta.people} people the sources place inside this hospital
          between {data.meta.first} and {data.meta.last} — staff and, where the
          building taught them, its nursing and midwifery pupils. A solid bar is
          a period a source gives; a dot is a single sighting in a single year,
          which is most of what survives. Hover a line for the record, or open
          the person on MidEastMed.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-1.5 mb-3 text-xs">
        {allRoles.map(r => {
          const on = !roles || roles.has(r);
          return (
            <button
              key={r}
              onClick={() => setRoles(prev => {
                const next = new Set(prev ?? allRoles);
                if (next.has(r)) next.delete(r); else next.add(r);
                if (next.size === 0 || next.size === allRoles.length) return null;
                return next;
              })}
              className={`px-2.5 py-1 rounded-full border transition-colors inline-flex items-center gap-1.5 ${
                on ? 'bg-white border-slate-300 text-slate-700'
                   : 'bg-slate-100 border-slate-200 text-slate-400'
              }`}
            >
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ background: on ? roleColor(r) : '#cbd5e1' }}
              />
              {r}
            </button>
          );
        })}
        {roles && (
          <button
            onClick={() => setRoles(null)}
            className="px-2.5 py-1 rounded-full border border-indigo-300 bg-indigo-50 text-indigo-700"
          >
            All roles
          </button>
        )}
        <span className="font-mono text-slate-400 ml-1">
          {shown.length} of {data.meta.people}
        </span>
        {offWindow > 0 && (
          // A silent shortfall reads as missing data. Say why the count moved:
          // these people are real and dated, just outside the years on screen.
          <span className="text-slate-400">
            — {offWindow} outside {lo}–{hi}
          </span>
        )}
      </div>

      <div ref={wrapRef} className="relative w-full">
        {shown.length === 0 ? (
          <p className="text-sm text-slate-500 py-6">
            No one is recorded here in these years.
          </p>
        ) : (
          <svg
            width={width}
            height={height}
            className="block select-none"
            role="img"
            aria-label={`${shown.length} people recorded at the hospital`}
            onMouseLeave={() => setHover(null)}
          >
            {/* Year rules, behind everything. A tick marks the START of its
                year, while a marker sits at the year's midpoint — so the rule
                is drawn half a year left of where that year's dots land. */}
            {ticks.map(t => {
              const tx = x(t) - halfYear;
              return (
                <g key={t}>
                  <line
                    x1={tx} y1={M.top - 2} x2={tx} y2={height - M.bottom + 4}
                    stroke="#e2e8f0" strokeWidth={1}
                  />
                  <text
                    x={tx} y={height - M.bottom + 16}
                    textAnchor="middle" fontSize={10}
                    className="font-mono" fill="#94a3b8"
                  >
                    {t}
                  </text>
                </g>
              );
            })}

            {shown.map((p, i) => {
              const y = M.top + i * ROW + ROW / 2;
              const active = card?.id === p.id;
              const c = roleColor(p.role);
              const pts = p.points.filter(q => q.year >= lo && q.year <= hi);
              // The inferred bridge: only when sightings alone carry this
              // person across years, and only between the outermost dots.
              const bridge = p.spans.length === 0 && p.points.length > 1
                ? [Math.min(...p.points.map(q => q.year)),
                   Math.max(...p.points.map(q => q.year))]
                : null;

              return (
                <g
                  key={p.id}
                  className="cursor-pointer"
                  role="button"
                  tabIndex={0}
                  aria-label={`${p.name}, ${p.role}`}
                  onMouseEnter={e => setHover({ p, x: e.clientX, y: e.clientY })}
                  onMouseMove={e => setHover({ p, x: e.clientX, y: e.clientY })}
                  onClick={() => setPinned(q => (q?.id === p.id ? null : p))}
                  onKeyDown={e => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setPinned(q => (q?.id === p.id ? null : p));
                    }
                  }}
                >
                  {/* full-width hit target, so thin marks stay reachable */}
                  <rect
                    x={M.left} y={y - ROW / 2} width={width - M.left - M.right} height={ROW}
                    fill={active ? '#f1f5f9' : 'transparent'}
                  />

                  <text
                    x={M.left + 4} y={y + 3.5}
                    fontSize={11}
                    fill={active ? '#0f172a' : '#475569'}
                    className={active ? 'font-semibold' : ''}
                  >
                    {p.name.length > 29 ? `${p.name.slice(0, 28)}…` : p.name}
                  </text>

                  {bridge && (
                    <line
                      x1={x(bridge[0])} y1={y} x2={x(bridge[1])} y2={y}
                      stroke={c} strokeWidth={1} strokeDasharray="2 3" opacity={0.42}
                    />
                  )}

                  {p.spans.map((s, j) => {
                    // A span runs to the END of its closing year, not to that
                    // year's midpoint: 1935–1948 covers all of 1948.
                    const a = Math.max(x(s.from), plotL);
                    const b = Math.min(x(s.to) + halfYear, plotR);
                    if (b < plotL || a > plotR) return null;
                    return (
                      <rect
                        key={j}
                        x={a} y={y - 3.5} width={Math.max(2, b - a)} height={7} rx={3.5}
                        fill={c}
                        opacity={active ? 1 : 0.8}
                        stroke={isStudy(s.kind) ? '#fff' : 'none'}
                        strokeWidth={isStudy(s.kind) ? 1 : 0}
                      />
                    );
                  })}

                  {pts.map((q, j) => (
                    // Study years are hollow, work years solid: the school and
                    // the staff are different facts about the same building.
                    <circle
                      key={j}
                      cx={x(q.year)} cy={y} r={isStudy(q.kind) ? 3.4 : 3.8}
                      fill={isStudy(q.kind) ? '#fff' : c}
                      stroke={c}
                      strokeWidth={isStudy(q.kind) ? 1.6 : 0}
                      opacity={active ? 1 : 0.85}
                    />
                  ))}
                </g>
              );
            })}
          </svg>
        )}

        {card && (
          <div
            className="absolute z-30 w-[280px] rounded-lg border border-slate-200 bg-white shadow-xl p-3.5"
            style={(() => {
              const idx = shown.findIndex(p => p.id === card.id);
              const top = M.top + idx * ROW + ROW + 6;
              return {
                top: Math.min(top, Math.max(0, height - 150)),
                left: Math.min(LABEL_W + 24, Math.max(8, width - 300))
              };
            })()}
            onMouseEnter={() => { /* keep open while the pointer is on it */ }}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="font-bold text-slate-900 text-[15px] leading-tight">
                  {card.name}
                </p>
                {card.nameAr && (
                  <p dir="rtl" className="text-slate-500 text-[13px] mt-0.5">
                    {card.nameAr}
                  </p>
                )}
              </div>
              <span
                className="shrink-0 mt-0.5 px-2 py-0.5 rounded-full text-[10px] font-semibold text-white"
                style={{ background: roleColor(card.role) }}
              >
                {card.role}
              </span>
            </div>

            <dl className="mt-3 space-y-1.5 text-[12px]">
              {card.spans.map((s, i) => (
                <div key={`s${i}`} className="flex gap-2">
                  <dt className="font-mono text-slate-900 w-[74px] shrink-0">
                    {s.from}–{s.to}
                  </dt>
                  <dd className="text-slate-600">
                    {s.kind === 'Study' ? 'Trained here' : 'Worked here'}
                  </dd>
                </div>
              ))}
              {card.points.map((q, i) => (
                <div key={`p${i}`} className="flex gap-2">
                  <dt className="font-mono text-slate-900 w-[74px] shrink-0">{q.year}</dt>
                  <dd className="text-slate-600">
                    {q.kind === 'Study' ? 'Recorded as a pupil' : 'Recorded here'}
                  </dd>
                </div>
              ))}
            </dl>

            {card.spans.length === 0 && card.points.length > 0 && (
              <p className="mt-2.5 text-[11px] leading-snug text-slate-500 border-t border-slate-100 pt-2">
                {card.points.length > 1
                  ? 'Separate sightings, not a continuous term — the dashed rule joins them but no source covers the years between.'
                  : 'A single sighting in a single year. How long they served is not recorded.'}
              </p>
            )}

            <a
              href={card.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex items-center gap-1.5 text-[12px] font-semibold text-indigo-600 hover:text-indigo-800"
            >
              MidEastMed record
              <ExternalLink size={12} />
            </a>
          </div>
        )}
      </div>

      <p className="mt-3 text-[11px] leading-relaxed text-slate-400">
        Personnel from{' '}
        <a
          href={data.meta.sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-slate-600"
        >
          MidEastMed
        </a>
        , Liat Kozma's ERC project ({data.meta.licence}) — {data.meta.activities} records
        for {data.meta.people} people
        {data.meta.undated > 0 && `, and ${data.meta.undated} undated ones no axis can place`}.
        These are the people the surviving paperwork happens to name; the hospital
        employed many more.
      </p>
    </section>
  );
};

export default PersonnelStrip;
