
import React, { useState, useMemo, useEffect } from 'react';
import { Search, Filter, Columns, ChevronLeft, ChevronRight, Hash, X, Plus, SlidersHorizontal, Download } from 'lucide-react';
import { RegistryRecord, ColumnConfig, FilterState } from '../types';
import FilterSidebar from './FilterSidebar';

declare const Papa: any;

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
  
  const pageSize = 50;

  const totalPages = Math.ceil(filteredData.length / pageSize);
  const paginatedData = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredData.slice(start, start + pageSize);
  }, [filteredData, currentPage]);

  useEffect(() => {
    setCurrentPage(1);
  }, [filterState]);

  const addAdvancedSearch = () => {
    setFilterState(prev => ({
      ...prev,
      advancedSearch: [...prev.advancedSearch, { column: columns[0].key, query: '' }]
    }));
  };

  const handleDownloadCSV = () => {
    if (filteredData.length === 0) return;
    const exportColumns = visibleColumns.map(c => c.key);
    const exportData = filteredData.map(row => {
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
              <div className="text-sm text-slate-500 whitespace-nowrap"><span className="font-bold text-slate-800">{filteredData.length.toLocaleString()}</span> records</div>
              <div className="flex items-center bg-slate-100 rounded-lg p-1">
                <button disabled={currentPage === 1} onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))} className="p-1.5 rounded-md hover:bg-white disabled:opacity-30"><ChevronLeft size={18} /></button>
                <span className="px-3 text-xs font-bold text-slate-600 font-mono">{currentPage} / {totalPages || 1}</span>
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
                {visibleColumns.map(col => <th key={col.key} className="px-4 py-3 min-w-[150px]">{col.label}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {paginatedData.map((row, idx) => (
                <tr key={idx} className="hover:bg-indigo-50/30 transition-colors">
                  <td className="px-4 py-3 text-xs text-slate-400 font-mono text-center">{(currentPage - 1) * pageSize + idx + 1}</td>
                  {visibleColumns.map(col => <td key={col.key} className="px-4 py-3 text-xs text-slate-600 truncate font-medium">{row[col.key] || '-'}</td>)}
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
    </div>
  );
};

export default DataBrowser;
