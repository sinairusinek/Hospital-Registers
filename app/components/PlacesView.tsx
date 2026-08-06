
import React, { useEffect, useMemo, useState } from 'react';
import { MapPin, ChevronLeft, ChevronRight, Download } from 'lucide-react';
import { RegistryRecord } from '../types';
import { UNKNOWN, facetValue } from '../facets';
import HelpPanel, { HelpSection } from './HelpPanel';
import ScanLink, { usePageScans } from './ScanLink';

declare const Papa: any;

const HELP: HelpSection[] = [
  {
    heading: 'Where these links come from',
    body: <p>Every distinct City value among the Jewish patients was matched against the Kima Historical Gazetteer in a human-in-the-loop session (August 2026). The decisions live in <em>kimatch/city-kima-decisions.tsv</em>; the build joins them onto every record that carries the same City value, whatever the patient's community. Values outside that queue are simply not yet reviewed — absence of a link is not a verdict.</p>
  },
  {
    heading: 'Reading the interpretation',
    body: <p><em>Decided by</em> says who made the call: <strong>auto</strong> is an exact-name engine match that passed a geographic audit; <strong>agent</strong> is the assistant's adjudication of a review-grade row; <strong>human</strong> is the historian's own ruling. The note carries the reasoning — a garbled spelling read, a naming tradition kept distinct, or the reason a value was held back.</p>
  },
  {
    heading: 'The queues to work first',
    body: <p><em>Held for review</em> is the standing question list: physical features (Mount Carmel, the valleys), foreign locations, and the cases explicitly kept open (Haifa|Bassa, Ghedera). <em>Ambiguous</em> holds the garbled singletons worth checking against the scans. Corrections go into the decisions file — edit <em>kimatch/build_decisions.py</em> and rebuild — never into this view.</p>
  }
];

interface Decision {
  kima_id: string;
  kima_name_rom: string;
  wikidata_qid: string;
  decision: string;
  decided_by: string;
  note: string;
}

// The reviewed City values, keyed by the exact City string; loaded beside the
// dataset (see scripts/copy-data.mjs).
const DECISIONS_URL = `${import.meta.env.BASE_URL}data/city-kima-decisions.tsv`;

const FIELDS = ['Address', 'City as written', 'City', 'City Kima ID', 'City Wikidata'];

const QUEUES: { key: string; title: string; question: string }[] = [
  {
    key: 'held',
    title: 'Held for your review',
    question: 'Cases deliberately left open: physical-feature and region entities (Mount Carmel, the valleys, Huleh), foreign locations, and the values you asked to keep — Haifa|Bassa, Ghedera. Each note carries the suggested Kima entry; confirming or rejecting it is a one-line change to the decisions table.'
  },
  {
    key: 'ambiguous',
    title: 'Ambiguous, unresolved',
    question: 'Values with more than one plausible referent or garbled beyond confident reading. The page is the only authority: open the scan and see what the clerk actually wrote.'
  },
  {
    key: 'no-entry',
    title: 'Real place, no Kima entry',
    question: 'Identified places the gazetteer does not yet carry — Haifa neighborhoods (Halisa, Ard el-Yahud), the Galilee Waldheim, Beit Gan, streets and institutions. These are the donation candidates for a future Kima contribution round.'
  },
  {
    key: 'matched-agent',
    title: 'Matched — assistant’s reading',
    question: 'Links resting on the assistant’s adjudication: spelling variants, garbled forms with a single plausible referent, catchment reasoning. Spot-check against the scans; a veto is an edit to the decisions table.'
  },
  {
    key: 'matched-human',
    title: 'Matched — your rulings',
    question: 'Links that follow decisions you made in the review session: Tel Amal to Nir David, Bethania to Bitanya, the finer-reading pipe policy, al-Bassa, Degania Alef.'
  },
  {
    key: 'matched-auto',
    title: 'Matched — engine, geo-audited',
    question: 'Unambiguous exact-name matches from the kimatch engine, each checked to fall inside the Israel/Palestine region. The least likely to need attention.'
  },
  {
    key: 'junk',
    title: 'Transcription junk',
    question: 'Values judged to be noise rather than places — fragments, generic words, debris. If one of these is legible on the page after all, it belongs back in the queue.'
  },
  {
    key: 'unreviewed',
    title: 'Not yet reviewed',
    question: 'Records whose City value was outside the reviewed queue — it appears only among Muslim, Christian or other communities’ records. A future matching round starts here.'
  },
  {
    key: 'no-city',
    title: 'No city recorded',
    question: 'Records where the City column is empty. Some carry an Address that names a place; those are candidates for lifting a settlement name into City in the source.'
  }
];

const PAGE_SIZE = 25;

const val = (row: RegistryRecord, key: string): string => {
  const raw = row[key];
  if (raw === null || raw === undefined) return '';
  const s = String(raw).trim();
  return s === 'null' || s === 'undefined' ? '' : s;
};

interface Props {
  data: RegistryRecord[];
}

const PlacesView: React.FC<Props> = ({ data }) => {
  const [decisions, setDecisions] = useState<Record<string, Decision> | null>(null);
  const scans = usePageScans();
  const [active, setActive] = useState<string>('held');
  const [page, setPage] = useState(1);
  const [religion, setReligion] = useState<string>('All');
  const [nationality, setNationality] = useState<string>('All');

  useEffect(() => {
    fetch(DECISIONS_URL)
      .then(r => (r.ok ? r.text() : Promise.reject(new Error(`${r.status}`))))
      .then(text => {
        const lines = text.split(/\r?\n/).filter(l => l.trim());
        const header = lines[0].split('\t');
        const idx = (name: string) => header.indexOf(name);
        const out: Record<string, Decision> = {};
        lines.slice(1).forEach(line => {
          const cells = line.split('\t');
          out[cells[idx('city')]] = {
            kima_id: cells[idx('kima_id')] || '',
            kima_name_rom: cells[idx('kima_name_rom')] || '',
            wikidata_qid: cells[idx('wikidata_qid')] || '',
            decision: cells[idx('decision')] || '',
            decided_by: cells[idx('decided_by')] || '',
            note: cells[idx('note')] || ''
          };
        });
        setDecisions(out);
      })
      .catch(() => setDecisions({}));
  }, []);

  const queueOf = (row: RegistryRecord): string => {
    const city = val(row, 'City');
    if (!city) return 'no-city';
    const d = decisions?.[city];
    if (!d) return 'unreviewed';
    if (d.note.includes('held for human review') || d.note.includes('held for your review')) return 'held';
    if (d.decision === 'matched') return `matched-${d.decided_by}`;
    if (d.decision === 'unmatched-ambiguous') return 'ambiguous';
    if (d.decision === 'unmatched-no-kima-entry') return 'no-entry';
    return 'junk';
  };

  const byQueue = useMemo(() => {
    const out: Record<string, RegistryRecord[]> = {};
    QUEUES.forEach(q => { out[q.key] = []; });
    if (!decisions) return out;
    data.forEach(row => {
      const q = queueOf(row);
      if (out[q]) out[q].push(row);
    });
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, decisions]);

  const facetOptions = (key: string): string[] => {
    const counts = new Map<string, number>();
    data.forEach(r => {
      const v = facetValue(r[key]);
      counts.set(v, (counts.get(v) || 0) + 1);
    });
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]).map(([v]) => v);
  };
  const religions = useMemo(() => facetOptions('Religion'), [data]);
  const nationalities = useMemo(() => facetOptions('Nationality'), [data]);

  const queue = QUEUES.find(q => q.key === active)!;
  const records = useMemo(() => {
    let rows = byQueue[active] || [];
    if (religion !== 'All') rows = rows.filter(r => facetValue(r['Religion']) === religion);
    if (nationality !== 'All') rows = rows.filter(r => facetValue(r['Nationality']) === nationality);
    return rows;
  }, [byQueue, active, religion, nationality]);

  const totalPages = Math.max(1, Math.ceil(records.length / PAGE_SIZE));
  const shown = records.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const select = (key: string) => { setActive(key); setPage(1); };

  const exportQueue = () => {
    if (records.length === 0) return;
    const cols = ['Notebook_Number', 'Page_Number', 'Notebook Record ID', 'Religion', 'Nationality', ...FIELDS, 'tempLink'];
    const csv = Papa.unparse(records.map(r => {
      const out: Record<string, string> = {};
      cols.forEach(c => { out[c] = val(r, c); });
      const d = decisions?.[val(r, 'City')];
      out['Match decision'] = d?.decision || '';
      out['Decided by'] = d?.decided_by || '';
      out['Match note'] = d?.note || '';
      return out;
    }));
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
    link.download = `places_${active}.csv`;
    link.click();
  };

  if (decisions === null) {
    return (
      <div className="flex-1 flex items-center justify-center p-12 bg-slate-50">
        <p className="text-sm text-slate-500 animate-pulse">Loading the gazetteer decisions…</p>
      </div>
    );
  }

  return (
    <div className="flex w-full h-full overflow-hidden bg-slate-50">
      {/* Queues + facets */}
      <div className="w-80 shrink-0 bg-white border-r border-slate-200 overflow-y-auto">
        <div className="p-5 border-b border-slate-200">
          <h3 className="font-bold text-slate-800 flex items-center gap-2">
            <MapPin size={18} className="text-slate-600" /> Places
          </h3>
          <p className="text-xs text-slate-500 mt-1">
            Every record, by the standing of its City value against the Kima gazetteer.
          </p>
          <div className="mt-3 space-y-2">
            <label className="block">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Religion</span>
              <select
                value={religion}
                onChange={e => { setReligion(e.target.value); setPage(1); }}
                className="mt-0.5 w-full text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white text-slate-700"
              >
                <option>All</option>
                {religions.map(v => <option key={v}>{v}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Nationality</span>
              <select
                value={nationality}
                onChange={e => { setNationality(e.target.value); setPage(1); }}
                className="mt-0.5 w-full text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white text-slate-700"
              >
                <option>All</option>
                {nationalities.map(v => <option key={v}>{v}</option>)}
              </select>
            </label>
          </div>
        </div>
        <ul className="p-3 space-y-1">
          {QUEUES.map(q => {
            const n = (byQueue[q.key] || []).length;
            const isActive = q.key === active;
            return (
              <li key={q.key}>
                <button
                  onClick={() => select(q.key)}
                  disabled={n === 0}
                  className={`w-full text-left px-3 py-2.5 rounded-xl transition-colors disabled:opacity-40 ${isActive ? 'bg-indigo-50 border border-indigo-200' : 'border border-transparent hover:bg-slate-50'}`}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className={`text-xs font-bold ${isActive ? 'text-indigo-700' : 'text-slate-700'}`}>
                      {q.title}
                    </span>
                    <span className={`text-xs font-bold tabular-nums shrink-0 ${isActive ? 'text-indigo-600' : 'text-slate-400'}`}>
                      {n.toLocaleString()}
                    </span>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {/* The queue itself */}
      <div className="flex-1 overflow-y-auto p-8 space-y-6 custom-scrollbar">
        <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-sm space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-xl font-black text-slate-800">{queue.title}</h2>
              <p className="text-xs text-slate-400 mt-1">
                {records.length.toLocaleString()} records
                {religion !== 'All' && <> · {religion}</>}
                {nationality !== 'All' && <> · {nationality}</>}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={exportQueue}
                disabled={records.length === 0}
                className="flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-600 text-xs font-bold hover:bg-slate-50 transition-colors disabled:opacity-30"
              >
                <Download size={14} /> Export queue
              </button>
              <div className="flex items-center bg-slate-100 rounded-lg p-1">
                <button disabled={page === 1} onClick={() => setPage(p => Math.max(1, p - 1))} className="p-1.5 rounded-md hover:bg-white disabled:opacity-30"><ChevronLeft size={16} /></button>
                <span className="px-3 text-xs font-bold text-slate-600 font-mono">{page} / {totalPages}</span>
                <button disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))} className="p-1.5 rounded-md hover:bg-white disabled:opacity-30"><ChevronRight size={16} /></button>
              </div>
            </div>
          </div>
          <p className="text-sm text-slate-600 leading-relaxed max-w-3xl">{queue.question}</p>
        </div>

        {records.length === 0 ? (
          <div className="text-center text-sm text-slate-400 italic py-16">No records in this queue under the current facets.</div>
        ) : (
          <div className="space-y-4">
            {shown.map((row, idx) => {
              const notebook = val(row, 'Notebook_Number');
              const pageNo = val(row, 'Page_Number');
              const link = val(row, 'tempLink');
              const d = decisions[val(row, 'City')];
              return (
                <div key={`${(page - 1) * PAGE_SIZE + idx}`} className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                  <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 bg-slate-50 border-b border-slate-200">
                    <div className="flex items-center gap-4 text-xs text-slate-500">
                      <span className="font-mono text-slate-400">#{(page - 1) * PAGE_SIZE + idx + 1}</span>
                      <span><span className="font-bold text-slate-700">Notebook {notebook || '—'}</span>, page {pageNo || '—'}</span>
                      {val(row, 'Notebook Record ID') && <span>record {val(row, 'Notebook Record ID')}</span>}
                      <span>{facetValue(row['Religion'])}{val(row, 'Nationality') ? ` · ${val(row, 'Nationality')}` : ''}</span>
                    </div>
                    <ScanLink scans={scans} notebook={notebook} page={pageNo} notebookUrl={link} />
                  </div>
                  <dl className="px-5 py-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-3">
                    {FIELDS.map(field => {
                      const v = val(row, field);
                      return (
                        <div key={field}>
                          <dt className="text-[9px] font-bold uppercase tracking-wider text-slate-400">{field}</dt>
                          <dd className={`text-xs mt-0.5 break-words ${v ? 'text-slate-700 font-medium' : 'text-slate-300 italic'}`}>
                            {!v ? UNKNOWN
                              : field === 'City Kima ID' ? (
                                <a href={`https://data.geo-kima.org/Places/Details/${v}`} target="_blank" rel="noreferrer" className="text-indigo-600 underline">#{v}{d?.kima_name_rom ? ` ${d.kima_name_rom}` : ''}</a>
                              ) : field === 'City Wikidata' ? (
                                <a href={`https://www.wikidata.org/wiki/${v}`} target="_blank" rel="noreferrer" className="text-indigo-600 underline">{v}</a>
                              ) : v}
                          </dd>
                        </div>
                      );
                    })}
                    <div className="sm:col-span-2 lg:col-span-3 pt-1 border-t border-slate-100">
                      <dt className="text-[9px] font-bold uppercase tracking-wider text-slate-400">Interpretation</dt>
                      <dd className="text-xs mt-0.5 text-slate-600">
                        {d ? (
                          <>
                            <span className="font-bold">{d.decision}</span>
                            {' '}· decided by {d.decided_by}
                            {d.note && <> — {d.note}</>}
                          </>
                        ) : val(row, 'City') ? (
                          <span className="italic text-slate-400">City value not in the reviewed queue.</span>
                        ) : (
                          <span className="italic text-slate-400">No City on this record.</span>
                        )}
                      </dd>
                    </div>
                  </dl>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <HelpPanel title="How to use this" sections={HELP} storageKey="help.places" />
    </div>
  );
};

export default PlacesView;
