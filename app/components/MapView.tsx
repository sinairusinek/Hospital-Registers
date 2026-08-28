import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar
} from 'recharts';
import { MapPin, X, Layers, ChevronLeft, ChevronRight, Download } from 'lucide-react';
import { RegistryRecord } from '../types';
import { UNKNOWN, facetValue } from '../facets';
import { SERIES, NEUTRAL } from '../colors';
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
    heading: 'What a circle is',
    body: <p>One confirmed City value, sized by how many admissions carry it. The point is the coordinate of the gazetteer entry the review matched that value to — the settlement's own location, not the patient's address, which the registers record too coarsely to place. Haifa dominates by design: it is the hospital's own town.</p>
  },
  {
    heading: 'The two basemaps',
    body: <p><strong>Survey of Palestine 1:20,000</strong> is the Mandate-era sheet, the ground as the register clerks would have known it — villages that no longer exist are on it under the names they were then called. <strong>Modern</strong> is OpenStreetMap, for orientation. Toggling between them is the point: a place the register names may sit under a later town, or under nothing at all.</p>
  },
  {
    heading: 'What is not on the map',
    body: <p>Records whose City was left ambiguous, judged transcription junk, identified but absent from the gazetteer (the Haifa neighbourhoods especially), never reviewed, or simply blank. The footer counts each. Absence from the map is a state of the review, never a claim about the patient.</p>
  }
];

interface Place {
  // The label the circle carries: the gazetteer's own name where there is one,
  // otherwise the commonest spelling in the registers.
  label: string;
  // Every City spelling that resolved to this point. The registers spell
  // Zichron Yaakov eighteen ways; they are one place and must be one circle,
  // or the map shows eighteen stacked dots and each click hides seventeen
  // nineteenths of the records.
  cities: string[];
  lat: number;
  lon: number;
  source: string;
  kimaId: string;
  kimaName: string;
  qid: string;
}

interface Unplaced { decision: string; records: number; }

const val = (row: RegistryRecord, key: string): string => {
  const raw = row[key];
  if (raw === null || raw === undefined) return '';
  const s = String(raw).trim();
  return s === 'null' || s === 'undefined' ? '' : s;
};

const FIELDS = ['Admission Date', 'Age', 'Sex', 'Religion', 'Nationality',
                'Occupation', 'Address', 'City as written', 'Ward', 'Diagnosis', 'Result'];

const PAGE_SIZE = 25;

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

interface Props { data: RegistryRecord[]; }

const MapView: React.FC<Props> = ({ data }) => {
  const [places, setPlaces] = useState<Place[] | null>(null);
  const [unplaced, setUnplaced] = useState<Unplaced[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [basemap, setBasemap] = useState<BasemapKey>('historic');
  const [page, setPage] = useState(1);
  // Bumped whenever a map instance is created, so the tile and marker effects
  // re-run against the new one rather than the removed one.
  const [mapReady, setMapReady] = useState(0);
  const scans = usePageScans();

  const mapRef = useRef<L.Map | null>(null);
  const tileRef = useRef<L.TileLayer | null>(null);
  const markersRef = useRef<Map<string, L.CircleMarker>>(new Map());

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
        const missed = new Map<string, number>();
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
            } else {
              const kimaName = at(c, 'kima_name_rom');
              grouped.set(key, {
                // Kima's romanized name carries a parenthetical country; the
                // circle wants the bare settlement.
                label: kimaName ? kimaName.replace(/\s*\([^)]*\)\s*$/, '') : at(c, 'city'),
                cities: [at(c, 'city')],
                lat, lon,
                source: at(c, 'source'),
                kimaId,
                kimaName,
                qid: at(c, 'wikidata_qid')
              });
            }
          } else {
            const d = at(c, 'decision') || 'unreviewed';
            missed.set(d, (missed.get(d) || 0) + (parseInt(at(c, 'n_records'), 10) || 0));
          }
        });
        setPlaces(Array.from(grouped.values()));
        setUnplaced(Array.from(missed.entries())
          .map(([decision, records]) => ({ decision, records }))
          .sort((a, b) => b.records - a.records));
      })
      .catch(() => { setPlaces([]); setUnplaced([]); });
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

  const counted = useMemo(() => {
    if (!places) return [];
    return places
      .map(p => ({ ...p, n: p.cities.reduce((sum, c) => sum + (byCity.get(c) || []).length, 0) }))
      .filter(p => p.n > 0)
      .sort((a, b) => b.n - a.n);
  }, [places, byCity]);

  const maxN = counted.length ? counted[0].n : 1;

  // Records not on the map at all: no City on the record, or a City value the
  // review never reached. Counted from the data itself rather than from the
  // decisions file, so the two cannot drift.
  const offMap = useMemo(() => {
    if (!places) return { noCity: 0, unmatched: 0 };
    const placed = new Set(places.flatMap(p => p.cities));
    let noCity = 0, unmatched = 0;
    data.forEach(row => {
      const city = val(row, 'City');
      if (!city) noCity++;
      else if (!placed.has(city)) unmatched++;
    });
    return { noCity, unmatched };
  }, [data, places]);

  // ------------------------------------------------------------ the map

  // A callback ref, not an effect over a plain one: the view renders a loading
  // screen until the coordinates arrive, so the map element does not exist on
  // first mount and an effect keyed on [] would never get a second chance at
  // it. This runs exactly when the node appears and again if it is replaced,
  // which is also what makes it correct under StrictMode's double mount.
  const attachMap = useCallback((node: HTMLDivElement | null) => {
    if (!node) {
      mapRef.current?.remove();
      mapRef.current = null;
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
      maxBounds: L.latLngBounds([29.2, 33.8], [33.6, 36.4]),
      maxBoundsViscosity: 0.85,
      minZoom: 8
    });
    setMapReady(n => n + 1);
  }, []);

  // The basemap is a toggle, not a blend: one layer at a time, swapped in
  // place, so what you are reading the points against is never in doubt.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const spec = BASEMAPS.find(b => b.key === basemap)!;
    const layer = L.tileLayer(spec.url, spec.options as L.TileLayerOptions);

    // Outside the surveyed area, Palestine Open Maps answers with a solid
    // black 256px JPEG rather than a 404, so Leaflet has no way to know the
    // tile is empty and the map ends in a black field. Nothing in CSS can
    // reach that — the black is the image. Each tile is therefore sampled
    // once it decodes, and the blank ones are hidden so the container's own
    // paper colour shows through and the sheet simply ends.
    if (spec.key === 'historic') {
      layer.on('tileload', (e: L.TileEvent) => {
        const img = e.tile as HTMLImageElement;
        try {
          const probe = document.createElement('canvas');
          probe.width = probe.height = 8;
          const ctx = probe.getContext('2d', { willReadFrequently: true });
          if (!ctx) return;
          ctx.drawImage(img, 0, 0, 8, 8);
          const { data: px } = ctx.getImageData(0, 0, 8, 8);
          let lightest = 0;
          for (let i = 0; i < px.length; i += 4) {
            lightest = Math.max(lightest, px[i], px[i + 1], px[i + 2]);
          }
          // The survey's darkest real ink still sits well above this; only a
          // tile that is black edge to edge fails it.
          if (lightest < 12) img.style.visibility = 'hidden';
        } catch {
          // A tainted canvas means no reading is possible; leave the tile be.
        }
      });
    }

    layer.addTo(map);
    const previous = tileRef.current;
    tileRef.current = layer;
    // Removing the old layer only once the new one has drawn avoids a white
    // flash between the two sheets.
    if (previous) layer.once('load', () => map.removeLayer(previous));
  }, [basemap, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !counted.length) return;
    markersRef.current.forEach(m => m.remove());
    markersRef.current = new Map();

    counted.forEach(p => {
      // Area, not radius, tracks the count — a radius scale would read Haifa as
      // hundreds of times the size of Acre rather than the ~9x it is.
      const radius = 5 + 22 * Math.sqrt(p.n / maxN);
      const marker = L.circleMarker([p.lat, p.lon], {
        radius,
        color: '#ffffff', weight: 1.5,
        fillColor: SERIES[0], fillOpacity: 0.72
      });
      marker.bindTooltip(
        `<strong>${p.label}</strong><br>${p.n.toLocaleString()} record${p.n === 1 ? '' : 's'}`,
        { direction: 'top', offset: [0, -4] }
      );
      marker.on('click', () => { setSelected(p.kimaId || p.label); setPage(1); });
      marker.addTo(map);
      markersRef.current.set(p.kimaId || p.label, marker);
    });

    return () => { markersRef.current.forEach(m => m.remove()); };
  }, [counted, maxN, mapReady]);

  // The selected circle is repainted rather than re-created, so the map does
  // not flicker on every selection.
  useEffect(() => {
    markersRef.current.forEach((marker, key) => {
      const on = key === selected;
      marker.setStyle({
        fillColor: on ? SERIES[1] : SERIES[0],
        fillOpacity: on ? 0.9 : 0.72,
        color: on ? '#1f2937' : '#ffffff',
        weight: on ? 2.5 : 1.5
      });
      if (on) marker.bringToFront();
    });
  }, [selected, counted]);

  // ------------------------------------------------------- the selection

  const selectedPlace = counted.find(p => (p.kimaId || p.label) === selected) || null;
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
        </div>

        {/* What the map does and does not carry */}
        <div className="absolute bottom-6 left-4 z-[500] bg-white/95 backdrop-blur rounded-2xl border border-slate-200 shadow-lg px-4 py-3 max-w-xs">
          <p className="text-xs font-bold text-slate-700">
            {counted.length} places · {mappedRecords.toLocaleString()} records
          </p>
          <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
            Not on the map: {offMap.unmatched.toLocaleString()} records whose City the
            review could not place, {offMap.noCity.toLocaleString()} with no City recorded.
            {unplaced.length > 0 && (
              <> Of the reviewed values: {unplaced.map(u => `${u.decision} ${u.records.toLocaleString()}`).join(', ')}.</>
            )}
          </p>
        </div>
      </div>

      {/* The selected place */}
      {selectedPlace && (
        <div className="w-[30rem] shrink-0 bg-white border-l border-slate-200 overflow-y-auto custom-scrollbar">
          <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 z-10">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-black text-slate-800">{selectedPlace.label}</h2>
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
                  {selectedPlace.qid && (
                    <a href={`https://www.wikidata.org/wiki/${selectedPlace.qid}`}
                       target="_blank" rel="noreferrer" className="text-indigo-600 underline">
                      {selectedPlace.qid}
                    </a>
                  )}
                  <span>point from {selectedPlace.source}</span>
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
              Click a circle, or a row here, for that place's records over time.
            </p>
          </div>
          <ul className="p-2">
            {counted.map(p => (
              <li key={p.kimaId || p.label}>
                <button
                  onClick={() => {
                    setSelected(p.kimaId || p.label);
                    setPage(1);
                    mapRef.current?.setView([p.lat, p.lon], Math.max(mapRef.current.getZoom(), 11));
                  }}
                  className="w-full flex items-baseline justify-between gap-3 px-3 py-2 rounded-lg hover:bg-slate-50 text-left"
                >
                  <span className="text-xs font-medium text-slate-700 truncate">{p.label}</span>
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
