import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar
} from 'recharts';
import { MapPin, X, Layers, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, Download } from 'lucide-react';
import { RegistryRecord, RangeFilter } from '../types';
import { UNKNOWN } from '../facets';
import { SERIES } from '../colors';
import { PieScheme, communityScheme, chapterScheme, usePieMode } from '../pieSchemes';
import { PieModeSwitch, PieLegend } from './PieControls';
import HelpPanel, { HelpSection } from './HelpPanel';
import ScanLink, { usePageScans } from './ScanLink';

declare const Papa: any;

/**
 * Where the patients came from, on the ground.
 *
 * The map draws only the City values the Kima review confirmed — a point here
 * is a decision somebody made and signed, not a string a geocoder guessed at.
 * Everything the review could not place is counted in the footer rather than
 * dropped, because a map that silently omits a third of the records reads as a
 * catchment far tighter than the registers actually describe.
 *
 * Coordinates come from pipeline/place_coords.py: Kima's own point for the
 * matched place, Wikidata P625 where the gazetteer entry carries none.
 */

const COORDS_URL = `${import.meta.env.BASE_URL}data/place-coords.tsv`;

const HELP: HelpSection[] = [
  {
    heading: 'What a pie is',
    body: <p>One place, sized by how many admissions name it, and cut like a pie by <em>Community</em> — religion crossed with nationality, as on the Statistics page — so each slice is that community's share of the admissions from there, in the same colours the charts use. Grey is records whose community cannot be told. The <em>Pies show</em> switch at the top right recuts every pie by <em>diagnosis</em> instead: the ICD-9 chapter, in the colours the Statistics page gives it. The eight commonest chapters in the whole registry keep their own slice; the other eleven share a pale <em>Other chapters</em> slice, and grey is records with no ICD-9 code — a diagnosis not yet coded, or none written. The pies follow the admission dates: narrow them in the box at the top of the map, or send a range from the Timeline, and every pie is recut for those admissions alone. The range is the same one the Browser's Admission Date slider sets, so the two always show the same admissions. No other filter reaches the map. A pie is one place, not one spelling: the registers write Zichron Yaakov eighteen ways and Hadar Hacarmel sixteen, and every spelling that resolves to the same gazetteer entry is gathered into a single pie. It is named by the registers' own commonest spelling of it, and in the lists beside and below the map the Mandate-era English name follows in brackets where it is a different word — Khalsa (Khalisa), Kufr Ata (Kfar Ata). The gazetteer's own name, given beside its link, is often the place's later one: Kima files al-Khalisa under Kiryat Shmona and Sa'sa' under the kibbutz Sasa, settlements built on their land after 1948. The point is the settlement's own location, not the patient's address, which the registers record too coarsely to place. Haifa dominates by design: it is the hospital's own town.</p>
  },
  {
    heading: 'Solid pies and dashed ones',
    body: <p>A <strong>solid</strong> pie is a place somebody ruled on — matched to the Kima gazetteer by the historian or by the assistant, and signed. A <strong>faded pie with a dashed rim</strong> is the matching engine's own suggestion, checked only for landing inside the region; nobody has confirmed it. Both draw real records, but a dashed pie's <em>location</em> is a lead rather than a finding, and it can be wrong in ways a ruling cannot. The engine matched "Hebron" to Hebron, Connecticut, perfectly and confidently — that is the failure mode a dashed rim is warning you about.</p>
  },
  {
    heading: 'The two basemaps',
    body: <p><strong>Survey of Palestine 1:20,000</strong> is the Mandate-era sheet, the ground as the register clerks would have known it — villages that no longer exist are on it under the names they were then called. <strong>Modern</strong> is OpenStreetMap, for orientation. Toggling between them is the point: a place the register names may sit under a later town, or under nothing at all. Where the survey has no sheet, the map simply ends.</p>
  },
  {
    heading: 'What is not on the map, and why it matters',
    body: <p>The gazetteer review began with the cities of Jewish patients. Because the join is blind to religion, those rulings carried every community's records for the places the communities shared — Acre, Nazareth, Jenin. The places they did not share got nothing, so the Galilee and Carmel villages no Jewish patient came from stayed off the map. That absence was systematic, and it fell on Muslim and Christian records. A second round is closing it; the dashed pies are its first result. Most of the villages now drawn solid were identified by Yoni Furas (University of Haifa), collaborator, whose annotation of the patient addresses also moved Herzliya to the Haifa quarter of that name and al-Tira back to the village. What remains unplaced is counted below the map — values still unreviewed, values judged ambiguous or illegible, and records carrying no city at all. Absence here is a state of the review, never a claim about the patient.</p>
  }
];

const MAP_BOUNDS = L.latLngBounds([28.9, 33.2], [34.4, 37.0]);

interface Place {
  // Stable identity: the Kima id, else the point.
  key: string;
  // The name the place goes by here: the registers' own commonest spelling of
  // it. Not the gazetteer's, which is often the place's later name — Kima
  // calls al-Khalisa Kiryat Shmona and al-Bassa Shelomi, towns built on their
  // land after 1948, and a map of 1930–48 must not say so.
  label: string;
  // The Mandate-era English name (kimatch/place-labels.tsv), added in brackets
  // wherever a place is named in a list rather than on the map. Empty where
  // none is recorded.
  mandateLabel: string;
  // Every City spelling that resolved to this point. The registers spell
  // Zichron Yaakov eighteen ways; they are one place and must be one circle,
  // or the map shows eighteen stacked dots and each click hides seventeen
  // nineteenths of the records.
  cities: string[];
  lat: number;
  lon: number;
  source: string;
  // 'confirmed' — a ruling in the decisions table; 'provisional' — an audited
  // engine candidate nobody has ruled on. Drawn differently, because a
  // provisional point is a lead and can be wrong in ways a ruling cannot.
  standing: string;
  kimaId: string;
  kimaName: string;
  qid: string;
}

interface Unplaced { decision: string; records: number; }

// The review's decisions, in words, for the note under the map.
const UNPLACED_LABEL: Record<string, string> = {
  unreviewed: 'not yet identified',
  'unmatched-ambiguous': 'held as ambiguous',
  'unmatched-no-kima-entry': 'identified but not in the gazetteer',
  'unmatched-junk': 'judged transcription debris',
  matched: 'identified, no coordinates'
};

type Mix = Record<string, number>;

/** A pie as an SVG string, for a Leaflet divIcon. The slices go round in the
 *  scheme's fixed order, so two pies can be read against each other at a glance. */
const pieSvg = (scheme: PieScheme, mix: Mix, r: number, provisional: boolean, selected: boolean): string => {
  const stroke = selected ? 2.5 : provisional ? 1.75 : 1.25;
  const size = Math.ceil(2 * (r + stroke));
  const c = size / 2;
  const total = scheme.keys.reduce((s, k) => s + (mix[k] || 0), 0) || 1;
  // A provisional place is faded and dashed — visibly not the same kind of claim
  // as a ruled one — but keeps its slices, since its records are real.
  const opacity = provisional && !selected ? 0.5 : 0.88;
  let a0 = -Math.PI / 2;
  const parts: string[] = [];
  scheme.keys.forEach(k => {
    const n = mix[k] || 0;
    if (!n) return;
    const fill = scheme.color(k);
    if (n === total) {
      parts.push(`<circle cx="${c}" cy="${c}" r="${r}" fill="${fill}"/>`);
      return;
    }
    const a1 = a0 + (2 * Math.PI * n) / total;
    const large = a1 - a0 > Math.PI ? 1 : 0;
    const x0 = c + r * Math.cos(a0), y0 = c + r * Math.sin(a0);
    const x1 = c + r * Math.cos(a1), y1 = c + r * Math.sin(a1);
    parts.push(`<path d="M${c},${c}L${x0.toFixed(2)},${y0.toFixed(2)}A${r},${r} 0 ${large} 1 ${x1.toFixed(2)},${y1.toFixed(2)}Z" fill="${fill}"/>`);
    a0 = a1;
  });
  const rim = selected ? '#1f2937' : provisional ? '#334155' : '#ffffff';
  const dash = provisional && !selected ? ' stroke-dasharray="3 2"' : '';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" style="display:block;overflow:visible">`
    + `<g fill-opacity="${opacity}">${parts.join('')}</g>`
    + `<circle cx="${c}" cy="${c}" r="${r}" fill="none" stroke="${rim}" stroke-width="${stroke}"${dash}/></svg>`;
};

const pieIcon = (scheme: PieScheme, mix: Mix, r: number, provisional: boolean, selected: boolean): L.DivIcon => {
  const stroke = selected ? 2.5 : provisional ? 1.75 : 1.25;
  const size = Math.ceil(2 * (r + stroke));
  return L.divIcon({
    html: pieSvg(scheme, mix, r, provisional, selected),
    className: 'map-pie',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2]
  });
};

const val = (row: RegistryRecord, key: string): string => {
  const raw = row[key];
  if (raw === null || raw === undefined) return '';
  const s = String(raw).trim();
  return s === 'null' || s === 'undefined' ? '' : s;
};

// Letters only, so "Bassa, El" and "Bassah" or "Sa'sa'" and "Sasa" are not
// told apart for want of a comma or an apostrophe.
const bare = (name: string): string => name.toLowerCase().replace(/[^a-z]/g, '');

/** A place as a list names it: the registers' spelling, and the Mandate-era
 *  English name in brackets where that is a different word. One name that
 *  only extends the other ("Bassa" and "Bassa, El", "Majdal, Tiberias S/D"
 *  and "Majdal") is not a different word. */
const listName = (p: { label: string; mandateLabel: string }): string => {
  const a = bare(p.label), b = bare(p.mandateLabel);
  return b && !a.startsWith(b) && !b.startsWith(a) ? `${p.label} (${p.mandateLabel})` : p.label;
};

const FIELDS = ['Admission Date', 'Age', 'Sex', 'Religion', 'Nationality',
                'Occupation', 'Address', 'City as written', 'Ward', 'Diagnosis', 'Result'];

const PAGE_SIZE = 25;

// The exact size of the survey's "nothing here" tile. Anything at or under it
// carries no map; the smallest real tile measured is six times larger.
const BLANK_TILE_BYTES = 700;

// Mandate-era sheet first: this is a historical map, and the modern basemap is
// the aid to orientation rather than the subject.
const BASEMAPS = [
  {
    key: 'historic',
    label: 'Survey of Palestine, 1:20,000',
    url: 'https://palopenmaps.org/tiles/pal20k-1940s/{z}/{x}/{y}.jpg',
    // crossOrigin so the blank-tile probe below can actually read the pixels:
    // without it the canvas taints and getImageData throws. The host sends
    // access-control-allow-origin: *.
    options: { maxNativeZoom: 16, maxZoom: 18, crossOrigin: 'anonymous' as const,
               attribution: 'Survey of Palestine 1:20,000 via Palestine Open Maps' }
  },
  {
    key: 'modern',
    label: 'Modern (OpenStreetMap)',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    options: { maxZoom: 18, attribution: '&copy; OpenStreetMap contributors' }
  }
] as const;

type BasemapKey = typeof BASEMAPS[number]['key'];

interface Props {
  /** The records inside the admission-date range, and only that range. */
  data: RegistryRecord[];
  /** Every record, so the diagnosis pies rank and colour their chapters on the
   *  whole registry rather than on whatever the range leaves. */
  fullData: RegistryRecord[];
  /** The shared Admission Date range, in ms; absent if the data has no dates. */
  dateRange?: RangeFilter;
  onDateRange?: (min: number, max: number) => void;
}

const isoOfMs = (ms: number): string => new Date(ms).toISOString().slice(0, 10);

/** A typed date to ms: 1938, 1938-07 or 1938-07-06. `end` fills in upward, so
 *  a bare 1938 as the "to" means the last day of 1938. Null if unreadable. */
const parseDay = (text: string, end: boolean): number | null => {
  const m = text.trim().match(/^(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?$/);
  if (!m) return null;
  const y = Number(m[1]);
  const mo = m[2] ? Number(m[2]) : (end ? 12 : 1);
  if (mo < 1 || mo > 12) return null;
  const last = new Date(Date.UTC(y, mo, 0)).getUTCDate();
  const d = m[3] ? Number(m[3]) : (end ? last : 1);
  if (d < 1 || d > last) return null;
  return Date.UTC(y, mo - 1, d);
};

/**
 * The admission dates the map is drawn for. Edits the same range the Browser's
 * slider does; the fields are text so a half-typed date can stay on screen.
 */
const DateBox: React.FC<{ range: RangeFilter; onChange: (min: number, max: number) => void }> = ({ range, onChange }) => {
  const [from, setFrom] = useState(isoOfMs(range.currentMin));
  const [to, setTo] = useState(isoOfMs(range.currentMax));
  // Follow changes made elsewhere — the Timeline, the Browser's slider.
  useEffect(() => { setFrom(isoOfMs(range.currentMin)); }, [range.currentMin]);
  useEffect(() => { setTo(isoOfMs(range.currentMax)); }, [range.currentMax]);
  const narrowed = range.currentMin > range.min || range.currentMax < range.max;
  const a = parseDay(from, false), b = parseDay(to, true);
  const field = (bad: boolean) => `w-[7.5em] px-2 py-1 rounded-lg border bg-white font-mono text-[11px] ${
    bad ? 'border-rose-300 text-rose-700' : 'border-slate-300 text-slate-700'}`;
  return (
    <form
      className="flex flex-wrap items-center gap-1.5"
      onSubmit={e => {
        e.preventDefault();
        if (a === null || b === null || a > b) return;
        onChange(Math.max(range.min, a), Math.min(range.max, b));
      }}
    >
      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mr-1">Admitted</span>
      <input value={from} onChange={e => setFrom(e.target.value)} aria-label="Admitted from"
        placeholder="1938" className={field(a === null)} />
      <span className="text-slate-400 text-xs">–</span>
      <input value={to} onChange={e => setTo(e.target.value)} aria-label="Admitted to"
        placeholder="1938-07-31" className={field(b === null)} />
      <button type="submit"
        className="px-2.5 py-1 rounded-lg border border-slate-300 bg-white text-slate-700 text-[11px] font-bold">
        Go
      </button>
      {narrowed && (
        <button type="button" onClick={() => onChange(range.min, range.max)}
          className="px-2.5 py-1 rounded-lg border border-indigo-300 bg-indigo-50 text-indigo-700 text-[11px] font-bold">
          All years
        </button>
      )}
    </form>
  );
};

const MapView: React.FC<Props> = ({ data, fullData, dateRange, onDateRange }) => {
  const [places, setPlaces] = useState<Place[] | null>(null);
  const [pieMode, setPieMode] = usePieMode();
  const scheme = useMemo(
    () => (pieMode === 'chapter' ? chapterScheme(fullData) : communityScheme),
    [pieMode, fullData]);
  // City value -> the review's decision, for values with no point to draw.
  const [decisionOf, setDecisionOf] = useState<Map<string, string>>(new Map());
  const [selected, setSelected] = useState<string | null>(null);
  const [basemap, setBasemap] = useState<BasemapKey>('historic');
  const [page, setPage] = useState(1);
  // The info box can be folded to its headline, so it stops covering the
  // southern coast; the reader's choice is remembered between visits.
  const [infoOpen, setInfoOpen] = useState<boolean>(() => {
    try { return localStorage.getItem('map.infoOpen') !== '0'; } catch { return true; }
  });
  const toggleInfo = () => setInfoOpen(v => {
    try { localStorage.setItem('map.infoOpen', v ? '0' : '1'); } catch { /* private window */ }
    return !v;
  });
  // Bumped whenever a map instance is created, so the tile and marker effects
  // re-run against the new one rather than the removed one.
  const [mapReady, setMapReady] = useState(0);
  const scans = usePageScans();

  const mapRef = useRef<L.Map | null>(null);
  const tileRef = useRef<L.TileLayer | null>(null);
  const markersRef = useRef<Map<string, L.Marker>>(new Map());
  // The opening view is fitted to the dots, once. After that the view is the
  // reader's to keep — a filter change should not yank the map out from under
  // a pan they made on purpose; the ⊹ button is there for when they want it.
  const fittedRef = useRef(false);
  const resizeRef = useRef<ResizeObserver | null>(null);
  // attachMap is created once and must not close over the render's data, so
  // what it needs to know about the points is read through refs.
  const hasPointsRef = useRef(false);

  // ------------------------------------------------------------ the data

  useEffect(() => {
    fetch(COORDS_URL)
      .then(r => (r.ok ? r.text() : Promise.reject(new Error(`${r.status}`))))
      .then(text => {
        const lines = text.split(/\r?\n/).filter(l => l.trim());
        const header = lines[0].split('\t');
        const at = (cells: string[], name: string) => cells[header.indexOf(name)] || '';
        // Keyed on the Kima id where present, else the rounded point, so two
        // spellings the review sent to the same entry become one circle.
        const grouped = new Map<string, Place>();
        const missed = new Map<string, string>();
        lines.slice(1).forEach(line => {
          const c = line.split('\t');
          const lat = parseFloat(at(c, 'lat'));
          const lon = parseFloat(at(c, 'lon'));
          if (Number.isFinite(lat) && Number.isFinite(lon)) {
            const kimaId = at(c, 'kima_id');
            const key = kimaId || `${lat.toFixed(5)},${lon.toFixed(5)}`;
            const existing = grouped.get(key);
            if (existing) {
              if (!existing.cities.includes(at(c, 'city'))) existing.cities.push(at(c, 'city'));
              existing.mandateLabel ||= at(c, 'mandate_label');
              // One confirmed spelling settles the whole point.
              if (at(c, 'standing') === 'confirmed') existing.standing = 'confirmed';
            } else {
              const kimaName = at(c, 'kima_name_rom');
              grouped.set(key, {
                key,
                // Provisional: replaced by the commonest spelling once the
                // records are counted.
                label: at(c, 'city'),
                mandateLabel: at(c, 'mandate_label'),
                cities: [at(c, 'city')],
                lat, lon,
                source: at(c, 'source'),
                standing: at(c, 'standing') || 'confirmed',
                kimaId,
                kimaName,
                qid: at(c, 'wikidata_qid')
              });
            }
          } else {
            missed.set(at(c, 'city'), at(c, 'decision') || 'unreviewed');
          }
        });
        setPlaces(Array.from(grouped.values()));
        setDecisionOf(missed);
      })
      .catch(() => { setPlaces([]); setDecisionOf(new Map()); });
  }, []);

  // Records grouped by the City string, so a click on a circle can hand back
  // exactly the rows that produced it.
  const byCity = useMemo(() => {
    const out = new Map<string, RegistryRecord[]>();
    data.forEach(row => {
      const city = val(row, 'City');
      if (!city) return;
      const bucket = out.get(city);
      if (bucket) bucket.push(row); else out.set(city, [row]);
    });
    return out;
  }, [data]);

  // How often each City spelling occurs across the whole registry, so a place
  // keeps the same name whatever the date range leaves of it.
  const spellingCount = useMemo(() => {
    const out = new Map<string, number>();
    fullData.forEach(row => {
      const city = val(row, 'City');
      if (city) out.set(city, (out.get(city) || 0) + 1);
    });
    return out;
  }, [fullData]);

  // Places past the map's edge — Cairo, London, El Qantara — are real
  // origins but cannot be drawn: Leaflet will not settle on a view that shows
  // anything past maxBounds, so one of them would hold the fit back for all
  // the rest. They are named under the map instead.
  const withCounts = useMemo(() => {
    if (!places) return [];
    return places
      .map(p => {
        const mix: Mix = {};
        let n = 0;
        p.cities.forEach(c => (byCity.get(c) || []).forEach(row => {
          const g = scheme.bucket(row);
          mix[g] = (mix[g] || 0) + 1;
          n++;
        }));
        // A spelling with an alternation in it ("Tulkarm|Tul-Karm") is the
        // transcriber's doubt, not the clerk's word: a plain one is preferred.
        const label = [...p.cities].sort((a, b) =>
          Number(a.includes('|')) - Number(b.includes('|'))
          || (spellingCount.get(b) || 0) - (spellingCount.get(a) || 0))[0] || p.label;
        return { ...p, label, n, mix };
      })
      .filter(p => p.n > 0)
      .sort((a, b) => b.n - a.n);
  }, [places, byCity, scheme, spellingCount]);
  const counted = useMemo(() => withCounts.filter(p => MAP_BOUNDS.contains([p.lat, p.lon])), [withCounts]);
  const abroad = useMemo(() => withCounts.filter(p => !MAP_BOUNDS.contains([p.lat, p.lon])), [withCounts]);

  const maxN = counted.length ? counted[0].n : 1;
  const radiusOf = useCallback((n: number) => 5 + 22 * Math.sqrt(n / maxN), [maxN]);

  // Records not on the map at all: no City on the record, or a City value the
  // review never reached. Counted from the data itself rather than from the
  // decisions file, so the two cannot drift.
  // Why each unplaced record is unplaced is counted from the records too — the
  // decisions file's own counts are round 1's, Jewish patients only.
  const offMap = useMemo(() => {
    if (!places) return { noCity: 0, unmatched: 0, why: [] as Unplaced[] };
    const placed = new Set(places.flatMap(p => p.cities));
    let noCity = 0, unmatched = 0;
    const why = new Map<string, number>();
    data.forEach(row => {
      const city = val(row, 'City');
      if (!city) { noCity++; return; }
      if (placed.has(city)) return;
      unmatched++;
      const d = decisionOf.get(city) || 'unreviewed';
      why.set(d, (why.get(d) || 0) + 1);
    });
    return {
      noCity, unmatched,
      why: Array.from(why.entries()).map(([decision, records]) => ({ decision, records })).sort((a, b) => b.records - a.records)
    };
  }, [data, places, decisionOf]);

  // ------------------------------------------------------------ the map

  // A callback ref, not an effect over a plain one: the view renders a loading
  // screen until the coordinates arrive, so the map element does not exist on
  // first mount and an effect keyed on [] would never get a second chance at
  // it. This runs exactly when the node appears and again if it is replaced,
  // which is also what makes it correct under StrictMode's double mount.
  const attachMap = useCallback((node: HTMLDivElement | null) => {
    if (!node) {
      resizeRef.current?.disconnect();
      resizeRef.current = null;
      mapRef.current?.remove();
      mapRef.current = null;
      fittedRef.current = false;
      tileRef.current = null;
      markersRef.current = new Map();
      return;
    }
    if (mapRef.current) return;
    mapRef.current = L.map(node, {
      center: [32.72, 35.1], zoom: 9, zoomControl: true, scrollWheelZoom: true,
      // The historical sheet covers Mandate Palestine and nothing else. Without
      // a bound, panning drifts off it into bare background that reads as a
      // failed render rather than as the edge of the survey.
      // Wide enough to hold the whole catchment with air around it. Beirut,
      // the register's northernmost place, used to sit just outside this box:
      // it could never be panned to, and worse, Leaflet will not settle on a
      // view that would show anything beyond the bound, so the opening fit was
      // clamped a whole zoom level below what it computed. Gaza is the
      // southernmost place and has always been comfortably inside.
      maxBounds: MAP_BOUNDS,
      maxBoundsViscosity: 0.85,
      minZoom: 8,
      // Leaflet snaps to whole zoom levels unless told otherwise, and the fit
      // to all 157 points falls just past level 8: it therefore rounds down and
      // draws the catchment at half the scale the panel could hold, ringed by
      // empty margin. A zoom snap of 0 lets the fit land where it actually
      // computes, filling the frame; the 0.25 delta keeps the +/- buttons
      // stepping in sensible amounts rather than by fractions.
      zoomSnap: 0,
      zoomDelta: 0.25
    });
    // Tied to the instance, not to the component: under StrictMode the first
    // map is created and torn down before the real one, and a flag that
    // survived that would spend the only opening fit on the discarded map.
    fittedRef.current = false;

    // The map is created inside a flex row before that row has been laid out,
    // so Leaflet caches a container width of ~126px against an element that
    // ends up 800px wide, and anything fitted to that cached size lands in a
    // thin strip down the left edge. The real width arrives some frames later
    // and not on any schedule worth guessing at, so watch the element and tell
    // Leaflet to re-measure whenever it actually changes — which also keeps the
    // map honest when the window or the side panels are resized later.
    const ro = new ResizeObserver(() => {
      mapRef.current?.invalidateSize();
      // Try the opening fit on every resize until one actually lands. The two
      // things it needs — the container's real width and the loaded points —
      // arrive in either order, so whichever is last triggers the fit that
      // counts; fitToPoints itself refuses to mark the job done until both are
      // there. Without the retry, a fit attempted at the placeholder width
      // would claim the one chance and leave the map at half scale.
      fitRef.current(true);
    });
    ro.observe(node);
    resizeRef.current = ro;

    setMapReady(n => n + 1);
  }, []);

  // The basemap is a toggle, not a blend: one layer at a time, swapped in
  // place, so what you are reading the points against is never in doubt.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const spec = BASEMAPS.find(b => b.key === basemap)!;
    const layer = L.tileLayer(spec.url, spec.options as L.TileLayerOptions);

    // Outside the surveyed area Palestine Open Maps answers with a solid black
    // 256px JPEG rather than a 404, so Leaflet lays it down like any other tile
    // and the map ends in a black field. The black is the image, so no CSS rule
    // reaches it.
    //
    // Those blanks are byte-identical and tiny — 668 bytes, against 4KB-76KB for
    // a tile with any survey on it — so the tile is fetched once and hidden on
    // size alone. Reading the pixels instead would mean a canvas, which taints
    // on any image already cached without CORS and then silently gives up; this
    // check has no such failure mode. The fetch is served from the browser cache
    // the tile itself populated.
    if (spec.key === 'historic') {
      layer.on('tileload', (e: L.TileEvent) => {
        const img = e.tile as HTMLImageElement;
        fetch(img.src)
          .then(r => (r.ok ? r.blob() : null))
          .then(blob => {
            if (blob && blob.size <= BLANK_TILE_BYTES) img.style.visibility = 'hidden';
          })
          .catch(() => { /* offline or blocked: leave the tile alone */ });
      });
    }

    layer.addTo(map);
    const previous = tileRef.current;
    tileRef.current = layer;
    // Removing the old layer only once the new one has drawn avoids a white
    // flash between the two sheets.
    if (previous) layer.once('load', () => map.removeLayer(previous));
  }, [basemap, mapReady]);

  // Frame every circle currently drawn, with just enough margin that the
  // outermost ones are not clipped by their own radius.
  const fitToPoints = useCallback((opening = false) => {
    const map = mapRef.current;
    if (!map || !counted.length) return;
    // Leaflet caches the container size at creation, inside a flex row that has
    // not been laid out, so it starts out ~126px wide against an element that
    // ends up 800px. Re-measure before deciding whether this is a real frame.
    map.invalidateSize();
    // An opening fit against the placeholder width would draw the catchment at
    // half scale and, worse, count as the one opening fit. Leave it for the
    // resize that brings the real width.
    if (opening) {
      if (map.getSize().x < 200) return;
      fittedRef.current = true;
    }
    const bounds = L.latLngBounds(counted.map(p => [p.lat, p.lon] as [number, number]));
    // Padding is deliberately tight. The points run Gaza to Beirut, a long
    // thin north-south spread, so in a panel taller than it is wide the height
    // is what limits the fit and every pixel of padding is thrown away as
    // margin on all four sides. maxZoom only guards fitting a single place.
    // fitBounds is left to compute the level but not to apply it: with
    // zoomSnap 0 the value it wants is fractional, and setting centre and zoom
    // directly is what makes that fraction stick. Going through fitBounds
    // alone settled a whole level lower and drew the catchment at half scale.
    const zoom = Math.min(13, map.getBoundsZoom(bounds, false, L.point(8, 8)));
    map.setView(bounds.getCenter(), zoom, { animate: false });
  }, [counted]);

  // The control is built once per map instance, so it cannot close over the
  // fitToPoints of the render that made it — that one would frame whatever the
  // filters said at mount. It calls through this ref, which always holds the
  // current one.
  const fitRef = useRef(fitToPoints);
  fitRef.current = fitToPoints;
  hasPointsRef.current = counted.length > 0;

  // A third button under the zoom pair, in Leaflet's own control stack so it
  // inherits the placement and the frame rather than floating over the map.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const Fit = L.Control.extend({
      options: { position: 'topleft' as L.ControlPosition },
      onAdd() {
        const bar = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
        const link = L.DomUtil.create('a', '', bar);
        link.href = '#';
        link.title = 'Fit the view to every place shown';
        link.setAttribute('role', 'button');
        link.setAttribute('aria-label', 'Fit the view to every place shown');
        link.innerHTML = '&#9974;';
        link.style.fontSize = '15px';
        L.DomEvent.on(link, 'click', L.DomEvent.stop).on(link, 'click', () => fitRef.current());
        return bar;
      }
    });
    const control = new Fit();
    control.addTo(map);
    return () => { control.remove(); };
  }, [mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !counted.length) return;
    markersRef.current.forEach(m => m.remove());
    markersRef.current = new Map();

    counted.forEach((p, i) => {
      // Area, not radius, tracks the count — a radius scale would read Haifa as
      // hundreds of times the size of Acre rather than the ~9x it is.
      const radius = radiusOf(p.n);
      const provisional = p.standing === 'provisional';
      const marker = L.marker([p.lat, p.lon], {
        icon: pieIcon(scheme, p.mix, radius, provisional, false),
        // Leaflet stacks markers by latitude; a pie has to stack by size
        // instead, smaller over larger, or Haifa buries its own suburbs.
        // counted runs largest first, so a later index sits higher.
        zIndexOffset: i * 10000,
        riseOnHover: true,
        keyboard: false
      });
      const breakdown = scheme.keys
        .filter(k => p.mix[k])
        .map(k => `<span style="display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:4px;background:${scheme.color(k)}"></span>`
          + `${scheme.label(k)} ${p.mix[k].toLocaleString()} (${Math.round(100 * p.mix[k] / p.n)}%)`)
        .join('<br>');
      marker.bindTooltip(
        `<strong>${p.label}</strong><br>${p.n.toLocaleString()} record${p.n === 1 ? '' : 's'}`
        + (provisional ? '<br><em>candidate, not yet reviewed</em>' : '')
        + `<div style="margin-top:4px;font-size:11px;line-height:1.5">${breakdown}</div>`,
        { direction: 'top', offset: [0, -radius] }
      );
      marker.on('click', () => { setSelected(p.key); setPage(1); });
      marker.addTo(map);
      markersRef.current.set(p.key, marker);
    });

    // The points may arrive after the container has settled, in which case no
    // further resize is coming and this is the only chance to frame them.
    if (!fittedRef.current) fitToPoints(true);

    return () => { markersRef.current.forEach(m => m.remove()); };
  }, [counted, radiusOf, mapReady, fitToPoints, scheme]);

  // The selected pie is redrawn with a dark rim and lifted to the top; the
  // marker itself is kept, so the map does not flicker on every selection.
  useEffect(() => {
    counted.forEach((p, i) => {
      const key = p.key;
      const marker = markersRef.current.get(key);
      if (!marker) return;
      const on = key === selected;
      marker.setIcon(pieIcon(scheme, p.mix, radiusOf(p.n), p.standing === 'provisional', on));
      marker.setZIndexOffset(on ? 10000000 : i * 10000);
    });
  }, [selected, counted, radiusOf, scheme]);

  // ------------------------------------------------------- the selection

  const selectedPlace = counted.find(p => p.key === selected) || null;
  // Every record from every spelling of the selected place, in the registers'
  // own order rather than grouped by spelling.
  const records = useMemo(
    () => (selectedPlace
      ? selectedPlace.cities.flatMap(c => byCity.get(c) || [])
      : []),
    [selectedPlace, byCity]
  );

  // Admissions per year for the selected place. Every year in the register's
  // span is present, zeros included: a place that supplied patients in 1934 and
  // again in 1946 must not read as a continuous stream.
  const yearly = useMemo(() => {
    if (!records.length) return { rows: [] as { year: string; n: number }[], undated: 0 };
    const counts = new Map<number, number>();
    let undated = 0;
    records.forEach(r => {
      const raw = val(r, 'Admission Date');
      const year = parseInt(raw.slice(0, 4), 10);
      if (!Number.isFinite(year) || year < 1900 || year > 2000) { undated++; return; }
      counts.set(year, (counts.get(year) || 0) + 1);
    });
    if (!counts.size) return { rows: [], undated };
    const years = Array.from(counts.keys());
    const rows: { year: string; n: number }[] = [];
    for (let y = Math.min(...years); y <= Math.max(...years); y++) {
      rows.push({ year: String(y), n: counts.get(y) || 0 });
    }
    return { rows, undated };
  }, [records]);

  const totalPages = Math.max(1, Math.ceil(records.length / PAGE_SIZE));
  const shown = records.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const exportPlace = () => {
    if (!records.length) return;
    const cols = ['Notebook_Number', 'Page_Number', 'Notebook Record ID',
                  ...FIELDS, 'City', 'City Kima ID', 'City Wikidata', 'tempLink'];
    const csv = Papa.unparse(records.map(r => {
      const out: Record<string, string> = {};
      cols.forEach(c => { out[c] = val(r, c); });
      return out;
    }));
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
    link.download = `records_${selectedPlace!.label.replace(/[^\w-]+/g, '_')}.csv`;
    link.click();
  };

  if (places === null) {
    return (
      <div className="flex-1 flex items-center justify-center p-12 bg-slate-50">
        <p className="text-sm text-slate-500 animate-pulse">Loading the placed gazetteer entries…</p>
      </div>
    );
  }

  if (!places.length) {
    return (
      <div className="flex-1 flex items-center justify-center p-12 bg-slate-50">
        <div className="max-w-md text-center space-y-2">
          <MapPin size={28} className="mx-auto text-slate-300" />
          <h2 className="font-bold text-slate-700">No coordinates yet</h2>
          <p className="text-sm text-slate-500">
            The map draws <code className="text-xs">data/public/place-coords.tsv</code>.
            Build it with <code className="text-xs">python3 pipeline/place_coords.py</code>,
            then rerun the site.
          </p>
        </div>
      </div>
    );
  }

  const mappedRecords = counted.reduce((s, p) => s + p.n, 0);
  const provisionalCount = counted.filter(p => p.standing === 'provisional').length;

  return (
    <div className="flex w-full h-full overflow-hidden bg-slate-50">
      {/* The map itself */}
      <div className="flex-1 min-w-0 relative">
        {/* An inline height, not a utility class. Leaflet ships its own rule
            for .leaflet-container, and once it attaches, that class can win
            the cascade over Tailwind's `absolute` — leaving `inset-0` with
            nothing to resolve against and the map zero pixels tall. Bundlers
            order the two stylesheets differently in dev and in the built site,
            so this is a bug that only appears once deployed. An inline style
            does not participate in that race. */}
        <div
          ref={attachMap}
          style={{
            position: 'absolute', inset: 0, height: '100%', width: '100%',
            // Where the survey has no sheet. A muted ground, not black: the
            // edge of the 1:20,000 is a fact about the map's coverage, and it
            // should look like paper running out rather than a broken tile.
            background: '#e8e4da'
          }}
        />

        {/* The admission dates the pies are cut for */}
        {dateRange && onDateRange && (
          <div className="absolute top-4 left-14 max-w-[calc(100%-20rem)] z-[500] bg-white/95 backdrop-blur rounded-2xl border border-slate-200 shadow-lg px-3 py-2">
            <DateBox range={dateRange} onChange={onDateRange} />
          </div>
        )}

        {/* Basemap toggle */}
        <div className="absolute top-4 right-4 z-[500] bg-white/95 backdrop-blur rounded-2xl border border-slate-200 shadow-lg p-2">
          <div className="flex items-center gap-1.5 px-2 pb-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <Layers size={12} /> Basemap
          </div>
          <div className="flex flex-col gap-1">
            {BASEMAPS.map(b => (
              <button
                key={b.key}
                onClick={() => setBasemap(b.key)}
                className={`text-left px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                  basemap === b.key
                    ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                    : 'text-slate-600 border border-transparent hover:bg-slate-50'
                }`}
              >
                {b.label}
              </button>
            ))}
          </div>
          <PieModeSwitch mode={pieMode} onChange={setPieMode} />
        </div>

        {/* What the map does and does not carry */}
        <div className="absolute bottom-6 left-4 z-[500] bg-white/95 backdrop-blur rounded-2xl border border-slate-200 shadow-lg px-4 py-3 max-w-xs">
          <button
            onClick={toggleInfo}
            aria-expanded={infoOpen}
            title={infoOpen ? 'Minimize' : 'Show the legend and what is not on the map'}
            className="w-full flex items-center justify-between gap-3 text-left"
          >
            <span className="text-xs font-bold text-slate-700">
              {counted.length} places · {mappedRecords.toLocaleString()} records
            </span>
            {infoOpen
              ? <ChevronDown size={14} className="text-slate-400 shrink-0" />
              : <ChevronUp size={14} className="text-slate-400 shrink-0" />}
          </button>
          {infoOpen && <>
          {provisionalCount > 0 && (
            <p className="text-[11px] text-amber-700 mt-0.5">
              {provisionalCount} of them unreviewed candidates, drawn faded with a dashed rim
            </p>
          )}
          <PieLegend scheme={scheme} />
          <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
            Not on the map: {offMap.noCity.toLocaleString()} records with no City recorded,
            and {offMap.unmatched.toLocaleString()} whose City has no point
            {offMap.why.length > 0 && (
              <> — {offMap.why.map(u => `${UNPLACED_LABEL[u.decision] || u.decision} ${u.records.toLocaleString()}`).join(', ')}</>
            )}. The open questions are under Review → Place questions.
          </p>
          {abroad.length > 0 && (
            <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
              Beyond the map's edge: {abroad.map(p => `${listName(p)} ${p.n.toLocaleString()}`).join(', ')}.
            </p>
          )}
          </>}
        </div>
      </div>

      {/* The selected place */}
      {selectedPlace && (
        <div className="w-[30rem] shrink-0 bg-white border-l border-slate-200 overflow-y-auto custom-scrollbar">
          <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 z-10">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-black text-slate-800">{listName(selectedPlace)}</h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  {records.length.toLocaleString()} record{records.length === 1 ? '' : 's'}
                  {selectedPlace.cities.length > 1
                    && <> · {selectedPlace.cities.length} spellings</>}
                </p>
                {selectedPlace.cities.length > 1 && (
                  <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                    Written here as {selectedPlace.cities.join(', ')}.
                  </p>
                )}
                <p className="text-[11px] text-slate-400 mt-1 flex flex-wrap gap-x-3">
                  {selectedPlace.kimaId && (
                    <a href={`https://data.geo-kima.org/Places/Details/${selectedPlace.kimaId}`}
                       target="_blank" rel="noreferrer" className="text-indigo-600 underline">
                      Kima #{selectedPlace.kimaId}
                    </a>
                  )}
                  {selectedPlace.kimaName && (
                    <span title="The gazetteer's name for the place, often its later one">
                      gazetteer: {selectedPlace.kimaName.replace(/\s*\([^)]*\)\s*$/, '')}
                    </span>
                  )}
                  {selectedPlace.qid && (
                    <a href={`https://www.wikidata.org/wiki/${selectedPlace.qid}`}
                       target="_blank" rel="noreferrer" className="text-indigo-600 underline">
                      {selectedPlace.qid}
                    </a>
                  )}
                  <span>point from {selectedPlace.source}</span>
                  {selectedPlace.standing === 'provisional' && (
                    <span className="font-bold text-amber-600">
                      candidate — not yet reviewed
                    </span>
                  )}
                </p>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 shrink-0"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Admissions over time */}
          {selectedPlace.standing === 'provisional' && (
            <div className="mx-6 mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
              <p className="text-[11px] text-amber-800 leading-relaxed">
                This place is the matching engine's own suggestion, checked only for
                falling inside the region. Nobody has ruled on it. The records below
                are certainly what the register says; the point on the map is a lead.
              </p>
            </div>
          )}
          <div className="px-6 py-5 border-b border-slate-200">
            <h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Admissions by year
            </h3>
            {yearly.rows.length === 0 ? (
              <p className="text-xs text-slate-400 italic mt-3">
                No record from this place carries a usable admission date.
              </p>
            ) : (
              <>
                <div className="h-44 mt-3 -ml-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={yearly.rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                      <XAxis dataKey="year" tick={{ fontSize: 10, fill: '#64748b' }}
                             interval="preserveStartEnd" tickLine={false} axisLine={{ stroke: '#e2e8f0' }} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: '#64748b' }}
                             tickLine={false} axisLine={false} width={34} />
                      <Tooltip
                        cursor={{ fill: '#f1f5f9' }}
                        contentStyle={{ fontSize: 12, borderRadius: 10, border: '1px solid #e2e8f0' }}
                        formatter={(v: number) => [v.toLocaleString(), 'admissions']}
                      />
                      <Bar dataKey="n" fill={SERIES[0]} radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
                  Zero years are real gaps in this place's contribution, but the registers
                  themselves have archival gaps — see the Timeline view before reading a
                  trough as a fall in admissions.
                  {yearly.undated > 0 && <> {yearly.undated.toLocaleString()} record
                    {yearly.undated === 1 ? '' : 's'} here carry no usable date.</>}
                </p>
              </>
            )}
          </div>

          {/* Every record from this place */}
          <div className="px-6 py-4">
            <div className="flex items-center justify-between gap-3 mb-3">
              <h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                All records
              </h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={exportPlace}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-600 text-[11px] font-bold hover:bg-slate-50"
                >
                  <Download size={12} /> Export
                </button>
                <div className="flex items-center bg-slate-100 rounded-lg p-0.5">
                  <button disabled={page === 1} onClick={() => setPage(p => Math.max(1, p - 1))}
                          className="p-1 rounded-md hover:bg-white disabled:opacity-30"><ChevronLeft size={14} /></button>
                  <span className="px-2 text-[11px] font-bold text-slate-600 font-mono">{page} / {totalPages}</span>
                  <button disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                          className="p-1 rounded-md hover:bg-white disabled:opacity-30"><ChevronRight size={14} /></button>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              {shown.map((row, idx) => {
                const notebook = val(row, 'Notebook_Number');
                const pageNo = val(row, 'Page_Number');
                return (
                  <div key={`${(page - 1) * PAGE_SIZE + idx}`}
                       className="rounded-xl border border-slate-200 overflow-hidden">
                    <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 bg-slate-50 border-b border-slate-200">
                      <span className="text-[11px] text-slate-500">
                        <span className="font-mono text-slate-400">#{(page - 1) * PAGE_SIZE + idx + 1}</span>
                        {' '}Notebook <span className="font-bold text-slate-700">{notebook || '—'}</span>, p. {pageNo || '—'}
                      </span>
                      <ScanLink scans={scans} notebook={notebook} page={pageNo}
                                notebookUrl={val(row, 'tempLink')} />
                    </div>
                    <dl className="px-3 py-3 grid grid-cols-2 gap-x-4 gap-y-2">
                      {FIELDS.map(field => {
                        const v = val(row, field);
                        return (
                          <div key={field}>
                            <dt className="text-[9px] font-bold uppercase tracking-wider text-slate-400">{field}</dt>
                            <dd className={`text-[11px] mt-0.5 break-words ${v ? 'text-slate-700 font-medium' : 'text-slate-300 italic'}`}>
                              {v || UNKNOWN}
                            </dd>
                          </div>
                        );
                      })}
                    </dl>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {!selectedPlace && (
        <div className="w-[22rem] shrink-0 bg-white border-l border-slate-200 overflow-y-auto custom-scrollbar">
          <div className="px-5 py-4 border-b border-slate-200">
            <h3 className="font-bold text-slate-800 flex items-center gap-2">
              <MapPin size={18} className="text-slate-600" /> Places on the map
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Click a pie, or a row here, for that place's records over time.
            </p>
          </div>
          <ul className="p-2">
            {counted.map(p => (
              <li key={p.key}>
                <button
                  onClick={() => {
                    setSelected(p.key);
                    setPage(1);
                    mapRef.current?.setView([p.lat, p.lon], Math.max(mapRef.current.getZoom(), 11));
                  }}
                  className="w-full flex items-baseline justify-between gap-3 px-3 py-2 rounded-lg hover:bg-slate-50 text-left"
                >
                  <span className="text-xs font-medium text-slate-700 truncate">{listName(p)}</span>
                  <span className="text-xs font-bold tabular-nums text-slate-400 shrink-0">
                    {p.n.toLocaleString()}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <HelpPanel title="How to use this" sections={HELP} storageKey="help.map" />
    </div>
  );
};

export default MapView;
