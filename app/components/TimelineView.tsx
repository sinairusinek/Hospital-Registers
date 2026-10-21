import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ExternalLink, X, Loader2, BookOpen } from 'lucide-react';
import { PageScan, PageScanIndex, usePageScans, pageImageUrl } from './ScanLink';
import PersonnelStrip from './PersonnelStrip';
import { colorsForRanked, ColorScale } from '../colors';
import { GROUP_DIM } from '../groups';

/**
 * The hospital's registers on one time axis, in four layers.
 *
 * The layers answer different questions and must not be collapsed into each
 * other: what was happening in the country, what the hospital did, how many
 * people it admitted, and which physical ledger says so. The fourth layer is
 * the one that keeps the third honest — an intake band drawn without its gaps
 * reads as a hospital that emptied in 1941, which is false. Every gap here is
 * an archival absence; the press has the hospital working throughout.
 *
 * The intake layer carries two series from pipeline/timeline_data.py — by month
 * for the long view, by day once the axis is zoomed past DAY_SPAN. They are
 * drawn on separate scales, since a month peaks near 450 and a day near 51, and
 * the caption on the y axis says which is in force.
 *
 * Data comes from pipeline/timeline_data.py. The view holds no history of its
 * own beyond layout.
 */

const DATA_URL = `${import.meta.env.BASE_URL}data/timeline.json`;

// ---------------------------------------------------------------- types

interface IntakeMonth { month: string; general: number; atlit: number; }
/** One way of colouring the band. Counts are over the general intake only, in
 *  `values` order, parallel to intake (month) and to daily (day); null where
 *  the register has no general admission. */
interface Facet {
  key: string; label: string; values: string[];
  month: (number[] | null)[]; day: (number[] | null)[];
  /** The Atlit book split the same way, keyed by month and by day. */
  atlitMonth?: Record<string, number[]>; atlitDay?: Record<string, number[]>;
}
/** One dated day: [date, general] or [date, general, atlit]. Packed as arrays
 *  by pipeline/timeline_data.py — 3,530 of them, and objects would dominate
 *  the file. Only days the register reaches are present. */
type IntakeDay = [string, number] | [string, number, number];
interface Gap { start: string; end: string; months: number; reason: string; }
interface Notebook {
  notebook: string; start: string; end: string; months: number;
  records: number; firstPage: number | null; atlit: boolean;
  /** The library's viewer for the whole notebook; null where it has none. */
  url?: string | null;
}
interface InstitutionalEvent {
  date: string; label: string; src: string | null; note: string;
  hasSource: boolean;
}
interface ExternalEvent {
  date: string; end: string | null; kind: string; label: string;
  scope: string; note: string; source: string;
}
interface Source {
  id: string; pub: string; place?: string; date: string; lang: string;
  url?: string; note?: string; orig?: string; trans?: string;
}
interface TimelineData {
  meta: {
    first: string; last: string; records: number; dated: number;
    undated: number; generalRecords: number; atlitRecords: number;
    atlitNotebook: string; sourceOrigin: string | null;
  };
  intake: IntakeMonth[];
  daily: IntakeDay[];
  /** Absent from a timeline.json built before the band could be split. */
  facets?: Facet[];
  gaps: Gap[];
  notebooks: Notebook[];
  institutional: InstitutionalEvent[];
  external: ExternalEvent[];
  sources: Record<string, Source>;
}

// ---------------------------------------------------------------- scales

// Below this many months on screen the axis names days rather than months, and
// the readout follows it. Two months is where day ticks stop colliding on a
// plot of any usable width.
const DAY_SPAN = 2;

// The floor on zooming in: about a fortnight. Closer than this and the axis is
// mostly empty — the register's own resolution is the day.
const MIN_SPAN = 0.5;

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Days in a month, Gregorian. The axis reaches day zoom, so February matters. */
const daysInMonth = (y: number, m: number): number =>
  [31, (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0 ? 29 : 28,
    31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m];

/** Months since 1900-01, so a date is a number the axis can place. */
const toM = (iso: string): number => {
  const y = Number(iso.slice(0, 4));
  const m = Number(iso.slice(5, 7) || '1');
  const d = Number(iso.slice(8, 10) || '1');
  // The day is carried as a fraction of its own month's length. A uniform /31
  // would be invisible at year zoom and wrong by up to three days at the end of
  // February, which at day zoom is the difference between two ticks.
  return (y - 1900) * 12 + (m - 1) + (d - 1) / daysInMonth(y, m - 1);
};

/** The inverse, back to a calendar day. */
const fromMParts = (n: number): { y: number; m: number; d: number } => {
  const total = Math.floor(n);
  const y = 1900 + Math.floor(total / 12);
  const m = ((total % 12) + 12) % 12;
  const frac = n - total;
  const d = Math.min(daysInMonth(y, m), Math.floor(frac * daysInMonth(y, m) + 1e-6) + 1);
  return { y, m, d };
};

const fromM = (n: number): string => {
  const { y, m } = fromMParts(n);
  return `${MONTH_NAMES[m]} ${y}`;
};

/**
 * A date typed by hand, to a month number. Accepts what a person actually
 * types: 1938, 1938-07, 7/1938, 6.7.1938, 1938-07-06. Day-first where it is
 * unambiguous, because the registers themselves are written that way
 * ("6.7.38"). Returns null for anything it cannot read, and the caller leaves
 * the field alone rather than guessing.
 *
 * `end` fills in the missing precision upward — a bare 1938 as a "to" means
 * the END of 1938, not its first instant — so "1938" in both fields is the
 * whole year rather than a zero-width range.
 */
function parseDateInput(text: string, end: boolean): number | null {
  const t = text.trim();
  if (!t) return null;
  const n = t.split(/[^0-9]+/).filter(Boolean).map(Number);
  if (!n.length || n.length > 3) return null;
  let y: number, mo: number, d: number | null = null;
  if (n.length === 1) {
    [y] = n; mo = end ? 12 : 1;
  } else {
    // Whichever part is four digits, or too large to be a month, is the year.
    const yi = n.findIndex(v => v > 31);
    if (yi === -1) return null;
    y = n[yi];
    const rest = n.filter((_, i) => i !== yi);
    if (rest.length === 1) {
      mo = rest[0];
    } else if (yi === 0) {
      [mo, d] = rest;              // 1938-07-06
    } else {
      [d, mo] = rest;              // 6.7.1938
    }
  }
  if (y < 100) y += y < 50 ? 1900 : 0;   // "38" is 1938
  if (y < 1800 || y > 2100 || mo < 1 || mo > 12) return null;
  const dim = daysInMonth(y, mo - 1);
  if (d !== null && (d < 1 || d > dim)) return null;
  if (d === null) d = end ? dim : 1;
  return toM(`${y}-${String(mo).padStart(2, '0')}-${String(d).padStart(2, '0')}`)
    + (end ? 1 / dim : 0);   // a "to" date includes its own day
}

/** Month or day, according to how much of the axis is on screen. */
const fromMDay = (n: number, span: number): string => {
  if (span > DAY_SPAN) return fromM(n);
  const { y, m, d } = fromMParts(n);
  return `${d} ${MONTH_NAMES[m]} ${y}`;
};

const longDate = (iso: string): string => {
  const [y, m, d] = iso.split('-');
  if (!d) return m ? `${MONTH_NAMES[Number(m) - 1]} ${y}` : y;
  return `${Number(d)} ${MONTH_NAMES[Number(m) - 1]} ${y}`;
};

// ---------------------------------------------------------------- palette

// The register's own hues come from app/colors.ts and mean what they mean
// everywhere else in the site. The event layers are deliberately outside that
// scale: they are not categories of patient, and must not be read as any.
const INTAKE = '#2a78d6';       // SERIES[0]
// The Atlit book is coloured like the rest of the band and set apart by a fine
// black frame: it is another institution's register, never part of the count.
const ATLIT_FRAME = '#0f172a';
const ATLIT = '#4a3aa7';        // SERIES[6]: the Atlit ledger in the notebooks strip
const GAP = '#898781';          // NEUTRAL: an absence, not a category

// The facet colours are the site's: Community keeps the fixed hues the
// Statistics pie and the Map give it, and the other facets are coloured by
// rank exactly as the Statistics pies are.
const facetColors = (f: Facet): ColorScale =>
  colorsForRanked(f.key === 'community' ? GROUP_DIM : f.label, f.values);

// The historical context is not a category of anything, and colouring it by
// kind put a second legend beside the band's. One quiet ink for all of it.
const EVENT = '#64748b';

const HOSPITAL = '#0f766e';     // the institution's own flag colour

// ---------------------------------------------------------------- layout

const M = { left: 56, right: 20, top: 14, bottom: 6 };
const EXT_LANE = 26;
const DOT_DROP = 9;   // marker below its label, never through it
const INST_LANE = 26;
const BAND_H = 132;
const NB_H = 13;
const OVERVIEW_H = 54;

interface Placed<T> {
  item: T; x: number; tx: number; lane: number; labelled: boolean;
}

/**
 * Lay flags out in lanes so no two labels collide.
 *
 * A label is only drawn if it can sit near its own dot without being pushed
 * far from it and without stacking the lanes into a wall of text: at twenty
 * years across, fifty labels do not fit, and the honest answer is to draw the
 * dot and let the tooltip and the drawer carry the words. Zooming in gives
 * the axis room and the labels come back. `maxLanes` is the ceiling; `slack`
 * is how far a label may drift from its dot before it is not worth drawing.
 */
function place<T>(
  items: T[],
  at: (t: T) => number,
  label: (t: T) => string,
  lo: number,
  hi: number,
  charW: number,
  maxLanes: number,
  slack: number
): Placed<T>[] {
  const rows: { lane: number; l: number; r: number }[] = [];
  // Earliest first, so a dense cluster gives its label to the event that
  // opens it rather than to whichever happens to be last in the file.
  const order = items
    .map((item, i) => ({ item, i, x: at(item) }))
    .sort((a, b) => a.x - b.x || a.i - b.i);

  const out = new Map<number, Placed<T>>();
  order.forEach(({ item, i, x }) => {
    const text = label(item);
    const half = text.length * charW / 2 + 9;
    const tx = Math.min(Math.max(x, lo + half), hi - half);
    let lane = 0;
    while (
      lane < maxLanes &&
      rows.some(r => r.lane === lane && !(tx + half < r.l || tx - half > r.r))
    ) {
      lane += 1;
    }
    // Too deep to stack, or shoved so far from its own dot that the stem
    // would mislead: keep the dot, drop the label.
    const labelled = lane < maxLanes && Math.abs(tx - x) <= slack + half * 0.15;
    if (labelled) rows.push({ lane, l: tx - half, r: tx + half });
    out.set(i, { item, x, tx, lane: labelled ? lane : 0, labelled });
  });

  return items.map((_, i) => out.get(i)!);
}

/** Year ticks, thinned so labels never overlap at any zoom. */
function yearTicks(lo: number, hi: number, width: number): number[] {
  const years: number[] = [];
  const y0 = 1900 + Math.floor(lo / 12);
  const y1 = 1900 + Math.ceil(hi / 12);
  for (let y = y0; y <= y1; y += 1) years.push(y);
  const step = Math.max(1, Math.ceil((years.length * 42) / Math.max(width, 1)));
  return years.filter((_, i) => i % step === 0);
}

/**
 * Day ticks for a span of a few weeks, thinned by the same arithmetic as the
 * years: how many labels fit in the width available. The first day of a month
 * carries the month's name, so a run of bare numbers never loses its footing.
 */
function dayTicks(lo: number, hi: number, width: number):
  { at: number; label: string; major: boolean }[] {
  const out: { at: number; label: string; major: boolean }[] = [];
  const start = fromMParts(lo);
  let y = start.y;
  let m = start.m;
  let d = start.d;
  const all: { at: number; y: number; m: number; d: number }[] = [];
  for (let guard = 0; guard < 400; guard += 1) {
    const at = (y - 1900) * 12 + m + (d - 1) / daysInMonth(y, m);
    if (at > hi) break;
    if (at >= lo) all.push({ at, y, m, d });
    d += 1;
    if (d > daysInMonth(y, m)) { d = 1; m += 1; }
    if (m > 11) { m = 0; y += 1; }
  }
  const step = Math.max(1, Math.ceil((all.length * 34) / Math.max(width, 1)));
  const perM = width / Math.max(hi - lo, 1e-6);   // pixels per month
  all.forEach((t, i) => {
    // A thinned axis must not drop the month boundary: it is the one tick that
    // says which month the bare numbers belong to. It is kept whatever the
    // thinning, and its neighbours give way to it — "1 Aug" is three glyphs
    // wider than a bare number and will collide with a 31st or a 2nd that the
    // even spacing would otherwise have kept.
    const major = t.d === 1;
    if (!major) {
      if (i % step !== 0) return;
      const near = all.find(o => o.d === 1 && Math.abs(o.at - t.at) * perM < 26);
      if (near) return;
    }
    out.push({
      at: t.at,
      label: major ? `${t.d} ${MONTH_NAMES[t.m]}` : String(t.d),
      major,
    });
  });
  return out;
}

// ---------------------------------------------------------------- drawer

const LANG_DIR: Record<string, 'rtl' | 'ltr'> = { Hebrew: 'rtl', Arabic: 'rtl' };

const SourceDrawer: React.FC<{
  source: Source | null;
  event: { label: string; note: string; date: string; sub?: string } | null;
  onClose: () => void;
}> = ({ source, event, onClose }) => {
  const open = Boolean(source || event);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const dir = source ? (LANG_DIR[source.lang] || 'ltr') : 'ltr';

  return (
    <>
      <div
        onClick={onClose}
        aria-hidden="true"
        className={`fixed inset-0 bg-slate-900/30 z-40 transition-opacity ${
          open ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Source"
        className={`fixed top-0 right-0 h-full w-[min(470px,94vw)] bg-white border-l border-slate-200
          shadow-2xl z-50 flex flex-col transition-transform duration-200 ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {open && (
          <>
            <header className="px-6 pt-5 pb-4 border-b border-slate-200 shrink-0">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-[10px] font-bold text-indigo-600 uppercase tracking-[0.16em] mb-2">
                    {source ? 'Source' : 'Event'}
                  </p>
                  <h2 className="text-xl font-bold text-slate-900 leading-tight">
                    {source ? source.pub : event?.label}
                  </h2>
                  <p className="mt-2 text-xs font-mono text-slate-500 flex flex-wrap gap-x-4 gap-y-1">
                    <span>{longDate(source ? source.date : event!.date)}</span>
                    {source?.place && <span>{source.place}</span>}
                    {source?.lang && <span>{source.lang}</span>}
                    {!source && event?.sub && <span>{event.sub}</span>}
                  </p>
                </div>
                <button
                  onClick={onClose}
                  aria-label="Close"
                  className="shrink-0 p-1.5 rounded border border-slate-200 text-slate-500
                    hover:bg-slate-50 hover:text-slate-900"
                >
                  <X size={15} />
                </button>
              </div>
            </header>

            <div className="px-6 py-5 overflow-y-auto custom-scrollbar text-[15px] leading-relaxed text-slate-700">
              {event && (
                <>
                  {source && (
                    <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-[0.13em] mb-2">
                      What it dates
                    </p>
                  )}
                  <p className="mb-5">
                    {source && <strong className="text-slate-900">{event.label}. </strong>}
                    {event.note}
                  </p>
                </>
              )}

              {source?.orig && (
                <>
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-[0.13em]
                    mb-2 pt-4 border-t border-slate-100">
                    The passage
                  </p>
                  <div
                    dir={dir}
                    className="bg-slate-50 border border-slate-200 rounded p-3.5 mb-2"
                    dangerouslySetInnerHTML={{ __html: source.orig }}
                  />
                </>
              )}

              {source?.trans && (
                <div
                  className="italic text-slate-500 mb-4"
                  dangerouslySetInnerHTML={{ __html: source.trans }}
                />
              )}

              {source?.note && (
                <>
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-[0.13em]
                    mb-2 pt-4 border-t border-slate-100">
                    Reading note
                  </p>
                  <div
                    className="[&_p]:mb-3 [&_p:last-child]:mb-0"
                    dangerouslySetInnerHTML={{ __html: source.note }}
                  />
                </>
              )}

              {source?.url && (
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 mt-5 px-3 py-2 rounded border border-slate-200
                    bg-slate-50 text-xs font-mono text-indigo-600 hover:border-indigo-400"
                >
                  <ExternalLink size={13} /> Open at the National Library
                </a>
              )}

              {source && !source.url && (
                <p className="mt-5 text-xs text-slate-400 leading-relaxed">
                  This title is not digitised at the National Library; the passage above is
                  the record.
                </p>
              )}
            </div>
          </>
        )}
      </aside>
    </>
  );
};

// ---------------------------------------------------------------- notebook panel

const NotebookPanel: React.FC<{
  notebook: Notebook | null;
  scans: PageScanIndex | null;
  onClose: () => void;
}> = ({ notebook, scans, onClose }) => {
  if (!notebook) return null;
  const scan: PageScan | undefined =
    scans?.get(`${notebook.notebook}/${notebook.firstPage ?? 1}`);

  return (
    <div className="absolute bottom-4 right-4 z-30 w-72 bg-white border border-slate-200
      rounded-xl shadow-xl overflow-hidden">
      <div className="flex items-start justify-between gap-2 px-4 pt-3 pb-2">
        <div>
          <p className="text-[10px] font-bold text-indigo-600 uppercase tracking-[0.16em]">
            Notebook {notebook.notebook}
          </p>
          <p className="text-xs text-slate-500 font-mono mt-1">
            {fromM(toM(notebook.start))} – {fromM(toM(notebook.end))}
          </p>
          <p className="text-xs text-slate-500 font-mono">
            {notebook.records.toLocaleString()} admissions
          </p>
        </div>
        <button
          onClick={onClose}
          aria-label="Close"
          className="p-1 rounded text-slate-400 hover:text-slate-900"
        >
          <X size={14} />
        </button>
      </div>
      {notebook.atlit && (
        <p className="px-4 pb-2 text-[11px] leading-snug text-amber-700 bg-amber-50 py-2 mx-4 mb-2 rounded">
          The Atlit camp's own admission book, not the hospital's general
          intake. It is excluded from every general statistic on this site.
        </p>
      )}
      {/* The card opens the whole notebook in the library's viewer; the first
          page is only its cover picture. Notebooks the library has no viewer
          link for fall back to the first page's scan. */}
      {notebook.url || scan ? (
        <a href={notebook.url || (scan?.service ? pageImageUrl(scan, 1400) : '#')}
          target="_blank" rel="noopener noreferrer"
          className="block border-t border-slate-100 hover:opacity-90">
          {scan && (
            <img
              src={pageImageUrl(scan, 560)}
              alt={`Notebook ${notebook.notebook}, page ${notebook.firstPage}`}
              loading="lazy"
              className="w-full h-36 object-cover object-top bg-slate-100"
            />
          )}
          <span className="flex items-center gap-1.5 px-4 py-2 text-[11px] font-mono text-indigo-600">
            <BookOpen size={12} />
            {notebook.url ? 'open the whole notebook' : `page ${notebook.firstPage} · open the scan`}
            <ExternalLink size={11} />
          </span>
        </a>
      ) : (
        <p className="px-4 pb-4 text-[11px] text-slate-400 leading-snug border-t border-slate-100 pt-2">
          No scan of this notebook is available online.
        </p>
      )}
    </div>
  );
};

// ---------------------------------------------------------------- view

const TimelineView: React.FC = () => {
  const [data, setData] = useState<TimelineData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const scans = usePageScans();

  const [range, setRange] = useState<[number, number] | null>(null);
  // The two date fields. Kept as text, not as parsed numbers: a half-typed
  // "1938-07" must stay on screen while the user finishes it.
  const [fromText, setFromText] = useState('');
  const [toText, setToText] = useState('');
  const [drawer, setDrawer] = useState<{
    source: Source | null;
    event: { label: string; note: string; date: string; sub?: string } | null;
  } | null>(null);
  const [openNotebook, setOpenNotebook] = useState<Notebook | null>(null);
  const [showNotebooks, setShowNotebooks] = useState(false);
  const [showAtlit, setShowAtlit] = useState(true);
  // The band's colouring: null for the plain intake, else a facet key.
  const [facetKey, setFacetKey] = useState<string | null>(null);
  // Each bar as shares of 100% rather than as counts.
  const [percent, setPercent] = useState(false);
  // The country's events. Folded by default: the band and the hospital's own
  // flags are the subject, and the context is there when it is asked for.
  const [showContext, setShowContext] = useState(false);
  // The hospital's own chronology, folded the same way.
  const [showHospital, setShowHospital] = useState(false);
  const [hover, setHover] = useState<
    { x: number; y: number; label: string; general: number; atlit: number;
      split?: number[] | null } | null
  >(null);

  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1100);

  useEffect(() => {
    let cancelled = false;
    // no-cache: revalidate with the server every time (a 304 when unchanged).
    // GitHub Pages serves max-age=600, and without this a redeploy that changes
    // the file's shape is invisible for ten minutes even across a hard refresh,
    // because the reload does not reach fetches the page makes itself.
    fetch(DATA_URL, { cache: 'no-cache' })
      .then(r => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((d: TimelineData) => { if (!cancelled) setData(d); })
      .catch(() => {
        if (!cancelled) {
          setError('The timeline data could not be loaded. Run pipeline/timeline_data.py.');
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

  // Full extent, padded a little either side so the first and last flags are
  // not pinned to the frame.
  const extent = useMemo<[number, number]>(() => {
    if (!data) return [toM('1929-01'), toM('1949-01')];
    return [toM(data.meta.first) - 12, toM(data.meta.last) + 9];
  }, [data]);

  const [lo, hi] = range ?? extent;

  const plotW = width - M.left - M.right;
  const x = useCallback(
    (m: number) => M.left + ((m - lo) / (hi - lo)) * plotW,
    [lo, hi, plotW]
  );
  const xFull = useCallback(
    (m: number) => M.left + ((m - extent[0]) / (extent[1] - extent[0])) * plotW,
    [extent, plotW]
  );
  const unx = useCallback(
    (px: number) => extent[0] + ((px - M.left) / plotW) * (extent[1] - extent[0]),
    [extent, plotW]
  );

  const visibleExternal = useMemo<ExternalEvent[]>(() => {
    if (!data || !showContext) return [];
    return data.external.filter(
      e => toM(e.date) <= hi && toM(e.end || e.date) >= lo
    );
  }, [data, showContext, lo, hi]);

  const visibleInstitutional = useMemo<InstitutionalEvent[]>(() => {
    if (!data || !showHospital) return [];
    return data.institutional.filter(e => toM(e.date) >= lo && toM(e.date) <= hi);
  }, [data, showHospital, lo, hi]);

  const charW = 6.1;
  // Wider spans get fewer lanes: at full extent the labels cannot all fit and
  // pretending otherwise buries the register band under them.
  const span = hi - lo;
  // At day zoom the events are spread over far more pixels each, so more of
  // them can carry a label rather than falling back to a bare dot.
  const laneBudget = span > 170 ? 3 : span > 90 ? 5 : span > 40 ? 7
    : span > DAY_SPAN ? 9 : 12;
  const slack = plotW / 9;

  const extPlaced = useMemo(
    () => place<ExternalEvent>(
      visibleExternal, e => x(toM(e.date)), e => e.label,
      M.left, width - M.right, charW, laneBudget, slack),
    [visibleExternal, x, width, laneBudget, slack]
  );
  const instPlaced = useMemo(
    () => place<InstitutionalEvent>(
      visibleInstitutional, e => x(toM(e.date)), e => e.label,
      M.left, width - M.right, charW, laneBudget, slack),
    [visibleInstitutional, x, width, laneBudget, slack]
  );

  const extLanes = Math.max(
    ...extPlaced.filter(p => p.labelled).map(p => p.lane + 1), 1);
  const instLanes = Math.max(
    ...instPlaced.filter(p => p.labelled).map(p => p.lane + 1), 1);

  const extTop = M.top;
  const extH = showContext ? extLanes * EXT_LANE : 0;
  const instTop = extTop + extH + (showContext ? 10 : 0);
  const instH = showHospital ? instLanes * INST_LANE : 0;
  const bandTop = instTop + instH + 12;
  const axisY = bandTop + BAND_H;
  const yearsY = axisY + 15;
  const nbTop = yearsY + 8;
  const nbH = showNotebooks ? NB_H + 10 : 0;
  const height = nbTop + nbH + M.bottom + 6;

  const dayZoom = hi - lo <= DAY_SPAN;

  // The days on screen, once the axis counts them. Filtered to the visible
  // range so a drag does not walk 3,530 rows per frame.
  const visibleDaily = useMemo(() => {
    if (!data || !dayZoom) return [];
    return data.daily
      .map((r, i) => ({ r, i }))
      .filter(({ r }) => {
        const at = toM(r[0]);
        return at >= lo - 0.05 && at <= hi + 0.05;
      });
  }, [data, dayZoom, lo, hi]);

  // Two scales, because one cannot serve both. A month peaks near 450 and a
  // day near 51: drawn against the monthly maximum, every daily bar would be a
  // sliver. The band is rescaled to whichever series it is drawing, and the
  // axis label beside it says which — otherwise the same height would silently
  // mean two different things.
  const maxIntake = useMemo(() => {
    if (!data) return 1;
    if (percent) return 100;
    if (dayZoom) {
      return Math.max(
        1,
        ...visibleDaily.map(({ r }) => r[1] + (showAtlit ? (r[2] ?? 0) : 0))
      );
    }
    return Math.max(
      1,
      ...data.intake.map(m => m.general + (showAtlit ? m.atlit : 0))
    );
  }, [data, showAtlit, dayZoom, visibleDaily, percent]);

  // The overview always draws whole months as counts, so it has its own scale
  // rather than borrowing the band's, which may be daily or in percent.
  const maxMonthly = useMemo(() => {
    if (!data) return 1;
    return Math.max(1, ...data.intake.map(m => m.general + (showAtlit ? m.atlit : 0)));
  }, [data, showAtlit]);

  const barY = useCallback(
    (v: number) => axisY - (v / maxIntake) * (BAND_H - 8),
    [axisY, maxIntake]
  );

  // ---- brush on the overview

  const ovRef = useRef<SVGSVGElement>(null);
  const drag = useRef<{ mode: 'new' | 'move'; a: number; b: number; grab: number } | null>(null);

  const ovX = useCallback(
    (m: number) => M.left + ((m - extent[0]) / (extent[1] - extent[0])) * plotW,
    [extent, plotW]
  );

  const pointerM = (e: React.PointerEvent | PointerEvent): number => {
    const svg = ovRef.current;
    if (!svg) return extent[0];
    const rect = svg.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * width;
    return Math.min(extent[1], Math.max(extent[0], unx(px)));
  };

  useEffect(() => {
    const move = (e: PointerEvent) => {
      if (!drag.current) return;
      const m = pointerM(e);
      if (drag.current.mode === 'new') {
        drag.current.b = m;
      } else {
        const span = drag.current.b - drag.current.a;
        let a = m - drag.current.grab;
        a = Math.min(Math.max(a, extent[0]), extent[1] - span);
        drag.current.a = a;
        drag.current.b = a + span;
      }
      const a = Math.min(drag.current.a, drag.current.b);
      const b = Math.max(drag.current.a, drag.current.b);
      // Below three months the axis has nothing left to show.
      if (b - a >= 3) setRange([a, b]);
    };
    const up = () => { drag.current = null; };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    return () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extent, width, plotW]);

  /**
   * A requested range, slid and clipped to sit inside the extent. Shared by
   * every way in — the zoom buttons, a click on a bar, the date fields — so a
   * range near 1930 or 1948 is nudged into view rather than clipped short and
   * silently narrower than asked for.
   */
  const clampRange = useCallback((a0: number, b0: number): [number, number] => {
    const span = Math.min(extent[1] - extent[0], Math.max(MIN_SPAN, b0 - a0));
    let a = (a0 + b0) / 2 - span / 2;
    let b = a + span;
    if (a < extent[0]) { b += extent[0] - a; a = extent[0]; }
    if (b > extent[1]) { a -= b - extent[1]; b = extent[1]; }
    return [Math.max(a, extent[0]), Math.min(b, extent[1])];
  }, [extent]);

  const zoom = (factor: number) => {
    const mid = (lo + hi) / 2;
    const span = (hi - lo) * factor;
    setRange(clampRange(mid - span / 2, mid + span / 2));
  };

  // Step to the previous or following slice, by half its width, so each new
  // view keeps the later (or earlier) half of the last one on screen.
  const pan = (dir: -1 | 1) => {
    const shift = dir * (hi - lo) / 2;
    setRange(clampRange(lo + shift, hi + shift));
  };
  const atStart = lo <= extent[0] + 0.01;
  const atEnd = hi >= extent[1] - 0.01;

  const openSource = (srcId: string | null, ev: InstitutionalEvent) => {
    setDrawer({
      source: srcId && data ? data.sources[srcId] ?? null : null,
      event: { label: ev.label, note: ev.note, date: ev.date }
    });
  };

  // ---- render

  if (error) {
    return (
      <div className="h-full flex items-center justify-center p-8">
        <p className="text-sm text-slate-500 max-w-md text-center">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="animate-spin text-indigo-500" size={28} />
      </div>
    );
  }

  const hiddenLabels =
    extPlaced.filter(p => !p.labelled).length +
    instPlaced.filter(p => !p.labelled).length;
  const ticks = dayZoom ? [] : yearTicks(lo, hi, plotW);
  const days = dayZoom ? dayTicks(lo, hi, plotW) : [];
  const monthTicks = !dayZoom && hi - lo <= 48;
  const zoomed = Boolean(range) && (hi - lo) < (extent[1] - extent[0]) - 0.5;
  // An older timeline.json has no facets; the colouring row is then not offered.
  const facets = data.facets ?? [];
  const facet = facets.find(f => f.key === facetKey) ?? null;
  const colorOf: ColorScale | null = facet ? facetColors(facet) : null;

  /**
   * One bar of the band, monthly or daily: the general intake, plain or split
   * by the facet, with the Atlit book on top when shown. In percent mode the
   * whole bar is 100 and every part is its share of it.
   */
  const bar = (
    key: string, a: number, w: number, hoverX: number, label: string,
    gen: number, atl: number, parts: number[] | null | undefined,
    atlParts: number[] | null | undefined
  ) => {
    const shownAtl = showAtlit ? atl : 0;
    const total = gen + shownAtl;
    if (!total) return null;
    const k = percent ? 100 / total : 1;
    const rects: React.ReactNode[] = [];
    // One segment of the bar from `from` upward: split by the facet when there
    // is one and the counts for it, else the plain intake blue.
    const segment = (tag: string, from: number, n: number, split?: number[] | null) => {
      if (facet && colorOf && split) {
        let base = from;
        split.forEach((c, i) => {
          if (!c) return;
          const y0 = barY(base * k);
          base += c;
          const y1 = barY(base * k);
          rects.push(<rect key={`${tag}${i}`} x={a} y={y1} width={w} height={y0 - y1}
            fill={colorOf(facet.values[i])} />);
        });
      } else if (n) {
        rects.push(<rect key={tag} x={a} y={barY((from + n) * k)} width={w}
          height={barY(from * k) - barY((from + n) * k)} fill={INTAKE} />);
      }
    };
    segment('g', 0, gen, parts);
    if (shownAtl) {
      segment('a', gen, atl, atlParts);
      rects.push(<rect key="frame" x={a} y={barY(total * k)} width={w}
        height={barY(gen * k) - barY(total * k)}
        fill="none" stroke={ATLIT_FRAME} strokeWidth={0.75} />);
    }
    // Clicking a bar zooms to it. The band is where you SEE the thing worth
    // looking at — a spike, a gap — and before this the only way to act on
    // that was seven presses of Zoom in, each one recentring on the middle of
    // the view rather than on what you were pointing at. A month opens to the
    // month; a day opens to a fortnight around itself, which is already inside
    // day mode.
    const focus = () => {
      const at = toM(key);
      const [a0, b0] = key.length > 7
        ? [at - MIN_SPAN / 2, at + MIN_SPAN / 2]
        : [at, at + 1];
      setRange(clampRange(a0, b0));
    };
    return (
      <g
        key={key}
        className="cursor-zoom-in"
        role="button"
        tabIndex={-1}
        aria-label={`Zoom to ${label}`}
        onClick={focus}
        onMouseEnter={() => setHover({
          x: hoverX, y: barY(total * k), label, general: gen, atlit: atl,
          split: facet ? parts : null,
        })}
      >
        {rects}
      </g>
    );
  };

  return (
    <div className="h-full overflow-y-auto custom-scrollbar bg-slate-50">
      <div className="max-w-[1400px] mx-auto px-6 py-8 space-y-5">

        <header className="space-y-2">
          <p className="text-[10px] font-bold text-indigo-600 uppercase tracking-[0.2em]">
            Haifa Government Hospital
          </p>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
            The registers in time
          </h1>
          <p className="text-slate-500 leading-relaxed max-w-3xl">
            Four layers on one axis: what was happening in the country, what the hospital
            itself did, how many people it admitted month by month, and which ledger says so.
            The country's events and the hospital's own are folded under <em>Historic
            context</em> and <em>Hospital history</em>. Colour the
            admissions by who the patients were or what became of them, and switch to
            percentages to compare the mix across years of very different size. Drag on
            the strip at the foot to zoom, or type a range into <em>Go to</em>; click any
            bar to zoom to it, any flag for its source. Below two months on screen both
            the axis and the intake band count days.
          </p>
        </header>

        {/* controls */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <button
            onClick={() => setShowContext(v => !v)}
            aria-expanded={showContext}
            className={`px-2.5 py-1 rounded-full border transition-colors ${
              showContext ? 'bg-white border-slate-300 text-slate-700'
                          : 'bg-slate-100 border-slate-200 text-slate-400'
            }`}
          >
            Historic context {showContext ? '▾' : '▸'}
          </button>
          <button
            onClick={() => setShowHospital(v => !v)}
            aria-expanded={showHospital}
            className={`px-2.5 py-1 rounded-full border transition-colors ${
              showHospital ? 'bg-white border-slate-300 text-slate-700'
                           : 'bg-slate-100 border-slate-200 text-slate-400'
            }`}
          >
            Hospital history {showHospital ? '▾' : '▸'}
          </button>

          <span className="w-px h-4 bg-slate-200 mx-1" />

          <button
            onClick={() => setShowAtlit(v => !v)}
            className={`px-2.5 py-1 rounded-full border transition-colors ${
              showAtlit ? 'bg-white border-slate-300 text-slate-700'
                        : 'bg-slate-100 border-slate-200 text-slate-400'
            }`}
          >
            Atlit camp book
          </button>
          <button
            onClick={() => setShowNotebooks(v => !v)}
            className={`px-2.5 py-1 rounded-full border transition-colors ${
              showNotebooks ? 'bg-white border-slate-300 text-slate-700'
                            : 'bg-slate-100 border-slate-200 text-slate-400'
            }`}
          >
            Notebooks
          </button>
          <button
            onClick={() => setPercent(v => !v)}
            title="Draw every bar as 100%, divided into its proportions"
            className={`px-2.5 py-1 rounded-full border transition-colors ${
              percent ? 'bg-white border-slate-300 text-slate-700'
                      : 'bg-slate-100 border-slate-200 text-slate-400'
            }`}
          >
            Percentages
          </button>

          <span className="w-px h-4 bg-slate-200 mx-1" />

          <button onClick={() => pan(-1)} disabled={!zoomed || atStart}
            title="Earlier: move back by half the range on screen"
            aria-label="Earlier"
            className="px-2.5 py-1 rounded-full border border-slate-300 bg-white text-slate-700 disabled:opacity-40 disabled:cursor-default">
            ←
          </button>
          <button onClick={() => pan(1)} disabled={!zoomed || atEnd}
            title="Later: move forward by half the range on screen"
            aria-label="Later"
            className="px-2.5 py-1 rounded-full border border-slate-300 bg-white text-slate-700 disabled:opacity-40 disabled:cursor-default">
            →
          </button>
          <button onClick={() => zoom(0.5)}
            className="px-2.5 py-1 rounded-full border border-slate-300 bg-white text-slate-700">
            Zoom in
          </button>
          <button onClick={() => zoom(2)}
            className="px-2.5 py-1 rounded-full border border-slate-300 bg-white text-slate-700">
            Zoom out
          </button>
          {zoomed && (
            <button onClick={() => setRange(null)}
              className="px-2.5 py-1 rounded-full border border-indigo-300 bg-indigo-50 text-indigo-700">
              Show all years
            </button>
          )}

          <span className="w-px h-4 bg-slate-200 mx-1" />

          {/* Go to a range. Seven presses of Zoom in is not a way to reach a
            * date you already have in mind, and the overview strip cannot be
            * dragged finer than a few months. Either field may be left empty:
            * a "from" alone runs to the end of the register, a "to" alone from
            * its start. */}
          <form
            className="flex items-center gap-1"
            onSubmit={e => {
              e.preventDefault();
              const a = parseDateInput(fromText, false);
              const b = parseDateInput(toText, true);
              if (a === null && b === null) return;
              setRange(clampRange(a ?? extent[0], b ?? extent[1]));
            }}
          >
            <label className="text-slate-400" htmlFor="tl-from">Go to</label>
            <input
              id="tl-from" value={fromText} onChange={e => setFromText(e.target.value)}
              placeholder="1938-07-06" size={10} inputMode="numeric"
              aria-label="Range start"
              className={`px-2 py-1 rounded-full border bg-white font-mono w-[9.5em] ${
                fromText && parseDateInput(fromText, false) === null
                  ? 'border-rose-300 text-rose-700' : 'border-slate-300 text-slate-700'
              }`}
            />
            <span className="text-slate-400">–</span>
            <input
              id="tl-to" value={toText} onChange={e => setToText(e.target.value)}
              placeholder="1938-07-31" size={10} inputMode="numeric"
              aria-label="Range end"
              className={`px-2 py-1 rounded-full border bg-white font-mono w-[9.5em] ${
                toText && parseDateInput(toText, true) === null
                  ? 'border-rose-300 text-rose-700' : 'border-slate-300 text-slate-700'
              }`}
            />
            <button type="submit"
              className="px-2.5 py-1 rounded-full border border-slate-300 bg-white text-slate-700">
              Go
            </button>
          </form>
          <span className="font-mono text-slate-400 ml-1">
            {fromMDay(lo, hi - lo)} – {fromMDay(hi, hi - lo)}
          </span>
          {hiddenLabels > 0 && (
            <span className="text-slate-400">
              · {hiddenLabels} flag{hiddenLabels === 1 ? '' : 's'} unlabelled
              here — hover, or zoom in for the names
            </span>
          )}
        </div>

        {/* what the band is coloured by */}
        {facets.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 text-xs -mt-2">
            <span className="text-slate-400 mr-1">Colour the admissions by</span>
            {[{ key: null as string | null, label: 'Nothing' },
              ...facets.map(f => ({ key: f.key as string | null, label: f.label }))].map(o => (
              <button
                key={o.key ?? 'none'}
                onClick={() => setFacetKey(o.key)}
                aria-pressed={facetKey === o.key}
                className={`px-2.5 py-1 rounded-full border transition-colors ${
                  facetKey === o.key ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                                     : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>
        )}

        {/* main plot */}
        <div
          ref={wrapRef}
          className="relative bg-white border border-slate-200 rounded-xl px-2 py-2"
        >
          <svg
            width="100%"
            viewBox={`0 0 ${width} ${height}`}
            role="img"
            aria-label="Timeline of the Haifa Government Hospital: external events, the
              hospital's own chronology, monthly admissions, and the surviving notebooks."
            onMouseLeave={() => setHover(null)}
          >
            {/* gaps, drawn first and behind everything */}
            {data.gaps.map(g => {
              const a = x(toM(g.start));
              const b = x(toM(g.end) + 1);
              if (b < M.left || a > width - M.right) return null;
              const l = Math.max(a, M.left);
              const r = Math.min(b, width - M.right);
              const wide = r - l > 78;
              return (
                <g key={g.start}>
                  <rect
                    x={l} y={bandTop} width={Math.max(0, r - l)} height={BAND_H}
                    fill={GAP} opacity={0.1}
                  />
                  {wide && (
                    <text
                      x={(l + r) / 2} y={bandTop + BAND_H / 2}
                      textAnchor="middle"
                      className="font-mono"
                      fontSize={10} fill={GAP}
                    >
                      <tspan x={(l + r) / 2} dy="-4">no register survives</tspan>
                      <tspan x={(l + r) / 2} dy="13">{g.months} months</tspan>
                    </text>
                  )}
                </g>
              );
            })}

            {/* external event spans */}
            {extPlaced.map(({ item, lane }) => {
              if (!item.end || item.end === item.date) return null;
              const a = Math.max(x(toM(item.date)), M.left);
              const b = Math.min(x(toM(item.end)), width - M.right);
              if (b <= a) return null;
              const y = extTop + lane * EXT_LANE + 11;
              return (
                <rect
                  key={`span-${item.date}-${item.label}`}
                  x={a} y={y - 3} width={b - a} height={6} rx={3}
                  fill={EVENT}
                  opacity={0.18}
                />
              );
            })}

            {/* external event flags */}
            {extPlaced.map(({ item, x: cx, tx, lane, labelled }) => {
              // Unlabelled flags share the bottom rule of the block, so they
              // read as a density of events rather than as a broken stack.
              const y = labelled
                ? extTop + lane * EXT_LANE + 11
                : extTop + extH + 2;
              const color = EVENT;
              return (
                <g
                  key={`ext-${item.date}-${item.label}`}
                  role="button"
                  tabIndex={0}
                  className="cursor-pointer"
                  onClick={() => setDrawer({
                    source: null,
                    event: {
                      label: item.label,
                      note: `${item.note}${item.source ? `\n\nSource: ${item.source}` : ''}`,
                      date: item.date,
                      sub: item.scope
                    }
                  })}
                  onKeyDown={e => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setDrawer({
                        source: null,
                        event: {
                          label: item.label, note: item.note,
                          date: item.date, sub: item.scope
                        }
                      });
                    }
                  }}
                >
                  <title>{`${longDate(item.date)} — ${item.label}`}</title>
                  <line
                    x1={cx} y1={y + (labelled ? DOT_DROP : 0)}
                    x2={cx} y2={bandTop - 2}
                    stroke={color} strokeWidth={0.75}
                    opacity={labelled ? 0.2 : 0.13}
                  />
                  {labelled ? (
                    <>
                      <rect
                        x={tx - item.label.length * charW / 2 - 5} y={y - 8}
                        width={item.label.length * charW + 10} height={16}
                        fill="transparent"
                      />
                      <text
                        x={tx} y={y + 3.5} textAnchor="middle"
                        fontSize={10.5} fill="#334155"
                        className="select-none"
                      >
                        {item.label}
                      </text>
                    </>
                  ) : (
                    <circle cx={cx} cy={y} r={7} fill="transparent" />
                  )}
                </g>
              );
            })}

            {/* institutional flags */}
            {instPlaced.map(({ item, x: cx, tx, lane, labelled }) => {
              const y = labelled
                ? instTop + lane * INST_LANE + 11
                : instTop + instH + 2;
              return (
                <g
                  key={`inst-${item.date}-${item.label}`}
                  role="button"
                  tabIndex={0}
                  className="cursor-pointer"
                  onClick={() => openSource(item.src, item)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      openSource(item.src, item);
                    }
                  }}
                >
                  <title>
                    {`${longDate(item.date)} — ${item.label}${
                      item.hasSource ? ' (open the source)' : ''}`}
                  </title>
                  <line
                    x1={cx} y1={y + (labelled ? DOT_DROP : 0)}
                    x2={cx} y2={bandTop - 2}
                    stroke={HOSPITAL} strokeWidth={0.75} opacity={0.28}
                  />
                  {labelled ? (
                    <text
                      x={tx} y={y + 3.5} textAnchor="middle"
                      fontSize={11} fill={HOSPITAL} fontWeight={500}
                      className="select-none"
                    >
                      {item.label}
                      {item.hasSource && <tspan fontSize={9} dy={-3}> ↗</tspan>}
                    </text>
                  ) : (
                    <circle cx={cx} cy={y} r={7} fill="transparent" />
                  )}
                </g>
              );
            })}

            {/* Every marker in one pass, above all the words: a dot must never
                be buried by a neighbouring label, and a label must never be
                pierced by a neighbouring dot. */}
            {extPlaced.map(({ item, x: cx, lane, labelled }) => (
              <circle
                key={`extdot-${item.date}-${item.label}`}
                cx={cx}
                cy={labelled
                  ? extTop + lane * EXT_LANE + 11 + DOT_DROP
                  : extTop + extH + 2}
                r={labelled ? 3 : 2.6}
                fill={EVENT}
                stroke="#fff" strokeWidth={1}
                pointerEvents="none"
              />
            ))}
            {instPlaced.map(({ item, x: cx, lane, labelled }) => (
              <circle
                key={`instdot-${item.date}-${item.label}`}
                cx={cx}
                cy={labelled
                  ? instTop + lane * INST_LANE + 11 + DOT_DROP
                  : instTop + instH + 2}
                r={3.4}
                fill={item.hasSource ? HOSPITAL : '#fff'}
                stroke={item.hasSource ? '#fff' : HOSPITAL} strokeWidth={1.4}
                pointerEvents="none"
              />
            ))}

            {/* intake band — daily
              *
              * Below DAY_SPAN the band redraws from the daily series. Only days
              * the register reaches are in it, so a day with no bar means no
              * admission recorded, and a stretch with no bars at all means no
              * ledger — the gap layer above says which. The band is rescaled to
              * the days on screen; the caption beside it says so, because the
              * same bar height means one thing per month and another per day.
              */}
            {dayZoom && visibleDaily.map(({ r, i }) => {
              const at = toM(r[0]);
              const a = x(at);
              // One day in month units, from this day's own month: the same
              // arithmetic toM uses, so a bar starts on its tick and ends on
              // the next one rather than drifting through February.
              const dayW = x(at + 1 / daysInMonth(
                Number(r[0].slice(0, 4)), Number(r[0].slice(5, 7)) - 1)) - a;
              const b = a + dayW;
              if (b < M.left || a > width - M.right) return null;
              const w = Math.max(1.2, dayW - (dayW > 4 ? 1 : 0.2));
              return bar(r[0], a, w, a + w / 2, longDate(r[0]),
                r[1], r[2] ?? 0, facet?.day[i], facet?.atlitDay?.[r[0]]);
            })}

            {/* intake band — monthly */}
            {!dayZoom && data.intake.map((m, i) => {
              const a = x(toM(m.month));
              const b = x(toM(m.month) + 1);
              if (b < M.left || a > width - M.right) return null;
              const w = Math.max(0.8, b - a - (b - a > 4 ? 1 : 0.2));
              return bar(m.month, a, w, (a + b) / 2, fromM(toM(m.month)),
                m.general, m.atlit, facet?.month[i], facet?.atlitMonth?.[m.month]);
            })}

            {/* hover readout */}
            {hover && (() => {
              // One line per figure: the date, the total, then a line per
              // facet value when the band is split, then the Atlit book. In
              // percent mode each carries its share of the whole bar too.
              const whole = hover.general + (showAtlit ? hover.atlit : 0);
              const pct = (n: number) => (percent && whole
                ? ` (${(100 * n / whole).toFixed(n / whole < 0.1 ? 1 : 0)}%)` : '');
              const lines: { text: string; fill: string; swatch?: string }[] = [
                { text: hover.label, fill: '#fff' },
                { text: `${hover.general.toLocaleString()} admissions${pct(hover.general)}`, fill: '#fff' },
              ];
              if (facet && colorOf && hover.split) {
                hover.split.forEach((n, i) => {
                  if (n) lines.push({
                    text: `${n.toLocaleString()} ${facet.values[i]}${pct(n)}`,
                    fill: '#e2e8f0', swatch: colorOf(facet.values[i]),
                  });
                });
              }
              if (showAtlit && hover.atlit > 0) {
                lines.push({ text: `${hover.atlit.toLocaleString()} at Atlit${pct(hover.atlit)}`, fill: '#c7d2fe' });
              }
              const longest = Math.max(...lines.map(l => l.text.length + (l.swatch ? 2 : 0)));
              const boxW = Math.max(124, 18 + longest * 6.4);
              const boxH = 8 + lines.length * 14;
              const bx = Math.min(Math.max(hover.x - boxW / 2, M.left), width - M.right - boxW);
              const by = Math.max(bandTop + 2, Math.min(hover.y - 42, axisY - boxH));
              return (
                <g pointerEvents="none">
                  <line
                    x1={hover.x} y1={bandTop} x2={hover.x} y2={axisY}
                    stroke="#0f172a" strokeWidth={0.6} opacity={0.3}
                  />
                  <rect x={bx} y={by} width={boxW} height={boxH} rx={4}
                    fill="#0f172a" opacity={0.9} />
                  {lines.map((l, i) => (
                    <g key={i}>
                      {l.swatch && (
                        <rect x={bx + 9} y={by + 7 + i * 14} width={7} height={7}
                          rx={1.5} fill={l.swatch} />
                      )}
                      <text
                        x={bx + 9 + (l.swatch ? 11 : 0)} y={by + 15 + i * 14}
                        fontSize={10.5} fill={l.fill} className="font-mono"
                      >
                        {l.text}
                      </text>
                    </g>
                  ))}
                </g>
              );
            })()}

            {/* y axis
              *
              * The step follows the scale in force. Rounding to 50 suits a
              * monthly band peaking near 450 and erases a daily one peaking
              * near 51, where both gridlines would round to the same number or
              * to nothing at all.
              */}
            {[0.5, 1].map(f => {
              const grid = maxIntake >= 200 ? 50 : maxIntake >= 40 ? 10 : 5;
              const v = Math.round((maxIntake * f) / grid) * grid;
              if (!v) return null;
              return (
                <g key={f}>
                  <line
                    x1={M.left} y1={barY(v)} x2={width - M.right} y2={barY(v)}
                    stroke="#e2e8f0" strokeWidth={1}
                  />
                  <text
                    x={M.left - 7} y={barY(v) + 3.5} textAnchor="end"
                    fontSize={10} fill="#94a3b8" className="font-mono"
                  >
                    {v}
                  </text>
                </g>
              );
            })}
            <text
              x={M.left - 7} y={bandTop + 9} textAnchor="end"
              fontSize={9} fill="#cbd5e1" className="font-mono"
            >
              {percent ? '% of bar' : dayZoom ? 'adm./day' : 'adm./mo.'}
            </text>

            {/* axis */}
            <line
              x1={M.left} y1={axisY} x2={width - M.right} y2={axisY}
              stroke="#94a3b8" strokeWidth={1}
            />
            {ticks.map(y => {
              const px = x(toM(`${y}-01`));
              if (px < M.left - 1 || px > width - M.right + 1) return null;
              return (
                <g key={y}>
                  <line x1={px} y1={axisY} x2={px} y2={axisY + 4} stroke="#94a3b8" />
                  <text
                    x={px} y={yearsY} textAnchor="middle"
                    fontSize={11} fill="#64748b" className="font-mono"
                  >
                    {y}
                  </text>
                </g>
              );
            })}
            {monthTicks && Array.from({ length: Math.ceil(hi - lo) + 1 }, (_, i) => {
              const m = Math.floor(lo) + i;
              if (m % 12 === 0) return null;
              const px = x(m);
              if (px < M.left || px > width - M.right) return null;
              return (
                <line
                  key={`mt-${m}`} x1={px} y1={axisY} x2={px} y2={axisY + 2.5}
                  stroke="#cbd5e1"
                />
              );
            })}
            {days.map(t => {
              const px = x(t.at);
              if (px < M.left - 1 || px > width - M.right + 1) return null;
              return (
                <g key={`d-${t.at}`}>
                  <line
                    x1={px} y1={axisY} x2={px} y2={axisY + (t.major ? 4 : 2.5)}
                    stroke={t.major ? '#94a3b8' : '#cbd5e1'}
                  />
                  <text
                    x={px} y={yearsY} textAnchor="middle" fontSize={11}
                    fill={t.major ? '#475569' : '#94a3b8'} className="font-mono"
                  >
                    {t.label}
                  </text>
                </g>
              );
            })}

            {/* notebooks */}
            {showNotebooks && data.notebooks.map((nb, i) => {
              const a = x(toM(nb.start));
              const b = x(toM(nb.end) + 1);
              if (b < M.left || a > width - M.right) return null;
              const l = Math.max(a, M.left);
              const r = Math.min(b, width - M.right);
              // Overlapping notebooks are the rule, not the exception — several
              // ledgers ran at once. Two rows keep them legible.
              const row = i % 2;
              const y = nbTop + row * 7;
              return (
                <g
                  key={nb.notebook}
                  className="cursor-pointer"
                  role="button"
                  tabIndex={0}
                  onClick={() => setOpenNotebook(nb)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setOpenNotebook(nb);
                    }
                  }}
                >
                  <title>
                    {`Notebook ${nb.notebook}: ${fromM(toM(nb.start))} – ${
                      fromM(toM(nb.end))}, ${nb.records.toLocaleString()} admissions`}
                  </title>
                  <rect
                    x={l} y={y} width={Math.max(1.5, r - l)} height={5.5} rx={2}
                    fill={nb.atlit ? ATLIT : '#475569'}
                    opacity={openNotebook?.notebook === nb.notebook ? 1 : 0.55}
                  />
                  {r - l > 20 && (
                    <text
                      x={(l + r) / 2} y={y + 4.4} textAnchor="middle"
                      fontSize={6.5} fill="#fff" className="font-mono select-none"
                    >
                      {nb.notebook}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>

          <NotebookPanel
            notebook={openNotebook}
            scans={scans}
            onClose={() => setOpenNotebook(null)}
          />
        </div>

        {/* overview + brush */}
        <div className="bg-white border border-slate-200 rounded-xl px-2 pt-2 pb-1">
          <svg
            ref={ovRef}
            width="100%"
            viewBox={`0 0 ${width} ${OVERVIEW_H}`}
            className="cursor-crosshair touch-none"
            role="slider"
            aria-label="Zoom range"
            aria-valuemin={extent[0]}
            aria-valuemax={extent[1]}
            aria-valuenow={lo}
            tabIndex={0}
            onKeyDown={e => {
              const span = hi - lo;
              const step = Math.max(1, span / 8);
              if (e.key === 'ArrowLeft') {
                e.preventDefault();
                setRange([Math.max(extent[0], lo - step),
                  Math.max(extent[0] + span, hi - step)]);
              } else if (e.key === 'ArrowRight') {
                e.preventDefault();
                setRange([Math.min(extent[1] - span, lo + step),
                  Math.min(extent[1], hi + step)]);
              }
            }}
            onPointerDown={e => {
              const m = pointerM(e);
              if (zoomed && m >= lo && m <= hi) {
                drag.current = { mode: 'move', a: lo, b: hi, grab: m - lo };
              } else {
                drag.current = { mode: 'new', a: m, b: m, grab: 0 };
              }
            }}
          >
            {/* the whole intake, unzoomed */}
            {data.intake.map(m => {
              const total = m.general + (showAtlit ? m.atlit : 0);
              if (!total) return null;
              const a = ovX(toM(m.month));
              const b = ovX(toM(m.month) + 1);
              const h = (total / maxMonthly) * (OVERVIEW_H - 20);
              return (
                <rect
                  key={m.month}
                  x={a} y={OVERVIEW_H - 14 - h}
                  width={Math.max(0.7, b - a - 0.3)} height={h}
                  fill={INTAKE} opacity={0.55}
                />
              );
            })}
            {data.gaps.map(g => (
              <rect
                key={g.start}
                x={ovX(toM(g.start))}
                y={4}
                width={Math.max(0, ovX(toM(g.end) + 1) - ovX(toM(g.start)))}
                height={OVERVIEW_H - 18}
                fill={GAP} opacity={0.12}
              />
            ))}
            <line
              x1={M.left} y1={OVERVIEW_H - 14} x2={width - M.right} y2={OVERVIEW_H - 14}
              stroke="#cbd5e1"
            />
            {yearTicks(extent[0], extent[1], plotW).map(y => {
              const px = ovX(toM(`${y}-01`));
              if (px < M.left - 1 || px > width - M.right + 1) return null;
              return (
                <text
                  key={y} x={px} y={OVERVIEW_H - 3} textAnchor="middle"
                  fontSize={9} fill="#94a3b8" className="font-mono"
                >
                  {y}
                </text>
              );
            })}
            {/* the window */}
            <rect
              x={M.left} y={2} width={Math.max(0, ovX(lo) - M.left)}
              height={OVERVIEW_H - 16} fill="#0f172a" opacity={0.06}
            />
            <rect
              x={ovX(hi)} y={2} width={Math.max(0, width - M.right - ovX(hi))}
              height={OVERVIEW_H - 16} fill="#0f172a" opacity={0.06}
            />
            <rect
              x={ovX(lo)} y={2} width={Math.max(2, ovX(hi) - ovX(lo))}
              height={OVERVIEW_H - 16}
              fill="none" stroke="#4f46e5" strokeWidth={1.4} rx={2}
              className={zoomed ? 'cursor-grab' : ''}
            />
          </svg>
        </div>

        {/* legend + the caveats that belong under the picture */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-xs text-slate-500">
          <div className="space-y-1.5">
            <p className="font-semibold text-slate-700">The band</p>
            {facet && colorOf ? (
              <>
                <p>{dayZoom ? 'Daily' : 'Monthly'} admissions, general register,
                  by {facet.label.toLowerCase()}{percent ? ', as shares of each bar' : ''}:</p>
                <p className="flex flex-wrap gap-x-3 gap-y-1">
                  {facet.values.map(k => (
                    <span key={k} className="flex items-center gap-1.5">
                      <span className="w-3 h-3 rounded-sm" style={{ background: colorOf(k) }} />
                      {k}
                    </span>
                  ))}
                </p>
                {facet.key === 'community' && (
                  <p className="leading-relaxed">
                    Community is religion crossed with nationality, as on the Statistics
                    page; <em>Not recorded</em> is a Muslim or Christian with no nationality,
                    or no religion at all.
                  </p>
                )}
                {facet.values.includes('Others') && (
                  <p className="leading-relaxed">
                    <em>Others</em> pools every value past the seven commonest.
                  </p>
                )}
              </>
            ) : (
              <p className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm" style={{ background: INTAKE }} />
                {dayZoom ? 'Daily' : 'Monthly'} admissions, general register
                {percent ? ', as shares of each bar' : ''}
              </p>
            )}
            <p className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-sm"
                style={{ background: facet ? '#fff' : INTAKE, border: `1px solid ${ATLIT_FRAME}` }} />
              Notebook {data.meta.atlitNotebook}: the Atlit camp book, coloured like the rest
              and framed in black
            </p>
          </div>
          <div className="space-y-1.5">
            <p className="font-semibold text-slate-700">The gaps</p>
            <p className="leading-relaxed">
              Grey marks months for which <strong>no register survives</strong> — not months
              in which the hospital admitted nobody. The press has it working throughout,
              including the 37-month hole of 1941–43.
            </p>
          </div>
          <div className="space-y-1.5">
            <p className="font-semibold text-slate-700">The flags</p>
            <p className="leading-relaxed">
              A filled dot has a source behind it: click for the passage, its translation
              where the original is not English, and a link to the newspaper.
            </p>
          </div>
          <div className="space-y-1.5">
            <p className="font-semibold text-slate-700">The counts</p>
            <p className="leading-relaxed font-mono">
              {data.meta.generalRecords.toLocaleString()} general
              {' + '}{data.meta.atlitRecords.toLocaleString()} Atlit admissions;
              {' '}{data.meta.undated.toLocaleString()} records carry no usable
              admission date and are absent from the band.
            </p>
          </div>
        </div>

        {/* The personnel share this view's axis exactly — same window, same
            margins, and the same content box — so a given year cuts
            vertically through the event lanes, the intake band and the staff
            lines alike. The strip rounds to whole years for its own markers,
            because the sources give years, but places them on this month
            scale. It must stay inside this container: moved out, it picks up
            different padding and every year drifts. */}
        <PersonnelStrip lo={lo} hi={hi} />
      </div>

      <SourceDrawer
        source={drawer?.source ?? null}
        event={drawer?.event ?? null}
        onClose={() => setDrawer(null)}
      />
    </div>
  );
};

export default TimelineView;
