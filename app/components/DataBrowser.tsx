
import React, { useState, useMemo, useEffect } from 'react';
import { Search, Filter, Columns, ChevronLeft, ChevronRight, Hash, X, Plus, SlidersHorizontal, Download, ArrowUp, ArrowDown, ChevronsUpDown } from 'lucide-react';
import { RegistryRecord, ColumnConfig, FilterState } from '../types';
import FilterSidebar from './FilterSidebar';
import HelpPanel, { HelpSection } from './HelpPanel';
import { UNKNOWN } from '../facets';

declare const Papa: any;

const HELP: HelpSection[] = [
  {
    heading: 'What a row is',
    body: <p>One row is one admission, in the order the clerk entered it in the register. The same patient readmitted appears as a second row; the registers give no patient identifier, so the table cannot be counted as a count of people.</p>
  },
  {
    heading: 'As written, and standardized',
    body: <p>Where a field was cleaned, two columns exist: the plain name holds the standardized value, and <em>… as written</em> holds what the clerk actually wrote. The table shows the standardized ones by default; open <strong>Columns</strong> to add the verbatim originals. For any argument that rests on wording, read the “as written” column.</p>
  },
  {
    heading: 'Reading a cell in full',
    body: <p>The table truncates long values to stay scannable — diagnoses especially, which are often the longest thing in the register. Hovering a cell shows the whole of it; clicking anywhere in the row opens the record entire, with every column the dataset carries, including the ones hidden from the table and the <em>… as written</em> originals. The text there can be selected and copied. <kbd>Esc</kbd> closes it.</p>
  },
  {
    heading: 'Sorting, and getting back',
    body: <p>Click a column heading to sort by it — ascending, then descending, then back to register order. Numeric columns such as <em>Age</em> and <em>Days in Hospital</em> sort as numbers; blanks always sink to the bottom, in either direction, so reversing the order never fills the first page with records that say nothing about the column you sorted on. Register order is the default and is worth returning to: it is the sequence the clerk wrote the admissions in, which carries information no sort preserves.</p>
  },
  {
    heading: 'How the filters combine',
    body: <p>A facet with several values ticked matches any of them. Different facets, the search box, the advanced criteria and the sliders all have to be satisfied at once. The record count at the top right is the size of the current selection.</p>
  },
  {
    heading: `The “${UNKNOWN}” bucket`,
    body: <p>Each facet lists its ten most frequent values, with <em>{UNKNOWN}</em> pinned below them. It counts the records where the register leaves the field blank — an absence in the source, not a value. Selecting it isolates exactly those records; <strong>View all</strong> lists the recorded values beyond the top ten.</p>
  },
  {
    heading: 'Export',
    body: <p>Export writes the current selection as CSV, with the columns you have chosen to display. It is the selection, not the whole dataset.</p>
  }
];

interface DataBrowserProps {
  data: RegistryRecord[];
  filteredData: RegistryRecord[];
  filterState: FilterState;
  setFilterState: React.Dispatch<React.SetStateAction<FilterState>>;
  columns: ColumnConfig[];
  visibleColumns: ColumnConfig[];
  onToggleColumn: (key: string) => void;
}

const DataBrowser: React.FC<DataBrowserProps> = ({ 
  data, 
  filteredData, 
  filterState, 
  setFilterState, 
  columns, 
  visibleColumns, 
  onToggleColumn 
}) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [showColumnPicker, setShowColumnPicker] = useState(false);
  const [showFacetPanel, setShowFacetPanel] = useState(true);
  const [showAdvancedSearch, setShowAdvancedSearch] = useState(false);
  // null is register order — the sequence the clerk wrote the admissions in,
  // which is itself information and so stays the default and stays reachable.
  const [sort, setSort] = useState<{ key: string; dir: 'asc' | 'desc' } | null>(null);
  // A cell is truncated to keep the table scannable, but a diagnosis is often
  // the longest field in the register and the whole of it is the point. Clicking
  // any cell opens the record entire — every column, not just the visible ones,
  // so the "as written" originals are one click away from the standardized value.
  const [detailRow, setDetailRow] = useState<RegistryRecord | null>(null);

  const pageSize = 50;

  const sortedData = useMemo(() => {
    if (!sort) return filteredData;
    const { key, dir } = sort;
    const sign = dir === 'asc' ? 1 : -1;
    // A blank is an absence, not a low value: it sorts to the bottom in both
    // directions, so that reversing the order never fills the first page with
    // records that have nothing in the column being sorted on.
    const rank = (v: unknown): { blank: boolean; num: number | null; str: string } => {
      if (v === null || v === undefined) return { blank: true, num: null, str: '' };
      const s = String(v).trim();
      if (s === '' || s === 'null' || s === 'undefined') return { blank: true, num: null, str: '' };
      const n = Number(s);
      return { blank: false, num: s !== '' && Number.isFinite(n) ? n : null, str: s };
    };
    // slice() first: filteredData is the parent's memo, and sorting in place
    // would reorder the array every other view is reading.
    return filteredData.slice().sort((a, b) => {
      const x = rank(a[key]);
      const y = rank(b[key]);
      if (x.blank || y.blank) return x.blank === y.blank ? 0 : x.blank ? 1 : -1;
      if (x.num !== null && y.num !== null) return (x.num - y.num) * sign;
      return x.str.localeCompare(y.str, undefined, { numeric: true }) * sign;
    });
  }, [filteredData, sort]);

  const totalPages = Math.ceil(sortedData.length / pageSize);
  const paginatedData = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sortedData.slice(start, start + pageSize);
  }, [sortedData, currentPage]);

  useEffect(() => {
    setCurrentPage(1);
  }, [filterState, sort]);

  // The page box is free text while being typed, so a half-typed "1" on the way
  // to "120" does not jump the table. It commits on Enter or blur, clamped to
  // the range; anything unreadable falls back to the page already shown.
  const [pageInput, setPageInput] = useState('1');
  useEffect(() => { setPageInput(String(currentPage)); }, [currentPage]);

  const commitPage = () => {
    const wanted = parseInt(pageInput, 10);
    if (!Number.isFinite(wanted)) return setPageInput(String(currentPage));
    const clamped = Math.min(Math.max(wanted, 1), Math.max(totalPages, 1));
    setCurrentPage(clamped);
    setPageInput(String(clamped));
  };

  useEffect(() => {
    if (!detailRow) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setDetailRow(null); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [detailRow]);

  // Ascending, then descending, then back to register order — so the default is
  // one more click away rather than something to hunt for.
  const cycleSort = (key: string) => {
    setSort(prev =>
      !prev || prev.key !== key
        ? { key, dir: 'asc' }
        : prev.dir === 'asc'
          ? { key, dir: 'desc' }
          : null
    );
  };

  const addAdvancedSearch = () => {
    setFilterState(prev => ({
      ...prev,
      advancedSearch: [...prev.advancedSearch, { column: columns[0].key, query: '' }]
    }));
  };

  const handleDownloadCSV = () => {
    if (sortedData.length === 0) return;
    const exportColumns = visibleColumns.map(c => c.key);
    // In the order on screen, sort included: a file that came out in a different
    // order from the table it was exported from would be a trap.
    const exportData = sortedData.map(row => {
      const filteredRow: Record<string, any> = {};
      exportColumns.forEach(col => { filteredRow[col] = row[col]; });
      return filteredRow;
    });
    const csv = Papa.unparse(exportData);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `hospital_registry_selection_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="flex w-full h-full overflow-hidden relative">
      {showFacetPanel && (
        <FilterSidebar 
          data={data} 
          filterState={filterState} 
          setFilterState={setFilterState} 
        />
      )}

      <div className="flex-1 flex flex-col min-w-0 bg-white">
        <div className="p-4 border-b border-slate-200 flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3 flex-1 min-w-[300px]">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                <input type="text" placeholder="Global search..." className="w-full pl-10 pr-4 py-2 bg-slate-100 border-none rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none" value={filterState.searchQuery} onChange={(e) => setFilterState(prev => ({ ...prev, searchQuery: e.target.value }))} />
              </div>
              <button onClick={() => setShowFacetPanel(!showFacetPanel)} className={`p-2 rounded-lg border transition-colors ${showFacetPanel ? 'bg-indigo-50 border-indigo-200 text-indigo-600' : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'}`}><Filter size={18} /></button>
              <button onClick={() => setShowAdvancedSearch(!showAdvancedSearch)} className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${showAdvancedSearch ? 'bg-indigo-50 border-indigo-200 text-indigo-600' : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'}`}><SlidersHorizontal size={18} /> Advanced</button>
              
              <div className="relative">
                <button onClick={() => setShowColumnPicker(!showColumnPicker)} className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${showColumnPicker ? 'bg-indigo-50 border-indigo-200 text-indigo-600' : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'}`}><Columns size={18} /> Columns</button>
                {showColumnPicker && (
                  <div className="absolute left-0 top-full mt-2 w-64 bg-white border border-slate-200 shadow-xl rounded-xl p-4 z-50 max-h-[60vh] overflow-y-auto">
                    <h5 className="font-bold text-slate-800 mb-3 text-sm">Configure Display</h5>
                    <div className="space-y-1">
                      {columns.map(col => (
                        <label key={col.key} className="flex items-center p-2 hover:bg-slate-50 rounded-lg cursor-pointer transition-colors group">
                          <input type="checkbox" checked={col.visible} onChange={() => onToggleColumn(col.key)} className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
                          <span className="ml-3 text-xs text-slate-700 group-hover:text-slate-900 truncate">{col.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <button onClick={handleDownloadCSV} disabled={filteredData.length === 0} className="flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-600 text-sm font-medium hover:bg-slate-50 transition-colors disabled:opacity-30"><Download size={18} /> Export</button>
            </div>

            <div className="flex items-center gap-4">
              {sort && (
                <button
                  onClick={() => setSort(null)}
                  className="flex items-center gap-1.5 text-xs font-medium text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-lg px-2.5 py-1.5 hover:bg-indigo-100 transition-colors whitespace-nowrap"
                  title="Return to the order the clerk entered the admissions in"
                >
                  sorted by {columns.find(c => c.key === sort.key)?.label || sort.key}
                  {sort.dir === 'asc' ? <ArrowUp size={11} /> : <ArrowDown size={11} />}
                  <X size={12} className="text-indigo-400" />
                </button>
              )}
              <div className="text-sm text-slate-500 whitespace-nowrap"><span className="font-bold text-slate-800">{filteredData.length.toLocaleString()}</span> records</div>
              <div className="flex items-center bg-slate-100 rounded-lg p-1">
                <button disabled={currentPage === 1} onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))} className="p-1.5 rounded-md hover:bg-white disabled:opacity-30"><ChevronLeft size={18} /></button>
                <div className="px-2 flex items-center gap-1 text-xs font-bold text-slate-600 font-mono">
                  <input
                    type="text"
                    inputMode="numeric"
                    aria-label="Page number"
                    value={pageInput}
                    onChange={(e) => setPageInput(e.target.value.replace(/[^0-9]/g, ''))}
                    onFocus={(e) => e.target.select()}
                    onBlur={commitPage}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
                      if (e.key === 'Escape') { setPageInput(String(currentPage)); (e.target as HTMLInputElement).blur(); }
                    }}
                    style={{ width: `${Math.max(2, String(totalPages || 1).length) + 1}ch` }}
                    className="bg-transparent text-center text-slate-800 outline-none focus:bg-white rounded px-1 py-0.5 focus:ring-1 focus:ring-indigo-400"
                  />
                  <span className="text-slate-400">/ {totalPages || 1}</span>
                </div>
                <button disabled={currentPage === totalPages || totalPages === 0} onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))} className="p-1.5 rounded-md hover:bg-white disabled:opacity-30"><ChevronRight size={18} /></button>
              </div>
            </div>
          </div>

          {showAdvancedSearch && (
            <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
              <div className="flex flex-col gap-2">
                {filterState.advancedSearch.map((adv, idx) => (
                  <div key={idx} className="flex gap-2 items-center">
                    <select value={adv.column} onChange={(e) => { const next = [...filterState.advancedSearch]; next[idx].column = e.target.value; setFilterState(prev => ({ ...prev, advancedSearch: next })); }} className="bg-white border border-slate-200 rounded-lg px-2 py-1.5 text-xs">
                      {columns.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
                    </select>
                    <input type="text" placeholder="Search term..." value={adv.query} onChange={(e) => { const next = [...filterState.advancedSearch]; next[idx].query = e.target.value; setFilterState(prev => ({ ...prev, advancedSearch: next })); }} className="flex-1 bg-white border border-slate-200 rounded-lg px-3 py-1.5 text-xs" />
                    <button onClick={() => { const next = filterState.advancedSearch.filter((_, i) => i !== idx); setFilterState(prev => ({ ...prev, advancedSearch: next })); }} className="text-slate-400 hover:text-red-500"><X size={14} /></button>
                  </div>
                ))}
                <button onClick={addAdvancedSearch} className="flex items-center gap-2 text-indigo-600 text-xs font-bold"><Plus size={14} /> Add criteria</button>
              </div>
            </div>
          )}
        </div>

        <div className="flex-1 overflow-auto relative">
          <table className="w-full text-left border-collapse table-fixed">
            <thead className="sticky top-0 z-10 bg-slate-50/95 backdrop-blur-sm border-b border-slate-200 shadow-sm text-[10px] font-bold text-slate-400 uppercase tracking-wider">
              <tr>
                <th className="w-12 px-4 py-3 text-center">#</th>
                {visibleColumns.map(col => {
                  const active = sort?.key === col.key;
                  return (
                    <th key={col.key} className="px-4 py-3 min-w-[150px]">
                      <button
                        onClick={() => cycleSort(col.key)}
                        title={active && sort?.dir === 'desc' ? 'Return to register order' : `Sort by ${col.label}`}
                        // w-full + min-w-0 on both: without them the flex child
                        // refuses to shrink below its text and a long header
                        // runs out over the next column.
                        className={`flex w-full min-w-0 items-center gap-1 uppercase tracking-wider transition-colors ${active ? 'text-indigo-600' : 'text-slate-400 hover:text-slate-600'}`}
                      >
                        <span className="truncate min-w-0">{col.label}</span>
                        {active
                          ? (sort!.dir === 'asc' ? <ArrowUp size={11} className="shrink-0" /> : <ArrowDown size={11} className="shrink-0" />)
                          : <ChevronsUpDown size={11} className="shrink-0 opacity-40" />}
                      </button>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {paginatedData.map((row, idx) => (
                <tr
                  key={idx}
                  onClick={() => setDetailRow(row)}
                  className="hover:bg-indigo-50/30 transition-colors cursor-pointer"
                  title="Open the whole record"
                >
                  <td className="px-4 py-3 text-xs text-slate-400 font-mono text-center">{(currentPage - 1) * pageSize + idx + 1}</td>
                  {visibleColumns.map(col => (
                    // title= gives the untruncated value on hover; the click gives
                    // it somewhere it can be selected and copied.
                    <td key={col.key} className="px-4 py-3 text-xs text-slate-600 truncate font-medium" title={String(row[col.key] ?? '')}>
                      {row[col.key] || '-'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {paginatedData.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 py-20">
              <Hash size={48} strokeWidth={1} className="mb-2" />
              <p className="font-medium">No records found matching your criteria</p>
            </div>
          )}
        </div>
      </div>

      {detailRow && (
        <div
          className="fixed inset-0 z-[60] bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-6"
          onClick={() => setDetailRow(null)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col overflow-hidden"
            onClick={e => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Full record"
          >
            <div className="flex items-start justify-between gap-4 p-5 border-b border-slate-200">
              <div>
                <h4 className="font-bold text-slate-800">One admission, in full</h4>
                <p className="text-xs text-slate-500 mt-1">
                  Every column the dataset carries, blanks included — an empty field is an absence
                  in the register, not a value.
                </p>
              </div>
              <button
                onClick={() => setDetailRow(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors shrink-0"
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>
            <div className="overflow-y-auto p-5">
              <dl className="divide-y divide-slate-100">
                {columns.map(col => {
                  const raw = detailRow[col.key];
                  const empty = raw === null || raw === undefined || String(raw).trim() === '';
                  return (
                    <div key={col.key} className="grid grid-cols-[minmax(0,14rem)_1fr] gap-4 py-2">
                      <dt className="text-[10px] font-bold uppercase tracking-wider text-slate-400 pt-0.5 break-words">
                        {col.label}
                      </dt>
                      {/* whitespace-pre-wrap + break-words: the long diagnosis strings
                          wrap here rather than being cut off, which is the whole
                          reason this panel exists. */}
                      <dd className={`text-xs whitespace-pre-wrap break-words ${empty ? 'text-slate-300 italic' : 'text-slate-700 font-medium select-text'}`}>
                        {empty ? `${UNKNOWN}`
                          : col.key === 'City Wikidata' ? (
                            <a href={`https://www.wikidata.org/wiki/${String(raw)}`} target="_blank" rel="noreferrer" className="text-indigo-600 underline">{String(raw)}</a>
                          ) : col.key === 'City Kima ID' ? (
                            <a href={`https://data.geo-kima.org/Places/Details/${String(raw)}`} target="_blank" rel="noreferrer" className="text-indigo-600 underline">{String(raw)}</a>
                          ) : String(raw)}
                      </dd>
                    </div>
                  );
                })}
              </dl>
            </div>
          </div>
        </div>
      )}

      <HelpPanel title="How to read this" sections={HELP} storageKey="help.browse" />
    </div>
  );
};

export default DataBrowser;
