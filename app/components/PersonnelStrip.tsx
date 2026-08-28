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
  /** Which body of evidence names this person. */
  origin: 'mideastmed' | 'press' | 'both';
  /** Present when the press names a post for this person. */
  post?: string;
  /** Press rows only: how firmly the source fixes the post. */
  certainty?: 'stated' | 'inferred';
  source?: string;
  note?: string;
}
interface PersonnelData {
  meta: {
    source: string; sourceUrl: string; sourceHome: string; licence: string;
    project: string; pi: string; institution: string;
    grant: string; grantKind: string;
    people: number; fromPress: number; merged: number;
    activities: number; undated: number;
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

/**
 * A press row's role is a sentence — "Deputy director", "Senior Medical
 * Officer" — not one of the MidEastMed professions, so it is read for the
 * profession inside it. Every one of these people is a physician; what
 * differs is the post, and the post belongs in the tooltip, not the hue.
 */
const roleColor = (r: string): string => {
  if (ROLE_COLOR[r]) return ROLE_COLOR[r];
  if (/surgeon|physician|medical officer|doctor|director/i.test(r)) {
    return ROLE_COLOR.Doctor;
  }
  return ROLE_FALLBACK;
};

/** One chip for every name that comes from the press and archives. */
const PRESS_FACET = 'Named in the press';

// Study is a different relationship to the building than work: these are the
// hospital's own nursing and midwifery pupils, not its staff.
const isStudy = (k: string): boolean => k === 'Study';

// Where a name came from, marked on the row itself. Two bodies of evidence
// with different reach: MidEastMed's prosopography is broad and shallow — it
// names midwives and pupils no newspaper ever mentioned — while the press and
// archives are narrow and deep, naming almost only the senior posts. A reader
// should be able to see which is speaking without opening anything.
//
// The MidEastMed red is taken from the tarbush in their own logo. It is a
// nod to their identity, not their artwork: their mark is a three-face line
// drawing that would be illegible at this size, and reproducing it would
// imply an endorsement they have not given.
const MEM_RED = '#8b0000';
const PRESS_INK = '#334155';

/** MidEastMed: a small tarbush, their logo's one unmistakable element. */
const MemMark: React.FC<{ x: number; y: number; dim?: boolean }> = ({ x, y, dim }) => (
  <g transform={`translate(${x},${y})`} opacity={dim ? 0.55 : 1}>
    <path d="M-3.1 2.2 L-2.4 -2.2 L2.4 -2.2 L3.1 2.2 Z"
      fill={MEM_RED} />
    <line x1="0" y1="-2.2" x2="0" y2="-4" stroke={MEM_RED} strokeWidth="0.9" />
    <circle cx="0" cy="-4.3" r="0.9" fill={MEM_RED} />
  </g>
);

/** Press and archives: a folded newspaper. */
const PressMark: React.FC<{ x: number; y: number; dim?: boolean }> = ({ x, y, dim }) => (
  <g transform={`translate(${x},${y})`} opacity={dim ? 0.55 : 1}>
    <rect x="-3.4" y="-3" width="6.8" height="6" rx="0.8"
      fill="none" stroke={PRESS_INK} strokeWidth="1" />
    <line x1="-1.8" y1="-1.1" x2="1.9" y2="-1.1" stroke={PRESS_INK} strokeWidth="0.9" />
    <line x1="-1.8" y1="0.4" x2="1.9" y2="0.4" stroke={PRESS_INK} strokeWidth="0.9" />
    <line x1="-1.8" y1="1.8" x2="0.6" y2="1.8" stroke={PRESS_INK} strokeWidth="0.9" />
  </g>
);

// ---------------------------------------------------------------- layout

// These margins are the Timeline's own (its `M`), not a choice of ours: the
// strip only aligns with the bands above if it plots into the same box. A
// year must cut vertically through every layer of the view, so left/right
// are copied and must be changed in step with TimelineView.
const M = { left: 56, right: 20, top: 8, bottom: 10 };
const ROW = 17;

const PersonnelStrip: React.FC<{
  /**
   * The window, in the Timeline's own units — months since 1900-01 — so both
   * share one scale exactly. The strip rounds to whole years for its markers
   * because the sources give years, but it places them on the month axis.
   */
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

  const loYear = Math.floor(lo / 12) + 1900;
  const hiYear = Math.floor(hi / 12) + 1900;

  // A press row's "role" is a sentence describing a post, not a category, so
  // the chips key on a coarser facet: the MidEastMed professions, plus one
  // chip for everyone the press and archives name.
  const facetOf = (p: Person): string =>
    p.origin === 'press' ? PRESS_FACET : p.role;

  const allRoles = useMemo(() => {
    if (!data) return [];
    const set = new Set<string>(data.people.map(facetOf));
    return Array.from(set).sort(
      (a, b) => (a === PRESS_FACET ? 1 : 0) - (b === PRESS_FACET ? 1 : 0)
        || a.localeCompare(b)
    );
  }, [data]);

  // Only people the current window can actually show. Filtering by role as
  // well keeps the strip's height honest: hidden rows leave no blank lanes.
  const shown = useMemo(() => {
    if (!data) return [];
    return data.people.filter(
      p => (!roles || roles.has(facetOf(p))) && p.last >= loYear && p.first <= hiYear
    );
  }, [data, roles, loYear, hiYear]);

  // Dropped by the axis rather than by the role filter — the two are different
  // kinds of absence and the caption must not blur them.
  const offWindow = useMemo(() => {
    if (!data) return 0;
    return data.people.filter(
      p => (!roles || roles.has(facetOf(p))) && !(p.last >= loYear && p.first <= hiYear)
    ).length;
  }, [data, roles, loYear, hiYear]);

  // The Timeline's scale, verbatim: months since 1900-01 across the same box.
  // Anything else and the year rules of the two views drift apart.
  const plotL = M.left;
  const plotR = width - M.right;
  const plotW = Math.max(80, plotR - plotL);
  const toM = (year: number): number => (year - 1900) * 12;
  const xm = (m: number): number => plotL + ((m - lo) / Math.max(hi - lo, 1)) * plotW;
  // A year's marker sits at the middle of that year — July — so a dot for 1946
  // cannot be confused with the rule that opens 1946.
  const x = (year: number): number => xm(toM(year) + 6);
  const halfYear = (6 / Math.max(hi - lo, 1)) * plotW;

  const height = M.top + shown.length * ROW + M.bottom;

  const ticks = useMemo(() => {
    const out: number[] = [];
    const yrs = hiYear - loYear;
    const step = yrs > 40 ? 10 : yrs > 18 ? 5 : yrs > 8 ? 2 : 1;
    for (let y = Math.ceil(loYear / step) * step; y <= hiYear; y += step) out.push(y);
    return out;
  }, [loYear, hiYear]);

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
          between {data.meta.first} and {data.meta.last} — staff, the senior
          officers, and, where the building taught them, its nursing and
          midwifery pupils. A solid bar is a period a source gives; a dot is a
          single sighting in a single year, which is most of what survives.
          Hover a line for the record.
        </p>
        <div className="mt-3 max-w-3xl space-y-2 text-[13px] leading-relaxed text-slate-600">
          <p className="text-slate-500">Two bodies of evidence, marked on every row.</p>
          <div className="flex gap-2.5">
            <svg width="13" height="15" viewBox="-6.5 -7.5 13 15"
              className="shrink-0 mt-[3px]" aria-hidden="true">
              <MemMark x={0} y={0.5} />
            </svg>
            <p>
              <strong className="font-semibold text-slate-800">
                {data.meta.people - data.meta.fromPress + data.meta.merged} from{' '}
                <a
                  href={data.meta.sourceHome}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-indigo-700 hover:text-indigo-900 underline"
                >
                  MidEastMed
                </a>
              </strong>{' '}
              — {data.meta.project}, the {data.meta.grantKind} project of{' '}
              {data.meta.pi}, {data.meta.institution} (
              <span className="font-mono text-[11.5px]">{data.meta.grant}</span>).
              Its reach extends to midwives and pupils no newspaper ever names.
            </p>
          </div>
          <div className="flex gap-2.5">
            <svg width="13" height="15" viewBox="-6.5 -7.5 13 15"
              className="shrink-0 mt-[3px]" aria-hidden="true">
              <PressMark x={0} y={0} />
            </svg>
            <p>
              <strong className="font-semibold text-slate-800">
                {data.meta.fromPress} from our own readings
              </strong>{' '}
              of the Hebrew and English press and the archives, which see almost
              only the senior posts — directors, deputies, medical officers. Each
              carries the source that names it.
              {data.meta.merged > 0 && ` ${data.meta.merged} person is named by
                both, and carries both marks on one line.`}
            </p>
          </div>
        </div>
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
                style={{ background: on
                  ? (r === PRESS_FACET ? PRESS_INK : roleColor(r)) : '#cbd5e1' }}
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
            — {offWindow} outside {loYear}–{hiYear}
          </span>
        )}
      </div>

      {/* The same box as the Timeline's main plot — identical padding and the
          same width/viewBox scaling — so the two SVGs map their user-space
          coordinates onto the same screen pixels and the years line up. */}
      <div
        ref={wrapRef}
        className="relative bg-white border border-slate-200 rounded-xl px-2 py-2"
      >
        {shown.length === 0 ? (
          <p className="text-sm text-slate-500 py-6">
            No one is recorded here in these years.
          </p>
        ) : (
          <svg
            width="100%"
            viewBox={`0 0 ${width} ${height}`}
            className="block select-none"
            role="img"
            aria-label={`${shown.length} people recorded at the hospital`}
            onMouseLeave={() => setHover(null)}
          >
            {/* Year rules, behind everything. A tick marks the START of its
                year, while a marker sits at the year's midpoint — so the rule
                is drawn half a year left of where that year's dots land. */}
            {/* Rules only, no year labels: the axis directly above this strip
                already carries them, and now that the two share a scale a
                second row of the same numbers would be noise. */}
            {ticks.map(t => {
              const tx = x(t) - halfYear;
              return (
                <line
                  key={t}
                  x1={tx} y1={M.top - 2} x2={tx} y2={height - M.bottom + 12}
                  stroke="#e2e8f0" strokeWidth={1}
                />
              );
            })}

            {shown.map((p, i) => {
              const y = M.top + i * ROW + ROW / 2;
              const active = card?.id === p.id;
              const c = roleColor(p.role);
              const pts = p.points.filter(q => q.year >= loYear && q.year <= hiYear);
              // The inferred bridge: only when sightings alone carry this
              // person across years, and only between the outermost dots.
              const bridge = p.spans.length === 0 && p.points.length > 1
                ? [Math.min(...p.points.map(q => q.year)),
                   Math.max(...p.points.map(q => q.year))]
                : null;

              // Anchor the label to this person's marks, clamped into the
              // plot so a career running off the left edge still gets a name.
              const right = Math.min(
                plotR, Math.max(x(p.last) + halfYear, plotL));
              const left = Math.max(plotL, Math.min(x(p.first), plotR));
              const label = p.name.length > 34
                ? `${p.name.slice(0, 33)}…` : p.name;
              // 6.1px/char matches the Timeline's own estimate for this size.
              // A person named by both bodies of evidence carries both marks.
              const marks = p.origin === 'both' ? [MemMark, PressMark]
                : p.origin === 'press' ? [PressMark] : [MemMark];
              const marksW = (marks.length - 1) * 9;
              const labelPx = label.length * 6.1 + 14 + marksW;
              const flip = right + labelPx > plotR;
              const labelX = flip ? left : right;

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

                  {/* The name rides with its own marks rather than sitting in
                      a left-hand column: the axis now belongs to the Timeline
                      above, and a gutter here would push every year out of
                      line with the bands. Labels go to the right of the marks
                      where there is room, and flip left near the frame. */}
                  <g>
                    {flip ? (
                      <>
                        <text
                          x={labelX - 9 - marksW} y={y + 3.6} textAnchor="end"
                          fontSize={11}
                          fill={active ? '#0f172a' : '#475569'}
                          className={active ? 'font-semibold' : ''}
                        >
                          {label}
                        </text>
                        {marks.map((Mk, k) => (
                          <Mk key={k} x={labelX - 4 - k * 9} y={y} dim={!active} />
                        ))}
                      </>
                    ) : (
                      <>
                        {marks.map((Mk, k) => (
                          <Mk key={k} x={labelX + 4 + k * 9} y={y} dim={!active} />
                        ))}
                        <text
                          x={labelX + 10 + marksW} y={y + 3.6}
                          fontSize={11}
                          fill={active ? '#0f172a' : '#475569'}
                          className={active ? 'font-semibold' : ''}
                        >
                          {label}
                        </text>
                      </>
                    )}
                  </g>

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
              // Follow the row's own marks horizontally so the card does not
              // cover the years it is describing.
              const anchor = card.first <= loYear
                ? plotL : Math.min(x(card.first), plotR);
              // The SVG scales to its container, so anchor the card in
              // percentages of user space rather than in raw pixels.
              const pct = Math.max(0, Math.min(
                ((anchor + 14) / width) * 100, 100));
              return {
                top: Math.min(top, Math.max(0, height - 150)),
                left: `min(${pct}%, calc(100% - 292px))`
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
              {card.origin === 'press' ? (
                <span className="shrink-0 mt-0.5 px-2 py-0.5 rounded-full text-[10px]
                  font-semibold border border-slate-300 text-slate-600 bg-slate-50">
                  Press
                </span>
              ) : (
                <span
                  className="shrink-0 mt-0.5 px-2 py-0.5 rounded-full text-[10px] font-semibold text-white"
                  style={{ background: roleColor(card.role) }}
                >
                  {card.role}
                </span>
              )}
            </div>

            <dl className="mt-3 space-y-1.5 text-[12px]">
              {card.spans.map((s, i) => (
                <div key={`s${i}`} className="flex gap-2">
                  <dt className="font-mono text-slate-900 w-[74px] shrink-0">
                    {s.from}–{s.to}
                  </dt>
                  <dd className="text-slate-600">
                    {s.kind === 'Study' ? 'Trained here'
                      : s.kind === 'Post' ? 'In post'
                      : 'Worked here'}
                  </dd>
                </div>
              ))}
              {card.points.map((q, i) => (
                <div key={`p${i}`} className="flex gap-2">
                  <dt className="font-mono text-slate-900 w-[74px] shrink-0">{q.year}</dt>
                  <dd className="text-slate-600">
                    {q.kind === 'Study' ? 'Recorded as a pupil'
                      : q.kind === 'Post' ? 'In post'
                      : 'Recorded here'}
                  </dd>
                </div>
              ))}
            </dl>

            {card.origin !== 'mideastmed' && (
              <div className="mt-2.5 border-t border-slate-100 pt-2 space-y-1.5">
                <p className="text-[12px] leading-snug text-slate-700">
                  {card.post || card.role}
                </p>
                {card.note && (
                  <p className="text-[11px] leading-snug text-slate-500">{card.note}</p>
                )}
                <p className="text-[11px] text-slate-400">
                  {card.certainty === 'inferred'
                    // An inferred post must never read as a printed one.
                    ? 'Deduced across readings — no single source states it.'
                    : 'Stated in the source.'}
                  {card.source && (
                    <span className="font-mono"> · {card.source}</span>
                  )}
                </p>
              </div>
            )}

            {card.origin === 'mideastmed' && card.spans.length === 0 && card.points.length > 0 && (
              <p className="mt-2.5 text-[11px] leading-snug text-slate-500 border-t border-slate-100 pt-2">
                {card.points.length > 1
                  ? 'Separate sightings, not a continuous term — the dashed rule joins them but no source covers the years between.'
                  : 'A single sighting in a single year. How long they served is not recorded.'}
              </p>
            )}

            {card.url && (
            <a
              href={card.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex items-center gap-1.5 text-[12px] font-semibold text-indigo-600 hover:text-indigo-800"
            >
              MidEastMed record
              <ExternalLink size={12} />
            </a>
            )}
          </div>
        )}
      </div>

      <p className="mt-3 text-[11px] leading-relaxed text-slate-400">
        {data.meta.activities} records for{' '}
        {data.meta.people - data.meta.fromPress} people from the{' '}
        <a
          href={data.meta.sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-slate-600"
        >
          MidEastMed record for this hospital
        </a>
        {data.meta.undated > 0 && `, ${data.meta.undated} of them undated and so absent here`}
        , used under {data.meta.licence}. Funded by the {data.meta.grantKind}{' '}
        <span className="font-mono">{data.meta.grant}</span>, {data.meta.pi},{' '}
        {data.meta.institution}. The remaining {data.meta.fromPress} names, and
        the posts they held, are our own readings — each row cites the source
        that names it. These are the people the surviving paperwork happens to
        name; the hospital employed many more.
      </p>
    </section>
  );
};

export default PersonnelStrip;
