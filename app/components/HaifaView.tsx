import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar
} from 'recharts';
import { Building2, X, Layers, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, Download, MapPinOff } from 'lucide-react';
import { RegistryRecord } from '../types';
import { UNKNOWN } from '../facets';
import { SERIES } from '../colors';
import { PieScheme, schemeFor, usePieMode } from '../pieSchemes';
import { PieModeSwitch, PieLegend } from './PieControls';
import HelpPanel, { HelpSection } from './HelpPanel';
import ScanLink, { usePageScans } from './ScanLink';

declare const Papa: any;

/**
 * Haifa, quarter by quarter.
 *
 * The Map view places patients by town; inside the hospital's own town the
 * register says more. The address layer (pipeline/address_layers.py) reads the
 * quarter the clerk wrote — Wadi Salib, Hadar HaCarmel, Acre Gate — and the
 * institution the address names. This view draws both.
 *
 * Points come from pipeline/haifa_places.py, each a Wikidata item's own
 * coordinate, marked as the place itself or a landmark standing near it. What
 * has no point is listed beside the map rather than dropped.
 */

const PLACES_URL = `${import.meta.env.BASE_URL}data/haifa-places.json`;

const HELP: HelpSection[] = [
  {
    heading: 'What a pie is',
    body: <p>One quarter of Haifa, sized by how many admissions give it as the address, and cut by <em>Community</em> in the colours the other charts use. <strong>Click a slice</strong> for that community's records from that quarter; the panel can then be widened to the whole quarter. The <em>Pies show</em> switch at the top right recuts the pies by <em>diagnosis</em> — the ICD-9 chapter, as on the Statistics page, with the eight commonest chapters in the registry kept apart and the rest pooled as <em>Other chapters</em> — and a slice then opens that chapter's records from the quarter. Two more cuts look at one part of the registry only, and the pies shrink to it: <em>Infectious diseases only</em> keeps the admissions coded to ICD-9 chapter 001–139 and cuts them by disease, and <em>Jewish patients by nationality</em> keeps the Jewish admissions and cuts them by the nationality the clerk wrote — a citizenship, so <em>Palestinian</em> means naturalised under the Mandate. The choice is shared with the Map tab. The quarter is read from the address the clerk wrote, so a record counts here only where the address names a quarter — most Haifa records give a street or nothing at all, and the box at the bottom left says how many.</p>
  },
  {
    heading: 'Where a point comes from',
    body: <p>A point is a Wikidata item's own coordinate, or, where Wikidata has none or a wrong one for the period, an OpenStreetMap feature's (a street that kept the quarter's name; the industrial zone on the beach where the hut quarter stood). Failing both, a pin is typed in and its note says where it came from (the Kishle). The side panel links to whichever was used. Where the item is the quarter itself the pie is drawn solid. Where the quarter has no item, it is drawn at a landmark in or beside it, with a dashed rim — Acre Gate at Faisal Square, where the gate stood; the churches' quarter at Hamra Square. Two quarters drawn at the same landmark are set slightly apart. A quarter with no item and no landmark close enough is listed in the side panel, not guessed onto the map.</p>
  },
  {
    heading: 'The institutions',
    body: <p>The square badges are the institutions the addresses name — the railway, the port, the hospital itself. An institution in the address means the patient was <em>reached through</em> it, not necessarily employed by it: the hospital as address is usually its own staff. Beside each badge is a pie of its records, cut like the quarters' and on the same scale, so an institution can be read against the quarter it sits in; a click on a slice opens those records. Only an institution with one site in Haifa is placed. The police, the army, the I.P.C. and the rest are many places, or places nobody has located; they are listed under the map's legend and in the side panel, and open their records the same way. The Government Hospital is two sites: the old leased wards on Mountain Road until 31 October 1938, drawn at St Luke's Church on that road because the building itself is not known, and the seashore building at Bat Galim after it.</p>
  }
];

const MAP_BOUNDS = L.latLngBounds([32.74, 34.93], [32.86, 35.09]);

const BASEMAPS = [
  {
    key: 'historic',
    label: 'Survey of Palestine, 1:20,000',
    url: 'https://palopenmaps.org/tiles/pal20k-1940s/{z}/{x}/{y}.jpg',
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

// See MapView: the survey answers outside its sheets with a tiny black tile.
const BLANK_TILE_BYTES = 700;


const FIELDS = ['Admission Date', 'Age', 'Sex', 'Religion', 'Nationality',
                'Occupation', 'Address', 'Neighbourhood', 'Address institution', 'Ward', 'Diagnosis', 'Result'];
const PAGE_SIZE = 25;
const HAIFA_PREFIX = 'Haifa: ';

interface Point {
  name: string; qid: string; relation: string; anchor: string;
  lat: number | null; lon: number | null; note: string;
  /** The Kima gazetteer's entry, and whether it is the place or only near it. */
  kima?: string; kimaRelation?: string;
  /** The OpenStreetMap feature the point was taken from, as W123 / N123 / R123, when it is not the item's own. */
  osm?: string;
}
interface Site extends Point { from: string | null; to: string | null; icon: string; }

type Mix = Record<string, number>;

type Selection =
  // slice: the pie slice clicked, in whichever cut the pies show.
  | { kind: 'quarter'; name: string; slice: string | null }
  | { kind: 'institution'; key: string; slice: string | null };

const val = (row: RegistryRecord, key: string): string => {
  const raw = row[key];
  if (raw === null || raw === undefined) return '';
  const s = String(raw).trim();
  return s === 'null' || s === 'undefined' ? '' : s;
};

const siteKey = (s: Site) => `${s.name}|${s.from || ''}|${s.to || ''}`;

// A record belongs to a site when its institution matches and its admission
// falls inside the site's window. An undated record fails a "from" bound and
// passes a "to" one, so it lands with the site that has no point to claim.
const inWindow = (row: RegistryRecord, s: Site) => {
  const d = val(row, 'Admission Date').slice(0, 10);
  if (s.from && (!d || d < s.from)) return false;
  if (s.to && d && d > s.to) return false;
  return true;
};

/** A pie whose slices carry their key, so a click can tell which. */
const pieSvg = (scheme: PieScheme, mix: Mix, r: number, near: boolean, selected: string | null | undefined): string => {
  const total = scheme.keys.reduce((s, k) => s + (mix[k] || 0), 0) || 1;
  const stroke = selected !== undefined ? 2.5 : 1.5;
  const size = Math.ceil(2 * (r + stroke + 3));
  const c = size / 2;
  let a0 = -Math.PI / 2;
  const parts: string[] = [];
  scheme.keys.forEach(k => {
    const n = mix[k] || 0;
    if (!n) return;
    // The chosen slice pulls out a little from the centre.
    const pull = selected === k ? 3 : 0;
    const fill = scheme.color(k);
    const dim = selected && selected !== k ? ' fill-opacity="0.35"' : '';
    if (n === total) {
      parts.push(`<circle data-k="${k}" cx="${c}" cy="${c}" r="${r}" fill="${fill}"${dim} style="cursor:pointer"/>`);
      return;
    }
    const a1 = a0 + (2 * Math.PI * n) / total;
    const mid = (a0 + a1) / 2;
    const cx = c + pull * Math.cos(mid), cy = c + pull * Math.sin(mid);
    const large = a1 - a0 > Math.PI ? 1 : 0;
    const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0);
    const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
    parts.push(`<path data-k="${k}" d="M${cx.toFixed(2)},${cy.toFixed(2)}L${x0.toFixed(2)},${y0.toFixed(2)}A${r},${r} 0 ${large} 1 ${x1.toFixed(2)},${y1.toFixed(2)}Z" fill="${fill}"${dim} stroke="#fff" stroke-width="0.75" style="cursor:pointer"/>`);
    a0 = a1;
  });
  const rim = selected !== undefined ? '#1f2937' : near ? '#334155' : '#ffffff';
  const dash = near && selected === undefined ? ' stroke-dasharray="3 2"' : '';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" style="display:block;overflow:visible">`
    + `<g fill-opacity="0.9">${parts.join('')}</g>`
    + `<circle cx="${c}" cy="${c}" r="${r}" fill="none" stroke="${rim}" stroke-width="${stroke}"${dash} pointer-events="none"/></svg>`;
};

const pieIcon = (scheme: PieScheme, mix: Mix, r: number, near: boolean, selected: string | null | undefined) => {
  const size = Math.ceil(2 * (r + (selected !== undefined ? 2.5 : 1.5) + 3));
  return L.divIcon({ html: pieSvg(scheme, mix, r, near, selected), className: 'map-pie',
                     iconSize: [size, size], iconAnchor: [size / 2, size / 2] });
};

/** An institution: its badge, and beside it a pie of its records on the
 *  quarters' scale, so an institution reads against the quarter round it. The
 *  badge's glyph stays on the point; the pie hangs off to its right. */
const badgeIcon = (glyph: string, n: number, selected: boolean,
                   scheme: PieScheme, mix: Mix, r: number, slice: string | null | undefined) => {
  const badgeW = 26 + 7 * n.toLocaleString().length;
  const pieSize = Math.ceil(2 * (r + (slice !== undefined ? 2.5 : 1.5) + 3));
  const h = Math.max(22, pieSize);
  return L.divIcon({
    html: `<div style="display:flex;align-items:center;gap:2px;height:${h}px">`
      + `<div style="display:flex;align-items:center;gap:3px;padding:2px 5px 2px 4px;border-radius:6px;`
      + `background:${selected ? '#1f2937' : '#ffffff'};color:${selected ? '#fff' : '#1f2937'};`
      + `border:1.5px solid #1f2937;font:600 11px/1.2 system-ui,sans-serif;white-space:nowrap;`
      + `box-shadow:0 1px 3px rgba(0,0,0,.25);cursor:pointer">`
      + `<span style="font-size:13px">${glyph || '■'}</span><span>${n.toLocaleString()}</span></div>`
      + pieSvg(scheme, mix, r, false, slice) + `</div>`,
    className: 'map-badge',
    // Sized to the content: a zero-size icon squeezes the badge into a sliver.
    iconSize: [badgeW + 2 + pieSize, h],
    iconAnchor: [13, h / 2]
  });
};

interface Props { data: RegistryRecord[]; }

const HaifaView: React.FC<Props> = ({ data }) => {
  const [quarters, setQuarters] = useState<Point[] | null>(null);
  const [sites, setSites] = useState<Site[]>([]);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [pieMode, setPieModeState] = usePieMode();
  // data is the whole registry here, so the ranked cuts rank on it directly.
  const scheme = useMemo(() => schemeFor(pieMode, data), [pieMode, data]);
  // A chosen slice belongs to the old cut; the quarter or institution stays
  // open, whole.
  const setPieMode = (m: typeof pieMode) => {
    setPieModeState(m);
    setSelection(s => (s ? { ...s, slice: null } : s));
  };
  const [basemap, setBasemap] = useState<BasemapKey>('historic');
  const [page, setPage] = useState(1);
  const [infoOpen, setInfoOpen] = useState<boolean>(() => {
    try { return localStorage.getItem('haifa.infoOpen') !== '0'; } catch { return true; }
  });
  const toggleInfo = () => setInfoOpen(v => {
    try { localStorage.setItem('haifa.infoOpen', v ? '0' : '1'); } catch { /* private window */ }
    return !v;
  });
  const [mapReady, setMapReady] = useState(0);
  const scans = usePageScans();

  const mapRef = useRef<L.Map | null>(null);
  const tileRef = useRef<L.TileLayer | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const resizeRef = useRef<ResizeObserver | null>(null);
  const fittedRef = useRef(false);

  useEffect(() => {
    fetch(PLACES_URL)
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`${r.status}`))))
      .then(j => { setQuarters(j.quarters || []); setSites(j.institutions || []); })
      .catch(() => { setQuarters([]); setSites([]); });
  }, []);

  // ------------------------------------------------------------ the records

  // Haifa's records: those the City puts in Haifa, and those whose address
  // names a Haifa quarter (Hawassa lay outside the municipality, and some
  // records carry no City at all).
  // A cut of one part of the registry (Jewish patients, infectious diseases)
  // narrows everything here to that part, badges and the side panel included.
  const haifaRows = useMemo(
    () => data.filter(r => (val(r, 'City') === 'Haifa' || val(r, 'Neighbourhood').startsWith(HAIFA_PREFIX))
                           && (!scheme.include || scheme.include(r))),
    [data, scheme]);

  const byQuarter = useMemo(() => {
    const out = new Map<string, RegistryRecord[]>();
    haifaRows.forEach(r => {
      const q = val(r, 'Neighbourhood');
      if (!q.startsWith(HAIFA_PREFIX)) return;
      const name = q.slice(HAIFA_PREFIX.length);
      const bucket = out.get(name);
      if (bucket) bucket.push(r); else out.set(name, [r]);
    });
    return out;
  }, [haifaRows]);
  let inQuarters = 0;
  byQuarter.forEach(b => { inQuarters += b.length; });
  const noQuarter = haifaRows.length - inQuarters;

  // Every institution the Haifa addresses name, whether or not it has a site.
  // Those listed in the places file use its windows; the rest are one entry.
  const institutions = useMemo(() => {
    const names = new Map<string, RegistryRecord[]>();
    haifaRows.forEach(r => {
      const inst = val(r, 'Address institution');
      if (!inst) return;
      const b = names.get(inst);
      if (b) b.push(r); else names.set(inst, [r]);
    });
    const out: { site: Site; rows: RegistryRecord[]; kind: string }[] = [];
    names.forEach((rows, name) => {
      const own = sites.filter(s => s.name === name);
      const kind = val(rows[0], 'Address institution type');
      if (own.length) {
        own.forEach(s => out.push({ site: s, rows: rows.filter(r => inWindow(r, s)), kind }));
      } else {
        out.push({ site: { name, qid: '', relation: '', anchor: '', lat: null, lon: null,
                           note: '', from: null, to: null, icon: '' }, rows, kind });
      }
    });
    return out.filter(i => i.rows.length).sort((a, b) => b.rows.length - a.rows.length);
  }, [haifaRows, sites]);

  const placedQuarters = useMemo(() => {
    if (!quarters) return [];
    // Two quarters drawn at the same landmark are nudged apart round a small
    // circle, so neither hides the other.
    const seen = new Map<string, number>();
    return quarters
      .filter(q => q.lat !== null && q.lon !== null && (byQuarter.get(q.name) || []).length)
      .map(q => {
        const rows = byQuarter.get(q.name) || [];
        const mix: Mix = {};
        rows.forEach(r => { const g = scheme.bucket(r); mix[g] = (mix[g] || 0) + 1; });
        const key = `${q.lat!.toFixed(4)},${q.lon!.toFixed(4)}`;
        const k = seen.get(key) || 0;
        seen.set(key, k + 1);
        const shift = k ? 0.0011 : 0;
        const angle = k * 2.1;
        return { ...q, rows, mix, n: rows.length, shifted: k > 0,
                 lat: q.lat! + shift * Math.sin(angle), lon: q.lon! + shift * 1.2 * Math.cos(angle) };
      })
      .sort((a, b) => b.n - a.n);
  }, [quarters, byQuarter, scheme]);

  // Quarters the address layer reads but the map cannot place.
  const unplacedQuarters = useMemo(() => {
    const placed = new Set(placedQuarters.map(q => q.name));
    const notes = new Map((quarters || []).map(q => [q.name, q.note]));
    return Array.from(byQuarter.entries())
      .filter(([name]) => !placed.has(name))
      .map(([name, rows]) => ({ name, n: rows.length, note: notes.get(name) || 'Not in the gazetteer table.' }))
      .sort((a, b) => b.n - a.n);
  }, [byQuarter, placedQuarters, quarters]);

  const placedSites = institutions.filter(i => i.site.lat !== null);
  const unplacedSites = institutions.filter(i => i.site.lat === null);

  const maxN = placedQuarters.length ? placedQuarters[0].n : 1;
  const radiusOf = useCallback((n: number) => 7 + 26 * Math.sqrt(n / maxN), [maxN]);

  // ------------------------------------------------------------ the map

  const attachMap = useCallback((node: HTMLDivElement | null) => {
    if (!node) {
      resizeRef.current?.disconnect();
      resizeRef.current = null;
      mapRef.current?.remove();
      mapRef.current = null;
      tileRef.current = null;
      layerRef.current = null;
      fittedRef.current = false;
      return;
    }
    if (mapRef.current) return;
    // zoomSnap 0 for the reason MapView gives: a whole-level snap would draw
    // the town at half the scale the panel holds.
    mapRef.current = L.map(node, {
      center: [32.81, 35.0], zoom: 13, maxBounds: MAP_BOUNDS, maxBoundsViscosity: 0.85,
      minZoom: 12, zoomSnap: 0, zoomDelta: 0.25
    });
    layerRef.current = L.layerGroup().addTo(mapRef.current);
    fittedRef.current = false;
    // The first pan, wheel or click on the map is the reader's; from then on
    // the view is theirs to keep.
    const mine = () => { fittedRef.current = true; };
    node.addEventListener('mousedown', mine);
    node.addEventListener('wheel', mine, { passive: true });
    node.addEventListener('touchstart', mine, { passive: true });
    const ro = new ResizeObserver(() => {
      const map = mapRef.current;
      if (!map) return;
      map.invalidateSize();
      fitRef.current();
    });
    ro.observe(node);
    resizeRef.current = ro;
    setMapReady(n => n + 1);
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const spec = BASEMAPS.find(b => b.key === basemap)!;
    const layer = L.tileLayer(spec.url, spec.options as L.TileLayerOptions);
    if (spec.key === 'historic') {
      layer.on('tileload', (e: L.TileEvent) => {
        const img = e.tile as HTMLImageElement;
        fetch(img.src).then(r => (r.ok ? r.blob() : null))
          .then(blob => { if (blob && blob.size <= BLANK_TILE_BYTES) img.style.visibility = 'hidden'; })
          .catch(() => { /* leave the tile alone */ });
      });
    }
    layer.addTo(map);
    const previous = tileRef.current;
    tileRef.current = layer;
    if (previous) layer.once('load', () => map.removeLayer(previous));
  }, [basemap, mapReady]);

  // The opening view frames every placed point, once the container has its
  // real width (see MapView on Leaflet's cached placeholder size). Called
  // through a ref from the ResizeObserver, which is created once.
  const fitToPoints = useCallback(() => {
    const map = mapRef.current;
    // Refitted on every resize until the reader takes the map in hand: the
    // panel reaches its real width some frames after the first fit.
    if (!map || fittedRef.current) return;
    map.invalidateSize();
    if (map.getSize().x < 200) return;
    const pts = [...placedQuarters.map(q => [q.lat, q.lon] as [number, number]),
                 ...placedSites.map(i => [i.site.lat!, i.site.lon!] as [number, number])];
    if (!pts.length) return;
    const bounds = L.latLngBounds(pts);
    map.setView(bounds.getCenter(), map.getBoundsZoom(bounds, false, L.point(70, 70)), { animate: false });
  }, [placedQuarters, placedSites]);
  const fitRef = useRef(fitToPoints);
  fitRef.current = fitToPoints;
  useEffect(() => { fitToPoints(); }, [fitToPoints, mapReady]);

  // Markers are redrawn whenever the selection changes: the selected slice is
  // drawn pulled out, the rest of its pie dimmed.
  useEffect(() => {
    const group = layerRef.current;
    if (!group) return;
    group.clearLayers();

    placedQuarters.forEach((q, i) => {
      const r = radiusOf(q.n);
      const isSel = selection?.kind === 'quarter' && selection.name === q.name;
      const marker = L.marker([q.lat, q.lon], {
        icon: pieIcon(scheme, q.mix, r, q.relation === 'near', isSel ? selection.slice : undefined),
        zIndexOffset: isSel ? 1000000 : i * 1000,
        riseOnHover: true, keyboard: false
      });
      const breakdown = scheme.keys.filter(k => q.mix[k])
        .map(k => `<span style="display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:4px;background:${scheme.color(k)}"></span>`
          + `${scheme.label(k)} ${q.mix[k].toLocaleString()} (${Math.round(100 * q.mix[k] / q.n)}%)`).join('<br>');
      marker.bindTooltip(
        `<strong>${q.name}</strong><br>${q.n.toLocaleString()} record${q.n === 1 ? '' : 's'}`
        + (q.relation === 'near' ? `<br><em>drawn at ${q.anchor}</em>` : '')
        + (q.shifted ? '<br><em>set slightly apart from a quarter drawn at the same point</em>' : '')
        + `<div style="margin-top:4px;font-size:11px;line-height:1.5">${breakdown}</div>`
        + '<div style="margin-top:4px;font-size:10px;color:#64748b">Click a slice for its records</div>',
        { direction: 'top', offset: [0, -r] }
      );
      marker.on('click', (e: L.LeafletMouseEvent) => {
        const target = (e.originalEvent?.target as Element | null)?.closest?.('[data-k]');
        setSelection({ kind: 'quarter', name: q.name, slice: target?.getAttribute('data-k') || null });
        setPage(1);
      });
      marker.addTo(group);
    });

    placedSites.forEach(inst => {
      const key = siteKey(inst.site);
      const isSel = selection?.kind === 'institution' && selection.key === key;
      const mix: Mix = {};
      inst.rows.forEach(r => { const g = scheme.bucket(r); mix[g] = (mix[g] || 0) + 1; });
      const r = radiusOf(inst.rows.length);
      const marker = L.marker([inst.site.lat!, inst.site.lon!], {
        icon: badgeIcon(inst.site.icon, inst.rows.length, isSel, scheme, mix, r, isSel ? selection.slice : undefined),
        zIndexOffset: 2000000, keyboard: false
      });
      const breakdown = scheme.keys.filter(k => mix[k])
        .map(k => `<span style="display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:4px;background:${scheme.color(k)}"></span>`
          + `${scheme.label(k)} ${mix[k].toLocaleString()} (${Math.round(100 * mix[k] / inst.rows.length)}%)`).join('<br>');
      marker.bindTooltip(
        `<strong>${inst.site.name}</strong><br>${inst.rows.length.toLocaleString()} records name it`
        + `<br><span style="font-size:11px">${inst.site.note}</span>`
        + `<div style="margin-top:4px;font-size:11px;line-height:1.5">${breakdown}</div>`
        + '<div style="margin-top:4px;font-size:10px;color:#64748b">Click a slice for its records</div>',
        { direction: 'top', offset: [0, -Math.max(12, r)] }
      );
      marker.on('click', (e: L.LeafletMouseEvent) => {
        const target = (e.originalEvent?.target as Element | null)?.closest?.('[data-k]');
        setSelection({ kind: 'institution', key, slice: target?.getAttribute('data-k') || null });
        setPage(1);
      });
      marker.addTo(group);
    });
  }, [placedQuarters, placedSites, selection, radiusOf, mapReady, scheme]);

  // ------------------------------------------------------- the selection

  const selected = useMemo(() => {
    if (!selection) return null;
    if (selection.kind === 'quarter') {
      const all = byQuarter.get(selection.name) || [];
      const rows = selection.slice
        ? all.filter(r => scheme.bucket(r) === selection.slice) : all;
      const q = (quarters || []).find(x => x.name === selection.name);
      const mix: Mix = {};
      all.forEach(r => { const g = scheme.bucket(r); mix[g] = (mix[g] || 0) + 1; });
      return { title: selection.name, subtitle: selection.slice && scheme.label(selection.slice),
               slice: selection.slice, rows, all: all.length, mix,
               qid: q?.qid || '', note: q?.note || '', anchor: q?.relation === 'near' ? q.anchor : '',
               kima: q?.kima || '', kimaNear: q?.kimaRelation === 'near', osm: q?.osm || '' };
    }
    const inst = institutions.find(i => siteKey(i.site) === selection.key);
    if (!inst) return null;
    const mix: Mix = {};
    inst.rows.forEach(r => { const g = scheme.bucket(r); mix[g] = (mix[g] || 0) + 1; });
    const rows = selection.slice ? inst.rows.filter(r => scheme.bucket(r) === selection.slice) : inst.rows;
    return { title: inst.site.name, subtitle: selection.slice && scheme.label(selection.slice),
             slice: selection.slice, rows, all: inst.rows.length, mix,
             qid: inst.site.qid, note: inst.site.note, anchor: inst.site.relation === 'near' ? inst.site.anchor : '',
             kima: '', kimaNear: false, osm: inst.site.osm || '' };
  }, [selection, byQuarter, quarters, institutions, scheme]);

  const records = selected?.rows || [];

  const yearly = useMemo(() => {
    const counts = new Map<number, number>();
    let undated = 0;
    records.forEach(r => {
      const year = parseInt(val(r, 'Admission Date').slice(0, 4), 10);
      if (!Number.isFinite(year) || year < 1900 || year > 2000) { undated++; return; }
      counts.set(year, (counts.get(year) || 0) + 1);
    });
    if (!counts.size) return { rows: [] as { year: string; n: number }[], undated };
    const years = Array.from(counts.keys());
    const rows: { year: string; n: number }[] = [];
    for (let y = Math.min(...years); y <= Math.max(...years); y++) rows.push({ year: String(y), n: counts.get(y) || 0 });
    return { rows, undated };
  }, [records]);

  const totalPages = Math.max(1, Math.ceil(records.length / PAGE_SIZE));
  const shown = records.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const exportRows = () => {
    if (!records.length || !selected) return;
    const cols = ['Notebook_Number', 'Page_Number', 'Notebook Record ID', ...FIELDS,
                  'City', 'Neighbourhood Wikidata', ...scheme.exportColumns, 'tempLink'];
    const csv = Papa.unparse(records.map(r => {
      const out: Record<string, string> = {};
      cols.forEach(c => { out[c] = val(r, c); });
      return out;
    }));
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
    link.download = `haifa_${[selected.title, selected.subtitle].filter(Boolean).join('_').replace(/[^\w-]+/g, '_')}.csv`;
    link.click();
  };

  if (quarters === null) {
    return (
      <div className="flex-1 flex items-center justify-center p-12 bg-slate-50">
        <p className="text-sm text-slate-500 animate-pulse">Loading Haifa's quarters…</p>
      </div>
    );
  }

  const mappedRecords = placedQuarters.reduce((s, q) => s + q.n, 0);
  const pick = (s: Selection) => { setSelection(s); setPage(1); };

  return (
    <div className="flex w-full h-full overflow-hidden bg-slate-50">
      <div className="flex-1 min-w-0 relative">
        {/* Inline height: see MapView for the Leaflet/Tailwind cascade race. */}
        <div ref={attachMap}
             style={{ position: 'absolute', inset: 0, height: '100%', width: '100%', background: '#e8e4da' }} />

        <div className="absolute top-4 right-4 z-[500] bg-white/95 backdrop-blur rounded-2xl border border-slate-200 shadow-lg p-2">
          <div className="flex items-center gap-1.5 px-2 pb-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <Layers size={12} /> Basemap
          </div>
          <div className="flex flex-col gap-1">
            {BASEMAPS.map(b => (
              <button key={b.key} onClick={() => setBasemap(b.key)}
                      className={`text-left px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                        basemap === b.key ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                                          : 'text-slate-600 border border-transparent hover:bg-slate-50'}`}>
                {b.label}
              </button>
            ))}
          </div>
          <PieModeSwitch mode={pieMode} onChange={setPieMode} />
        </div>

        <div className="absolute bottom-6 left-4 z-[500] bg-white/95 backdrop-blur rounded-2xl border border-slate-200 shadow-lg px-4 py-3 max-w-xs">
          <button onClick={toggleInfo} aria-expanded={infoOpen}
                  className="w-full flex items-center justify-between gap-3 text-left">
            <span className="text-xs font-bold text-slate-700">
              {placedQuarters.length} quarters · {mappedRecords.toLocaleString()}{scheme.subset ? ` ${scheme.subset}` : ''} records
            </span>
            {infoOpen ? <ChevronDown size={14} className="text-slate-400 shrink-0" />
                      : <ChevronUp size={14} className="text-slate-400 shrink-0" />}
          </button>
          {infoOpen && <>
            <PieLegend scheme={scheme} />
            <p className="text-[11px] text-slate-500 mt-2 leading-relaxed">
              Dashed rim: drawn at a landmark, the quarter has no point of its own.
              Square badges: institutions the addresses name, each with its own pie beside it.
            </p>
            <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
              Of {haifaRows.length.toLocaleString()}{scheme.subset ? ` ${scheme.subset}` : ''} Haifa records, {noQuarter.toLocaleString()} name
              no quarter, and {unplacedQuarters.reduce((s, q) => s + q.n, 0).toLocaleString()} name
              one the map cannot place — listed in the side panel.
            </p>
          </>}
        </div>
      </div>

      {selected ? (
        <div className="w-[30rem] shrink-0 bg-white border-l border-slate-200 overflow-y-auto custom-scrollbar">
          <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 z-10">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-black text-slate-800">
                  {selected.title}
                  {selected.subtitle && <span className="text-slate-400 font-bold"> · {selected.subtitle}</span>}
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  {records.length.toLocaleString()} record{records.length === 1 ? '' : 's'}
                  {selected.subtitle && <> of {selected.all.toLocaleString()} in {selection?.kind === 'institution' ? 'all' : 'the quarter'}</>}
                </p>
                <p className="text-[11px] text-slate-400 mt-1 flex flex-wrap gap-x-3">
                  {selected.qid && (
                    <a href={`https://www.wikidata.org/wiki/${selected.qid}`} target="_blank" rel="noreferrer"
                       className="text-indigo-600 underline">{selected.qid}</a>
                  )}
                  {selected.anchor && <span>drawn at {selected.anchor}</span>}
                  {selected.osm && (
                    <a href={`https://www.openstreetmap.org/${({ W: 'way', N: 'node', R: 'relation' } as Record<string, string>)[selected.osm[0]]}/${selected.osm.slice(1)}`}
                       target="_blank" rel="noreferrer" className="text-indigo-600 underline">OpenStreetMap</a>
                  )}
                  {selected.kima && (
                    <a href={`https://data.geo-kima.org/Places/Details/${selected.kima}`} target="_blank" rel="noreferrer"
                       className="text-indigo-600 underline">
                      Kima #{selected.kima}{selected.kimaNear && ' (nearby)'}
                    </a>
                  )}
                </p>
                {selected.note && <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">{selected.note}</p>}
              </div>
              <button onClick={() => setSelection(null)}
                      className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 shrink-0">
                <X size={16} />
              </button>
            </div>
            {/* The pie's slices as chips, so the reader can move between
                slices, or back to the whole, without the map. */}
            {selection && selected.mix && (
              <div className="flex flex-wrap gap-1.5 mt-3">
                <button onClick={() => pick({ ...selection, slice: null })}
                        className={`px-2 py-1 rounded-md text-[11px] font-bold border ${
                          !selection.slice ? 'bg-slate-800 text-white border-slate-800' : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
                  All {selected.all.toLocaleString()}
                </button>
                {scheme.keys.filter(k => selected.mix![k]).map(k => (
                  <button key={k} onClick={() => pick({ ...selection, slice: k })}
                          className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-bold border ${
                            selection.slice === k ? 'bg-slate-800 text-white border-slate-800' : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
                    <span className="w-2 h-2 rounded-sm" style={{ background: scheme.color(k) }} />
                    {scheme.label(k)} {selected.mix![k].toLocaleString()}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="px-6 py-5 border-b border-slate-200">
            <h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Admissions by year</h3>
            {yearly.rows.length === 0 ? (
              <p className="text-xs text-slate-400 italic mt-3">No record here carries a usable admission date.</p>
            ) : (
              <>
                <div className="h-40 mt-3 -ml-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={yearly.rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                      <XAxis dataKey="year" tick={{ fontSize: 10, fill: '#64748b' }} interval="preserveStartEnd"
                             tickLine={false} axisLine={{ stroke: '#e2e8f0' }} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: '#64748b' }}
                             tickLine={false} axisLine={false} width={34} />
                      <Tooltip cursor={{ fill: '#f1f5f9' }}
                               contentStyle={{ fontSize: 12, borderRadius: 10, border: '1px solid #e2e8f0' }}
                               formatter={(v: number) => [v.toLocaleString(), 'admissions']} />
                      <Bar dataKey="n" fill={selected.slice ? scheme.color(selected.slice) : SERIES[0]}
                           radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
                  The registers have archival gaps (1941–43 is missing) — see the Timeline before
                  reading a trough as a fall.
                  {yearly.undated > 0 && <> {yearly.undated.toLocaleString()} undated.</>}
                </p>
              </>
            )}
          </div>

          <div className="px-6 py-4">
            <div className="flex items-center justify-between gap-3 mb-3">
              <h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Records</h3>
              <div className="flex items-center gap-2">
                <button onClick={exportRows}
                        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-600 text-[11px] font-bold hover:bg-slate-50">
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
                  <div key={`${(page - 1) * PAGE_SIZE + idx}`} className="rounded-xl border border-slate-200 overflow-hidden">
                    <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 bg-slate-50 border-b border-slate-200">
                      <span className="text-[11px] text-slate-500">
                        <span className="font-mono text-slate-400">#{(page - 1) * PAGE_SIZE + idx + 1}</span>
                        {' '}Notebook <span className="font-bold text-slate-700">{notebook || '—'}</span>, p. {pageNo || '—'}
                      </span>
                      <ScanLink scans={scans} notebook={notebook} page={pageNo} notebookUrl={val(row, 'tempLink')} />
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
      ) : (
        <div className="w-[22rem] shrink-0 bg-white border-l border-slate-200 overflow-y-auto custom-scrollbar">
          <div className="px-5 py-4 border-b border-slate-200">
            <h3 className="font-bold text-slate-800 flex items-center gap-2">
              <Building2 size={18} className="text-slate-600" /> Haifa
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Click a pie slice, a badge, or a row here, for the records.
            </p>
          </div>

          <h4 className="px-5 pt-4 text-[10px] font-bold uppercase tracking-wider text-slate-400">Quarters on the map</h4>
          <ul className="p-2">
            {placedQuarters.map(q => (
              <li key={q.name}>
                <button onClick={() => {
                          pick({ kind: 'quarter', name: q.name, slice: null });
                          mapRef.current?.setView([q.lat, q.lon], Math.max(mapRef.current.getZoom(), 14));
                        }}
                        className="w-full flex items-baseline justify-between gap-3 px-3 py-1.5 rounded-lg hover:bg-slate-50 text-left">
                  <span className="text-xs font-medium text-slate-700 truncate">
                    {q.name}{q.relation === 'near' && <span className="text-slate-400"> · at {q.anchor}</span>}
                  </span>
                  <span className="text-xs font-bold tabular-nums text-slate-400 shrink-0">{q.n.toLocaleString()}</span>
                </button>
              </li>
            ))}
          </ul>

          {unplacedQuarters.length > 0 && <>
            <h4 className="px-5 pt-2 text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <MapPinOff size={11} /> Quarters with no point
            </h4>
            <ul className="p-2">
              {unplacedQuarters.map(q => (
                <li key={q.name}>
                  <button onClick={() => pick({ kind: 'quarter', name: q.name, slice: null })} title={q.note}
                          className="w-full flex items-baseline justify-between gap-3 px-3 py-1.5 rounded-lg hover:bg-slate-50 text-left">
                    <span className="text-xs text-slate-500 truncate italic">{q.name}</span>
                    <span className="text-xs font-bold tabular-nums text-slate-400 shrink-0">{q.n.toLocaleString()}</span>
                  </button>
                </li>
              ))}
            </ul>
          </>}

          <h4 className="px-5 pt-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">Institutions on the map</h4>
          <ul className="p-2">
            {placedSites.map(i => (
              <li key={siteKey(i.site)}>
                <button onClick={() => {
                          pick({ kind: 'institution', key: siteKey(i.site), slice: null });
                          mapRef.current?.setView([i.site.lat!, i.site.lon!], Math.max(mapRef.current.getZoom(), 14));
                        }}
                        className="w-full flex items-baseline justify-between gap-3 px-3 py-1.5 rounded-lg hover:bg-slate-50 text-left">
                  <span className="text-xs font-medium text-slate-700 truncate">
                    <span className="mr-1">{i.site.icon}</span>{i.site.name}
                    {i.site.from && <span className="text-slate-400"> · from {i.site.from}</span>}
                  </span>
                  <span className="text-xs font-bold tabular-nums text-slate-400 shrink-0">{i.rows.length.toLocaleString()}</span>
                </button>
              </li>
            ))}
          </ul>

          <h4 className="px-5 pt-2 text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <MapPinOff size={11} /> Institutions with no single site
          </h4>
          <p className="px-5 text-[11px] text-slate-400 leading-relaxed">
            Many places (the police, the army), or a site nobody has located.
          </p>
          <ul className="p-2">
            {unplacedSites.map(i => (
              <li key={siteKey(i.site)}>
                <button onClick={() => pick({ kind: 'institution', key: siteKey(i.site), slice: null })}
                        title={i.site.note || i.kind}
                        className="w-full flex items-baseline justify-between gap-3 px-3 py-1.5 rounded-lg hover:bg-slate-50 text-left">
                  <span className="text-xs text-slate-600 truncate">
                    {i.site.name}
                    {i.site.to && <span className="text-slate-400"> · until {i.site.to}</span>}
                    {i.kind && <span className="text-slate-300"> · {i.kind}</span>}
                  </span>
                  <span className="text-xs font-bold tabular-nums text-slate-400 shrink-0">{i.rows.length.toLocaleString()}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <HelpPanel title="How to use this" sections={HELP} storageKey="help.haifa" />
    </div>
  );
};

export default HaifaView;
