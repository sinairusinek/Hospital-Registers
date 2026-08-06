
import React, { useMemo, useState } from 'react';
import { ClipboardCheck, ExternalLink, ChevronLeft, ChevronRight, Download, BookOpen } from 'lucide-react';
import { RegistryRecord } from '../types';
import { UNKNOWN } from '../facets';
import HelpPanel, { HelpSection } from './HelpPanel';

declare const Papa: any;

const HELP: HelpSection[] = [
  {
    heading: 'A flag is not an error',
    body: <p>Every record here is one the pipeline could not settle on its own. Some are plainly wrong; most are places where the machine's reading is uncertain and the page is the only authority. Nothing has been corrected on the strength of a flag — the flag exists so that a person can go and look.</p>
  },
  {
    heading: 'Work from the smallest queue',
    body: <p>The queues are ordered by how tractable they are, not by size. Twenty records where an operation was entered in the diagnosis column can be settled in an afternoon and will change how that column is read; the 1,465 with no placeable ICD-9 code are a long project. Start at the top.</p>
  },
  {
    heading: 'What the scan link gives you',
    body: <p>The link opens the notebook in the Haifa library's viewer — the whole volume, not the single page, because that is the granularity the dataset records. The notebook and page numbers beside it are what to navigate to. Records whose notebook carries no link show the numbers alone.</p>
  },
  {
    heading: 'Corrections go to the source',
    body: <p>This view is read-only by design. The published file is rebuilt from the consolidated TSV by <em>pipeline/build.py</em> on every change, so anything edited here would be overwritten on the next build. Fix the consolidated TSV, or add a rule to the pipeline, and the flag disappears of its own accord.</p>
  }
];

// Keyed by flag: what the reviewer needs in front of them, and what to check.
// A record flagged for a broken stay does not need its address; one flagged for
// a procedure code does not need its dates.
const QUEUES: { flag: string; title: string; question: string; fields: string[] }[] = [
  {
    flag: 'procedure-not-diagnosis',
    title: 'An operation where a diagnosis belongs',
    question: 'The diagnosis column holds an intervention — a forceps delivery, a curettage — rather than the condition that called for it. What was the patient admitted for? The same substitution may well appear in records whose codes are well-formed, where nothing catches it.',
    fields: ['Diagnosis as written', 'Diagnosis', 'ICD-9 Code', 'ICD-9 Chapter', 'Ward', 'Result']
  },
  {
    flag: 'impossible-stay',
    title: 'Discharged before admitted',
    question: 'The dates as written put the discharge before the admission, so the length of stay has been cleared rather than published as a negative number. Which of the two dates does the page actually carry?',
    fields: ['Admission Date as written', 'Admission Date', 'Discharge Date as written', 'Discharge Date', 'Days in Hospital as written', 'Days in Hospital']
  },
  {
    flag: 'stay-over-by-a-year',
    title: 'A stay exactly a year too long',
    question: 'The computed stay sits 365 days above the count the clerk wrote beside it — the discharge year in the register is one too high. Correcting it would mean overruling the source, so it has been left standing. Does the page bear out the clerk\'s count?',
    fields: ['Admission Date as written', 'Admission Date', 'Discharge Date as written', 'Discharge Date', 'Days in Hospital as written', 'Days in Hospital']
  },
  {
    flag: 'sex-cleared',
    title: 'A stray letter where a sex belongs',
    question: 'The source held a single letter that is not an abbreviation of either term in any reading — debris from a neighbouring column. It has been cleared here; the consolidated TSV still holds the letter. What does the page say?',
    fields: ['Sex', 'Age', 'Ward', 'Diagnosis']
  },
  {
    flag: 'date-unreadable',
    title: 'A date that could not be read',
    question: 'The clerk\'s own writing could not be parsed into a date, so the upstream conversion has been left in place — the only reading available, and an unverified one. Does it match the page?',
    fields: ['Admission Date as written', 'Admission Date', 'Discharge Date as written', 'Discharge Date', 'Days in Hospital as written', 'Days in Hospital']
  },
  {
    flag: 'stay-disagrees',
    title: 'The stay disagrees with the count beside it',
    question: 'The stay computed from the two dates differs from the number the clerk wrote in the register. Usually one date is off by a day or two. Which does the page support — and is the discrepancy a transcription slip or the clerk\'s own arithmetic?',
    fields: ['Admission Date as written', 'Admission Date', 'Discharge Date as written', 'Discharge Date', 'Days in Hospital as written', 'Days in Hospital']
  },
  {
    flag: 'result-in-diagnosis',
    title: 'A Result value in the diagnosis column',
    question: 'The diagnosis or code field holds "Cured", "Died" or another outcome — the Result column\'s content one field to the left. This is a column misalignment in the source, not a missing diagnosis, so nothing has been classified from it. What does the page have in the diagnosis column?',
    fields: ['Diagnosis as written', 'Diagnosis', 'ICD-9 Code', 'Result as written', 'Result']
  },
  {
    flag: 'classifier-debris',
    title: 'Classifier error text where a diagnosis belongs',
    question: 'The original classification pass ran on GPT-4o and hit a rate limit; on these records the 429 error text was written into the diagnosis field instead of a diagnosis. The register almost certainly carries a legible diagnosis here — it was simply never read. These are the clearest candidates for re-running the classification.',
    fields: ['Diagnosis as written', 'Diagnosis as standardized', 'Diagnosis', 'ICD-9 Code']
  },
  {
    flag: 'procedure-only',
    title: 'An operation with no diagnosis behind it',
    question: 'The diagnosis column names an operation — a forceps delivery, a curettage, a tonsillectomy — and no diagnosis was placed behind it. The condition that called for the operation is what the chapter would need. Note that 476 further records name an operation *and* carry a diagnosis; those are in the "Procedure named?" facet, not here.',
    fields: ['Diagnosis as written', 'Diagnosis', 'ICD-9 Code', 'Procedure', 'Ward', 'Result']
  },
  {
    flag: 'no-icd9-chapter',
    title: 'No ICD-9 code that could be placed',
    question: 'No code the classification could place, so the record sits outside every chapter and outside every diagnosis chart. Of these, 729 carry no diagnosis at all — the register\'s own silence, and nothing a classifier could reach. The rest carry a diagnosis the coding never got to. Is the diagnosis legible on the page, and does it correspond to a code?',
    fields: ['Diagnosis as written', 'Diagnosis as standardized', 'Diagnosis', 'ICD-9 Code', 'ICD-9 Category']
  }
];

const PAGE_SIZE = 25;

interface Props {
  data: RegistryRecord[];
}

const val = (row: RegistryRecord, key: string): string => {
  const raw = row[key];
  if (raw === null || raw === undefined) return '';
  const s = String(raw).trim();
  return s === 'null' || s === 'undefined' ? '' : s;
};

const ReviewView: React.FC<Props> = ({ data }) => {
  const [active, setActive] = useState<string>(QUEUES[0].flag);
  const [page, setPage] = useState(1);

  // The flag column is written by pipeline/build.py. If an older file is
  // uploaded it will not be there, and the view says so rather than showing an
  // empty queue that looks like a clean bill of health.
  const flagKey = useMemo(() => {
    if (data.length === 0) return undefined;
    return Object.keys(data[0]).find(k => k.toLowerCase().trim() === 'review flags');
  }, [data]);

  const byFlag = useMemo(() => {
    const out: Record<string, RegistryRecord[]> = {};
    QUEUES.forEach(q => { out[q.flag] = []; });
    if (!flagKey) return out;
    data.forEach(row => {
      val(row, flagKey).split('|').filter(Boolean).forEach(flag => {
        if (out[flag]) out[flag].push(row);
      });
    });
    return out;
  }, [data, flagKey]);

  const queue = QUEUES.find(q => q.flag === active)!;
  const records = byFlag[active] || [];
  const totalPages = Math.max(1, Math.ceil(records.length / PAGE_SIZE));
  const shown = records.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const totalFlagged = useMemo(
    () => (flagKey ? data.filter(r => val(r, flagKey)).length : 0),
    [data, flagKey]
  );

  const select = (flag: string) => { setActive(flag); setPage(1); };

  const exportQueue = () => {
    if (records.length === 0) return;
    const cols = ['Notebook_Number', 'Page_Number', 'Notebook Record ID', ...queue.fields, 'tempLink'];
    const csv = Papa.unparse(records.map(r => {
      const out: Record<string, string> = {};
      cols.forEach(c => { out[c] = val(r, c); });
      return out;
    }));
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
    link.download = `review_${active}.csv`;
    link.click();
  };

  if (!flagKey) {
    return (
      <div className="flex-1 flex items-center justify-center p-12 text-center bg-slate-50">
        <div className="max-w-md space-y-3">
          <ClipboardCheck size={40} className="mx-auto text-slate-300" strokeWidth={1.5} />
          <h3 className="font-bold text-slate-700">No review flags in this file</h3>
          <p className="text-sm text-slate-500">
            The loaded dataset carries no <em>Review Flags</em> column. It is written by
            <span className="font-mono text-xs"> pipeline/build.py</span>; rebuild the artifact,
            or reload the bundled dataset, to work through the queues.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex w-full h-full overflow-hidden bg-slate-50">
      {/* Queues */}
      <div className="w-80 shrink-0 bg-white border-r border-slate-200 overflow-y-auto">
        <div className="p-5 border-b border-slate-200">
          <h3 className="font-bold text-slate-800 flex items-center gap-2">
            <ClipboardCheck size={18} className="text-slate-600" /> Needs a human eye
          </h3>
          <p className="text-xs text-slate-500 mt-1">
            {totalFlagged.toLocaleString()} of {data.length.toLocaleString()} records
            {' '}({((totalFlagged / Math.max(1, data.length)) * 100).toFixed(1)}%) carry at least one flag.
          </p>
        </div>
        <ul className="p-3 space-y-1">
          {QUEUES.map(q => {
            const n = (byFlag[q.flag] || []).length;
            const isActive = q.flag === active;
            return (
              <li key={q.flag}>
                <button
                  onClick={() => select(q.flag)}
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
                  <span className="block text-[10px] text-slate-400 font-mono mt-0.5">{q.flag}</span>
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
              <p className="text-xs font-mono text-slate-400 mt-1">{queue.flag}</p>
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
          <div className="text-center text-sm text-slate-400 italic py-16">Nothing flagged in this queue.</div>
        ) : (
          <div className="space-y-4">
            {shown.map((row, idx) => {
              const notebook = val(row, 'Notebook_Number');
              const pageNo = val(row, 'Page_Number');
              const link = val(row, 'tempLink');
              return (
                <div key={`${(page - 1) * PAGE_SIZE + idx}`} className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                  <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 bg-slate-50 border-b border-slate-200">
                    <div className="flex items-center gap-4 text-xs text-slate-500">
                      <span className="font-mono text-slate-400">#{(page - 1) * PAGE_SIZE + idx + 1}</span>
                      <span><span className="font-bold text-slate-700">Notebook {notebook || '—'}</span>, page {pageNo || '—'}</span>
                      {val(row, 'Notebook Record ID') && <span>record {val(row, 'Notebook Record ID')}</span>}
                    </div>
                    {link ? (
                      <a
                        href={link}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1.5 text-xs font-bold text-indigo-600 hover:text-indigo-800 transition-colors"
                      >
                        <BookOpen size={13} /> Open the notebook scan <ExternalLink size={11} />
                      </a>
                    ) : (
                      <span className="text-xs text-slate-400 italic">no scan link for this notebook</span>
                    )}
                  </div>
                  <dl className="px-5 py-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-3">
                    {queue.fields.map(field => {
                      const v = val(row, field);
                      return (
                        <div key={field}>
                          <dt className="text-[9px] font-bold uppercase tracking-wider text-slate-400">{field}</dt>
                          <dd className={`text-xs mt-0.5 break-words ${v ? 'text-slate-700 font-medium' : 'text-slate-300 italic'}`}>
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
        )}
      </div>

      <HelpPanel title="How to use this" sections={HELP} storageKey="help.review" />
    </div>
  );
};

export default ReviewView;
